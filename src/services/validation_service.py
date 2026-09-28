"""Loads everything Pipeline 2 needs, runs the pure engine off the event loop,
and stores the result. No generative model is involved at any point."""
import asyncio
import hashlib
import json
import uuid

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from src.comparison_engine.status import VerificationInputs, derive_plan_status
from src.contradiction_checks.detector import ChunkFact, PolarityChecker, detect_corpus
from src.core.app_config import get_config, set_config
from src.core.exceptions import NotFoundError, ValidationFailedError
from src.document_processing.embeddings import embed_texts
from src.python_validation import engine
from src.python_validation.base import ActiveChunk, ValidationContext
from src.models.validation import ValidationFinding, ValidationResult
from src.repositories.document import ChunkRepository, DocumentRepository
from src.repositories.organization import StageRepository
from src.repositories.plan import PlanRepository
from src.repositories.requirement import PrerequisiteRepository, RequirementRepository, RoleRepository, RoleRequirementRepository
from src.repositories.validation import ValidationRepository
from src.services.audit_service import AuditService
from src.services.matrix_service import MatrixService, requirement_dict
from src.services.plan_views import flat_items, plan_dict

UNSUPPORTED_RULES = {"coverage", "hallucination"}


class CachedEmbedder:
    def __init__(self):
        self.cache: dict[str, np.ndarray] = {}

    def __call__(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if missing:
            for text, vector in zip(missing, embed_texts(missing)):
                self.cache[text] = np.asarray(vector, dtype=np.float32)
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        return np.stack([self.cache[t] for t in texts])


def fingerprint(f: dict) -> str:
    key = json.dumps([f["rule"], f["item_type"], f["item_id"], f["requirement_code"], f["message"]], sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()


class ValidationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plans = PlanRepository(session)
        self.results = ValidationRepository(session)
        self.documents = DocumentRepository(session)
        self.chunks = ChunkRepository(session)
        self.requirements = RequirementRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------ corpus
    async def corpus_contradictions(self, include_obsolete: bool = True) -> list[dict]:
        config = await get_config(self.session, "validation_rules")
        settings = (config.get("rules", {}) or {}).get("contradictions", {}) or {}
        facts = []
        for chunk, doc in await self.chunks.with_documents(active_only=not include_obsolete):
            if chunk.is_suspicious:
                continue
            facts.append(ChunkFact(
                chunk.chunk_code, str(doc.id), doc.document_code, doc.document_type.value, doc.version,
                doc.status.value, doc.precedence_rank, doc.effective_date, chunk.section_id, chunk.content,
                np.asarray(chunk.embedding, dtype=np.float32) if chunk.embedding is not None else None,
            ))
        polarity = PolarityChecker(config.get("permissive_patterns", []), config.get("prohibitive_patterns", []))
        # Role titles are the subject of an obligation, never its object.
        subjects = [r.title for r in await RoleRepository(self.session).list()]
        found = await asyncio.to_thread(
            lambda: detect_corpus(
                facts, polarity,
                pair_similarity=float(settings.get("pair_similarity", 0.55)),
                polarity_similarity=float(settings.get("polarity_similarity", 0.45)),
                min_overlap=float(settings.get("min_overlap", 0.6)),
                min_shared=int(settings.get("min_shared_terms", 2)),
                generic_terms=set(settings.get("generic_terms", []) or []),
                subject_phrases=subjects,
                ignore_patterns=settings.get("ignore_sentence_patterns", []),
                numeric_min_jaccard=float(settings.get("numeric_min_jaccard", 0.55)),
            )
        )
        return [c.as_dict() for c in found]

    # ------------------------------------------------------------ context
    async def build_context(self, plan_id: uuid.UUID) -> tuple[ValidationContext, dict]:
        plan = await self.plans.full(plan_id)
        if plan is None:
            raise NotFoundError("Plan not found")
        serial = plan_dict(plan)
        serial["raw_response"] = plan.raw_response
        role = await RoleRepository(self.session).get(plan.job_role_id)
        roles = await RoleRepository(self.session).list()
        matrix = (await MatrixService(self.session).role_matrix(plan.job_role_id))["requirements"]

        all_reqs = await self.requirements.list()
        titles = {r.id: r.title for r in roles}
        req_roles: dict[str, list[str]] = {}
        id_to_code = {r.id: r.requirement_code for r in all_reqs}
        for mapping, job_role in await RoleRequirementRepository(self.session).roles_for_requirements(list(id_to_code)):
            req_roles.setdefault(id_to_code[mapping.requirement_id], []).append(job_role.title)

        documents = {}
        for d in await self.documents.list_all():
            documents[str(d.id)] = {"id": str(d.id), "document_code": d.document_code, "version": d.version,
                                    "status": d.status.value, "document_type": d.document_type.value,
                                    "precedence_rank": d.precedence_rank}
        sections: dict[str, set] = {}
        doc_chunks: dict[str, dict] = {}
        chunk_text: dict[tuple, str] = {}
        active, vectors = [], []
        for chunk, doc in await self.chunks.with_documents(active_only=False):
            did = str(doc.id)
            if chunk.section_id:
                sections.setdefault(did, set()).add(chunk.section_id)
            doc_chunks.setdefault(did, {})[chunk.chunk_code] = chunk.section_id
            chunk_text[(did, chunk.chunk_code)] = chunk.content
            if doc.status.value == "ACTIVE" and chunk.embedding is not None and not chunk.is_suspicious:
                active.append(ActiveChunk(chunk.chunk_code, did, doc.document_code, chunk.section_id, chunk.content))
                vectors.append(np.asarray(chunk.embedding, dtype=np.float32))

        prereqs = [
            (id_to_code.get(p.requirement_id), id_to_code.get(p.depends_on_requirement_id), p.reason)
            for p in await PrerequisiteRepository(self.session).all_edges()
        ]
        stages = {s.code: {"sequence": s.sequence, "offset_days": s.offset_days, "name": s.name}
                  for s in await StageRepository(self.session).list() if s.is_active}
        quiz_types = {t["code"] for t in (await get_config(self.session, "quiz_types")).get("types", [])}
        config = await get_config(self.session, "validation_rules")
        business = (await get_config(self.session, "business_rules")).get("rules", [])

        ctx = ValidationContext(
            plan=serial, items=flat_items(serial),
            role={"id": str(role.id), "code": role.code, "title": role.title},
            known_role_codes={r.code for r in roles}, matrix=matrix,
            requirements={r.requirement_code: requirement_dict(r) for r in all_reqs},
            requirement_roles=req_roles, documents=documents, document_sections=sections,
            document_chunks=doc_chunks, active_chunks=active,
            active_vectors=np.stack(vectors) if vectors else np.zeros((0, 384), dtype=np.float32),
            chunk_text=chunk_text, prerequisites=[p for p in prereqs if p[0] and p[1]],
            stages=stages, quiz_types=quiz_types, config=config, business_rules=business,
            contradictions=await self.corpus_contradictions(), embed=CachedEmbedder(),
        )
        return ctx, {"plan": plan, "config": config, "business": business}

    # ------------------------------------------------------------ run
    async def run(self, plan_id: uuid.UUID) -> dict:
        ctx, extra = await self.build_context(plan_id)
        report = await asyncio.to_thread(engine.run, ctx)
        plan = extra["plan"]
        carried = await self.results.decided_fingerprints(plan_id)

        result = ValidationResult(
            plan_id=plan_id,
            rule_set_version=engine.rule_set_version(extra["config"], extra["business"]),
            rule_config={"validation_rules": extra["config"], "business_rules": extra["business"]},
            enabled_rules=report["enabled_rules"],
            extra_metrics=report["extra_metrics"],
            counts_by_severity=report["counts_by_severity"],
            rule_summaries=report["rule_summaries"],
            duration_ms=report["duration_ms"],
            verification_status="PENDING",
            **report["metrics"],
        )
        self.session.add(result)
        await self.session.flush()
        open_findings = []
        for f in report["findings"]:
            fp = fingerprint(f)
            status = carried.get(fp, "OPEN")
            row = ValidationFinding(
                result_id=result.id, plan_id=plan_id, rule_name=f["rule"], severity=f["severity"],
                item_type=f["item_type"], item_id=f["item_id"], requirement_code=f["requirement_code"],
                item_status=f["item_status"], message=f["message"], evidence=_jsonable(f["evidence"]),
                fingerprint=fp, review_status=status,
            )
            self.session.add(row)
            if status not in ("APPROVED",):
                open_findings.append(f)

        inputs = self.verification_inputs(report["metrics"], open_findings)
        status, reasons = derive_plan_status(inputs)
        result.verification_status = status
        result.is_verified = status in ("VERIFIED", "VERIFIED_WITH_WARNING")
        result.status_reasons = reasons
        plan.verification_status = status
        if plan.status in ("GENERATED", "VALIDATED"):
            plan.status = "VALIDATED"
        self.audit.record("plan", plan_id, "validated",
                          after={"verification_status": status, "metrics": report["metrics"],
                                 "rule_set_version": result.rule_set_version})
        await self.session.commit()
        return await self.get_result(plan_id)

    @staticmethod
    def verification_inputs(metrics: dict, open_findings: list[dict]) -> VerificationInputs:
        blocking_rules = {"traceability", "contradictions", *UNSUPPORTED_RULES}
        return VerificationInputs(
            coverage_percent=metrics.get("mandatory_requirement_coverage_score") or 0.0,
            invalid_or_outdated_references=sum(
                1 for f in open_findings if f["rule"] == "traceability"),
            unresolved_contradictions=sum(
                1 for f in open_findings if f["rule"] == "contradictions" and f["severity"] in ("ERROR", "CRITICAL")),
            unsupported_requirements=sum(
                1 for f in open_findings if f["rule"] in UNSUPPORTED_RULES
                and f["item_status"] == "UNSUPPORTED_REQUIREMENT"),
            open_errors=sum(1 for f in open_findings if f["severity"] in ("ERROR", "CRITICAL")
                            and f["rule"] not in blocking_rules),
            open_warnings=sum(1 for f in open_findings if f["severity"] == "WARNING"),
        )

    # ------------------------------------------------------------ reads
    def _result_dict(self, r: ValidationResult) -> dict:
        return {
            "id": str(r.id), "plan_id": str(r.plan_id), "run_at": r.run_at.isoformat() if r.run_at else None,
            "rule_set_version": r.rule_set_version, "enabled_rules": r.enabled_rules,
            "verification_status": r.verification_status, "is_verified": r.is_verified,
            "status_reasons": r.status_reasons,
            "metrics": {
                "mandatory_requirement_coverage_score": r.mandatory_requirement_coverage_score,
                "source_traceability_score": r.source_traceability_score,
                "requirement_consistency_score": r.requirement_consistency_score,
                "missing_requirement_count": r.missing_requirement_count,
                "unsupported_requirement_count": r.unsupported_requirement_count,
                "contradiction_count": r.contradiction_count,
            },
            "extra_metrics": r.extra_metrics, "counts_by_severity": r.counts_by_severity,
            "rule_summaries": r.rule_summaries, "duration_ms": r.duration_ms,
        }

    @staticmethod
    def finding_dict(f: ValidationFinding) -> dict:
        return {"id": str(f.id), "result_id": str(f.result_id), "plan_id": str(f.plan_id), "rule": f.rule_name,
                "severity": f.severity, "item_type": f.item_type, "item_id": f.item_id,
                "requirement_code": f.requirement_code, "item_status": f.item_status, "message": f.message,
                "evidence": f.evidence, "review_status": f.review_status,
                "created_at": f.created_at.isoformat() if f.created_at else None}

    async def get_result(self, plan_id: uuid.UUID, include_findings: bool = True) -> dict:
        result = await self.results.latest(plan_id)
        if result is None:
            raise NotFoundError("This plan has not been validated yet. POST /validation/run/{plan_id}")
        data = self._result_dict(result)
        if include_findings:
            data["findings"] = [self.finding_dict(f) for f in await self.results.findings(result.id)]
        return data

    async def findings(self, plan_id: uuid.UUID, rule: str | None, severity: str | None) -> list[dict]:
        result = await self.results.latest(plan_id)
        if result is None:
            raise NotFoundError("This plan has not been validated yet")
        return [self.finding_dict(f) for f in await self.results.findings(result.id, rule, severity)]

    async def rules(self) -> dict:
        config = await get_config(self.session, "validation_rules")
        settings = config.get("rules", {}) or {}
        return {
            "version": config.get("version"),
            "rules": [
                {**r, "enabled": (settings.get(r["name"], {}) or {}).get("enabled", True),
                 "settings": settings.get(r["name"], {}) or {}}
                for r in engine.available_rules()
            ],
            "business_rules": (await get_config(self.session, "business_rules")).get("rules", []),
        }

    async def update_rules(self, changes: dict[str, dict], actor_id) -> dict:
        known = {r["name"] for r in engine.available_rules()}
        unknown = set(changes) - known
        if unknown:
            raise ValidationFailedError(f"Unknown rule(s): {', '.join(sorted(unknown))}",
                                        details={"known": sorted(known)})
        config = dict(await get_config(self.session, "validation_rules"))
        rules = {k: dict(v or {}) for k, v in (config.get("rules") or {}).items()}
        for name, patch in changes.items():
            rules.setdefault(name, {}).update(patch)
        config["rules"] = rules
        config["version"] = int(config.get("version", 1)) + 1
        await set_config(self.session, "validation_rules", config, description="Validation rules updated at runtime")
        self.audit.record("config", "validation_rules", "updated", actor_id=actor_id, after=changes)
        await self.session.commit()
        return await self.rules()


def _jsonable(value):
    return json.loads(json.dumps(value, default=str))
