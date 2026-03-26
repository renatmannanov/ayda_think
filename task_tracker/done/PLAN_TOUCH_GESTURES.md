# План реализации: Сенсорное управление (Touch Gestures)

## Обзор

Реализуем три жеста для мобильного управления заметками:
- **Свайп влево** → следующая заметка
- **Свайп вправо** → предыдущая заметка
- **Двойной тап** → фокус

При каждом жесте будет подсвечиваться соответствующая кнопка для визуальной обратной связи.

---

## Архитектура решения

### Новый модуль: `gestures.js`

Создаём отдельный модуль для обработки жестов. Это обеспечит:
- Чистое разделение ответственности
- Лёгкое тестирование
- Возможность отключить/включить жесты

### Структура модуля:

```javascript
// gestures.js
export const gestures = {
    // Настройки
    config: {
        swipeThreshold: 50,      // Минимальная дистанция свайпа (px)
        swipeTimeout: 300,       // Максимальное время свайпа (ms)
        doubleTapTimeout: 300,   // Максимальный интервал для двойного тапа (ms)
        highlightDuration: 200   // Длительность подсветки кнопки (ms)
    },

    // Состояние
    state: {
        startX: 0,
        startY: 0,
        startTime: 0,
        lastTap: 0
    },

    // Методы
    init(element, callbacks),
    handleTouchStart(e),
    handleTouchEnd(e),
    highlightButton(buttonId),
    destroy()
}
```

---

## Детальный план реализации

### Шаг 1: Создать модуль `gestures.js`

**Файл:** `webapp/gestures.js`

```javascript
// gestures.js - Touch gesture handling for mobile
export const gestures = {
    config: {
        swipeThreshold: 50,
        swipeTimeout: 300,
        doubleTapTimeout: 300,
        highlightDuration: 200
    },

    state: {
        startX: 0,
        startY: 0,
        startTime: 0,
        lastTap: 0,
        element: null,
        callbacks: null
    },

    init(element, callbacks) {
        this.state.element = element;
        this.state.callbacks = callbacks;

        // Bind handlers
        this._onTouchStart = this.handleTouchStart.bind(this);
        this._onTouchEnd = this.handleTouchEnd.bind(this);

        element.addEventListener('touchstart', this._onTouchStart, { passive: true });
        element.addEventListener('touchend', this._onTouchEnd, { passive: true });
    },

    handleTouchStart(e) {
        const touch = e.touches[0];
        this.state.startX = touch.clientX;
        this.state.startY = touch.clientY;
        this.state.startTime = Date.now();
    },

    handleTouchEnd(e) {
        const touch = e.changedTouches[0];
        const deltaX = touch.clientX - this.state.startX;
        const deltaY = touch.clientY - this.state.startY;
        const deltaTime = Date.now() - this.state.startTime;

        // Check for swipe
        if (deltaTime < this.config.swipeTimeout) {
            const absX = Math.abs(deltaX);
            const absY = Math.abs(deltaY);

            // Horizontal swipe (X > Y means horizontal)
            if (absX > this.config.swipeThreshold && absX > absY) {
                if (deltaX < 0) {
                    // Swipe left → Next
                    this.highlightButton('#btnNext');
                    this.state.callbacks?.onSwipeLeft?.();
                } else {
                    // Swipe right → Prev
                    this.highlightButton('#btnPrev');
                    this.state.callbacks?.onSwipeRight?.();
                }
                return;
            }
        }

        // Check for double tap (only if no significant movement)
        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);
        if (absX < 10 && absY < 10) {
            const now = Date.now();
            if (now - this.state.lastTap < this.config.doubleTapTimeout) {
                // Double tap → Focus
                this.highlightButton('#btnFocus');
                this.state.callbacks?.onDoubleTap?.();
                this.state.lastTap = 0; // Reset to prevent triple-tap
            } else {
                this.state.lastTap = now;
            }
        }
    },

    highlightButton(selector) {
        const btn = document.querySelector(selector);
        if (!btn) return;

        btn.classList.add('gesture-highlight');
        setTimeout(() => {
            btn.classList.remove('gesture-highlight');
        }, this.config.highlightDuration);
    },

    destroy() {
        if (this.state.element) {
            this.state.element.removeEventListener('touchstart', this._onTouchStart);
            this.state.element.removeEventListener('touchend', this._onTouchEnd);
        }
    }
};
```

---

### Шаг 2: Добавить CSS для подсветки кнопок

**Файл:** `webapp/styles.css`

Добавить в конец файла:

```css
/* ==========================================================================
   Touch Gesture Feedback
   ========================================================================== */

/* Highlight animation for gesture feedback */
.gesture-highlight {
    animation: gestureHighlight 0.2s ease-out;
}

@keyframes gestureHighlight {
    0% {
        transform: scale(1);
        background-color: transparent;
    }
    50% {
        transform: scale(1.3);
        background-color: rgba(249, 115, 22, 0.2); /* orange-500 with opacity */
    }
    100% {
        transform: scale(1);
        background-color: transparent;
    }
}

/* Specific highlight for focus button */
#btnFocus.gesture-highlight {
    animation: gestureHighlightFocus 0.2s ease-out;
}

@keyframes gestureHighlightFocus {
    0% {
        transform: scale(1);
    }
    50% {
        transform: scale(1.4);
        color: var(--orange-500);
    }
    100% {
        transform: scale(1);
    }
}

/* Specific highlight for navigation arrows */
#btnPrev.gesture-highlight,
#btnNext.gesture-highlight {
    animation: gestureHighlightArrow 0.2s ease-out;
}

@keyframes gestureHighlightArrow {
    0% {
        transform: scale(1);
        color: var(--gray-500);
    }
    50% {
        transform: scale(1.5);
        color: var(--orange-500);
    }
    100% {
        transform: scale(1);
        color: var(--gray-500);
    }
}
```

---

### Шаг 3: Интегрировать в `app.js`

**Файл:** `webapp/app.js`

**Изменения:**

1. Добавить импорт:
```javascript
import { gestures } from './gestures.js';
```

2. В функции `init()` добавить инициализацию жестов:
```javascript
async function init() {
    api.init();
    await loadNotes();
    setupEventListeners();
    setupGestures();  // <-- Добавить
    ui.render();
}
```

3. Добавить новую функцию:
```javascript
// Setup touch gestures for mobile
function setupGestures() {
    const gestureArea = ui.elements.body;

    gestures.init(gestureArea, {
        onSwipeLeft: () => {
            // Next note (same logic as btnNext)
            if (state.mode === 'related') {
                handleNextRelated();
            } else if (state.mode !== 'reply_related') {
                handleNext();
            }
        },
        onSwipeRight: () => {
            // Prev note (same logic as btnPrev)
            if (state.mode === 'related') {
                handlePrevRelated();
            } else if (state.mode !== 'reply_related') {
                handlePrev();
            }
        },
        onDoubleTap: () => {
            // Toggle focus (same logic as btnFocus)
            handleToggleFocus();
        }
    });
}
```

---

### Шаг 4: Учесть режим related/reply_related

В режиме `related` используются кнопки `#btnPrevRelated` и `#btnNextRelated`.
В режиме `reply_related` навигация через дерево (↑↓↔).

Обновить `highlightButton` в callbacks:

```javascript
onSwipeLeft: () => {
    if (state.mode === 'related') {
        gestures.highlightButton('#btnNextRelated');
        handleNextRelated();
    } else if (state.mode !== 'reply_related') {
        gestures.highlightButton('#btnNext');
        handleNext();
    }
},
onSwipeRight: () => {
    if (state.mode === 'related') {
        gestures.highlightButton('#btnPrevRelated');
        handlePrevRelated();
    } else if (state.mode !== 'reply_related') {
        gestures.highlightButton('#btnPrev');
        handlePrev();
    }
}
```

**Примечание:** В режиме `reply_related` свайпы отключены, т.к. там древовидная навигация.

---

## Схема взаимодействия

```
┌─────────────────────────────────────────────────────────┐
│                    Touch Event                          │
│                    (on .body)                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   gestures.js                           │
│  ┌─────────────┬─────────────┬─────────────────────┐   │
│  │ Swipe Left  │ Swipe Right │    Double Tap       │   │
│  └──────┬──────┴──────┬──────┴──────────┬──────────┘   │
└─────────┼─────────────┼─────────────────┼───────────────┘
          │             │                 │
          ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────┐
│                     app.js                              │
│  ┌─────────────┬─────────────┬─────────────────────┐   │
│  │ handleNext()│ handlePrev()│ handleToggleFocus() │   │
│  └──────┬──────┴──────┬──────┴──────────┬──────────┘   │
└─────────┼─────────────┼─────────────────┼───────────────┘
          │             │                 │
          ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────┐
│              Visual Feedback                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │   highlightButton() + haptic feedback           │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Файлы для изменения

| Файл | Действие | Описание |
|------|----------|----------|
| `webapp/gestures.js` | Создать | Новый модуль для обработки жестов |
| `webapp/styles.css` | Изменить | Добавить CSS для подсветки кнопок |
| `webapp/app.js` | Изменить | Импорт gestures + вызов setupGestures() |

---

## Тестирование

1. **Свайп влево** → проверить переход на следующую заметку + подсветка кнопки →
2. **Свайп вправо** → проверить переход на предыдущую заметку + подсветка кнопки ←
3. **Двойной тап** → проверить toggle focus + подсветка кнопки фокуса
4. **Режим related** → проверить что используются правильные кнопки
5. **Режим reply_related** → проверить что свайпы отключены
6. **Haptic feedback** → проверить вибрацию на телефоне

---

## Возможные улучшения (на будущее)

- Свайп вверх/вниз для дополнительных действий
- Long press для контекстного меню
- Pinch-to-zoom для увеличения текста
- Настройка чувствительности свайпов

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Конфликт с прокруткой | Низкая | Проверяем горизонтальность свайпа (absX > absY) |
| Двойной тап конфликтует с кликом | Низкая | Проверяем минимальное смещение (< 10px) |
| Не работает в Telegram WebApp | Низкая | Используем стандартные touch events |
