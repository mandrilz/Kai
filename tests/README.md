# Тесты

## E2E тесты

Минимальные end-to-end тесты для проверки основного потока чата.

### Запуск

```bash
# Установка зависимостей
pip install pytest requests

# Запуск тестов
pytest tests/e2e/test_chat_flow.py -v

# С указанием URL сервера
BASE_URL=http://localhost:8000 pytest tests/e2e/test_chat_flow.py -v
```

### Требования

- Запущенный backend сервер
- Настроенная аутентификация (для полных тестов)

### Тесты

- `test_create_chat` - создание нового чата
- `test_send_message_basic` - отправка сообщения и получение SSE потока
- `test_idempotency_key` - проверка работы idempotency key
- `test_chat_history` - загрузка истории чата

### Примечания

Тесты требуют доработки для работы с реальной аутентификацией. Сейчас они проверяют базовую функциональность API.
