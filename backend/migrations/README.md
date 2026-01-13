# Миграции базы данных

## Добавление поля last_summarized_message_count

### Способ 1: Через Python скрипт (рекомендуется)

```bash
cd backend
python migrations/add_last_summarized_message_count.py
```

### Способ 2: Через SQLite CLI

```bash
cd backend
sqlite3 kometta_ai.db
```

Затем выполните SQL команды:

```sql
ALTER TABLE conversationstate ADD COLUMN last_summarized_message_count INTEGER;
UPDATE conversationstate SET last_summarized_message_count = 0 WHERE last_summarized_message_count IS NULL;
.exit
```

## Добавление поля printed_at

### Способ 1: Через Python скрипт (рекомендуется)

```bash
cd backend
python migrations/add_printed_at.py
```

### Способ 2: Через SQLite CLI

```bash
cd backend
sqlite3 kometta_ai.db
```

Затем выполните SQL команды:

```sql
ALTER TABLE message ADD COLUMN printed_at TIMESTAMP;
.exit
```

## Добавление поля idempotency_key

### Способ 1: Через Python скрипт (рекомендуется)

```bash
cd backend
python migrations/add_idempotency_key.py
```

### Способ 2: Через SQLite CLI

```bash
cd backend
sqlite3 kometta_ai.db
```

Затем выполните SQL команды:

```sql
ALTER TABLE message ADD COLUMN idempotency_key TEXT;
CREATE INDEX IF NOT EXISTS idx_message_idempotency_key ON message(idempotency_key);
.exit
```

### Способ 3: Через Python REPL

```bash
cd backend
python
```

```python
import sqlite3
conn = sqlite3.connect('kometta_ai.db')
cursor = conn.cursor()
cursor.execute("ALTER TABLE message ADD COLUMN idempotency_key TEXT")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_idempotency_key ON message(idempotency_key)")
conn.commit()
conn.close()
```

## Расположение базы данных

Файл базы данных: `backend/kometta_ai.db`

Путь задан в `backend/models.py`:
```python
DATABASE_URL = "sqlite:///./kometta_ai.db"
```

## Примечания

- SQLite не требует перезапуска сервера после миграции
- Если таблица `message` еще не создана, SQLModel создаст её автоматически при следующем запуске с новым полем
- Индекс создается для ускорения поиска по `idempotency_key`
