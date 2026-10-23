"""Импорт списков участников из CSV/XLSX: разбор, валидация, сопоставление с учениками, применение."""
import csv
import io
import re
import secrets
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (Event, ImportLog, ImportStatus, ParticipationType, Registration, Team, TokenKind, User, UserRole)
from app.deps import random_code

MAX_ROWS = 2000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CLASS_RE = re.compile(r"^\s*(\d{1,2})\s*[-\s]?\s*([A-Za-zА-Яа-яЁё])?\s*(?:кл(?:асс)?\.?)?\s*$", re.IGNORECASE)

# Допустимые названия колонок (в нижнем регистре)
HEADER_ALIASES = {
    "fio": {"фио", "ф.и.о.", "ф.и.о", "ученик", "фамилия имя отчество", "фамилия, имя, отчество"},
    "last": {"фамилия"},
    "first": {"имя"},
    "middle": {"отчество"},
    "class": {"класс", "кл.", "кл"},
    "email": {"email", "e-mail", "почта", "электронная почта", "эл. почта"},
    "team": {"команда", "название команды"},
}


class ImportFileError(Exception):
    """Файл невозможно прочитать или в нём нет нужных колонок."""


def _norm(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е")


def read_table(path: Path, filename: str) -> list[dict]:
    """Возвращает строки как словари {поле: значение}; поле '_row' — номер строки в файле."""
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "xlsx":
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
            raw_rows = [list(r) for r in wb.active.iter_rows(values_only=True)]
        except Exception as exc:  # noqa: BLE001
            raise ImportFileError("Не удалось прочитать XLSX-файл") from exc
    elif ext == "csv":
        data = path.read_bytes()
        for enc in ("utf-8-sig", "cp1251"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ImportFileError("Не удалось определить кодировку CSV (нужна UTF-8 или Windows-1251)")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"
        raw_rows = list(csv.reader(io.StringIO(text), dialect))
    else:
        raise ImportFileError("Поддерживаются только файлы CSV и XLSX")

    raw_rows = [r for r in raw_rows if any(str(c).strip() for c in r if c is not None)]
    if not raw_rows:
        raise ImportFileError("Файл пустой")
    if len(raw_rows) - 1 > MAX_ROWS:
        raise ImportFileError(f"Слишком много строк (максимум {MAX_ROWS})")

    # Сопоставляем заголовки с полями
    header = [_norm(str(c)) if c is not None else "" for c in raw_rows[0]]
    cols: dict[str, int] = {}
    for idx, h in enumerate(header):
        for field, names in HEADER_ALIASES.items():
            if h in names and field not in cols:
                cols[field] = idx
    if "fio" not in cols and not ("last" in cols and "first" in cols):
        raise ImportFileError("Не найдена колонка «ФИО» (или «Фамилия» и «Имя»)")
    if "class" not in cols:
        raise ImportFileError("Не найдена колонка «Класс»")

    rows = []
    for n, r in enumerate(raw_rows[1:], start=2):  # номер строки как в Excel (заголовок — строка 1)
        item = {"_row": n}
        for field, idx in cols.items():
            val = r[idx] if idx < len(r) else None
            if isinstance(val, float) and val.is_integer():
                val = int(val)  # Excel часто отдаёт 9.0 вместо 9
            item[field] = str(val).strip() if val is not None else ""
        rows.append(item)
    return rows


def _split_name(item: dict) -> tuple[str, str, str]:
    if item.get("fio"):
        parts = item["fio"].split()
        return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "", " ".join(parts[2:]))
    return item.get("last", ""), item.get("first", ""), item.get("middle", "")


def parse_class(value: str) -> tuple[int, str | None] | None:
    m = CLASS_RE.match(value or "")
    if not m:
        return None
    grade = int(m.group(1))
    if not 1 <= grade <= 11:
        return None
    return grade, (m.group(2).upper() if m.group(2) else None)


def analyze(db: Session, event: Event, rows: list[dict]) -> list[dict]:
    """Проверяет каждую строку и ищет ученика в системе. Статусы: ok, new, ambiguous, error."""
    out = []
    seen_users: set[int] = set()
    seen_emails: set[str] = set()
    is_team = event.participation_type == ParticipationType.team
    for item in rows:
        last, first, middle = _split_name(item)
        res = {"row": item["_row"], "name": " ".join(p for p in (last, first, middle) if p),
               "class": item.get("class", ""), "email": item.get("email", "").lower(),
               "team": item.get("team", ""), "status": "error", "message": "", "user_id": None}
        if not last or not first:
            res["message"] = "Укажите фамилию и имя"
            out.append(res)
            continue
        cls = parse_class(item.get("class", ""))
        if not cls:
            res["message"] = "Некорректный класс (пример: 8Б)" if item.get("class") else "Не указан класс"
            out.append(res)
            continue
        grade, letter = cls
        res["grade"], res["letter"] = grade, letter
        if res["email"] and not EMAIL_RE.match(res["email"]):
            res["message"] = "Некорректный email"
            out.append(res)
            continue
        if is_team and not res["team"]:
            res["message"] = "Для командного конкурса укажите команду"
            out.append(res)
            continue

        user = None
        if res["email"]:
            user = db.scalar(select(User).where(func.lower(User.email) == res["email"]))
        candidates: list[User] = []
        if not user:
            candidates = [u for u in db.scalars(select(User).where(
                User.role == UserRole.student, User.grade == grade,
                func.lower(User.last_name) == last.lower(), func.lower(User.first_name) == first.lower()))
                if _norm(u.last_name) == _norm(last) and _norm(u.first_name) == _norm(first)]
            if len(candidates) > 1 and middle:
                narrowed = [u for u in candidates if _norm(u.middle_name or "") == _norm(middle)]
                candidates = narrowed or candidates
            if len(candidates) > 1 and letter:
                narrowed = [u for u in candidates if (u.class_letter or "").upper() == letter]
                candidates = narrowed or candidates
            if len(candidates) == 1:
                user = candidates[0]

        if user:
            if user.id in seen_users:
                res.update(status="error", message="Ученик уже встречается в файле выше")
            else:
                seen_users.add(user.id)
                already = db.scalar(select(Registration.id).where(
                    Registration.event_id == event.id, Registration.user_id == user.id))
                res.update(status="ok", user_id=user.id, already=bool(already),
                           message="Уже записан на мероприятие" if already else "Найден в системе")
        elif len(candidates) > 1:
            res.update(status="ambiguous", message="Найдено несколько учеников — выберите нужного",
                       candidates=[{"id": u.id, "name": u.full_name, "class": u.class_name, "email": u.email}
                                   for u in candidates])
        elif res["email"]:
            if res["email"] in seen_emails:
                res.update(status="error", message="Этот email уже встречается в файле выше")
            else:
                seen_emails.add(res["email"])
                res.update(status="new", message="Не найден: будет создана учётная запись и отправлено приглашение")
        else:
            res["message"] = "Ученик не найден в системе. Укажите email, чтобы создать учётную запись"
        out.append(res)
    return out


def summary(log: ImportLog, rows: list[dict]) -> dict:
    count = lambda s: sum(1 for r in rows if r["status"] == s)  # noqa: E731
    return {"id": log.id, "event_id": log.event_id, "filename": log.filename, "status": log.status.value,
            "total": len(rows), "ok": count("ok"), "new": count("new"),
            "ambiguous": count("ambiguous"), "errors": count("error"), "rows": rows}


def commit(db: Session, log: ImportLog, event: Event, rows: list[dict], choices: dict[str, int]) -> dict:
    """Применяет проверенный импорт: создаёт новых учеников, записи и команды."""
    from app.api.auth import issue_token          # локальный импорт, чтобы не было циклов
    from app.services import mailer

    is_team = event.participation_type == ParticipationType.team
    matched = created = skipped = 0
    errors: list[dict] = []
    teams: dict[str, Team] = {}
    invites: list[tuple[User, str]] = []

    for r in rows:
        user: User | None = None
        if r["status"] == "ok":
            user = db.get(User, r["user_id"])
            if r.get("already"):
                skipped += 1
                continue
            matched += 1
        elif r["status"] == "ambiguous":
            chosen = choices.get(str(r["row"]))
            if chosen and chosen in {c["id"] for c in r["candidates"]}:
                user = db.get(User, chosen)
                matched += 1
                if db.scalar(select(Registration.id).where(Registration.event_id == event.id,
                                                           Registration.user_id == user.id)):
                    skipped += 1
                    continue
            else:
                errors.append({"row": r["row"], "message": "Ученик не выбран, строка пропущена"})
                continue
        elif r["status"] == "new":
            parts = r["name"].split()
            user = User(email=r["email"], password_hash=hash_password(secrets.token_urlsafe(24)),
                        role=UserRole.student, last_name=parts[0], first_name=parts[1],
                        middle_name=" ".join(parts[2:]) or None, grade=r["grade"], class_letter=r["letter"],
                        school=None, email_verified=False)
            db.add(user)
            db.flush()
            invites.append((user, issue_token(db, user, TokenKind.reset_password, 48)))
            created += 1
        else:
            errors.append({"row": r["row"], "message": r["message"]})
            continue

        team = None
        if is_team:
            key = r["team"].strip().lower()
            team = teams.get(key) or db.scalar(select(Team).where(
                Team.event_id == event.id, func.lower(Team.name) == key))
            if not team:
                team = Team(event_id=event.id, name=r["team"].strip(), join_code=random_code(6), captain_id=user.id)
                db.add(team)
                db.flush()
            teams[key] = team
        db.add(Registration(event_id=event.id, user_id=user.id, team_id=team.id if team else None, source="import"))
        db.flush()

    log.status = ImportStatus.committed
    log.total_rows = len(rows)
    log.matched_rows = matched
    log.created_rows = created
    log.error_rows = len(errors)
    log.errors = errors
    log.committed_at = func.now()
    db.commit()
    # Письма уходят только после успешного сохранения
    for user, raw in invites:
        mailer.send_reset(user.email, user.first_name, raw, invite=True)
    return {"registered": matched + created, "created_users": created, "skipped_existing": skipped,
            "errors": errors}
