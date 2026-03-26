# telegram-gather — план изменений для сбора фрагментов

*Февраль 2026. Часть общего плана интеграции.*
*Связанные планы: plan_ayda_brain.md, plan_ayda_think.md*

---

## Роль в системе

telegram-gather остаётся тем же: Telethon userbot для транскрипций и ассистента. Добавляется **одна новая задача**: сбор фрагментов из Telegram и отправка в ayda_brain.

```
telegram-gather
│
├── handlers/voice_handler.py     ← как было (транскрипция)
├── assistant/                    ← как было (сводки чатов)
│
└── fragments/                    ← НОВОЕ
    ├── collector.py              # Сбор из saved + каналы
    └── sender.py                 # Отправка в ayda_brain API
```

telegram-gather **не** строит эмбеддинги, **не** кластеризует, **не** держит Chroma. Он только собирает сырые фрагменты и шлёт POST в ayda_brain.

---

## Что меняется

### 1. Новый модуль `fragments/`

```
telegram-gather/
├── fragments/
│   ├── __init__.py          # start_fragments(client, config)
│   ├── collector.py         # FragmentCollector: читает сообщения через Telethon
│   ├── sender.py            # BrainSender: POST /fragments в ayda_brain
│   └── config.py            # FragmentsConfig: источники, URL brain, интервал
```

### 2. fragments/collector.py — сбор

Использует **тот же Telethon client**, как assistant/collector.py.

```python
class FragmentCollector:
    def __init__(self, client: TelegramClient, config: FragmentsConfig):
        self.client = client
        self.config = config

    async def collect_new(self) -> list[dict]:
        """Собирает новые сообщения с момента последнего сбора."""
        fragments = []
        for source in self.config.sources:
            last_id = self._get_last_id(source)
            async for msg in self.client.iter_messages(
                source, min_id=last_id, reverse=True
            ):
                if not msg.text or len(msg.text.strip()) < 10:
                    continue
                fragments.append({
                    'external_id': f"{source}_{msg.id}",
                    'text': msg.text,
                    'created_at': msg.date.isoformat(),
                    'tags': self._extract_tags(msg.text),
                    'metadata': {
                        'telegram_msg_id': msg.id,
                        'chat': str(source)
                    }
                })
            if fragments:
                max_id = max(
                    f['metadata']['telegram_msg_id']
                    for f in fragments
                    if f['metadata']['chat'] == str(source)
                )
                self._save_last_id(source, max_id)
        return fragments

    async def collect_all(self) -> list[dict]:
        """Первичный полный сбор. Запускается один раз."""
        fragments = []
        for source in self.config.sources:
            async for msg in self.client.iter_messages(source, reverse=True):
                if not msg.text or len(msg.text.strip()) < 10:
                    continue
                fragments.append({
                    'external_id': f"{source}_{msg.id}",
                    'text': msg.text,
                    'created_at': msg.date.isoformat(),
                    'tags': self._extract_tags(msg.text),
                    'metadata': {
                        'telegram_msg_id': msg.id,
                        'chat': str(source)
                    }
                })
        return fragments

    def _extract_tags(self, text: str) -> list[str]:
        return [w for w in text.split() if w.startswith('#')]

    def _get_last_id(self, source: str) -> int:
        # Из data/fragments_state.json
        ...

    def _save_last_id(self, source: str, msg_id: int):
        # В data/fragments_state.json
        ...
```

### 3. fragments/sender.py — отправка в ayda_brain

```python
import aiohttp
import logging

BATCH_SIZE = 200  # максимум фрагментов за один POST

class BrainSender:
    def __init__(self, brain_url: str):
        self.brain_url = brain_url

    async def send(self, fragments: list[dict]) -> dict:
        """Отправляет фрагменты в ayda_brain пачками по BATCH_SIZE."""
        total_indexed = 0
        total_skipped = 0

        for i in range(0, len(fragments), BATCH_SIZE):
            batch = fragments[i:i + BATCH_SIZE]
            result = await self._send_batch(batch)
            total_indexed += result.get('indexed', 0)
            total_skipped += result.get('duplicates_skipped', 0)
            logging.info(
                f"Batch {i//BATCH_SIZE + 1}: "
                f"sent {len(batch)}, indexed {result.get('indexed', 0)}"
            )

        return {
            "indexed": total_indexed,
            "duplicates_skipped": total_skipped,
            "total_in_db": result.get('total_in_db', 0)
        }

    async def _send_batch(self, batch: list[dict]) -> dict:
        """Отправляет одну пачку."""
        payload = {
            "source": "telegram",
            "fragments": batch
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.brain_url}/fragments",
                json=payload
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    raise Exception(f"Brain API error {resp.status}: {text}")

    async def health_check(self) -> bool:
        """Проверяет доступность ayda_brain."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.brain_url}/health") as resp:
                    return resp.status == 200
        except:
            return False
```

### 4. fragments/config.py

```python
from dataclasses import dataclass

@dataclass
class FragmentsConfig:
    sources: list[str]                    # ['me', 'my_channel']
    brain_url: str = 'http://localhost:8100'
    state_file: str = 'data/fragments_state.json'
    collect_interval_hours: int = 24      # как часто собирать новые
    min_text_length: int = 10
    batch_size: int = 200                 # фрагментов за один POST
```

### 5. fragments/__init__.py — запуск

```python
import asyncio
import logging

async def start_fragments(client, brain_url='http://localhost:8100'):
    """Запускает фоновый сбор фрагментов."""
    from fragments.config import FragmentsConfig
    from fragments.collector import FragmentCollector
    from fragments.sender import BrainSender

    config = FragmentsConfig(
        sources=['me'],    # TODO: загружать из fragments_config.yaml
        brain_url=brain_url
    )
    collector = FragmentCollector(client, config)
    sender = BrainSender(config.brain_url)

    # Проверяем что brain доступен
    if not await sender.health_check():
        logging.warning("ayda_brain недоступен, fragments collection отключён")
        return None

    async def background_loop():
        # Первый запуск — собрать новое
        try:
            fragments = await collector.collect_new()
            if fragments:
                result = await sender.send(fragments)
                logging.info(f"Fragments sent: {result}")
            else:
                logging.info("No new fragments to collect")
        except Exception as e:
            logging.error(f"Fragments collection error: {e}")

        # Далее — по расписанию
        while True:
            await asyncio.sleep(config.collect_interval_hours * 3600)
            try:
                fragments = await collector.collect_new()
                if fragments:
                    result = await sender.send(fragments)
                    logging.info(f"Fragments sent: {result}")
            except Exception as e:
                logging.error(f"Fragments collection error: {e}")

    task = asyncio.create_task(background_loop())
    logging.info("Fragments collection started")
    return task
```

### 6. Интеграция в main.py

```python
# После start_assistant():
from fragments import start_fragments

brain_url = os.getenv("BRAIN_URL", "http://localhost:8100")
fragments_task = await start_fragments(client, brain_url=brain_url)
```

---

## Как работает сбор — детально

### Первичный сбор (один раз)

Через CLI-скрипт `collect_fragments.py`:

```
python collect_fragments.py --sources me my_channel --brain-url http://localhost:8100
```

1. Подключается через существующую Telethon-сессию
2. Читает **все** сообщения из каждого источника (saved, канал)
3. Фильтрует: только текст, длина > 10 символов
4. Разбивает на пачки по 200
5. Последовательно шлёт POST /fragments в brain
6. Сохраняет last_id для каждого источника

**Примерные объёмы:**

| Источник | Сообщений | Пачек по 200 | Размер JSON |
|----------|-----------|-------------|-------------|
| Saved messages | 500-3000 | 3-15 | 150 КБ — 1.5 МБ |
| Приватный канал | 600-1200 | 3-6 | 200-600 КБ |
| Другой канал | 100-1000 | 1-5 | 50-500 КБ |
| **Итого** | **2000-5000** | **10-25** | **~2-3 МБ** |

Время первичного сбора: зависит от скорости Ollama (эмбеддинги на стороне brain). На ноутбуке без GPU — ~1-3 секунды на фрагмент, итого 30-150 минут для 2000-5000 фрагментов. Можно запустить и пойти пить чай.

### Ежедневный фоновый сбор

Фоновый цикл в `start_fragments()`:

1. Раз в 24 часа просыпается
2. Читает новые сообщения (min_id > last_id)
3. Обычно 0-10 новых фрагментов в день
4. Одна пачка, один POST, секунды

### Что НЕ собирается

- Сообщения короче 10 символов ("ок", "да", ссылки)
- Медиа без текста (фото, видео, стикеры)
- Сервисные сообщения (join/leave/pin)

---

## Новые env-переменные

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `BRAIN_URL` | `http://localhost:8100` | URL ayda_brain API |

Добавить в `.env`.

---

## Состояние сбора

Файл `data/fragments_state.json` (рядом с `data/assistant_state.json`):

```json
{
  "last_ids": {
    "me": 45678,
    "my_channel": 1234
  },
  "last_collected_at": "2026-02-20T10:00:00"
}
```

Добавить в `.gitignore` (если `data/` ещё не целиком).

---

## Новые зависимости

Никаких! `aiohttp` уже есть в requirements.txt.

---

## Что НЕ меняется

- `handlers/voice_handler.py` — без изменений
- `assistant/` — без изменений
- `services/` — без изменений
- `main.py` — +3 строки (import + запуск fragments)
- `config.py` — +1 переменная (BRAIN_URL)

---

## Порядок реализации

### Этап 1 — Collector
- [ ] Создать `fragments/` модуль (4 файла)
- [ ] FragmentCollector: сбор из `'me'` (saved messages)
- [ ] Тест: собрать 10 последних saved, вывести в консоль

### Этап 2 — Sender
- [ ] BrainSender: POST в ayda_brain (с пачками по 200)
- [ ] Health check перед запуском
- [ ] Тест: отправить собранные фрагменты (ayda_brain должен быть запущен)

### Этап 3 — Фоновый цикл
- [ ] start_fragments() в main.py
- [ ] fragments_state.json: сохранение/чтение last_id
- [ ] Тест: запустить, подождать, проверить что новые сообщения подхватываются

### Этап 4 — CLI для полного сбора
- [ ] collect_fragments.py
- [ ] Первичный сбор всей истории saved + канал

### Этап 5 — Дополнительные источники
- [ ] Конфиг: sources из yaml или env
- [ ] Добавить приватный канал
- [ ] Другие каналы по необходимости

---

*Документ создан: февраль 2026*
*Путь: оба проекта → docs/task_tracker/to_do/plan_tg_gather.md*
