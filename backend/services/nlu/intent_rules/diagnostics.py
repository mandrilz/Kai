"""
Правило для определения интента DIAGNOSTICS.
"""
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult


def check_diagnostics(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос диагностикой проблем с насосом.
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с DIAGNOSTICS или None
    """
    message_lower = message.lower()
    state = context.get("state", {})
    
    # Ключевые слова для диагностики
    diagnostics_keywords = [
        "шумит", "шум", "кавитация", "вибрация", "вибрирует",
        "не работает", "не качает", "перегревается", "греется"
    ]
    
    if any(keyword in message_lower for keyword in diagnostics_keywords):
        # Если в состоянии есть информация о выбранном насосе, добавляем её в data
        selected_pump_data = {}
        if state.get("last_selected_pump"):
            selected_pump_data["last_selected_pump"] = state.get("last_selected_pump")
        
        return IntentResult(
            intent=Intent.DIAGNOSTICS,
            data=selected_pump_data,
            confidence=0.9
        )
    
    return None
