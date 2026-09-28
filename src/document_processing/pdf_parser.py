import pdfplumber

from src.document_processing.models import ParsedDocument, RawBlock


def parse_pdf(path: str) -> ParsedDocument:
    """Extracts text page by page, keeping the page number for traceability.
    SRS Step 6: page reference is required for PDF sources."""
    parsed = ParsedDocument(parser="pdfplumber")

    with pdfplumber.open(path) as pdf:
        parsed.page_count = len(pdf.pages)
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                parsed.warnings.append(f"Page {page_index} contained no extractable text")
                continue
            for line in text.split("\n"):
                cleaned = line.strip()
                if cleaned:
                    parsed.blocks.append(RawBlock(text=cleaned, page_number=page_index))

    if not parsed.blocks:
        parsed.warnings.append(
            "No text could be extracted. The file may be a scan and would need OCR."
        )
    return parsed