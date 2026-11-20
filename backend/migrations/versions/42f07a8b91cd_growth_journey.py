"""Durable interview-to-publication journeys."""

import sqlalchemy as sa
from alembic import op

revision = "42f07a8b91cd"
down_revision = "19cf4c750044"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "growth_journeys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("lease_until", sa.Double(), nullable=False),
        sa.Column("next_check", sa.Double(), nullable=False),
        sa.Column("error_code", sa.String(100)),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_growth_journeys_project_id", "growth_journeys", ["project_id"])


def downgrade():
    op.drop_table("growth_journeys")
