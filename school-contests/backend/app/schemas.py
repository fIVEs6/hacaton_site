"""Pydantic-схемы запросов и ответов."""
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models import (EventLevel, EventStatus, ParticipationType, PStatus, User, UserRole)

# Простая проверка email (поддерживает и внутренние домены вида school.local)
Email = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=255,
                                         pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegisterIn(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=128)
    last_name: Name
    first_name: Name
    middle_name: Name | None = None
    grade: int = Field(ge=1, le=11)
    class_letter: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2)] | None = None
    school: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    consent: bool = False


class LoginIn(BaseModel):
    email: Email
    password: str


class TokenIn(BaseModel):
    token: str


class EmailIn(BaseModel):
    email: Email


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class ProfileIn(BaseModel):
    last_name: Name | None = None
    first_name: Name | None = None
    middle_name: Name | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    class_letter: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2)] | None = None
    school: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None


def user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "role": u.role.value, "last_name": u.last_name,
        "first_name": u.first_name, "middle_name": u.middle_name, "full_name": u.full_name,
        "grade": u.grade, "class_letter": u.class_letter, "class_name": u.class_name,
        "school": u.school, "has_photo": bool(u.photo_path), "email_verified": u.email_verified,
        "is_active": u.is_active,
    }


class EventIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
    description: str = ""
    rules: str = ""
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    level: EventLevel = EventLevel.school
    participation_type: ParticipationType = ParticipationType.individual
    team_min_size: int | None = Field(default=None, ge=2, le=50)
    team_max_size: int | None = Field(default=None, ge=2, le=50)
    start_date: date
    end_date: date
    status: EventStatus = EventStatus.draft

    @field_validator("end_date")
    @classmethod
    def _dates(cls, v, info):
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("Дата окончания раньше даты начала")
        return v


class TeamIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]


class JoinTeamIn(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=4, max_length=12)]


class ResultItem(BaseModel):
    registration_id: int | None = None
    team_id: int | None = None
    place: int | None = Field(default=None, ge=1, le=999)
    score: float | None = Field(default=None, ge=0, le=99999)
    status: PStatus

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v == PStatus.registered:
            raise ValueError("Для результата выберите: участник, призёр или победитель")
        return v


class ResultsIn(BaseModel):
    items: list[ResultItem]


class DiplomaGenIn(BaseModel):
    include_participants: bool = False


class CommitIn(BaseModel):
    choices: dict[str, int] = {}


class UserPatch(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class TemplateIn(BaseModel):
    html: str = Field(min_length=50, max_length=200_000)
