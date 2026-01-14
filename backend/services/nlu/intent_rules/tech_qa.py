"""
Правило для определения интента TECH_QA.
"""
import re
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult
from services.question_detection import is_question as detect_question


def check_tech_qa(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос техническим вопросом для поиска в базе знаний.
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с TECH_QA или None
    """
    message_lower = message.lower()
    
    # 1. Специфичные вопросы о типах насосов и компонентах
    if any(phrase in message_lower for phrase in [
        "какие типы насосов", "какие типы есть", "типы насосов в ассортименте",
        "какие насосы есть", "какие насосы в линейке", "ассортимент насосов",
        "из чего состоит насос", "компоненты насоса", "части насоса",
        "состав насоса", "устройство насоса", "конструкция насоса"
    ]):
        return IntentResult(
            intent=Intent.TECH_QA,
            data={"query": message},
            confidence=0.9
        )
    
    # 2. Проверяем, является ли сообщение вопросом
    is_question, question_reason = detect_question(message)
    
    # Проверяем, что это не конкретный технический запрос
    # (Q/H, модель, артикул уже проверили в других правилах)
    if is_question and len(message.strip()) > 10:
        # Дополнительная проверка: не содержит ли запрос конкретных технических параметров
        has_technical_params = (
            "q=" in message_lower or "h=" in message_lower or
            "м3/ч" in message_lower or "м³/ч" in message_lower or
            re.search(r'\d{6,12}', message) is not None  # артикул
        )
        
        if not has_technical_params:
            return IntentResult(
                intent=Intent.TECH_QA,
                data={"query": message},
                confidence=0.75
            )
    
    return None
