# Этап 5.5 — AI-имена кластеров + поиск через кластеры

## Задача 1: AI-имена кластеров в продакшне

### Шаг 1.1. Модель Cluster — добавить поле `name`
**Файл:** `storage/fragments_db.py`
- Добавить `name = Column(Text, nullable=True)` в класс Cluster (между preview и created_at)

### Шаг 1.2. ALTER TABLE в init_db()
**Файл:** `storage/db.py`
- После `Base.metadata.create_all()`, добавить:
```python
# Add 'name' column to clusters table if it doesn't exist
if not DATABASE_URL.startswith("sqlite"):
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE clusters ADD COLUMN IF NOT EXISTS name TEXT"))
            conn.commit()
    except Exception as e:
        logging.warning(f"Could not add 'name' column to clusters: {e}")
```
- PostgreSQL 9.6+ поддерживает `IF NOT EXISTS` — на Railway работает
- Для SQLite `create_all()` создаст таблицу с полем сразу (если таблица новая)

### Шаг 1.3. Функция генерации AI-имён
**Файл:** `services/clustering_service.py`
- Добавить импорт `get_openai_client` из `services.transcription_service`
- Новая функция `generate_cluster_names(clusters_data, all_fragments) -> dict[int, str]`
- Логика скопирована из `scripts/export_clusters_html.py::generate_ai_names()`:
  - Построить `frag_by_id = {f['id']: f for f in all_fragments}`
  - Для каждого кластера: взять fragment_ids, выбрать 5 семплов (spread по списку)
  - Промпт: "Дай короткое название (2-4 слова, на русском)..."
  - GPT-4o-mini, max_tokens=30, temperature=0.3
  - try/except на каждый кластер — при ошибке пустая строка
  - Логировать прогресс

### Шаг 1.4. Интеграция в run_clustering()
**Файл:** `services/clustering_service.py`
- Между шагами 6 (Build cluster data) и 7 (Save to DB):
```python
# 6.5. Generate AI names
try:
    names = generate_cluster_names(clusters_data, fragments)
    for cd in clusters_data:
        cd['name'] = names.get(cd['label'], '')
except Exception as e:
    logger.warning(f"Failed to generate AI names: {e}")
    for cd in clusters_data:
        cd['name'] = ''
```
- Обернуто в try/except — ошибка AI-имён НЕ ломает кластеризацию
- Добавить `name` в возвращаемый clusters dict:
  `{'label': c['label'], 'size': c['size'], 'preview': c['preview'], 'name': c.get('name', '')}`

### Шаг 1.5. save_cluster_results() — сохранять name
**Файл:** `storage/fragments_db.py`
- При создании Cluster добавить `name=cd.get('name', '')`

### Шаг 1.6. get_clusters_by_version() — возвращать name
**Файл:** `storage/fragments_db.py`
- В возвращаемый словарь добавить `'name': r.name or ''`

### Шаг 1.7. Отображение в brain_handler.py
**Файл:** `bot/brain_handler.py`

**cluster_command** (топ-10 после кластеризации):
- Показывать `name` если есть, иначе `preview[:100]`

**chains_command** (/chains):
- Показывать `name` если есть, иначе `preview[:80]`

**chain_command** (/chain N):
- В заголовке: `🔗 Кластер #42 — Чайные идеи (15 фрагментов):`

**Промежуточное обновление**: добавить `await status_msg.edit_text("⏳ Генерирую имена кластеров...")`
перед вызовом run_clustering() или после, чтобы пользователь знал что бот не завис (50 запросов ≈ 15-25 сек).

---

## Задача 2: Поиск через кластеры

### Шаг 2.1. Batch-функция get_fragments_clusters()
**Файл:** `storage/fragments_db.py`
- Новая функция `get_fragments_clusters(fragment_ids, version) -> dict[int, dict]`
- JOIN fragment_clusters + clusters, фильтр по version и fragment_ids
- Возвращает `{fragment_id: {id, label, size, preview, name}, ...}`
- Batch-запрос вместо N+1, т.к. search возвращает несколько результатов

### Шаг 2.2. Обновить search_command
**Файл:** `bot/brain_handler.py`
- Добавить импорт `get_fragments_clusters`
- После получения results:
  1. Получить `version = get_latest_cluster_version()`
  2. `cluster_map = get_fragments_clusters([r['id'] for r in results], version)`
  3. Подсчитать кластеры с >= 2 результатами
- Формат вывода:
  - Одиночный результат: `1. [0.12] 2025-04-21 📦Чайные идеи`
  - Группа (>= 2 из одного кластера): заголовок `📦 Чайные идеи (15 фр., /chain 42)` + элементы с отступом
  - Без кластера: как сейчас
- Важно: сохранить порядок по distance (группа появляется в позиции первого элемента)
- Следить за Telegram лимитом 4096 символов

---

## Порядок коммитов

### Коммит 1 (Задача 1): AI-имена кластеров
1. fragments_db.py: модель + save + get (шаги 1.1, 1.5, 1.6)
2. db.py: ALTER TABLE (шаг 1.2)
3. clustering_service.py: generate + интеграция (шаги 1.3, 1.4)
4. brain_handler.py: отображение (шаг 1.7)

### Коммит 2 (Задача 2): Поиск через кластеры
1. fragments_db.py: get_fragments_clusters() (шаг 2.1)
2. brain_handler.py: search_command (шаг 2.2)

## Потенциальные проблемы

1. **50 запросов к GPT-4o-mini** ≈ 15-25 сек → добавить промежуточное обновление статуса
2. **ALTER TABLE на проде**: безопасно, nullable колонка не блокирует
3. **Telegram 4096 символов**: группировка увеличивает длину → обрезать если нужно
4. **Стоимость**: ~$0.001 за 50 кластеров, ничтожно
