"""Adversarial pattern scanning at parse time (SRS Step 42).

Document text is data, never instruction. This scanner flags text that tries to
talk to the model, so flagged chunks can be excluded from every prompt.
"""
import re
from functools import lru_cache

from src.core.app_config import load_yaml


@lru_cache
def _compiled() -> list[tuple[str, re.Pattern, str]]:
    config = load_yaml("adversarial_patterns")
    return [
        (p["name"], re.compile(p["regex"], re.IGNORECASE | re.DOTALL), p.get("reason", ""))
        for p in config.get("patterns", [])
    ]


def scan_text(text: str) -> list[dict]:
    """Returns one finding per matched pattern, empty when the text is clean."""
    findings = []
    for name, pattern, reason in _compiled():
        match = pattern.search(text)
        if match:
            findings.append({"pattern": name, "reason": reason, "matched_text": match.group(0)[:200]})
    return findings
