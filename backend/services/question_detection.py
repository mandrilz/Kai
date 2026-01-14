"""
Определение вопросов в сообщениях пользователя.
Поддерживает вопросы с "?" и без "?".
"""
import re
from typing import Dict, Any, Tuple


# Вопросительные слова
QUESTION_WORDS = [
    "где", "как", "почему", "зачем", "когда", "сколько", "какой", "какая", "какие",
    "какое", "каков", "кто", "что", "чей", "откуда", "куда", "отчего", "чем",
    "можно ли", "нужно ли", "есть ли", "будет ли", "можно", "нужно", "есть",
]

# Паттерны запросов (действия, которые обычно означают вопрос)
REQUEST_PATTERNS = [
    "подбери", "подобрать", "расскажи", "рассказать", "объясни", "объяснить",
    "подскажи", "подсказать", "покажи", "показать", "дай", "дать", "нужен",
    "нужна", "нужно", "хочу узнать", "интересует", "интересно", "интересует",
    "что такое", "что это", "что значит", "что означает",
]


def is_question(text: str) -> Tuple[bool, str]:
    """
    Определяет, является ли текст вопросом.
    
    Args:
        text: Текст сообщения
        
    Returns:
        (is_question: bool, reason: str) - является ли вопросом и причина
    """
    if not text or not text.strip():
        return False, "empty"
    
    text_lower = text.lower().strip()
    
    # Проверка 1: Есть ли знак вопроса
    if "?" in text:
        return True, "has_question_mark"
    
    # Проверка 2: Начинается ли с вопросительного слова
    for qword in QUESTION_WORDS:
        if text_lower.startswith(qword):
            return True, f"starts_with_{qword}"
    
    # Проверка 3: Содержит ли паттерны запроса
    for pattern in REQUEST_PATTERNS:
        if pattern in text_lower:
            return True, f"contains_request_{pattern}"
    
    # Проверка 4: Эвристика "вопрос без ?"
    # Краткая фраза (до 50 символов) с вопросительным словом в середине
    if len(text_lower) <= 50:
        for qword in QUESTION_WORDS:
            if qword in text_lower:
                # Проверяем, что это не просто упоминание слова
                # Должно быть в начале или после запятой/пробела
                pattern = rf'\b{qword}\b'
                if re.search(pattern, text_lower):
                    return True, f"short_question_with_{qword}"
    
    # Проверка 5: Паттерн "сущ. + контекст запроса"
    # Например: "где производятся насосы кометта", "цена k377", "характеристики k610"
    # Ищем существительные + ключевые слова запроса
    query_keywords = ["где", "цена", "характеристики", "параметры", "описание", "информация"]
    for keyword in query_keywords:
        if keyword in text_lower:
            # Проверяем, что после ключевого слова есть существительное (слово из 3+ букв)
            pattern = rf'{keyword}\s+[а-яёa-z]{{3,}}'
            if re.search(pattern, text_lower):
                return True, f"query_pattern_{keyword}"
    
    # ИСПРАВЛЕНО: Проверка 6: Паттерн "где + глагол + существительное" (например, "где производятся насосы")
    production_patterns = [
        r'где\s+[а-яё]+\s+[а-яё]{3,}',  # "где производятся насосы"
        r'где\s+[а-яё]{3,}\s+[а-яё]+',  # "где насосы производятся"
    ]
    for pattern in production_patterns:
        if re.search(pattern, text_lower):
            return True, f"production_pattern_{pattern}"
    
    return False, "not_a_question"


def should_use_kb_fallback(intent: str, response_text: str, confidence: float = 1.0) -> bool:
    """
    Определяет, нужно ли использовать KB fallback.
    
    Args:
        intent: Определенный интент
        response_text: Текст ответа
        confidence: Уверенность в ответе (если доступна)
        
    Returns:
        True если нужно использовать KB fallback
    """
    # Если это OFF_TOPIC и ответ стандартный - нужен fallback
    if intent == "off_topic":
        # Проверяем, не является ли ответ стандартным "не по теме"
        standard_responses = [
            "я кометтик",
            "инженер-помощник",
            "могу помочь",
            "не по теме"
        ]
        response_lower = response_text.lower()
        if any(standard in response_lower for standard in standard_responses):
            return True
    
    # Если confidence низкая (< 0.7) - нужен fallback
    if confidence < 0.7:
        return True
    
    # Если ответ пустой или очень короткий (< 20 символов) - нужен fallback
    if len(response_text.strip()) < 20:
        return True
    
    return False
