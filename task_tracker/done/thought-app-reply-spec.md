# Thought App — Спецификация связей v2

## Обзор

Два типа связей между записями:
1. **По тегам** — записи с общими тегами
2. **По реплаям** — цепочки ответов (дерево)

---

## Основной экран

```
┌─────────────────────────────────────┐
│  Все / Фокус                  12/47 │
├─────────────────────────────────────┤
│                                     │
│  Текст записи...                    │
│                                     │
│  #tag1  #tag2                       │
│                             28 Nov  │
├─────────────────────────────────────┤
│  🎯  ✓      [#5] [↩3]      ←  →  ↗ │
└─────────────────────────────────────┘
```

### Кнопки

| Позиция | Элементы | Описание |
|---------|----------|----------|
| Слева | `🎯` `✓` | Фокус (toggle), Готово |
| Центр | `[#5]` `[↩3]` | Связи по тегам, Связи по реплаям |
| Справа | `←` `→` `↗` | Назад, Вперёд, В канал |

### Кнопки связей

| Кнопка | Формат | Действие |
|--------|--------|----------|
| `[#5]` | `#` + количество | Вход в режим связей по тегам |
| `[↩3]` | `↩` + количество | Вход в режим связей по реплаям |
| `[#0]` | Неактивна (серая) | Нет связей по тегам |
| `[↩0]` | Неактивна (серая) | Нет связей по реплаям |

---

## Режим связей по тегам

Без изменений от предыдущей версии.

```
┌─────────────────────────────────────┐
│  ← К записи               связь 2/5 │
├─────────────────────────────────────┤
│                                     │
│  Текст связанной записи...          │
│                                     │
├─────────────────────────────────────┤
│  🎯  ✓           ↓            ←  ↗ │
└─────────────────────────────────────┘
```

### Кнопки

| Позиция | Элементы | Описание |
|---------|----------|----------|
| Слева | `🎯` `✓` | Фокус, Готово |
| Центр | `↓` | Следующая связь по тегам |
| Справа | `←` `↗` | К записи, В канал |

---

## Режим связей по реплаям

```
┌─────────────────────────────────────┐
│  ← К записи    ветка 1    связь 2/4 │
├─────────────────────────────────────┤
│                                     │
│  Текст записи в цепочке...          │
│                                     │
├─────────────────────────────────────┤
│  🎯  ✓       ↑3  ↓1  ↔2       ←  ↗ │
└─────────────────────────────────────┘
```

### Header

| Элемент | Описание |
|---------|----------|
| `← К записи` | Возврат к основной записи |
| `ветка 1` | Название текущей ветки (если есть ветвление) |
| `связь 2/4` | Позиция в цепочке / всего в цепочке |

### Кнопки навигации по дереву

| Кнопка | Формат | Действие |
|--------|--------|----------|
| `↑3` | `↑` + число | Перейти на уровень вверх (к родителю) |
| `↓1` | `↓` + число | Перейти на уровень вниз (к первому ответу) |
| `↔2` | `↔` + число | Переключить ветку (если есть несколько ответов) |
| `—` | Прочерк | Направление недоступно |

### Состояния навигации

**На корне (нет родителя):**
```
│  🎯  ✓        —  ↓3  ↔2       ←  ↗ │
```

**На листе (нет ответов):**
```
│  🎯  ✓       ↑4  —   —        ←  ↗ │
```

**Линейная цепочка (без веток):**
```
│  🎯  ✓       ↑2  ↓1           ←  ↗ │
```

---

## Структура данных

### Запись

```javascript
{
  id: number,
  text: string,
  tags: string[],
  date: string,
  timestamp: string,      // ISO формат для сортировки
  status: "new" | "done",
  focus: boolean,
  reply_to_id: number | null  // ID записи на которую отвечает
}
```

### Примеры

```javascript
// Корневая запись
{ id: 1, reply_to_id: null, ... }

// Ответ на запись 1
{ id: 2, reply_to_id: 1, ... }

// Ещё один ответ на запись 1 (ветка)
{ id: 3, reply_to_id: 1, ... }

// Ответ на запись 2
{ id: 4, reply_to_id: 2, ... }
```

### Дерево из примера

```
1 (корень)
├── 2
│   └── 4
└── 3
```

---

## Алгоритмы

### Получить ответы на запись

```javascript
function getReplies(thoughtId) {
  return thoughts.filter(t => t.reply_to_id === thoughtId);
}
```

### Получить родителя

```javascript
function getParent(thought) {
  if (!thought.reply_to_id) return null;
  return thoughts.find(t => t.id === thought.reply_to_id);
}
```

### Получить всех предков (путь вверх)

```javascript
function getAncestors(thought) {
  const ancestors = [];
  let current = thought;
  
  while (current.reply_to_id) {
    const parent = getParent(current);
    if (parent) {
      ancestors.push(parent);
      current = parent;
    } else break;
  }
  
  return ancestors; // [родитель, дед, прадед, ...]
}
```

### Получить потомков (путь вниз по первой ветке)

```javascript
function getDescendants(thought) {
  const descendants = [];
  const replies = getReplies(thought.id);
  
  if (replies.length > 0) {
    const firstReply = replies[0];
    descendants.push(firstReply);
    descendants.push(...getDescendants(firstReply));
  }
  
  return descendants;
}
```

### Построить цепочку

```javascript
function buildReplyChain(thought) {
  const ancestors = getAncestors(thought).reverse(); // от корня к родителю
  const descendants = getDescendants(thought);
  return [...ancestors, thought, ...descendants];
}
```

### Получить siblings (записи на том же уровне)

```javascript
function getSiblings(thought) {
  if (!thought.reply_to_id) return [];
  return thoughts.filter(t => 
    t.reply_to_id === thought.reply_to_id && t.id !== thought.id
  );
}
```

### Посчитать статистику для кнопки `[↩N]`

```javascript
function countAllReplies(thought) {
  const ancestors = getAncestors(thought);
  const root = ancestors.length > 0 
    ? ancestors[ancestors.length - 1] 
    : thought;
  
  const allInChain = new Set();
  
  function countTree(t) {
    allInChain.add(t.id);
    getReplies(t.id).forEach(reply => countTree(reply));
  }
  
  countTree(root);
  return allInChain.size;
}
```

---

## Навигация по дереву

### Вход в режим реплаев

```javascript
function enterReplyRelated() {
  const thought = getCurrentThought();
  
  state.replyChain = buildReplyChain(thought);
  state.replyIndex = state.replyChain.findIndex(t => t.id === thought.id);
  state.mode = 'reply_related';
  
  updateBranches();
}
```

### Вверх (к родителю)

```javascript
function replyUp() {
  const current = state.replyChain[state.replyIndex];
  const parent = getParent(current);
  
  if (!parent) return; // уже на корне
  
  const parentIndex = state.replyChain.findIndex(t => t.id === parent.id);
  state.replyIndex = parentIndex;
  
  updateBranches();
}
```

### Вниз (к первому ответу)

```javascript
function replyDown() {
  const current = state.replyChain[state.replyIndex];
  const replies = getReplies(current.id);
  
  if (replies.length === 0) return; // уже на листе
  
  const firstReply = replies[0];
  
  // Перестроить цепочку если нужно
  state.replyChain = buildReplyChain(firstReply);
  state.replyIndex = state.replyChain.findIndex(t => t.id === firstReply.id);
  
  updateBranches();
}
```

### Вбок (переключить ветку)

```javascript
function replyBranch() {
  if (state.replyBranches.length <= 1) return;
  
  // Следующая ветка (loop)
  state.replyBranchIndex = (state.replyBranchIndex + 1) % state.replyBranches.length;
  
  const newBranch = state.replyBranches[state.replyBranchIndex];
  
  // Перестроить цепочку от этой ветки
  state.replyChain = buildReplyChain(newBranch);
  state.replyIndex = state.replyChain.findIndex(t => t.id === newBranch.id);
}
```

### Обновить список веток

```javascript
function updateBranches() {
  const current = state.replyChain[state.replyIndex];
  const siblings = getSiblings(current);
  
  state.replyBranches = [current, ...siblings];
  state.replyBranchIndex = 0;
}
```

---

## Состояние приложения

```javascript
state = {
  // Основные режимы
  mode: "all" | "focus" | "tag" | "tags_related" | "reply_related",
  currentIndex: number,
  previousMode: string,
  
  // Связи по тегам
  relatedThoughts: array,
  relatedIndex: number,
  parentThoughtId: number,
  
  // Связи по реплаям
  replyChain: array,         // текущая цепочка записей
  replyIndex: number,        // позиция в цепочке
  replyBranches: array,      // доступные ветки на текущем уровне
  replyBranchIndex: number   // индекс текущей ветки
}
```

---

## Стилизация

### Кнопки типов связей

```css
.conn-btn {
  background: #f3f4f6;
  border: none;
  border-radius: 12px;
  padding: 4px 10px;
  font-size: 13px;
  color: #6b7280;
}

.conn-btn.disabled {
  color: #d1d5db;
  cursor: default;
}
```

### Навигация по дереву

```css
.tree-nav {
  display: flex;
  gap: 6px;
  font-size: 14px;
}

.tree-nav-btn {
  padding: 2px 6px;
  color: #6b7280;
}

.tree-nav-btn.disabled {
  color: #d1d5db;
}
```

---

## Жесты

| Жест | Основной режим | Связи по тегам | Связи по реплаям |
|------|----------------|----------------|------------------|
| Swipe left | → Следующая | ↓ Следующая связь | ↓ Вниз по дереву |
| Swipe right | ← Предыдущая | ← К записи | ← К записи |
| Double tap | 🎯 Toggle фокус | 🎯 Toggle фокус | 🎯 Toggle фокус |

---

## Файлы

- `thought-app-v6.html` — рабочий прототип
- `thought-app-ui-spec.md` — базовая спецификация Phase 1
- `thought-app-related-spec.md` — спецификация связей по тегам
