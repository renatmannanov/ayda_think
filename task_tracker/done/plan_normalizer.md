# Plan: normalizer_service.py + /search command

*Этап 3 + часть Этапа 5 из plan_ayda_think_v2.md*
*Создан: 2026-03-10*
*Обновлён: 2026-03-10*

---

## Цель

Обработать 686 фрагментов в БД:
1. Сгенерировать эмбеддинги (для семантического поиска)
2. Найти дубликаты (cosine > 0.95)
3. Определить язык (ru/en/mixed)
4. Дать возможность искать через бот-команду `/search`
5. Автоматически нормализовать новые фрагменты при вставке

---

## Что создаём

```
services/normalizer_service.py   # НОВЫЙ: эмбеддинги, дедупликация, язык
bot/brain_handler.py             # НОВЫЙ: /search команда
```

Что меняем:
```
storage/fragments_db.py          # + update_embedding(), get_unembedded(), find_duplicates()
api_server.py                    # + вызов нормализации после POST /api/fragments
main.py                          # + регистрация /search хендлера
CLAUDE.md                        # + обновить Project Structure, API
```

---

## Шаги реализации

### Шаг 1: CRUD для эмбеддингов в fragments_db.py

Добавить функции в `storage/fragments_db.py`:

```python
def get_unembedded_fragments(limit: int = 100) -> list[dict]:
    """Фрагменты без эмбеддингов (embedding IS NULL, is_duplicate=False)."""
    # Возвращает: [{id, text}, ...]

def update_embedding(fragment_id: int, embedding: list[float]) -> None:
    """Сохранить эмбеддинг для фрагмента."""

def update_fragment_fields(fragment_id: int, **fields) -> None:
    """Обновить произвольные поля (language, is_duplicate, is_outdated)."""

def find_near_duplicates(embedding: list[float], threshold: float = 0.95, exclude_id: int = None) -> list[dict]:
    """Найти фрагменты с cosine similarity > threshold.
    Использует pgvector: 1 - cosine_distance < threshold.
    ВАЖНО: фильтрует по is_duplicate=False — сравниваем только с оригиналами.
    """
```

### Шаг 2: normalizer_service.py

Один файл `services/normalizer_service.py`:

```python
# Публичный API:
def normalize_all(batch_size=50) -> dict:
    """Прогнать нормализацию по всем необработанным фрагментам.
    Коммитит в БД после каждого батча (прогресс не теряется при ошибке).
    Возвращает: {embedded: N, duplicates: N, errors: N}
    """

def normalize_fragments(fragment_ids: list[int]) -> dict:
    """Нормализовать конкретные фрагменты (для автонормализации после вставки).
    Возвращает: {embedded: N, duplicates: N, errors: N}
    """

# Внутренние функции:
def _generate_embeddings(fragments: list[dict]) -> list[list[float]]:
    """Батч-запрос к OpenAI text-embedding-3-small.
    OpenAI API принимает до 2048 текстов за раз.
    Батчим по 50 для экономии памяти.
    """

def _detect_language(text: str) -> str:
    """Определение языка по буквенным символам (без API).
    Фильтрует через str.isalpha() — URL, цифры, эмодзи игнорируются.
    Считает долю кириллицы vs латиницы среди букв.
    > 70% кириллица → 'ru'
    > 70% латиница → 'en'
    Иначе → 'mixed'
    """

def _check_duplicates(fragment_id: int, embedding: list[float]) -> bool:
    """Проверить, есть ли near-duplicate.
    Если cosine_similarity > 0.95 с существующим — пометить is_duplicate=True.
    Возвращает True если дубликат.
    """
```

**Важные решения:**
- Эмбеддинги через OpenAI API (text-embedding-3-small, 1536 dims)
- Батч по 50 текстов (один API-вызов)
- Коммит в БД после каждого батча — при ошибке теряем максимум 50 фрагментов
- Определение языка — эвристика по буквенным символам (`isalpha()`), БЕЗ вызова GPT
- URL, цифры, эмодзи не учитываются при определении языка
- Определение типа контента — НЕ делаем, tg_gather уже определяет (note/link/repost)
- Проверка актуальности ссылок — ОТКЛАДЫВАЕМ (требует HTTP-запросы к каждой ссылке)
- Дедупликация: сравниваем только с оригиналами (is_duplicate=False)

**Стоимость:**
- 686 фрагментов × ~450 символов ≈ 310K символов ≈ 77K токенов
- text-embedding-3-small: $0.02 / 1M tokens
- Итого: ~$0.002 (менее 1 цента)

### Шаг 3: Автонормализация при вставке

В `api_server.py`, в `POST /api/fragments` — после `insert_fragments_batch()`:

```python
# После успешной вставки — нормализуем новые фрагменты
from services.normalizer_service import normalize_fragments
normalize_result = normalize_fragments(inserted_ids)
```

Для этого `insert_fragments_batch()` должен возвращать список id вставленных фрагментов (сейчас возвращает `{indexed: N, duplicates_skipped: N}`).

**Изменение в fragments_db.py:** `insert_fragments_batch()` → возвращает `{indexed: N, duplicates_skipped: N, inserted_ids: [int]}`.

### Шаг 4: /search команда в bot/brain_handler.py

```python
async def search_command(update, context):
    """Обработчик /search [запрос]
    1. Получить эмбеддинг запроса (OpenAI)
    2. Найти ТОП-5 ближайших через search_by_embedding()
    3. Отформатировать и отправить
    """
```

Формат ответа:
```
🔍 Поиск: "чайный бизнес"

1. [0.12] 2025-04-21
   #aretea Можно вместо коробок делать шоперы...

2. [0.15] 2025-04-20
   #aretea Ощущение приятной горечи, теплоты...

3. [0.18] 2024-12-01
   Идея: продавать чай в банках...
```

Где `[0.12]` — cosine distance (меньше = ближе).

### Шаг 5: /normalize команда (только для админа)

В `bot/brain_handler.py`:

```python
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

async def normalize_command(update, context):
    """Обработчик /normalize — только для админа.
    Прогоняет normalize_all() и отправляет результат.
    """
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("Нет доступа.")
        return
    ...
```

### Шаг 6: Регистрация в main.py

```python
from bot.brain_handler import search_command, normalize_command
application.add_handler(CommandHandler("search", search_command))
application.add_handler(CommandHandler("normalize", normalize_command))
```

### Шаг 7: Обновить CLAUDE.md

- Добавить `normalizer_service.py` в Project Structure
- Добавить `brain_handler.py` в Project Structure
- Добавить `/search`, `/normalize` в описание команд

---

## Порядок написания кода

1. `storage/fragments_db.py` — CRUD для эмбеддингов (4 новые функции + правка insert_fragments_batch)
2. `services/normalizer_service.py` — нормализация (1 файл)
3. `api_server.py` — автонормализация после вставки
4. `bot/brain_handler.py` — /search + /normalize команды
5. `main.py` — регистрация хендлеров
6. `CLAUDE.md` — обновить документацию
7. Тест: прогнать /normalize, попробовать /search

---

## Что НЕ делаем сейчас (отложено)

- ❌ Проверка актуальности ссылок (HTTP запросы — сложно, мало пользы)
- ❌ GPT для определения типа контента (tg_gather уже определяет)
- ❌ Кластеризация (Этап 4, отдельный план)
- ❌ Рефакторинг SessionLocal → context manager (в бэклоге)

---

## Зависимости

- OpenAI API key (уже есть в .env — `OPENAI_API_KEY`)
- pgvector (уже установлен, embedding column создана)
- Данные в БД (686 фрагментов — есть)
- `ADMIN_USER_ID` — добавить в .env

Новых пакетов НЕ нужно (openai уже в requirements.txt).
