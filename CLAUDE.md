# Ayda Think — Telegram Notes Bot

Telegram-бот для сохранения заметок в Google Sheets (multi-tenant) + Mini App для просмотра.

## Язык

- Общение: русский
- Код и коммиты: английский

## Quick Reference

| What | Where |
|------|-------|
| Bot entry point | `main.py` |
| API server | `api_server.py` |
| Config | `config.py` |
| Bot handlers | `bot/` |
| Business logic | `services/` |
| Data layer | `storage/` |
| Frontend (Mini App) | `webapp/` |
| Pydantic models | `schemas.py` |
| Runtime data (JSON) | `data/` |
| Documentation | `internal/docs/` |
| Tasks | `task_tracker/` |
| Domain model | `internal/docs/knowledges/domain_model.md` |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Bot framework | python-telegram-bot 20+ |
| API | FastAPI + uvicorn |
| Google Sheets | gspread + google-auth |
| Database | SQLite (local) / PostgreSQL (Railway) via SQLAlchemy |
| Vector search | pgvector + OpenAI text-embedding-3-small |
| Clustering | UMAP + HDBSCAN |
| Synthesis | OpenAI GPT-4o-mini |
| Voice | OpenAI Whisper + GPT-4o-mini |
| Frontend | Vanilla JS (ES6 modules) |
| Config | python-dotenv |

## Git Workflow

**Никогда не коммитить напрямую в main!**

### Структура веток
- `main` — продакшн (Railway деплоит автоматически)
- `dev` — разработка, тестирование перед продакшном
- `feature/*` — новые фичи
- `fix/*` — баг-фиксы

### Порядок работы
```
1. git checkout dev && git pull origin dev
2. git checkout -b feature/название-фичи
3. ... делаем изменения ...
4. git add && git commit
5. git push origin feature/название-фичи
6. git checkout dev && git merge feature/название-фичи
7. git push origin dev
8. Тестируем на dev
9. git checkout main && git merge dev && git push origin main
```

### Если случайно сделал изменения в main (не закоммитил)
```bash
git stash
git checkout dev
git stash pop
```

## Commands

```bash
# Run bot (polling mode)
python main.py

# Run API server
python api_server.py

# Run both (production)
bash start.sh

# Deploy (Railway auto-deploys from main)
git checkout main && git merge dev && git push origin main
```

## Project Structure

```
ayda_think/
├── main.py                  # Bot entry, handler registration
├── api_server.py            # FastAPI: serves webapp + REST API
├── config.py                # Env vars loading
├── schemas.py               # Pydantic response models
│
├── bot/
│   ├── handlers.py          # Re-export hub
│   ├── start_handler.py     # /start command
│   ├── registration_handler.py  # Sheet URL → save user
│   ├── note_handler.py      # Save text/voice/forward notes
│   ├── voice_handler.py     # Download + transcribe audio
│   ├── tag_handler.py       # /tag command
│   ├── brain_handler.py     # /search, /normalize, /cluster, /artifact commands
│   ├── channel_integration.py   # Channel → user DM sync
│   ├── forward_utils.py     # Extract forward metadata
│   └── utils.py             # User/spreadsheet lookups
│
├── services/
│   ├── note_service.py      # Notes CRUD for API
│   ├── transcription_service.py  # Whisper + GPT
│   ├── normalizer_service.py    # Embeddings, language detection, dedup
│   ├── clustering_service.py    # UMAP + HDBSCAN clustering + AI names
│   ├── synthesis_service.py     # GPT synthesis (artifacts)
│   └── relation_service.py  # Tag-based relations + reply chains
│
├── storage/
│   ├── base.py              # Abstract interface
│   ├── db.py                # SQLite/PostgreSQL (User, ChannelMapping, ChannelMessageMapping)
│   ├── fragments_db.py      # Fragment/Cluster/FragmentCluster/Artifact models + CRUD (pgvector)
│   └── google_sheets.py     # Google Sheets read/write
│
├── webapp/
│   ├── index.html           # Single page app
│   ├── app.js               # Main orchestration
│   ├── api.js               # Telegram WebApp API wrapper
│   ├── state.js             # State management
│   ├── ui.js                # DOM rendering
│   ├── gestures.js          # Touch/swipe controls
│   └── styles.css           # Mobile-first CSS
│
├── data/                    # Runtime data (gitignored, NOT used for persistent state)
│   └── (legacy JSON files removed — mappings now in DB)
│
├── task_tracker/            # Tasks (tracked in git)
│   ├── todo/
│   ├── in_progress/
│   ├── done/
│   └── backlog/
└── internal/                # Personal docs & AI context (gitignored)
    └── docs/
        ├── ai_settings/     # AI context, specs
        └── knowledges/      # Domain model, research
```

## Google Sheets Schema (11 columns)

| Col | Header | Content |
|-----|--------|---------|
| A | ID | `{timestamp}_{msg_id}` |
| B | Telegram Message ID | int |
| C | Created At | ISO 8601 |
| D | Content | Text (sanitized against formula injection) |
| E | Tags | Comma-separated `#tags` |
| F | Reply To Message ID | int or empty |
| G | Message Type | general / forwarded / voice / channel_post |
| H | Source Chat ID | For forwards/channels |
| I | Source Chat Link | URL to original |
| J | Telegram Username | @username |
| K | Status | new / focus / done / archived |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serve index.html |
| GET | `/api/notes?user_id=X` | Get user notes (filtered, sorted) |
| POST | `/api/notes/{id}/status` | Update note status |
| GET | `/api/notes/{id}/related?user_id=X` | Related notes by tags |
| GET | `/api/notes/{id}/replies?user_id=X` | Reply chain tree |
| POST | `/api/fragments` | Ingest fragments + auto-normalize (requires X-API-Key) |

## Bot Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Registration flow | All users |
| `/tag #a #b` | Add tags to replied message | All users |
| `/link_channel` | Link channel to user | All users |
| `/search <query>` | Semantic search across fragments | All users |
| `/cluster [min_size] [min_samples]` | Run UMAP+HDBSCAN clustering | Admin only |
| `/normalize` | Run normalization on unembedded fragments | Admin only |
| `/artifact <тема>` | GPT synthesis on a topic (evolution, connections) | All users |

## Critical Rules

### Formula injection — always sanitize
```python
# Content starting with = + - @ gets prefixed with '
def sanitize_for_sheets(text):
    if text and text[0] in ('=', '+', '-', '@'):
        return f"'{text}"
    return text
```

### Show errors to user — never silent
```python
# WRONG
except Exception as e:
    logging.error(e)

# RIGHT
except Exception as e:
    logging.error(e)
    await msg.answer(f"Error: {e}")
```

### Persistent state — always use DB, never JSON files
```python
# Channel mappings are in PostgreSQL, NOT in JSON files.
# JSON files in data/ are ephemeral and get lost on redeploy.
from storage.db import save_channel_mapping, get_channel_user
```

## Доменная модель

Полная модель: `docs/knowledges/domain_model.md`. **Читать перед работой с бизнес-логикой.**

Ключевые сущности:
- **Fragment** — атомарная мысль/заметка. Три типа связей: Reply (явная), Tag (явная), Semantic (неявная)
- **Cluster** — группа семантически близких фрагментов (UMAP + HDBSCAN). Версионируется
- **Artifact** — результат GPT-синтеза. Анализ эволюции мысли, не пересказ. Привязан к fragment_ids + опционально cluster_id

При добавлении/изменении сущностей — **обновить `internal/docs/knowledges/domain_model.md`**.

## Навигация

- `internal/docs/` — читать свободно
- `task_tracker/todo/` — текущие задачи, читать свободно
- `task_tracker/done/` — НЕ читать без запроса (экономия контекста)

## Выполнение планов

- Если план записан в файле — идти строго по нему
- После compaction контекста — перечитать план и файлы
- Если план > 300 строк — предупредить, предложить разбить

## После создания нового компонента

- [ ] Добавлен import
- [ ] Зарегистрирован handler в `main.py`
- [ ] Вызывается оттуда, где нужно
- [ ] Есть путь от user action до этого кода
- [ ] CLAUDE.md обновлён (Quick Reference, Project Structure, API Endpoints)
