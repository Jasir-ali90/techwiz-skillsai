"""Section-level change detection between two document versions (SRS Step 57)."""
import difflib
import re
from dataclasses import dataclass

from src.core.textutil import SECTION_PREFIX, numeric_facts

WORD = re.compile(r"\S+")


@dataclass
class SectionText:
    key: str
    section_id: str | None
    heading: str | None
    chunk_codes: list[str]
    content: str


def group_sections(chunks: list[dict]) -> dict[str, SectionText]:
    """chunks: dicts with section_id, heading, chunk_code, content, sequence."""
    grouped: dict[str, SectionText] = {}
    for c in sorted(chunks, key=lambda c: c["sequence"]):
        key = c["section_id"] or f"heading:{(c.get('heading') or c['chunk_code']).strip().lower()}"
        text = SECTION_PREFIX.sub("", c["content"].strip())
        if key in grouped:
            grouped[key].chunk_codes.append(c["chunk_code"])
            grouped[key].content += " " + text
        else:
            grouped[key] = SectionText(key, c["section_id"], c.get("heading"), [c["chunk_code"]], text)
    return grouped


def _norm(text: str) -> str:
    return " ".join(text.split())


def word_changes(old: str, new: str) -> list[dict]:
    a, b = WORD.findall(old), WORD.findall(new)
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    changes = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        changes.append({
            "operation": op,
            "from": " ".join(a[i1:i2]) or None,
            "to": " ".join(b[j1:j2]) or None,
            "context": " ".join(a[max(0, i1 - 6):i1]),
        })
    return changes


def numeric_changes(old: str, new: str) -> list[dict]:
    fo, fn = numeric_facts(old), numeric_facts(new)
    old_set = {(f["kind"], f["text"].lower()) for f in fo}
    new_set = {(f["kind"], f["text"].lower()) for f in fn}
    removed = sorted(t for t in old_set - new_set)
    added = sorted(t for t in new_set - old_set)
    if not removed and not added:
        return []
    return [{"kind": "numeric", "removed": [t for _, t in removed], "added": [t for _, t in added]}]


def summarise(change: list[dict], numeric: list[dict]) -> str:
    parts = []
    for n in numeric:
        if n["removed"] and n["added"]:
            parts.append(f"{', '.join(n['removed'])} → {', '.join(n['added'])}")
    for c in change:
        if c["operation"] == "replace" and c["from"] and c["to"] and len(parts) < 4:
            parts.append(f"'{c['from']}' → '{c['to']}'")
        elif c["operation"] == "insert" and len(parts) < 4:
            parts.append(f"added '{c['to']}'")
        elif c["operation"] == "delete" and len(parts) < 4:
            parts.append(f"removed '{c['from']}'")
    return "; ".join(dict.fromkeys(parts))


def diff_versions(old_chunks: list[dict], new_chunks: list[dict]) -> dict:
    old, new = group_sections(old_chunks), group_sections(new_chunks)
    added, removed, modified, unchanged = [], [], [], []
    for key, section in new.items():
        if key not in old:
            added.append({"key": key, "section_id": section.section_id, "heading": section.heading,
                          "chunk_codes": section.chunk_codes, "content": section.content[:600]})
        elif _norm(old[key].content) != _norm(section.content):
            changes = word_changes(old[key].content, section.content)
            numeric = numeric_changes(old[key].content, section.content)
            modified.append({
                "key": key, "section_id": section.section_id, "heading": section.heading,
                "old_chunk_codes": old[key].chunk_codes, "new_chunk_codes": section.chunk_codes,
                "old_text": old[key].content[:600], "new_text": section.content[:600],
                "summary": summarise(changes, numeric), "numeric_changes": numeric, "word_changes": changes[:20],
            })
        else:
            unchanged.append({"key": key, "section_id": section.section_id,
                              "old_chunk_codes": old[key].chunk_codes, "new_chunk_codes": section.chunk_codes})
    for key, section in old.items():
        if key not in new:
            removed.append({"key": key, "section_id": section.section_id, "heading": section.heading,
                            "chunk_codes": section.chunk_codes, "content": section.content[:600]})
    return {
        "added": added, "removed": removed, "modified": modified, "unchanged": unchanged,
        "counts": {"added": len(added), "removed": len(removed), "modified": len(modified),
                   "unchanged": len(unchanged)},
    }
