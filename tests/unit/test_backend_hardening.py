"""Regression tests for the backend hardening pass: weak secrets, upload paths,
reviewer edit types, database-outage detection and PDF escaping."""
import uuid

import pytest
from pydantic import ValidationError

from src.core.config import Settings
from src.core.exceptions import ValidationFailedError
from src.main import _database_down
from src.models.plan import Assessment, QuizQuestion
from src.reports.export import render
from src.services.document_service import DOCUMENT_CODE
from src.services.review_service import _checked_edit


@pytest.mark.parametrize("key", ["change-me", "short-key", ""])
def test_weak_or_placeholder_secret_key_is_refused(key):
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(database_url="postgresql+asyncpg://x/y", secret_key=key, _env_file=None)


def test_strong_secret_key_is_accepted():
    assert Settings(database_url="postgresql+asyncpg://x/y", secret_key="k" * 48, _env_file=None).secret_key


@pytest.mark.parametrize("code", ["POL-HR-003", "SOP_DEPLOY_7", "FAQ-ENG-002"])
def test_normal_document_codes_are_allowed(code):
    assert DOCUMENT_CODE.match(code)


@pytest.mark.parametrize("code", ["../../src/x", "C:/Temp/evil", "a/b", "..", "POL.HR", "", "x" * 61])
def test_document_codes_that_could_escape_the_upload_folder_are_refused(code):
    assert not DOCUMENT_CODE.match(code)


def test_reviewer_edits_keep_each_field_type():
    quiz = QuizQuestion(question="q", options=["A", "B"], correct_answer=["A"], source_document_id=uuid.uuid4())
    assessment = Assessment(title="t", passing_score=70)
    assert _checked_edit(quiz, "correct_answer", ["B"]) == ["B"]
    assert _checked_edit(assessment, "passing_score", 80) == 80
    for item, field, value in [(quiz, "correct_answer", "B"), (assessment, "passing_score", "abc"),
                               (assessment, "passing_score", True), (quiz, "source_document_id", "nope")]:
        with pytest.raises(ValidationFailedError):
            _checked_edit(item, field, value)


def test_database_outage_is_recognised_through_wrapped_errors():
    try:
        try:
            raise ConnectionRefusedError("connection refused")
        except ConnectionRefusedError as inner:
            raise RuntimeError("query failed") from inner
    except RuntimeError as outer:
        assert _database_down(outer)
    assert not _database_down(ValueError("bad input"))


def test_pdf_export_survives_text_full_of_markup_characters():
    rows = [{"text": "A & B < C > D " * 40, "n": 1}]
    pdf = render(rows, "pdf", "Test report", {"note": "x & y <z>"})
    assert pdf[:4] == b"%PDF"
