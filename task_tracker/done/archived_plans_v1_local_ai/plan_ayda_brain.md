# ayda_brain — AI-движок (новый сервис)

*Февраль 2026. Часть общего плана интеграции.*
*Связанные планы: plan_tg_gather.md, plan_ayda_think.md*

---

## Что это

Самостоятельный FastAPI-сервис. Принимает **фрагменты** (сырые мысли, заметки, обрывки) из любых источников, индексирует, ищет связи, кластеризует, синтезирует **артефакты** (осмысленные находки).

Не знает ничего про Telegram, Google Sheets, носимые устройства. Знает только про **фрагменты на входе** и **артефакты на выходе**.

```
Любой клиент                        ayda_brain
                                    (FastAPI, порт 8100)

tg-gather    ── POST /fragments ──→  Принимает фрагменты (сырьё)
ayda_think   ── GET /search ──────→  Семантический поиск
бег-проект   ── POST /fragments ──→  Принимает данные с устройств
что угодно   ── GET /chains ──────→  Кластеры / цепочки
             ── GET /pattern ─────→  Эволюция темы
             ── POST /synthesize ─→  Синтез артефакта (DeepSeek)
```

### Глоссарий

| Термин | Что это |
|--------|---------|
| **Fragment** (фрагмент) | Единица входных данных. Сырая мысль, заметка, обрывок. Приходит извне. |
| **Artifact** (артефакт) | Результат работы brain. Найденная связь, синтезированная мысль, достроенный образ. |
| **Chain** (цепочка) | Группа семантически близких фрагментов, найденная кластеризацией. |

---

## Стек

| Компонент | Технология |
|-----------|-----------|
| API | FastAPI + uvicorn |
| Эмбеддинги | Ollama (nomic-embed-text), локально |
| Векторная БД | Chroma (PersistentClient) |
| Кластеризация | scikit-learn (DBSCAN) |
| Синтез текста | Ollama (DeepSeek R1 14B), локально |
| Конфиг | python-dotenv + yaml |

---

## Структура проекта

```
ayda_brain/
├── main.py                  # FastAPI app, uvicorn запуск
├── config.py                # Env vars + yaml конфиг
├── requirements.txt
├── .env                     # OLLAMA_HOST, CHROMA_PATH, порт
│
├── api/
│   ├── __init__.py
│   ├── fragments.py         # POST /fragments, GET /fragments/stats
│   ├── search.py            # GET /search?q=...
│   ├── chains.py            # GET /chains, GET /chains/{id}
│   ├── pattern.py           # GET /pattern?topic=...
│   └── synthesize.py        # POST /synthesize
│
├── core/
│   ├── __init__.py
│   ├── indexer.py            # Ollama эмбеддинги → Chroma
│   ├── clusterer.py          # DBSCAN кластеризация
│   ├── synthesizer.py        # DeepSeek промпт + генерация артефактов
│   └── embeddings.py         # Обёртка над Ollama embeddings
│
├── models/
│   ├── __init__.py
│   └── schemas.py            # Pydantic: Fragment, Chain, Artifact, SearchResult
│
└── data/
    └── chroma/               # Chroma persistent storage (gitignored)
```

---

## API — полная спецификация

### POST /fragments — добавить фрагменты

Принимает пачку фрагментов. Строит эмбеддинги, сохраняет в Chroma.

Рекомендуемый размер пачки: **100-200 фрагментов**. При первичном сборе большого объёма — разбивать на пачки и слать последовательно.

```
POST /fragments
Content-Type: application/json

{
  "source": "telegram",              # откуда пришли данные
  "fragments": [
    {
      "external_id": "me_12345",     # ID в системе-источнике
      "text": "AI ассистент для IAM — реальный продукт",
      "created_at": "2025-01-15T02:30:00",
      "tags": ["#ai", "#iam"],       # опционально
      "metadata": {                  # произвольные метаданные источника
        "telegram_msg_id": 12345,
        "chat": "saved_messages"
      }
    },
    ...
  ]
}

→ 200 OK
{
  "indexed": 15,
  "duplicates_skipped": 2,
  "total_in_db": 1150
}
```

**Размер пачки в цифрах:** один фрагмент ~300-500 байт JSON. 200 фрагментов = ~100 КБ. Даже 1000 = ~500 КБ. Лимит в 200 — не из-за размера запроса, а из-за времени обработки (каждый фрагмент = один вызов Ollama для эмбеддинга).

### GET /fragments/stats — статистика базы

```
GET /fragments/stats

→ 200 OK
{
  "total": 1150,
  "by_source": {
    "telegram": 1100,
    "garmin": 50
  },
  "date_range": {
    "earliest": "2023-05-10",
    "latest": "2026-02-20"
  },
  "last_indexed_at": "2026-02-20T10:30:00"
}
```

### GET /search — семантический поиск по фрагментам

```
GET /search?q=автоматизация+аудита+прав&limit=10

→ 200 OK
{
  "query": "автоматизация аудита прав",
  "results": [
    {
      "id": "me_12345",
      "text": "AI ассистент для IAM — реальный продукт",
      "created_at": "2025-01-15T02:30:00",
      "source": "telegram",
      "tags": ["#ai", "#iam"],
      "similarity": 0.87          # 1.0 = идентично
    },
    ...
  ]
}
```

### GET /chains — список цепочек (кластеров)

```
GET /chains?min_size=3

→ 200 OK
{
  "chains": [
    {
      "id": 0,
      "size": 7,
      "first_date": "2024-03-15",
      "last_date": "2025-02-10",
      "preview": "AI + IAM + аудит прав",   # авто-сгенерированная метка
      "fragment_ids": ["me_100", "me_234", ...]
    },
    ...
  ],
  "total_chains": 12,
  "orphans_count": 83,
  "clustered_at": "2026-02-20T10:00:00"
}
```

### GET /chains/{id} — конкретная цепочка

```
GET /chains/0

→ 200 OK
{
  "id": 0,
  "fragments": [
    {
      "id": "me_100",
      "text": "интересно было бы автоматизировать аудит прав",
      "created_at": "2024-03-15",
      "source": "telegram",
      "tags": ["#iam"]
    },
    ...
  ],
  "artifact": null    # null если синтез ещё не запускался
}
```

### GET /pattern — эволюция темы во времени

```
GET /pattern?topic=AI+и+IAM&limit=20

→ 200 OK
{
  "topic": "AI и IAM",
  "timeline": [
    {
      "id": "me_100",
      "text": "интересно было бы автоматизировать аудит прав",
      "created_at": "2024-03-15",
      "similarity": 0.82
    },
    ...
  ],
  "span_days": 340,
  "total_found": 8
}
```

### POST /synthesize — синтез артефакта

Берёт цепочку фрагментов и генерирует артефакт через DeepSeek — не резюме, а **следующую мысль**, достроенный образ.

```
POST /synthesize
{
  "fragment_ids": ["me_100", "me_234", "me_567"],
  # ИЛИ
  "chain_id": 0
}

→ 200 OK
{
  "artifact": {
    "common_thread": "Идея созревала 11 месяцев: от автоматизации...",
    "evolution": "Март 2024 → ...",
    "next_thought": "Логичный следующий шаг: ...",
    "generated_at": "2026-02-20T11:00:00"
  }
}
```

### POST /recluster — принудительная перекластеризация

```
POST /recluster
{
  "eps": 0.25,            # опционально, дефолт из конфига
  "min_samples": 2        # опционально
}

→ 200 OK
{
  "chains_found": 12,
  "orphans": 83,
  "duration_ms": 450
}
```

### GET /health — проверка здоровья

```
GET /health

→ 200 OK
{
  "status": "ok",
  "ollama": "connected",       # или "unavailable"
  "chroma": "connected",
  "fragments_count": 1150,
  "embedding_model": "nomic-embed-text",
  "llm_model": "deepseek-r1:14b"
}
```

---

## Pydantic-модели (models/schemas.py)

```python
from pydantic import BaseModel
from datetime import datetime

# --- Входные ---

class FragmentInput(BaseModel):
    external_id: str
    text: str
    created_at: datetime
    tags: list[str] = []
    metadata: dict = {}

class FragmentsRequest(BaseModel):
    source: str
    fragments: list[FragmentInput]

# --- Выходные ---

class FragmentResult(BaseModel):
    id: str
    text: str
    created_at: datetime
    source: str
    tags: list[str] = []
    similarity: float | None = None

class ChainSummary(BaseModel):
    id: int
    size: int
    first_date: str
    last_date: str
    preview: str
    fragment_ids: list[str]

class Artifact(BaseModel):
    common_thread: str
    evolution: str
    next_thought: str
    generated_at: datetime
```

---

## core/indexer.py — ядро

```python
import chromadb
from core.embeddings import get_embedding

class Indexer:
    def __init__(self, chroma_path: str):
        self.chroma = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.chroma.get_or_create_collection(
            name="fragments",
            metadata={"hnsw:space": "cosine"}
        )

    def index_batch(self, fragments: list[dict]) -> dict:
        """Индексирует пачку фрагментов. Возвращает статистику."""
        indexed = 0
        skipped = 0
        for f in fragments:
            existing = self.collection.get(ids=[f['external_id']])
            if existing['ids']:
                skipped += 1
                continue

            embedding = get_embedding(f['text'])
            self.collection.upsert(
                ids=[f['external_id']],
                embeddings=[embedding],
                documents=[f['text']],
                metadatas=[{
                    'created_at': f['created_at'],
                    'source': f['source'],
                    'tags': ','.join(f.get('tags', [])),
                    **{f'meta_{k}': str(v) for k, v in f.get('metadata', {}).items()}
                }]
            )
            indexed += 1

        return {"indexed": indexed, "skipped": skipped, "total": self.collection.count()}

    def search(self, query: str, n_results: int = 10) -> list[dict]:
        embedding = get_embedding(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        return self._format(results)

    def get_all_embeddings(self) -> dict:
        """Для кластеризации — все данные из коллекции."""
        return self.collection.get(
            include=['embeddings', 'documents', 'metadatas']
        )
```

## core/embeddings.py — обёртка Ollama

```python
import ollama

EMBEDDING_MODEL = "nomic-embed-text"

def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)
    return response['embedding']
```

Вынесено отдельно, чтобы потом заменить модель в одном месте.

---

## Конфигурация

### .env
```
CHROMA_PATH=./data/chroma
OLLAMA_HOST=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
LLM_MODEL=deepseek-r1:14b
BRAIN_PORT=8100
```

### config.py
```python
import os
from dotenv import load_dotenv

load_dotenv()

config = {
    "chroma_path": os.getenv("CHROMA_PATH", "./data/chroma"),
    "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    "embedding_model": os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
    "llm_model": os.getenv("LLM_MODEL", "deepseek-r1:14b"),
    "port": int(os.getenv("BRAIN_PORT", "8100")),
}
```

---

## Запуск

```bash
# Предварительно
ollama pull nomic-embed-text
ollama pull deepseek-r1:14b

# Запуск
cd ayda_brain
python main.py
# → FastAPI на http://localhost:8100
# → Swagger docs на http://localhost:8100/docs
```

---

## Зависимости (requirements.txt)

```
fastapi>=0.100.0
uvicorn>=0.23.0
chromadb>=0.4.0
ollama>=0.1.0
scikit-learn>=1.3.0
numpy>=1.24.0
pydantic>=2.0.0
python-dotenv
```

---

## Принципы

1. **Источнико-агностичный** — API не знает про Telegram. Поле `source` — просто строка. Завтра можно прислать `source: "garmin"` с данными пульса и заметками к тренировкам.

2. **Fragments in → Artifacts out** — чёткое разделение. На входе сырьё, на выходе осмысленные находки.

3. **Stateless API** — всё состояние в Chroma. Сервис можно перезапустить без потерь.

4. **Сменяемый AI-бэкенд** — `core/embeddings.py` и `core/synthesizer.py` — единственные файлы, которые знают про конкретного AI-провайдера. Замена Ollama на облачный API = замена одного файла.

5. **Swagger из коробки** — FastAPI генерирует полную документацию API. Любой клиент может посмотреть `/docs` и понять как интегрироваться.

6. **Пачки по 100-200** — при массовой загрузке фрагментов бить на пачки. Не из-за лимита сети, а из-за времени обработки эмбеддингов.

---

## Стратегия деплоя

Три ступеньки, от разработки до прода:

### 1. Локалка (разработка)
- Ollama на ноутбуке (nomic-embed-text + DeepSeek 14B)
- Chroma + FastAPI локально
- Стоимость: **$0**
- Для: разработка, тестирование, отладка

### 2. Hetzner VPS (набить руку с деплоем)
- Hetzner CAX31: 8 vCPU ARM, 16 GB RAM — **~€11/мес (~$12)**
- Ollama на CPU (медленно, но работает)
- Docker, настройка сервера, CI/CD — полезный опыт
- Для: научиться деплоить, прощупать лимиты CPU-инференса

### 3. Прод (облачные AI API)
- Дешёвый VPS (€4-7/мес) — только FastAPI + Chroma
- Эмбеддинги и генерация через облачные API:

| Провайдер | Эмбеддинги | Генерация (синтез) |
|-----------|-----------|-------------------|
| Together.ai | $0.008/1M токенов | DeepSeek 14B: $0.18/1M |
| DeepSeek API | — | DeepSeek R1: $0.55/1M input |
| OpenAI | text-embedding-3-small: $0.02/1M | GPT-4o-mini: $0.15/1M input |

- При 5000 фрагментов: индексация ~$0.01-0.05 разово, ежедневно — копейки
- **Итого: $10-15/мес** (VPS + API usage)
- Для: стабильная работа, быстрые ответы

### Что меняется при переходе между ступеньками

Только два файла:

```python
# core/embeddings.py — Ollama вариант (ступенька 1-2)
import ollama
def get_embedding(text: str) -> list[float]:
    return ollama.embeddings(model='nomic-embed-text', prompt=text)['embedding']

# core/embeddings.py — облачный вариант (ступенька 3)
import openai
def get_embedding(text: str) -> list[float]:
    resp = openai.embeddings.create(model='text-embedding-3-small', input=text)
    return resp.data[0].embedding
```

Аналогично `core/synthesizer.py`: Ollama → OpenAI/DeepSeek API.

Всё остальное (API, Chroma, кластеризация, модели) — **без изменений**.

---

## Порядок реализации

### Этап 1 — Каркас
- [ ] Создать репозиторий `ayda_brain`
- [ ] Структура проекта (api/, core/, models/)
- [ ] FastAPI app + config + health endpoint
- [ ] Убедиться что Ollama доступен

### Этап 2 — Индексация
- [ ] core/embeddings.py
- [ ] core/indexer.py
- [ ] POST /fragments endpoint
- [ ] GET /fragments/stats endpoint
- [ ] Тест: отправить 5 фрагментов, проверить что сохранились

### Этап 3 — Поиск
- [ ] GET /search endpoint
- [ ] Тест: поиск по реальным данным, оценить качество

### Этап 4 — Кластеризация
- [ ] core/clusterer.py
- [ ] GET /chains, GET /chains/{id}
- [ ] POST /recluster
- [ ] GET /pattern

### Этап 5 — Синтез
- [ ] core/synthesizer.py (DeepSeek промпт)
- [ ] POST /synthesize
- [ ] Тест: синтез на реальных цепочках

---

*Документ создан: февраль 2026*
*Путь: все проекты → docs/task_tracker/to_do/plan_ayda_brain.md*
