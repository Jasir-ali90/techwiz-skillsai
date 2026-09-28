"""Deterministic offline provider.

Used when GENAI_PROVIDER=offline: no API key, no cost, identical output for
identical input. It builds the plan from the same structured context the real
model receives, so the rest of the system (persistence, Pipeline 2, dashboards)
behaves exactly as it would with a live model. Every GenerationRun records
provider "offline" so its output is never mistaken for a model's.

`simulate_malformed` makes the first N attempts return broken JSON, which is
how the retry cap is demonstrated without a live provider.
"""
import json
import re
from collections import OrderedDict
from typing import Any

from src.genai_pipeline.client import Completion, GenAIClient, GenAIRequest

DURATION = re.compile(
    r"\b(one|two|three|four|five|six|seven|ten|fourteen|twenty-four|thirty|sixty|ninety|\d+)\s+"
    r"((?:calendar |working )?(?:days?|hours?|minutes?|weeks?))\b",
    re.IGNORECASE,
)
DISTRACTOR_NUMBERS = ["one", "three", "five", "seven", "fourteen", "thirty"]


class OfflineClient(GenAIClient):
    provider = "offline"

    def __init__(self, model: str = "deterministic-template-v1", config: dict | None = None):
        self.model = model
        self.config = config or {}

    async def complete(self, request: GenAIRequest, attempt: int) -> Completion:
        if attempt <= int(request.parameters.get("simulate_malformed", 0)):
            return Completion(text='{"plan_title": "Truncated output", "modules": [', usage={})
        builder = _Builder(request.context, self.config)
        payload = builder.modules_only() if request.context.get("mode") == "modules" else builder.plan()
        text = json.dumps(payload)
        return Completion(text=text, usage={"input_tokens": len(request.prompt) // 4,
                                            "output_tokens": len(text) // 4})


class _Builder:
    def __init__(self, context: dict[str, Any], config: dict):
        self.ctx = context
        self.config = config
        self.stages = sorted(context["stages"], key=lambda s: s["sequence"])
        self.by_seq = {s["sequence"]: s for s in self.stages}
        self.requirements = {r["requirement_code"]: r for r in context["requirements"]}
        self.priority_seq = config.get("priority_stage_sequence", {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 5})
        self._stage_cache: dict[str, dict] = {}

    # --------------------------------------------------------------- staging
    def _stage_for(self, req: dict) -> dict:
        code = req["requirement_code"]
        if code in self._stage_cache:
            return self._stage_cache[code]
        if req.get("deadline_days"):
            eligible = [s for s in self.stages if s["offset_days"] <= req["deadline_days"]]
            stage = eligible[-1] if eligible else self.stages[0]
        else:
            wanted = self.priority_seq.get(req["priority"], 3)
            stage = min(self.stages, key=lambda s: (abs(s["sequence"] - wanted), s["sequence"]))
        # A requirement is never scheduled before its prerequisites.
        fixed = self.ctx.get("scheduled_prerequisites", {})
        by_code = {s["code"]: s for s in self.stages}
        for dep in req.get("prerequisites", []):
            dep_stage = None
            if dep in self.requirements and dep != code:
                dep_stage = self._stage_for(self.requirements[dep])
            elif dep in fixed and fixed[dep] in by_code:
                dep_stage = by_code[fixed[dep]]
            if dep_stage and dep_stage["sequence"] > stage["sequence"]:
                stage = dep_stage
        self._stage_cache[code] = stage
        return stage

    def _ref(self, req: dict, stage: dict | None = None) -> dict:
        chunk = req["chunks"][0]
        return {
            "requirement_code": req["requirement_code"],
            "source_document_id": chunk["document_id"],
            "source_section_id": chunk["section_id"],
            "source_chunk_code": chunk["chunk_code"],
            "mandatory": req["is_mandatory"],
            "priority": req["priority"],
            "due_stage": (stage or self._stage_for(req))["code"],
        }

    # --------------------------------------------------------------- items
    @staticmethod
    def _clean(statement: str) -> str:
        return statement.strip().rstrip(".")

    def _quiz(self, req: dict) -> dict | None:
        statement = self._clean(req["statement"])
        types = self.ctx.get("quiz_types", ["MULTIPLE_CHOICE", "TRUE_FALSE"])
        match = DURATION.search(statement)
        if match and "MULTIPLE_CHOICE" in types:
            correct = match.group(0)
            unit = match.group(2)
            distractors = [f"{n} {unit}" for n in DISTRACTOR_NUMBERS if n != match.group(1).lower()][:3]
            options = sorted([correct] + distractors)
            stem = statement[:match.start()].strip().rstrip(",")
            return {
                **self._ref(req),
                "question_type": "MULTIPLE_CHOICE",
                "question": f"Complete the requirement: \"{stem} ...\"",
                "options": options,
                "correct_answer": [correct],
                "explanation": f"{req['source_document_code']} section {req['chunks'][0]['section_id']}: {statement}.",
                "difficulty": "BASIC",
            }
        if "TRUE_FALSE" in types:
            return {
                **self._ref(req),
                "question_type": "TRUE_FALSE",
                "question": f"True or false: {statement}.",
                "options": ["True", "False"],
                "correct_answer": ["True"],
                "explanation": f"Stated in {req['source_document_code']} section {req['chunks'][0]['section_id']}.",
                "difficulty": "BASIC",
            }
        return None

    def _module(self, competency: str, reqs: list[dict]) -> dict:
        reqs = sorted(reqs, key=lambda r: (self._stage_for(r)["sequence"], r["requirement_code"]))
        lead = reqs[0]
        checklist, tasks, quiz, scenarios, rubric = [], [], [], [], []
        for req in reqs:
            rtype = req["requirement_type"]
            statement = self._clean(req["statement"])
            if rtype == "MUST_ACKNOWLEDGE":
                checklist.append({**self._ref(req), "activity": f"Acknowledge: {statement}.",
                                  "is_required": True, "responsible_person": "Employee"})
            elif rtype in ("MUST_COMPLETE", "MUST_DEMONSTRATE"):
                tasks.append({
                    **self._ref(req),
                    "description": f"{statement}.",
                    "expected_outcome": f"Evidence that the requirement in {req['source_document_code']} "
                                        f"section {req['chunks'][0]['section_id']} is met.",
                    "completion_criteria": "Confirmed by your manager or the system of record.",
                    "difficulty": "INTERMEDIATE" if rtype == "MUST_DEMONSTRATE" else "BASIC",
                })
                checklist.append({**self._ref(req), "activity": f"Complete: {statement}.",
                                  "is_required": True,
                                  "responsible_person": "Manager" if rtype == "MUST_DEMONSTRATE" else "Employee"})
            elif rtype == "MUST_KNOW":
                scenarios.append({
                    **self._ref(req),
                    "title": f"Applying {req['source_document_code']} §{req['chunks'][0]['section_id']}",
                    "situation": f"You are asked to act in a way that conflicts with this rule: {statement}.",
                    "expected_action": "Decline, follow the documented rule and raise it with your manager.",
                })
            else:
                checklist.append({**self._ref(req), "activity": f"Optional: {statement}.",
                                  "is_required": False, "responsible_person": "Employee"})
            if req["is_mandatory"]:
                question = self._quiz(req)
                if question:
                    quiz.append(question)
            if req.get("assessment_required"):
                rubric.append({
                    "criterion": statement[:240],
                    "weight": 0.0,
                    "expected_performance": "Performs the requirement correctly without prompting.",
                    "pass_condition": "Observed or evidenced at least once.",
                    "requirement_code": req["requirement_code"],
                })

        assessment = None
        if rubric:
            weight = round(100 / len(rubric), 2)
            for criterion in rubric:
                criterion["weight"] = weight
            anchor = next(r for r in reqs if r["requirement_code"] == rubric[0]["requirement_code"])
            last_stage = max((self._stage_for(r) for r in reqs), key=lambda s: s["sequence"])
            assessment = {
                **self._ref(anchor, last_stage),
                "title": f"{competency} assessment",
                "assessment_type": "PRACTICAL",
                "topic": competency,
                "passing_score": 80.0,
                "rubric": rubric,
            }

        documents = list(OrderedDict.fromkeys(r["source_document_code"] for r in reqs))
        minutes = int(self.config.get("minutes_per_requirement", 15)) * len(reqs)
        return {
            **self._ref(lead),
            "title": f"{competency} for {self.ctx['role']['title']}s",
            "category": competency,
            "competency": competency,
            "purpose": f"Learn and apply the {competency.lower()} requirements that apply to your role.",
            "learning_objectives": [f"Explain and follow: {self._clean(r['statement'])}." for r in reqs[:6]],
            "key_concepts": [competency] + [f"{r['source_document_code']} §{r['chunks'][0]['section_id']}"
                                            for r in reqs[:5]],
            "required_source_documents": documents,
            "estimated_duration_minutes": max(15, minutes),
            "learning_activities": [f"Read {r['source_document_code']} section {r['chunks'][0]['section_id']}."
                                    for r in reqs[:6]] + ["Discuss anything unclear with your manager."],
            "assessment_summary": f"{len(quiz)} quiz question(s)" + (" and a practical assessment." if assessment else "."),
            "completion_criteria": "All required checklist items and tasks complete, and a quiz score of at least 80%.",
            "requirement_codes": [r["requirement_code"] for r in reqs],
            "checklist": checklist,
            "tasks": tasks,
            "scenarios": scenarios,
            "quiz": quiz,
            "assessment": assessment,
        }

    def _modules(self) -> list[dict]:
        groups: OrderedDict[str, list[dict]] = OrderedDict()
        supported = [r for r in self.ctx["requirements"] if r.get("chunks")]
        for req in sorted(supported, key=lambda r: r["requirement_code"]):
            groups.setdefault(req["competency"], []).append(req)
        modules = [self._module(c, reqs) for c, reqs in groups.items()]
        seq = {s["code"]: s["sequence"] for s in self.stages}
        return sorted(modules, key=lambda m: (seq.get(m["due_stage"], 99), m["title"]))

    def _gaps(self) -> list[dict]:
        return [
            {"topic": g["topic"], "reason": g["reason"], "requirement_code": g.get("requirement_code")}
            for g in self.ctx.get("gaps", [])
        ]

    def plan(self) -> dict:
        employee, role = self.ctx["employee"], self.ctx["role"]
        return {
            "employee_code": employee["employee_code"],
            "role_code": role["code"],
            "plan_title": f"{role['title']} onboarding plan for {employee['full_name']}",
            "summary": f"A {len(self.stages)}-stage onboarding plan covering "
                       f"{len(self.ctx['requirements'])} Matrix requirements for the {role['title']} role.",
            "modules": self._modules(),
            "gaps": self._gaps(),
        }

    def modules_only(self) -> dict:
        return {"modules": self._modules(), "gaps": self._gaps()}
