"""WBS: CSI cost-code library + per-line manual ETC override

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

Adds the cost_codes reference table (seeded from
app/data/csi_masterformat_2022.csv via scripts/load_cost_codes.py or the demo
seed) and budget_lines.manual_etc for PM-entered cost-to-complete.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("division", sa.String(length=2), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cost_codes_code"), "cost_codes", ["code"], unique=True)
    op.create_index(op.f("ix_cost_codes_division"), "cost_codes", ["division"], unique=False)
    op.add_column("budget_lines", sa.Column("manual_etc", sa.Numeric(precision=16, scale=2),
                                            nullable=True))


def downgrade() -> None:
    op.drop_column("budget_lines", "manual_etc")
    op.drop_index(op.f("ix_cost_codes_division"), table_name="cost_codes")
    op.drop_index(op.f("ix_cost_codes_code"), table_name="cost_codes")
    op.drop_table("cost_codes")
