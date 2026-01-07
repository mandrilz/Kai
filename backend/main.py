from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import os
from dotenv import load_dotenv
from api import chat, plot

# Загружаем переменные окружения из .env
load_dotenv()

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
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(plot.router, prefix="/api", tags=["plot"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "K.ai API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

