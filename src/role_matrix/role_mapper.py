"""Maps requirements to job roles. Every mapping is explainable: it records the
method and the phrase that triggered it. Embedding similarity is never used,
because the Matrix must be defensible line by line.

Works for roles created after the documents were uploaded, since role titles
are read from the database at mapping time.
"""
import re
from dataclasses import dataclass
from typing import Any

from src.core.textutil import phrase_regex
from src.models.enums import MappingMethod, Priority, RequirementType

BOOST = {Priority.MEDIUM: Priority.HIGH, Priority.LOW: Priority.MEDIUM}


@dataclass
class RoleInput:
    id: Any
    code: str
    title: str
    department_id: Any
    department_name: str
    department_code: str = ""


@dataclass
class RequirementInput:
    id: Any
    code: str
    statement: str
    requirement_type: RequirementType
    is_mandatory: bool
    priority: Priority
    document_department_id: Any | None
    clause_text: str = ""   # the whole numbered clause the sentence came from


@dataclass
class Mapping:
    job_role_id: Any
    requirement_id: Any
    is_mandatory_for_role: bool
    priority_for_role: Priority
    mapping_method: MappingMethod
    mapping_reason: str


def _role_pattern(role: RoleInput, aliases: dict[str, list[str]]) -> re.Pattern:
    phrases = [re.escape(role.title.lower()) + "s?"]
    phrases += aliases.get(role.code, [])
    return phrase_regex(phrases)


class RoleMapper:
    def __init__(self, roles: list[RoleInput], rules: dict):
        self.roles = roles
        self.rules = rules
        aliases = rules.get("role_aliases", {})
        self.patterns = {r.id: _role_pattern(r, aliases) for r in roles}
        suffixes = rules.get("department_mention_suffixes", [])
        departments = {r.department_id: r.department_name for r in roles}
        self.department_patterns = {
            dept_id: phrase_regex([re.escape(name.lower()) + r"\s+(?:" + "|".join(suffixes) + ")"])
            for dept_id, name in departments.items()
        } if suffixes else {}
        self.applies_all = phrase_regex(rules.get("applies_to_all_markers", []))
        self.boost = rules.get("explicit_mention_priority_boost", True)
        self.topics = [
            (re.compile(r"\b(?:" + t["pattern"] + ")", re.IGNORECASE), set(t.get("departments", [])))
            for t in rules.get("topic_departments", [])
        ]

    def _mapping(self, role, req, method, reason, boost=False) -> Mapping:
        priority = BOOST.get(req.priority, req.priority) if boost and self.boost else req.priority
        return Mapping(role.id, req.id, req.is_mandatory, priority, method, reason)

    def map(self, req: RequirementInput) -> list[Mapping]:
        if req.requirement_type == RequirementType.NOT_APPLICABLE:
            return []

        # Roles named after "except" are excluded, not included.
        lowered = req.statement.lower()
        main, _, excepted = lowered.partition(" except ")
        excluded = {rid for rid, p in self.patterns.items() if excepted and p.search(excepted)}

        mappings: dict[Any, Mapping] = {}
        for role in self.roles:
            if role.id in excluded:
                continue
            match = self.patterns[role.id].search(main)
            if match:
                mappings[role.id] = self._mapping(
                    role, req, MappingMethod.EXPLICIT_ROLE_MENTION,
                    f"Sentence names the role: '{match.group(0)}'", boost=True,
                )
        for role in self.roles:
            if role.id in mappings or role.id in excluded:
                continue
            pattern = self.department_patterns.get(role.department_id)
            match = pattern.search(main) if pattern else None
            if match:
                mappings[role.id] = self._mapping(
                    role, req, MappingMethod.DEPARTMENT_MATCH,
                    f"Sentence names the role's department: '{match.group(0)}'",
                )
        if mappings:
            return list(mappings.values())

        # A continuation sentence ("The query must be logged ...") inherits the
        # role its clause names ("... a DevOps Engineer may query raw records").
        clause = req.clause_text.lower().partition(" except ")[0]
        if clause and clause != main:
            for role in self.roles:
                if role.id in excluded:
                    continue
                match = self.patterns[role.id].search(clause)
                if match:
                    mappings[role.id] = self._mapping(
                        role, req, MappingMethod.EXPLICIT_ROLE_MENTION,
                        f"The clause this sentence continues names the role: '{match.group(0)}'", boost=True,
                    )
            if mappings:
                return list(mappings.values())

        if req.document_department_id is not None:
            dept_roles = [r for r in self.roles if r.department_id == req.document_department_id]
            return [
                self._mapping(
                    r, req, MappingMethod.DEPARTMENT_MATCH,
                    f"Source document belongs to the {r.department_name} department",
                )
                for r in dept_roles if r.id not in excluded
            ]

        match = self.applies_all.search(main) if self.applies_all else None
        if match is None:
            for pattern, dept_codes in self.topics:
                topic = pattern.search(main)
                if topic:
                    targets = [r for r in self.roles if r.department_code in dept_codes and r.id not in excluded]
                    if targets:
                        return [
                            self._mapping(r, req, MappingMethod.DEPARTMENT_MATCH,
                                          f"Clause concerns '{topic.group(0)}', an activity of the "
                                          f"{r.department_name} department")
                            for r in targets
                        ]
        reason = (
            f"Sentence applies to everyone: '{match.group(0)}'" if match
            else "Company-wide document with no department, and no role is named"
        )
        return [
            self._mapping(r, req, MappingMethod.APPLIES_TO_ALL, reason)
            for r in self.roles if r.id not in excluded
        ]
