"""Role Requirement Matrix: extraction, role mapping, prerequisites (SRS Steps 10-12).
Deterministic Python only."""
import re
import uuid
from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import get_config
from src.contradiction_checks.detector import GENERIC_TERMS, numeric_conflict, same_obligation
from src.core.exceptions import NotFoundError, ValidationFailedError
from src.core.textutil import jaccard, phrase_regex
from src.models.enums import DocumentStatus, MANDATORY_TYPES, MappingMethod, Priority, RequirementType
from src.models.requirement import Requirement, RoleRequirement
from src.repositories.document import ChunkRepository, DocumentRepository
from src.repositories.requirement import (
    PrerequisiteRepository,
    RequirementRepository,
    RoleRepository,
    RoleRequirementRepository,
)
from src.role_matrix.extractor import ChunkInput, RuleSet, extract_from_chunk
from src.role_matrix.prerequisites import ReqNode, detect
from src.role_matrix.role_mapper import RequirementInput, RoleInput, RoleMapper
from src.services.audit_service import AuditService

CLASSIFICATION_FIELDS = (
    "statement", "requirement_type", "is_mandatory", "priority", "competency",
    "policy_requirement", "process_requirement", "assessment_required", "assessment_topic",
    "applies_to_all_roles", "is_compliance", "deadline_days", "conditions",
    "extraction_confidence", "extraction_method",
)
SOURCE_FIELDS = (
    "source_document_id", "source_document_code", "source_chunk_id",
    "source_chunk_code", "source_section_id",
)
SRS_MINIMUMS = {"requirements": 150, "mandatory": 50, "role_specific": 30}


def requirement_dict(r: Requirement) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "requirement_code": r.requirement_code,
        "statement": r.statement,
        "requirement_type": r.requirement_type.value,
        "competency": r.competency,
        "policy_requirement": r.policy_requirement,
        "process_requirement": r.process_requirement,
        "is_mandatory": r.is_mandatory,
        "priority": r.priority.value,
        "is_compliance": r.is_compliance,
        "deadline_days": r.deadline_days,
        "source_document_id": str(r.source_document_id),
        "source_document_code": r.source_document_code,
        "source_chunk_id": str(r.source_chunk_id) if r.source_chunk_id else None,
        "source_chunk_code": r.source_chunk_code,
        "source_section_id": r.source_section_id,
        "assessment_required": r.assessment_required,
        "assessment_topic": r.assessment_topic,
        "applies_to_all_roles": r.applies_to_all_roles,
        "conditions": r.conditions,
        "extraction_confidence": r.extraction_confidence,
        "extraction_method": r.extraction_method,
        "manually_overridden": r.manually_overridden,
        "is_active": r.is_active,
        "overridden_by": r.overridden_by,
        "override_reason": r.override_reason,
    }


class MatrixService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.documents = DocumentRepository(session)
        self.chunks = ChunkRepository(session)
        self.requirements = RequirementRepository(session)
        self.mappings = RoleRequirementRepository(session)
        self.prerequisites = PrerequisiteRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditService(session)

    async def rules(self) -> dict:
        return await get_config(self.session, "requirement_rules")

    # ------------------------------------------------------------ extraction
    async def extract(
        self,
        document_id: uuid.UUID | None = None,
        force: bool = False,
        sections: set[str] | None = None,
    ) -> dict:
        """Runs extraction over ACTIVE documents.

        `sections` limits re-classification to those section ids (selective
        regeneration after a policy update). Requirements in the other sections
        keep their classification and are only re-pointed at the new version.
        """
        rule_set = RuleSet(await self.rules())
        if document_id:
            document = await self.documents.get(document_id)
            if document is None:
                raise NotFoundError("Document not found")
            if document.status != DocumentStatus.ACTIVE:
                raise ValidationFailedError(
                    f"{document.document_code} v{document.version} is {document.status.value}; "
                    "requirements are only extracted from active documents"
                )
            documents = [document]
        else:
            documents = await self.documents.list_all(active_only=True)

        by_type: Counter = Counter()
        rejected: list[dict] = []
        warnings: list[str] = []
        created = updated = repointed = deactivated = 0
        next_number = await self.requirements.max_code_number()

        for document in documents:
            chunks = await self.chunks.for_document(document.id)
            if not chunks:
                warnings.append(f"{document.document_code} v{document.version} has no chunks; parse it first")
                continue
            extracted = []
            for chunk in chunks:
                outcome = extract_from_chunk(
                    ChunkInput(
                        chunk_id=chunk.id, chunk_code=chunk.chunk_code, section_id=chunk.section_id,
                        heading=chunk.heading, content=chunk.content, document_id=document.id,
                        document_code=document.document_code,
                        document_type=document.document_type.value, document_title=document.title,
                        is_suspicious=chunk.is_suspicious,
                    ),
                    rule_set,
                )
                extracted.extend((chunk, e) for e in outcome.requirements)
                rejected.extend(outcome.rejected)
                warnings.extend(outcome.warnings)

            existing = {r.source_key: r for r in await self.requirements.for_document_codes([document.document_code])}
            produced: set[str] = set()
            for chunk, item in extracted:
                produced.add(item.source_key)
                row = existing.get(item.source_key)
                reclassify = sections is None or (chunk.section_id in sections)
                if row is None:
                    next_number += 1
                    row = Requirement(requirement_code=f"R{next_number:03d}", source_key=item.source_key,
                                      is_active=True)
                    for name in CLASSIFICATION_FIELDS + SOURCE_FIELDS:
                        setattr(row, name, getattr(item, name))
                    self.session.add(row)
                    created += 1
                    by_type[item.requirement_type.value] += 1
                    continue

                before = requirement_dict(row)
                for name in SOURCE_FIELDS:
                    setattr(row, name, getattr(item, name))
                row.is_active = True
                if reclassify and (force or not row.manually_overridden):
                    changed = [n for n in CLASSIFICATION_FIELDS if getattr(row, n) != getattr(item, n)]
                    for name in CLASSIFICATION_FIELDS:
                        setattr(row, name, getattr(item, name))
                    if force:
                        row.manually_overridden = False
                    if changed:
                        updated += 1
                        self.audit.record("requirement", row.requirement_code, "re_extracted",
                                          before={k: before[k] for k in changed if k in before},
                                          after={k: requirement_dict(row)[k] for k in changed if k in before})
                elif before["source_document_id"] != str(item.source_document_id):
                    repointed += 1
                by_type[row.requirement_type.value] += 1

            for key, row in existing.items():
                if key not in produced and row.is_active:
                    row.is_active = False
                    deactivated += 1
                    self.audit.record("requirement", row.requirement_code, "deactivated",
                                      reason="Clause no longer present in the active document version")

        if document_id is None:
            active_ids = {d.id for d in documents}
            for row in await self.requirements.active():
                if row.source_document_id not in active_ids:
                    row.is_active = False
                    deactivated += 1

        await self.session.commit()
        reasons = Counter(r["reason"].split(":")[0] for r in rejected)
        return {
            "documents_processed": len(documents),
            "requirements_found": sum(by_type.values()),
            "created": created,
            "updated": updated,
            "repointed_to_new_version": repointed,
            "deactivated": deactivated,
            "by_type": dict(by_type),
            "rejected_sentences": len(rejected),
            "rejected_by_reason": dict(reasons),
            "rejected_sample": rejected[:15],
            "warnings": warnings,
        }

    # ------------------------------------------------------------ role mapping
    async def _mapper(self, job_role_id: uuid.UUID | None = None) -> RoleMapper:
        roles = [
            RoleInput(id=r.id, code=r.code, title=r.title, department_id=d.id, department_name=d.name,
                      department_code=d.code)
            for r, d in await self.roles.active_with_departments(job_role_id)
        ]
        return RoleMapper(roles, await self.rules())

    async def map_roles(
        self, job_role_id: uuid.UUID | None = None, requirement_ids: list[uuid.UUID] | None = None
    ) -> dict:
        if job_role_id and not await self.roles.get(job_role_id):
            raise NotFoundError("Role not found")
        mapper = await self._mapper(job_role_id)
        requirements = await self.requirements.active()
        if requirement_ids is not None:
            wanted = set(requirement_ids)
            requirements = [r for r in requirements if r.id in wanted]
        documents = await self.documents.by_ids(list({r.source_document_id for r in requirements}))
        clauses = await self.chunks.by_ids([r.source_chunk_id for r in requirements if r.source_chunk_id])

        await self.mappings.delete_generated(job_role_id=job_role_id, requirement_ids=requirement_ids)
        manual = await self.mappings.manual_pairs()
        per_role: Counter = Counter()
        per_method: Counter = Counter()
        role_titles = {r.id: r.title for r in mapper.roles}
        for req in requirements:
            doc = documents.get(req.source_document_id)
            for m in mapper.map(RequirementInput(
                id=req.id, code=req.requirement_code, statement=req.statement,
                requirement_type=req.requirement_type, is_mandatory=req.is_mandatory,
                priority=req.priority, document_department_id=doc.department_id if doc else None,
                clause_text=clauses[req.source_chunk_id].content if req.source_chunk_id in clauses else "",
            )):
                if (m.job_role_id, m.requirement_id) in manual:
                    continue
                self.session.add(RoleRequirement(
                    job_role_id=m.job_role_id, requirement_id=m.requirement_id,
                    is_mandatory_for_role=m.is_mandatory_for_role, priority_for_role=m.priority_for_role,
                    mapping_reason=m.mapping_reason, mapping_method=m.mapping_method,
                ))
                per_role[role_titles[m.job_role_id]] += 1
                per_method[m.mapping_method.value] += 1
        await self.session.commit()
        return {
            "roles_mapped": len(mapper.roles),
            "requirements_considered": len(requirements),
            "mappings_created": sum(per_role.values()),
            "per_role": dict(sorted(per_role.items())),
            "per_method": dict(per_method),
            "manual_mappings_preserved": len(manual),
        }

    # ------------------------------------------------------------ prerequisites
    async def build_prerequisites(self) -> dict:
        requirements = await self.requirements.active()
        nodes = [ReqNode(r.id, r.requirement_code, r.statement, r.competency) for r in requirements]
        edges, cycles = detect(nodes, await self.rules())
        await self.prerequisites.replace_generated([
            {"requirement_id": e.requirement_id, "depends_on_requirement_id": e.depends_on_id,
             "reason": e.reason, "method": e.method}
            for e in edges
        ])
        await self.session.commit()
        return {
            "edges": [
                {"requirement": e.requirement_code, "depends_on": e.depends_on_code,
                 "method": e.method, "reason": e.reason}
                for e in edges
            ],
            "edge_count": len(edges),
            "cycles_rejected": cycles,
        }

    # ------------------------------------------------------------ precedence
    async def apply_precedence(self) -> dict:
        """When two active documents state the same obligation differently, the
        requirement from the lower-precedence clause leaves the Matrix
        (SRS Step 34). It is kept on record with the winner and the reason, so a
        reviewer can see exactly why it no longer applies. Manual overrides win."""
        from src.services.validation_service import ValidationService

        contradictions = await ValidationService(self.session).corpus_contradictions(include_obsolete=False)
        subjects = phrase_regex([re.escape(r.title.lower()) + "s?" for r in await self.roles.list()])
        requirements = await self.requirements.active()
        by_chunk: dict[tuple, list[Requirement]] = {}
        for r in requirements:
            by_chunk.setdefault((r.source_document_code, r.source_chunk_code), []).append(r)
        for r in requirements:
            if r.override_reason and not r.manually_overridden:
                r.overridden_by, r.override_reason = None, None

        overridden = []
        for c in contradictions:
            if c["kind"] == "OLD_VS_NEW_VERSION":
                continue
            a_wins = (c["winner"]["document_code"], c["winner"]["chunk_code"]) == \
                     (c["a"]["document_code"], c["a"]["chunk_code"])
            win_side, lose_side = (c["a"], c["b"]) if a_wins else (c["b"], c["a"])
            evidence = c.get("evidence", {})
            win_sentence = evidence.get("sentence_a" if a_wins else "sentence_b", "")
            lose_sentence = evidence.get("sentence_b" if a_wins else "sentence_a", "")
            winners = [r for r in by_chunk.get((win_side["document_code"], win_side["chunk_code"]), [])
                       if not win_sentence or r.statement.strip() == win_sentence.strip()]
            for r in by_chunk.get((lose_side["document_code"], lose_side["chunk_code"]), []):
                # Any requirement in the losing clause that states the same
                # obligation as the winning sentence is overridden, not only
                # the sentence the detector happened to pair first.
                same = r.statement.strip() == lose_sentence.strip() or (
                    win_sentence and same_obligation(r.statement, win_sentence, GENERIC_TERMS, 0.5, 2, subjects))
                if lose_sentence and not same:
                    continue
                if r.manually_overridden:
                    continue
                r.overridden_by = winners[0].requirement_code if winners else None
                r.override_reason = f"{c['kind']}: {c['detail']}. {c['resolution']}"
                overridden.append({"requirement": r.requirement_code, "overridden_by": r.overridden_by,
                                   "reason": r.override_reason})
                self.audit.record("requirement", r.requirement_code, "overridden_by_precedence",
                                  after={"overridden_by": r.overridden_by}, reason=r.override_reason)
        # The same obligation restated elsewhere (a handbook repeating a policy
        # clause) is kept once, from the most authoritative source.
        docs = await self.documents.by_ids(list({r.source_document_id for r in requirements}))

        def authority(r: Requirement) -> tuple:
            d = docs.get(r.source_document_id)
            return (d.precedence_rank if d else 999, -(d.effective_date.toordinal() if d else 0), r.requirement_code)

        live = sorted((r for r in requirements if not r.override_reason), key=authority)
        kept: list[Requirement] = []
        duplicates = 0
        for r in live:
            original = next((k for k in kept if k.source_document_code != r.source_document_code
                             and jaccard(k.statement, r.statement) >= 0.75), None)
            if original is None:
                kept.append(r)
                continue
            if r.manually_overridden:
                continue
            d = docs.get(original.source_document_id)
            rank = d.precedence_rank if d else "?"
            numbers = numeric_conflict(original.statement, r.statement)
            r.overridden_by = original.requirement_code
            r.override_reason = (
                f"CONFLICT: states the same obligation as {original.requirement_code} "
                f"({', '.join(numbers['b'])} vs {', '.join(numbers['a'])}); {original.source_document_code} "
                f"(rank {rank}) is authoritative" if numbers else
                f"DUPLICATE: restates {original.requirement_code} from {original.source_document_code} "
                f"(rank {rank}), the more authoritative source")
            duplicates += 1
            overridden.append({"requirement": r.requirement_code, "overridden_by": r.overridden_by,
                               "reason": r.override_reason})
            self.audit.record("requirement", r.requirement_code, "consolidated_duplicate",
                              after={"overridden_by": r.overridden_by}, reason=r.override_reason)
        await self.session.commit()
        return {"contradictions_considered": len(contradictions), "overridden": overridden,
                "overridden_count": len(overridden), "duplicates_consolidated": duplicates}

    # ------------------------------------------------------------ reads
    async def list_requirements(self, **filters) -> list[dict]:
        return [requirement_dict(r) for r in await self.requirements.filtered(**filters)]

    async def get_requirement(self, code: str) -> dict:
        req = await self.requirements.by_code(code)
        if req is None:
            raise NotFoundError(f"No requirement with code '{code}'")
        chunk = (await self.chunks.by_ids([req.source_chunk_id])).get(req.source_chunk_id) if req.source_chunk_id else None
        document = await self.documents.get(req.source_document_id)
        roles = await self.mappings.roles_for_requirements([req.id])
        prereqs = await self.prerequisites.for_requirements([req.id])
        codes = await self._codes_by_id([p.depends_on_requirement_id for p in prereqs])
        return {
            **requirement_dict(req),
            "source_document": {
                "document_code": document.document_code, "title": document.title,
                "version": document.version, "status": document.status.value,
                "precedence_rank": document.precedence_rank,
            } if document else None,
            "source_chunk": {
                "chunk_code": chunk.chunk_code, "section_id": chunk.section_id,
                "heading_path": chunk.heading_path, "page_number": chunk.page_number,
                "content": chunk.content,
            } if chunk else None,
            "mapped_roles": [
                {"role_code": role.code, "role_title": role.title,
                 "method": m.mapping_method.value, "reason": m.mapping_reason,
                 "is_mandatory_for_role": m.is_mandatory_for_role,
                 "priority_for_role": m.priority_for_role.value}
                for m, role in sorted(roles, key=lambda x: x[1].code)
            ],
            "prerequisites": [
                {"depends_on": codes.get(p.depends_on_requirement_id), "reason": p.reason} for p in prereqs
            ],
        }

    async def _codes_by_id(self, ids) -> dict:
        rows = await self.requirements.list()
        return {r.id: r.requirement_code for r in rows if r.id in set(ids)}

    async def role_matrix(self, job_role_id: uuid.UUID) -> dict:
        """The answer key the validation pipeline compares every plan against."""
        role = await self.roles.get(job_role_id)
        if role is None:
            raise NotFoundError("Role not found")
        rows = await self.mappings.matrix_for_role(job_role_id)
        req_ids = [r.id for _, r in rows]
        prereqs = await self.prerequisites.for_requirements(req_ids)
        all_codes = {r.id: r.requirement_code for r in await self.requirements.list()}
        docs = await self.documents.by_ids(list({r.source_document_id for _, r in rows}))
        prereq_map: dict = {}
        for p in prereqs:
            prereq_map.setdefault(p.requirement_id, []).append(all_codes.get(p.depends_on_requirement_id))

        items = []
        for m, r in rows:
            doc = docs.get(r.source_document_id)
            items.append({
                "requirement_code": r.requirement_code,
                "statement": r.statement,
                "requirement_type": r.requirement_type.value,
                "competency": r.competency,
                "is_mandatory": m.is_mandatory_for_role,
                "priority": m.priority_for_role.value,
                "is_compliance": r.is_compliance,
                "deadline_days": r.deadline_days,
                "policy_requirement": r.policy_requirement,
                "process_requirement": r.process_requirement,
                "source_document_id": str(r.source_document_id),
                "source_document_code": r.source_document_code,
                "source_document_version": doc.version if doc else None,
                "source_section_id": r.source_section_id,
                "source_chunk_code": r.source_chunk_code,
                "assessment_required": r.assessment_required,
                "assessment_topic": r.assessment_topic,
                "conditions": r.conditions,
                "prerequisites": sorted(c for c in prereq_map.get(r.id, []) if c),
                "mapping_method": m.mapping_method.value,
                "mapping_reason": m.mapping_reason,
            })
        return {
            "job_role_id": str(role.id),
            "role_code": role.code,
            "role_title": role.title,
            "total": len(items),
            "mandatory": sum(1 for i in items if i["is_mandatory"]),
            "requirements": items,
        }

    async def summary(self) -> dict:
        requirements = await self.requirements.active()
        role_counts = await self.mappings.counts_by_role()
        roles_total = len(await self.roles.active_with_departments())
        per_req_roles = await self.mappings.role_counts_per_requirement()
        role_specific = sum(1 for r in requirements if 0 < per_req_roles.get(r.id, 0) < roles_total)
        mandatory = sum(1 for r in requirements if r.is_mandatory)
        totals = {"requirements": len(requirements), "mandatory": mandatory, "role_specific": role_specific}
        return {
            **totals,
            "optional_or_recommended": len(requirements) - mandatory,
            "unmapped": sum(1 for r in requirements if per_req_roles.get(r.id, 0) == 0),
            "overridden_by_precedence": sum(1 for r in requirements if r.override_reason),
            "per_type": dict(Counter(r.requirement_type.value for r in requirements)),
            "per_priority": dict(Counter(r.priority.value for r in requirements)),
            "per_document": dict(Counter(r.source_document_code for r in requirements)),
            "per_role": [
                {"role_code": code, "role_title": title, "requirements": total, "mandatory": mand}
                for code, title, total, mand in role_counts
            ],
            "srs_minimums": {
                k: {"required": v, "actual": totals[k], "met": totals[k] >= v} for k, v in SRS_MINIMUMS.items()
            },
        }

    async def patch_requirement(self, code: str, changes: dict, actor_id: uuid.UUID, reason: str | None) -> dict:
        """Human override for a heuristic misclassification, recorded in the audit log."""
        req = await self.requirements.by_code(code)
        if req is None:
            raise NotFoundError(f"No requirement with code '{code}'")
        before = requirement_dict(req)
        if "requirement_type" in changes and changes["requirement_type"] is not None:
            rtype = RequirementType(changes["requirement_type"])
            changes["requirement_type"] = rtype
            changes.setdefault("is_mandatory", rtype in MANDATORY_TYPES)
        if changes.get("priority") is not None:
            changes["priority"] = Priority(changes["priority"])
        for name, value in changes.items():
            if value is not None:
                setattr(req, name, value)
        req.manually_overridden = True
        after = requirement_dict(req)
        diff = [k for k in after if after[k] != before[k] and k != "manually_overridden"]
        self.audit.record("requirement", code, "manual_override", actor_id=actor_id,
                          before={k: before[k] for k in diff}, after={k: after[k] for k in diff},
                          reason=reason)
        await self.session.commit()
        return {"requirement": after, "changed_fields": diff}

    async def add_manual_mapping(self, code: str, job_role_id: uuid.UUID, reason: str, actor_id) -> dict:
        req = await self.requirements.by_code(code)
        role = await self.roles.get(job_role_id)
        if req is None or role is None:
            raise NotFoundError("Requirement or role not found")
        existing = await self.mappings.get_by(job_role_id=job_role_id, requirement_id=req.id)
        if existing is not None and existing.mapping_method == MappingMethod.MANUAL:
            return {"requirement_code": code, "role_code": role.code, "method": "MANUAL", "already_mapped": True}
        await self.mappings.delete_generated(job_role_id=job_role_id, requirement_ids=[req.id])
        self.session.add(RoleRequirement(
            job_role_id=job_role_id, requirement_id=req.id, is_mandatory_for_role=req.is_mandatory,
            priority_for_role=req.priority, mapping_reason=reason, mapping_method=MappingMethod.MANUAL,
        ))
        self.audit.record("requirement", code, "manual_role_mapping", actor_id=actor_id,
                          after={"role": role.code}, reason=reason)
        await self.session.commit()
        return {"requirement_code": code, "role_code": role.code, "method": "MANUAL"}
