# K.ai (Кометтик) — MVP

AI-бот для подбора насосов Кометта.

## Структура проекта

```
/var/www/kai/  (или любая другая директория проекта)
├── backend/          # Python FastAPI backend
│   ├── main.py
│   ├── .env          # Переменные окружения (создать из .env.example)
│   ├── venv/         # Виртуальное окружение Python
│   ├── api/
│   │   ├── chat.py
│   │   └── plot.py
│   └── services/
│       ├── curve_math.py
│       ├── data_loader.py
│       ├── normalize.py
│       ├── selector.py
│       ├── intents.py
│       └── file_extractors.py
├── frontend/         # Next.js 14 frontend
│   ├── app/
│   │   ├── page.tsx
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Chat.tsx
│   │   ├── Message.tsx
│   │   ├── Composer.tsx
│   │   └── FileUpload.tsx
│   └── .next/        # Production build
└── data/             # XLSX файлы (на уровне проекта!)
    ├── K.ai_database_kometta.xlsx
    └── K.ai_database_competitors_cnp.xlsx
```

## Требования

### Backend
- Python 3.11+
- pip

### Frontend
- Node.js 18+
- npm или yarn

## Установка и запуск локально

### 1. Backend

```bash
cd backend

# Создать виртуальное окружение
python -m venv venv

# Активировать виртуальное окружение
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Создать .env файл из примера
cp .env.example .env

# Для локальной разработки: создать папку data на уровень выше backend
# (или изменить DATA_DIR в .env)
mkdir ../data
# Скопировать K.ai_database_kometta.xlsx и K.ai_database_competitors_cnp.xlsx в ../data/

# Или установить DATA_DIR в .env на нужный путь
# DATA_DIR=C:\Users\Admin\Desktop\3\data  (Windows)
# DATA_DIR=/path/to/data  (Linux/Mac)

# Запустить сервер
python main.py
```

Backend будет доступен на `http://localhost:8000`

### 2. Frontend

```bash
cd frontend

# Установить зависимости
npm install

# Запустить dev сервер
npm run dev
```

Frontend будет доступен на `http://localhost:3000`

## Развёртывание на VPS Beget

### 1. Подготовка сервера

```bash
# Установить Python 3.11+ и Node.js 18+
# Установить nginx
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm nginx
```

### 2. Backend

```bash
# Создать директорию для проекта
sudo mkdir -p /var/www/kai
sudo chown $USER:$USER /var/www/kai
cd /var/www/kai

# Скопировать проект
# (через git, scp или другой способ)

# Создать папку data и поместить XLSX файлы
mkdir data
# Скопировать K.ai_database_kometta.xlsx и K.ai_database_competitors_cnp.xlsx в data/

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Создать .env файл
cp .env.example .env
nano .env  # Установить DATA_DIR=/var/www/kai/data

# Создать systemd service для backend
sudo nano /etc/systemd/system/kai-backend.service
```

Содержимое файла `/etc/systemd/system/kai-backend.service`:

```ini
[Unit]
Description=K.ai Backend (FastAPI)
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/kai/backend
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/var/www/kai/backend/.env
ExecStart=/var/www/kai/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Запустить service
sudo systemctl daemon-reload
sudo systemctl enable kai-backend
sudo systemctl start kai-backend
```

### 3. Frontend

**Вариант A: Использование PM2 (рекомендуется)**

```bash
cd /var/www/kai/frontend

# Установить зависимости
npm install

# Собрать production build
npm run build

# Установить PM2 глобально (если ещё не установлен)
npm install -g pm2

# Создать ecosystem файл
nano ecosystem.config.js
```

Содержимое файла `ecosystem.config.js`:
```javascript
module.exports = {
  apps: [{
    name: 'kai-frontend',
    script: 'npm',
    args: 'start',
    cwd: '/var/www/kai/frontend',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production',
      PORT: 3000
    }
  }]
}
```

```bash
# Запустить через PM2
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # Настроить автозапуск при перезагрузке системы
```

**Вариант B: Использование systemd**

```bash
cd /var/www/kai/frontend

# Установить зависимости
npm install

# Собрать production build
npm run build

# Создать systemd service для frontend
sudo nano /etc/systemd/system/kai-frontend.service
```

Содержимое файла `/etc/systemd/system/kai-frontend.service`:

```ini
[Unit]
Description=K.ai Frontend (Next.js)
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/var/www/kai/frontend
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=3
Environment="NODE_ENV=production"
Environment="PORT=3000"

[Install]
WantedBy=multi-user.target
```

```bash
# Запустить service
sudo systemctl daemon-reload
sudo systemctl enable kai-frontend
sudo systemctl start kai-frontend
```

**⚠️ Важно:** При обновлении кода всегда очищайте кэш Next.js:
```bash
cd /var/www/kai/frontend
rm -rf .next
npm run build
# Затем перезапустите PM2 или systemd service
```

### 4. Nginx конфигурация

Создать файл `/etc/nginx/sites-available/kai`:

```nginx
server {
    listen 80;
    server_name kai.kometta.ru;
    client_max_body_size 25m;

    # Frontend (Next.js)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    # ВАЖНО: Проверьте порт backend в systemd service (может быть 8000 или 8001)
    # Слэш в конце proxy_pass убирает /api/ из пути запроса
    location /api/ {
        proxy_pass http://127.0.0.1:8001/;  # ← Измените на правильный порт!
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Для SSE (Server-Sent Events)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

**⚠️ ВАЖНО:** 
1. Проверьте порт backend: `sudo systemctl status kai-backend` (в логах будет `Uvicorn running on http://127.0.0.1:XXXX`)
2. Убедитесь, что порт в nginx совпадает с портом в systemd service
3. Слэш `/` в конце `proxy_pass` обязателен для правильного проксирования

```bash
# Активировать конфигурацию
sudo ln -s /etc/nginx/sites-available/kai /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезагрузить nginx
sudo systemctl reload nginx
```

**Важно:** Убедитесь, что в `/var/www/kai/backend/.env` установлен правильный путь:
```
DATA_DIR=/var/www/kai/data
```

### 5. SSL сертификат (опционально, но рекомендуется)

```bash
# Установить certbot
sudo apt install certbot python3-certbot-nginx

# Получить сертификат
sudo certbot --nginx -d kai.kometta.ru
```

## Проверка работы

1. Backend: `curl http://localhost:8000/health` должен вернуть `{"status":"healthy"}`
2. Frontend: открыть `http://localhost:3000` в браузере
3. API: `curl http://localhost:8000/api/chat` (должна быть ошибка метода, но это нормально)

## Примечания

- **Важно:** Файлы XLSX должны находиться в папке `data/` на уровне проекта (не в `backend/data/`)
- Путь к папке `data/` настраивается через переменную окружения `DATA_DIR` в файле `backend/.env`
- Для локальной разработки можно использовать относительный путь: `DATA_DIR=../data`
- Для production используйте абсолютный путь: `DATA_DIR=/var/www/kai/data`
- **Для frontend:** При обновлении кода всегда очищайте кэш Next.js: `rm -rf .next && npm run build`
- Если видите ошибку "Failed to find Server Action" - см. `DEPLOYMENT.md` для решения
- Для OCR (обработка изображений) может потребоваться установка Tesseract:
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-rus
  ```
- Если pytesseract не установлен, обработка изображений будет недоступна, но PDF всё равно будет работать
- Для production рекомендуется использовать переменные окружения для конфигурации (порты, пути к файлам и т.д.)

## API Endpoints

- `POST /api/chat` — чат с Кометтиком (SSE streaming)
- `POST /api/plot/compare` — генерация графика сравнения кривых
- `GET /health` — проверка здоровья сервиса

## Лицензия

Проект для внутреннего использования Кометта.
