# Telegram API для работы с каналами и Saved Messages

## Проблема
Накапливается полезная информация в:
1. Подписках на каналы — не успеваем читать
2. Saved Messages — сохраняем и забываем

**Решение:** создать "рекомендательную ленту" или Tinder-подобный интерфейс для переоткрытия контента.

---

## Два типа Telegram API

### 1. Bot API (HTTP)
- **Ограничения:** Бот может читать только сообщения, где он упомянут или является админом
- **Не подходит** для твоей задачи — бот не видит твои подписки и Saved Messages

### 2. MTProto API (User API) ✅
- **Полный доступ** как у настоящего клиента Telegram
- Можно читать все каналы, Saved Messages, историю чатов
- **Это то, что тебе нужно**

---

## Библиотеки для работы с MTProto

### Python (рекомендую)

| Библиотека | GitHub Stars | Особенности |
|------------|--------------|-------------|
| **Telethon** | 10k+ | Самая популярная, отличная документация |
| **Pyrogram** | 5k+ | Современная, async-first, чистый API |

**Мой выбор: Pyrogram** — более чистый API, лучше документирована работа с Saved Messages.

### JavaScript
- **GramJS** — порт Telethon на TypeScript
- **telegram-mtproto** — низкоуровневая библиотека

### Другие языки
- **Go:** gotd/td
- **C#:** WTelegramClient
- **PHP:** MadelineProto

---

## Получение API credentials

1. Зайти на https://my.telegram.org
2. Войти с номером телефона
3. Перейти в "API development tools"
4. Создать приложение, получить:
   - `api_id` (число)
   - `api_hash` (строка)

---

## Ключевые API методы

### 1. Получить список всех диалогов (чаты + каналы)

**Метод:** `messages.getDialogs`

**Документация:** https://core.telegram.org/method/messages.getDialogs

```python
# Pyrogram
async with app:
    async for dialog in app.get_dialogs():
        if dialog.chat.type == ChatType.CHANNEL:
            print(f"Канал: {dialog.chat.title}")
```

**Параметры:**
- `offset_date` — для пагинации
- `offset_id` — ID последнего загруженного
- `limit` — количество (макс ~100)
- `folder_id` — для фильтрации по папкам

**Возвращает:**
- `dialogs` — список диалогов
- `messages` — последние сообщения
- `chats` — информация о чатах/каналах
- `users` — информация о пользователях

---

### 2. Получить историю сообщений канала

**Метод:** `messages.getHistory`

**Документация:** https://core.telegram.org/method/messages.getHistory

```python
# Pyrogram
async for message in app.get_chat_history(channel_id, limit=100):
    print(message.text or message.caption)
```

**Параметры:**
- `peer` — ID канала/чата
- `offset_id` — для пагинации
- `offset_date` — фильтр по дате
- `limit` — количество сообщений
- `min_id` / `max_id` — диапазон ID

---

### 3. Работа с Saved Messages

**Ключевой момент:** Saved Messages = чат с самим собой (`inputPeerSelf` или `"me"`)

#### Получить все сообщения из Saved Messages

**Метод:** `messages.getHistory` с `peer=self`

```python
# Pyrogram — получить Saved Messages
async for message in app.get_chat_history("me", limit=100):
    print(message.text)
```

#### Новые методы для организованных Saved Messages (2024+)

Telegram добавил систему "Saved Dialogs" — сообщения группируются по источнику:

| Метод | Описание | Документация |
|-------|----------|--------------|
| `messages.getSavedDialogs` | Список всех saved dialogs | https://core.telegram.org/method/messages.getSavedDialogs |
| `messages.getSavedHistory` | История конкретного saved dialog | https://core.telegram.org/method/messages.getSavedHistory |
| `messages.getPinnedSavedDialogs` | Закреплённые saved dialogs | https://core.telegram.org/method/messages.getPinnedSavedDialogs |
| `messages.deleteSavedHistory` | Удалить saved dialog | https://core.telegram.org/method/messages.deleteSavedHistory |

```python
# Telethon — получить Saved Dialogs
result = await client(functions.messages.GetSavedDialogsRequest(
    offset_date=0,
    offset_id=0,
    offset_peer=types.InputPeerEmpty(),
    limit=100,
    hash=0
))
```

---

### 4. Поиск по сообщениям

**Метод:** `messages.search`

**Документация:** https://core.telegram.org/method/messages.search

```python
# Pyrogram — поиск в канале
async for message in app.search_messages(channel_id, query="python"):
    print(message.text)
```

**Параметры:**
- `peer` — где искать
- `q` — поисковый запрос
- `filter` — тип контента (фото, видео, документы и т.д.)
- `min_date` / `max_date` — диапазон дат
- `from_id` — от конкретного автора

#### Доступные фильтры (MessagesFilter)

| Фильтр | Описание |
|--------|----------|
| `inputMessagesFilterEmpty` | Без фильтра |
| `inputMessagesFilterPhotos` | Только фото |
| `inputMessagesFilterVideo` | Только видео |
| `inputMessagesFilterPhotoVideo` | Фото и видео |
| `inputMessagesFilterDocument` | Документы |
| `inputMessagesFilterUrl` | Ссылки |
| `inputMessagesFilterGif` | GIF |
| `inputMessagesFilterVoice` | Голосовые |
| `inputMessagesFilterMusic` | Музыка |
| `inputMessagesFilterPinned` | Закреплённые |
| `inputMessagesFilterMyMentions` | Упоминания |

**Документация фильтров:** https://core.telegram.org/type/MessagesFilter

---

### 5. Глобальный поиск

**Метод:** `messages.searchGlobal`

```python
# Поиск по всем чатам и каналам
async for message in app.search_global(query="machine learning"):
    print(f"{message.chat.title}: {message.text[:100]}")
```

---

## Пример: Базовый скрипт для сбора контента

```python
from pyrogram import Client
from pyrogram.enums import ChatType
import asyncio

api_id = "YOUR_API_ID"
api_hash = "YOUR_API_HASH"

app = Client("my_session", api_id=api_id, api_hash=api_hash)

async def collect_channel_posts():
    """Собрать посты из всех каналов"""
    posts = []
    
    async with app:
        # Получаем все диалоги
        async for dialog in app.get_dialogs():
            # Фильтруем только каналы
            if dialog.chat.type == ChatType.CHANNEL:
                channel = dialog.chat
                print(f"📺 Канал: {channel.title}")
                
                # Получаем последние 50 постов
                async for message in app.get_chat_history(
                    channel.id, 
                    limit=50
                ):
                    if message.text or message.caption:
                        posts.append({
                            "channel": channel.title,
                            "channel_id": channel.id,
                            "message_id": message.id,
                            "date": message.date,
                            "text": message.text or message.caption,
                            "has_media": bool(message.media),
                            "views": message.views
                        })
                
                # Пауза между каналами (flood protection)
                await asyncio.sleep(1)
    
    return posts

async def collect_saved_messages():
    """Собрать Saved Messages"""
    saved = []
    
    async with app:
        async for message in app.get_chat_history("me", limit=200):
            saved.append({
                "message_id": message.id,
                "date": message.date,
                "text": message.text or message.caption,
                "has_media": bool(message.media),
                "forward_from": message.forward_from_chat.title 
                    if message.forward_from_chat else None
            })
    
    return saved

if __name__ == "__main__":
    # Собрать посты каналов
    channel_posts = asyncio.run(collect_channel_posts())
    print(f"Собрано {len(channel_posts)} постов из каналов")
    
    # Собрать Saved Messages
    saved = asyncio.run(collect_saved_messages())
    print(f"Собрано {len(saved)} сохранённых сообщений")
```

---

## Rate Limits и защита от блокировки

### ⚠️ Критически важно

Telegram агрессивно борется с автоматизацией. Нарушение лимитов приводит к:
- `FLOOD_WAIT_X` — бан на X секунд
- Временная блокировка аккаунта
- Полная блокировка аккаунта (в крайних случаях)

### Известные лимиты

| Действие | Лимит |
|----------|-------|
| Запросы в секунду | ~1-2 запроса |
| `getHistory` | ~30 запросов в минуту |
| Сообщений за запрос | max 100 |
| Общий rate | Динамический, зависит от "репутации" |

### Стратегии защиты

```python
import asyncio
from pyrogram.errors import FloodWait

async def safe_get_history(client, chat_id, limit=100):
    """Безопасное получение истории с обработкой FloodWait"""
    try:
        messages = []
        async for msg in client.get_chat_history(chat_id, limit=limit):
            messages.append(msg)
        return messages
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value} секунд")
        await asyncio.sleep(e.value + 1)
        return await safe_get_history(client, chat_id, limit)

# Между запросами к разным каналам
await asyncio.sleep(2)  # 2 секунды между каналами

# Между батчами
await asyncio.sleep(60)  # 1 минута между большими батчами
```

### Рекомендации

1. **Используй официальные api_id/api_hash** — создай через https://my.telegram.org
2. **Добавь случайные задержки** — `random.uniform(1, 3)` секунды
3. **Инкрементальная загрузка** — не грузи всё сразу, а постепенно
4. **Кэшируй локально** — храни уже загруженное в БД
5. **Используй offset** — загружай только новое

---

## Архитектура приложения "Tinder для контента"

### Компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│                        TELEGRAM API                              │
│                    (MTProto / Pyrogram)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SYNC SERVICE                                 │
│  • Периодическая синхронизация каналов                          │
│  • Обработка FLOOD_WAIT                                          │
│  • Инкрементальные updates                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LOCAL DATABASE                              │
│  • SQLite / PostgreSQL                                          │
│  • posts: id, channel, text, date, media_type, is_seen, rating │
│  • channels: id, title, priority, last_sync                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RECOMMENDATION ENGINE                          │
│  • Ранжирование по дате, популярности, каналу                   │
│  • ML-модель на основе свайпов (опционально)                    │
│  • Фильтры: тип контента, канал, дата                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  • Tinder-like UI (swipe left/right)                            │
│  • React / React Native / Telegram Mini App                     │
│  • Действия: skip, save, comment, share                         │
└─────────────────────────────────────────────────────────────────┘
```

### Схема базы данных

```sql
-- Каналы
CREATE TABLE channels (
    id INTEGER PRIMARY KEY,
    telegram_id BIGINT UNIQUE,
    title TEXT,
    username TEXT,
    priority INTEGER DEFAULT 5,  -- 1-10, влияет на частоту показа
    last_sync_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Посты
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id),
    telegram_message_id INTEGER,
    text TEXT,
    caption TEXT,
    media_type TEXT,  -- photo, video, document, etc.
    media_url TEXT,
    views INTEGER,
    post_date TIMESTAMP,
    sync_date TIMESTAMP,
    
    -- User interaction
    is_seen BOOLEAN DEFAULT FALSE,
    is_saved BOOLEAN DEFAULT FALSE,
    rating INTEGER,  -- -1 (dislike), 0 (skip), 1 (like)
    user_comment TEXT,
    seen_at TIMESTAMP,
    
    UNIQUE(channel_id, telegram_message_id)
);

-- Saved Messages
CREATE TABLE saved_messages (
    id INTEGER PRIMARY KEY,
    telegram_message_id INTEGER UNIQUE,
    text TEXT,
    media_type TEXT,
    forward_from_channel TEXT,
    forward_from_channel_id BIGINT,
    original_date TIMESTAMP,
    saved_date TIMESTAMP,
    
    is_processed BOOLEAN DEFAULT FALSE,
    rating INTEGER,
    user_tags TEXT,  -- JSON array
    user_note TEXT
);

-- История взаимодействий
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id),
    action TEXT,  -- 'view', 'swipe_left', 'swipe_right', 'save', 'comment'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Варианты реализации фронтенда

### 1. Telegram Mini App (рекомендую)

**Плюсы:**
- Нативная интеграция с Telegram
- Не нужен отдельный логин
- Доступно всем пользователям Telegram

**Стек:** React + Telegram Mini Apps SDK

### 2. Web App

**Стек:** React/Vue/Svelte + API backend

### 3. Desktop App

**Стек:** Electron или Tauri

### 4. CLI Tool

Для гиков — простой терминальный интерфейс:

```bash
$ tg-review
📺 Channel: AI Daily
📝 "GPT-5 leaked benchmarks show..."
[👎 skip] [❤️ save] [💬 comment] [➡️ next]
```

---

## Дополнительные фичи

### 1. Отметка прочитанным в Telegram

**Метод:** `messages.readHistory`

```python
# Отметить канал прочитанным
await client.read_chat_history(channel_id)
```

### 2. Пересылка в Saved Messages

**Метод:** `messages.forwardMessages`

```python
# Переслать в Saved Messages
await app.forward_messages("me", channel_id, message_id)
```

### 3. Получение Updates в реальном времени

```python
from pyrogram import Client, filters

@app.on_message(filters.channel)
async def new_channel_post(client, message):
    # Новый пост в канале — сразу добавляем в очередь
    save_to_database(message)
```

---

## Сложности и подводные камни

### 1. Авторизация
- Требуется номер телефона и код
- Session файл нужно хранить безопасно
- При смене устройства нужна повторная авторизация

### 2. Rate Limits
- Неизвестны точные лимиты
- Динамически меняются
- Требуется робастная обработка FLOOD_WAIT

### 3. Типы контента
- Текст может быть в `message.text` или `message.caption`
- Медиа требует отдельной загрузки
- Форматирование (entities) нужно парсить отдельно

### 4. Удалённые сообщения
- Telegram не сообщает об удалённых постах
- Нужна проверка при отображении

### 5. Приватные каналы
- Работают так же, но нужна подписка
- Нельзя поделиться ссылкой на пост

---

## Полезные ссылки

### Официальная документация
- [MTProto API Overview](https://core.telegram.org/api)
- [Available Methods](https://core.telegram.org/methods)
- [Available Types](https://core.telegram.org/schema)
- [Saved Messages](https://core.telegram.org/api/saved-messages)
- [Search](https://core.telegram.org/api/search)
- [Error Handling](https://core.telegram.org/api/errors)

### Библиотеки
- [Pyrogram Docs](https://docs.pyrogram.org/)
- [Telethon Docs](https://docs.telethon.dev/)
- [GramJS](https://gram.js.org/)

### Конкретные методы API
- [messages.getDialogs](https://core.telegram.org/method/messages.getDialogs)
- [messages.getHistory](https://core.telegram.org/method/messages.getHistory)
- [messages.getSavedDialogs](https://core.telegram.org/method/messages.getSavedDialogs)
- [messages.getSavedHistory](https://core.telegram.org/method/messages.getSavedHistory)
- [messages.search](https://core.telegram.org/method/messages.search)
- [channels.getMessages](https://core.telegram.org/method/channels.getMessages)

---

## Quick Start

```bash
# 1. Установка
pip install pyrogram tgcrypto

# 2. Создать файл config.py
# api_id = 12345
# api_hash = "your_hash"

# 3. Первый запуск — авторизация
python -c "
from pyrogram import Client
app = Client('my_session', api_id=12345, api_hash='your_hash')
app.run()
"

# 4. Готово! Session сохранён, можно работать с API
```

---

## Резюме

| Что нужно | Решение |
|-----------|---------|
| Доступ к подпискам | MTProto API + `messages.getDialogs` |
| Чтение каналов | `messages.getHistory` по каждому каналу |
| Saved Messages | `messages.getHistory("me")` или `messages.getSavedHistory` |
| Поиск | `messages.search` с фильтрами |
| Библиотека | Pyrogram (Python) или GramJS (JS) |
| Rate limits | 1-2 req/sec, обработка FLOOD_WAIT |

Твоя идея отличная и полностью реализуема! Главное — аккуратно работать с rate limits и не пытаться загрузить всё сразу.
