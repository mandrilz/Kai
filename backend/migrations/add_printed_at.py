"""
Миграция: добавление поля printed_at в таблицу message.

Выполнение:
    python migrations/add_printed_at.py

Или через SQLite CLI:
    sqlite3 kometta_ai.db
    ALTER TABLE message ADD COLUMN printed_at DATETIME;
    .exit
"""
import sqlite3
import os
from pathlib import Path

# Путь к файлу базы данных (относительно корня backend)
DB_PATH = Path(__file__).parent.parent / "kometta_ai.db"

def migrate():
    """Добавляет поле printed_at в таблицу message."""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        print("   Убедитесь, что вы запускаете скрипт из директории backend/")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже колонка
        cursor.execute("PRAGMA table_info(message)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "printed_at" in columns:
            print("✅ Колонка printed_at уже существует")
        else:
            # Добавляем колонку
            cursor.execute("ALTER TABLE message ADD COLUMN printed_at DATETIME")
            print("✅ Колонка printed_at добавлена")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Миграция успешно выполнена для базы данных: {DB_PATH}")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Ошибка при выполнении миграции: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False


if __name__ == "__main__":
    print(f"Миграция: добавление printed_at в таблицу message")
    print(f"База данных: {DB_PATH}\n")
    
    success = migrate()
    
    if success:
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция не выполнена. Проверьте ошибки выше.")
        exit(1)
