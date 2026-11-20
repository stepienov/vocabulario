"""Content report contracts (E-001/F-007/T-002)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import UUID4, BaseModel, Field, field_validator

TargetKind = Literal["card", "lookup", "practice"]
ReportField = Literal[
    "meaning",
    "definition",
    "example",
    "translation",
    "association",
    "related",
    "question",
    "answer",
    "feedback",
    "other",
]
ReportReason = Literal["incorrect", "offensive", "privacy", "other"]
ReportStatus = Literal["received", "in_review", "resolved"]
# `expired`: the details were deleted after the retention; only the receipt is left.
ReportView = Literal["received", "in_review", "resolved", "expired"]


class ContentReportCreate(BaseModel):
    client_report_id: UUID4
    profile_id: UUID
    target_kind: TargetKind
    target_id: UUID | None = None
    field: ReportField
    reason: ReportReason
    excerpt: str = Field(min_length=1, max_length=4000)
    note: str | None = Field(default=None, max_length=1000)
    app_version: str | None = Field(default=None, max_length=32)

    @field_validator("excerpt")
    @classmethod
    def _excerpt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("excerpt_blank")
        return value

    @field_validator("note")
    @classmethod
    def _blank_note_is_none(cls, value: str | None) -> str | None:
        return value if value and value.strip() else None


class ContentReportResponse(BaseModel):
    report_id: UUID
    status: ReportView
    received_at: datetime
    resolution_code: str | None = None
