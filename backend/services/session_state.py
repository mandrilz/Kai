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


def _validate_session_id(session_id: str) -> str:
    """Базовая валидация session_id (чтобы не терять контекст из-за пустых/битых id)."""
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        raise ValueError(f"session_id не может быть пустым или невалидным: {session_id}")
    return session_id.strip()


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
            "created_at": str,
            "updated_at": str,
        }
    """
    session_id = _validate_session_id(session_id)
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
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    return _session_states[session_id]


def update_session_state(session_id: str, updates: Dict[str, Any]) -> None:
    """Обновляет состояние сессии."""
    session_id = _validate_session_id(session_id)
    state = get_session_state(session_id)
    state.update(updates)
    state["updated_at"] = datetime.now().isoformat()
    
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
    session_id = _validate_session_id(session_id)
    if session_id in _session_states:
        del _session_states[session_id]


def cleanup_expired_sessions(ttl_hours: Optional[float] = None) -> int:
    """
    Очищает устаревшие сессии из session_state (MVP in-memory).

    Args:
        ttl_hours: TTL в часах. Если None, берется из env SESSION_STATE_TTL_HOURS (по умолчанию 24).

    Returns:
        Количество удаленных сессий
    """
    if ttl_hours is None:
        try:
            ttl_hours = float(os.getenv("SESSION_STATE_TTL_HOURS", "24"))
        except Exception:
            ttl_hours = 24.0

    if ttl_hours <= 0:
        return 0

    now = datetime.now()
    deleted = 0
    to_delete = []
    for sid, st in _session_states.items():
        updated_at = st.get("updated_at")
        try:
            if updated_at:
                dt = datetime.fromisoformat(updated_at)
            else:
                dt = datetime.fromisoformat(st.get("created_at")) if st.get("created_at") else now
            age_hours = (now - dt).total_seconds() / 3600.0
            if age_hours > ttl_hours:
                to_delete.append(sid)
        except Exception:
            # Если дата битая — лучше удалить, чем держать мусор
            to_delete.append(sid)

    for sid in to_delete:
        _session_states.pop(sid, None)
        deleted += 1

    return deleted


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

