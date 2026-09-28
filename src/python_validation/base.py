"""Pipeline 2 foundations: the validation context, findings, statuses and the
rule registry. Plain Python. The engine receives data; it loads nothing and
calls no generative model."""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Item-level statuses, SRS section 1.2.
VERIFIED = "VERIFIED"
VERIFIED_WITH_WARNING = "VERIFIED_WITH_WARNING"
PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
SOURCE_SUPPORT_MISSING = "SOURCE_SUPPORT_MISSING"
REQUIREMENT_MISSING = "REQUIREMENT_MISSING"
UNSUPPORTED_REQUIREMENT = "UNSUPPORTED_REQUIREMENT"
OUTDATED_SOURCE = "OUTDATED_SOURCE"
CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
ITEM_STATUSES = [
    VERIFIED, VERIFIED_WITH_WARNING, PARTIALLY_VERIFIED, SOURCE_SUPPORT_MISSING, REQUIREMENT_MISSING,
    UNSUPPORTED_REQUIREMENT, OUTDATED_SOURCE, CONTRADICTION_DETECTED, MANUAL_REVIEW_REQUIRED,
]

SEVERITIES = ["CRITICAL", "ERROR", "WARNING", "INFO"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    item_status: str
    item_type: str | None = None
    item_id: str | None = None
    requirement_code: str | None = None
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "rule": self.rule, "severity": self.severity, "message": self.message,
            "item_status": self.item_status, "item_type": self.item_type, "item_id": self.item_id,
            "requirement_code": self.requirement_code, "evidence": self.evidence,
        }


@dataclass
class RuleOutput:
    findings: list[Finding] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)


@dataclass
class ActiveChunk:
    chunk_code: str
    document_id: str
    document_code: str
    section_id: str | None
    content: str


@dataclass
class ValidationContext:
    plan: dict
    items: list[dict]
    role: dict
    known_role_codes: set[str]
    matrix: list[dict]                       # the role's Matrix rows
    requirements: dict[str, dict]            # every requirement by code
    requirement_roles: dict[str, list[str]]  # code -> role titles it maps to
    documents: dict[str, dict]               # every document version by id
    document_sections: dict[str, set]        # document id -> section ids
    document_chunks: dict[str, dict]         # document id -> {chunk_code: section_id}
    active_chunks: list[ActiveChunk]
    active_vectors: np.ndarray               # aligned with active_chunks, L2-normalised
    chunk_text: dict[tuple, str]             # (document_id, chunk_code) -> content
    prerequisites: list[tuple[str, str, str]]  # (requirement, depends_on, reason)
    stages: dict[str, dict]                  # stage code -> {sequence, offset_days, name}
    quiz_types: set[str]
    config: dict                             # validation_rules
    business_rules: list[dict]
    contradictions: list[dict]               # corpus contradictions, precomputed
    embed: Callable[[list[str]], np.ndarray]

    @property
    def matrix_by_code(self) -> dict[str, dict]:
        return {r["requirement_code"]: r for r in self.matrix}

    def rule_settings(self, name: str) -> dict:
        return (self.config.get("rules", {}) or {}).get(name, {}) or {}

    def best_chunks(self, vectors: np.ndarray, top: int = 1) -> list[list[tuple[ActiveChunk, float]]]:
        if len(self.active_chunks) == 0 or len(vectors) == 0:
            return [[] for _ in range(len(vectors))]
        sims = vectors @ self.active_vectors.T
        results = []
        for row in sims:
            order = np.argsort(-row)[:top]
            results.append([(self.active_chunks[i], float(row[i])) for i in order])
        return results

    def stage_seq(self, code: str | None) -> int | None:
        stage = self.stages.get(code or "")
        return stage["sequence"] if stage else None


class Rule:
    name: str = ""
    description: str = ""

    def run(self, ctx: ValidationContext, settings: dict) -> RuleOutput:
        raise NotImplementedError


REGISTRY: dict[str, type[Rule]] = {}


def register(cls: type[Rule]) -> type[Rule]:
    REGISTRY[cls.name] = cls
    return cls


def item_text(item: dict) -> list[tuple[str, str]]:
    """(field, text) pairs of generated prose on an item."""
    fields = {
        "module": ["purpose", "learning_objectives", "learning_activities", "assessment_summary",
                   "completion_criteria"],
        "checklist_item": ["activity"],
        "task": ["description", "expected_outcome", "completion_criteria"],
        "quiz_question": ["explanation"],
        "assessment": ["title"],
        "scenario": ["situation", "expected_action"],
    }.get(item["item_type"], [])
    pairs = []
    for name in fields:
        value = item.get(name)
        if isinstance(value, list):
            pairs += [(name, v) for v in value if isinstance(v, str) and v.strip()]
        elif isinstance(value, str) and value.strip():
            pairs.append((name, value))
    if item["item_type"] == "assessment":
        pairs += [("rubric", r["criterion"]) for r in item.get("rubric", [])]
    return pairs


def primary_text(item: dict) -> str:
    return {
        "module": lambda i: f"{i.get('title', '')}. {i.get('purpose', '')}",
        "checklist_item": lambda i: i.get("activity", ""),
        "task": lambda i: i.get("description", ""),
        "quiz_question": lambda i: i.get("question", ""),
        "assessment": lambda i: f"{i.get('title', '')} {i.get('topic', '')}",
        "scenario": lambda i: i.get("situation", ""),
    }[item["item_type"]](item)
