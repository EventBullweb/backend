"""split ticket number and lottery code

Revision ID: 7ff97d43439f
Revises: 9fd94634e3e9
Create Date: 2026-03-07 14:13:30.572201

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ff97d43439f'
down_revision: Union[str, Sequence[str], None] = '9fd94634e3e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Сохраняем существующие данные билетов через rename колонки.
    op.alter_column(
        "tickets",
        "ticket_code",
        existing_type=sa.String(length=64),
        new_column_name="ticket_number",
        existing_nullable=False,
    )
    op.alter_column(
        "tickets",
        "ticket_number",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.add_column('tickets', sa.Column('lottery_code', sa.String(length=64), nullable=True))
    op.drop_index(op.f('ix_tickets_ticket_code'), table_name='tickets')
    op.create_index(op.f('ix_tickets_lottery_code'), 'tickets', ['lottery_code'], unique=True)
    op.create_index(op.f('ix_tickets_ticket_number'), 'tickets', ['ticket_number'], unique=True)

    # Для уже активированных билетов генерируем лотерейный код детерминированно.
    op.execute(
        """
        UPDATE tickets
        SET lottery_code = LPAD(
            (((('x' || SUBSTRING(MD5(ticket_number), 1, 12))::bit(48)::bigint % 900000) + 100000)::text),
            6,
            '0'
        ) || '_' || UPPER(SUBSTRING(MD5(ticket_number), 13, 5))
        WHERE is_activated = true AND lottery_code IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tickets_ticket_number'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_lottery_code'), table_name='tickets')
    op.alter_column(
        "tickets",
        "ticket_number",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "tickets",
        "ticket_number",
        existing_type=sa.String(length=64),
        new_column_name="ticket_code",
        existing_nullable=False,
    )
    op.create_index(op.f('ix_tickets_ticket_code'), 'tickets', ['ticket_code'], unique=True)
    op.drop_column('tickets', 'lottery_code')
