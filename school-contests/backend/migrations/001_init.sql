-- school-contests/backend/migrations/001_init.sql
-- Начальная схема БД платформы школьных конкурсов (PostgreSQL 16)

BEGIN;

-- ===== Типы-перечисления =====
CREATE TYPE user_role AS ENUM ('student', 'admin');
CREATE TYPE event_status AS ENUM ('draft', 'published', 'finished');
CREATE TYPE event_level AS ENUM ('school', 'municipal', 'regional', 'federal', 'international');
CREATE TYPE participation_type AS ENUM ('individual', 'team');
-- Статус участия: записан / участвовал / призёр / победитель
CREATE TYPE participation_status AS ENUM ('registered', 'participated', 'prizewinner', 'winner');
CREATE TYPE email_token_kind AS ENUM ('verify_email', 'reset_password');
CREATE TYPE import_status AS ENUM ('preview', 'committed', 'failed');

-- ===== Пользователи =====
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,          -- argon2
    role            user_role NOT NULL DEFAULT 'student',
    last_name       VARCHAR(100) NOT NULL,
    first_name      VARCHAR(100) NOT NULL,
    middle_name     VARCHAR(100),
    grade           SMALLINT CHECK (grade BETWEEN 1 AND 11),   -- параллель: 5..11
    class_letter    VARCHAR(2),                                 -- буква класса: А, Б...
    school          VARCHAR(255),
    photo_path      VARCHAR(500),                   -- необязательное фото
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    consent_at      TIMESTAMPTZ,                    -- согласие на обработку ПДн (152-ФЗ)
    failed_logins   SMALLINT NOT NULL DEFAULT 0,    -- защита от перебора пароля
    locked_until    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Email уникален без учёта регистра
CREATE UNIQUE INDEX ux_users_email ON users (lower(email));
-- Поиск ученика при сопоставлении импорта (ФИО + класс)
CREATE INDEX ix_users_fio ON users (lower(last_name), lower(first_name), grade);

-- ===== Одноразовые токены (подтверждение email, сброс пароля) =====
CREATE TABLE email_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        email_token_kind NOT NULL,
    token_hash  CHAR(64) NOT NULL UNIQUE,           -- SHA-256 токена; сам токен в БД не хранится
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_email_tokens_user ON email_tokens (user_id, kind);

-- ===== Мероприятия (конкурсы) =====
CREATE TABLE events (
    id                  BIGSERIAL PRIMARY KEY,
    title               VARCHAR(255) NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    rules               TEXT NOT NULL DEFAULT '',
    subject             VARCHAR(100) NOT NULL,          -- предмет
    level               event_level NOT NULL DEFAULT 'school',
    participation_type  participation_type NOT NULL DEFAULT 'individual',
    team_min_size       SMALLINT,                       -- только для командных
    team_max_size       SMALLINT,
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    status              event_status NOT NULL DEFAULT 'draft',
    created_by          BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_events_dates CHECK (end_date >= start_date),
    CONSTRAINT ck_events_team_size CHECK (
        (participation_type = 'individual' AND team_min_size IS NULL AND team_max_size IS NULL)
        OR (participation_type = 'team' AND team_min_size >= 2 AND team_max_size >= team_min_size)
    )
);
CREATE INDEX ix_events_filters ON events (status, subject, start_date);

-- ===== Команды (для командных конкурсов) =====
CREATE TABLE teams (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name        VARCHAR(150) NOT NULL,
    join_code   VARCHAR(12) NOT NULL UNIQUE,            -- код для вступления
    captain_id  BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, name)
);

-- ===== Записи на участие =====
-- Одна запись = один ученик в одном мероприятии (для команд team_id заполнен)
CREATE TABLE registrations (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    team_id     BIGINT REFERENCES teams(id) ON DELETE SET NULL,
    status      participation_status NOT NULL DEFAULT 'registered',
    source      VARCHAR(20) NOT NULL DEFAULT 'self',    -- self | import
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, user_id)                          -- нельзя записаться дважды
);
CREATE INDEX ix_registrations_user ON registrations (user_id);
CREATE INDEX ix_registrations_team ON registrations (team_id);

-- ===== Результаты =====
-- Индивидуальный конкурс: результат по записи (registration_id).
-- Командный конкурс: результат по команде (team_id), статус копируется в записи участников.
CREATE TABLE results (
    id               BIGSERIAL PRIMARY KEY,
    event_id         BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    registration_id  BIGINT REFERENCES registrations(id) ON DELETE CASCADE,
    team_id          BIGINT REFERENCES teams(id) ON DELETE CASCADE,
    place            SMALLINT CHECK (place >= 1),
    score            NUMERIC(7,2) CHECK (score >= 0),
    status           participation_status NOT NULL,
    entered_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- ровно одно из двух: участник или команда
    CONSTRAINT ck_results_subject CHECK ((registration_id IS NULL) <> (team_id IS NULL))
);
CREATE UNIQUE INDEX ux_results_registration ON results (registration_id) WHERE registration_id IS NOT NULL;
CREATE UNIQUE INDEX ux_results_team ON results (team_id) WHERE team_id IS NOT NULL;
CREATE INDEX ix_results_event ON results (event_id);

-- ===== Шаблоны дипломов =====
CREATE TABLE diploma_templates (
    id            BIGSERIAL PRIMARY KEY,
    name          VARCHAR(150) NOT NULL,
    html          TEXT NOT NULL,                        -- HTML/CSS-шаблон для WeasyPrint
    is_default    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Шаблон по умолчанию может быть только один
CREATE UNIQUE INDEX ux_templates_default ON diploma_templates (is_default) WHERE is_default;

-- ===== Дипломы =====
CREATE TABLE diplomas (
    id            BIGSERIAL PRIMARY KEY,
    number        VARCHAR(20) NOT NULL UNIQUE,          -- формат SC-2026-7K3F9Q, случайный
    event_id      BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    result_id     BIGINT NOT NULL REFERENCES results(id) ON DELETE CASCADE,
    template_id   BIGINT REFERENCES diploma_templates(id) ON DELETE SET NULL,
    pdf_path      VARCHAR(500) NOT NULL,
    issued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    issued_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
    revoked_at    TIMESTAMPTZ,                          -- отозванный диплом не проходит проверку
    UNIQUE (event_id, user_id)                          -- один диплом на ученика за мероприятие
);
CREATE INDEX ix_diplomas_user ON diplomas (user_id);

-- ===== Журнал импорта участников =====
CREATE TABLE import_logs (
    id             BIGSERIAL PRIMARY KEY,
    event_id       BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    uploaded_by    BIGINT REFERENCES users(id) ON DELETE SET NULL,
    filename       VARCHAR(255) NOT NULL,
    stored_path    VARCHAR(500) NOT NULL,               -- имя на диске — UUID
    status         import_status NOT NULL DEFAULT 'preview',
    total_rows     INTEGER NOT NULL DEFAULT 0,
    matched_rows   INTEGER NOT NULL DEFAULT 0,          -- сопоставлены с существующими учениками
    created_rows   INTEGER NOT NULL DEFAULT 0,          -- созданы новые учётные записи
    error_rows     INTEGER NOT NULL DEFAULT 0,
    errors         JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{row, field, message}]
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    committed_at   TIMESTAMPTZ
);
CREATE INDEX ix_import_logs_event ON import_logs (event_id);

-- ===== Журнал действий администраторов =====
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(60) NOT NULL,                   -- например: result.update, diploma.issue
    entity      VARCHAR(40) NOT NULL,
    entity_id   BIGINT,
    details     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_created ON audit_log (created_at DESC);

COMMIT;
