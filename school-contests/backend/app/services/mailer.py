"""Отправка писем через SMTP (в прототипе — Mailpit, веб-интерфейс на :8025)."""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger(__name__)


def send_mail(to: str, subject: str, text: str) -> None:
    """Ошибки отправки не прерывают запрос: пишем их в лог."""
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось отправить письмо на %s: %s", to, exc)


def send_verification(to: str, name: str, token: str) -> None:
    link = f"{settings.public_base_url}/verify-email?token={token}"
    send_mail(to, "Подтверждение email",
              f"Здравствуйте, {name}!\n\nПодтвердите адрес почты, перейдя по ссылке:\n{link}\n\n"
              "Ссылка действует 24 часа. Если вы не регистрировались, просто проигнорируйте письмо.")


def send_reset(to: str, name: str, token: str, invite: bool = False) -> None:
    link = f"{settings.public_base_url}/reset-password?token={token}"
    if invite:
        subject = "Приглашение на платформу школьных конкурсов"
        intro = "Для вас создан личный кабинет. Задайте пароль по ссылке:"
    else:
        subject = "Восстановление пароля"
        intro = "Чтобы задать новый пароль, перейдите по ссылке:"
    send_mail(to, subject, f"Здравствуйте, {name}!\n\n{intro}\n{link}\n\nСсылка действует 2 часа.")
