"""add users and project ownership

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # This project predates any deployed install (see data/catalog's own
    # history), so there's no pre-existing `projects` data to backfill
    # with an owner. If that stops being true before this migration ships,
    # add a data migration here first that assigns existing rows to some
    # admin user — don't just relax this to nullable.
    op.add_column(
        "projects",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_projects_owner_id_users", "projects", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_owner_id_users", "projects", type_="foreignkey")
    op.drop_column("projects", "owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
