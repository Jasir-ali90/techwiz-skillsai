"""Prerequisite detection and cycle rejection.

Two deterministic sources of edges:
1. Named artefacts. A requirement that completes, passes or acknowledges a
   named artefact ("Production Access Certification") provides it. A
   requirement that mentions the artefact after a marker ("before", "once"), or
   without a provider verb, depends on the provider.
2. Competency levels. Within one competency, basics come before advanced.

Any edge that would close a cycle is rejected and reported.
"""
import re
from dataclasses import dataclass
from typing import Any

import networkx as nx

from src.core.textutil import phrase_regex


@dataclass
class ReqNode:
    id: Any
    code: str
    statement: str
    competency: str


@dataclass
class Edge:
    requirement_id: Any
    requirement_code: str
    depends_on_id: Any
    depends_on_code: str
    reason: str
    method: str


def _artifact_regex(suffixes: list[str]) -> re.Pattern:
    alternatives = "|".join(re.escape(s) for s in suffixes)
    return re.compile(r"((?:[A-Z][\w/-]*\s+){1,5})(?i:(" + alternatives + r"))\b")


def artifacts(statement: str, pattern: re.Pattern) -> list[tuple[str, int, int]]:
    found = []
    for match in pattern.finditer(statement):
        prefix = [w for w in match.group(1).split() if w.lower() not in {"the", "a", "an", "their", "this"}]
        if not prefix:
            continue
        key = " ".join(prefix).lower()
        if match.group(2).lower() == "basics":
            key += " basics"
        found.append((key, match.start(), match.end()))
    return found


def detect(nodes: list[ReqNode], rules: dict) -> tuple[list[Edge], list[dict]]:
    artifact_re = _artifact_regex(rules.get("artifact_suffixes", []))
    marker_re = phrase_regex([re.escape(m) for m in rules.get("prerequisite_markers", [])])
    provider_re = phrase_regex([re.escape(v) for v in rules.get("provider_verbs", [])])
    levels = {
        int(level): phrase_regex([re.escape(w) for w in words])
        for level, words in rules.get("competency_levels", {}).items()
    }

    providers: dict[str, list[ReqNode]] = {}
    consumers: dict[str, list[tuple[ReqNode, str]]] = {}
    for node in nodes:
        marker = marker_re.search(node.statement) if marker_re else None
        for key, start, _ in artifacts(node.statement, artifact_re):
            after_marker = marker is not None and start > marker.start()
            window = node.statement[max(0, start - 45):start]
            has_provider_verb = bool(provider_re and provider_re.search(window))
            if has_provider_verb and not after_marker:
                providers.setdefault(key, []).append(node)
            else:
                how = f"mentions it after '{marker.group(0)}'" if after_marker else "relies on it"
                consumers.setdefault(key, []).append((node, how))

    candidates: list[Edge] = []
    for key, users in consumers.items():
        for provider in providers.get(key, []):
            for consumer, how in users:
                if consumer.id == provider.id:
                    continue
                candidates.append(Edge(
                    consumer.id, consumer.code, provider.id, provider.code,
                    f"{consumer.code} {how} the '{key}' artefact, which {provider.code} requires completing",
                    "EXPLICIT_MARKER",
                ))

    def level_of(statement: str) -> int | None:
        hits = [lvl for lvl, pattern in levels.items() if pattern and pattern.search(statement)]
        return min(hits) if hits else None

    by_competency: dict[str, list[tuple[ReqNode, int]]] = {}
    for node in nodes:
        lvl = level_of(node.statement)
        if lvl is not None:
            by_competency.setdefault(node.competency, []).append((node, lvl))
    for competency, group in by_competency.items():
        for advanced, adv_level in group:
            for basic, basic_level in group:
                if basic_level < adv_level and basic.id != advanced.id:
                    candidates.append(Edge(
                        advanced.id, advanced.code, basic.id, basic.code,
                        f"Within '{competency}', level {basic_level} ({basic.code}) comes before "
                        f"level {adv_level} ({advanced.code})",
                        "COMPETENCY_LEVEL",
                    ))

    graph = nx.DiGraph()
    graph.add_nodes_from(n.id for n in nodes)
    codes = {n.id: n.code for n in nodes}
    accepted: list[Edge] = []
    cycles: list[dict] = []
    seen: set[tuple] = set()
    for edge in sorted(candidates, key=lambda e: (e.method != "EXPLICIT_MARKER", e.requirement_code, e.depends_on_code)):
        pair = (edge.requirement_id, edge.depends_on_id)
        if pair in seen:
            continue
        seen.add(pair)
        # The edge reads requirement -> depends_on. It closes a cycle when the
        # prerequisite already (transitively) depends on the requirement.
        if nx.has_path(graph, edge.depends_on_id, edge.requirement_id):
            path = nx.shortest_path(graph, edge.depends_on_id, edge.requirement_id)
            cycles.append({
                "rejected_edge": f"{edge.requirement_code} -> {edge.depends_on_code}",
                "cycle": [codes[p] for p in path] + [codes[edge.depends_on_id]],
                "reason": edge.reason,
            })
            continue
        graph.add_edge(edge.requirement_id, edge.depends_on_id)
        accepted.append(edge)
    return accepted, cycles
