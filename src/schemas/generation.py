"""Output contract for Pipeline 1. Mirrored as JSON Schema under schemas/
(scripts/export_schemas.py writes them; a test keeps the two in sync).

Every generated item carries its source reference: requirement_code,
source_document_id, source_section_id, source_chunk_code, mandatory, priority
and due_stage. Pipeline 1 checks only the shape; Pipeline 2 checks whether the
references are true.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PriorityLiteral = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
DifficultyLiteral = Literal["BASIC", "INTERMEDIATE", "ADVANCED"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceReference(Strict):
    requirement_code: str = Field(description="Matrix requirement code, e.g. R012")
    source_document_id: str = Field(description="UUID of the cited document version")
    source_section_id: str | None = Field(description="Section id inside the document, e.g. 2.3")
    source_chunk_code: str = Field(description="Chunk code, e.g. POL-INFOSEC-001#C004")
    mandatory: bool
    priority: PriorityLiteral
    due_stage: str = Field(description="Onboarding stage code, e.g. WEEK_1")


class ChecklistItemOut(SourceReference):
    activity: str
    is_required: bool
    responsible_person: str = Field(description="Employee, Manager, Buddy, IT, HR ...")


class TaskOut(SourceReference):
    description: str
    expected_outcome: str
    completion_criteria: str
    difficulty: DifficultyLiteral


class ScenarioOut(SourceReference):
    title: str
    situation: str
    expected_action: str


class QuizQuestionOut(SourceReference):
    question_type: str = Field(description="One of the configured quiz types")
    question: str
    options: list[str]
    correct_answer: list[str] = Field(description="Option text(s) that are correct")
    explanation: str
    difficulty: DifficultyLiteral


class RubricCriterionOut(Strict):
    criterion: str
    weight: float = Field(ge=0, le=100)
    expected_performance: str
    pass_condition: str
    requirement_code: str | None = None


class AssessmentOut(SourceReference):
    title: str
    assessment_type: str = Field(description="PRACTICAL, WRITTEN, OBSERVATION or SIGN_OFF")
    topic: str
    passing_score: float = Field(ge=0, le=100)
    rubric: list[RubricCriterionOut]


class ModuleOut(SourceReference):
    title: str
    category: str = Field(description="Learning module category, usually the competency")
    competency: str
    purpose: str
    learning_objectives: list[str]
    key_concepts: list[str]
    required_source_documents: list[str] = Field(description="Document codes")
    estimated_duration_minutes: int = Field(ge=1)
    learning_activities: list[str]
    assessment_summary: str
    completion_criteria: str
    requirement_codes: list[str] = Field(description="Every requirement this module covers")
    checklist: list[ChecklistItemOut]
    tasks: list[TaskOut]
    scenarios: list[ScenarioOut]
    quiz: list[QuizQuestionOut]
    assessment: AssessmentOut | None


class GapOut(Strict):
    topic: str
    reason: str
    requirement_code: str | None = None


class GeneratedPlan(Strict):
    """The plan envelope."""
    employee_code: str
    role_code: str
    plan_title: str
    summary: str
    modules: list[ModuleOut]
    gaps: list[GapOut]


class GeneratedModules(Strict):
    """Envelope for selective regeneration of some modules only."""
    modules: list[ModuleOut]
    gaps: list[GapOut]


SCHEMA_FILES = {
    "plan.schema.json": GeneratedPlan,
    "module.schema.json": ModuleOut,
    "checklist_item.schema.json": ChecklistItemOut,
    "task.schema.json": TaskOut,
    "scenario.schema.json": ScenarioOut,
    "quiz_question.schema.json": QuizQuestionOut,
    "assessment.schema.json": AssessmentOut,
    "rubric.schema.json": RubricCriterionOut,
    "source_reference.schema.json": SourceReference,
    "module_regeneration.schema.json": GeneratedModules,
}
