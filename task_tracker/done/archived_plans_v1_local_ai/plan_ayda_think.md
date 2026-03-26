# ayda_think — план изменений для работы с артефактами

*Февраль 2026. Часть общего плана интеграции.*
*Связанные планы: plan_ayda_brain.md, plan_tg_gather.md*

---

## Роль в системе

ayda_think остаётся Telegram-ботом для заметок (Google Sheets) + добавляет **команды для работы с артефактами** через ayda_brain API.

```
Пользователь
    │
    ├── /save, текст, голосовое    →  как сейчас → Google Sheets
    │
    └── /search, /chains, /pattern →  НОВОЕ → ayda_brain API
                                              (http://localhost:8100)
```

ayda_think **не** хранит эмбеддинги, **не** работает с Chroma напрямую. Ходит к ayda_brain по HTTP. Получает фрагменты, цепочки, артефакты — и показывает пользователю.

---

## Глоссарий (общий для всех трёх сервисов)

| Термин | Что это |
|--------|---------|
| **Fragment** (фрагмент) | Сырая мысль, заметка, обрывок. Приходит из tg-gather (или другого источника). |
| **Artifact** (артефакт) | Результат работы brain. Найденная связь, синтезированная мысль, достроенный образ. |
| **Chain** (цепочка) | Группа семантически близких фрагментов, найденная кластеризацией. |

---

## Что меняется

### 1. Новый сервис `services/brain_client.py`

HTTP-клиент к ayda_brain. Название `brain_client` а не `crystal_service` — потому что это клиент к конкретному API, а не бизнес-логика.

```python
import aiohttp
import logging

class BrainClient:
    def __init__(self, brain_url: str):
        self.brain_url = brain_url

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """Семантический поиск по фрагментам через ayda_brain."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.brain_url}/search",
                params={"q": query, "limit": limit}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", [])
                logging.error(f"Brain search error: {resp.status}")
                return []

    async def get_chains(self, min_size: int = 3) -> list[dict]:
        """Список цепочек."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.brain_url}/chains",
                params={"min_size": min_size}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("chains", [])
                return []

    async def get_chain(self, chain_id: int) -> dict | None:
        """Конкретная цепочка с фрагментами и артефактом."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.brain_url}/chains/{chain_id}"
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def get_pattern(self, topic: str, limit: int = 20) -> dict | None:
        """Эволюция темы."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.brain_url}/pattern",
                params={"topic": topic, "limit": limit}
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def synthesize(self, chain_id: int) -> dict | None:
        """Синтез артефакта для цепочки."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.brain_url}/synthesize",
                json={"chain_id": chain_id}
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def is_available(self) -> bool:
        """Проверка доступности brain."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.brain_url}/health") as resp:
                    return resp.status == 200
        except:
            return False
```

### 2. Новый хендлер `bot/brain_handler.py`

```python
from telegram import Update
from telegram.ext import ContextTypes

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/search [запрос] — семантический поиск по фрагментам."""
    if not context.args:
        await update.message.reply_text("Использование: /search <запрос>")
        return

    brain = context.bot_data.get('brain_client')
    if not brain:
        await update.message.reply_text("Brain service не настроен.")
        return

    query = ' '.join(context.args)
    await update.message.reply_text(f"Ищу: «{query}»...")

    try:
        results = await brain.search(query, limit=5)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return

    if not results:
        await update.message.reply_text("Ничего не найдено.")
        return

    lines = [f"Результаты по «{query}»:\n"]
    for i, r in enumerate(results, 1):
        date = r.get('created_at', '')[:10]
        text = r.get('text', '')[:120]
        sim = r.get('similarity', 0)
        lines.append(f"{i}. [{date}] {text}")
        lines.append(f"   Близость: {sim:.0%}\n")

    await update.message.reply_text('\n'.join(lines))


async def chains_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chains — топ цепочек мыслей."""
    brain = context.bot_data.get('brain_client')
    if not brain:
        await update.message.reply_text("Brain service не настроен.")
        return

    try:
        chains = await brain.get_chains(min_size=2)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return

    if not chains:
        await update.message.reply_text("Цепочки не найдены. Попробуй позже.")
        return

    lines = ["Цепочки мыслей:\n"]
    for c in chains[:10]:
        lines.append(
            f"[{c['id']}] {c['size']} мыслей — {c.get('preview', '...')}\n"
            f"    {c['first_date']} → {c['last_date']}\n"
            f"    /chain {c['id']}\n"
        )

    await update.message.reply_text('\n'.join(lines))


async def chain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chain N — конкретная цепочка + артефакт."""
    brain = context.bot_data.get('brain_client')
    if not brain:
        await update.message.reply_text("Brain service не настроен.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /chain <номер>")
        return

    try:
        chain_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Номер цепочки должен быть числом.")
        return

    try:
        chain = await brain.get_chain(chain_id)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return

    if not chain:
        await update.message.reply_text(f"Цепочка #{chain_id} не найдена.")
        return

    lines = [f"Цепочка #{chain_id}:\n"]
    for f in chain.get('fragments', []):
        date = f.get('created_at', '')[:10]
        text = f.get('text', '')[:150]
        lines.append(f"→ [{date}] {text}\n")

    artifact = chain.get('artifact')
    if artifact:
        lines.append(f"\n--- Артефакт ---")
        lines.append(artifact.get('next_thought', ''))
    else:
        lines.append(f"\nАртефакт ещё не создан. (будет после /synthesize)")

    await update.message.reply_text('\n'.join(lines))


async def pattern_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pattern [тема] — как менялась мысль о теме."""
    brain = context.bot_data.get('brain_client')
    if not brain:
        await update.message.reply_text("Brain service не настроен.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /pattern <тема>")
        return

    topic = ' '.join(context.args)

    try:
        result = await brain.get_pattern(topic)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
        return

    if not result or not result.get('timeline'):
        await update.message.reply_text(f"Не нашёл мыслей по теме «{topic}».")
        return

    span = result.get('span_days', 0)
    lines = [f"Эволюция мысли «{topic}» ({span} дней):\n"]
    for t in result['timeline']:
        date = t.get('created_at', '')[:10]
        text = t.get('text', '')[:120]
        lines.append(f"→ [{date}] {text}\n")

    await update.message.reply_text('\n'.join(lines))
```

### 3. Регистрация в main.py

```python
from telegram.ext import CommandHandler
from bot.brain_handler import (
    search_command, chains_command, chain_command, pattern_command
)
from services.brain_client import BrainClient

# В main():

# Инициализация brain client
brain_url = config.get("brain_url", "http://localhost:8100")
brain_client = BrainClient(brain_url=brain_url)
application.bot_data['brain_client'] = brain_client

# Регистрация хендлеров
application.add_handler(CommandHandler("search", search_command))
application.add_handler(CommandHandler("chains", chains_command))
application.add_handler(CommandHandler("chain", chain_command))
application.add_handler(CommandHandler("pattern", pattern_command))
```

### 4. Новая env-переменная

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `BRAIN_URL` | `http://localhost:8100` | URL ayda_brain API |

Добавить в `config.py`:
```python
"brain_url": os.getenv("BRAIN_URL", "http://localhost:8100")
```

---

## Новые зависимости

Добавить в `requirements.txt`:
```
aiohttp>=3.9.0
```

(chromadb и ollama НЕ нужны — всё через HTTP к brain)

---

## Что НЕ меняется

- Вся текущая логика заметок (Google Sheets) — без изменений
- Mini App — без изменений
- storage/ — без изменений
- api_server.py — без изменений

---

## Двойная запись (будущее, бэклог)

Когда всё заработает стабильно, можно добавить: при сохранении заметки через бот — параллельно отправлять её как фрагмент в brain. Тогда заметки из бота тоже попадут в семантический поиск.

```python
# В note_handler.py (будущее):
async def handle_message(update, context):
    # ... сохранение в Sheets как сейчас ...

    # + отправка в brain как фрагмент
    brain = context.bot_data.get('brain_client')
    if brain:
        await brain.send_fragment(text, tags, msg_date)
```

Пока дублирование ок — brain дедуплицирует по `external_id`.

---

## Порядок реализации

### Этап 1 — Brain Client
- [ ] Создать `services/brain_client.py`
- [ ] Метод `is_available()` — проверка brain
- [ ] Метод `search()` — семантический поиск

### Этап 2 — Команда /search
- [ ] Создать `bot/brain_handler.py`
- [ ] Реализовать `search_command`
- [ ] Зарегистрировать в `main.py`
- [ ] Тест: `/search AI` → результаты из brain

### Этап 3 — Цепочки
- [ ] Команда `/chains`
- [ ] Команда `/chain N`

### Этап 4 — Паттерны
- [ ] Команда `/pattern`

### Этап 5 (бэклог)
- [ ] Двойная запись (заметки → brain как фрагменты)
- [ ] Вкладка "Артефакты" в Mini App
- [ ] Команда `/hot`

---

*Документ создан: февраль 2026*
*Путь: оба проекта → docs/task_tracker/to_do/plan_ayda_think.md*
