"""Админ-панель: мероприятия, импорт участников, результаты, дипломы, отчёты, пользователи."""
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.student import event_out, place_text
from app.core.config import settings
from app.db import get_db
from app.deps import audit, require_admin
from app.models import (STATUS_RU, Diploma, Event, EventStatus, ImportLog, ImportStatus, ParticipationType, PStatus,
                        Registration, Result, Team, User, UserRole)
from app.schemas import (CommitIn, DiplomaGenIn, EventIn, ResultsIn, TemplateIn, UserPatch, user_out)
from app.services import diploma_pdf, importer, reports

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _event(db: Session, event_id: int) -> Event:
    e = db.get(Event, event_id)
    if not e:
        raise HTTPException(404, "Мероприятие не найдено")
    return e


# ---------- Мероприятия ----------

def _apply_event(e: Event, data: EventIn) -> None:
    values = data.model_dump()
    if data.participation_type == ParticipationType.team:
        values["team_min_size"] = data.team_min_size or 2
        values["team_max_size"] = data.team_max_size or max(values["team_min_size"], 5)
        if values["team_max_size"] < values["team_min_size"]:
            raise HTTPException(422, "Максимальный размер команды меньше минимального")
    else:
        values["team_min_size"] = values["team_max_size"] = None
    for k, v in values.items():
        setattr(e, k, v)


def _count(db: Session, event_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event_id))


@router.get("/events")
def admin_events(db: Session = Depends(get_db)):
    events = db.scalars(select(Event).order_by(Event.start_date.desc())).all()
    counts = dict(db.execute(select(Registration.event_id, func.count()).group_by(Registration.event_id)).all())
    return [event_out(e, None, counts.get(e.id, 0)) for e in events]


@router.post("/events", status_code=201)
def create_event(data: EventIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    e = Event(created_by=admin.id)
    _apply_event(e, data)
    db.add(e)
    db.flush()
    audit(db, admin, "event.create", "event", e.id, title=e.title)
    db.commit()
    return event_out(e, None, 0)


@router.get("/events/{event_id}")
def admin_event(event_id: int, db: Session = Depends(get_db)):
    e = _event(db, event_id)
    return event_out(e, None, _count(db, e.id))


@router.put("/events/{event_id}")
def update_event(event_id: int, data: EventIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    e = _event(db, event_id)
    if e.participation_type != data.participation_type and _count(db, e.id):
        raise HTTPException(409, "Нельзя менять формат (индивидуальный/командный), когда есть записавшиеся")
    _apply_event(e, data)
    audit(db, admin, "event.update", "event", e.id)
    db.commit()
    return event_out(e, None, _count(db, e.id))


@router.delete("/events/{event_id}")
def delete_event(event_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    e = _event(db, event_id)
    if db.scalar(select(Diploma.id).where(Diploma.event_id == e.id)):
        raise HTTPException(409, "По мероприятию выданы дипломы — удалить его нельзя. Переведите в статус «Завершено».")
    audit(db, admin, "event.delete", "event", e.id, title=e.title)
    db.delete(e)
    db.commit()
    return {"message": "Мероприятие удалено"}


@router.get("/events/{event_id}/participants")
def participants(event_id: int, db: Session = Depends(get_db)):
    e = _event(db, event_id)
    regs = db.scalars(select(Registration).where(Registration.event_id == e.id)
                      .order_by(Registration.created_at)).all()
    results = db.scalars(select(Result).where(Result.event_id == e.id)).all()
    by_reg = {r.registration_id: r for r in results if r.registration_id}
    by_team = {r.team_id: r for r in results if r.team_id}
    diplomas = {d.user_id: d for d in db.scalars(select(Diploma).where(Diploma.event_id == e.id))}

    def res_out(r: Result | None):
        return {"place": r.place, "score": float(r.score) if r.score is not None else None,
                "status": r.status.value} if r else None

    def dip_out(uid: int):
        d = diplomas.get(uid)
        return {"id": d.id, "number": d.number, "revoked": bool(d.revoked_at)} if d else None

    if e.participation_type == ParticipationType.team:
        teams = db.scalars(select(Team).where(Team.event_id == e.id).order_by(Team.name)).all()
        out = []
        for t in teams:
            members = [r for r in regs if r.team_id == t.id]
            out.append({"team_id": t.id, "name": t.name, "result": res_out(by_team.get(t.id)),
                        "members": [{"name": m.user.full_name, "class": m.user.class_name,
                                     "diploma": dip_out(m.user_id)} for m in members]})
        return {"type": "team", "teams": out, "individual": []}
    return {"type": "individual", "teams": [], "individual": [
        {"registration_id": r.id, "name": r.user.full_name, "class": r.user.class_name, "email": r.user.email,
         "status": r.status.value, "source": r.source, "result": res_out(by_reg.get(r.id)),
         "diploma": dip_out(r.user_id)} for r in regs]}


# ---------- Импорт участников ----------

@router.post("/events/{event_id}/imports", status_code=201)
async def upload_import(event_id: int, file: UploadFile = File(...), admin: User = Depends(require_admin),
                        db: Session = Depends(get_db)):
    e = _event(db, event_id)
    name = file.filename or "file"
    ext = name.lower().rsplit(".", 1)[-1]
    if ext not in ("csv", "xlsx"):
        raise HTTPException(400, "Допустимы только файлы CSV и XLSX")
    limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"Файл больше {settings.max_upload_mb} МБ")
    if ext == "xlsx" and not content.startswith(b"PK"):
        raise HTTPException(400, "Файл не похож на настоящий XLSX")
    if ext == "csv" and b"\x00" in content[:4096]:
        raise HTTPException(400, "Файл не похож на текстовый CSV")
    folder = Path(settings.data_dir) / "imports"
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"imports/{uuid.uuid4().hex}.{ext}"
    path = Path(settings.data_dir) / stored
    path.write_bytes(content)
    try:
        rows = importer.analyze(db, e, importer.read_table(path, name))
    except importer.ImportFileError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc))
    log = ImportLog(event_id=e.id, uploaded_by=admin.id, filename=name[:255], stored_path=stored,
                    status=ImportStatus.preview)
    db.add(log)
    s = importer.summary(log, rows)
    log.total_rows, log.error_rows = s["total"], s["errors"]
    log.matched_rows, log.created_rows = s["ok"], s["new"]
    log.errors = [{"row": r["row"], "message": r["message"]} for r in rows if r["status"] == "error"]
    db.commit()
    s["id"] = log.id
    return s


def _log(db: Session, import_id: int) -> tuple[ImportLog, Event]:
    log = db.get(ImportLog, import_id)
    if not log:
        raise HTTPException(404, "Импорт не найден")
    return log, db.get(Event, log.event_id)


def _reanalyze(db: Session, log: ImportLog, e: Event) -> list[dict]:
    path = Path(settings.data_dir) / log.stored_path
    if not path.exists():
        raise HTTPException(410, "Исходный файл удалён, загрузите список заново")
    return importer.analyze(db, e, importer.read_table(path, log.filename))


@router.get("/imports/{import_id}")
def get_import(import_id: int, db: Session = Depends(get_db)):
    log, e = _log(db, import_id)
    return importer.summary(log, _reanalyze(db, log, e))


@router.post("/imports/{import_id}/commit")
def commit_import(import_id: int, data: CommitIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    log, e = _log(db, import_id)
    if log.status == ImportStatus.committed:
        raise HTTPException(409, "Этот импорт уже применён")
    rows = _reanalyze(db, log, e)
    result = importer.commit(db, log, e, rows, data.choices)
    audit(db, admin, "import.commit", "event", e.id, registered=result["registered"])
    db.commit()
    return result


@router.get("/events/{event_id}/imports")
def list_imports(event_id: int, db: Session = Depends(get_db)):
    logs = db.scalars(select(ImportLog).where(ImportLog.event_id == event_id).order_by(ImportLog.created_at.desc())).all()
    return [{"id": l.id, "filename": l.filename, "status": l.status.value, "total": l.total_rows,
             "matched": l.matched_rows, "created": l.created_rows, "errors": l.error_rows,
             "created_at": l.created_at.isoformat()} for l in logs]


# ---------- Результаты ----------

@router.put("/events/{event_id}/results")
def put_results(event_id: int, data: ResultsIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    e = _event(db, event_id)
    saved = 0
    for item in data.items:
        if (item.registration_id is None) == (item.team_id is None):
            raise HTTPException(422, "Укажите ровно одно: registration_id или team_id")
        if item.registration_id:
            reg = db.get(Registration, item.registration_id)
            if not reg or reg.event_id != e.id or reg.team_id:
                raise HTTPException(422, f"Запись {item.registration_id} не найдена в этом индивидуальном мероприятии")
            res = db.scalar(select(Result).where(Result.registration_id == reg.id))
            if not res:
                res = Result(event_id=e.id, registration_id=reg.id)
                db.add(res)
            regs = [reg]
        else:
            team = db.get(Team, item.team_id)
            if not team or team.event_id != e.id:
                raise HTTPException(422, f"Команда {item.team_id} не найдена в этом мероприятии")
            res = db.scalar(select(Result).where(Result.team_id == team.id))
            if not res:
                res = Result(event_id=e.id, team_id=team.id)
                db.add(res)
            regs = db.scalars(select(Registration).where(Registration.team_id == team.id)).all()
        res.place, res.status, res.entered_by = item.place, item.status, admin.id
        res.score = item.score
        for r in regs:  # статус участия копируется в записи (для команды — всем участникам)
            r.status = item.status
        saved += 1
    audit(db, admin, "results.save", "event", e.id, count=saved)
    db.commit()
    return {"saved": saved}


# ---------- Дипломы ----------

@router.get("/events/{event_id}/diplomas")
def event_diplomas(event_id: int, db: Session = Depends(get_db)):
    rows = db.execute(select(Diploma, User, Result).join(User, User.id == Diploma.user_id)
                      .join(Result, Result.id == Diploma.result_id)
                      .where(Diploma.event_id == event_id).order_by(User.last_name)).all()
    return [{"id": d.id, "number": d.number, "holder": u.full_name, "class": u.class_name,
             "result": place_text(r) or STATUS_RU[r.status.value], "issued_at": d.issued_at.isoformat(),
             "revoked": bool(d.revoked_at)} for d, u, r in rows]


@router.post("/events/{event_id}/diplomas", status_code=201)
def generate_diplomas(event_id: int, data: DiplomaGenIn, admin: User = Depends(require_admin),
                      db: Session = Depends(get_db)):
    e = _event(db, event_id)
    out = diploma_pdf.issue_for_event(db, e, admin, data.include_participants)
    if out["issued"] == 0 and out["skipped"] == 0:
        raise HTTPException(400, "Нет результатов со статусом «призёр» или «победитель». Сначала внесите результаты.")
    audit(db, admin, "diploma.issue", "event", e.id, **out)
    db.commit()
    return out


@router.post("/diplomas/{diploma_id}/revoke")
def revoke_diploma(diploma_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    d = db.get(Diploma, diploma_id)
    if not d:
        raise HTTPException(404, "Диплом не найден")
    d.revoked_at = func.now()
    audit(db, admin, "diploma.revoke", "diploma", d.id, number=d.number)
    db.commit()
    return {"message": "Диплом отозван. Чтобы выдать новый, нажмите «Сгенерировать дипломы»."}


@router.get("/template")
def get_template(db: Session = Depends(get_db)):
    return {"html": diploma_pdf.ensure_default_template(db).html}


@router.put("/template")
def put_template(data: TemplateIn, db: Session = Depends(get_db)):
    sample = {"full_name": "Иванов Иван Иванович", "event_title": "Пример", "subject": "Математика",
              "level": "Школьный", "result_label": "Победитель", "place_text": "За 1 место", "place": 1,
              "score": 90.0, "date": "1 сентября 2026 г.", "number": "SC-2026-TEST00", "qr": "",
              "school": "Школа", "verify_url": "http://example", "team_name": None}
    try:
        diploma_pdf.render_pdf(data.html, sample)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Ошибка в шаблоне: {exc}")
    tpl = diploma_pdf.ensure_default_template(db)
    tpl.html = data.html
    db.commit()
    return {"message": "Шаблон сохранён. Он применяется к новым дипломам."}


# ---------- Отчёты ----------

@router.get("/reports/{kind}")
def report(kind: str, format: str = "xlsx", grade: int | None = None, event_id: int | None = None,
           date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db)):
    if kind not in reports.KINDS:
        raise HTTPException(404, "Неизвестный вид отчёта")
    if format not in ("xlsx", "csv", "pdf"):
        raise HTTPException(400, "Формат: xlsx, csv или pdf")
    title, headers, rows = reports.build(db, kind, grade, event_id, date_from, date_to)
    media = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "csv": "text/csv; charset=utf-8", "pdf": "application/pdf"}[format]
    content = {"xlsx": lambda: reports.to_xlsx(title, headers, rows),
               "csv": lambda: reports.to_csv(headers, rows),
               "pdf": lambda: reports.to_pdf(title, headers, rows)}[format]()
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="report-{kind}-{date.today()}.{format}"'})


# ---------- Пользователи ----------

@router.get("/users")
def list_users(q: str | None = None, role: UserRole | None = None, grade: int | None = None,
               db: Session = Depends(get_db)):
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.last_name.ilike(like), User.first_name.ilike(like), User.email.ilike(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if grade:
        stmt = stmt.where(User.grade == grade)
    users = db.scalars(stmt.order_by(User.last_name, User.first_name).limit(300)).all()
    return [user_out(u) for u in users]


@router.patch("/users/{user_id}")
def patch_user(user_id: int, data: UserPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Пользователь не найден")
    if u.id == admin.id and (data.role == UserRole.student or data.is_active is False):
        raise HTTPException(400, "Нельзя понизить или заблокировать самого себя")
    if data.role is not None:
        u.role = data.role
    if data.is_active is not None:
        u.is_active = data.is_active
    audit(db, admin, "user.update", "user", u.id, role=u.role.value, is_active=u.is_active)
    db.commit()
    return user_out(u)
