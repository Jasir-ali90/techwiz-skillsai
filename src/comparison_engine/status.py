"""Verification statuses (SRS section 1.2 and Step 47).

Items carry one of nine detailed statuses; the plan-level status is derived
from them and from the metrics. The Verified rule is one function with its
three conditions spelled out, because it is the most-tested rule in the SRS.
"""
from dataclasses import dataclass

PLAN_VERIFIED = "VERIFIED"
PLAN_VERIFIED_WITH_WARNING = "VERIFIED_WITH_WARNING"
PLAN_INCOMPLETE = "INCOMPLETE"
PLAN_UNSUPPORTED = "UNSUPPORTED"
PLAN_CONTRADICTORY = "CONTRADICTORY"
PLAN_MANUAL_REVIEW = "MANUAL_REVIEW_REQUIRED"
PLAN_STATUSES = [PLAN_VERIFIED, PLAN_VERIFIED_WITH_WARNING, PLAN_INCOMPLETE, PLAN_UNSUPPORTED,
                 PLAN_CONTRADICTORY, PLAN_MANUAL_REVIEW]


@dataclass
class VerificationInputs:
    coverage_percent: float
    invalid_or_outdated_references: int
    unresolved_contradictions: int
    unsupported_requirements: int
    open_errors: int = 0
    open_warnings: int = 0


def can_mark_verified(v: VerificationInputs) -> tuple[bool, list[str]]:
    """A plan may be Verified only when all three hold:
    1. mandatory coverage is 100 percent,
    2. every source reference is valid and current,
    3. no unresolved contradictions and no unsupported requirements remain.
    """
    reasons = []
    condition_1 = v.coverage_percent >= 100.0
    condition_2 = v.invalid_or_outdated_references == 0
    condition_3 = v.unresolved_contradictions == 0 and v.unsupported_requirements == 0
    if not condition_1:
        reasons.append(f"Mandatory coverage is {v.coverage_percent}%, not 100%")
    if not condition_2:
        reasons.append(f"{v.invalid_or_outdated_references} source reference(s) are invalid or outdated")
    if v.unresolved_contradictions:
        reasons.append(f"{v.unresolved_contradictions} unresolved contradiction(s)")
    if v.unsupported_requirements:
        reasons.append(f"{v.unsupported_requirements} unsupported requirement(s) or claim(s)")
    return condition_1 and condition_2 and condition_3, reasons


def derive_plan_status(v: VerificationInputs) -> tuple[str, list[str]]:
    verified, reasons = can_mark_verified(v)
    if verified:
        if v.open_errors:
            return PLAN_MANUAL_REVIEW, [f"{v.open_errors} other error finding(s) need review"]
        if v.open_warnings:
            return PLAN_VERIFIED_WITH_WARNING, [f"{v.open_warnings} warning(s)"]
        return PLAN_VERIFIED, []
    if v.unresolved_contradictions:
        return PLAN_CONTRADICTORY, reasons
    if v.unsupported_requirements or v.invalid_or_outdated_references:
        return PLAN_UNSUPPORTED, reasons
    if v.coverage_percent < 100.0:
        return PLAN_INCOMPLETE, reasons
    return PLAN_MANUAL_REVIEW, reasons
