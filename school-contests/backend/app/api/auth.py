"""Регистрация, вход, подтверждение email, восстановление пароля."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (check_password_strength, create_access_token, hash_password,
                               hash_token, new_csrf_token, new_token, verify_password)
from app.db import get_db
from app.deps import get_current_user
from app.models import EmailToken, TokenKind, User, UserRole
from app.schemas import EmailIn, LoginIn, RegisterIn, ResetIn, TokenIn, user_out
from app.services import mailer

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED = 5
LOCK_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(db: Session, user: User, kind: TokenKind, hours: int) -> str:
    """Создаёт одноразовый токен, в БД сохраняется только его хеш."""
    raw, digest = new_token()
    db.add(EmailToken(user_id=user.id, kind=kind, token_hash=digest, expires_at=_now() + timedelta(hours=hours)))
    return raw


def _consume_token(db: Session, raw: str, kind: TokenKind) -> User:
    tok = db.scalar(select(EmailToken).where(EmailToken.token_hash == hash_token(raw), EmailToken.kind == kind))
    if not tok or tok.used_at or tok.expires_at < _now():
        raise HTTPException(400, "Ссылка недействительна или устарела")
    tok.used_at = _now()
    user = db.get(User, tok.user_id)
    if not user:
        raise HTTPException(400, "Ссылка недействительна или устарела")
    return user


def _set_cookies(response: Response, user_id: int) -> None:
    max_age = settings.access_token_minutes * 60
    response.set_cookie("access_token", create_access_token(user_id), max_age=max_age, httponly=True,
                        samesite="lax", secure=settings.cookie_secure, path="/")
    # Читается из JavaScript и возвращается заголовком X-CSRF-Token
    response.set_cookie("csrf_token", new_csrf_token(), max_age=max_age, httponly=False,
                        samesite="lax", secure=settings.cookie_secure, path="/")


@router.post("/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if settings.require_consent and not data.consent:
        raise HTTPException(422, "Необходимо согласие на обработку персональных данных")
    err = check_password_strength(data.password)
    if err:
        raise HTTPException(422, err)
    if db.scalar(select(User.id).where(func.lower(User.email) == data.email)):
        raise HTTPException(409, "Пользователь с таким email уже зарегистрирован")
    user = User(email=data.email, password_hash=hash_password(data.password), role=UserRole.student,
                last_name=data.last_name, first_name=data.first_name, middle_name=data.middle_name,
                grade=data.grade, class_letter=(data.class_letter or "").upper() or None,
                school=data.school or settings.school_name,
                consent_at=_now() if data.consent else None)
    db.add(user)
    db.flush()
    raw = issue_token(db, user, TokenKind.verify_email, 24)
    db.commit()
    mailer.send_verification(user.email, user.first_name, raw)
    return {"message": "Письмо с подтверждением отправлено на вашу почту"}


@router.post("/verify-email")
def verify_email(data: TokenIn, db: Session = Depends(get_db)):
    user = _consume_token(db, data.token, TokenKind.verify_email)
    user.email_verified = True
    db.commit()
    return {"message": "Email подтверждён. Теперь можно войти."}


@router.post("/resend-verification")
def resend_verification(data: EmailIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email))
    if user and not user.email_verified and user.is_active:
        raw = issue_token(db, user, TokenKind.verify_email, 24)
        db.commit()
        mailer.send_verification(user.email, user.first_name, raw)
    return {"message": "Если адрес зарегистрирован, письмо отправлено"}


@router.post("/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email))
    if user and user.locked_until and user.locked_until > _now():
        raise HTTPException(429, "Слишком много попыток входа. Повторите через несколько минут.")
    if not user or not verify_password(data.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED:
                user.locked_until = _now() + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            db.commit()
        raise HTTPException(401, "Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(403, "Учётная запись отключена")
    if not user.email_verified:
        raise HTTPException(403, "Подтвердите email: проверьте почту и перейдите по ссылке из письма")
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    _set_cookies(response, user.id)
    return user_out(user)


@router.post("/logout")
def logout(response: Response, _: User = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Вы вышли из системы"}


@router.post("/forgot-password")
def forgot_password(data: EmailIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email))
    if user and user.is_active:
        raw = issue_token(db, user, TokenKind.reset_password, 2)
        db.commit()
        mailer.send_reset(user.email, user.first_name, raw)
    # Ответ одинаковый всегда, чтобы нельзя было узнать, есть ли такой email
    return {"message": "Если адрес зарегистрирован, на него отправлена ссылка для сброса пароля"}


@router.post("/reset-password")
def reset_password(data: ResetIn, db: Session = Depends(get_db)):
    err = check_password_strength(data.password)
    if err:
        raise HTTPException(422, err)
    user = _consume_token(db, data.token, TokenKind.reset_password)
    user.password_hash = hash_password(data.password)
    user.email_verified = True       # письмо дошло — адрес подтверждён
    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    return {"message": "Пароль изменён. Теперь можно войти."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
