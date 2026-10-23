"""Администратор по умолчанию и демо-данные.

Запуск вручную: python -m app.seed
При старте контейнера вызывается автоматически, если SEED_ON_START=true.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db import SessionLocal, run_migrations
from app.deps import random_code
from app.models import (Event, EventLevel, EventStatus, ParticipationType, PStatus, Registration, Result, Team, User,
                        UserRole)
from app.services import diploma_pdf

log = logging.getLogger(__name__)

STUDENT_PASSWORD = "Student123"

# (фамилия, имя, отчество, класс, буква, email)
STUDENTS = [
    ("Иванов", "Иван", "Петрович", 8, "Б", "ivan@school.local"),
    ("Петрова", "Мария", "Сергеевна", 8, "Б", "maria@school.local"),
    ("Сидоров", "Алексей", "Андреевич", 9, "А", "alexey@school.local"),
    ("Кузнецова", "Дарья", "Игоревна", 9, "А", "darya@school.local"),
    ("Смирнов", "Максим", "Олегович", 10, "В", "maxim@school.local"),
    ("Попова", "Анастасия", "Викторовна", 10, "В", "anastasia@school.local"),
    ("Васильев", "Егор", "Дмитриевич", 11, "А", "egor@school.local"),
    ("Морозова", "Полина", "Алексеевна", 11, "А", "polina@school.local"),
    ("Новиков", "Артём", "Павлович", 7, "Б", "artem@school.local"),
    ("Фёдорова", "Софья", "Николаевна", 7, "Б", "sofia@school.local"),
    ("Новикова", "Анна", "Романовна", 9, "Б", "anna@school.local"),
    ("Петров", "Пётр", "Иванович", 8, "А", "petr.a@school.local"),
    ("Петров", "Пётр", "Игоревич", 8, "Б", "petr.b@school.local"),  # однофамильцы — для демонстрации импорта
]


def ensure_admin(db: Session) -> User:
    admin = db.scalar(select(User).where(User.role == UserRole.admin))
    if not admin:
        admin = User(email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password),
                     role=UserRole.admin, last_name="Администратор", first_name="Школьный", middle_name=None,
                     school=settings.school_name, email_verified=True)
        db.add(admin)
        db.commit()
    return admin


def _event(db: Session, admin: User, **kw) -> Event:
    e = Event(created_by=admin.id, **kw)
    db.add(e)
    db.flush()
    return e


def seed_demo(db: Session) -> None:
    admin = ensure_admin(db)
    diploma_pdf.ensure_default_template(db)
    if db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.student)):
        return  # демо-данные уже есть

    today = date.today()
    pw = hash_password(STUDENT_PASSWORD)
    users = []
    for last, first, middle, grade, letter, email in STUDENTS:
        u = User(email=email, password_hash=pw, role=UserRole.student, last_name=last, first_name=first,
                 middle_name=middle, grade=grade, class_letter=letter, school=settings.school_name,
                 email_verified=True)
        db.add(u)
        users.append(u)
    db.flush()
    by_email = {u.email: u for u in users}

    # 1. Завершённая олимпиада (индивидуальная) с результатами
    math = _event(db, admin, title="Школьный этап олимпиады по математике", subject="Математика",
                  description="Ежегодная олимпиада для учеников 7–11 классов. Пять задач, 120 минут.",
                  rules="Калькуляторы запрещены. Победителем становится участник с максимальным баллом.",
                  level=EventLevel.school, participation_type=ParticipationType.individual,
                  start_date=today - timedelta(days=14), end_date=today - timedelta(days=14),
                  status=EventStatus.finished)
    scores = [("ivan@school.local", 1, 98.5, PStatus.winner), ("maria@school.local", 2, 91, PStatus.prizewinner),
              ("alexey@school.local", 3, 84, PStatus.prizewinner), ("darya@school.local", None, 62, PStatus.participated),
              ("maxim@school.local", None, 55, PStatus.participated), ("egor@school.local", None, 48, PStatus.participated)]
    for email, place, score, status in scores:
        reg = Registration(event_id=math.id, user_id=by_email[email].id, status=status, source="import")
        db.add(reg)
        db.flush()
        db.add(Result(event_id=math.id, registration_id=reg.id, place=place, score=score, status=status,
                      entered_by=admin.id))

    # 2. Завершённая командная игра с результатами
    brain = _event(db, admin, title="Интеллектуальная игра «Брейн-ринг»", subject="Общеобразовательный",
                   description="Командная игра: вопросы по истории, литературе и науке.",
                   rules="Команда от 3 до 5 человек. Время на ответ — 60 секунд.",
                   level=EventLevel.municipal, participation_type=ParticipationType.team, team_min_size=3,
                   team_max_size=5, start_date=today - timedelta(days=30), end_date=today - timedelta(days=29),
                   status=EventStatus.finished)
    teams_def = [("Эрудиты", "ivan@school.local", ["maria@school.local", "anna@school.local"], 1, 47, PStatus.winner),
                 ("Мозговой штурм", "polina@school.local", ["egor@school.local", "artem@school.local"], 2, 41,
                  PStatus.prizewinner)]
    for name, captain, members, place, score, status in teams_def:
        team = Team(event_id=brain.id, name=name, join_code=random_code(6), captain_id=by_email[captain].id)
        db.add(team)
        db.flush()
        for email in [captain, *members]:
            db.add(Registration(event_id=brain.id, user_id=by_email[email].id, team_id=team.id, status=status))
        db.add(Result(event_id=brain.id, team_id=team.id, place=place, score=score, status=status, entered_by=admin.id))

    # 3. Идёт сейчас — индивидуальный конкурс
    inf = _event(db, admin, title="Конкурс проектов по информатике", subject="Информатика",
                 description="Представьте проект: игра, сайт, программа или робот. Защита — 5 минут.",
                 rules="Работы принимаются до конца недели. Проект должен быть выполнен самостоятельно.",
                 level=EventLevel.school, participation_type=ParticipationType.individual,
                 start_date=today - timedelta(days=2), end_date=today + timedelta(days=5),
                 status=EventStatus.published)
    for email in ["maxim@school.local", "darya@school.local", "sofia@school.local"]:
        db.add(Registration(event_id=inf.id, user_id=by_email[email].id, source="self"))

    # 4. Скоро — командный турнир, одна команда уже есть
    quiz = _event(db, admin, title="Турнир по физике «Эксперимент»", subject="Физика",
                  description="Командный турнир: теория и практические эксперименты.",
                  rules="Команда 2–4 человека. Нужен код команды для вступления.",
                  level=EventLevel.regional, participation_type=ParticipationType.team, team_min_size=2,
                  team_max_size=4, start_date=today + timedelta(days=12), end_date=today + timedelta(days=12),
                  status=EventStatus.published)
    team = Team(event_id=quiz.id, name="Ньютоны", join_code="NEWTON", captain_id=by_email["egor@school.local"].id)
    db.add(team)
    db.flush()
    db.add(Registration(event_id=quiz.id, user_id=by_email["egor@school.local"].id, team_id=team.id))

    # 5. Скоро — индивидуальная олимпиада (для демонстрации записи)
    _event(db, admin, title="Олимпиада по русскому языку", subject="Русский язык",
           description="Грамотность, словообразование, работа с текстом.",
           rules="Письменная работа 90 минут. Словари не разрешены.",
           level=EventLevel.school, participation_type=ParticipationType.individual,
           start_date=today + timedelta(days=9), end_date=today + timedelta(days=9), status=EventStatus.published)

    # 6. Черновик
    _event(db, admin, title="Конкурс чтецов «Живое слово»", subject="Литература",
           description="Черновик: даты уточняются.", rules="", level=EventLevel.school,
           participation_type=ParticipationType.individual, start_date=today + timedelta(days=40),
           end_date=today + timedelta(days=40), status=EventStatus.draft)
    db.commit()

    # Дипломы для завершённых мероприятий
    for e in (math, brain):
        try:
            diploma_pdf.issue_for_event(db, e, admin)
        except Exception as exc:  # noqa: BLE001
            log.warning("Не удалось сгенерировать демо-дипломы: %s", exc)
    log.info("Демо-данные созданы")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_migrations()
    with SessionLocal() as db:
        seed_demo(db)


if __name__ == "__main__":
    main()
