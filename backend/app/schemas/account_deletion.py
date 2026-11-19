"""Public account deletion contract (E-001/F-006/T-002)."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import UUID4, BaseModel, EmailStr, Field, StringConstraints

CONFIRMATION_VERSION = "delete-account-v1"
# 32 random bytes as unpadded base64url; anything else is rejected before hashing.
Secret32 = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{43}$")]
DeletionAction = Literal["request", "cancel"]


class DeletionPasswordProofRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    action: DeletionAction


class DeletionEmailRequest(BaseModel):
    email: EmailStr
    action: DeletionAction


class DeletionGoogleChallengeRequest(BaseModel):
    action: DeletionAction


class DeletionGoogleProofRequest(BaseModel):
    challenge_id: UUID4
    id_token: str = Field(min_length=1, max_length=8192)
    action: DeletionAction


class DeletionProofResponse(BaseModel):
    action_token: str
    action: DeletionAction
    method: str
    expires_at: datetime
    user_id: UUID
    deletion_id: UUID | None = None
    state: str | None = None


class DeletionRequestBody(BaseModel):
    request_id: UUID4
    action_token: Secret32
    status_secret: Secret32
    confirmation_version: Literal["delete-account-v1"]


class DeletionStatusRequest(BaseModel):
    request_id: UUID4 | None = None
    status_secret: Secret32 | None = None
    action_token: Secret32 | None = None


class DeletionCancelBody(BaseModel):
    deletion_id: UUID4
    request_id: UUID4
    action_token: Secret32


class DeletionView(BaseModel):
    deletion_id: UUID
    state: str
    requested_at: datetime
    cancel_until: datetime
    purge_due_at: datetime
    can_cancel: bool
    cancelled_at: datetime | None = None
    completed_at: datetime | None = None
    server_time: datetime


class DeletionCancelResponse(BaseModel):
    status: str = "cancelled"
    requires_login: bool = True
    deletion: DeletionView
