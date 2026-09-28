"""Policy update detection, impact analysis and selective regeneration
(SRS Steps 57-59)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.app_config import get_config
from src.core.exceptions import NotFoundError, ValidationFailedError
from src.genai_pipeline.client import GenAIError
from src.impact.diff import diff_versions
from src.models.enums import DocumentStatus
from src.models.impact import ImpactRecord
from src.repositories.document import ChunkRepository, DocumentRepository
from src.repositories.plan import PlanRepository
from src.repositories.requirement import RequirementRepository
from src.role_matrix.extractor import ChunkInput, RuleSet, extract_from_chunk
from src.services.audit_service import AuditService, jsonable
from src.services.matrix_service import MatrixService


def _chunk_dicts(chunks) -> list[dict]:
    return [{"section_id": c.section_id, "heading": c.heading, "chunk_code": c.chunk_code,
             "content": c.content, "sequence": c.sequence} for c in chunks]


class ImpactService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.documents = DocumentRepository(session)
        self.chunks = ChunkRepository(session)
        self.plans = PlanRepository(session)
        self.requirements = RequirementRepository(session)
        self.audit = AuditService(session)

    async def _pair(self, document_id: uuid.UUID):
        new = await self.documents.get(document_id)
        if new is None:
            raise NotFoundError("Document not found")
        old = await self.documents.previous_version(new)
        if old is None:
            raise ValidationFailedError(f"{new.document_code} v{new.version} has no previous version to compare with")
        for doc in (new, old):
            if await self.chunks.count_for_document(doc.id) == 0:
                from src.services.parse_service import ParseService

                await ParseService(self.session).parse(doc.id)
        return new, old

    async def analyse(self, document_id: uuid.UUID, actor_id=None) -> dict:
        new, old = await self._pair(document_id)
        diff = diff_versions(_chunk_dicts(await self.chunks.for_document(old.id)),
                             _chunk_dicts(await self.chunks.for_document(new.id)))
        changed = {s["section_id"] for s in diff["modified"] + diff["removed"] + diff["added"] if s["section_id"]}
        changed_keys = {s["key"] for s in diff["modified"] + diff["removed"] + diff["added"]}

        # One query chain: sections -> requirements -> items -> plans -> employees.
        reqs = [r for r in await self.requirements.for_document_codes([new.document_code])
                if (r.source_section_id or r.source_key.split(":")[1]) in changed or
                r.source_key.split(":")[1] in changed_keys]
        codes = sorted(r.requirement_code for r in reqs)
        cited = await self.plans.items_citing(codes, [str(old.id)])
        affected: dict[str, list[str]] = {}
        reference_only: dict[str, list[str]] = {}
        plan_ids: set = set()
        for kind, rows in cited.items():
            for item in rows:
                plan = await self.plans.get(item.plan_id)
                if plan is None or not plan.is_current:
                    continue
                touches = item.requirement_code in codes or (
                    item.source_document_id == str(old.id) and item.source_section_id in changed)
                if kind == "module":
                    touches = touches or bool(set(item.requirement_codes or []) & set(codes))
                if touches:
                    affected.setdefault(kind, []).append(str(item.id))
                    item.is_outdated = True
                    plan_ids.add(item.plan_id)
                elif item.source_document_id == str(old.id):
                    reference_only.setdefault(kind, []).append(str(item.id))
                    plan_ids.add(item.plan_id)
        employees = sorted({str((await self.plans.get(pid)).employee_id) for pid in plan_ids})

        record = ImpactRecord(
            document_id=new.id, previous_document_id=old.id, document_code=new.document_code,
            previous_version=old.version, new_version=new.version, changed_sections=jsonable(diff),
            affected_requirement_ids=[str(r.id) for r in reqs], affected_requirement_codes=codes,
            affected_item_ids=affected, reference_only_item_ids=reference_only,
            affected_plan_ids=[str(p) for p in sorted(plan_ids, key=str)], affected_employee_ids=employees,
            regeneration_status="PENDING",
        )
        self.session.add(record)
        self.audit.record("document", new.id, "impact_analysed", actor_id=actor_id,
                          after={"previous_version": old.version, "counts": diff["counts"],
                                 "affected_plans": len(plan_ids)})
        await self.session.commit()
        return self._record_dict(record, new, old)

    def _record_dict(self, record: ImpactRecord, new=None, old=None) -> dict:
        diff = record.changed_sections
        return {
            "id": str(record.id), "document_id": str(record.document_id),
            "previous_document_id": str(record.previous_document_id) if record.previous_document_id else None,
            "document_code": record.document_code, "previous_version": record.previous_version,
            "new_version": record.new_version,
            "previous_version_status": old.status.value if old else None,
            "diff": {"counts": diff.get("counts"),
                     "modified": [{k: s[k] for k in ("section_id", "heading", "summary", "old_text", "new_text",
                                                     "numeric_changes")} for s in diff.get("modified", [])],
                     "added": [{k: s[k] for k in ("section_id", "heading", "content")} for s in diff.get("added", [])],
                     "removed": [{k: s[k] for k in ("section_id", "heading", "content")} for s in diff.get("removed", [])]},
            "affected_requirement_codes": record.affected_requirement_codes,
            "affected_items": {k: len(v) for k, v in record.affected_item_ids.items()},
            "reference_only_items": {k: len(v) for k, v in record.reference_only_item_ids.items()},
            "affected_plan_ids": record.affected_plan_ids,
            "affected_employee_ids": record.affected_employee_ids,
            "regeneration_status": record.regeneration_status,
            "regeneration_result": record.regeneration_result,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }

    async def _latest(self, document_id: uuid.UUID) -> ImpactRecord:
        record = await self.session.scalar(
            select(ImpactRecord).where(ImpactRecord.document_id == document_id)
            .order_by(ImpactRecord.created_at.desc()).limit(1))
        if record is None:
            raise NotFoundError("No impact analysis for this document. POST /impact/analyse/{document_id}")
        return record

    async def get(self, document_id: uuid.UUID) -> dict:
        record = await self._latest(document_id)
        return self._record_dict(record, await self.documents.get(record.document_id),
                                 await self.documents.get(record.previous_document_id) if record.previous_document_id else None)

    async def affected(self, document_id: uuid.UUID) -> dict:
        record = await self._latest(document_id)
        grouped: dict[str, list] = {}
        for kind, ids in record.affected_item_ids.items():
            for iid in ids:
                item = await self.plans.item(kind, uuid.UUID(iid))
                if item is None:
                    continue
                grouped.setdefault(kind, []).append({
                    "id": iid, "plan_id": str(item.plan_id), "requirement_code": item.requirement_code,
                    "source_section_id": item.source_section_id, "source_chunk_code": item.source_chunk_code,
                    "text": (getattr(item, "title", None) or getattr(item, "question", None) or
                             getattr(item, "description", None) or getattr(item, "activity", None) or "")[:160],
                    "is_outdated": item.is_outdated,
                })
        requirements = [
            {"requirement_code": r.requirement_code, "statement": r.statement, "section": r.source_section_id,
             "document_version": (await self.documents.get(r.source_document_id)).version}
            for r in (await self.requirements.by_codes(record.affected_requirement_codes)).values()
        ]
        plans = []
        for pid in record.affected_plan_ids:
            plan = await self.plans.get(uuid.UUID(pid))
            if plan:
                plans.append({"id": pid, "title": plan.title, "employee_id": str(plan.employee_id),
                              "verification_status": plan.verification_status})
        return {"document_code": record.document_code, "versions": f"v{record.previous_version} → v{record.new_version}",
                "requirements": requirements, "items": grouped, "plans": plans,
                "employees": record.affected_employee_ids,
                "reference_only_items": {k: len(v) for k, v in record.reference_only_item_ids.items()}}

    async def regenerate(self, document_id: uuid.UUID, dry_run: bool = True, actor_id=None) -> dict:
        record = await self._latest(document_id)
        new = await self.documents.get(record.document_id)
        old = await self.documents.get(record.previous_document_id)
        if new.status != DocumentStatus.ACTIVE:
            raise ValidationFailedError("The new version is not active")
        diff = record.changed_sections
        changed = {s["section_id"] for s in diff["modified"] + diff["removed"] + diff["added"] if s["section_id"]}
        new_chunks = await self.chunks.for_document(new.id)
        section_to_chunk = {}
        for c in new_chunks:
            if c.section_id and c.section_id not in section_to_chunk:
                section_to_chunk[c.section_id] = c.chunk_code

        # Preview of re-extraction from changed sections only.
        rules = RuleSet(await get_config(self.session, "requirement_rules"))
        preview = []
        for c in new_chunks:
            if c.section_id in changed:
                for e in extract_from_chunk(ChunkInput(c.id, c.chunk_code, c.section_id, c.heading, c.content,
                                                       new.id, new.document_code, new.document_type.value,
                                                       new.title, c.is_suspicious), rules).requirements:
                    preview.append({"source_key": e.source_key, "section": e.section_id if hasattr(e, "section_id")
                                    else e.source_section_id, "type": e.requirement_type.value,
                                    "statement": e.statement})
        existing_keys = {r.source_key: r.requirement_code
                         for r in await self.requirements.for_document_codes([new.document_code])}
        plan_actions = []
        for pid in record.affected_plan_ids:
            plan = await self.plans.full(uuid.UUID(pid))
            if plan is None:
                continue
            outdated_modules = [m for m in plan.modules if str(m.id) in set(record.affected_item_ids.get("module", []))
                                or set(m.requirement_codes or []) & set(record.affected_requirement_codes)]
            plan_actions.append({
                "plan_id": pid, "title": plan.title,
                "modules_to_regenerate": [{"id": str(m.id), "title": m.title,
                                           "completion_status": m.completion_status} for m in outdated_modules],
                "modules_preserved": [{"id": str(m.id), "title": m.title, "completion_status": m.completion_status}
                                      for m in plan.modules if m not in outdated_modules],
            })
        plan_preview = {
            "re_extract_sections": sorted(changed),
            "requirements_updated": sorted({existing_keys[p["source_key"]] for p in preview if p["source_key"] in existing_keys}),
            "requirements_new": [p for p in preview if p["source_key"] not in existing_keys],
            "references_repointed": {k: len(v) for k, v in record.reference_only_item_ids.items()},
            "plans": plan_actions,
        }
        if dry_run:
            return {"dry_run": True, "would_change": plan_preview}

        from src.services.generation_service import GenerationService
        from src.services.validation_service import ValidationService

        matrix = MatrixService(self.session)
        in_matrix_before = await self._matrix_members()
        extraction = await matrix.extract(new.id, sections=changed)
        await matrix.map_roles()
        await matrix.build_prerequisites()
        await matrix.apply_precedence()
        # A new version can change other documents' requirements too: a handbook
        # clause that merely restated the old wording is no longer a duplicate,
        # and one that now conflicts is overridden. Those move in or out of the
        # Matrix and their modules are regenerated with the rest.
        knock_on = sorted(in_matrix_before ^ await self._matrix_members())
        if knock_on:  # other roles' plans may hold, or now need, a knock-on requirement
            listed = {a["plan_id"] for a in plan_actions}
            for plan in await self.plans.filtered(current_only=True):
                if str(plan.id) not in listed:
                    full = await self.plans.full(plan.id)
                    plan_actions.append({"plan_id": str(plan.id), "title": plan.title, "modules_to_regenerate": [],
                                         "modules_preserved": [{"id": str(m.id), "title": m.title,
                                                                "completion_status": m.completion_status}
                                                               for m in full.modules]})

        # Unchanged sections: the clause is identical, so only the citation moves
        # to the new version. Completion state is untouched.
        repointed = 0
        for kind, ids in record.reference_only_item_ids.items():
            for iid in ids:
                item = await self.plans.item(kind, uuid.UUID(iid))
                if item is None or item.source_document_id != str(old.id):
                    continue
                new_code = section_to_chunk.get(item.source_section_id)
                if new_code:
                    item.source_document_id = str(new.id)
                    item.source_chunk_code = new_code
                    item.is_outdated = False
                    repointed += 1
        # Scenarios live inside their module; re-point those in unchanged sections too.
        for action in plan_actions:
            plan = await self.plans.full(uuid.UUID(action["plan_id"]))
            for module in plan.modules:
                scenarios, touched = [], False
                for sc in module.scenarios or []:
                    if sc.get("source_document_id") == str(old.id) and sc.get("source_section_id") not in changed \
                            and section_to_chunk.get(sc.get("source_section_id")):
                        sc = {**sc, "source_document_id": str(new.id),
                              "source_chunk_code": section_to_chunk[sc["source_section_id"]]}
                        touched = True
                        repointed += 1
                    scenarios.append(sc)
                if touched:
                    module.scenarios = scenarios
        await self.session.commit()

        affected_codes = set(record.affected_requirement_codes) | set(knock_on)
        new_codes = {r.requirement_code for r in (await self.requirements.for_document_codes([new.document_code]))
                     if r.is_active and (r.source_section_id in changed)}
        results = []
        summary = [{"section": s["section_id"], "change": s["summary"]} for s in diff["modified"]] + \
                  [{"section": s["section_id"], "change": "added"} for s in diff["added"]]
        for action in plan_actions:
            pid = uuid.UUID(action["plan_id"])
            try:
                regen = await GenerationService(self.session).regenerate_modules(
                    pid, affected_codes | new_codes, summary, actor_id)
            except ValidationFailedError as exc:
                results.append({"plan_id": action["plan_id"], "skipped": exc.message})
                continue
            except GenAIError as exc:
                # Every AI provider failed for this plan (its failed run is already
                # recorded). Carry on with the other plans rather than leaving the
                # regeneration half-done with no final status.
                await self.session.rollback()
                results.append({"plan_id": action["plan_id"], "failed": exc.message})
                continue
            validation = await ValidationService(self.session).run(pid)
            results.append({"plan_id": action["plan_id"],
                            "modules_replaced": [m["title"] for m in regen["modules_replaced"]],
                            "modules_created": [m["title"] for m in regen["modules_created"]],
                            "modules_preserved": [m["title"] for m in action["modules_preserved"]],
                            "verification_status": validation["verification_status"]})
        record = await self._latest(document_id)
        record.regeneration_status = "COMPLETED_WITH_ERRORS" if any("failed" in r for r in results) else "COMPLETED"
        record.regeneration_result = jsonable({"extraction": {k: extraction[k] for k in
                                                              ("created", "updated", "repointed_to_new_version", "deactivated")},
                                               "knock_on_requirements": knock_on,
                                               "references_repointed": repointed, "plans": results})
        self.audit.record("document", new.id, "selective_regeneration", actor_id=actor_id,
                          after=record.regeneration_result)
        await self.session.commit()
        return {"dry_run": False, **record.regeneration_result}

    async def _matrix_members(self) -> set[str]:
        return {r.requirement_code for r in await self.requirements.active() if not r.override_reason}

    async def outdated(self, plan_id: uuid.UUID) -> dict:
        plan = await self.plans.full(plan_id)
        if plan is None:
            raise NotFoundError("Plan not found")
        docs = {str(d.id): d for d in await self.documents.list_all()}
        impacts = {str(r.previous_document_id): r for r in await self.session.scalars(select(ImpactRecord))}
        from src.services.plan_views import flat_items, plan_dict

        items = []
        for item in flat_items(plan_dict(plan)):
            doc = docs.get(str(item.get("source_document_id")))
            status = None
            if doc is None:
                status = "SOURCE_MISSING"
            elif doc.status != DocumentStatus.ACTIVE:
                impact = impacts.get(str(doc.id))
                changed = set()
                if impact:
                    diff = impact.changed_sections
                    changed = {s["section_id"] for s in diff["modified"] + diff["removed"] if s["section_id"]}
                status = ("SECTION_CHANGED" if item.get("source_section_id") in changed else
                          "VERSION_SUPERSEDED" if impact else "DOCUMENT_OBSOLETE")
            elif item.get("is_outdated"):
                status = "FLAGGED_OUTDATED"
            if status:
                items.append({"item_type": item["item_type"], "id": item.get("id"),
                              "requirement_code": item.get("requirement_code"), "status": status,
                              "cited": f"{doc.document_code} v{doc.version} §{item.get('source_section_id')}"
                              if doc else item.get("source_document_id"),
                              "text": (item.get("title") or item.get("question") or item.get("description")
                                       or item.get("activity") or "")[:160]})
        by_status: dict[str, int] = {}
        for i in items:
            by_status[i["status"]] = by_status.get(i["status"], 0) + 1
        return {"plan_id": str(plan_id), "outdated_items": len(items), "by_status": by_status, "items": items}
