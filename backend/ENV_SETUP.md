# Настройка переменных окружения

## Быстрый старт

1. Скопируйте шаблон в `.env`:
   ```bash
   cd backend
   cp .env.template .env
   ```

2. Откройте файл `.env` и заполните необходимые переменные.

## Обязательные переменные

### JWT_SECRET
Секретный ключ для подписи JWT токенов. **ОБЯЗАТЕЛЬНО измените в продакшене!**

Генерация безопасного ключа:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### SMTP настройки (для magic-link)
Если вы хотите отправлять письма с magic-link, заполните:
- `SMTP_HOST` - хост SMTP сервера (например, `smtp.gmail.com`)
- `SMTP_PORT` - порт (обычно `587` для TLS)
- `SMTP_USER` - ваш email
- `SMTP_PASS` - пароль приложения (для Gmail нужен App Password)

**Для Gmail:**
1. Включите двухфакторную аутентификацию
2. Перейдите: Настройки аккаунта → Безопасность → Пароли приложений
3. Создайте новый пароль приложения для "Почта"
4. Используйте этот пароль в `SMTP_PASS`

**Если SMTP не настроен:**
В режиме разработки (`ENVIRONMENT=development`) magic-link будет выводиться в консоль сервера вместо отправки на email.

### FRONTEND_URL
URL вашего фронтенда для ссылок в письмах:
- Разработка: `http://localhost:3000`
- Продакшен: `https://kai.kometta.ru`

### ENVIRONMENT
Режим работы:
- `development` - для разработки
- `production` - для продакшена (включает HTTPS для cookies)

## Опциональные переменные

### DEBUG_LOG_PATH
Путь к файлу debug лога. По умолчанию: `/var/www/kai/.cursor/debug.log`

### DATA_DIR
Директория с Excel файлами базы данных. По умолчанию: `./data`

### TYPO_FUZZY
Включить исправление опечаток (1 = да, 0 = нет). По умолчанию: `1`

### CONVERSATION_TTL_HOURS
Время жизни диалогов в часах. По умолчанию: `24`

### SESSION_STATE_TTL_HOURS
Время жизни сессий в часах. По умолчанию: `24`

## Пример минимального .env для разработки

```bash
JWT_SECRET=dev-secret-key-change-in-production
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

## Пример .env для продакшена

```bash
JWT_SECRET=<сгенерированный-безопасный-ключ-32+ символов>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@kometta.ru
SMTP_PASS=<app-password>
FRONTEND_URL=https://kai.kometta.ru
ENVIRONMENT=production
DEBUG_LOG_PATH=/var/www/kai/.cursor/debug.log
```

## Проверка настроек

После заполнения `.env` запустите backend:

```bash
cd backend
python main.py
```

Если все настроено правильно, вы увидите:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Если есть ошибки, проверьте:
1. Все обязательные переменные заполнены
2. SMTP настройки корректны (если используете email)
3. Пути к файлам существуют (если указаны кастомные пути)
