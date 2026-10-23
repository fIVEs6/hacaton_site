"""Настройки приложения. Значения берутся из переменных окружения (.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://contests:contests@db:5432/contests"
    secret_key: str = "change-me-in-production"
    access_token_minutes: int = 60 * 8
    cookie_secure: bool = False          # в продакшене за HTTPS — True

    # Адрес, на который ведёт QR-код диплома, и ссылки в письмах
    public_base_url: str = "http://localhost:8080"

    # Почта (в прототипе — Mailpit)
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    mail_from: str = "Школьные конкурсы <no-reply@school.local>"

    # Согласие на обработку ПДн (152-ФЗ): включить обязательный чекбокс при регистрации
    require_consent: bool = False

    school_name: str = "Школа №1"
    data_dir: str = "/data"              # фото, PDF дипломов, загруженные файлы импорта
    max_upload_mb: int = 5

    seed_on_start: bool = True           # заполнить демо-данными, если БД пуста
    admin_email: str = "admin@school.local"
    admin_password: str = "Admin12345"


settings = Settings()
