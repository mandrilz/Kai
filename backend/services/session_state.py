"""
Управление состоянием сессии для запоминания контекста диалога.
Позволяет боту не повторять вопросы и вести естественный диалог.
"""
from typing import Dict, Any, Optional
import json
import os
from datetime import datetime
from pathlib import Path


# Глобальное хранилище состояний сессий (в продакшене лучше Redis или БД)
_session_states: Dict[str, Dict[str, Any]] = {}


def get_session_state(session_id: str) -> Dict[str, Any]:
    """
    Получает состояние сессии.
    
    Returns:
        {
            "liquid_text": str | None,
            "liquid_category": str | None,
            "temp_c": float | None,
            "has_abrasive": bool | None,
            "confidence": str,  # "high" | "medium" | "low"
            "last_question": str | None,  # последний заданный вопрос
            "materials_discussed": bool,  # обсуждали ли материалы
        }
    """
    if session_id not in _session_states:
        _session_states[session_id] = {
            "liquid_text": None,
            "liquid_category": None,
            "temp_c": None,
            "has_abrasive": None,
            "confidence": "low",
            "last_question": None,
            "materials_discussed": False,
            "q": None,
            "h": None,
            "pump_type": None,
        }
    
    return _session_states[session_id]


def update_session_state(session_id: str, updates: Dict[str, Any]) -> None:
    """Обновляет состояние сессии."""
    state = get_session_state(session_id)
    state.update(updates)
    
    # Логируем обновление
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "session_state.py:update_session_state",
                "message": "Session state updated",
                "data": {
                    "session_id": session_id,
                    "updates": updates,
                },
                "sessionId": session_id,
                "runId": "state",
                "hypothesisId": "A"
            }, ensure_ascii=False) + "\n")
    except:
        pass


def clear_session_state(session_id: str) -> None:
    """Очищает состояние сессии."""
    if session_id in _session_states:
        del _session_states[session_id]


def calculate_confidence(state: Dict[str, Any]) -> str:
    """
    Вычисляет уверенность на основе заполненности данных.
    
    Returns:
        "high" | "medium" | "low"
    """
    filled = sum([
        state.get("liquid_category") not in [None, "unknown"],
        state.get("temp_c") is not None,
        state.get("has_abrasive") is not None,
    ])
    
    if filled == 3:
        return "high"
    elif filled >= 1:
        return "medium"
    else:
        return "low"

