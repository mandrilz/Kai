"""
SQLite + FTS5 для базы знаний.
Создаёт схему БД и предоставляет функции для работы с ней.
"""
import sqlite3
from pathlib import Path
from typing import Optional
import os


# Путь к БД (в папке data)
BASE_DIR = Path(__file__).parent.parent.parent.parent
DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "kb.sqlite"


def get_conn() -> sqlite3.Connection:
    """
    Получает соединение с БД.
    
    Returns:
        SQLite connection с row_factory
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Инициализирует схему БД (создаёт таблицы и FTS5 индекс).
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Таблица документов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kb_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            source_id TEXT,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица чанков текста
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kb_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY(doc_id) REFERENCES kb_docs(id) ON DELETE CASCADE
        )
    """)
    
    # Индексы для быстрого поиска
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON kb_chunks(doc_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_source_id ON kb_docs(source_id)")
    
    # FTS5 виртуальная таблица для полнотекстового поиска
    # Храним данные напрямую в FTS5
    # rowid в FTS5 автоматически создается, но его нельзя указывать явно
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks_fts
        USING fts5(
            chunk_id UNINDEXED,
            title,
            text,
            tokenize='unicode61'
        )
    """)
    
    conn.commit()
    conn.close()


def clear_db():
    """
    Очищает все данные из БД (но не удаляет схему).
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Удаляем в правильном порядке (сначала зависимые таблицы)
    cur.execute("DELETE FROM kb_chunks_fts")
    cur.execute("DELETE FROM kb_chunks")
    cur.execute("DELETE FROM kb_docs")
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Инициализация БД при запуске модуля
    init_db()
    print(f"База данных инициализирована: {DB_PATH}")

