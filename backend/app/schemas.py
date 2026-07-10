from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models import UrgencyLevel, UserRole


URGENCY_LABELS = {
    UrgencyLevel.LOW: "Низкая",
    UrgencyLevel.MEDIUM: "Средняя",
    UrgencyLevel.HIGH: "Высокая",
    UrgencyLevel.CRITICAL: "Критическая",
}


class CategoryOut(BaseModel):
    id: int
    name: str


class StatusOut(BaseModel):
    id: int
    name: str
    sort_order: int


class ClientAutocomplete(BaseModel):
    id: int
    full_name: str
    department: str | None


class ClientOut(BaseModel):
    id: int
    full_name: str
    department: str | None


class UserOut(BaseModel):
    id: int
    login: str
    full_name: str
    role: UserRole


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PublicRequestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    cabinet: str = Field(min_length=1, max_length=64)
    category_id: int
    description: str = Field(min_length=5)
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    preferred_visit_time: str | None = Field(default=None, max_length=255)


class PublicRequestResponse(BaseModel):
    id: int
    message: str = "Ваша заявка успешно зарегистрирована."


class SpecialistBrief(BaseModel):
    id: int
    full_name: str


class RequestListItem(BaseModel):
    id: int
    created_at: datetime
    client_name: str
    cabinet: str
    category_name: str
    urgency: UrgencyLevel
    urgency_label: str
    status_id: int
    status_name: str
    specialist: SpecialistBrief | None


class RequestHistoryItem(BaseModel):
    id: int
    changed_at: datetime
    old_status_name: str | None
    new_status_name: str
    changed_by_name: str | None
    comment: str | None


class RequestDetail(BaseModel):
    id: int
    created_at: datetime
    client: ClientOut
    cabinet: str
    category_id: int
    category_name: str
    urgency: UrgencyLevel
    urgency_label: str
    description: str
    preferred_visit_time: str | None
    status_id: int
    status_name: str
    specialist: SpecialistBrief | None
    accepted_at: datetime | None
    completed_at: datetime | None
    specialist_comment: str | None
    history: list[RequestHistoryItem]


class RequestUpdate(BaseModel):
    status_id: int | None = None
    specialist_id: int | None = None
    specialist_comment: str | None = None
    client_department: str | None = Field(default=None, max_length=255)


class SortField(str, Enum):
    created_at = "created_at"
    urgency = "urgency"
    status = "status"


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2, max_length=255)
    role: UserRole = UserRole.SPECIALIST


class UserAdminOut(BaseModel):
    id: int
    login: str
    full_name: str
    role: UserRole
    account_status: str
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None


class StatusCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    sort_order: int = 0


class StatusUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    sort_order: int | None = None
    is_active: bool | None = None


class StatsDashboard(BaseModel):
    new_count: int
    in_progress_count: int
    completed_count: int
    avg_processing_hours: float | None
    by_category: list[dict]
    by_specialist: list[dict]
