# K.ai / «Кометтик» — MVP веб‑приложения подбора насосов Кометта

MVP в стиле ChatGPT: слева список чатов, справа диалог с Кометтиком (инженер‑помощник Кометта). Поддерживаются текстовые сообщения, вложения и отображение графиков Q‑H прямо в ленте.

## Возможности (MVP)

- **Чаты**
  - Создание нового чата
  - Выбор чата из списка
  - **Переименование** (inline) и **удаление** чатов из сайдбара
- **Сообщения**
  - Текст + вложения в одном сообщении (jpg/png/pdf/xlsx/txt/doc/docx)
  - Потоковый ответ (SSE) с эффектом «печатает»
- **Кометтик (поведение)**
  - Отвечает по теме насосов Кометта (подбор/аналоги/эксплуатация/диагностика/документация)
  - В конце каждого ответа добавляет 1–3 продолжения диалога (вопросы/предложения)
- **Графики**
  - Построение Q‑H и сравнение кривых (Кометта vs конкурент)
  - График отдаётся как PNG и отображается в сообщении

## Структура проекта

- `backend/` — FastAPI API + логика подбора/графиков/вложений
- `frontend/` — Next.js (App Router) UI
- `data/` — Excel базы:
  - `K.ai_database_kometta.xlsx`
  - `K.ai_database_competitors_cnp.xlsx`

## Требования

- **Backend**: Python 3.10+ (рекомендуется 3.11)
- **Frontend**: Node.js 18+

## Быстрый старт (локально)

### 1) Backend (FastAPI)

Перейдите в `backend/`, установите зависимости и запустите:

```bash
cd backend
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

Backend поднимется на `http://localhost:8000`.

### 2) Frontend (Next.js)

Перейдите в `frontend/`, установите зависимости и запустите dev‑сервер:

```bash
cd frontend
npm install
npm run dev
```

Frontend поднимется на `http://localhost:3000`.

## Переменные окружения (backend)

Backend читает `.env` (см. `backend/main.py`).

- **`DATA_DIR`**: путь к папке `data/` (если не указан — берётся `../data` относительно `backend/`)
- **`DEBUG_LOG_PATH`**: путь к debug‑логу (по умолчанию `/var/www/kai/.cursor/debug.log`)
- **`TYPO_FUZZY`**: `1/0` — включить/выключить нормализацию опечаток

## Основные API эндпоинты (backend)

Базовый префикс: `/api`

- **Auth**
  - `/api/auth/...` (magic link / callback)
- **Chats**
  - `GET /api/chats` — список чатов пользователя
  - `POST /api/chats` — создать чат
  - `GET /api/chats/{chat_id}` — получить чат + сообщения
  - `PATCH /api/chats/{chat_id}?title=...` — переименовать чат
  - `DELETE /api/chats/{chat_id}` — удалить чат (soft delete)
  - `POST /api/chats/{chat_id}/messages` — отправить сообщение (SSE поток в ответ)
- **Plots**
  - `GET  /api/plot/compare?kometta_articul=...&competitor_articul=...` — PNG (для встраивания ссылкой)
  - `POST /api/plot/compare` — PNG (MVP по ТЗ)

## Данные и математика кривых

Логика аппроксимации и пересечения кривых опирается на `archive/app.py`:

- Кубическая аппроксимация: \(H = aQ^3 + bQ^2 + cQ + d\) через `np.linalg.solve` **строго по 4 опорным точкам**
- Рабочая точка: `root_scalar(..., method='brentq')`
- Сетевая кривая: \(H_{net} = H_{st} + S Q^2\)

Нормализация десятичных запятых у конкурентов (`"0,37" → 0.37`) делается при загрузке Excel в `backend/services/normalize.py`.

## Production (пример)

В репозитории есть `frontend/ecosystem.config.js` (пример запуска Next.js через PM2).
Backend обычно запускается через `uvicorn` (см. `backend/main.py`).

## Примечания

- Проект — MVP: код намеренно простой, читаемый и расширяемый.
- Графики сохраняются с прозрачным фоном, чтобы корректно выглядеть в тёмной/светлой теме UI.

