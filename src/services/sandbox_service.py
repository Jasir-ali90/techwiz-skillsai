"""Technical Role Sandbox & Automated Assessment Verifier.

Provides hands-on coding and practical scenario assessments for Nexora Labs roles
with deterministic automated evaluation and grading.
"""
import ast
import re
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

# Curated challenges mapped to roles and real enterprise tasks
CHALLENGES = {
    "BACKEND_DEV": [
        {
            "id": "chal-be-001",
            "title": "Secure Session & Token Expiry Validator",
            "role": "BACKEND_DEV",
            "language": "python",
            "difficulty": "INTERMEDIATE",
            "summary": "Implement a token validator adhering to POL-INFOSEC-001 (Section 2.3: 15-minute inactivity session timeout).",
            "instructions": (
                "Write a function `validate_session(token_payload: dict, current_time: int) -> bool` that:\n"
                "1. Checks if 'iat' (issued at) and 'last_activity' keys are present.\n"
                "2. Returns False if `current_time - token_payload['last_activity'] > 900` (15 minutes in seconds).\n"
                "3. Returns True otherwise.\n"
                "4. Handles missing or negative timestamps gracefully by returning False."
            ),
            "starter_code": (
                "def validate_session(token_payload: dict, current_time: int) -> bool:\n"
                "    # TODO: Implement 15-minute inactivity timeout according to POL-INFOSEC-001 §2.3\n"
                "    pass\n"
            ),
            "solution_criteria": ["checks_keys", "handles_inactivity", "safe_exception_handling"],
        },
        {
            "id": "chal-be-002",
            "title": "SQL Injection & Input Sanitizer",
            "role": "BACKEND_DEV",
            "language": "python",
            "difficulty": "BEGINNER",
            "summary": "Implement safe parameterized filter builder to prevent SQL injection in internal database queries.",
            "instructions": (
                "Write a function `sanitize_search_query(user_query: str) -> str` that:\n"
                "1. Strips dangerous SQL keywords like `DROP`, `DELETE`, `--`, `;` (case-insensitive).\n"
                "2. Trims leading and trailing whitespace.\n"
                "3. Returns an empty string if query contains malicious characters."
            ),
            "starter_code": (
                "def sanitize_search_query(user_query: str) -> str:\n"
                "    # TODO: Sanitize query against SQL injection attacks\n"
                "    return user_query\n"
            ),
            "solution_criteria": ["strips_keywords", "handles_empty"],
        },
    ],
    "DEVOPS_ENG": [
        {
            "id": "chal-devops-001",
            "title": "Hardened Multi-Stage Dockerfile Audit",
            "role": "DEVOPS_ENG",
            "language": "dockerfile",
            "difficulty": "INTERMEDIATE",
            "summary": "Write a secure, production-grade Dockerfile complying with Nexora Labs Deployment SOP.",
            "instructions": (
                "Define a multi-stage Dockerfile containing:\n"
                "1. Multi-stage build (`AS builder` and final stage).\n"
                "2. Minimal base image (`python:3.12-slim` or `alpine`).\n"
                "3. Non-root user declaration (`USER appuser` or `USER nonroot`).\n"
                "4. `EXPOSE` port declaration and clean `CMD` instruction."
            ),
            "starter_code": (
                "# Stage 1: Build\n"
                "FROM python:3.12-slim AS builder\n"
                "WORKDIR /app\n"
                "# TODO: Install dependencies\n\n"
                "# Stage 2: Runtime\n"
                "FROM python:3.12-slim\n"
                "WORKDIR /app\n"
                "# TODO: Create non-root user and set entrypoint\n"
            ),
            "solution_criteria": ["has_multistage", "non_root_user", "slim_image"],
        }
    ],
    "QA_ENG": [
        {
            "id": "chal-qa-001",
            "title": "API Authentication Status Code Test Suite",
            "role": "QA_ENG",
            "language": "python",
            "difficulty": "BEGINNER",
            "summary": "Write automated test assertions verifying 401 Unauthorized for expired or missing Bearer tokens.",
            "instructions": (
                "Write a function `test_auth_guard(response_status: int, response_json: dict) -> bool` that:\n"
                "1. Asserts status code is 401 or 403.\n"
                "2. Asserts response JSON contains an 'error' or 'detail' key.\n"
                "3. Returns True if tests pass, False if assertion fails."
            ),
            "starter_code": (
                "def test_auth_guard(response_status: int, response_json: dict) -> bool:\n"
                "    # TODO: Verify standard unauthorized API response format\n"
                "    pass\n"
            ),
            "solution_criteria": ["checks_status_401", "checks_error_body"],
        }
    ],
    "DATA_ANALYST": [
        {
            "id": "chal-data-001",
            "title": "Onboarding Completion Rate Aggregator",
            "role": "DATA_ANALYST",
            "language": "python",
            "difficulty": "BEGINNER",
            "summary": "Calculate department-level onboarding completion percentages from raw employee event records.",
            "instructions": (
                "Write a function `calculate_department_completion(records: list[dict]) -> dict[str, float]` where:\n"
                "Each record has `{'department': 'ENG', 'completed': True/False}`.\n"
                "Returns a dictionary mapping department to completion percentage rounded to 2 decimals."
            ),
            "starter_code": (
                "def calculate_department_completion(records: list[dict]) -> dict[str, float]:\n"
                "    # TODO: Calculate percent completed per department\n"
                "    return {}\n"
            ),
            "solution_criteria": ["aggregates_by_dept", "calculates_percent"],
        }
    ],
}

# Generic fallback challenges for other roles (Frontend, Intern, PM, SEO, Support, UIUX)
GENERIC_CHALLENGE = {
    "id": "chal-general-001",
    "title": "Company Policy Compliance Checklist Verifier",
    "role": "GENERAL",
    "language": "python",
    "difficulty": "BEGINNER",
    "summary": "Verify mandatory compliance acknowledgment for newly onboarded staff.",
    "instructions": (
        "Write a function `verify_compliance(checklist: dict) -> bool` that checks if 'INFOSEC', 'CONDUCT', "
        "and 'PRIVACY' are all marked True. Return True only if all three mandatory policies are acknowledged."
    ),
    "starter_code": (
        "def verify_compliance(checklist: dict) -> bool:\n"
        "    # Check all mandatory policy acknowledgments\n"
        "    return False\n"
    ),
    "solution_criteria": ["checks_all_mandatory"],
}


class SandboxService:
    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    def get_challenges_for_role(self, role_code: str | None) -> list[dict[str, Any]]:
        code = (role_code or "").upper().strip()
        if code in CHALLENGES:
            return CHALLENGES[code]
        # Match by prefix or return tailored general challenge
        for k, v in CHALLENGES.items():
            if k in code or code in k:
                return v
        return [{**GENERIC_CHALLENGE, "role": role_code or "GENERAL"}]

    def evaluate(self, challenge_id: str, submitted_code: str) -> dict[str, Any]:
        code = (submitted_code or "").strip()
        if not code:
            return {
                "passed": False,
                "score": 0,
                "feedback": "No code submitted. Please write your solution before running tests.",
                "test_results": [],
            }

        # 1. AST Syntax validation
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {
                "passed": False,
                "score": 0,
                "feedback": f"Syntax Error on line {e.lineno}: {e.msg}",
                "test_results": [{"test": "Syntax Validation", "passed": False, "error": str(e)}],
            }

        test_results = []
        score = 0

        # Security AST Scan: Disallow external imports and execution primitives
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return {
                    "passed": False,
                    "score": 0,
                    "feedback": "Security policy violation: External module imports are disallowed in the assessment sandbox.",
                    "test_results": [{"test": "Security AST Scan", "passed": False, "error": "Disallowed module import"}],
                }
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec", "open", "__import__"):
                return {
                    "passed": False,
                    "score": 0,
                    "feedback": f"Security policy violation: Use of `{node.func.id}` is prohibited in the assessment sandbox.",
                    "test_results": [{"test": "Security AST Scan", "passed": False, "error": f"Function `{node.func.id}` prohibited"}],
                }

        # Safe in-memory execution environment with clean builtins
        env: dict[str, Any] = {}
        safe_builtins = {
            "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
            "int": int, "float": float, "len": len, "list": list, "max": max,
            "min": min, "range": range, "round": round, "set": set, "str": str,
            "sum": sum, "tuple": tuple, "isinstance": isinstance, "Exception": Exception,
        }

        try:
            exec(compile(tree, filename="<sandbox>", mode="exec"), {"__builtins__": safe_builtins}, env)
        except Exception as e:
            return {
                "passed": False,
                "score": 10,
                "feedback": f"Execution error during code initialization: {e}",
                "test_results": [{"test": "Code Compilation", "passed": False, "error": str(e)}],
            }

        # Targeted test suites per challenge
        if challenge_id == "chal-be-001":
            func = env.get("validate_session")
            if not callable(func):
                return {"passed": False, "score": 15, "feedback": "Function `validate_session` was not defined.", "test_results": []}

            # Test 1: Valid active session (5 minutes ago)
            try:
                res1 = func({"iat": 1000, "last_activity": 1700}, 2000)
                t1 = bool(res1) is True
                test_results.append({"test": "Active session (300s inactive) returns True", "passed": t1})
            except Exception as e:
                test_results.append({"test": "Active session check", "passed": False, "error": str(e)})

            # Test 2: Expired session (> 15 minutes inactive = 901s)
            try:
                res2 = func({"iat": 1000, "last_activity": 1000}, 1901)
                t2 = bool(res2) is False
                test_results.append({"test": "Expired session (>900s inactive) returns False", "passed": t2})
            except Exception as e:
                test_results.append({"test": "Expired session check", "passed": False, "error": str(e)})

            # Test 3: Malformed payload handling
            try:
                res3 = func({}, 2000)
                t3 = bool(res3) is False
                test_results.append({"test": "Malformed payload returns False safely", "passed": t3})
            except Exception:
                test_results.append({"test": "Malformed payload check", "passed": False})

        elif challenge_id == "chal-be-002":
            func = env.get("sanitize_search_query")
            if not callable(func):
                return {"passed": False, "score": 15, "feedback": "Function `sanitize_search_query` was not defined.", "test_results": []}
            try:
                res1 = func("SELECT * FROM users; DROP TABLE users; --")
                t1 = "drop" not in res1.lower() and "--" not in res1
                test_results.append({"test": "Strips dangerous SQL keywords", "passed": t1})
            except Exception as e:
                test_results.append({"test": "Sanitizer test", "passed": False, "error": str(e)})

            try:
                res2 = func("  clean search term  ")
                t2 = res2.strip() == "clean search term"
                test_results.append({"test": "Preserves safe search terms and trims whitespace", "passed": t2})
            except Exception as e:
                test_results.append({"test": "Safe term test", "passed": False, "error": str(e)})

        elif challenge_id == "chal-qa-001":
            func = env.get("test_auth_guard")
            if not callable(func):
                return {"passed": False, "score": 15, "feedback": "Function `test_auth_guard` was not defined.", "test_results": []}
            try:
                t1 = bool(func(401, {"error": "unauthorized"})) is True
                test_results.append({"test": "Validates 401 with error JSON", "passed": t1})
                t2 = bool(func(200, {"status": "ok"})) is False
                test_results.append({"test": "Rejects 200 OK as unauthenticated test", "passed": t2})
            except Exception as e:
                test_results.append({"test": "QA Assertions", "passed": False, "error": str(e)})

        elif challenge_id == "chal-data-001":
            func = env.get("calculate_department_completion")
            if not callable(func):
                return {"passed": False, "score": 15, "feedback": "Function `calculate_department_completion` was not defined.", "test_results": []}
            sample = [
                {"department": "ENG", "completed": True},
                {"department": "ENG", "completed": False},
                {"department": "HR", "completed": True},
            ]
            try:
                res = func(sample)
                t1 = isinstance(res, dict) and res.get("ENG") == 50.0 and res.get("HR") == 100.0
                test_results.append({"test": "Calculates 50.0% ENG and 100.0% HR completion correctly", "passed": t1})
            except Exception as e:
                test_results.append({"test": "Data calculation test", "passed": False, "error": str(e)})

        elif challenge_id == "chal-devops-001":
            has_multi = "as builder" in code.lower()
            has_user = "user " in code.lower()
            has_slim = "slim" in code.lower() or "alpine" in code.lower()
            test_results.append({"test": "Multi-stage build pattern detected", "passed": has_multi})
            test_results.append({"test": "Non-root USER directive configured", "passed": has_user})
            test_results.append({"test": "Minimal base image (slim/alpine) utilized", "passed": has_slim})

        else:
            func = env.get("verify_compliance")
            if callable(func):
                try:
                    t1 = bool(func({"INFOSEC": True, "CONDUCT": True, "PRIVACY": True})) is True
                    t2 = bool(func({"INFOSEC": True, "CONDUCT": False, "PRIVACY": True})) is False
                    test_results.append({"test": "All True returns True", "passed": t1})
                    test_results.append({"test": "Missing policy returns False", "passed": t2})
                except Exception as e:
                    test_results.append({"test": "Compliance test", "passed": False, "error": str(e)})
            else:
                test_results.append({"test": "Code Structure & Execution", "passed": True})

        passed_count = sum(1 for t in test_results if t.get("passed"))
        total_tests = max(1, len(test_results))
        score = int((passed_count / total_tests) * 100)
        all_passed = passed_count == total_tests

        feedback = (
            "Outstanding work! All automated unit tests passed with 100% compliance."
            if all_passed
            else f"Passed {passed_count}/{total_tests} test cases. Review test feedback and refine your implementation."
        )

        return {
            "passed": all_passed,
            "score": score,
            "passed_tests": passed_count,
            "total_tests": total_tests,
            "feedback": feedback,
            "test_results": test_results,
        }
