import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import AppStatus, Platform, ResultMethod, ResultStatus, Severity, TestRunStatus


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class AppOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    platform: Platform
    package_name: str | None
    version_name: str | None
    status: AppStatus
    uploaded_at: datetime
    extracted_metadata: dict | None = None


class ControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    version: str
    code: str
    category: str
    title: str
    description: str
    mastg_tests: list[str]
    maswe_ids: list[str]
    applies_to: list[str]
    automatable: bool


class TestRunCreate(BaseModel):
    tester_name: str | None = None


class TestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    app_id: uuid.UUID
    catalog_version: str
    status: TestRunStatus
    started_at: datetime
    completed_at: datetime | None
    tester_name: str | None
    notes: str | None


class ControlResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    test_run_id: uuid.UUID
    control_id: uuid.UUID
    status: ResultStatus
    method: ResultMethod
    evidence: str | None
    notes: str | None
    updated_at: datetime
    control: ControlOut


class ControlResultUpdate(BaseModel):
    status: ResultStatus | None = None
    evidence: str | None = None
    notes: str | None = None


class FindingCreate(BaseModel):
    control_id: uuid.UUID | None = None
    title: str
    severity: Severity = Severity.medium
    description: str
    evidence: str | None = None
    remediation: str | None = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    test_run_id: uuid.UUID
    control_id: uuid.UUID | None
    title: str
    severity: Severity
    description: str
    evidence: str | None
    remediation: str | None
    created_at: datetime
