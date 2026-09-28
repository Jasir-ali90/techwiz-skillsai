"""Writes the JSON Schemas under schemas/ from src/schemas/generation.py.

Run:  python -m scripts.export_schemas
"""
import json
from pathlib import Path

from src.schemas.generation import SCHEMA_FILES

OUT = Path(__file__).resolve().parents[1] / "schemas"


def render(model) -> str:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://skillsprint.ai/schemas/{model.__name__}"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for filename, model in SCHEMA_FILES.items():
        (OUT / filename).write_text(render(model), encoding="utf-8")
        print("wrote", OUT / filename)


if __name__ == "__main__":
    main()
