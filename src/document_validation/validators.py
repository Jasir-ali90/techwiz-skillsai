import hashlib
from dataclasses import dataclass, field
from datetime import date

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MIN_FILE_BYTES = 64

PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"


@dataclass
class ValidationReport:
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, passed: bool, message: str) -> None:
        self.checks.append({"check": name, "passed": passed, "message": message})

    @property
    def failures(self) -> list[dict]:
        return [c for c in self.checks if not c["passed"]]

    @property
    def ok(self) -> bool:
        return not self.failures


def compute_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def check_file_type(filename: str, content: bytes, report: ValidationReport) -> str:
    """SRS Step 5: file type. Checks the extension and the real magic bytes,
    so a renamed .exe cannot pass as a .pdf."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        report.add("file_type", False, f"'{ext or 'none'}' is not a PDF or DOCX file")
        return ext

    header = content[:4] if ext == ".docx" else content[:5]
    expected = DOCX_MAGIC if ext == ".docx" else PDF_MAGIC
    if not header.startswith(expected):
        report.add(
            "file_type", False,
            f"The file is named {ext} but its contents are not a valid {ext[1:].upper()}",
        )
    else:
        report.add("file_type", True, f"Valid {ext[1:].upper()} file")
    return ext


def check_file_size(content: bytes, max_mb: int, report: ValidationReport) -> None:
    size = len(content)
    if size > max_mb * 1024 * 1024:
        report.add("file_size", False, f"File is {size / 1048576:.1f} MB, limit is {max_mb} MB")
    else:
        report.add("file_size", True, f"{size / 1024:.1f} KB")


def check_not_empty(content: bytes, report: ValidationReport) -> None:
    if len(content) < MIN_FILE_BYTES:
        report.add("empty_document", False, "The file is empty or too small to contain content")
    else:
        report.add("empty_document", True, "File contains data")


def check_dates(
    effective_date: date, expiry_date: date | None, report: ValidationReport
) -> None:
    if expiry_date and expiry_date <= effective_date:
        report.add("dates", False, "The expiry date must fall after the effective date")
    elif expiry_date and expiry_date < date.today():
        report.add("dates", True, "Accepted, but this document has already expired")
    else:
        report.add("dates", True, "Effective and expiry dates are consistent")


def check_version(version: int, latest_version: int | None, report: ValidationReport) -> None:
    if version < 1:
        report.add("version", False, "Version must be 1 or higher")
    elif latest_version is not None and version <= latest_version:
        report.add(
            "version", False,
            f"Version {version} is not newer than the stored version {latest_version}",
        )
    else:
        report.add("version", True, f"Version {version} accepted")