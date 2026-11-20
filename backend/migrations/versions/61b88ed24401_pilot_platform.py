"""Pilot outcomes, private footage, billing and resource reservations."""

import sqlalchemy as sa
from alembic import op

revision = "61b88ed24401"
down_revision = "42f07a8b91cd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "billing_accounts",
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("customer_id", sa.String(100), unique=True),
        sa.Column("subscription_id", sa.String(100), unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("period_end", sa.Double(), nullable=False),
        sa.Column("updated_event", sa.Integer(), nullable=False),
        sa.Column("checkout_key", sa.String(36)),
        sa.Column("checkout_session_id", sa.String(100)),
        sa.Column("checkout_url", sa.String(1000)),
        sa.Column("checkout_expires", sa.Double(), nullable=False),
    )
    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_table(
        "resource_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("resource_key", sa.String(100), unique=True, nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_resource_usage_organization_id", "resource_usage", ["organization_id"])
    op.create_table(
        "video_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("lease_until", sa.Double(), nullable=False),
    )
    op.create_index("ix_video_assets_project_id", "video_assets", ["project_id"])
    op.create_table(
        "pilot_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("observed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("project_id", "external_id"),
    )
    op.create_index("ix_pilot_observations_project_id", "pilot_observations", ["project_id"])


def downgrade():
    for name in [
        "pilot_observations",
        "video_assets",
        "resource_usage",
        "billing_events",
        "billing_accounts",
    ]:
        op.drop_table(name)
