"""Prompt template registry and rendering. Prompts live in versioned Jinja
files under prompt_templates/, never inline in code (SRS Step 40)."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "prompt_templates"
UNTRUSTED_CLOSE = "</untrusted_document_data>"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
)


@dataclass
class TemplateSpec:
    name: str
    version: str
    file: str
    purpose: str
    output_schema: str

    @property
    def path(self) -> Path:
        return TEMPLATE_DIR / self.file

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    @property
    def label(self) -> str:
        return f"{self.name}_{self.version}"


def manifest() -> list[TemplateSpec]:
    data = yaml.safe_load((TEMPLATE_DIR / "manifest.yaml").read_text(encoding="utf-8")) or {}
    return [TemplateSpec(**t) for t in data.get("templates", [])]


def find(name: str, version: str) -> TemplateSpec | None:
    return next((t for t in manifest() if t.name == name and t.version == version), None)


def sanitise_excerpt(text: str) -> str:
    """Document text can never close the untrusted-data block early."""
    return text.replace(UNTRUSTED_CLOSE, "</untrusted_document_data_>").replace("[/EXCERPT]", "[/EXCERPT_]")


def render(spec: TemplateSpec, context: dict) -> tuple[str, str]:
    """Returns (system, user)."""
    ctx = dict(context)
    ctx["chunks"] = [{**c, "content": sanitise_excerpt(c["content"])} for c in context.get("chunks", [])]
    schema_path = ROOT / spec.output_schema
    ctx["output_schema"] = schema_path.read_text(encoding="utf-8") if schema_path.exists() else "{}"
    text = _env.get_template(spec.file).render(**ctx)
    system, _, user = text.partition("=== USER ===")
    return system.replace("=== SYSTEM ===", "").strip(), user.strip()


def compact_json(value) -> str:
    return json.dumps(value, separators=(",", ":"))
