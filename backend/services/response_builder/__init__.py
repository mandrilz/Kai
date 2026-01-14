"""
ResponseBuilder - форматирование ответов в стиле ChatGPT.

PR6: ResponseBuilder - стиль ChatGPT и follow-ups.

Отвечает за:
- Форматирование ответов на основе результатов domain services
- Естественный язык в стиле ChatGPT
- Follow-up вопросы и предложения
- Интеграция с DialogueManager

Без бизнес-логики:
- Не выполняет расчеты
- Не ищет данные
- Только форматирует результаты
"""
from services.response_builder.builder import ResponseBuilder

__all__ = ["ResponseBuilder"]
