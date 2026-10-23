"""Генерация дипломов: HTML-шаблон (Jinja2) → PDF (WeasyPrint), QR-код для проверки."""
import base64
import io
import secrets
from datetime import date, datetime, timezone
from pathlib import Path

import qrcode
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.core.config import settings
from app.models import (LEVEL_RU, STATUS_RU, Diploma, DiplomaTemplate, Event, PStatus, Registration, Result, Team, User)

TEMPLATE_FILE = Path(__file__).resolve().parents[1] / "templates" / "diploma.html"
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]
# Шаблон редактирует администратор, поэтому рендерим в «песочнице» с автоэкранированием
_env = SandboxedEnvironment(autoescape=True)


def ru_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year} г."


def ensure_default_template(db: Session) -> DiplomaTemplate:
    tpl = db.scalar(select(DiplomaTemplate).where(DiplomaTemplate.is_default))
    if not tpl:
        tpl = DiplomaTemplate(name="Школьная грамота", html=TEMPLATE_FILE.read_text(encoding="utf-8"), is_default=True)
        db.add(tpl)
        db.commit()
    return tpl


def new_number(db: Session) -> str:
    """Случайный непоследовательный номер, например SC-2026-7K3F9Q."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        number = f"SC-{datetime.now().year}-" + "".join(secrets.choice(alphabet) for _ in range(6))
        if not db.scalar(select(Diploma.id).where(Diploma.number == number)):
            return number


def qr_data_uri(url: str) -> str:
    img = qrcode.make(url, box_size=8, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def render_pdf(template_html: str, ctx: dict) -> bytes:
    html = _env.from_string(template_html).render(**ctx)
    return HTML(string=html).write_pdf()


def _place_text(result: Result) -> str:
    if result.place and result.status in (PStatus.winner, PStatus.prizewinner):
        return f"за {result.place} место"
    return {"winner": "за победу", "prizewinner": "за призовое место",
            "participated": "за участие"}.get(result.status.value, "за участие")


def _issue_one(db: Session, template: DiplomaTemplate, event: Event, result: Result, user: User,
               team: Team | None, admin: User | None, existing: Diploma | None) -> Diploma:
    number = new_number(db)
    verify_url = f"{settings.public_base_url}/verify/{number}"
    ctx = {
        "full_name": user.full_name, "event_title": event.title, "subject": event.subject,
        "level": LEVEL_RU[event.level.value], "result_label": STATUS_RU[result.status.value],
        "place_text": _place_text(result).capitalize(), "place": result.place,
        "score": float(result.score) if result.score is not None else None,
        "date": ru_date(event.end_date), "number": number, "qr": qr_data_uri(verify_url),
        "school": user.school or settings.school_name, "verify_url": verify_url,
        "team_name": team.name if team else None,
    }
    pdf = render_pdf(template.html, ctx)
    rel = f"diplomas/{number}.pdf"
    path = Path(settings.data_dir) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf)
    if existing:  # перевыпуск после отзыва: старую запись обновляем, старый файл удаляем
        (Path(settings.data_dir) / existing.pdf_path).unlink(missing_ok=True)
        existing.number, existing.pdf_path, existing.result_id = number, rel, result.id
        existing.template_id, existing.issued_by = template.id, admin.id if admin else None
        existing.revoked_at, existing.issued_at = None, datetime.now(timezone.utc)
        return existing
    d = Diploma(number=number, event_id=event.id, user_id=user.id, result_id=result.id, template_id=template.id,
                pdf_path=rel, issued_by=admin.id if admin else None)
    db.add(d)
    return d


def issue_for_event(db: Session, event: Event, admin: User | None, include_participants: bool = False) -> dict:
    """Массовая выдача: по всем результатам мероприятия, для которых диплома ещё нет."""
    template = ensure_default_template(db)
    wanted = [PStatus.winner, PStatus.prizewinner] + ([PStatus.participated] if include_participants else [])
    results = db.scalars(select(Result).where(Result.event_id == event.id, Result.status.in_(wanted))).all()
    issued = skipped = 0
    for res in results:
        if res.team_id:
            team = db.get(Team, res.team_id)
            regs = db.scalars(select(Registration).where(Registration.team_id == res.team_id)).all()
        else:
            team = None
            regs = [db.get(Registration, res.registration_id)]
        for reg in regs:
            existing = db.scalar(select(Diploma).where(Diploma.event_id == event.id, Diploma.user_id == reg.user_id))
            if existing and not existing.revoked_at:
                skipped += 1
                continue
            _issue_one(db, template, event, res, reg.user, team, admin, existing)
            issued += 1
        db.flush()
    db.commit()
    return {"issued": issued, "skipped": skipped}
