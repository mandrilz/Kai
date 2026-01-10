# Установка зависимостей для базы знаний

## Проблема

При запуске `rebuild_kb.py` возникает ошибка:
```
ModuleNotFoundError: No module named 'requests'
```

## Решение

Установите недостающие зависимости для индексера базы знаний:

```bash
cd /var/www/kai/backend
pip install requests beautifulsoup4
```

Или установите все зависимости из `requirements.txt`:

```bash
cd /var/www/kai/backend
pip install -r requirements.txt
```

## Проверка установки

После установки проверьте, что модули доступны:

```bash
python -c "import requests; import bs4; print('OK')"
```

Если выводит `OK` - зависимости установлены правильно.

## Запуск пересборки

После установки зависимостей запустите пересборку:

```bash
python rebuild_kb.py
```
