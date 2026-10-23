"""ORM-модели. Структура таблиц задаётся SQL-миграцией migrations/001_init.sql."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer,
                        Numeric, SmallInteger, String, Text, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _enum(py_enum: type[enum.Enum], name: str) -> Enum:
    """Enum, привязанный к уже созданному в миграции типу PostgreSQL."""
    return Enum(py_enum, name=name, create_type=False, values_callable=lambda e: [m.value for m in e])


class UserRole(str, enum.Enum):
    student = "student"
    admin = "admin"


class EventStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    finished = "finished"


class EventLevel(str, enum.Enum):
    school = "school"
    municipal = "municipal"
    regional = "regional"
    federal = "federal"
    international = "international"


class ParticipationType(str, enum.Enum):
    individual = "individual"
    team = "team"


class PStatus(str, enum.Enum):
    registered = "registered"
    participated = "participated"
    prizewinner = "prizewinner"
    winner = "winner"


class TokenKind(str, enum.Enum):
    verify_email = "verify_email"
    reset_password = "reset_password"


class ImportStatus(str, enum.Enum):
    preview = "preview"
    committed = "committed"
    failed = "failed"


# Подписи для интерфейса и дипломов
STATUS_RU = {"registered": "Записан", "participated": "Участник", "prizewinner": "Призёр", "winner": "Победитель"}
LEVEL_RU = {"school": "Школьный", "municipal": "Муниципальный", "regional": "Региональный",
            "federal": "Всероссийский", "international": "Международный"}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), default=UserRole.student)
    last_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    grade: Mapped[int | None] = mapped_column(SmallInteger)
    class_letter: Mapped[str | None] = mapped_column(String(2))
    school: Mapped[str | None] = mapped_column(String(255))
    photo_path: Mapped[str | None] = mapped_column(String(500))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_logins: Mapped[int] = mapped_column(SmallInteger, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.last_name, self.first_name, self.middle_name) if p)

    @property
    def short_name(self) -> str:
        """«Иванов И. П.» — для публичной проверки диплома (минимизация данных)."""
        initials = " ".join(f"{p[0]}." for p in (self.first_name, self.middle_name) if p)
        return f"{self.last_name} {initials}".strip()

    @property
    def class_name(self) -> str:
        return f"{self.grade or ''}{self.class_letter or ''}"


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[TokenKind] = mapped_column(_enum(TokenKind, "email_token_kind"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    rules: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(String(100))
    level: Mapped[EventLevel] = mapped_column(_enum(EventLevel, "event_level"), default=EventLevel.school)
    participation_type: Mapped[ParticipationType] = mapped_column(
        _enum(ParticipationType, "participation_type"), default=ParticipationType.individual)
    team_min_size: Mapped[int | None] = mapped_column(SmallInteger)
    team_max_size: Mapped[int | None] = mapped_column(SmallInteger)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[EventStatus] = mapped_column(_enum(EventStatus, "event_status"), default=EventStatus.draft)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    join_code: Mapped[str] = mapped_column(String(12), unique=True)
    captain_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    status: Mapped[PStatus] = mapped_column(_enum(PStatus, "participation_status"), default=PStatus.registered)
    source: Mapped[str] = mapped_column(String(20), default="self")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(lazy="joined")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    registration_id: Mapped[int | None] = mapped_column(ForeignKey("registrations.id", ondelete="CASCADE"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    place: Mapped[int | None] = mapped_column(SmallInteger)
    score: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    status: Mapped[PStatus] = mapped_column(_enum(PStatus, "participation_status"))
    entered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiplomaTemplate(Base):
    __tablename__ = "diploma_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    html: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Diploma(Base):
    __tablename__ = "diplomas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id", ondelete="CASCADE"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("diploma_templates.id", ondelete="SET NULL"))
    pdf_path: Mapped[str] = mapped_column(String(500))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    issued_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[ImportStatus] = mapped_column(_enum(ImportStatus, "import_status"), default=ImportStatus.preview)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    matched_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
