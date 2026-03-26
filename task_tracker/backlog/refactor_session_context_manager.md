# Refactor: SessionLocal → context manager

*Создан: 2026-03-10*

## Что

Заменить 10 мест в `storage/db.py` и `storage/fragments_db.py` где используется паттерн:

```python
session = SessionLocal()
try:
    ...
finally:
    session.close()
```

На context manager:

```python
@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
```

## Зачем

- Чище код, меньше boilerplate
- Автоматический rollback при ошибках (сейчас не везде есть)
- Единый паттерн для всех CRUD-функций

## Файлы

- `storage/db.py` — 6 мест
- `storage/fragments_db.py` — 4 места (+ новые функции)

## Приоритет

Низкий. Не блокирует ничего. Делать когда будет окно.
