"""At most one current plan per employee

Revision ID: a7c3e1f9b2d4
Revises: 5f09fedc19d7
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "a7c3e1f9b2d4"
down_revision = "5f09fedc19d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Two concurrent generations could each retire the old plan and insert a new
    # "current" one. The service now locks the employee row; this makes the
    # database refuse a second current plan outright.
    op.create_index(
        "uq_onboarding_plans_one_current", "onboarding_plans", ["employee_id"],
        unique=True, postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("uq_onboarding_plans_one_current", table_name="onboarding_plans")
