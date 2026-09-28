"""Pipeline 2 rules against controlled plans: Python validation, coverage,
traceability, quiz answers, learning sequence, hallucination, duplicates,
role relevance, business rules and the Verified function."""
import copy

import pytest

from src.comparison_engine.status import VerificationInputs, can_mark_verified, derive_plan_status
from src.python_validation import engine
from tests.factories import DOC, OLD_DOC, context, findings, good_plan, quiz, task


def run(plan, embedder, **kw):
    return engine.run(context(plan, embedder, **kw))


# ------------------------------------------------------------ baseline / Python validation
def test_clean_plan_has_no_errors(embedder):
    report = run(good_plan(), embedder)
    errors = findings(report, severity="ERROR")
    assert errors == [], [e["message"] for e in errors]
    assert report["metrics"]["mandatory_requirement_coverage_score"] == 100.0
    assert report["metrics"]["source_traceability_score"] == 100.0
    assert report["metrics"]["requirement_consistency_score"] == 100.0


def test_report_carries_all_six_srs_metrics(embedder):
    metrics = run(good_plan(), embedder)["metrics"]
    assert set(metrics) == {"mandatory_requirement_coverage_score", "source_traceability_score",
                            "requirement_consistency_score", "missing_requirement_count",
                            "unsupported_requirement_count", "contradiction_count"}


# ------------------------------------------------------------ JSON / schema validation
def test_schema_detects_missing_field_invalid_type_and_bad_ids(embedder):
    plan = good_plan()
    t = plan["modules"][0]["tasks"][0]
    t["description"] = ""
    t["priority"] = "URGENT"
    t["source_document_id"] = "not-a-uuid"
    plan["modules"][1]["tasks"][0]["mandatory"] = None
    plan["modules"][1]["estimated_duration_minutes"] = "thirty"
    plan["raw_response"]["role_code"] = "ASTRONAUT"
    messages = [f["message"] for f in findings(run(plan, embedder), "schema")]
    assert any("missing 'description'" in m for m in messages)
    assert any("priority 'URGENT'" in m for m in messages)
    assert any("not a valid id" in m for m in messages)
    assert any("no mandatory status" in m for m in messages)
    assert any("estimated_duration_minutes has type str" in m for m in messages)
    assert any("Unknown role 'ASTRONAUT'" in m for m in messages)


def test_schema_detects_duplicate_ids_and_unknown_requirement(embedder):
    plan = good_plan()
    duplicate = copy.deepcopy(plan["modules"][0]["tasks"][0])
    duplicate["requirement_code"] = "R777"
    plan["modules"][0]["tasks"].append(duplicate)
    messages = [f["message"] for f in findings(run(plan, embedder), "schema")]
    assert any("Duplicate id" in m for m in messages)
    assert any("R777" in m and "does not exist" in m for m in messages)


def test_schema_rejects_unconfigured_quiz_type_and_answer_not_in_options(embedder):
    plan = good_plan()
    q = plan["modules"][0]["quiz"][0]
    q["question_type"] = "ESSAY"
    q["correct_answer"] = ["ten calendar days"]
    messages = [f["message"] for f in findings(run(plan, embedder), "schema")]
    assert any("Quiz type 'ESSAY' is not configured" in m for m in messages)
    assert any("not one of the options" in m for m in messages)


# ------------------------------------------------------------ coverage
def test_srs_worked_example_two_of_three_is_67_percent_and_incomplete(embedder):
    plan = good_plan()
    plan["modules"] = plan["modules"][:2]           # drop the only module covering R003
    report = run(plan, embedder)
    assert report["metrics"]["mandatory_requirement_coverage_score"] == pytest.approx(66.67, abs=0.01)
    assert report["metrics"]["missing_requirement_count"] == 1
    missing = findings(report, "coverage")
    assert missing[0]["requirement_code"] == "R003"
    assert missing[0]["item_status"] == "REQUIREMENT_MISSING"
    summary = report["rule_summaries"]["coverage"]
    assert summary["status"] == "INCOMPLETE"
    assert summary["missing_requirements"][0]["code"] == "R003"


def test_content_outside_the_matrix_is_unsupported(embedder):
    plan = good_plan()
    plan["modules"][0]["tasks"][0]["requirement_code"] = "R099"
    report = run(plan, embedder)
    unsupported = [f for f in findings(report, "coverage") if f["item_status"] == "UNSUPPORTED_REQUIREMENT"]
    assert unsupported and unsupported[0]["requirement_code"] == "R099"


# ------------------------------------------------------------ traceability
def test_citing_an_obsolete_version_fails_traceability(embedder):
    plan = good_plan()
    t = plan["modules"][0]["tasks"][0]
    t["source_document_id"] = OLD_DOC
    report = run(plan, embedder)
    trace = findings(report, "traceability")
    assert trace and trace[0]["item_status"] == "OUTDATED_SOURCE"
    assert "OBSOLETE" in trace[0]["message"]
    assert report["metrics"]["source_traceability_score"] < 100
    assert report["extra_metrics"]["mandatory_traceability_score"] < 100


def test_unknown_section_and_chunk_are_reported(embedder):
    plan = good_plan()
    plan["modules"][1]["tasks"][0]["source_section_id"] = "9.9"
    plan["modules"][1]["tasks"][0]["source_chunk_code"] = "POL#C999"
    problems = findings(run(plan, embedder), "traceability")[0]["evidence"]["problems"]
    assert any("section 9.9 does not exist" in p for p in problems)
    assert any("POL#C999 does not resolve" in p for p in problems)


# ------------------------------------------------------------ quiz answers
def test_quiz_answer_contradicting_its_section_is_flagged(embedder):
    plan = good_plan()
    q = plan["modules"][0]["quiz"][0]
    q["correct_answer"] = ["seven calendar days"]        # the section says three
    flagged = findings(run(plan, embedder), "quiz_answers", "ERROR")
    assert flagged and "contradicts the cited section" in flagged[0]["message"]


def test_true_false_statement_contradicting_its_section_is_flagged(embedder):
    plan = good_plan()
    plan["modules"][2]["quiz"].append(quiz(
        "R001", "POL#C001", "True or false: Employees must complete the Information Security Basics module within "
        "fourteen calendar days of their joining date.", ["True", "False"], ["True"], qtype="TRUE_FALSE"))
    flagged = findings(run(plan, embedder), "quiz_answers", "ERROR")
    assert any("contradicts its cited section" in f["message"] for f in flagged)


def test_distractor_that_is_actually_true_is_flagged(embedder):
    plan = good_plan()
    q = plan["modules"][0]["quiz"][0]
    q["options"] = ["three calendar days", "72 hours", "fourteen calendar days"]
    q["correct_answer"] = ["fourteen calendar days"]
    messages = [f["message"] for f in findings(run(plan, embedder), "quiz_answers")]
    assert messages, "a wrong answer and a true distractor must be flagged"


# ------------------------------------------------------------ learning sequence
def test_task_before_its_prerequisite_is_flagged_with_both_codes(embedder):
    plan = good_plan()
    report = run(plan, embedder, prerequisites=[("R003", "R002", "R003 relies on R002")])
    assert not findings(report, "learning_sequence", "ERROR")
    plan["modules"][1]["tasks"][0]["due_stage"] = "DAY_30"   # R002 now after R003 (WEEK_1)
    flagged = findings(run(plan, embedder, prerequisites=[("R003", "R002", "R003 relies on R002")]),
                       "learning_sequence", "ERROR")
    assert flagged
    assert "R003" in flagged[0]["message"] and "R002" in flagged[0]["message"]
    assert flagged[0]["evidence"]["prerequisite"] == "R002"


def test_assessment_before_its_learning_content_is_flagged(embedder):
    plan = good_plan()
    plan["modules"][0]["tasks"][0]["due_stage"] = "WEEK_2"
    flagged = findings(run(plan, embedder), "learning_sequence", "ERROR")
    assert any("before the learning content" in f["message"] for f in flagged)


def test_advanced_task_before_basic_training_is_flagged(embedder):
    plan = good_plan()
    module = plan["modules"][0]
    module["tasks"][0]["due_stage"] = "WEEK_1"
    module["tasks"].append(task("R001", "POL#C001", "Run an advanced security drill.", stage="DAY_1",
                                difficulty="ADVANCED"))
    flagged = findings(run(plan, embedder), "learning_sequence", "ERROR")
    assert any("Advanced task scheduled before the basic training" in f["message"] for f in flagged)


# ------------------------------------------------------------ hallucination
def test_fabricated_company_rule_is_flagged_but_instructional_wording_is_not(embedder):
    plan = good_plan()
    plan["modules"][1]["tasks"][0]["expected_outcome"] = (
        "Employees must submit a signed expense reimbursement form to payroll within two days of travel.")
    plan["modules"][1]["learning_activities"] = ["Review the module and take notes.",
                                                 "Discuss anything unclear with your manager."]
    report = run(plan, embedder)
    flags = findings(report, "hallucination", "ERROR")
    assert len(flags) == 1
    assert "expense reimbursement" in flags[0]["evidence"]["claim"]
    assert flags[0]["evidence"]["category"] == "UNSUPPORTED_FACTUAL_CLAIM"
    assert report["rule_summaries"]["hallucination"]["instructional"] >= 2


def test_source_supported_claims_pass(embedder):
    report = run(good_plan(), embedder)
    summary = report["rule_summaries"]["hallucination"]
    assert summary["unsupported_rule_claim"] == 0
    assert summary["source_supported"] > 0


# ------------------------------------------------------------ contradictions (plan level)
def test_generated_task_violating_a_rule_is_a_contradiction(embedder):
    plan = good_plan()
    plan["modules"][0]["tasks"][0]["description"] = (
        "Complete the Information Security Basics module within fourteen calendar days of joining.")
    report = run(plan, embedder)
    flagged = findings(report, "contradictions", "ERROR")
    assert flagged and flagged[0]["evidence"]["category"] == "ITEM_VIOLATES_RULE"
    assert report["extra_metrics"]["unresolved_contradictions"] >= 1


def test_item_permitting_a_prohibited_action_is_a_contradiction(embedder):
    plan = good_plan()
    plan["modules"][2]["tasks"].append(task("R003", "POL#C003", "Committing API keys to a repository is fine "
                                                                "for test services.", stage="WEEK_1"))
    flagged = findings(run(plan, embedder), "contradictions", "ERROR")
    assert any("permits what R003 prohibits" in f["message"] for f in flagged)


def _corpus_conflict(winner_cited: bool) -> dict:
    policy = {"chunk_code": "POL#C001", "document_id": DOC, "document_code": "POL", "document_type": "INFOSEC_POLICY",
              "version": 2, "status": "ACTIVE", "precedence_rank": 20, "section_id": "2.3", "content": "three days"}
    faq = {"chunk_code": "FAQ#C003", "document_id": "faq", "document_code": "FAQ", "document_type": "FAQ",
           "version": 1, "status": "ACTIVE", "precedence_rank": 60, "section_id": "2.1", "content": "two weeks"}
    return {"kind": "FAQ_VS_POLICY", "category": "NUMERIC", "similarity": 0.7, "detail": "FAQ says two weeks",
            "a": faq, "b": policy, "winner": {"chunk_code": "POL#C001", "document_code": "POL", "version": 2,
                                              "precedence_rank": 20}, "resolution": "POL outranks FAQ",
            "evidence": {}}


def test_resolved_source_conflict_is_reported_with_winner(embedder):
    report = run(good_plan(), embedder, contradictions=[_corpus_conflict(True)])
    flagged = findings(report, "contradictions")
    assert flagged[0]["severity"] == "INFO"          # configurable: rules.contradictions.resolved_severity
    assert flagged[0]["evidence"]["resolved"] is True
    assert flagged[0]["evidence"]["contradiction"]["winner"]["document_code"] == "POL"
    assert report["metrics"]["contradiction_count"] == 1


def test_plan_following_the_losing_source_is_unresolved(embedder):
    plan = good_plan()
    t = plan["modules"][0]["tasks"][0]
    t["source_document_id"], t["source_chunk_code"] = "faq", "FAQ#C003"
    report = run(plan, embedder, contradictions=[_corpus_conflict(False)],
                 extra_documents={"faq": {"id": "faq", "document_code": "FAQ", "version": 1, "status": "ACTIVE",
                                          "document_type": "FAQ", "precedence_rank": 60}})
    flagged = [f for f in findings(report, "contradictions") if f["item_type"] == "source"]
    assert flagged[0]["severity"] == "ERROR" and flagged[0]["item_status"] == "CONTRADICTION_DETECTED"


# ------------------------------------------------------------ duplicates, relevance, completeness
def test_duplicate_tasks_are_reported_as_a_pair_with_score(embedder):
    plan = good_plan()
    plan["modules"][1]["tasks"].append(copy.deepcopy(plan["modules"][1]["tasks"][0]) | {"id": "dup-task"})
    flagged = findings(run(plan, embedder), "duplicates")
    assert flagged
    evidence = flagged[0]["evidence"]
    assert {"first", "second", "score"} <= set(evidence) and evidence["score"] >= 0.95


def test_content_for_another_role_is_irrelevant_and_names_that_role(embedder):
    plan = good_plan()
    plan["modules"][0]["tasks"][0]["requirement_code"] = "R099"
    flagged = findings(run(plan, embedder), "role_relevance")
    assert flagged and flagged[0]["evidence"]["maps_to_roles"] == ["QA Engineer"]


def test_content_mapping_to_no_requirement_at_all_is_reported(embedder):
    plan = good_plan()
    plan["modules"][1]["tasks"][0]["requirement_code"] = "R555"
    flagged = findings(run(plan, embedder), "role_relevance")
    assert flagged and flagged[0]["evidence"]["maps_to_roles"] == []
    assert "no requirement in any role's Matrix" in flagged[0]["message"]


def test_relevant_plan_has_no_role_relevance_findings(embedder):
    assert findings(run(good_plan(), embedder), "role_relevance") == []


def test_missing_assessment_and_competency_are_reported(embedder):
    plan = good_plan()
    plan["modules"][1]["assessments"] = []
    plan["modules"][1]["competency"] = plan["modules"][1]["category"] = "Something else"
    plan["modules"][1]["key_concepts"] = []
    report = run(plan, embedder)
    assert any("R002 requires assessment" in f["message"] for f in findings(report, "assessment_coverage"))
    assert any("Account Security" in f["message"] for f in findings(report, "competency_coverage"))


# ------------------------------------------------------------ business rules
def test_item_due_after_its_deadline_breaks_a_business_rule(embedder):
    plan = good_plan()
    plan["modules"][0]["tasks"][0]["due_stage"] = "WEEK_2"     # deadline is 3 days
    flagged = findings(run(plan, embedder), "business_rules", "ERROR")
    assert any("due_within_deadline" in f["message"] for f in flagged)


def test_new_business_rule_from_config_applies_without_code_change(embedder):
    rules = [{"name": "no_friday_deploys", "type": "forbidden_pattern", "pattern": r"friday", "severity": "ERROR",
              "message": "No Friday deployments"}]
    plan = good_plan()
    plan["modules"][1]["tasks"][0]["description"] = "Deploy the key rotation on Friday evening."
    flagged = findings(run(plan, embedder, business_rules=rules), "business_rules")
    assert flagged and "no_friday_deploys" in flagged[0]["message"]


# ------------------------------------------------------------ rule toggles
def test_disabling_a_rule_removes_its_findings(embedder):
    plan = good_plan()
    plan["modules"][1]["tasks"].append(copy.deepcopy(plan["modules"][1]["tasks"][0]) | {"id": "dup-task"})
    assert findings(run(plan, embedder), "duplicates")
    from src.core.app_config import load_yaml

    config = load_yaml("validation_rules")
    config["rules"]["duplicates"]["enabled"] = False
    report = run(plan, embedder, config=config)
    assert not findings(report, "duplicates")
    assert "duplicates" in report["disabled_rules"]


# ------------------------------------------------------------ the Verified rule
@pytest.mark.parametrize("inputs, verified", [
    (VerificationInputs(100.0, 0, 0, 0), True),
    (VerificationInputs(66.67, 0, 0, 0), False),
    (VerificationInputs(100.0, 1, 0, 0), False),
    (VerificationInputs(100.0, 0, 1, 0), False),
    (VerificationInputs(100.0, 0, 0, 1), False),
])
def test_can_mark_verified_needs_all_three_conditions(inputs, verified):
    assert can_mark_verified(inputs)[0] is verified


def test_plan_status_derivation():
    assert derive_plan_status(VerificationInputs(66.67, 0, 0, 0))[0] == "INCOMPLETE"
    assert derive_plan_status(VerificationInputs(100.0, 0, 2, 0))[0] == "CONTRADICTORY"
    assert derive_plan_status(VerificationInputs(100.0, 3, 0, 0))[0] == "UNSUPPORTED"
    assert derive_plan_status(VerificationInputs(100.0, 0, 0, 0, open_warnings=2))[0] == "VERIFIED_WITH_WARNING"
    assert derive_plan_status(VerificationInputs(100.0, 0, 0, 0, open_errors=1))[0] == "MANUAL_REVIEW_REQUIRED"
    assert derive_plan_status(VerificationInputs(100.0, 0, 0, 0))[0] == "VERIFIED"
