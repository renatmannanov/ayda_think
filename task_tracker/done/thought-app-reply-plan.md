# Thought App — План реализации связей по реплаям

## Обзор

Добавляем второй тип связей между записями — по реплаям (цепочки ответов).
Также обновляем UI навигации.

---

## Изменения в UI навигации

### Основной экран (до)
```
│  🎯 Фокус  ✓ Готово      [#5] [↩3]      ←  →  ↗ │
```

### Основной экран (после)
```
│  🎯  ✓           [#5] [↗3]           ←  →  ↗ │
```

**Изменения:**
- Убрать текст "Фокус" и "Готово" — оставить только иконки `🎯` и `✓`
- Кнопки связей в центре:
  - `[#N]` — вход в связи по тегам
  - `[↗N]` — вход в связи по реплаям (иконка `↗`)

---

### Режим связей по тегам
```
│  🎯  ✓          ↑  ↓           ←  ↗ │
```

**Изменения:**
- Добавить `↑` — предыдущая связь по тегам
- `↓` — следующая связь по тегам

---

### Режим связей по реплаям
```
│  🎯  ✓       ↑3  ↓1  ↔2       ←  ↗ │
```

**Кнопки навигации:**
- `↑N` — к родителю (N = количество предков)
- `↓N` — к первому ответу (N = количество ответов)
- `↔N` — переключить ветку (N = количество веток на уровне)
- `←` — вернуться к исходной записи
- `↗` — открыть сообщение в Telegram

---

## Бэкенд

### 1. RelationService — новые методы

**Файл:** `services/relation_service.py`

```python
async def get_reply_chain(
    self,
    note_id: str,
    spreadsheet_id: str
) -> Dict[str, Any]:
    """
    Построить цепочку реплаев для записи.

    Returns:
        {
            'chain': [...],           # Все записи в цепочке
            'current_index': int,     # Позиция текущей записи
            'stats': {
                'up': int,            # Количество предков
                'down': int,          # Количество потомков + прямых ответов
                'branches': int,      # Количество веток на текущем уровне
                'total': int          # Размер всего дерева
            }
        }
    """

def _find_note_by_telegram_id(
    self,
    telegram_message_id: str,
    notes: List[Dict]
) -> Optional[Dict]:
    """Найти запись по Telegram Message ID."""

def _get_ancestors(self, note: Dict, notes: List[Dict]) -> List[Dict]:
    """Получить всех предков (путь вверх до корня)."""

def _get_descendants(self, note: Dict, notes: List[Dict]) -> List[Dict]:
    """Получить потомков по первой ветке."""

def _get_replies(self, telegram_message_id: str, notes: List[Dict]) -> List[Dict]:
    """Получить прямые ответы на запись."""

def _get_siblings(self, note: Dict, notes: List[Dict]) -> List[Dict]:
    """Получить записи на том же уровне (siblings)."""

def _count_tree_size(self, root: Dict, notes: List[Dict]) -> int:
    """Посчитать размер всего дерева от корня."""
```

### 2. API endpoint

**Файл:** `api_server.py`

```python
@app.get("/api/notes/{note_id}/replies", response_model=ReplyChainResponse)
async def get_reply_chain(note_id: str, user_id: int = Query(...)):
    """
    Get reply chain for the specified note.

    Returns chain of notes connected by replies,
    with navigation stats for tree traversal.
    """
```

### 3. Schemas

**Файл:** `schemas.py`

```python
class ReplyChainStats(BaseModel):
    """Stats for reply chain navigation."""
    up: int              # Количество предков
    down: int            # Количество ответов + потомков
    branches: int        # Количество веток на уровне
    total: int           # Размер всего дерева

class ReplyChainNote(BaseModel):
    """Note in reply chain with position info."""
    id: str
    telegram_message_id: str
    created_at: str
    content: str
    tags: str
    reply_to_message_id: Optional[str]
    message_type: str
    status: str

class ReplyChainResponse(BaseModel):
    """Response for reply chain endpoint."""
    chain: List[ReplyChainNote]
    current_index: int
    stats: ReplyChainStats
    note_id: str
```

---

## Фронтенд

### 4. state.js

**Добавить состояние:**
```javascript
// Reply related mode
replyChain: [],           // Все записи в цепочке
replyIndex: 0,            // Текущая позиция
replyBranches: [],        // Доступные ветки на уровне
replyBranchIndex: 0,      // Индекс текущей ветки
replyStats: null,         // { up, down, branches, total }
```

**Добавить методы:**
```javascript
enterReplyMode()
exitReplyMode()
setReplyChain(chain, currentIndex, stats)
replyUp()
replyDown()
replyBranch()
getReplyStats()
```

### 5. api.js

```javascript
async fetchReplyChain(noteId, userId) {
    const response = await fetch(`/api/notes/${noteId}/replies?user_id=${userId}`);
    return response.json();
}
```

### 6. ui.js

**Обновить renderActions():**
- Основной режим: показать `[#N]` и `[↩N]` в центре
- Режим тегов: заменить `↓` на `[#N]`
- Режим реплаев: показать `↑N ↓N ↔N`

**Обновить кнопки:**
- Убрать текст "Фокус" и "Готово"
- Оставить только иконки `🎯` и `✓`

### 7. app.js

**Добавить хендлеры:**
```javascript
handleEnterReplyRelated()
handleReplyUp()
handleReplyDown()
handleReplyBranch()
handleExitReplyMode()
```

---

## Логика поиска связей

### Поиск по Telegram Message ID

Связи хранятся как `reply_to_message_id` (Telegram ID).
Для поиска используем `telegram_message_id` (колонка B).

```python
# Найти родителя
parent = find(notes, n => n.telegram_message_id == current.reply_to_message_id)

# Найти детей
children = filter(notes, n => n.reply_to_message_id == current.telegram_message_id)
```

### Обработка отсутствующего родителя

Если `reply_to_message_id` указан, но записи нет — считаем текущую запись корнем своей цепочки.

---

## Порядок реализации

1. **UI навигации** — обновить кнопки (можно сделать без бэка)
2. **Schemas** — добавить новые модели
3. **RelationService** — добавить методы для реплаев
4. **API endpoint** — добавить `/replies`
5. **Frontend state** — добавить состояние реплаев
6. **Frontend api** — добавить `fetchReplyChain`
7. **Frontend ui** — рендер навигации по реплаям
8. **Frontend app** — хендлеры навигации
9. **Тестирование**

---

## Файлы для изменения

| Файл | Изменения |
|------|-----------|
| `services/relation_service.py` | Новые методы для реплаев |
| `api_server.py` | Новый endpoint |
| `schemas.py` | Новые схемы |
| `webapp/state.js` | Состояние reply mode |
| `webapp/api.js` | fetchReplyChain |
| `webapp/ui.js` | Рендер кнопок и навигации |
| `webapp/app.js` | Хендлеры навигации |
| `webapp/styles.css` | Стили для tree-nav (если нужно) |
