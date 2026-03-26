# Step 1 — Модель Artifact + CRUD

## Что делаем
Добавить модель `Artifact` в `storage/fragments_db.py` и CRUD-функции.

## Модель (SQLAlchemy)

```python
class Artifact(Base):
    __tablename__ = 'artifacts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(Text, nullable=False)           # тема запроса ("чайный бизнес")
    content = Column(Text, nullable=False)          # GPT-ответ (анализ)
    cluster_id = Column(Integer, ForeignKey('clusters.id'), nullable=True)  # если привязан к кластеру
    fragment_ids = Column(ARRAY(Integer), default=[])  # какие фрагменты использовались
    created_at = Column(DateTime, default=datetime.utcnow)
```

## CRUD-функции

```python
def save_artifact(topic, content, fragment_ids, cluster_id=None) -> int:
    """Сохранить артефакт. Возвращает id."""

def get_artifacts_by_cluster(cluster_id) -> list[dict]:
    """Все артефакты для кластера."""

def get_artifacts_by_topic(topic_query, limit=5) -> list[dict]:
    """Поиск артефактов по теме (ILIKE)."""

def get_latest_artifacts(limit=10) -> list[dict]:
    """Последние артефакты по дате."""
```

## Файлы для изменения
- `storage/fragments_db.py` — добавить модель + CRUD

## Проверка
- [ ] Модель создаётся при init_db()
- [ ] save_artifact возвращает id
- [ ] get_artifacts_by_cluster возвращает список
