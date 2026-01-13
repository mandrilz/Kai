"""
Миграция: добавление поля last_summarized_message_count в таблицу conversationstate.

Выполнение:
    python migrations/add_last_summarized_message_count.py

Или через SQLite CLI:
    sqlite3 kometta_ai.db
    ALTER TABLE conversationstate ADD COLUMN last_summarized_message_count INTEGER;
    .exit
"""
import sqlite3
import os
from pathlib import Path

# Путь к файлу базы данных (относительно корня backend)
DB_PATH = Path(__file__).parent.parent / "kometta_ai.db"

def migrate():
    """Добавляет поле last_summarized_message_count в таблицу conversationstate."""
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        print("   Убедитесь, что вы запускаете скрипт из директории backend/")
        return False
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже колонка
        cursor.execute("PRAGMA table_info(conversationstate)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "last_summarized_message_count" in columns:
            print("✅ Колонка last_summarized_message_count уже существует")
        else:
            # Добавляем колонку (INTEGER, может быть NULL)
            cursor.execute("ALTER TABLE conversationstate ADD COLUMN last_summarized_message_count INTEGER")
            print("✅ Колонка last_summarized_message_count добавлена")
            
            # Устанавливаем значение по умолчанию 0 для существующих записей
            cursor.execute("UPDATE conversationstate SET last_summarized_message_count = 0 WHERE last_summarized_message_count IS NULL")
            print("✅ Установлено значение по умолчанию 0 для существующих записей")
        
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
    print(f"Миграция: добавление last_summarized_message_count в таблицу conversationstate")
    print(f"База данных: {DB_PATH}\n")
    
    success = migrate()
    
    if success:
        print("\n✅ Миграция завершена успешно!")
    else:
        print("\n❌ Миграция не выполнена. Проверьте ошибки выше.")
        exit(1)
