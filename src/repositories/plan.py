import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.plan import (
    Assessment,
    AssessmentRubricCriterion,
    ChecklistItem,
    GenerationRun,
    OnboardingPlan,
    PlanModule,
    PlanTask,
    PromptTemplate,
    QuizQuestion,
)
from src.models.organization import Employee
from src.repositories.base import BaseRepository

REF_FIELDS = ("requirement_code", "source_document_id", "source_section_id",
              "source_chunk_code", "mandatory", "priority", "due_stage")
ITEM_MODELS = {
    "module": PlanModule,
    "checklist_item": ChecklistItem,
    "task": PlanTask,
    "quiz_question": QuizQuestion,
    "assessment": Assessment,
}


def _ref(data: dict) -> dict:
    return {k: data.get(k) for k in REF_FIELDS}


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    model = PromptTemplate

    async def find(self, name: str, version: str) -> PromptTemplate | None:
        return await self.get_by(name=name, version=version)

    async def all(self) -> list[PromptTemplate]:
        rows = await self.session.scalars(select(PromptTemplate).order_by(PromptTemplate.name, PromptTemplate.version))
        return list(rows)


class GenerationRunRepository(BaseRepository[GenerationRun]):
    model = GenerationRun

    async def for_plan(self, plan_id: uuid.UUID) -> list[GenerationRun]:
        rows = await self.session.scalars(
            select(GenerationRun).where(GenerationRun.plan_id == plan_id).order_by(GenerationRun.started_at)
        )
        return list(rows)


class PlanRepository(BaseRepository[OnboardingPlan]):
    model = OnboardingPlan

    async def full(self, plan_id: uuid.UUID) -> OnboardingPlan | None:
        stmt = (
            select(OnboardingPlan)
            .where(OnboardingPlan.id == plan_id)
            .options(
                selectinload(OnboardingPlan.modules).selectinload(PlanModule.checklist),
                selectinload(OnboardingPlan.modules).selectinload(PlanModule.tasks),
                selectinload(OnboardingPlan.modules).selectinload(PlanModule.quiz),
                selectinload(OnboardingPlan.modules)
                .selectinload(PlanModule.assessments)
                .selectinload(Assessment.rubric),
            )
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def filtered(self, employee_id=None, job_role_id=None, status=None,
                       verification_status=None, current_only: bool = False) -> list[OnboardingPlan]:
        stmt = select(OnboardingPlan).order_by(OnboardingPlan.generated_at.desc())
        if employee_id:
            stmt = stmt.where(OnboardingPlan.employee_id == employee_id)
        if job_role_id:
            stmt = stmt.where(OnboardingPlan.job_role_id == job_role_id)
        if status:
            stmt = stmt.where(OnboardingPlan.status == status)
        if verification_status:
            stmt = stmt.where(OnboardingPlan.verification_status == verification_status)
        if current_only:
            stmt = stmt.where(OnboardingPlan.is_current.is_(True))
        return list(await self.session.scalars(stmt))

    async def current_for_employee(self, employee_id: uuid.UUID) -> OnboardingPlan | None:
        return await self.session.scalar(
            select(OnboardingPlan)
            .where(OnboardingPlan.employee_id == employee_id, OnboardingPlan.is_current.is_(True))
            .order_by(OnboardingPlan.generated_at.desc())
            .limit(1)
        )

    async def retire_current(self, employee_id: uuid.UUID) -> None:
        # Lock the employee row first so two generations for the same person run
        # one after the other instead of both ending up "current"; the partial
        # unique index uq_onboarding_plans_one_current backs this up.
        await self.session.execute(select(Employee.id).where(Employee.id == employee_id).with_for_update())
        await self.session.execute(
            update(OnboardingPlan)
            .where(OnboardingPlan.employee_id == employee_id, OnboardingPlan.is_current.is_(True))
            .values(is_current=False, status="SUPERSEDED")
        )

    def add_module(self, plan: OnboardingPlan, data: dict, sequence: int) -> PlanModule:
        module = PlanModule(
            plan_id=plan.id, sequence=sequence,
            title=data["title"], category=data.get("category"), competency=data.get("competency"),
            purpose=data.get("purpose"), learning_objectives=data.get("learning_objectives", []),
            key_concepts=data.get("key_concepts", []),
            required_source_documents=data.get("required_source_documents", []),
            estimated_duration_minutes=data.get("estimated_duration_minutes"),
            learning_activities=data.get("learning_activities", []),
            assessment_summary=data.get("assessment_summary"),
            completion_criteria=data.get("completion_criteria"),
            requirement_codes=data.get("requirement_codes", []),
            scenarios=data.get("scenarios", []),
            **_ref(data),
        )
        self.session.add(module)
        for position, item in enumerate(data.get("checklist", [])):
            module.checklist.append(ChecklistItem(
                plan_id=plan.id, position=position, activity=item["activity"], is_required=item.get("is_required", True),
                responsible_person=item.get("responsible_person"), **_ref(item),
            ))
        for position, item in enumerate(data.get("tasks", [])):
            module.tasks.append(PlanTask(
                plan_id=plan.id, position=position, description=item["description"],
                expected_outcome=item.get("expected_outcome"),
                completion_criteria=item.get("completion_criteria"),
                difficulty=item.get("difficulty"), **_ref(item),
            ))
        for position, item in enumerate(data.get("quiz", [])):
            module.quiz.append(QuizQuestion(
                plan_id=plan.id, position=position, question_type=item["question_type"], question=item["question"],
                options=item.get("options", []), correct_answer=item.get("correct_answer", []),
                explanation=item.get("explanation"), difficulty=item.get("difficulty"), **_ref(item),
            ))
        if data.get("assessment"):
            item = data["assessment"]
            assessment = Assessment(
                plan_id=plan.id, title=item["title"], assessment_type=item["assessment_type"],
                topic=item.get("topic"), passing_score=item.get("passing_score", 70.0), **_ref(item),
            )
            for position, criterion in enumerate(item.get("rubric", [])):
                assessment.rubric.append(AssessmentRubricCriterion(
                    position=position, criterion=criterion["criterion"], weight=criterion["weight"],
                    expected_performance=criterion["expected_performance"],
                    pass_condition=criterion["pass_condition"],
                    requirement_code=criterion.get("requirement_code"),
                ))
            module.assessments.append(assessment)
        return module

    async def item(self, item_type: str, item_id: uuid.UUID):
        model = ITEM_MODELS.get(item_type)
        if model is None:
            return None
        return await self.session.get(model, item_id)

    async def modules_by_ids(self, ids: Sequence[uuid.UUID]) -> list[PlanModule]:
        if not ids:
            return []
        return list(await self.session.scalars(select(PlanModule).where(PlanModule.id.in_(ids))))

    async def items_citing(self, requirement_codes: Sequence[str], document_ids: Sequence[str]) -> dict[str, list]:
        """Every generated item that cites one of the requirements or documents."""
        found: dict[str, list] = {}
        for name, model in ITEM_MODELS.items():
            conditions = []
            if requirement_codes:
                conditions.append(model.requirement_code.in_(requirement_codes))
            if document_ids:
                conditions.append(model.source_document_id.in_(document_ids))
            if not conditions:
                continue
            from sqlalchemy import or_

            rows = await self.session.scalars(select(model).where(or_(*conditions)))
            found[name] = list(rows)
        return found
