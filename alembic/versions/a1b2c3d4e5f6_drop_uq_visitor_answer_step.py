"""drop uq_visitor_answer_step

Revision ID: a1b2c3d4e5f6
Revises: 11fba6c3d5c4
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "11fba6c3d5c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_visitor_answer_step",
        "visitor_answers",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_visitor_answer_step",
        "visitor_answers",
        ["visitor_id", "step_key"],
    )
