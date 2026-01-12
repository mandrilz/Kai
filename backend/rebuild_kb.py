#!/usr/bin/env python3
"""
Скрипт для пересборки базы знаний.
Использование: python rebuild_kb.py
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в путь
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from services.kb.indexer import rebuild_index

if __name__ == "__main__":
    print("=" * 60)
    print("Пересборка базы знаний K.ai")
    print("=" * 60)
    print()
    
    try:
        rebuild_index()
        print()
        print("=" * 60)
        print("Пересборка завершена успешно!")
        print("=" * 60)
    except KeyboardInterrupt:
        print()
        print("\nПрервано пользователем.")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"\nОШИБКА при пересборке: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
