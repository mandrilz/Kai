"""
Правило для определения интента DOCUMENTATION.
Обрабатывает запросы документации, графиков, сравнения насосов.
"""
import re
from typing import Optional, Dict, Any
from services.nlu.types import Intent, IntentResult


def check_documentation(
    message: str,
    context: Dict[str, Any]
) -> Optional[IntentResult]:
    """
    Проверяет, является ли запрос запросом документации/характеристик.
    
    Args:
        message: Сообщение пользователя
        context: Контекст диалога
        
    Returns:
        IntentResult с DOCUMENTATION или None
    """
    message_lower = message.lower()
    state = context.get("state", {})
    
    # Получаем расширенный контекст для поиска
    recent_messages = context.get("recent_messages", [])
    context_text = ""
    if recent_messages:
        user_messages = [msg.get("content", "") for msg in recent_messages[-5:] if msg.get("role") == "user"]
        if user_messages:
            context_text = " ".join(user_messages)
    
    full_context = f"{context_text} {message}".strip() if context_text else message
    search_text = full_context.lower()
    
    # 1. Запрос на сравнение двух насосов
    compare_pattern = re.search(r"сравн[иь]?\s+(?:насос[ы]?|артикул[ы]?)\s+(\d{6,12})\s+(?:и|с)\s+(\d{6,12})", search_text)
    if compare_pattern:
        return IntentResult(
            intent=Intent.DOCUMENTATION,
            data={
                "action": "compare",
                "articul1": compare_pattern.group(1),
                "articul2": compare_pattern.group(2)
            },
            confidence=0.95
        )
    
    # 2. Запрос на построение графика
    plot_keywords = ["построй", "построить", "график", "кривая", "покажи график", "нарисуй"]
    if any(keyword in search_text for keyword in plot_keywords):
        plot_data = {"action": "plot"}
        
        # Ищем артикул Кометта в сообщении
        articul_match = re.search(r'\d{6,12}', message)
        if articul_match:
            plot_data["articul"] = articul_match.group()
        
        # Ищем модель конкурента в сообщении
        competitor_model = None
        competitor_patterns = [
            r'(?:сравни|сравнить|сравнение)\s+(?:с|со|и)\s+([A-Za-zА-Яа-я0-9\s\-\.]+)',
            r'(?:второй|вторая|второго)\s+(?:насос|модель|конкурент)\s+([A-Za-zА-Яа-я0-9\s\-\.]+)',
            r'(?:конкурент|конкурентом)\s+([A-Za-zА-Яа-я0-9\s\-\.]+)',
            r'(?:и|и|vs|против)\s+([A-Za-zА-Яа-я0-9\s\-\.]{3,})',
        ]
        for pattern in competitor_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                competitor_model = match.group(1).strip()
                competitor_model = re.sub(r'\s+', ' ', competitor_model)
                competitor_model = re.sub(r'[.,;:!?]+$', '', competitor_model)
                if len(competitor_model) >= 2:
                    break
        
        if competitor_model:
            plot_data["competitor_model"] = competitor_model
        
        return IntentResult(
            intent=Intent.DOCUMENTATION,
            data=plot_data,
            confidence=0.9
        )
    
    # 3. Запрос документации по ключевым словам
    doc_keywords = [
        "паспорт", "характеристика", "лист данных",
        "datasheet", "manual", "инструкция", "руководство",
        "характеристики", "параметры", "описание", "информация", 
        "кривая", "график", "технические данные"
    ]
    if any(keyword in search_text for keyword in doc_keywords):
        # Проверяем, есть ли модель Кометта в запросе (К/K + 3 цифры)
        kometta_model_pattern = r"\b[кk]\s*\d{3}[\w\s\-\/\.]*"
        match = re.search(kometta_model_pattern, message, re.IGNORECASE)
        if match:
            model_text = match.group(0).strip()
            return IntentResult(
                intent=Intent.DOCUMENTATION,
                data={"model": model_text, "action": "by_model"},
                confidence=0.85
            )
        
        # Проверяем, есть ли артикул или модель в запросе
        model_match = re.search(r'\b[Kk]\d{3,4}\b|\b\d{6,12}\b', message)
        if model_match:
            return IntentResult(
                intent=Intent.DOCUMENTATION,
                data={"action": "info", "model": model_match.group(0)},
                confidence=0.85
            )
        
        return IntentResult(
            intent=Intent.DOCUMENTATION,
            data={},
            confidence=0.8
        )
    
    # 4. Проверяем, является ли сообщение артикулом (только цифры, 6-12 символов)
    articul_pattern = re.match(r"^\d{6,12}$", message.strip())
    if articul_pattern:
        return IntentResult(
            intent=Intent.DOCUMENTATION,
            data={"articul": message.strip(), "action": "by_articul"},
            confidence=0.95
        )
    
    # 5. Запросы на аналоги с артикулом
    analog_with_articul = re.search(r"аналог[и]?\s+(?:насос[а]?\s+)?(?:кометта\s+)?(\d{6,12})", search_text)
    if analog_with_articul:
        articul = analog_with_articul.group(1)
        return IntentResult(
            intent=Intent.DOCUMENTATION,
            data={"articul": articul, "action": "analog_by_articul"},
            confidence=0.9
        )
    
    # 6. Материал корпуса насоса по модели/артикулу
    if any(k in search_text for k in ["из чего сделан", "материал корпуса", "корпус насоса", "из какого материала"]):
        # По артикулу
        articul_any = re.search(r"\b\d{6,12}\b", message)
        if articul_any:
            return IntentResult(
                intent=Intent.DOCUMENTATION,
                data={"action": "body_material_by_articul", "articul": articul_any.group(0)},
                confidence=0.9
            )
        
        # По модели
        model_match = re.search(r"\b[КK]\s*\d{3}[^\n]{0,80}", message, re.IGNORECASE)
        if model_match:
            model_text = model_match.group(0).strip()
            return IntentResult(
                intent=Intent.DOCUMENTATION,
                data={"action": "body_material_by_model", "model": model_text},
                confidence=0.9
            )
    
    # 7. Артикул в тексте
    articul_in_text = re.search(r"(?:артикул|articul)[\s\w]*?(\d{6,12})", search_text)
    if articul_in_text:
        articul = articul_in_text.group(1)
        return IntentResult(
            intent=Intent.DOCUMENTATION,
            data={"articul": articul, "action": "by_articul"},
            confidence=0.9
        )
    
    # 8. Контекстные вопросы о ранее выбранном насосе
    context_question_keywords = [
        "этот насос", "этот", "его", "него", "насос", "про него", "про этот",
        "характеристики", "параметры", "мощность", "артикул"
    ]
    if (any(keyword in message_lower for keyword in context_question_keywords) and 
        state.get("last_selected_pump")):
        last_pump = state.get("last_selected_pump")
        if isinstance(last_pump, dict) and last_pump.get("articul"):
            return IntentResult(
                intent=Intent.DOCUMENTATION,
                data={
                    "articul": last_pump.get("articul"),
                    "action": "by_articul",
                    "from_context": True
                },
                confidence=0.85
            )
    
    return None
