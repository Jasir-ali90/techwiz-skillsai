"""Rules 7-11: contradictions, duplicates, role relevance, completeness,
business rules."""
import re

import numpy as np

from src.contradiction_checks.detector import PolarityChecker, numeric_conflict
from src.python_validation.base import (
    CONTRADICTION_DETECTED,
    MANUAL_REVIEW_REQUIRED,
    PARTIALLY_VERIFIED,
    REQUIREMENT_MISSING,
    UNSUPPORTED_REQUIREMENT,
    VERIFIED_WITH_WARNING,
    Finding,
    Rule,
    RuleOutput,
    ValidationContext,
    item_text,
    primary_text,
    register,
)


def _same(winner: dict, side: dict) -> bool:
    return (winner["chunk_code"], winner["document_code"], winner["version"]) == \
        (side["chunk_code"], side["document_code"], side["version"])


@register
class ContradictionRule(Rule):
    name = "contradictions"
    description = "Old vs new policy, FAQ vs policy, role description vs SOP, and items that break a rule (Step 33)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        cited = {(str(i.get("source_document_id")), i.get("source_chunk_code")) for i in ctx.items}
        cited_codes = {c for _, c in cited}
        matrix_chunks = {r["source_chunk_code"] for r in ctx.matrix}
        relevant = unresolved = 0
        # A conflict the plan already resolves in favour of the winning source is
        # still reported and counted; its severity is configurable.
        resolved_severity = str(settings.get("resolved_severity", "INFO")).upper()

        for c in ctx.contradictions:
            a, b = c["a"], c["b"]
            touches = {a["chunk_code"], b["chunk_code"]} & (cited_codes | matrix_chunks)
            if not touches:
                continue
            relevant += 1
            win_side, loser = (a, b) if _same(c["winner"], a) else (b, a)
            follows_loser = (loser["document_id"], loser["chunk_code"]) in cited
            if follows_loser:
                unresolved += 1
            winner = c["winner"]
            out.findings.append(Finding(
                self.name, "ERROR" if follows_loser else resolved_severity,
                (f"{c['kind']}: plan cites {loser['document_code']} v{loser['version']} §{loser['section_id']}, "
                 f"which loses to {win_side['document_code']} v{win_side['version']} §{win_side['section_id']}"
                 if follows_loser else
                 f"{c['kind']} in the sources ({c['detail']}); resolved in favour of {winner['document_code']} "
                 f"v{winner['version']} and the plan follows the winner"),
                CONTRADICTION_DETECTED if follows_loser else VERIFIED_WITH_WARNING,
                "source", loser["chunk_code"], None,
                {"contradiction": c, "resolved": not follows_loser},
            ))

        polarity = PolarityChecker(ctx.config.get("permissive_patterns", []),
                                   ctx.config.get("prohibitive_patterns", []))
        for item in ctx.items:
            code = item.get("requirement_code")
            req = ctx.requirements.get(code or "")
            # Modules and assessments aggregate several requirements; their
            # parts are checked individually.
            if not req or item["item_type"] in ("module", "assessment"):
                continue
            text = " ".join(t for _, t in item_text(item)) or ""
            if item["item_type"] == "quiz_question":
                text = " ".join([item.get("question", "")] + list(item.get("correct_answer") or []))
            conflict = numeric_conflict(text, req["statement"])
            if conflict:
                unresolved += 1
                relevant += 1
                out.findings.append(Finding(
                    self.name, "ERROR",
                    f"{item['item_type']} says {', '.join(conflict['a'])} but {code} requires "
                    f"{', '.join(conflict['b'])}",
                    CONTRADICTION_DETECTED, item["item_type"], str(item.get("id")), code,
                    {"item_values": conflict["a"], "requirement_values": conflict["b"],
                     "requirement": req["statement"], "category": "ITEM_VIOLATES_RULE"}))
                continue
            p_item, p_req = polarity.polarity(text), polarity.polarity(req["statement"])
            if p_req == "PROHIBITS" and p_item == "PERMITS":
                unresolved += 1
                relevant += 1
                out.findings.append(Finding(
                    self.name, "ERROR", f"{item['item_type']} permits what {code} prohibits",
                    CONTRADICTION_DETECTED, item["item_type"], str(item.get("id")), code,
                    {"item_text": text[:300], "requirement": req["statement"], "category": "ITEM_VIOLATES_RULE"}))
        out.summary = {"corpus_contradictions": len(ctx.contradictions), "relevant_to_plan": relevant,
                       "unresolved": unresolved}
        out.metrics = {"contradiction_count": relevant, "unresolved_contradictions": unresolved}
        return out


@register
class DuplicateRule(Rule):
    name = "duplicates"
    description = "Substantially duplicated modules, tasks, checklist items and quiz questions (Step 35)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        threshold = float(settings.get("threshold", 0.95))
        pairs = 0
        for kind in ("module", "task", "checklist_item", "quiz_question"):
            items = [i for i in ctx.items if i["item_type"] == kind]
            if len(items) < 2:
                continue
            vectors = ctx.embed([primary_text(i) for i in items])
            sims = vectors @ vectors.T
            for x in range(len(items)):
                for y in range(x + 1, len(items)):
                    score = float(sims[x, y])
                    if score >= threshold:
                        pairs += 1
                        out.findings.append(Finding(
                            self.name, "WARNING", f"Two {kind}s are near duplicates (similarity {score:.2f})",
                            VERIFIED_WITH_WARNING, kind, str(items[y].get("id")), items[y].get("requirement_code"),
                            {"first": {"id": str(items[x].get("id")), "text": primary_text(items[x])[:200],
                                       "requirement_code": items[x].get("requirement_code")},
                             "second": {"id": str(items[y].get("id")), "text": primary_text(items[y])[:200],
                                        "requirement_code": items[y].get("requirement_code")},
                             "score": round(score, 4), "threshold": threshold}))
        out.summary = {"duplicate_pairs": pairs, "threshold": threshold}
        return out


@register
class RoleRelevanceRule(Rule):
    name = "role_relevance"
    description = "Content that is valid company information but maps to no requirement for this role (Step 36)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        matrix = ctx.matrix_by_code
        irrelevant = 0
        for item in ctx.items:
            code = item.get("requirement_code")
            if code in matrix:
                continue
            irrelevant += 1
            roles = ctx.requirement_roles.get(code or "", [])
            out.findings.append(Finding(
                self.name, "WARNING",
                (f"{item['item_type']} maps to {code}, which applies to {', '.join(roles)} but not to "
                 f"{ctx.role['title']}" if roles else
                 f"{item['item_type']} maps to no requirement in any role's Matrix"),
                UNSUPPORTED_REQUIREMENT, item["item_type"], str(item.get("id")), code,
                {"maps_to_roles": roles, "requirement": ctx.requirements.get(code or "", {}).get("statement")}))
        out.summary = {"items": len(ctx.items), "irrelevant": irrelevant}
        return out


@register
class ChecklistCompletenessRule(Rule):
    name = "checklist_completeness"
    description = "Every checklist item traces to a requirement; every acknowledgement has a checklist item"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        matrix = ctx.matrix_by_code
        checklist = [i for i in ctx.items if i["item_type"] == "checklist_item"]
        for item in checklist:
            if item.get("requirement_code") not in matrix:
                out.findings.append(Finding(
                    self.name, "WARNING", "Checklist item does not trace to a requirement in this role's Matrix",
                    UNSUPPORTED_REQUIREMENT, "checklist_item", str(item["id"]), item.get("requirement_code"),
                    {"activity": item.get("activity")}))
        have = {i.get("requirement_code") for i in checklist}
        for r in ctx.matrix:
            if r["is_mandatory"] and r["requirement_type"] == "MUST_ACKNOWLEDGE" and r["requirement_code"] not in have:
                out.findings.append(Finding(
                    self.name, "ERROR", f"{r['requirement_code']} needs an acknowledgement checklist item",
                    PARTIALLY_VERIFIED, "requirement", r["requirement_code"], r["requirement_code"],
                    {"statement": r["statement"]}))
        out.summary = {"checklist_items": len(checklist)}
        return out


@register
class AssessmentCoverageRule(Rule):
    name = "assessment_coverage"
    description = "Every mandatory requirement that needs assessment has a matching assessment"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        assessed = set()
        for item in ctx.items:
            if item["item_type"] == "assessment":
                assessed.add(item.get("requirement_code"))
                assessed |= {r.get("requirement_code") for r in item.get("rubric", [])}
        needed = [r for r in ctx.matrix if r["is_mandatory"] and r["assessment_required"]]
        for r in needed:
            if r["requirement_code"] not in assessed:
                out.findings.append(Finding(
                    self.name, "ERROR", f"{r['requirement_code']} requires assessment on "
                    f"'{r['assessment_topic']}' but no assessment covers it",
                    PARTIALLY_VERIFIED, "requirement", r["requirement_code"], r["requirement_code"],
                    {"statement": r["statement"], "topic": r["assessment_topic"]}))
        covered = len([r for r in needed if r["requirement_code"] in assessed])
        out.summary = {"requiring_assessment": len(needed), "assessed": covered,
                       "assessment_topic_coverage_percent": round(100 * covered / len(needed), 2) if needed else 100.0}
        return out


@register
class CompetencyCoverageRule(Rule):
    name = "competency_coverage"
    description = "Every competency required by a mandatory requirement appears in some module"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        present = set()
        for item in ctx.items:
            if item["item_type"] == "module":
                present |= {str(item.get("competency") or "").lower(), str(item.get("category") or "").lower()}
                present |= {str(k).lower() for k in item.get("key_concepts") or []}
        required = sorted({r["competency"] for r in ctx.matrix if r["is_mandatory"]})
        missing = [c for c in required if c.lower() not in present]
        for c in missing:
            codes = [r["requirement_code"] for r in ctx.matrix if r["competency"] == c and r["is_mandatory"]]
            out.findings.append(Finding(
                self.name, "ERROR", f"Required competency '{c}' is not taught by any module",
                REQUIREMENT_MISSING, "competency", c, codes[0] if codes else None, {"requirements": codes}))
        out.summary = {"required_competencies": len(required), "missing": missing}
        return out


@register
class BusinessRuleConformance(Rule):
    name = "business_rules"
    description = "Configurable business rules, separate from the Matrix"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        evaluated = []
        for rule in ctx.business_rules:
            kind, name = rule.get("type"), rule.get("name", "unnamed")
            severity = rule.get("severity", "WARNING")
            roles = rule.get("roles")
            if roles and ctx.role["code"] not in roles:
                continue
            evaluated.append(name)
            status = CONTRADICTION_DETECTED if severity in ("ERROR", "CRITICAL") else VERIFIED_WITH_WARNING
            if kind == "forbidden_pattern":
                pattern = re.compile(rule["pattern"], re.IGNORECASE)
                unless = re.compile(rule["unless"], re.IGNORECASE) if rule.get("unless") else None
                for item in ctx.items:
                    for fname, text in item_text(item) + [("primary", primary_text(item))]:
                        if pattern.search(text) and not (unless and unless.search(text)):
                            out.findings.append(Finding(
                                self.name, severity, f"{name}: {rule.get('message', 'rule violated')}", status,
                                item["item_type"], str(item.get("id")), item.get("requirement_code"),
                                {"rule": name, "field": fname, "text": text[:300]}))
                            break
            elif kind == "deadline_stage":
                for item in ctx.items:
                    req = ctx.matrix_by_code.get(item.get("requirement_code") or "")
                    stage = ctx.stages.get(item.get("due_stage") or "")
                    if req and stage and req.get("deadline_days") and item["item_type"] not in ("module", "assessment") \
                            and stage["offset_days"] > req["deadline_days"]:
                        out.findings.append(Finding(
                            self.name, severity,
                            f"{name}: due at {item['due_stage']} (day {stage['offset_days']}) but "
                            f"{req['requirement_code']} sets a {req['deadline_days']}-day deadline", status,
                            item["item_type"], str(item.get("id")), req["requirement_code"],
                            {"rule": name, "stage": item["due_stage"], "deadline_days": req["deadline_days"]}))
            elif kind == "critical_early":
                limit = int(rule.get("max_sequence", 2))
                for item in ctx.items:
                    seq = ctx.stage_seq(item.get("due_stage"))
                    if item.get("priority") == "CRITICAL" and item.get("mandatory") and seq and seq > limit \
                            and item["item_type"] not in ("module", "assessment"):
                        out.findings.append(Finding(
                            self.name, severity, f"{name}: critical item due at {item['due_stage']}",
                            VERIFIED_WITH_WARNING, item["item_type"], str(item.get("id")),
                            item.get("requirement_code"), {"rule": name, "stage": item["due_stage"]}))
            elif kind == "max_stage_share":
                dated = [i for i in ctx.items if i["item_type"] in ("task", "checklist_item", "quiz_question")]
                if dated:
                    counts: dict[str, int] = {}
                    for i in dated:
                        counts[i.get("due_stage")] = counts.get(i.get("due_stage"), 0) + 1
                    stage, top = max(counts.items(), key=lambda kv: kv[1])
                    share = top / len(dated)
                    if share > float(rule.get("max_share", 0.6)):
                        out.findings.append(Finding(
                            self.name, severity, f"{name}: {share:.0%} of items fall on {stage}",
                            MANUAL_REVIEW_REQUIRED, "plan", ctx.plan["id"], None,
                            {"rule": name, "distribution": counts}))
        out.summary = {"rules_evaluated": evaluated, "violations": len(out.findings)}
        return out
