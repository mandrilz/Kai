"""
Обработчик интента TECH_QA - технические вопросы, поиск в базе знаний.
"""
from typing import Dict, Any
from services.dialog_handlers.types import HandlerResult
from services.prompt_templates import get_tech_qa_error


def handle_tech_qa(
    *,
    chat_id: str,
    message: str,
    data: Dict[str, Any],
    context: Dict[str, Any],
) -> HandlerResult:
    """
    Обрабатывает технические вопросы, выполняя поиск в базе знаний.
    
    Args:
        chat_id: ID чата
        message: Текст сообщения пользователя (уже нормализован)
        data: Извлеченные данные из сообщения (intent detection)
        context: Контекст диалога (recent_messages, dialog_summary)
    
    Returns:
        HandlerResult с частями ответа
    """
    result = HandlerResult()
    
    try:
        query = data.get("query", message)
        message_lower = message.lower()
        
        # Обработка общих вопросов о типах насосов
        if any(phrase in message_lower for phrase in [
            "какие типы насосов", "какие типы есть", "типы насосов в ассортименте",
            "какие насосы есть", "какие насосы в линейке", "ассортимент насосов"
        ]):
            from services.pump_types import list_available_pump_types
            types_list = list_available_pump_types()
            result.response_parts.append("**Типы насосов в ассортименте Кометта:**\n\n")
            for i, type_info in enumerate(types_list, 1):
                result.response_parts.append(f"{i}. {type_info}\n")
            return result
        
        # Обработка вопросов о компонентах насоса
        if any(phrase in message_lower for phrase in [
            "из чего состоит насос", "компоненты насоса", "части насоса",
            "состав насоса", "устройство насоса", "конструкция насоса"
        ]):
            from services.pump_types import get_pump_components_description
            result.response_parts.append(get_pump_components_description())
            return result
        
        # Добавляем контекст из предыдущих сообщений для улучшения поиска
        context_text = ""
        if context.get("recent_messages"):
            # Берем последние 3 сообщения пользователя для контекста
            user_messages = [msg for msg in context["recent_messages"][-5:] if msg.get("role") == "user"]
            if user_messages:
                context_text = " ".join([msg.get("content", "") for msg in user_messages[-3:]])
                # Объединяем контекст с текущим запросом
                enhanced_query = f"{context_text} {query}".strip()
            else:
                enhanced_query = query
        else:
            enhanced_query = query
        
        from services.kb.search import search
        from services.kb.summarize import format_answer
        
        # Выполняем поиск по нормализованному запросу с контекстом
        hits = search(enhanced_query, limit=5)
        
        # Если не нашли результатов с контекстом, пробуем без контекста
        if not hits:
            hits = search(query, limit=5)
        
        # Форматируем ответ с тезисами
        answer = format_answer(query, hits, max_bullets=7)
        result.response_parts.append(answer)
    except Exception as e:
        from services.error_handler import log_error
        log_error(e, "tech_qa.py:handle_tech_qa", 
                 context={"intent": "TECH_QA", "query": query}, session_id=None)
        result.response_parts.append(get_tech_qa_error())
    
    return result
