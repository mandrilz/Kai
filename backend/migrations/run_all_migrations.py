"""
Запускает все миграции базы данных по порядку.

Выполнение:
    python migrations/run_all_migrations.py
"""
import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from migrations.add_idempotency_key import migrate as migrate_idempotency
from migrations.add_last_summarized_message_count import migrate as migrate_summarized_count
from migrations.add_printed_at import migrate as migrate_printed_at

def run_all():
    """Запускает все миграции."""
    print("=" * 60)
    print("Запуск всех миграций базы данных")
    print("=" * 60)
    print()
    
    migrations = [
        ("idempotency_key", migrate_idempotency),
        ("last_summarized_message_count", migrate_summarized_count),
        ("printed_at", migrate_printed_at),
    ]
    
    success_count = 0
    for name, migrate_func in migrations:
        print(f"\n{'=' * 60}")
        print(f"Миграция: {name}")
        print(f"{'=' * 60}\n")
        
        try:
            if migrate_func():
                success_count += 1
            else:
                print(f"❌ Миграция {name} не выполнена")
        except Exception as e:
            print(f"❌ Ошибка при выполнении миграции {name}: {e}")
    
    print(f"\n{'=' * 60}")
    print(f"Результат: {success_count}/{len(migrations)} миграций выполнено успешно")
    print(f"{'=' * 60}")
    
    if success_count == len(migrations):
        print("\n✅ Все миграции выполнены успешно!")
        return True
    else:
        print(f"\n⚠️  Некоторые миграции не выполнены. Проверьте ошибки выше.")
        return False


if __name__ == "__main__":
    success = run_all()
    exit(0 if success else 1)
