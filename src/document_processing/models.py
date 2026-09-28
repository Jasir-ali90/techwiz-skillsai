from dataclasses import dataclass, field


@dataclass
class RawBlock:
    """One paragraph or line pulled from a file, before chunking."""
    text: str
    page_number: int | None = None
    paragraph_index: int | None = None
    is_heading: bool = False
    style_name: str | None = None


@dataclass
class ParsedDocument:
    blocks: list[RawBlock] = field(default_factory=list)
    page_count: int = 0
    parser: str = ""
    warnings: list[str] = field(default_factory=list)