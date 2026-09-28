"""Runs the enabled rules and computes the six SRS metrics."""
import hashlib
import json
import time

from src.python_validation import rules_consistency, rules_content, rules_structure  # noqa: F401  (registers rules)
from src.python_validation.base import REGISTRY, SEVERITIES, ValidationContext


def rule_set_version(config: dict, business_rules: list[dict]) -> str:
    digest = hashlib.sha256(json.dumps([config, business_rules], sort_keys=True, default=str).encode()).hexdigest()
    return f"v{config.get('version', 1)}-{digest[:10]}"


def requirement_consistency(ctx: ValidationContext) -> float:
    """Share of items whose mandatory flag and priority match the Matrix row
    for the requirement they cite."""
    matrix = ctx.matrix_by_code
    comparable = [i for i in ctx.items if i.get("requirement_code") in matrix]
    if not comparable:
        return 0.0
    consistent = sum(
        1 for i in comparable
        if bool(i.get("mandatory")) == matrix[i["requirement_code"]]["is_mandatory"]
        and i.get("priority") == matrix[i["requirement_code"]]["priority"]
    )
    return round(100 * consistent / len(comparable), 2)


def run(ctx: ValidationContext) -> dict:
    started = time.perf_counter()
    rule_config = ctx.config.get("rules", {}) or {}
    findings, summaries, metrics = [], {}, {}
    enabled, disabled = [], []
    for name, cls in REGISTRY.items():
        settings = rule_config.get(name, {}) or {}
        if settings.get("enabled", True) is False:
            disabled.append(name)
            continue
        enabled.append(name)
        t = time.perf_counter()
        output = cls().run(ctx, settings)
        findings.extend(output.findings)
        summaries[name] = {**output.summary, "findings": len(output.findings),
                           "duration_ms": int((time.perf_counter() - t) * 1000)}
        metrics.update(output.metrics)

    unsupported = metrics.get("unsupported_requirement_codes", 0) + metrics.get("unsupported_claim_count", 0)
    six = {
        "mandatory_requirement_coverage_score": metrics.get("mandatory_coverage_score"),
        "source_traceability_score": metrics.get("source_traceability_score"),
        "requirement_consistency_score": requirement_consistency(ctx),
        "missing_requirement_count": metrics.get("missing_requirement_count"),
        "unsupported_requirement_count": unsupported,
        "contradiction_count": metrics.get("contradiction_count"),
    }
    extra = {
        "mandatory_traceability_score": metrics.get("mandatory_traceability_score"),
        "unresolved_contradictions": metrics.get("unresolved_contradictions"),
        "unsupported_requirement_codes": metrics.get("unsupported_requirement_codes"),
        "unsupported_claims": metrics.get("unsupported_claim_count"),
    }
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
    return {
        "metrics": six,
        "extra_metrics": extra,
        "findings": [f.as_dict() for f in findings],
        "rule_summaries": summaries,
        "enabled_rules": enabled,
        "disabled_rules": disabled,
        "counts_by_severity": counts,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }


def available_rules() -> list[dict]:
    return [{"name": name, "description": cls.description} for name, cls in REGISTRY.items()]
