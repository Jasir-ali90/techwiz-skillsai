"""Requirement extraction (SRS Steps 10-11). Deterministic Python only.

Takes chunks in, returns candidate requirements out. Persistence and code
assignment live in the service, so this module is pure and unit-testable.
"""
import re
from dataclasses import dataclass, field
from typing import Any

from src.core.textutil import deadline_days, phrase_regex, split_sentences
from src.models.enums import MANDATORY_TYPES, Priority, RequirementType

POLICY_TYPES = {
    "INFOSEC_POLICY", "DATA_PRIVACY_POLICY", "CONDUCT_POLICY", "HR_POLICY",
    "LEAVE_POLICY", "COMPLIANCE_INSTRUCTION", "HANDBOOK", "FAQ",
}
PROCESS_TYPES = {"DEPARTMENT_SOP", "PROCESS_DOCUMENT", "ESCALATION_PROCEDURE", "ROLE_DESCRIPTION"}


@dataclass
class ChunkInput:
    chunk_id: Any
    chunk_code: str
    section_id: str | None
    heading: str | None
    content: str
    document_id: Any
    document_code: str
    document_type: str
    document_title: str
    is_suspicious: bool = False


@dataclass
class ExtractedRequirement:
    source_key: str
    statement: str
    requirement_type: RequirementType
    is_mandatory: bool
    priority: Priority
    competency: str
    policy_requirement: str | None
    process_requirement: str | None
    assessment_required: bool
    assessment_topic: str | None
    applies_to_all_roles: bool
    is_compliance: bool
    deadline_days: int | None
    conditions: dict
    extraction_confidence: float
    extraction_method: str
    source_document_id: Any
    source_document_code: str
    source_chunk_id: Any
    source_chunk_code: str
    source_section_id: str | None


@dataclass
class ExtractionOutcome:
    requirements: list[ExtractedRequirement] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RuleSet:
    """Compiled view of config/requirement_rules.yaml."""

    def __init__(self, config: dict):
        self.config = config
        self.informational = phrase_regex(config.get("informational_markers", []))
        self.informational_headings = [h.lower() for h in config.get("informational_headings", [])]
        self.families = [
            (f["name"], RequirementType(f["type"]), phrase_regex(f["patterns"]))
            for f in config.get("modal_families", [])
        ]
        self.condition = re.compile(
            r"(?<![\w])(" + "|".join(re.escape(m) for m in config.get("condition_markers", [])) + r")(?![\w])",
            re.IGNORECASE,
        )
        self.exception = phrase_regex([re.escape(m) for m in config.get("exception_markers", [])])
        self.exclusion = phrase_regex([re.escape(m) for m in config.get("exclusion_markers", [])])
        signals = config.get("priority_signals", {})
        self.critical = phrase_regex(signals.get("critical", []))
        self.high = phrase_regex(signals.get("high", []))
        self.default_priority = Priority(config.get("default_priority", "MEDIUM"))
        self.default_by_type = {
            RequirementType(k): Priority(v) for k, v in config.get("default_priority_by_type", {}).items()
        }
        self.competencies = [
            (re.compile(r"\b(?:" + pattern + ")", re.IGNORECASE), name)
            for pattern, name in config.get("competency_keywords", {}).items()
        ]
        self.compliance = phrase_regex([re.escape(m) for m in config.get("compliance_markers", [])])
        self.applies_all = phrase_regex(config.get("applies_to_all_markers", []))
        self.deadline_anchor = phrase_regex(config.get("deadline_anchor_patterns", []))

    def onboarding_deadline(self, sentence: str) -> int | None:
        if self.deadline_anchor is None or not self.deadline_anchor.search(sentence):
            return None
        return deadline_days(sentence)


def classify(sentence: str, rules: RuleSet) -> tuple[str, RequirementType] | None:
    for name, rtype, pattern in rules.families:
        if pattern is not None and pattern.search(sentence):
            return name, rtype
    return None


def _priority(sentence: str, rtype: RequirementType, rules: RuleSet) -> tuple[Priority, str]:
    if rtype in MANDATORY_TYPES:
        if rules.critical and (m := rules.critical.search(sentence)):
            return Priority.CRITICAL, f"critical:{m.group(0).lower()}"
        if rules.high and (m := rules.high.search(sentence)):
            return Priority.HIGH, f"high:{m.group(0).lower()}"
    default = rules.default_by_type.get(rtype, rules.default_priority)
    return default, "default"


def _competency(sentence: str, heading: str | None, rules: RuleSet) -> tuple[str, str]:
    for pattern, name in rules.competencies:
        if pattern.search(sentence):
            return name, "keyword"
    # The heading goes through the same keyword map, so "Audit Evidence" and
    # "Evidence for Client Audits" land on one competency.
    for pattern, name in rules.competencies:
        if heading and pattern.search(heading):
            return name, "heading_keyword"
    return (heading or "General").strip()[:150], "heading"


def _conditions(sentence: str, rules: RuleSet) -> dict:
    conditions: dict = {}
    match = rules.condition.search(sentence)
    if match:
        conditions["condition"] = sentence[match.start():].strip().rstrip(".")
        conditions["marker"] = match.group(1).lower()
    if rules.exception and rules.exception.search(sentence):
        conditions["exception"] = True
    if rules.exclusion and (m := rules.exclusion.search(sentence)):
        conditions["exclusion"] = sentence[m.start():].strip().rstrip(".")
    return conditions


def extract_from_chunk(chunk: ChunkInput, rules: RuleSet) -> ExtractionOutcome:
    outcome = ExtractionOutcome()
    if chunk.is_suspicious:
        outcome.warnings.append(
            f"{chunk.chunk_code} is flagged as suspicious and was not read for requirements"
        )
        return outcome
    heading = (chunk.heading or "").lower()
    if any(h in heading for h in rules.informational_headings):
        for sentence in split_sentences(chunk.content):
            outcome.rejected.append(
                {"chunk_code": chunk.chunk_code, "sentence": sentence, "reason": "informational_heading"}
            )
        return outcome

    section_key = chunk.section_id or chunk.chunk_code.split("#")[-1]
    for index, sentence in enumerate(split_sentences(chunk.content), start=1):
        if rules.informational and (m := rules.informational.search(sentence)):
            outcome.rejected.append({
                "chunk_code": chunk.chunk_code, "sentence": sentence,
                "reason": f"informational:{m.group(0).lower()}",
            })
            continue
        if sentence.rstrip().endswith("?"):
            outcome.rejected.append({"chunk_code": chunk.chunk_code, "sentence": sentence, "reason": "question"})
            continue
        classified = classify(sentence, rules)
        if classified is None:
            outcome.rejected.append(
                {"chunk_code": chunk.chunk_code, "sentence": sentence, "reason": "no_modal_verb"}
            )
            continue

        family, rtype = classified
        is_mandatory = rtype in MANDATORY_TYPES
        priority, priority_rule = _priority(sentence, rtype, rules)
        competency, competency_rule = _competency(sentence, chunk.heading, rules)
        conditions = _conditions(sentence, rules)
        assessment_required = rtype in {RequirementType.MUST_DEMONSTRATE, RequirementType.MUST_COMPLETE}
        location = f"{chunk.document_title} §{chunk.section_id}" if chunk.section_id else chunk.document_title

        signals = 1 + (priority_rule != "default") + (competency_rule == "keyword") + bool(chunk.section_id)
        confidence = min(0.95, 0.35 + 0.15 * signals - (0.1 if family == "generic_mandatory" else 0))

        outcome.requirements.append(ExtractedRequirement(
            source_key=f"{chunk.document_code}:{section_key}:{index}",
            statement=sentence,
            requirement_type=rtype,
            is_mandatory=is_mandatory,
            priority=priority,
            competency=competency,
            policy_requirement=location if chunk.document_type in POLICY_TYPES else None,
            process_requirement=location if chunk.document_type in PROCESS_TYPES else None,
            assessment_required=assessment_required,
            assessment_topic=competency if assessment_required else None,
            applies_to_all_roles=bool(rules.applies_all and rules.applies_all.search(sentence)),
            is_compliance=bool(
                chunk.document_type == "COMPLIANCE_INSTRUCTION"
                or (rules.compliance and rules.compliance.search(sentence))
            ),
            deadline_days=rules.onboarding_deadline(sentence),
            conditions=conditions,
            extraction_confidence=round(confidence, 2),
            extraction_method=f"modal:{family}|priority:{priority_rule}|competency:{competency_rule}",
            source_document_id=chunk.document_id,
            source_document_code=chunk.document_code,
            source_chunk_id=chunk.chunk_id,
            source_chunk_code=chunk.chunk_code,
            source_section_id=chunk.section_id,
        ))
    return outcome
