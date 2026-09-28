"""Rules 4-6: quiz answers, learning sequence, hallucination."""
import re

import numpy as np

from src.core.textutil import durations, lexical_overlap, phrase_regex, split_sentences
from src.python_validation.base import (
    CONTRADICTION_DETECTED,
    MANUAL_REVIEW_REQUIRED,
    PARTIALLY_VERIFIED,
    SOURCE_SUPPORT_MISSING,
    UNSUPPORTED_REQUIREMENT,
    Finding,
    Rule,
    RuleOutput,
    ValidationContext,
    item_text,
    register,
)

TF_PREFIX = re.compile(r"^\s*true or false\s*[:\-]\s*", re.IGNORECASE)


def _hours(text: str) -> set[float]:
    return {round(d["hours"], 3) for d in durations(text)}


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


@register
class QuizAnswerRule(Rule):
    name = "quiz_answers"
    description = "Correct answers are supported by the cited chunk and no distractor is true (SRS Step 22)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        threshold = float(settings.get("support_threshold", 0.40))
        margin = float(settings.get("distractor_margin", 0.05))
        questions = [i for i in ctx.items if i["item_type"] == "quiz_question"]
        checked = supported = 0
        for q in questions:
            iid, code = str(q["id"]), q.get("requirement_code")
            chunk = ctx.chunk_text.get((str(q.get("source_document_id")), q.get("source_chunk_code")))
            if chunk is None:
                out.findings.append(Finding(self.name, "ERROR", "The cited chunk cannot be found, so the answer "
                                            "cannot be checked", SOURCE_SUPPORT_MISSING, "quiz_question", iid, code))
                continue
            checked += 1
            options = q.get("options") or []
            answers = q.get("correct_answer") or []
            stem = TF_PREFIX.sub("", q.get("question", ""))
            is_tf = (q.get("question_type") == "TRUE_FALSE") or set(o.lower() for o in options) == {"true", "false"}
            chunk_hours = _hours(chunk)

            if is_tf:
                claim_true = any(a.lower() == "true" for a in answers)
                stem_hours = _hours(stem)
                conflicting = bool(stem_hours and chunk_hours and not (stem_hours & chunk_hours))
                if claim_true and conflicting:
                    out.findings.append(Finding(
                        self.name, "ERROR", "The statement marked True contradicts its cited section",
                        CONTRADICTION_DETECTED, "quiz_question", iid, code,
                        {"statement": stem, "chunk": chunk[:300], "statement_durations": sorted(stem_hours),
                         "chunk_durations": sorted(chunk_hours)}))
                    continue
                support = self._support(ctx, stem, chunk)
                if claim_true and support < threshold:
                    out.findings.append(Finding(
                        self.name, "ERROR", f"The statement marked True is not supported by its cited chunk "
                        f"(support {support:.2f})", SOURCE_SUPPORT_MISSING, "quiz_question", iid, code,
                        {"statement": stem, "chunk": chunk[:300], "support": round(support, 3)}))
                    continue
                # A False statement is usually a near copy with one fact changed, so
                # only an almost verbatim copy counts as "actually stated".
                if not claim_true and not conflicting and lexical_overlap(stem, chunk) >= 0.9:
                    out.findings.append(Finding(
                        self.name, "ERROR", "The statement marked False is actually stated by the cited chunk",
                        CONTRADICTION_DETECTED, "quiz_question", iid, code,
                        {"statement": stem, "chunk": chunk[:300], "support": round(support, 3)}))
                    continue
                supported += 1
                continue

            answer_hours = set().union(*[_hours(a) for a in answers]) if answers else set()
            if chunk_hours and answer_hours and not (answer_hours & chunk_hours):
                out.findings.append(Finding(
                    self.name, "ERROR", f"The stated answer {answers} contradicts the cited section",
                    CONTRADICTION_DETECTED, "quiz_question", iid, code,
                    {"answer": answers, "chunk": chunk[:300], "chunk_durations_hours": sorted(chunk_hours)}))
                continue
            distractors = [o for o in options if o not in answers]
            true_distractors = [d for d in distractors if chunk_hours and _hours(d) and _hours(d) <= chunk_hours
                                and not answer_hours & _hours(d)]
            if true_distractors:
                out.findings.append(Finding(
                    self.name, "ERROR", f"Distractor(s) {true_distractors} are true according to the cited section",
                    CONTRADICTION_DETECTED, "quiz_question", iid, code,
                    {"distractors": true_distractors, "chunk": chunk[:300]}))
                continue
            answer_support = max((self._support(ctx, f"{stem} {a}", chunk) for a in answers), default=0.0)
            if answer_support < threshold:
                out.findings.append(Finding(
                    self.name, "ERROR", f"The correct answer is not supported by the cited chunk "
                    f"(support {answer_support:.2f})", SOURCE_SUPPORT_MISSING, "quiz_question", iid, code,
                    {"answer": answers, "support": round(answer_support, 3), "chunk": chunk[:300]}))
                continue
            suspicious = [d for d in distractors if not _hours(d)
                          and lexical_overlap(d, chunk) >= 0.8 and lexical_overlap(d, chunk) + margin
                          >= max(lexical_overlap(a, chunk) for a in answers or [""])]
            if suspicious:
                out.findings.append(Finding(
                    self.name, "WARNING", f"Distractor(s) {suspicious} are worded like the cited section and "
                    "may be true", MANUAL_REVIEW_REQUIRED, "quiz_question", iid, code,
                    {"distractors": suspicious}))
            supported += 1
        out.summary = {"questions": len(questions), "checked": checked, "supported": supported}
        return out

    @staticmethod
    def _support(ctx: ValidationContext, claim: str, chunk: str) -> float:
        vectors = ctx.embed([claim, chunk])
        return max(_cos(vectors[0], vectors[1]), lexical_overlap(claim, chunk))


@register
class LearningSequenceRule(Rule):
    name = "learning_sequence"
    description = "Prerequisites present and earlier, basics before advanced, learning before assessment (Step 27)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        earliest: dict[str, int] = {}
        for item in ctx.items:
            seq = ctx.stage_seq(item.get("due_stage"))
            code = item.get("requirement_code")
            if seq is None or not code or item["item_type"] in ("module", "assessment"):
                continue
            earliest[code] = min(seq, earliest.get(code, seq))
        matrix = ctx.matrix_by_code
        stage_name = {v["sequence"]: k for k, v in ctx.stages.items()}

        for req_code, dep_code, reason in ctx.prerequisites:
            if req_code not in earliest:
                continue
            if dep_code not in earliest:
                if dep_code in matrix:
                    out.findings.append(Finding(
                        self.name, "WARNING", f"{req_code} depends on {dep_code}, which the plan does not include",
                        PARTIALLY_VERIFIED, "requirement", req_code, req_code,
                        {"requirement": req_code, "prerequisite": dep_code, "reason": reason}))
                continue
            if earliest[dep_code] > earliest[req_code]:
                out.findings.append(Finding(
                    self.name, "ERROR",
                    f"{req_code} is scheduled at {stage_name.get(earliest[req_code])} before its prerequisite "
                    f"{dep_code} at {stage_name.get(earliest[dep_code])}",
                    MANUAL_REVIEW_REQUIRED, "requirement", req_code, req_code,
                    {"requirement": req_code, "prerequisite": dep_code, "reason": reason,
                     "requirement_stage": stage_name.get(earliest[req_code]),
                     "prerequisite_stage": stage_name.get(earliest[dep_code])}))

        by_competency: dict[str, list[dict]] = {}
        modules = {i["id"]: i for i in ctx.items if i["item_type"] == "module"}
        for item in ctx.items:
            if item["item_type"] == "task":
                competency = modules.get(item["module_id"], {}).get("competency") or "General"
                by_competency.setdefault(competency, []).append(item)
        for competency, tasks in by_competency.items():
            basics = [ctx.stage_seq(t["due_stage"]) for t in tasks if t.get("difficulty") == "BASIC"]
            for t in tasks:
                seq = ctx.stage_seq(t.get("due_stage"))
                if t.get("difficulty") == "ADVANCED" and basics and seq is not None and seq < min(b for b in basics if b is not None):
                    out.findings.append(Finding(
                        self.name, "ERROR", f"Advanced task scheduled before the basic training in '{competency}'",
                        MANUAL_REVIEW_REQUIRED, "task", str(t["id"]), t.get("requirement_code"),
                        {"competency": competency, "task_stage": t.get("due_stage")}))

        for item in ctx.items:
            if item["item_type"] != "assessment":
                continue
            seq = ctx.stage_seq(item.get("due_stage"))
            assessed = {r.get("requirement_code") for r in item.get("rubric", [])} | {item.get("requirement_code")}
            learning = [ctx.stage_seq(i.get("due_stage")) for i in ctx.items
                        if i["module_id"] == item["module_id"] and i["item_type"] in ("task", "checklist_item")
                        and i.get("requirement_code") in assessed]
            learning = [s for s in learning if s is not None]
            if seq is not None and learning and seq < max(learning):
                out.findings.append(Finding(
                    self.name, "ERROR", "Assessment is scheduled before the learning content it assesses",
                    MANUAL_REVIEW_REQUIRED, "assessment", str(item["id"]), item.get("requirement_code"),
                    {"assessment_stage": item.get("due_stage"), "latest_content_stage": stage_name.get(max(learning))}))
        out.summary = {"prerequisite_edges": len(ctx.prerequisites), "issues": len(out.findings)}
        return out


def _is_active(ctx: ValidationContext, item: dict) -> bool:
    doc = ctx.documents.get(str(item.get("source_document_id")))
    return bool(doc and doc["status"] == "ACTIVE")


@register
class HallucinationRule(Rule):
    name = "hallucination"
    description = "Every factual company-rule claim is supported by an active chunk (SRS Steps 31-32)"

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        out = RuleOutput()
        rule_floor = float(settings.get("rule_claim_floor", 0.55))
        general_floor = float(settings.get("general_floor", 0.35))
        mechanics = phrase_regex(ctx.config.get("plan_mechanics_patterns", []))
        rule_claim = phrase_regex(ctx.config.get("rule_claim_patterns", []))
        instructional = phrase_regex(ctx.config.get("instructional_patterns", []))

        claims: list[tuple[dict, str, str]] = []
        for item in ctx.items:
            for fname, text in item_text(item):
                for sentence in split_sentences(text):
                    claims.append((item, fname, sentence))
        counts = {"source_supported": 0, "instructional": 0, "unsupported_rule_claim": 0,
                  "weak_general": 0, "plan_mechanics": 0}
        pending = []
        for item, fname, sentence in claims:
            if mechanics and mechanics.search(sentence):
                counts["plan_mechanics"] += 1
                continue
            # "Complete: <clause>" or "... conflicts with this rule: <clause>":
            # the short framing is instructional; the quoted clause is the claim.
            prefix, sep, rest = sentence.partition(":")
            if sep and rest.strip() and len(prefix.split()) <= 14:
                sentence = rest.strip()
            is_rule = bool(rule_claim and rule_claim.search(sentence))
            if not is_rule and instructional and instructional.search(sentence):
                counts["instructional"] += 1
                continue
            pending.append((item, fname, sentence, is_rule))

        overlap_floor = float(settings.get("lexical_support_floor", 0.75))
        unsupported_rules = 0
        if pending:
            vectors = ctx.embed([p[2] for p in pending])
            best = ctx.best_chunks(vectors, top=3)
            for (item, fname, sentence, is_rule), hits in zip(pending, best):
                chunk, score = hits[0] if hits else (None, 0.0)
                # A sentence copied from a long clause embeds far from the whole
                # chunk, so word overlap with the cited or nearest chunks is a
                # second, deterministic support signal.
                cited = ctx.chunk_text.get((str(item.get("source_document_id")), item.get("source_chunk_code")))
                candidates = [c.content for c, _ in hits] + ([cited] if cited and _is_active(ctx, item) else [])
                overlap = max((lexical_overlap(sentence, text) for text in candidates), default=0.0)
                if overlap >= overlap_floor:
                    score = max(score, overlap)
                if is_rule and score < rule_floor:
                    unsupported_rules += 1
                    counts["unsupported_rule_claim"] += 1
                    out.findings.append(Finding(
                        self.name, "ERROR", f"Unsupported claim about company rules in {item['item_type']}.{fname}",
                        UNSUPPORTED_REQUIREMENT, item["item_type"], str(item.get("id")), item.get("requirement_code"),
                        {"claim": sentence, "best_similarity": round(score, 3), "floor": rule_floor,
                         "closest_chunk": chunk.chunk_code if chunk else None,
                         "category": "UNSUPPORTED_FACTUAL_CLAIM"}))
                elif not is_rule and score < general_floor:
                    counts["weak_general"] += 1
                    out.findings.append(Finding(
                        self.name, "INFO", f"Sentence in {item['item_type']}.{fname} has little source support",
                        MANUAL_REVIEW_REQUIRED, item["item_type"], str(item.get("id")), item.get("requirement_code"),
                        {"claim": sentence, "best_similarity": round(score, 3), "category": "GENERAL_WORDING"}))
                else:
                    counts["source_supported"] += 1
        out.summary = {"claims_checked": len(claims), **counts}
        out.metrics = {"unsupported_claim_count": unsupported_rules}
        return out
