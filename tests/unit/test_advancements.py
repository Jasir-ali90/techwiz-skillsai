import pytest
from src.services.copilot_service import CopilotService
from src.services.sandbox_service import SandboxService
from src.services.certificate_service import CertificateService


def test_sandbox_challenges_exist():
    service = SandboxService()
    challenges = service.get_challenges_for_role("BACKEND_DEV")
    assert len(challenges) >= 2
    assert any(c["id"] == "chal-be-001" for c in challenges)
    assert any(c["id"] == "chal-be-002" for c in challenges)


def test_sandbox_evaluation_passing():
    service = SandboxService()
    # Correct solution for chal-be-001: validate_session
    valid_code = """
def validate_session(token_payload: dict, current_time: int) -> bool:
    if not isinstance(token_payload, dict):
        return False
    if "iat" not in token_payload or "last_activity" not in token_payload:
        return False
    diff = current_time - token_payload["last_activity"]
    if diff < 0 or diff > 900:
        return False
    return True
"""
    result = service.evaluate("chal-be-001", valid_code)
    assert result["passed"] is True
    assert result["score"] == 100
    assert len(result["test_results"]) == 3
    assert all(t["passed"] for t in result["test_results"])


def test_sandbox_evaluation_failing():
    service = SandboxService()
    # Failing solution: always returns False
    failing_code = """
def validate_session(token_payload: dict, current_time: int) -> bool:
    return False
"""
    result = service.evaluate("chal-be-001", failing_code)
    assert result["passed"] is False
    assert result["score"] < 100


def test_sandbox_security_rejection():
    service = SandboxService()
    unsafe_code = """
import os
def validate_session(token_payload: dict, current_time: int) -> bool:
    os.system("echo unsafe")
    return True
"""
    result = service.evaluate("chal-be-001", unsafe_code)
    assert result["passed"] is False
    assert "External module imports are disallowed" in result["feedback"]


def test_certificate_signature_verification():
    service = CertificateService(session=None)
    payload_str = "EMP-001|Software Engineer|2026-10-22|dummy-id"
    sig = service._sign(payload_str)
    assert len(sig) == 64  # SHA256 hex digest length
    # Validating deterministic signature
    sig2 = service._sign(payload_str)
    assert sig == sig2
    # Changing payload alters signature
    sig_diff = service._sign("EMP-002|Software Engineer|2026-10-22|dummy-id")
    assert sig != sig_diff


def test_copilot_service_initialization():
    service = CopilotService(session=None)
    assert service is not None
