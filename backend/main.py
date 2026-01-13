from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import os
from dotenv import load_dotenv
from api import plot, auth, chats
from models import init_db

# Загружаем переменные окружения из .env
load_dotenv()

# Очистка debug.log при старте приложения
def clear_debug_log():
    """Очищает debug.log при перезапуске сервиса"""
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        if os.path.exists(log_path):
            # Создаем резервную копию с timestamp
            import shutil
            from datetime import datetime
            backup_path = f"{log_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.move(log_path, backup_path)
            # Оставляем только последние 3 резервные копии
            log_dir = os.path.dirname(log_path)
            if os.path.exists(log_dir):
                backups = sorted([f for f in os.listdir(log_dir) if f.startswith(os.path.basename(log_path) + ".")], reverse=True)
                for old_backup in backups[3:]:  # Оставляем только 3 последние
                    try:
                        os.remove(os.path.join(log_dir, old_backup))
                    except:
                        pass
        else:
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
    except Exception as e:
        # Не падаем, если не удалось очистить лог
        print(f"Warning: Could not clear debug.log: {e}")

# Очищаем debug.log при старте
clear_debug_log()

# Инициализируем БД
init_db()

app = FastAPI(title="K.ai API", version="1.0.0")

# CORS для Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://kai.kometta.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роуты
app.include_router(auth.router, prefix="/api", tags=["auth"])  # Добавил префикс /api для единообразия
app.include_router(chats.router, prefix="/api", tags=["chats"])
app.include_router(plot.router, prefix="/api", tags=["plot"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "K.ai API"}


@app.get("/health")
async def health():
    """Health check endpoint (без префикса /api для совместимости)."""
    return {"status": "healthy"}


@app.get("/api/health")
async def api_health():
    """Health check endpoint с префиксом /api для единообразия."""
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

