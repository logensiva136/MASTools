import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Platform(str, enum.Enum):
    android = "android"
    ios = "ios"


class AppStatus(str, enum.Enum):
    uploaded = "uploaded"
    analyzing = "analyzing"
    analyzed = "analyzed"
    failed = "failed"


class ResultStatus(str, enum.Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    not_applicable = "not_applicable"
    manual_review = "manual_review"


class ResultMethod(str, enum.Enum):
    manual = "manual"
    automated = "automated"


class Severity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TestRunStatus(str, enum.Enum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="owner")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="projects")
    apps: Mapped[list["App"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class App(Base):
    __tablename__ = "apps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    platform: Mapped[Platform] = mapped_column(Enum(Platform), nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[AppStatus] = mapped_column(Enum(AppStatus), default=AppStatus.uploaded)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    # Raw metadata extracted by static analysis (manifest contents, permissions, etc.)
    extracted_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="apps")
    test_runs: Mapped[list["TestRun"]] = relationship(back_populates="app", cascade="all, delete-orphan")


class MasvsControl(Base):
    """A single row of the MASVS/MASTG/MASWE catalog. Data, not code — seeded
    from data/catalog/*.yaml. Upserted on (code, version)."""

    __tablename__ = "masvs_controls"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_control_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. MASVS-STORAGE-1
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # STORAGE, CRYPTO, AUTH, ...
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mastg_tests: Mapped[list] = mapped_column(JSON, default=list)  # ["MASTG-TEST-0001", ...]
    maswe_ids: Mapped[list] = mapped_column(JSON, default=list)  # ["MASWE-0001", ...]
    applies_to: Mapped[list] = mapped_column(JSON, default=list)  # ["android", "ios"]
    automatable: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)

    results: Mapped[list["ControlResult"]] = relationship(back_populates="control")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    app_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("apps.id", ondelete="CASCADE"))
    catalog_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[TestRunStatus] = mapped_column(Enum(TestRunStatus), default=TestRunStatus.created)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tester_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    app: Mapped["App"] = relationship(back_populates="test_runs")
    results: Mapped[list["ControlResult"]] = relationship(back_populates="test_run", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="test_run", cascade="all, delete-orphan")


class ControlResult(Base):
    """The status of one MASVS control for one test run. Rows are created
    (status=pending) for every applicable control when a TestRun starts, then
    updated either by a tester (manual) or a Celery check (automated)."""

    __tablename__ = "control_results"
    __table_args__ = (UniqueConstraint("test_run_id", "control_id", name="uq_result_run_control"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"))
    control_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("masvs_controls.id", ondelete="CASCADE"))
    status: Mapped[ResultStatus] = mapped_column(Enum(ResultStatus), default=ResultStatus.pending)
    method: Mapped[ResultMethod] = mapped_column(Enum(ResultMethod), default=ResultMethod.manual)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    test_run: Mapped["TestRun"] = relationship(back_populates="results")
    control: Mapped["MasvsControl"] = relationship(back_populates="results")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    test_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"))
    control_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("masvs_controls.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.medium)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    test_run: Mapped["TestRun"] = relationship(back_populates="findings")
    control: Mapped["MasvsControl | None"] = relationship()
