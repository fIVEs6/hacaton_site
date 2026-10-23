# Спецификация REST API

Базовый префикс: `/api`. Формат: JSON (кроме загрузки файлов и скачивания). Интерактивная документация: `/api/docs` (Swagger).

## Аутентификация и CSRF

- После входа сервер ставит две cookie:
  - `access_token` — JWT, `HttpOnly`, `SameSite=Lax` (недоступна из JavaScript);
  - `csrf_token` — случайная строка, читается фронтендом.
- Все небезопасные запросы (`POST/PUT/PATCH/DELETE`) с авторизацией обязаны передавать заголовок `X-CSRF-Token` со значением cookie `csrf_token`. Иначе — `403`.
- Права: `public` — без входа, `student` — любой вошедший, `admin` — только администратор.
- Ошибки: `{"detail": "Текст на русском"}` со статусами 400/401/403/404/409/422/429.

## Авторизация — `/api/auth`

| Метод | Путь | Права | Описание |
|---|---|---|---|
| POST | `/auth/register` | public | Регистрация ученика, отправка письма подтверждения |
| POST | `/auth/verify-email` | public | Подтверждение email по токену из письма |
| POST | `/auth/resend-verification` | public | Повторная отправка письма |
| POST | `/auth/login` | public | Вход, установка cookie |
| POST | `/auth/logout` | student | Выход |
| POST | `/auth/forgot-password` | public | Письмо со ссылкой сброса (всегда 200) |
| POST | `/auth/reset-password` | public | Новый пароль по токену |
| GET | `/auth/me` | student | Текущий пользователь |

Пример регистрации:

```http
POST /api/auth/register
{"email":"ivan@example.com","password":"Qwerty123","last_name":"Иванов","first_name":"Иван",
 "middle_name":"Петрович","grade":8,"class_letter":"Б","school":"Школа №1","consent":true}
→ 201 {"message":"Письмо с подтверждением отправлено"}
```

Пример входа:

```http
POST /api/auth/login   {"email":"ivan@example.com","password":"Qwerty123"}
→ 200 {"id":5,"email":"ivan@example.com","role":"student","full_name":"Иванов Иван Петрович",...}
```

После 5 неверных паролей аккаунт блокируется на 15 минут (`429`).

## Профиль — `/api/profile` (student)

| Метод | Путь | Описание |
|---|---|---|
| PATCH | `/profile` | Изменить ФИО, класс, школу |
| POST | `/profile/photo` | Загрузить фото (multipart, jpg/png/webp, до 2 МБ) |
| GET | `/profile/photo` | Получить своё фото |
| DELETE | `/profile/photo` | Удалить фото |

## Мероприятия для ученика (student)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/events` | Лента. Параметры: `subject`, `date_from`, `date_to`, `status` (`upcoming`/`ongoing`/`finished`), `q`. Показывает только опубликованные и завершённые |
| GET | `/events/{id}` | Карточка: описание, правила, моя запись, моя команда |
| POST | `/events/{id}/register` | Записаться (индивидуальный конкурс) |
| DELETE | `/events/{id}/register` | Отменить запись (пока нет результата) |
| POST | `/events/{id}/teams` | Создать команду и записаться: `{"name":"Альфа"}` |
| POST | `/events/{id}/teams/join` | Вступить в команду: `{"code":"K7F3QP"}` |
| GET | `/me/progress` | Мои участия + статистика |
| GET | `/me/diplomas` | Мои дипломы |
| GET | `/diplomas/{id}/pdf` | Скачать PDF (владелец или админ) |

Пример `GET /me/progress`:

```json
{"stats":{"total":4,"participated":1,"prizewinner":1,"winner":1,"registered":1,"total_score":172.5,"diplomas":2},
 "items":[{"event_id":2,"title":"Олимпиада по математике","subject":"Математика","start_date":"2026-10-12",
           "status":"winner","place":1,"score":98.5,"team_name":null,"diploma_id":7}]}
```

## Публичная проверка диплома

| Метод | Путь | Права | Описание |
|---|---|---|---|
| GET | `/verify/{number}` | public | Проверка подлинности по номеру из QR-кода |

```json
{"valid":true,"number":"SC-2026-7K3F9Q","holder":"Иванов И. П.","event":"Олимпиада по математике",
 "place":1,"result":"Победитель","issued_at":"2026-10-20"}
```

Для отозванного или несуществующего диплома: `{"valid":false}`.

## Админ-панель — `/api/admin` (admin)

### Мероприятия

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/events` | Список (все статусы) |
| POST | `/admin/events` | Создать |
| GET | `/admin/events/{id}` | Получить |
| PUT | `/admin/events/{id}` | Изменить |
| DELETE | `/admin/events/{id}` | Удалить (нельзя, если выданы дипломы) |
| GET | `/admin/events/{id}/participants` | Участники (и команды) с результатами |

Тело создания:

```json
{"title":"Олимпиада по физике","description":"...","rules":"...","subject":"Физика","level":"school",
 "participation_type":"individual","team_min_size":null,"team_max_size":null,
 "start_date":"2026-11-10","end_date":"2026-11-10","status":"draft"}
```

### Импорт участников

| Метод | Путь | Описание |
|---|---|---|
| POST | `/admin/events/{id}/imports` | Загрузить CSV/XLSX (multipart `file`), вернуть предпросмотр |
| GET | `/admin/imports/{id}` | Предпросмотр заново |
| POST | `/admin/imports/{id}/commit` | Применить: `{"choices":{"7":42}}` — ручной выбор ученика для неоднозначных строк |
| GET | `/admin/events/{id}/imports` | История импортов |

Колонки файла (заголовки не чувствительны к регистру): `ФИО` (или `Фамилия`, `Имя`, `Отчество`), `Класс` (например `8Б`), `Email` (необязательно), `Команда` (для командных).

Ответ предпросмотра:

```json
{"id":3,"status":"preview","total":20,"ok":15,"new":2,"ambiguous":1,"errors":2,
 "rows":[{"row":2,"status":"ok","name":"Иванов Иван","grade":8,"user_id":5,"message":"Найден в системе"},
         {"row":5,"status":"ambiguous","candidates":[{"id":11,"name":"Петров Пётр","class":"8А"},{"id":12,"name":"Петров Пётр","class":"8Б"}]},
         {"row":9,"status":"error","message":"Не указан класс"}]}
```

Строки со статусом `new` — ученики, которых нет в системе, но указан email: создаётся учётная запись и отправляется приглашение для установки пароля.

### Результаты

| Метод | Путь | Описание |
|---|---|---|
| PUT | `/admin/events/{id}/results` | Массовое внесение результатов |

```json
{"items":[{"registration_id":4,"place":1,"score":98.5,"status":"winner"},
          {"team_id":2,"place":2,"score":87,"status":"prizewinner"}]}
```

Допустимые статусы: `participated`, `prizewinner`, `winner`. Для команды статус копируется всем её участникам.

### Дипломы

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/events/{id}/diplomas` | Выданные дипломы мероприятия |
| POST | `/admin/events/{id}/diplomas` | Массовая генерация для призёров и победителей (`{"include_participants":false}`) |
| POST | `/admin/diplomas/{id}/revoke` | Отозвать |
| GET | `/admin/template` | Текущий шаблон (HTML) |
| PUT | `/admin/template` | Заменить шаблон |

### Отчёты

`GET /admin/reports/{kind}?format=xlsx|csv|pdf` — вид отчёта `students`, `classes`, `events`, `period`. Дополнительные параметры: `grade`, `event_id`, `date_from`, `date_to`.

### Пользователи

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/users` | Список. Параметры: `q`, `role`, `grade` |
| PATCH | `/admin/users/{id}` | Роль и активность: `{"role":"admin","is_active":true}` |

Нельзя понизить или заблокировать самого себя.
