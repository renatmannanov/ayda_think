# Plan: DBSCAN кластеризация + команды бота

*Этап 4 + часть Этапа 5 из plan_ayda_think_v2.md*
*Создан: 2026-03-10*

---

## Цель

Сгруппировать ~1190 фрагментов с эмбеддингами в смысловые кластеры (темы).
Дать возможность просматривать кластеры через бот-команды `/chains` и `/chain N`.
Запуск кластеризации — по команде `/cluster` (admin only).

---

## Что создаём

```
services/clustering_service.py   # НОВЫЙ: DBSCAN, сохранение кластеров
```

Что меняем:
```
storage/fragments_db.py          # + CRUD для кластеров (5 новых функций)
bot/brain_handler.py             # + /cluster, /chains, /chain N команды
main.py                          # + регистрация новых хендлеров
```

---

## Шаги реализации

### Шаг 1: CRUD для кластеров в fragments_db.py

Добавить функции:

```python
def get_all_embedded_fragments() -> list[dict]:
    """Все фрагменты с эмбеддингами (кроме дубликатов).
    Возвращает: [{id, embedding, tags, text, created_at}, ...]
    ВАЖНО: embedding — list[float], нужен для numpy.
    ~1190 фрагментов × 1536 dims ≈ 7MB в памяти — ОК.
    """

def get_latest_cluster_version() -> int | None:
    """Максимальная version из таблицы clusters. None если нет кластеров."""

def save_cluster_results(version: int, clusters_data: list[dict]) -> None:
    """Записать результаты кластеризации.
    clusters_data: [{label, fragment_ids, preview}, ...]
    Для каждого кластера:
      1. INSERT в clusters (version, label, size, preview)
      2. INSERT в fragment_clusters (fragment_id, cluster_id, version)
    Всё в одной транзакции.
    """

def get_clusters_by_version(version: int) -> list[dict]:
    """Список кластеров конкретной версии, отсортированных по size DESC.
    Возвращает: [{id, label, size, preview, created_at}, ...]
    """

def get_cluster_fragments(cluster_id: int) -> list[dict]:
    """Фрагменты конкретного кластера, отсортированные по created_at.
    JOIN fragment_clusters → fragments.
    Возвращает: [{id, external_id, text, tags, created_at}, ...]
    """
```

### Шаг 2: clustering_service.py

```python
import numpy as np
from sklearn.cluster import DBSCAN

def run_clustering(eps: float = 0.35, min_samples: int = 3) -> dict:
    """Основная функция кластеризации.

    Алгоритм:
    1. Загрузить все эмбеддинги из БД
    2. Собрать numpy матрицу (N × 1536)
    3. DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
    4. version = (latest_version or 0) + 1
    5. Для каждого кластера (label != -1):
       - fragment_ids: список id фрагментов
       - size: len(fragment_ids)
       - preview: первые 2 фрагмента, обрезанные до 80 символов
    6. Сохранить через save_cluster_results()
    7. Вернуть результат

    Возвращает: {
        version: int,
        n_clusters: int,
        n_noise: int,        # фрагменты вне кластеров (label = -1)
        n_total: int,        # всего фрагментов обработано
        clusters: [{label, size, preview}, ...]  # top 20 по размеру
    }
    """
```

**Важные решения:**

- **metric='cosine'** — то же расстояние что у pgvector, согласованность с поиском
- **eps=0.35** по умолчанию — средний порог, не слишком строгий/свободный
  - 0.25 → слишком строго, много шума
  - 0.50 → слишком свободно, темы слипнутся
  - Подберём эмпирически при первом прогоне
- **min_samples=3** — кластер от 3 фрагментов (2 слишком мало, 5 потеряем мелкие темы)
- **Preview** — простая конкатенация первых 2 фрагментов (без GPT). GPT-синтез — Этап 6
- **Версионирование** — каждый прогон создаёт новую version:
  - Позволяет сравнивать разные прогоны
  - `/chains` всегда показывает последнюю версию
  - Старые версии остаются в БД, но не чистятся автоматически
- **Шум (label=-1)** — не записывается в clusters, но показывается в статистике
- **Перекластеризация** — при каждом `/cluster` обрабатываются ВСЕ фрагменты заново
  - Инкрементальный DBSCAN сложный и ненадёжный
  - 1190 × 1536 — это ~7MB, DBSCAN отработает за секунды
  - При 10K+ фрагментов можно будет оптимизировать

**Производительность:**
- Загрузка 1190 эмбеддингов из БД: ~1-2 сек
- DBSCAN на 1190 точках: < 1 сек
- Запись результатов: ~1 сек
- Итого: 3-5 секунд, без вызовов OpenAI

### Шаг 3: Команды бота в brain_handler.py

**`/cluster [eps] [min]`** — запустить кластеризацию (admin only)

```
/cluster           → eps=0.35, min_samples=3
/cluster 0.25 5    → eps=0.25, min_samples=5
```

Формат ответа:
```
⏳ Кластеризация...

✅ Кластеризация v3:
  Кластеров: 42
  Шум (без группы): 150
  Всего обработано: 1190

Топ-10:
1. [58] #aretea: Можно вместо коробок делать шоперы... | Ощущение приятной горечи...
2. [35] #feelings: Очень хорошо провели 10 часов... | Поболтал так хорошо с Элиной...
3. [28] #ayda_run: Для веб портала... | Айка говорит, что какой-то тренер...
...
```

Где `[58]` — количество фрагментов в кластере.

**`/chains [N]`** — список кластеров (последняя версия)

```
/chains       → топ 10
/chains 20    → топ 20
```

Формат:
```
📊 Кластеры (v3, 42 шт.):

1. #12 [58 фр.] #aretea: Можно вместо коробок делать шоперы... | Ощущение приятной горечи...
2. #7 [35 фр.] #feelings: Очень хорошо провели 10 часов... | Поболтал так хорошо с Элиной...
3. #15 [28 фр.] #ayda_run: Для веб портала... | Айка говорит, что какой-то тренер...
...
```

Где `#12` — cluster_id (для `/chain 12`).

**`/chain N`** — фрагменты конкретного кластера

```
/chain 12
```

Формат (отсортировано по дате):
```
🔗 Кластер #12 (58 фрагментов):

1. 2024-08-15
   #aretea Самый первый эксперимент с пуэром...
   https://t.me/c/2163129581/50

2. 2024-09-03
   #aretea Идея: чай в банке без сахара...
   https://t.me/c/2163129581/120

...

[показано 10 из 58, /chain 12 2 — стр. 2]
```

Пагинация: `/chain 12 2` — вторая страница (по 10 фрагментов).

### Шаг 4: Регистрация в main.py

```python
from bot.brain_handler import cluster_command, chains_command, chain_command
application.add_handler(CommandHandler("cluster", cluster_command))
application.add_handler(CommandHandler("chains", chains_command))
application.add_handler(CommandHandler("chain", chain_command))
```

---

## Preview кластера — как генерировать

Простой подход (без GPT):
1. Взять самый частый тег среди фрагментов кластера → `#aretea`
2. Взять первые 80 символов 2 самых ранних фрагментов → `text1... | text2...`
3. Склеить: `#aretea: text1... | text2...`

Этого достаточно для идентификации кластера. GPT-синтез (красивое название темы) — Этап 6.

---

## Порядок написания кода

1. `storage/fragments_db.py` — 5 новых CRUD функций
2. `services/clustering_service.py` — DBSCAN + сохранение (1 файл)
3. `bot/brain_handler.py` — 3 новые команды (/cluster, /chains, /chain)
4. `main.py` — регистрация хендлеров
5. Коммит → мерж в main → деплой
6. Тест: /cluster → /chains → /chain N

---

## Зависимости

- scikit-learn (уже в requirements.txt)
- numpy (уже в requirements.txt)
- Эмбеддинги в БД (~1190 фрагментов — есть)
- Таблицы clusters + fragment_clusters (уже созданы в Этап 1)

Новых пакетов НЕ нужно.

---

## Что НЕ делаем сейчас (отложено)

- ❌ GPT-синтез названий кластеров (Этап 6)
- ❌ Инкрементальная кластеризация (не нужно при текущем объёме)
- ❌ Автоматическая перекластеризация (Этап 7 — еженедельная задача)
- ❌ /pattern, /hot команды (Этап 6)
- ❌ Удаление старых версий кластеров (пока не проблема)
