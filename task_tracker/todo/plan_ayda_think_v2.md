# ayda_think v2 — мозг для поиска смыслов

*Март 2026. Заменяет plan_ayda_think.md и plan_ayda_brain.md.*
*Связанный план: plan_tg_gather_v2.md*

---

## Роль в системе

ayda_think — единый сервис. Принимает фрагменты из любых источников, нормализует, группирует, ищет паттерны, синтезирует артефакты.

```
tg_gather ──────────┐
insta (импорт ZIP)  ├──→ PostgreSQL + pgvector ──→ ayda_think
linkedin (импорт)   │                              ├── Нормализация
browser (MCP)  ─────┘                              ├── Группировка (DBSCAN)
                                                   ├── Поиск паттернов
                                                   ├── Синтез артефактов
                                                   └── Бот + Mini App
```

ayda_think **не** собирает данные сам (кроме заметок через бота). Данные приходят извне: от gather'ов (INSERT в БД) или через `POST /api/fragments`.

---

## Глоссарий

| Термин | Что это |
|--------|---------|
| **Fragment** (фрагмент) | Сырая мысль, заметка, сохранённый пост. Приходит из любого источника. |
| **Artifact** (артефакт) | Результат анализа. Найденная связь, синтезированная мысль, достроенный образ. |
| **Chain** (цепочка) | Группа семантически близких фрагментов, найденная кластеризацией. |

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| Бот | python-telegram-bot 20+ (как сейчас) |
| API | FastAPI + uvicorn (как сейчас) |
| БД | PostgreSQL на Railway (как сейчас) + **pgvector** (новое) |
| Эмбеддинги | OpenAI text-embedding-3-small |
| Кластеризация | UMAP + HDBSCAN |
| Синтез | OpenAI GPT-4o-mini |
| Синтез | OpenAI GPT-4o-mini |
| Frontend | Mini App (как сейчас) |

---

## Что добавляется в проект

### 1. pgvector в PostgreSQL

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE fragments (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE,     -- 'telegram_me_12345'
    source VARCHAR(50) NOT NULL,          -- 'telegram', 'instagram', 'linkedin', 'browser'
    text TEXT NOT NULL,
    embedding vector(1536),               -- OpenAI text-embedding-3-small
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMP NOT NULL,        -- когда создан оригинал
    indexed_at TIMESTAMP DEFAULT NOW(),   -- когда попал к нам
    metadata JSONB DEFAULT '{}',          -- произвольные метаданные источника
    content_type VARCHAR(20) DEFAULT 'note',  -- note / link / quote / repost
    language VARCHAR(5),                  -- ru / en / mixed
    is_duplicate BOOLEAN DEFAULT FALSE,
    is_outdated BOOLEAN DEFAULT FALSE
);

CREATE TABLE clusters (
    id SERIAL PRIMARY KEY,
    version INTEGER NOT NULL,            -- версия кластеризации (инкремент при каждом прогоне)
    label INTEGER NOT NULL,              -- DBSCAN label внутри прогона
    size INTEGER DEFAULT 0,
    preview TEXT,                         -- первые N символов для превью
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(version, label)
);

CREATE TABLE fragment_clusters (
    fragment_id INTEGER REFERENCES fragments(id),
    cluster_id INTEGER REFERENCES clusters(id),
    version INTEGER NOT NULL,
    PRIMARY KEY (fragment_id, version)
);

CREATE INDEX idx_fragments_source ON fragments(source);
CREATE INDEX idx_fragment_clusters_cluster ON fragment_clusters(cluster_id);
-- HNSW вместо IVFFlat: работает на пустой таблице, не требует обучения
CREATE INDEX idx_fragments_embedding ON fragments USING hnsw (embedding vector_cosine_ops);
```

### 2. Новые файлы

```
ayda_think/
├── services/
│   ├── brain_service.py          # НОВОЕ: эмбеддинги, поиск, кластеризация
│   ├── normalizer_service.py     # НОВОЕ: дедупликация, актуальность, тип контента
│   └── synthesis_service.py      # НОВОЕ: синтез артефактов через GPT-4o-mini
│
├── bot/
│   └── brain_handler.py          # НОВОЕ: /search, /chains, /pattern, /hot
│
├── storage/
│   └── fragments_db.py           # НОВОЕ: CRUD для таблицы fragments
│
├── scripts/
│   ├── import_instagram.py       # НОВОЕ: импорт из Instagram ZIP
│   └── import_linkedin.py        # НОВОЕ: импорт из LinkedIn ZIP
│
└── api_server.py                 # + POST /api/fragments (новый эндпоинт)
```

### 3. API-эндпоинт для приёма фрагментов

**Авторизация:** API-key в заголовке `X-API-Key`. Ключ хранится в env-переменной `FRAGMENTS_API_KEY`.

```
POST /api/fragments
Content-Type: application/json
X-API-Key: <FRAGMENTS_API_KEY>

{
  "source": "telegram",
  "fragments": [
    {
      "external_id": "telegram_me_12345",
      "text": "AI ассистент для IAM — реальный продукт",
      "created_at": "2025-01-15T02:30:00",
      "tags": ["#ai", "#iam"],
      "content_type": "note",
      "metadata": { "chat": "saved_messages" }
    }
  ]
}

→ 200 OK
{ "indexed": 15, "duplicates_skipped": 2, "total": 1150 }
```

### 4. Команды бота

| Команда | Что делает |
|---------|-----------|
| `/search [запрос]` | Семантический поиск по фрагментам (+ показ кластера) |
| `/artifact [тема]` | GPT-синтез: эволюция мысли, связи, достройка |
| ~~`/chains`~~ | ~~Убрано — дублирует /search и HTML-экспорт~~ |
| ~~`/chain N`~~ | ~~Убрано — дублирует /search и HTML-экспорт~~ |
| ~~`/pattern [тема]`~~ | ~~Убрано как термин — заменено на /artifact~~ |
| ~~`/hot`~~ | ~~Убрано — сомнительная ценность на текущем объёме~~ |

---

## Пайплайн обработки

### Шаг 1: Приём фрагмента
Фрагмент попадает в таблицу `fragments` (через INSERT от gather'а или через POST /api/fragments).

### Шаг 2: Нормализация (normalizer_service.py)
Фоновая задача, обрабатывает новые фрагменты:
- **Эмбеддинг** — вызов OpenAI text-embedding-3-small, сохраняет в поле `embedding`
- **Дедупликация** — cosine similarity > 0.95 с существующими → помечает `is_duplicate = True`
- **Тип контента** — определяет: своя мысль / ссылка / цитата / репост
- **Язык** — определяет RU / EN / mixed
- **Актуальность** — для ссылок на статьи проверяет дату (> 2 лет → `is_outdated = True`)

### Шаг 3: Группировка (clustering_service.py)
Периодическая задача (по запросу `/cluster`):
- Берёт все эмбеддинги (кроме дубликатов)
- UMAP (1536→50 dims) + HDBSCAN кластеризация
- Создаёт новую `version` в таблице `clusters`, записывает результаты в `fragment_clusters`
- Генерирует AI-имена для кластеров (GPT-4o-mini)
- Старые версии сохраняются

### Шаг 4: Синтез артефактов (synthesis_service.py)
По запросу (`/artifact [тема]`) или пассивно (при `/cluster` для крупных кластеров):
- Семантический поиск по теме → подтягивание кластерного контекста
- Двухпроходный GPT-4o-mini: 1) выборка ключевых фрагментов, 2) анализ эволюции мысли
- Результат — артефакт (не резюме, а достройка: связи, эволюция, продолжение)
- Сохраняется в таблице `artifacts`

### Шаг 5: Алерты (будущее)
Раз в неделю бот присылает:
- Новые кластеры
- Крупные кластеры без артефакта

---

## Источники данных

| Источник | Способ сбора | Автоматический? |
|----------|-------------|----------------|
| Telegram (saved, каналы) | tg_gather → INSERT в PostgreSQL | Да |
| Заметки через бота | ayda_think бот (как сейчас) + INSERT в fragments | Да |
| Instagram | Скачать ZIP → python scripts/import_instagram.py | Ручной |
| LinkedIn | Скачать ZIP → python scripts/import_linkedin.py | Ручной |
| Браузер | MCP-коннектор Chrome/Firefox (будущее) | Полуавтоматический |

---

## Новые зависимости (requirements.txt)

```
pgvector>=0.2.0
scikit-learn>=1.3.0
numpy>=1.24.0
```

OpenAI уже есть (используется для Whisper).

---

## Новые env-переменные

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `OPENAI_API_KEY` | — | Уже есть (для Whisper) |
| `FRAGMENTS_API_KEY` | — | API-key для POST /api/fragments |

---

## Что НЕ меняется

- Текущая логика заметок (Google Sheets) — без изменений
- Mini App — без изменений (позже добавим вкладку артефактов)
- storage/db.py — без изменений (User, ChannelMapping — как есть)
- Все текущие хендлеры — без изменений

---

## Порядок реализации

### Этап 1 — pgvector + таблица fragments ✅
- [x] Включить pgvector на Railway (`CREATE EXTENSION vector`) — `storage/db.py init_db()`
- [x] Создать таблицу `fragments` (SQLAlchemy модель) — `storage/fragments_db.py`
- [x] Создать таблицы `clusters` + `fragment_clusters` (версионирование кластеров)
- [x] CRUD: вставка, чтение, поиск по embedding — `insert_fragment`, `insert_fragments_batch`, `search_by_embedding`
- [x] HNSW индекс вместо IVFFlat (работает на пустой таблице)
- [ ] Тест: вставить 5 фрагментов вручную, найти похожие

### Этап 2 — Приём данных ✅ (кроме эмбеддингов)
- [x] `POST /api/fragments` эндпоинт в api_server.py (с X-API-Key авторизацией)
- [x] Pydantic модели: `FragmentsRequest`, `FragmentsResponse`, `FragmentInput` — `schemas.py`
- [x] При сохранении заметки через бот — дублировать в fragments — `bot/note_handler.py _save_to_fragments()`
- [ ] Генерация эмбеддингов при вставке (OpenAI API) — перенесено в Этап 3
- [ ] Тест: отправить POST, проверить что сохранилось

### Этап 3 — Нормализация ✅
- [x] normalizer_service.py — эмбеддинги (OpenAI text-embedding-3-small), дедупликация
- [x] Дедупликация (cosine similarity > 0.95) — 2 дубликата найдено из 686
- [x] Определение языка (эвристика: ru/en/mixed)
- [x] /normalize команда (admin only, ADMIN_USER_ID)
- [x] /search — гибридный поиск (semantic + keyword/tag + stemming)
- [x] Авто-нормализация при POST /api/fragments
- [ ] Определение типа контента (note / link / quote / repost) — отложено
- [ ] Проверка актуальности (для ссылок) — отложено

### Этап 4 — Группировка ✅
- [x] clustering_service.py: DBSCAN → HDBSCAN + UMAP
- [x] Версионирование: таблицы `clusters` + `fragment_clusters`, новая version при каждом прогоне
- [x] Метаданные кластеров (размер, превью из топ-тега + первых 2 фрагментов)
- [x] /cluster [min_cluster_size] [min_samples] — запуск кластеризации (admin only)
- [x] UMAP (1536→50 dims, cosine) + HDBSCAN (euclidean, EOM) — 53 кластера, 14% шум
- [x] Интерактивный HTML-экспорт с 3 вкладками (по размеру, по близости, дерево иерархии)
- [x] AI-названия кластеров через GPT-4o-mini
- [x] Локальная среда разработки (Docker PostgreSQL + pgvector)

### Этап 5 — Команды бота ✅
- [x] brain_handler.py: /search (гибридный поиск) — перенесён в Этап 3
- [x] Зарегистрировать хендлеры в main.py
- [x] ~~/chains, /chain~~ — убрано, дублирует /search с кластерами и HTML-экспорт
- [x] Тест: реальные запросы через бот

### Этап 5.5 — Улучшение кластеров ✅
- [x] AI-имена кластеров в продакшне (поле `name` в таблице clusters, генерация при /cluster)
- [x] Поиск через кластеры (/search → показывать кластер найденного фрагмента)
- [x] Убраны /chains, /chain — дублировали /search и HTML-экспорт

### Этап 6 — Артефакты (GPT-синтез)
Подробный план: `task_tracker/todo/etap6_artifacts/`
- [ ] Модель Artifact + CRUD в fragments_db.py
- [ ] synthesis_service.py: двухпроходный GPT-движок
- [ ] /artifact [тема] — GPT-синтез эволюции мысли (поиск + кластерный контекст + GPT)
- [ ] Пассивная генерация артефактов при /cluster (кластеры ≥ 7 фрагментов)
- [ ] Тест на реальных данных, итерация промптов
- [ ] **Защита от галлюцинаций**: промпт "опирайся ТОЛЬКО на предоставленные фрагменты"
- ~~[ ] /hot~~ — убрано (сомнительная ценность на текущем объёме)
- ~~[ ] /pattern~~ — убрано как термин (заменено на /artifact)

### Этап 7 — Алерты
- [ ] Фоновая задача: еженедельная кластеризация
- [ ] Алерт в бот: новые кластеры, кластеры без артефакта
- [ ] Тест: дождаться алерта

### Этап 8 — Импорт из других источников
- [ ] scripts/import_instagram.py
- [ ] scripts/import_linkedin.py
- [ ] Документация: как скачать архив и импортировать

---

*Документ создан: март 2026*
*Заменяет: plan_ayda_think.md, plan_ayda_brain.md*
