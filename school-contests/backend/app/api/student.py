"""Личный кабинет ученика: профиль, лента конкурсов, запись, команды, прогресс, дипломы, проверка диплома."""
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.deps import get_current_user, random_code
from app.models import (STATUS_RU, LEVEL_RU, Diploma, Event, EventStatus, ParticipationType, PStatus,
                        Registration, Result, Team, User, UserRole)
from app.schemas import JoinTeamIn, ProfileIn, TeamIn, user_out

router = APIRouter(tags=["student"])

MAX_PHOTO = 2 * 1024 * 1024


# ---------- Профиль ----------

@router.patch("/profile")
def update_profile(data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "class_letter":
            value = (value or "").upper() or None
        if value is None and field in ("last_name", "first_name", "grade"):
            continue  # обязательные поля нельзя очистить
        setattr(user, field, value)
    db.commit()
    return user_out(user)


def _detect_image(head: bytes) -> str | None:
    """Определяет тип по сигнатуре файла, а не по расширению от клиента."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


@router.post("/profile/photo")
async def upload_photo(file: UploadFile = File(...), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    content = await file.read(MAX_PHOTO + 1)
    if len(content) > MAX_PHOTO:
        raise HTTPException(413, "Файл больше 2 МБ")
    ext = _detect_image(content[:16])
    if not ext:
        raise HTTPException(400, "Допустимы изображения JPG, PNG или WEBP")
    folder = Path(settings.data_dir) / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (folder / name).write_bytes(content)
    _remove_photo_file(user)
    user.photo_path = f"photos/{name}"
    db.commit()
    return user_out(user)


def _remove_photo_file(user: User) -> None:
    if user.photo_path:
        (Path(settings.data_dir) / user.photo_path).unlink(missing_ok=True)


@router.get("/profile/photo")
def get_photo(user: User = Depends(get_current_user)):
    if not user.photo_path:
        raise HTTPException(404, "Фото не загружено")
    path = Path(settings.data_dir) / user.photo_path
    if not path.exists():
        raise HTTPException(404, "Фото не найдено")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})


@router.delete("/profile/photo")
def delete_photo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _remove_photo_file(user)
    user.photo_path = None
    db.commit()
    return user_out(user)


# ---------- Лента конкурсов ----------

def event_out(e: Event, reg: Registration | None = None, count: int | None = None) -> dict:
    today = date.today()
    if e.status == EventStatus.finished or e.end_date < today:
        phase = "finished"
    elif e.start_date > today:
        phase = "upcoming"
    else:
        phase = "ongoing"
    return {
        "id": e.id, "title": e.title, "description": e.description, "rules": e.rules,
        "subject": e.subject, "level": e.level.value, "level_label": LEVEL_RU[e.level.value],
        "participation_type": e.participation_type.value,
        "team_min_size": e.team_min_size, "team_max_size": e.team_max_size,
        "start_date": e.start_date.isoformat(), "end_date": e.end_date.isoformat(),
        "status": e.status.value, "phase": phase,
        "can_register": e.status == EventStatus.published and e.end_date >= today,
        "registered": reg is not None, "my_status": reg.status.value if reg else None,
        "participants": count,
    }


@router.get("/events")
def list_events(subject: str | None = None, date_from: date | None = None, date_to: date | None = None,
                status: str | None = None, q: str | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    stmt = select(Event).where(Event.status.in_([EventStatus.published, EventStatus.finished]))
    if subject:
        stmt = stmt.where(func.lower(Event.subject) == subject.lower())
    if date_from:
        stmt = stmt.where(Event.end_date >= date_from)
    if date_to:
        stmt = stmt.where(Event.start_date <= date_to)
    if q:
        stmt = stmt.where(Event.title.ilike(f"%{q}%"))
    if status == "upcoming":
        stmt = stmt.where(Event.status == EventStatus.published, Event.start_date > today)
    elif status == "ongoing":
        stmt = stmt.where(Event.status == EventStatus.published, Event.start_date <= today, Event.end_date >= today)
    elif status == "finished":
        stmt = stmt.where(or_(Event.status == EventStatus.finished, Event.end_date < today))
    events = db.scalars(stmt.order_by(Event.start_date.desc())).all()
    regs = {r.event_id: r for r in db.scalars(select(Registration).where(Registration.user_id == user.id))}
    subjects = sorted(db.scalars(select(Event.subject).where(
        Event.status.in_([EventStatus.published, EventStatus.finished])).distinct()).all())
    return {"items": [event_out(e, regs.get(e.id)) for e in events], "subjects": subjects}


def _team_info(db: Session, team: Team | None, user: User) -> dict | None:
    if not team:
        return None
    members = db.scalars(select(Registration).where(Registration.team_id == team.id)).all()
    return {"id": team.id, "name": team.name, "join_code": team.join_code,
            "is_captain": team.captain_id == user.id,
            "members": [{"id": m.user_id, "name": m.user.full_name, "class": m.user.class_name,
                         "captain": m.user_id == team.captain_id} for m in members]}


def _published_event(db: Session, event_id: int) -> Event:
    e = db.get(Event, event_id)
    if not e or e.status == EventStatus.draft:
        raise HTTPException(404, "Мероприятие не найдено")
    return e


@router.get("/events/{event_id}")
def get_event(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = _published_event(db, event_id)
    reg = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.user_id == user.id))
    count = db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == e.id))
    out = event_out(e, reg, count)
    team = db.get(Team, reg.team_id) if reg and reg.team_id else None
    out["team"] = _team_info(db, team, user)
    return out


def _check_open(e: Event) -> None:
    if e.status != EventStatus.published or e.end_date < date.today():
        raise HTTPException(400, "Запись на это мероприятие закрыта")


@router.post("/events/{event_id}/register", status_code=201)
def register_event(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = _published_event(db, event_id)
    _check_open(e)
    if e.participation_type == ParticipationType.team:
        raise HTTPException(400, "Это командный конкурс: создайте команду или вступите в существующую")
    if db.scalar(select(Registration.id).where(Registration.event_id == e.id, Registration.user_id == user.id)):
        raise HTTPException(409, "Вы уже записаны на это мероприятие")
    db.add(Registration(event_id=e.id, user_id=user.id, source="self"))
    db.commit()
    return {"message": "Вы записаны на мероприятие"}


@router.delete("/events/{event_id}/register")
def unregister_event(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = _published_event(db, event_id)
    reg = db.scalar(select(Registration).where(Registration.event_id == e.id, Registration.user_id == user.id))
    if not reg:
        raise HTTPException(404, "Вы не записаны на это мероприятие")
    if db.scalar(select(Result.id).where(or_(Result.registration_id == reg.id,
                                             and_(Result.team_id.is_not(None), Result.team_id == reg.team_id)))):
        raise HTTPException(400, "Результат уже внесён, отменить запись нельзя")
    if reg.team_id:
        team = db.get(Team, reg.team_id)
        others = db.scalar(select(func.count()).select_from(Registration).where(
            Registration.team_id == reg.team_id, Registration.user_id != user.id))
        if team and team.captain_id == user.id and others:
            raise HTTPException(400, "Капитан не может выйти, пока в команде есть другие участники")
        db.delete(reg)
        db.flush()
        if team and not others:
            db.delete(team)
    else:
        db.delete(reg)
    db.commit()
    return {"message": "Запись отменена"}


@router.post("/events/{event_id}/teams", status_code=201)
def create_team(event_id: int, data: TeamIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = _published_event(db, event_id)
    _check_open(e)
    if e.participation_type != ParticipationType.team:
        raise HTTPException(400, "Это индивидуальный конкурс")
    if db.scalar(select(Registration.id).where(Registration.event_id == e.id, Registration.user_id == user.id)):
        raise HTTPException(409, "Вы уже участвуете в этом мероприятии")
    if db.scalar(select(Team.id).where(Team.event_id == e.id, func.lower(Team.name) == data.name.lower())):
        raise HTTPException(409, "Команда с таким названием уже есть")
    for _ in range(10):
        code = random_code(6)
        if not db.scalar(select(Team.id).where(Team.join_code == code)):
            break
    team = Team(event_id=e.id, name=data.name, join_code=code, captain_id=user.id)
    db.add(team)
    db.flush()
    db.add(Registration(event_id=e.id, user_id=user.id, team_id=team.id, source="self"))
    db.commit()
    return {"message": "Команда создана", "join_code": code}


@router.post("/events/{event_id}/teams/join", status_code=201)
def join_team(event_id: int, data: JoinTeamIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = _published_event(db, event_id)
    _check_open(e)
    team = db.scalar(select(Team).where(Team.event_id == e.id, Team.join_code == data.code))
    if not team:
        raise HTTPException(404, "Команда с таким кодом не найдена")
    if db.scalar(select(Registration.id).where(Registration.event_id == e.id, Registration.user_id == user.id)):
        raise HTTPException(409, "Вы уже участвуете в этом мероприятии")
    size = db.scalar(select(func.count()).select_from(Registration).where(Registration.team_id == team.id))
    if e.team_max_size and size >= e.team_max_size:
        raise HTTPException(400, f"В команде уже максимальное число участников ({e.team_max_size})")
    db.add(Registration(event_id=e.id, user_id=user.id, team_id=team.id, source="self"))
    db.commit()
    return {"message": f"Вы вступили в команду «{team.name}»"}


# ---------- Прогресс и дипломы ----------

def place_text(result: Result | None) -> str:
    if not result:
        return ""
    return f"{result.place} место" if result.place else STATUS_RU[result.status.value]


@router.get("/me/progress")
def my_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Registration, Event).join(Event, Event.id == Registration.event_id)
        .where(Registration.user_id == user.id).order_by(Event.start_date.desc())).all()
    diplomas = {d.event_id: d.id for d in db.scalars(
        select(Diploma).where(Diploma.user_id == user.id, Diploma.revoked_at.is_(None)))}
    items = []
    stats = {"total": 0, "registered": 0, "participated": 0, "prizewinner": 0, "winner": 0,
             "total_score": 0.0, "diplomas": len(diplomas)}
    for reg, ev in rows:
        res = db.scalar(select(Result).where(or_(
            Result.registration_id == reg.id,
            and_(Result.team_id.is_not(None), Result.team_id == reg.team_id))))
        team = db.get(Team, reg.team_id) if reg.team_id else None
        stats["total"] += 1
        stats[reg.status.value] += 1
        if res and res.score is not None:
            stats["total_score"] += float(res.score)
        items.append({
            "event_id": ev.id, "title": ev.title, "subject": ev.subject, "level_label": LEVEL_RU[ev.level.value],
            "start_date": ev.start_date.isoformat(), "status": reg.status.value,
            "status_label": STATUS_RU[reg.status.value], "place": res.place if res else None,
            "score": float(res.score) if res and res.score is not None else None,
            "team_name": team.name if team else None, "diploma_id": diplomas.get(ev.id)})
    stats["total_score"] = round(stats["total_score"], 2)
    return {"stats": stats, "items": items}


@router.get("/me/diplomas")
def my_diplomas(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Diploma, Event, Result).join(Event, Event.id == Diploma.event_id)
        .join(Result, Result.id == Diploma.result_id)
        .where(Diploma.user_id == user.id, Diploma.revoked_at.is_(None))
        .order_by(Diploma.issued_at.desc())).all()
    return [{"id": d.id, "number": d.number, "event_title": ev.title, "subject": ev.subject,
             "place": res.place, "result": STATUS_RU[res.status.value],
             "issued_at": d.issued_at.date().isoformat()} for d, ev, res in rows]


@router.get("/diplomas/{diploma_id}/pdf")
def download_diploma(diploma_id: int, inline: bool = False, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    d = db.get(Diploma, diploma_id)
    if not d or (d.user_id != user.id and user.role != UserRole.admin):
        raise HTTPException(404, "Диплом не найден")
    if d.revoked_at:
        raise HTTPException(410, "Диплом отозван")
    path = Path(settings.data_dir) / d.pdf_path
    if not path.exists():
        raise HTTPException(404, "Файл диплома не найден")
    # inline=true — открыть в браузере (просмотр), иначе — скачать
    return FileResponse(path, media_type="application/pdf", filename=f"{d.number}.pdf",
                        content_disposition_type="inline" if inline else "attachment")


# ---------- Публичная проверка диплома ----------

@router.get("/verify/{number}")
def verify_diploma(number: str, db: Session = Depends(get_db)):
    d = db.scalar(select(Diploma).where(Diploma.number == number.strip().upper()))
    if not d or d.revoked_at:
        return {"valid": False}
    holder = db.get(User, d.user_id)
    event = db.get(Event, d.event_id)
    res = db.get(Result, d.result_id)
    return {"valid": True, "number": d.number, "holder": holder.short_name, "event": event.title,
            "place": res.place, "result": STATUS_RU[res.status.value], "issued_at": d.issued_at.date().isoformat()}
