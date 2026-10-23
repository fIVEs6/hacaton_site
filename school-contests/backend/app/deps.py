"""Общие зависимости FastAPI: текущий пользователь, проверка ролей, CSRF."""
import hmac
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import AuditLog, User, UserRole

# Эти эндпоинты вызываются до входа, CSRF-токена у клиента ещё может не быть
CSRF_EXEMPT = {
    "/api/auth/login", "/api/auth/register", "/api/auth/verify-email",
    "/api/auth/resend-verification", "/api/auth/forgot-password", "/api/auth/reset-password",
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_protect(request: Request) -> None:
    """Double-submit cookie: заголовок X-CSRF-Token должен совпасть с cookie csrf_token."""
    if request.method in SAFE_METHODS or request.url.path in CSRF_EXEMPT:
        return
    if not request.cookies.get("access_token"):
        return  # без авторизации менять нечего — эндпоинт всё равно вернёт 401
    cookie = request.cookies.get("csrf_token", "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, "Недействительный CSRF-токен. Обновите страницу.")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    user_id = decode_access_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(401, "Требуется вход в систему")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(403, "Недостаточно прав")
    return user


def audit(db: Session, actor: User | None, action: str, entity: str, entity_id: int | None = None, **details) -> None:
    db.add(AuditLog(actor_id=actor.id if actor else None, action=action, entity=entity,
                    entity_id=entity_id, details=details))


def random_code(length: int = 6) -> str:
    """Код без похожих символов (0/O, 1/I)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))
