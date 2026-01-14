"""
Правило для определения интента ANALOG_BY_MODEL.
"""
import re
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult
from services.intents import detect_model_name, extract_brand_and_model


def check_analog_by_model(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос поиском аналога по модели конкурента.
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с ANALOG_BY_MODEL или None
    """
    message_lower = message.lower()
    
    # Получаем расширенный контекст для поиска
    recent_messages = context.get("recent_messages", [])
    context_text = ""
    if recent_messages:
        user_messages = [msg.get("content", "") for msg in recent_messages[-5:] if msg.get("role") == "user"]
        if user_messages:
            context_text = " ".join(user_messages)
    
    full_context = f"{context_text} {message}".strip() if context_text else message
    search_text = full_context.lower()
    
    # 1. Запросы на аналоги по бренду
    analog_by_brand = re.search(r"аналог[и]?\s+(?:насос[а]?|для)\s+(grundfos|cnp|wilo|pedrollo)", search_text)
    if analog_by_brand:
        brand = analog_by_brand.group(1).upper()
        return IntentResult(
            intent=Intent.ANALOG_BY_MODEL,
            data={"brand": brand, "action": "by_brand"},
            confidence=0.9
        )
    
    # 2. Определение модели конкурента
    model_name = detect_model_name(message)
    brand_model = extract_brand_and_model(message) if model_name else None
    
    if model_name:
        # Проверяем, что это действительно модель, а не числа
        model_keywords = ["модел", "аналог", "cnp", "grundfos", "wilo", "pedrollo", "конкурент"]
        if any(keyword in search_text for keyword in model_keywords):
            return IntentResult(
                intent=Intent.ANALOG_BY_MODEL,
                data={
                    "model": model_name,
                    "brand": brand_model.get("brand") if brand_model else None,
                    "model_only": brand_model.get("model") if brand_model else None
                },
                confidence=0.85
            )
        
        # Если модель найдена, но нет Q/H данных - это аналог
        from services.intents import extract_qh_from_text
        qh_data = extract_qh_from_text(message)
        if not qh_data:
            return IntentResult(
                intent=Intent.ANALOG_BY_MODEL,
                data={"model": model_name},
                confidence=0.75
            )
    
    return None
