"""Rule 3 of the brief: the validation layer imports nothing AI.

Pipeline 2 must stay independent of Pipeline 1. These directories may not
reference a generative AI SDK or the generation pipeline in any form, and they
may not import it transitively either.
"""
import ast
import subprocess
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARDED = ["src/python_validation", "src/comparison_engine", "src/contradiction_checks", "src/role_matrix"]
FORBIDDEN = re.compile(r"\b(anthropic|openai|google\.generativeai|genai_pipeline|llm)\b", re.IGNORECASE)
FORBIDDEN_MODULES = ("anthropic", "openai", "google.generativeai", "src.genai_pipeline")


def guarded_files():
    for folder in GUARDED:
        yield from sorted((ROOT / folder).rglob("*.py"))


@pytest.mark.parametrize("path", list(guarded_files()), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_forbidden_reference_in_source(path):
    text = path.read_text(encoding="utf-8")
    hits = [(n, line.strip()) for n, line in enumerate(text.splitlines(), 1) if FORBIDDEN.search(line)]
    assert not hits, f"{path.relative_to(ROOT)} references AI code: {hits}"


@pytest.mark.parametrize("path", list(guarded_files()), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_forbidden_import(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert not name.startswith(FORBIDDEN_MODULES), f"{path.name} imports {name}"


def test_guarded_packages_do_not_pull_in_ai_transitively():
    """Importing every guarded module, in a fresh interpreter, must not load an
    AI SDK or Pipeline 1."""
    modules = [".".join(p.relative_to(ROOT).with_suffix("").parts) for p in guarded_files()]
    script = (
        "import importlib, sys\n"
        f"for m in {modules!r}: importlib.import_module(m)\n"
        f"leaked = sorted(m for m in sys.modules if m.startswith({FORBIDDEN_MODULES!r}))\n"
        "print(','.join(leaked))\n"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    leaked = result.stdout.strip()
    assert not leaked, f"validation layer transitively imported {leaked}"


def test_guard_covers_every_guarded_directory():
    for folder in GUARDED:
        assert (ROOT / folder).is_dir(), folder
        assert list((ROOT / folder).glob("*.py")), f"{folder} has no Python files"
