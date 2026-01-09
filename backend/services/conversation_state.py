"""
Управление состоянием диалога с историей сообщений и слотами.
Реализует полноценную память диалога для контекстного понимания.
"""
from typing import Dict, Any, Optional, List, Tuple
import json
import os
from datetime import datetime
from pathlib import Path

# Временное хранилище для значений температуры без знака
_temp_without_sign: Dict[str, float] = {}


# Глобальное хранилище (в продакшене лучше Redis или БД)
_conversations: Dict[str, Dict[str, Any]] = {}

def cleanup_expired_conversations(ttl_hours: Optional[float] = None) -> int:
    """
    Очищает устаревшие диалоги из conversation_state (MVP in-memory).

    Args:
        ttl_hours: TTL в часах. Если None, берется из env CONVERSATION_TTL_HOURS (по умолчанию 24).

    Returns:
        Количество удаленных сессий
    """
    if ttl_hours is None:
        try:
            ttl_hours = float(os.getenv("CONVERSATION_TTL_HOURS", "24"))
        except Exception:
            ttl_hours = 24.0

    if ttl_hours <= 0:
        return 0

    now = datetime.now()
    deleted = 0
    to_delete = []
    for sid, conv in _conversations.items():
        updated_at = conv.get("updated_at")
        try:
            dt = datetime.fromisoformat(updated_at) if updated_at else now
            age_hours = (now - dt).total_seconds() / 3600.0
            if age_hours > ttl_hours:
                to_delete.append(sid)
        except Exception:
            to_delete.append(sid)

    for sid in to_delete:
        _conversations.pop(sid, None)
        _temp_without_sign.pop(sid, None)
        deleted += 1

    return deleted


# Схема слотов для подбора насоса
SLOT_SCHEMA = {
    "fluid": {"type": str, "description": "Тип жидкости (вода, этиленгликоль, масло и т.д.)"},
    "temperature_c": {"type": float, "description": "Температура жидкости в градусах Цельсия"},
    "flow_m3h": {"type": float, "description": "Расход в м³/ч"},
    "head_m": {"type": float, "description": "Напор в метрах"},
    "viscosity": {"type": float, "description": "Вязкость (если нужно)"},
    "concentration": {"type": float, "description": "Концентрация (для этиленгликоля и т.д.)"},
    "solids": {"type": bool, "description": "Наличие твердых частиц/примесей"},
    "installation": {"type": str, "description": "Тип установки (вертикальный/горизонтальный)"},
    "materials": {"type": str, "description": "Требуемые материалы (A/E/X/H)"},
    "body_material_code": {"type": str, "description": "Материал корпуса насоса (код: 04=304, 16=316, 25=чугун)"},
    "h_st": {"type": float, "description": "Статический напор сети"},
    "pending_analog_confirmation": {"type": dict, "description": "Ожидание подтверждения модели для поиска аналога"},
}


def get_temp_without_sign(session_id: str) -> Optional[float]:
    """Получает сохраненное значение температуры без знака для сессии."""
    return _temp_without_sign.get(session_id)


def set_temp_without_sign(session_id: str, temp: float) -> None:
    """Сохраняет значение температуры без знака для сессии."""
    _temp_without_sign[session_id] = temp


def clear_temp_without_sign(session_id: str) -> None:
    """Очищает сохраненное значение температуры без знака."""
    if session_id in _temp_without_sign:
        del _temp_without_sign[session_id]


def get_conversation(session_id: str) -> Dict[str, Any]:
    """
    Получает полное состояние диалога.
    
    Args:
        session_id: ID сессии (валидируется)
    
    Returns:
        {
            "messages": List[Dict],  # История сообщений [{"role": "user|assistant", "content": "...", "timestamp": "..."}]
            "state": Dict,  # Заполненные слоты
            "pending_slot": str | None,  # Какой слот сейчас уточняется
            "last_question": str | None,  # Последний заданный вопрос
            "dialog_summary": str | None,  # Краткое резюме диалога
            "updated_at": str,
            "created_at": str
        }
    
    Raises:
        ValueError: если session_id пустой или невалидный
    """
    # Валидация session_id
    if not session_id or not isinstance(session_id, str) or not session_id.strip():
        raise ValueError(f"session_id не может быть пустым или невалидным: {session_id}")
    
    session_id = session_id.strip()

    # Ленивая уборка старых диалогов (чтобы не разрасталась память)
    try:
        cleanup_expired_conversations()
    except Exception:
        pass
    
    if session_id not in _conversations:
        _conversations[session_id] = {
            "messages": [],
            "state": {slot: None for slot in SLOT_SCHEMA.keys()},
            "pending_slot": None,
            "last_question": None,
            "dialog_summary": None,
            "updated_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat()
        }
    
    return _conversations[session_id]


def add_message(session_id: str, role: str, content: str) -> None:
    """Добавляет сообщение в историю диалога."""
    conv = get_conversation(session_id)
    conv["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    conv["updated_at"] = datetime.now().isoformat()
    
    # Авто-резюме если диалог длинный (>30 сообщений)
    if len(conv["messages"]) > 30:
        generate_summary(session_id)


def update_state(session_id: str, updates: Dict[str, Any], pending_slot: Optional[str] = None, keep_pending_if_not_set: bool = True) -> None:
    """
    Обновляет слоты состояния.
    
    Args:
        session_id: ID сессии
        updates: обновления слотов
        pending_slot: новый pending_slot (если None и keep_pending_if_not_set=True, старый сохраняется)
        keep_pending_if_not_set: если True, не сбрасывать pending_slot если он не передан явно
    """
    conv = get_conversation(session_id)
    
    # Валидация и обновление слотов
    for slot, value in updates.items():
        if slot in SLOT_SCHEMA:
            slot_type = SLOT_SCHEMA[slot]["type"]
            if value is not None:
                # Приведение типов
                try:
                    if slot_type == float:
                        conv["state"][slot] = float(value)
                    elif slot_type == bool:
                        conv["state"][slot] = bool(value)
                    elif slot_type == str:
                        conv["state"][slot] = str(value)
                    else:
                        conv["state"][slot] = value
                except (ValueError, TypeError):
                    # Если не удалось привести тип, сохраняем как есть
                    conv["state"][slot] = value
    
    # КРИТИЧНО: обновляем pending_slot только если он передан явно
    # Если keep_pending_if_not_set=True и pending_slot=None, сохраняем старый
    if pending_slot is not None:
        conv["pending_slot"] = pending_slot
    elif not keep_pending_if_not_set:
        # Явно сбросить pending_slot (передан None и keep_pending_if_not_set=False)
        conv["pending_slot"] = None
    
    conv["updated_at"] = datetime.now().isoformat()
    
    # Логирование
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "conversation_state.py:update_state",
                "message": "State updated",
                "data": {
                    "session_id": session_id,
                    "updates": updates,
                    "pending_slot": pending_slot
                },
                "sessionId": session_id,
                "runId": "state",
                "hypothesisId": "UPDATE"
            }, ensure_ascii=False) + "\n")
    except:
        pass


def set_last_question(session_id: str, question: str) -> None:
    """Устанавливает последний заданный вопрос."""
    conv = get_conversation(session_id)
    conv["last_question"] = question
    conv["updated_at"] = datetime.now().isoformat()


def get_recent_messages(session_id: str, n: int = 10) -> List[Dict[str, str]]:
    """Возвращает последние N сообщений."""
    conv = get_conversation(session_id)
    return conv["messages"][-n:]


def get_context_for_model(session_id: str, max_messages: int = 20) -> Dict[str, Any]:
    """
    Формирует контекст для модели.
    
    Returns:
        {
            "state": Dict,  # Текущее заполнение слотов
            "pending_slot": str | None,
            "last_question": str | None,
            "dialog_summary": str | None,
            "recent_messages": List[Dict],  # Последние сообщения
            "full_message_count": int
        }
    """
    conv = get_conversation(session_id)
    
    # Дополняем контекст состоянием материалов (session_state.py),
    # чтобы бот сохранял контекст материалов и мог продолжать диалог без повторов.
    try:
        from services.session_state import get_session_state
        materials_state = get_session_state(session_id).copy()
    except Exception:
        materials_state = None

    return {
        "session_id": session_id,  # Добавляем session_id в context
        "state": conv["state"].copy(),
        "pending_slot": conv["pending_slot"],
        "last_question": conv["last_question"],
        "dialog_summary": conv["dialog_summary"],
        "recent_messages": get_recent_messages(session_id, max_messages),
        "full_message_count": len(conv["messages"]),
        "materials_state": materials_state,
    }


def generate_summary(session_id: str) -> None:
    """Генерирует краткое резюме диалога и очищает старые сообщения."""
    conv = get_conversation(session_id)
    
    if len(conv["messages"]) <= 20:
        return  # Не нужно резюме для коротких диалогов
    
    # Простое резюме на основе заполненных слотов
    filled_slots = {k: v for k, v in conv["state"].items() if v is not None}
    
    summary_parts = []
    if filled_slots.get("fluid"):
        summary_parts.append(f"Жидкость: {filled_slots['fluid']}")
    if filled_slots.get("temperature_c"):
        summary_parts.append(f"Температура: {filled_slots['temperature_c']}°C")
    if filled_slots.get("flow_m3h"):
        summary_parts.append(f"Расход: {filled_slots['flow_m3h']} м³/ч")
    if filled_slots.get("head_m"):
        summary_parts.append(f"Напор: {filled_slots['head_m']} м")
    
    if summary_parts:
        conv["dialog_summary"] = ". ".join(summary_parts) + "."
    else:
        conv["dialog_summary"] = "Диалог начат, параметры уточняются."
    
    # Оставляем только последние 10 сообщений
    conv["messages"] = conv["messages"][-10:]
    conv["updated_at"] = datetime.now().isoformat()


def clear_conversation(session_id: str) -> None:
    """Очищает диалог."""
    if session_id in _conversations:
        del _conversations[session_id]

    # Также очищаем состояние материалов, чтобы не было рассинхронизации
    try:
        from services.session_state import clear_session_state
        clear_session_state(session_id)
    except Exception:
        pass

    # И очищаем временное значение температуры без знака
    try:
        clear_temp_without_sign(session_id)
    except Exception:
        pass


def parse_short_answer(text: str, pending_slot: Optional[str], session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Парсит ответы с привязкой к pending_slot.
    Более гибкий: работает даже если текст длиннее 30 символов, если есть pending_slot.
    
    Args:
        text: текст сообщения
        pending_slot: ожидаемый слот
        session_id: ID сессии (для работы с сохраненными значениями температуры без знака)
    
    Returns:
        {"updates": {slot: value}, "confidence": float, "next_slot": str | None, "needs_sign_clarification": bool, "detected_value": float | None} или None
    """
    if not pending_slot:
        return None
    
    text_lower = text.lower().strip()
    
    # Специальная обработка: если pending_slot="temperature_c" и есть сохраненное значение без знака
    # Парсим ответ на вопрос о знаке ("плюс", "минус", "+", "-")
    if pending_slot == "temperature_c" and session_id:
        saved_temp = get_temp_without_sign(session_id)
        if saved_temp is not None:
            # Парсим ответ о знаке
            if any(word in text_lower for word in ["минус", "минусовая", "отрицательная", "ниже нуля", "-", "минус"]):
                clear_temp_without_sign(session_id)
                return {
                    "updates": {"temperature_c": -saved_temp},
                    "confidence": 0.95,
                    "next_slot": None,
                    "needs_sign_clarification": False
                }
            elif any(word in text_lower for word in ["плюс", "плюсовая", "положительная", "выше нуля", "+", "плюс"]):
                clear_temp_without_sign(session_id)
                return {
                    "updates": {"temperature_c": saved_temp},
                    "confidence": 0.95,
                    "next_slot": None,
                    "needs_sign_clarification": False
                }
    
    # Парсинг температуры (более гибкий - понимает разные форматы, включая минусовые и плюсовые)
    if pending_slot == "temperature_c":
        import re
        
        # Приоритет 1: Проверяем "минус" как слово
        minus_word_match = re.search(r'минус\s+(\d+(?:[.,]\d+)?)', text_lower)
        if minus_word_match:
            try:
                temp = -float(minus_word_match.group(1).replace(',', '.'))
                if -50 <= temp <= 200:
                    return {
                        "updates": {"temperature_c": temp},
                        "confidence": 0.9,
                        "next_slot": None,
                        "needs_sign_clarification": False
                    }
            except (ValueError, IndexError):
                pass
        
        # Приоритет 2: Проверяем "плюс" как слово (приравнивается к положительному)
        plus_word_match = re.search(r'плюс\s+(\d+(?:[.,]\d+)?)', text_lower)
        if plus_word_match:
            try:
                temp = float(plus_word_match.group(1).replace(',', '.'))
                if -50 <= temp <= 200:
                    return {
                        "updates": {"temperature_c": temp},
                        "confidence": 0.9,
                        "next_slot": None,
                        "needs_sign_clarification": False
                    }
            except (ValueError, IndexError):
                pass
        
        # Приоритет 3: Паттерны с явным знаком (+, -)
        patterns_with_sign = [
            r'([+-]\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп|с\b|c\b)',
            r'([+-]\d+(?:[.,]\d+)?)\s*(?:°|c\b|с\b)',
        ]
        for pattern in patterns_with_sign:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                try:
                    temp_str = match.group(1).replace(',', '.')
                    temp = float(temp_str)
                    if -50 <= temp <= 200:
                        return {
                            "updates": {"temperature_c": temp},
                            "confidence": 0.9,
                            "next_slot": None,
                            "needs_sign_clarification": False
                        }
                except (ValueError, IndexError):
                    pass
        
        # Приоритет 4: Паттерны без явного знака (может быть положительное или отрицательное)
        patterns_without_sign = [
            r'(\d+(?:[.,]\d+)?)\s*(?:градус|°|degree|temp|темп|с\b|c\b)',
            r'(?:темп|temp)[\s:]+(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*(?:°|c\b|с\b)',
            r'(\d+(?:[.,]\d+)?)(?:\s|$)'  # Просто число в начале/конце
        ]
        for pattern in patterns_without_sign:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                try:
                    temp_str = match.group(1).replace(',', '.')
                    temp = float(temp_str)
                    if -50 <= temp <= 200:
                        # Если число без знака - сохраняем значение и нужно уточнить знак
                        if session_id:
                            set_temp_without_sign(session_id, temp)
                        return {
                            "updates": {},  # Не обновляем, нужно уточнить знак
                            "confidence": 0.7,
                            "next_slot": "temperature_c",  # Оставляем тот же слот
                            "needs_sign_clarification": True,
                            "detected_value": temp  # Сохраняем найденное значение
                        }
                except (ValueError, IndexError):
                    pass
    
    # Парсинг расхода (используем q_extractor - он понимает все единицы)
    elif pending_slot == "flow_m3h":
        from services.q_extractor import extract_q_from_text
        q_data = extract_q_from_text(text)
        if q_data and q_data.get("q_m3h"):
            return {
                "updates": {"flow_m3h": q_data["q_m3h"]},
                "confidence": q_data.get("confidence", 0.8),
                "next_slot": None
            }
    
    # Парсинг напора (используем h_extractor - он понимает все единицы)
    elif pending_slot == "head_m":
        from services.h_extractor import extract_h_from_text
        h_data = extract_h_from_text(text)
        if h_data and h_data.get("h_m"):
            return {
                "updates": {"head_m": h_data["h_m"]},
                "confidence": h_data.get("confidence", 0.8),
                "next_slot": None
            }
    
    # Парсинг статического напора
    elif pending_slot == "h_st":
        from services.h_extractor import extract_h_from_text
        h_data = extract_h_from_text(text)
        if h_data and h_data.get("h_m"):
            return {
                "updates": {"h_st": h_data["h_m"]},
                "confidence": h_data.get("confidence", 0.8),
                "next_slot": None
            }
    
    # Парсинг жидкости (более гибкий - ищет даже в длинных текстах)
    elif pending_slot == "fluid":
        fluid_keywords = {
            "этиленгликоль": "этиленгликоль",
            "пропиленгликоль": "пропиленгликоль",
            "вода": "вода",
            "water": "вода",
            "масло": "масло",
            "oil": "масло",
            "гликоль": "этиленгликоль",
            "антифриз": "этиленгликоль"
        }
        for keyword, fluid in fluid_keywords.items():
            if keyword in text_lower:
                return {
                    "updates": {"fluid": fluid},
                    "confidence": 0.85,
                    "next_slot": None
                }
    
    # Парсинг наличия примесей (да/нет)
    elif pending_slot == "solids":
        if any(word in text_lower for word in ["да", "yes", "есть", "присутствуют", "имеются"]):
            return {
                "updates": {"solids": True},
                "confidence": 0.8,
                "next_slot": None
            }
        elif any(word in text_lower for word in ["нет", "no", "нету", "отсутствуют", "без"]):
            return {
                "updates": {"solids": False},
                "confidence": 0.8,
                "next_slot": None
            }
    
    return None
