import re

from src.document_processing.models import ParsedDocument, RawBlock

# "1." / "2.3" / "4.1.2" at the start of a line, optionally followed by a title.
SECTION_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(.*)$")
# A heading is a numbered line with a short title and no sentence punctuation.
HEADING_MAX_WORDS = 12

MAX_CHUNK_CHARS = 1400
MIN_CHUNK_CHARS = 120


def _looks_like_heading(section_id: str, remainder: str, block: RawBlock) -> bool:
    if block.is_heading:
        return True
    if not remainder:
        return True
    words = remainder.split()
    if len(words) > HEADING_MAX_WORDS:
        return False
    if remainder.endswith((".", ";", ":")) and len(words) > 6:
        return False
    # A heading rarely contains a verb phrase like "must" or "should".
    lowered = remainder.lower()
    if any(w in lowered for w in (" must ", " shall ", " should ", " may ", " is ", " are ")):
        return False
    return section_id.count(".") <= 1


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_document(parsed: ParsedDocument, document_code: str) -> list[dict]:
    """Groups blocks into section-aligned chunks.

    A chunk starts at a numbered clause and absorbs following unnumbered lines,
    so a clause split across two PDF lines stays whole. Headings are tracked as a
    breadcrumb so a chunk under 2.1.1 still knows it sits inside section 2.
    """
    chunks: list[dict] = []
    heading_stack: list[tuple[str, str]] = []

    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        text = " ".join(current["parts"]).strip()
        if len(text) >= MIN_CHUNK_CHARS or current["section_id"]:
            sequence = len(chunks) + 1
            chunks.append({
                "chunk_code": f"{document_code}#C{sequence:03d}",
                "sequence": sequence,
                "section_id": current["section_id"],
                "heading": current["heading"],
                "heading_path": current["heading_path"],
                "page_number": current["page_number"],
                "paragraph_index": current["paragraph_index"],
                "content": text,
                "char_count": len(text),
                "token_estimate": _estimate_tokens(text),
            })
        current = None

    def start(section_id: str | None, text: str, block: RawBlock) -> dict:
        # An unnumbered paragraph under a numbered heading (an FAQ answer under
        # "2.1 How long...?") belongs to that heading's section.
        if section_id is None and heading_stack and heading_stack[-1][0] != "0":
            section_id = heading_stack[-1][0]
        return {
            "section_id": section_id,
            "heading": heading_stack[-1][1] if heading_stack else None,
            "heading_path": " > ".join(h[1] for h in heading_stack) or None,
            "page_number": block.page_number,
            "paragraph_index": block.paragraph_index,
            "parts": [text],
        }

    for block in parsed.blocks:
        match = SECTION_RE.match(block.text)

        if match:
            section_id, remainder = match.group(1), match.group(2).strip()

            if _looks_like_heading(section_id, remainder, block):
                flush()
                depth = section_id.count(".")
                while heading_stack and heading_stack[-1][0].count(".") >= depth:
                    heading_stack.pop()
                heading_stack.append((section_id, remainder or section_id))
                continue

            flush()
            current = start(section_id, block.text, block)
            continue

        if block.is_heading:
            flush()
            heading_stack = [(("0"), block.text)]
            continue

        if current is None:
            current = start(None, block.text, block)
        else:
            joined = " ".join(current["parts"]) + " " + block.text
            if len(joined) > MAX_CHUNK_CHARS:
                flush()
                current = start(None, block.text, block)
            else:
                current["parts"].append(block.text)

    flush()
    return chunks