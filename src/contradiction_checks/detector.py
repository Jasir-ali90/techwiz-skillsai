"""Contradiction detection (SRS Step 33, FR xxxvi) and precedence resolution.

Deterministic: numeric comparison of obligations, polarity (prohibits versus
permits), and version comparison. Similarity between chunks comes from the
stored local embeddings, which are numeric vectors and not a generative model.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np

from src.core.textutil import numeric_facts, phrase_regex, split_sentences, tokens

KIND_LABELS = {
    frozenset({"FAQ"}): "FAQ_VS_POLICY",
    frozenset({"ROLE_DESCRIPTION", "DEPARTMENT_SOP"}): "ROLE_DESCRIPTION_VS_SOP",
}
POLICY_TYPES = {"INFOSEC_POLICY", "DATA_PRIVACY_POLICY", "CONDUCT_POLICY", "HR_POLICY",
                "LEAVE_POLICY", "COMPLIANCE_INSTRUCTION"}


@dataclass
class ChunkFact:
    chunk_code: str
    document_id: str
    document_code: str
    document_type: str
    version: int
    status: str
    precedence_rank: int
    effective_date: date | None
    section_id: str | None
    content: str
    vector: Any = None


@dataclass
class Contradiction:
    kind: str
    category: str                    # NUMERIC, POLARITY, VERSION
    a: ChunkFact
    b: ChunkFact
    winner: ChunkFact
    loser: ChunkFact
    similarity: float
    detail: str
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        def side(c: ChunkFact) -> dict:
            return {"chunk_code": c.chunk_code, "document_id": c.document_id, "document_code": c.document_code,
                    "document_type": c.document_type, "version": c.version, "status": c.status,
                    "precedence_rank": c.precedence_rank, "section_id": c.section_id,
                    "content": c.content[:400]}
        return {
            "kind": self.kind, "category": self.category, "similarity": round(self.similarity, 3),
            "detail": self.detail, "a": side(self.a), "b": side(self.b),
            "winner": {"chunk_code": self.winner.chunk_code, "document_code": self.winner.document_code,
                       "version": self.winner.version, "precedence_rank": self.winner.precedence_rank},
            "resolution": resolution_reason(self.winner, self.loser),
            "evidence": self.evidence,
        }


def resolve(a: ChunkFact, b: ChunkFact) -> tuple[ChunkFact, ChunkFact]:
    """Newer active version beats an obsolete one; otherwise lower precedence
    rank wins and a tie breaks on the later effective date."""
    if a.document_code == b.document_code and a.version != b.version:
        return (a, b) if a.version > b.version else (b, a)
    key = lambda c: (c.precedence_rank, -(c.effective_date.toordinal() if c.effective_date else 0))
    return (a, b) if key(a) <= key(b) else (b, a)


def resolution_reason(winner: ChunkFact, loser: ChunkFact) -> str:
    if winner.document_code == loser.document_code:
        return (f"{winner.document_code} v{winner.version} supersedes v{loser.version}; "
                "the newer version is authoritative.")
    if winner.precedence_rank != loser.precedence_rank:
        return (f"{winner.document_code} ({winner.document_type}, rank {winner.precedence_rank}) outranks "
                f"{loser.document_code} ({loser.document_type}, rank {loser.precedence_rank}).")
    return f"Equal rank {winner.precedence_rank}; {winner.document_code} has the later effective date."


def kind_of(a: ChunkFact, b: ChunkFact) -> str:
    if a.document_code == b.document_code:
        return "OLD_VS_NEW_VERSION"
    types = {a.document_type, b.document_type}
    if "FAQ" in types and types & (POLICY_TYPES | {"DEPARTMENT_SOP"}):
        return "FAQ_VS_POLICY"
    if types == {"ROLE_DESCRIPTION", "DEPARTMENT_SOP"}:
        return "ROLE_DESCRIPTION_VS_SOP"
    return "CROSS_DOCUMENT"


def numeric_conflict(text_a: str, text_b: str) -> dict | None:
    """Same obligation, different number: durations compared in hours,
    counts and percentages compared by unit."""
    fa, fb = numeric_facts(text_a), numeric_facts(text_b)
    for kind in ("duration", "count", "percent"):
        va = [f for f in fa if f["kind"] == kind]
        vb = [f for f in fb if f["kind"] == kind]
        if not va or not vb:
            continue
        unit = lambda f: f["unit"].rstrip("s")  # "reviewers" and "reviewer" are one unit
        measure = (lambda f: round(f["hours"], 3)) if kind == "duration" else (lambda f: (unit(f), f["value"]))
        if kind == "count":
            units = {unit(f) for f in va} & {unit(f) for f in vb}
            if not units:
                continue
            va = [f for f in va if unit(f) in units]
            vb = [f for f in vb if unit(f) in units]
        if not ({measure(f) for f in va} & {measure(f) for f in vb}):
            return {"kind": kind, "a": [f["text"] for f in va], "b": [f["text"] for f in vb]}
    return None


class PolarityChecker:
    def __init__(self, permissive: list[str], prohibitive: list[str]):
        self.permissive = phrase_regex(permissive)
        self.prohibitive = phrase_regex(prohibitive)

    def polarity(self, text: str) -> str | None:
        """A prohibition wins over a permission word in the same sentence, so
        "may not" reads as prohibiting."""
        if self.prohibitive and self.prohibitive.search(text):
            return "PROHIBITS"
        if self.permissive and self.permissive.search(text):
            return "PERMITS"
        return None


GENERIC_TERMS = {
    "employee", "employees", "staff", "every", "all", "new", "joiner", "joiners", "company", "nexora", "labs",
    "complete", "completed", "completion", "within", "calendar", "working", "business", "day", "days", "hour",
    "hours", "minute", "minutes", "week", "weeks", "month", "months", "joining", "date", "first", "least",
    "before", "after", "end", "their", "your", "required", "requires", "must", "shall", "should", "may",
    "submit", "record", "report", "ensure", "confirm", "attend", "full", "period", "time",
    "module", "training", "policy", "procedure", "section", "document", "team", "manager", "lead",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "fourteen", "fifteen",
    "twenty", "thirty", "sixty", "ninety", "twelve", "twenty-four", "yes", "fine", "usually",
}


SEVERITY = re.compile(r"\b(severity|sev|priority|p)\s*([0-9])\b", re.IGNORECASE)


def _singular(token: str) -> str:
    return token[:-1] if len(token) > 4 and token.endswith("s") and not token.endswith("ss") else token


def obligation_terms(sentence: str, generic: set[str], subjects: re.Pattern | None = None) -> set[str]:
    """The distinctive words of an obligation: its object, with the subject
    (a role title), generic obligation vocabulary and numbers removed.
    "Severity 1" stays one term, because severity levels are different duties."""
    text = SEVERITY.sub(lambda m: f" {m.group(1).lower()}{m.group(2)} ", sentence)
    if subjects is not None:
        text = subjects.sub(" ", text)
    return {_singular(t) for t in tokens(text) if t not in generic and not t.isdigit() and len(t) > 2}


def same_obligation(a: str, b: str, generic: set[str], min_overlap: float, min_shared: int,
                    subjects: re.Pattern | None = None, min_jaccard: float = 0.0) -> set[str] | None:
    """Two sentences state the same obligation when they share its object:
    most of the distinctive terms of the shorter one appear in the other."""
    ta, tb = obligation_terms(a, generic, subjects), obligation_terms(b, generic, subjects)
    if not ta or not tb:
        return None
    shared = ta & tb
    if len(shared) < min_shared or len(shared) / min(len(ta), len(tb)) < min_overlap:
        return None
    if len(shared) / len(ta | tb) < min_jaccard:
        return None
    return shared


def _sentences(text: str, ignore: re.Pattern | None = None) -> list[str]:
    return [s for s in split_sentences(text) if len(s.split()) >= 4 and not (ignore and ignore.search(s))]


def detect_corpus(
    chunks: list[ChunkFact],
    polarity: PolarityChecker,
    pair_similarity: float = 0.55,
    polarity_similarity: float = 0.45,
    min_overlap: float = 0.6,
    min_shared: int = 2,
    generic_terms: set[str] | None = None,
    subject_phrases: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
    numeric_min_jaccard: float = 0.5,
) -> list[Contradiction]:
    """Every contradiction among the given chunks (active and obsolete)."""
    found: list[Contradiction] = []
    if not chunks:
        return found

    # Old versus new: same document code, same section, different wording.
    by_section: dict[tuple, list[ChunkFact]] = {}
    for c in chunks:
        if c.section_id:
            by_section.setdefault((c.document_code, c.section_id), []).append(c)
    for group in by_section.values():
        versions = sorted(group, key=lambda c: c.version)
        for older, newer in zip(versions, versions[1:]):
            if older.version != newer.version and _norm(older.content) != _norm(newer.content):
                numeric = numeric_conflict(older.content, newer.content)
                detail = (f"{older.document_code} §{older.section_id} changed between v{older.version} "
                          f"and v{newer.version}")
                if numeric:
                    detail += f": {', '.join(numeric['a'])} became {', '.join(numeric['b'])}"
                found.append(Contradiction("OLD_VS_NEW_VERSION", "VERSION", older, newer, newer, older, 1.0,
                                           detail, {"numeric": numeric}))

    # Across documents: compare obligation sentences, not whole chunks. Two
    # sentences conflict only when they concern the same obligation (they share
    # its distinctive terms) and differ in number or in permission.
    generic = GENERIC_TERMS | set(generic_terms or [])
    subjects = phrase_regex([re.escape(p.lower()) + "s?" for p in subject_phrases or []])
    ignore = re.compile("|".join(ignore_patterns), re.IGNORECASE) if ignore_patterns else None
    live = [c for c in chunks if c.vector is not None and c.section_id and c.status != "OBSOLETE"]
    if len(live) < 2:
        return found
    matrix = np.array([c.vector for c in live], dtype=np.float32)
    sims = matrix @ matrix.T
    sentences = [_sentences(c.content, ignore) for c in live]
    seen: set[tuple] = set()
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            a, b = live[i], live[j]
            if a.document_code == b.document_code:
                continue  # versions are handled above
            sim = float(sims[i, j])
            if sim < min(pair_similarity, polarity_similarity):
                continue
            conflict = _sentence_conflict(sentences[i], sentences[j], sim, polarity, pair_similarity,
                                          polarity_similarity, generic, min_overlap, min_shared, subjects,
                                          numeric_min_jaccard)
            if conflict is None:
                continue
            category, sa, sb, evidence = conflict
            key = (a.chunk_code, a.document_code, b.chunk_code, b.document_code)
            if key in seen:
                continue
            seen.add(key)
            winner, loser = resolve(a, b)
            if category == "NUMERIC":
                detail = (f"{a.document_code} §{a.section_id} says {', '.join(evidence['numeric']['a'])}; "
                          f"{b.document_code} §{b.section_id} says {', '.join(evidence['numeric']['b'])}")
            else:
                pa, pb = evidence["polarity"]["a"], evidence["polarity"]["b"]
                detail = (f"{a.document_code} §{a.section_id} {pa.lower()} what "
                          f"{b.document_code} §{b.section_id} {pb.lower()}")
            evidence.update({"sentence_a": sa, "sentence_b": sb})
            found.append(Contradiction(kind_of(a, b), category, a, b, winner, loser, sim, detail, evidence))
    return found


def _sentence_conflict(sents_a, sents_b, sim, polarity, pair_similarity, polarity_similarity,
                       generic, min_overlap, min_shared, subjects, numeric_min_jaccard):
    for sa in sents_a:
        for sb in sents_b:
            if sim >= pair_similarity:
                numeric = numeric_conflict(sa, sb)
                shared = numeric and same_obligation(sa, sb, generic, min_overlap, min_shared, subjects,
                                                     numeric_min_jaccard)
                if shared:
                    return "NUMERIC", sa, sb, {"numeric": numeric, "shared_terms": sorted(shared)}
            if sim >= polarity_similarity:
                pa, pb = polarity.polarity(sa), polarity.polarity(sb)
                if pa and pb and pa != pb:
                    shared = same_obligation(sa, sb, generic, min(min_overlap, 0.5), min_shared, subjects)
                    if shared:
                        return "POLARITY", sa, sb, {"polarity": {"a": pa, "b": pb}, "shared_terms": sorted(shared)}
    return None


def _norm(text: str) -> str:
    return " ".join(text.lower().split())
