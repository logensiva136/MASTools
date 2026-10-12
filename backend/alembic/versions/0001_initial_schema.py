"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


platform_enum = postgresql.ENUM("android", "ios", name="platform")
app_status_enum = postgresql.ENUM("uploaded", "analyzing", "analyzed", "failed", name="appstatus")
result_status_enum = postgresql.ENUM(
    "pending", "passed", "failed", "not_applicable", "manual_review", name="resultstatus"
)
result_method_enum = postgresql.ENUM("manual", "automated", name="resultmethod")
severity_enum = postgresql.ENUM("info", "low", "medium", "high", "critical", name="severity")
test_run_status_enum = postgresql.ENUM("created", "running", "completed", "failed", name="testrunstatus")


def upgrade() -> None:
    bind = op.get_bind()
    platform_enum.create(bind, checkfirst=True)
    app_status_enum.create(bind, checkfirst=True)
    result_status_enum.create(bind, checkfirst=True)
    result_method_enum.create(bind, checkfirst=True)
    severity_enum.create(bind, checkfirst=True)
    test_run_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "masvs_controls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mastg_tests", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("maswe_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("applies_to", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("automatable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("code", "version", name="uq_control_code_version"),
    )

    op.create_table(
        "apps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("package_name", sa.String(255), nullable=True),
        sa.Column("version_name", sa.String(100), nullable=True),
        sa.Column("status", app_status_enum, nullable=False, server_default="uploaded"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extracted_metadata", sa.JSON(), nullable=True),
    )

    op.create_table(
        "test_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_version", sa.String(50), nullable=False),
        sa.Column("status", test_run_status_enum, nullable=False, server_default="created"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tester_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "control_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("masvs_controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", result_status_enum, nullable=False, server_default="pending"),
        sa.Column("method", result_method_enum, nullable=False, server_default="manual"),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("test_run_id", "control_id", name="uq_result_run_control"),
    )

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("masvs_controls.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("severity", severity_enum, nullable=False, server_default="medium"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("findings")
    op.drop_table("control_results")
    op.drop_table("test_runs")
    op.drop_table("apps")
    op.drop_table("masvs_controls")
    op.drop_table("projects")

    bind = op.get_bind()
    test_run_status_enum.drop(bind, checkfirst=True)
    severity_enum.drop(bind, checkfirst=True)
    result_method_enum.drop(bind, checkfirst=True)
    result_status_enum.drop(bind, checkfirst=True)
    app_status_enum.drop(bind, checkfirst=True)
    platform_enum.drop(bind, checkfirst=True)
