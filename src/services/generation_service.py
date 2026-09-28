"""Pipeline 1: the GenAI generation pipeline (SRS Steps 13-24, 39-42).

It generates only. It never validates, approves or scores; that is Pipeline 2.
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import get_config
from src.core.exceptions import NotFoundError, ValidationFailedError
from src.document_processing.embeddings import embed_texts
from src.genai_pipeline import prompts
from src.genai_pipeline.client import GenAIError, GenAIRequest, generate_with_fallback
from src.genai_pipeline.factory import build_chain
from src.models.enums import DocumentStatus
from src.models.plan import GenerationRun, OnboardingPlan, PromptTemplate
from src.repositories.document import ChunkRepository, DocumentRepository
from src.repositories.organization import DepartmentRepository, EmployeeRepository, JobRoleRepository, StageRepository
from src.repositories.plan import GenerationRunRepository, PlanRepository, PromptTemplateRepository
from src.schemas.generation import GeneratedModules, GeneratedPlan
from src.services.audit_service import AuditService
from src.services.matrix_service import MatrixService
from src.services.plan_views import plan_dict

logger = logging.getLogger("skillsprint.generation")
COMPANY = "Nexora Labs"


class GenerationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.plans = PlanRepository(session)
        self.runs = GenerationRunRepository(session)
        self.templates = PromptTemplateRepository(session)
        self.chunks = ChunkRepository(session)
        self.documents = DocumentRepository(session)
        self.employees = EmployeeRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------ templates
    async def register_templates(self) -> list[dict]:
        """Records every template on disk, so the prompt actually used is stored."""
        registered = []
        for spec in prompts.manifest():
            row = await self.templates.find(spec.name, spec.version)
            digest = spec.content_hash
            if row is None:
                row = PromptTemplate(name=spec.name, version=spec.version, purpose=spec.purpose,
                                     file_path=f"prompt_templates/{spec.file}", content_hash=digest,
                                     output_schema=spec.output_schema, is_active=True)
                self.session.add(row)
            elif row.content_hash != digest:
                logger.warning("Prompt %s %s changed on disk; recording the new hash. Released versions "
                               "should not be edited in place.", spec.name, spec.version)
                row.content_hash = digest
            registered.append(spec)
        await self.session.commit()
        return [{"name": s.name, "version": s.version, "hash": s.content_hash} for s in registered]

    async def list_templates(self) -> list[dict]:
        return [
            {"id": str(t.id), "name": t.name, "version": t.version, "purpose": t.purpose,
             "file_path": t.file_path, "content_hash": t.content_hash, "output_schema": t.output_schema,
             "is_active": t.is_active, "created_at": t.created_at.isoformat() if t.created_at else None}
            for t in await self.templates.all()
        ]

    # ------------------------------------------------------------ context
    async def _employee_bundle(self, employee_id: uuid.UUID):
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("Employee not found")
        role = await JobRoleRepository(self.session).get(employee.job_role_id)
        department = await DepartmentRepository(self.session).get(employee.department_id)
        stages = sorted([s for s in await StageRepository(self.session).list() if s.is_active],
                        key=lambda s: s.sequence)
        if not stages:
            raise ValidationFailedError("No active onboarding stages are configured")
        return employee, role, department, stages

    async def build_context(
        self,
        employee_id: uuid.UUID,
        requirement_codes: set[str] | None = None,
        extra_topics: list[str] | None = None,
        fixed_chunk_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        config = await get_config(self.session, "generation")
        retrieval = config.get("retrieval", {})
        floor = float(retrieval.get("min_similarity", 0.45))
        per_req = int(retrieval.get("per_requirement", 3))
        employee, role, department, stages = await self._employee_bundle(employee_id)

        matrix = await MatrixService(self.session).role_matrix(role.id)
        requirements = matrix["requirements"]
        if requirement_codes is not None:
            requirements = [r for r in requirements if r["requirement_code"] in requirement_codes]
        if not requirements:
            raise ValidationFailedError(
                f"The {role.title} role has no Matrix requirements. Run /matrix/extract and "
                "/matrix/map-roles first."
            )

        pool = await self.chunks.with_documents(active_only=True, embedded_only=True)
        by_code = {(c.chunk_code, str(d.id)): (c, d) for c, d in pool}
        by_chunk_code = {}
        for c, d in pool:
            by_chunk_code.setdefault(c.chunk_code, (c, d))
        allowed = set(fixed_chunk_codes) if fixed_chunk_codes else None

        queries = [r["statement"] for r in requirements]
        topics = list(dict.fromkeys((extra_topics or []) + list(employee.required_competencies or [])))
        vectors = await asyncio.to_thread(embed_texts, queries + topics)
        # Score every query against every active chunk in one matrix product,
        # rather than one index query per requirement.
        pool_matrix = np.array([c.embedding for c, _ in pool], dtype=np.float32) if pool else \
            np.zeros((0, 384), dtype=np.float32)
        scores = np.asarray(vectors, dtype=np.float32) @ pool_matrix.T if len(pool) else None

        def nearest(row: int, limit: int) -> list[tuple]:
            if scores is None:
                return []
            order = np.argsort(-scores[row])[:limit]
            return [(pool[i][0], pool[i][1], float(scores[row, i])) for i in order]

        used: dict[str, tuple] = {}
        excluded: dict[str, dict] = {}
        gaps: list[dict] = []
        context_reqs: list[dict] = []

        def admit(chunk, doc) -> bool:
            if chunk.is_suspicious:
                if chunk.chunk_code not in excluded:
                    excluded[chunk.chunk_code] = {"chunk_code": chunk.chunk_code, "reasons": chunk.suspicion_reasons}
                    logger.warning("Excluded suspicious chunk %s from the prompt", chunk.chunk_code)
                return False
            if allowed is not None and chunk.chunk_code not in allowed:
                return False
            return True

        for row, req in enumerate(requirements):
            chosen: list[tuple] = []
            source = by_chunk_code.get(req["source_chunk_code"]) if req["source_chunk_code"] else None
            if source and source[1].status == DocumentStatus.ACTIVE and admit(*source):
                chosen.append(source)
            for chunk, doc, similarity in nearest(row, per_req + 2):
                if similarity < floor or not admit(chunk, doc):
                    continue
                if all(chunk.id != c.id for c, _ in chosen):
                    chosen.append((chunk, doc))
                if len(chosen) >= per_req:
                    break
            if not chosen:
                gaps.append({
                    "topic": req["statement"][:200],
                    "requirement_code": req["requirement_code"],
                    "reason": "No active, non-suspicious excerpt supports this requirement above the "
                              f"similarity floor of {floor}; content was not generated for it.",
                })
            for chunk, doc in chosen:
                used[chunk.chunk_code + str(doc.id)] = (chunk, doc)
            context_reqs.append({
                "requirement_code": req["requirement_code"],
                "statement": req["statement"],
                "requirement_type": req["requirement_type"],
                "competency": req["competency"],
                "is_mandatory": req["is_mandatory"],
                "priority": req["priority"],
                "deadline_days": req["deadline_days"],
                "assessment_required": req["assessment_required"],
                "assessment_topic": req["assessment_topic"],
                "prerequisites": req["prerequisites"],
                "source_document_code": req["source_document_code"],
                "chunks": [
                    {"document_id": str(d.id), "document_code": d.document_code,
                     "section_id": c.section_id, "chunk_code": c.chunk_code}
                    for c, d in chosen
                ],
            })

        topic_support = []
        for offset, topic in enumerate(topics):
            hits = [(c, d, sim) for c, d, sim in nearest(len(requirements) + offset, 3) if not c.is_suspicious]
            best = max((s for _, _, s in hits), default=0.0)
            if best < floor:
                gaps.append({"topic": topic, "requirement_code": None,
                             "reason": f"No active document covers this topic (best similarity {best:.2f}, "
                                       f"floor {floor}). Content was not invented for it."})
            else:
                topic_support.append({"topic": topic, "chunk_codes": [c.chunk_code for c, _, s in hits if s >= floor]})

        max_chunks = int(retrieval.get("max_prompt_chunks", 80))
        chunk_list = [
            {"chunk_code": c.chunk_code, "document_code": d.document_code, "document_id": str(d.id),
             "version": d.version, "section_id": c.section_id, "content": c.content}
            for c, d in list(used.values())[:max_chunks]
        ]
        documents = {}
        for c, d in used.values():
            documents[str(d.id)] = {"document_id": str(d.id), "document_code": d.document_code,
                                    "version": d.version, "status": d.status.value}
        quiz_types = [t["code"] for t in (await get_config(self.session, "quiz_types")).get("types", [])]
        return {
            "company": COMPANY,
            "employee": {
                "employee_code": employee.employee_code, "full_name": employee.full_name,
                "experience_level": employee.experience_level.value,
                "joining_date": str(employee.joining_date), "location": employee.location,
                "department": department.name if department else None,
                "previous_experience": employee.previous_experience,
                "required_competencies": employee.required_competencies,
            },
            "role": {"id": str(role.id), "code": role.code, "title": role.title,
                     "department": department.name if department else None},
            "stages": [{"code": s.code, "name": s.name, "sequence": s.sequence, "offset_days": s.offset_days}
                       for s in stages],
            "requirements": context_reqs,
            "chunks": chunk_list,
            "gaps": gaps,
            "topics": topic_support,
            "quiz_types": quiz_types,
            "_documents": list(documents.values()),
            "_excluded": list(excluded.values()),
            "_employee_id": str(employee.id),
            "_role_id": str(role.id),
        }

    # ------------------------------------------------------------ generation
    async def _call(self, context: dict, template_name: str, prompt_version: str,
                    output_model, purpose: str, employee_id, parameters: dict, plan_id=None):
        config = await get_config(self.session, "generation")
        spec = prompts.find(template_name, prompt_version)
        if spec is None:
            raise ValidationFailedError(f"No prompt template '{template_name}' version '{prompt_version}'")
        system, user = prompts.render(spec, {k: v for k, v in context.items() if not k.startswith("_")})
        clients, skipped = build_chain(config)
        params = {**config.get("parameters", {}), **parameters}
        retry = config.get("retry", {})
        started = datetime.now(timezone.utc)
        clock = time.perf_counter()
        run = GenerationRun(
            plan_id=plan_id, employee_id=employee_id, purpose=purpose,
            prompt_template_version=spec.label, provider=clients[0].provider, model=clients[0].model,
            parameters={**params, "retrieval": config.get("retrieval", {}), "prompt_hash": spec.content_hash,
                        "provider_chain": [c.provider for c in clients], "providers_skipped": skipped},
            started_at=started, source_documents=context["_documents"],
            raw_request=f"[SYSTEM]\n{system}\n\n[USER]\n{user}", status="RUNNING",
        )
        self.session.add(run)
        try:
            outcome = await generate_with_fallback(
                clients,
                GenAIRequest(system=system, prompt=user, output_model=output_model,
                             context={**context, "mode": "modules" if output_model is GeneratedModules else "plan"},
                             parameters=params),
                max_attempts=retry.get("max_attempts", 3),
                backoff_seconds=float(parameters.get("backoff_seconds", retry.get("backoff_seconds", 1.0))),
                backoff_cap_seconds=float(retry.get("backoff_cap_seconds", 8.0)),
            )
        except GenAIError as exc:
            run.status = "FAILED"
            run.error = exc.message
            run.attempts = exc.details.get("attempts", [])
            run.attempt_count = len(run.attempts)
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = int((time.perf_counter() - clock) * 1000)
            await self.session.commit()
            exc.details["generation_run_id"] = str(run.id)
            raise
        result = outcome.result
        # Record the provider that actually produced the plan, not the one first asked.
        run.provider, run.model = outcome.client.provider, outcome.client.model
        run.parameters = {**run.parameters, "fell_back": outcome.client is not clients[0]}
        run.status = "SUCCEEDED"
        run.attempts = result.attempts
        run.attempt_count = len(result.attempts)
        run.token_usage = result.usage
        run.raw_response = result.raw_text
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - clock) * 1000)
        return run, result, spec

    async def generate_plan(
        self,
        employee_id: uuid.UUID,
        prompt_version: str | None = None,
        extra_topics: list[str] | None = None,
        simulate_malformed: int = 0,
        actor_id: uuid.UUID | None = None,
    ) -> dict:
        config = await get_config(self.session, "generation")
        prompt_version = prompt_version or config.get("default_prompt_version", "v1")
        template_name = config.get("prompt_template", "plan_generation")
        context = await self.build_context(employee_id, extra_topics=extra_topics)
        params = {"simulate_malformed": simulate_malformed} if simulate_malformed else {}
        if simulate_malformed:
            params["backoff_seconds"] = 0.1
        run, result, spec = await self._call(context, template_name, prompt_version, GeneratedPlan,
                                             "PLAN", employee_id, params)
        payload: GeneratedPlan = result.payload
        template_row = await self.templates.find(spec.name, spec.version)
        if template_row is None:  # startup registration did not run; record the template now
            await self.register_templates()
            template_row = await self.templates.find(spec.name, spec.version)

        await self.plans.retire_current(employee_id)
        plan = OnboardingPlan(
            employee_id=employee_id, job_role_id=uuid.UUID(context["_role_id"]),
            title=payload.plan_title, summary=payload.summary, status="GENERATED", is_current=True,
            prompt_template_id=template_row.id if template_row else None, prompt_version=spec.version,
            provider=run.provider, model=run.model, generated_at=run.finished_at,
            source_document_versions=context["_documents"], raw_response=payload.model_dump(),
            gaps=_merge_gaps(context["gaps"], [g.model_dump() for g in payload.gaps]),
            excluded_chunks=context["_excluded"],
        )
        self.session.add(plan)
        await self.session.flush()
        for index, module in enumerate(payload.modules, start=1):
            self.plans.add_module(plan, module.model_dump(), index)
        run.plan_id = plan.id
        self.audit.record("plan", plan.id, "generated", actor_id=actor_id,
                          after={"prompt_version": spec.version, "model": run.model, "modules": len(payload.modules),
                                 "gaps": len(plan.gaps)})
        await self.session.commit()
        full = await self.plans.full(plan.id)
        return {**await self._with_codes(plan_dict(full)), "generation_run_id": str(run.id),
                "attempt_count": run.attempt_count,
                "duration_ms": run.duration_ms}

    async def generate_payload(self, employee_id: uuid.UUID, prompt_version: str,
                               fixed_chunk_codes: list[str] | None, parameters: dict) -> tuple[dict, dict]:
        """Generates without persisting a plan. Used by consistency testing."""
        config = await get_config(self.session, "generation")
        context = await self.build_context(employee_id, fixed_chunk_codes=fixed_chunk_codes)
        run, result, spec = await self._call(context, config.get("prompt_template", "plan_generation"),
                                             prompt_version, GeneratedPlan, "CONSISTENCY", employee_id, parameters)
        await self.session.commit()
        return result.payload.model_dump(), {
            "generation_run_id": str(run.id), "model": run.model, "provider": run.provider,
            "prompt_version": spec.label, "chunk_codes": sorted(c["chunk_code"] for c in context["chunks"]),
        }

    async def regenerate_modules(self, plan_id: uuid.UUID, requirement_codes: set[str],
                                 change_summary: list[dict], actor_id=None) -> dict:
        """Selective regeneration (SRS Step 59): only modules touching the given
        requirements are rewritten; every other module, and its completion
        state, is left exactly as it was."""
        config = await get_config(self.session, "generation")
        plan = await self.plans.full(plan_id)
        if plan is None:
            raise NotFoundError("Plan not found")
        affected = [m for m in plan.modules
                    if requirement_codes & set(m.requirement_codes or [m.requirement_code])]
        codes = set(requirement_codes)
        for m in affected:
            codes |= set(m.requirement_codes or [])
        # A requirement being rewritten whose competency an untouched module
        # already teaches (a new clause, or a changed clause re-classified)
        # belongs in that module, so that module is rewritten too rather than
        # getting a duplicate beside it.
        matrix = (await MatrixService(self.session).role_matrix(plan.job_role_id))["requirements"]
        target_competencies = {r["competency"] for r in matrix if r["requirement_code"] in codes}
        for m in plan.modules:
            if m not in affected and m.competency in target_competencies:
                affected.append(m)
                codes |= set(m.requirement_codes or [])
        context = await self.build_context(plan.employee_id, requirement_codes=codes)
        context["change_summary"] = change_summary
        # Where prerequisites that are not being rewritten already sit, so a
        # rewritten module is never scheduled ahead of them.
        seq = {s["code"]: s["sequence"] for s in context["stages"]}
        kept: dict[str, str] = {}
        for m in plan.modules:
            if m in affected:
                continue
            for part in list(m.tasks) + list(m.checklist) + list(m.quiz):
                code, stage = part.requirement_code, part.due_stage
                if code and stage in seq and (code not in kept or seq[stage] < seq[kept[code]]):
                    kept[code] = stage
        context["scheduled_prerequisites"] = {
            dep: kept[dep] for r in context["requirements"] for dep in r["prerequisites"] if dep in kept
        }
        run, result, spec = await self._call(context, config.get("module_template", "module_regeneration"),
                                             "v1", GeneratedModules, "MODULE_REGENERATION",
                                             plan.employee_id, {}, plan_id=plan.id)
        payload: GeneratedModules = result.payload
        removed = [{"id": str(m.id), "title": m.title, "requirement_codes": m.requirement_codes} for m in affected]
        regen_counts = {m.competency: m.regeneration_count for m in affected}
        sequences = [m.sequence for m in affected]
        for m in affected:
            await self.session.delete(m)
        await self.session.flush()
        next_seq = max([m.sequence for m in plan.modules if m not in affected] + sequences + [0])
        created = []
        for index, module in enumerate(payload.modules):
            seq = sequences[index] if index < len(sequences) else next_seq + index + 1
            row = self.plans.add_module(plan, module.model_dump(), seq)
            row.regeneration_count = regen_counts.get(module.competency, 0) + 1
            created.append(row)
        plan.gaps = _merge_gaps(plan.gaps or [], [g.model_dump() for g in payload.gaps])
        plan.source_document_versions = _merge_docs(plan.source_document_versions or [], context["_documents"])
        plan.status = "GENERATED"
        await self.session.flush()
        self.audit.record("plan", plan.id, "modules_regenerated", actor_id=actor_id,
                          before={"modules": removed},
                          after={"modules": [{"id": str(m.id), "title": m.title} for m in created]},
                          reason="Selective regeneration after a policy change")
        await self.session.commit()
        return {"plan_id": str(plan.id), "generation_run_id": str(run.id),
                "modules_replaced": removed,
                "modules_created": [{"id": str(m.id), "title": m.title, "requirement_codes": m.requirement_codes}
                                    for m in created]}

    # ------------------------------------------------------------ reads
    async def get_plan(self, plan_id: uuid.UUID) -> dict:
        plan = await self.plans.full(plan_id)
        if plan is None:
            raise NotFoundError("Plan not found")
        return await self._with_codes(plan_dict(plan))

    async def _with_codes(self, plan: dict) -> dict:
        from src.services.plan_views import with_document_codes

        docs = {str(d.id): (d.document_code, d.version, d.status.value) for d in await self.documents.list_all()}
        return with_document_codes(plan, docs)

    async def list_plans(self, **filters) -> list[dict]:
        from src.services.plan_views import plan_header

        return [plan_header(p) for p in await self.plans.filtered(**filters)]

    async def generation_runs(self, plan_id: uuid.UUID) -> list[dict]:
        if await self.plans.get(plan_id) is None:
            raise NotFoundError("Plan not found")
        return [
            {"id": str(r.id), "plan_id": str(r.plan_id) if r.plan_id else None, "purpose": r.purpose,
             "prompt_template_version": r.prompt_template_version, "provider": r.provider, "model": r.model,
             "parameters": r.parameters, "started_at": r.started_at.isoformat(),
             "finished_at": r.finished_at.isoformat() if r.finished_at else None,
             "duration_ms": r.duration_ms, "attempt_count": r.attempt_count, "attempts": r.attempts,
             "source_documents": r.source_documents, "token_usage": r.token_usage, "status": r.status,
             "error": r.error, "raw_request": r.raw_request, "raw_response": r.raw_response}
            for r in await self.runs.for_plan(plan_id)
        ]


def _merge_gaps(a: list[dict], b: list[dict]) -> list[dict]:
    seen, merged = set(), []
    for gap in a + b:
        key = (gap.get("requirement_code"), gap.get("topic"))
        if key not in seen:
            seen.add(key)
            merged.append(gap)
    return merged


def _merge_docs(a: list[dict], b: list[dict]) -> list[dict]:
    merged = {d["document_id"]: d for d in a}
    merged.update({d["document_id"]: d for d in b})
    return list(merged.values())
