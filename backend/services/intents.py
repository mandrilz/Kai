"""
Определение интентов пользовательских сообщений.
"""
import re
from typing import Optional, Dict, Any


class Intent:
    """Типы интентов."""
    SELECTION_BY_POINT = "selection_by_point"  # Подбор по рабочей точке
    ANALOG_BY_MODEL = "analog_by_model"  # Аналог по модели конкурента
    FILE_UPLOAD = "file_upload"  # Шильдик / PDF / фото
    DIAGNOSTICS = "diagnostics"  # Диагностика
    DOCUMENTATION = "documentation"  # Документация
    OFF_TOPIC = "off_topic"  # Не по теме


def extract_qh_from_text(text: str) -> Optional[Dict[str, float]]:
    """
    Извлекает Q и H из текста.
    
    Ищет паттерны типа:
    - Q=10, H=20
    - расход 10 м³/ч, напор 20 м
    - 10 м³/ч, 20 м
    - подача 10 м³/ч и напор 30 м
    
    Returns:
        {"q": float, "h": float} или None
    """
    # #region agent log
    import json
    import os
    from datetime import datetime
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "intents.py:18",
                "message": "Extracting Q and H from text",
                "data": {"input_text": text},
                "sessionId": "analysis",
                "runId": "analysis",
                "hypothesisId": "A"
            }) + "\n")
    except: pass
    # #endregion
    text_lower = text.lower()
    
    # Паттерн 1: Q=10, H=20 или Q:10, H:20 или Q 10 и H 20 (без знака =)
    # Улучшенный: учитывает единицы измерения между Q и H
    pattern1 = r"q\s*[=:]?\s*(\d+\.?\d*)\s*(?:м[³3]/ч|м3/ч|л/с|л/мин)?\s*[,\s]+(?:и\s+)?h\s*[=:]?\s*(\d+\.?\d*)\s*(?:м|метр[ов]?)?"
    match1 = re.search(pattern1, text_lower)
    if match1:
        result = {"q": float(match1.group(1)), "h": float(match1.group(2))}
        # #region agent log
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "intents.py:56",
                    "message": "Q and H extracted (pattern1)",
                    "data": {"extracted": result, "pattern": "pattern1"},
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        return result
    
    # Паттерн 2: расход/подача ... напор ... (улучшенный)
    pattern2 = r"(?:расход[а]?|подач[аи]?)\s*(\d+\.?\d*)\s*(?:м[³3]/ч|м3/ч|л/с|л/мин)?\s*(?:и|с|,)\s*напор[а]?\s*(\d+\.?\d*)\s*м"
    match2 = re.search(pattern2, text_lower)
    if match2:
        return {"q": float(match2.group(1)), "h": float(match2.group(2))}
    
    # Паттерн 3: числа с единицами измерения (улучшенный)
    pattern3 = r"(\d+\.?\d*)\s*м[³3]/ч\s*(?:и|с|,)\s*(\d+\.?\d*)\s*м"
    match3 = re.search(pattern3, text_lower)
    if match3:
        result = {"q": float(match3.group(1)), "h": float(match3.group(2))}
        # #region agent log
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "intents.py:68",
                    "message": "Q and H extracted (pattern3)",
                    "data": {"extracted": result, "pattern": "pattern3"},
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        return result
    
    # Паттерн 3.5: "X кубов на Y метров" или "X кубов на Y м" (с возможными словами перед "кубов")
    pattern3_5 = r"(\d+\.?\d*)\s*куб[ов]?\s+на\s+(\d+\.?\d*)\s*(?:метр[ов]?|м\b)"
    match3_5 = re.search(pattern3_5, text_lower)
    if match3_5:
        result = {"q": float(match3_5.group(1)), "h": float(match3_5.group(2))}
        # #region agent log
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "intents.py:95",
                    "message": "Q and H extracted (pattern3_5 - кубов на метров)",
                    "data": {"extracted": result, "pattern": "pattern3_5"},
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        return result
    
    # Паттерн 4: "подача X м³/ч и напор Y м" или "расход X м³/ч напор Y м"
    pattern4 = r"(?:подач[аи]|расход)\s+(\d+\.?\d*)\s*м[³3]/ч\s+(?:и\s+)?напор\s+(\d+\.?\d*)\s*м"
    match4 = re.search(pattern4, text_lower)
    if match4:
        result = {"q": float(match4.group(1)), "h": float(match4.group(2))}
        # #region agent log
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "intents.py:53",
                    "message": "Q and H extracted (pattern4)",
                    "data": {"extracted": result, "pattern": "pattern4"},
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        return result
    
    # Паттерн 5: просто два числа подряд (только если есть ключевые слова)
    # НО сначала проверяем, нет ли "кубов на ... метров" - это более специфичный паттерн
    # ВАЖНО: Этот паттерн должен быть последним, чтобы не перехватывать правильные паттерны
    if any(word in text_lower for word in ["подача", "расход", "напор", "м³/ч", "м3/ч", "кубов", "куб"]):
        # Ищем числа с контекстом (Q перед первым числом, H перед вторым)
        # Или числа в формате "X м³/ч, Y м"
        pattern5_qh = r"(\d+\.?\d*)\s*(?:м[³3]/ч|м3/ч)\s*[,\s]+(?:и\s+)?(\d+\.?\d*)\s*(?:м|метр[ов]?)"
        match5_qh = re.search(pattern5_qh, text_lower)
        if match5_qh:
            result = {"q": float(match5_qh.group(1)), "h": float(match5_qh.group(2))}
            return result
        
        # Если не нашли специфичный паттерн, пробуем общий поиск чисел
        numbers = re.findall(r"\d+\.?\d*", text)
        if len(numbers) >= 2:
            # Пробуем интерпретировать как Q и H
            try:
                q = float(numbers[0])
                h = float(numbers[1])
                # Более строгие проверки: Q обычно меньше 1000, H может быть до 500
                # НО: если H слишком маленький (< 5), возможно это ошибка парсинга
                if 0.1 < q < 1000 and 0.1 < h < 500 and h >= 5:  # Минимальный H = 5м
                    result = {"q": q, "h": h}
                    # #region agent log
                    import json
                    import os
                    from datetime import datetime
                    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "timestamp": datetime.now().isoformat(),
                                "location": "intents.py:66",
                                "message": "Q and H extracted (pattern5)",
                                "data": {"extracted": result, "numbers_found": numbers},
                                "sessionId": "analysis",
                                "runId": "analysis",
                                "hypothesisId": "A"
                            }) + "\n")
                    except: pass
                    # #endregion
                    return result
            except:
                pass
    
    # #region agent log
    import json
    import os
    from datetime import datetime
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "intents.py:71",
                "message": "Q and H extraction failed",
                "data": {"input_text": text},
                "sessionId": "analysis",
                "runId": "analysis",
                "hypothesisId": "A"
            }) + "\n")
    except: pass
    # #endregion
    return None


def detect_model_name(text: str) -> Optional[str]:
    """
    Определяет, есть ли в тексте название модели насоса.
    
    Ищет паттерны типа:
    - CNP CDMF 1-3
    - CNP CDM 5-6
    - Grundfos CR
    - модель ...
    - аналог насоса CNP CDMF 2-2
    
    Returns:
        название модели или None
    """
    text_upper = text.upper()
    
    # Сначала проверяем ключевые слова для моделей
    text_lower = text.lower()
    model_keywords = ["модел", "аналог", "насос", "cnp", "grundfos", "wilo", "pedrollo"]
    has_model_keyword = any(keyword in text_lower for keyword in model_keywords)
    
    # СНАЧАЛА проверяем короткие модели типа "cdm 2-2" (без CNP) - проверяем в нижнем регистре
    short_model_pattern = r"\b([a-z]{2,4})\s+(\d+)-(\d+)\b"
    match_short = re.search(short_model_pattern, text_lower)
    if match_short:
        model = f"{match_short.group(1).upper()} {match_short.group(2)}-{match_short.group(3)}"
        return model
    
    # Паттерны моделей (более точные)
    model_patterns = [
        r"CNP\s+[A-Z0-9]+\s+[0-9]+-[0-9]+",  # CNP CDMF 1-3
        r"CNP\s+[A-Z0-9]+\s+[0-9]+",  # CNP CDM 5
        r"CNP\s+[A-Z0-9]+",  # CNP CDMF
        r"GRUNDFOS\s+[A-Z0-9\s\-]+",
        r"WILO\s+[A-Z0-9\s\-]+",
        r"PEDROLLO\s+[A-Z0-9\s\-]+",
        r"модел[иь]?\s+([A-Z0-9\s\-]+)",
        r"аналог\s+насос[а]?\s+([A-Z0-9\s\-]+)",
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, text_upper)
        if match:
            model = match.group(1) if match.lastindex and match.lastindex > 0 else match.group(0)
            model = model.strip()
            # Убираем лишние слова
            model = re.sub(r"^(МОДЕЛ[ИЬ]?|АНАЛОГ|НАСОС[А]?)\s+", "", model, flags=re.IGNORECASE)
            model = model.strip()
            if len(model) >= 3:  # Минимальная длина
                return model
    
    # Если есть ключевые слова, но паттерн не сработал, пробуем найти любую модель
    if has_model_keyword:
        # Ищем паттерн: буквы, пробел, буквы/цифры, возможно дефис
        general_pattern = r"([A-Z]{2,}\s+[A-Z0-9]+(?:\s*-\s*[0-9]+)?)"
        match = re.search(general_pattern, text_upper)
        if match:
            model = match.group(1).strip()
            if len(model) >= 3:
                return model
    
    return None


def detect_intent(
    message: str,
    has_attachments: bool = False
) -> Dict[str, Any]:
    """
    Определяет интент сообщения.
    
    Args:
        message: текст сообщения
        has_attachments: есть ли вложения
        
    Returns:
        {
            "intent": str,
            "data": dict  # дополнительные данные (Q, H, модель и т.д.)
        }
    """
    message_lower = message.lower().strip()
    
    # Если есть вложения
    if has_attachments:
        return {
            "intent": Intent.FILE_UPLOAD,
            "data": {}
        }
    
    # Диагностика
    diagnostics_keywords = [
        "шумит", "шум", "кавитация", "вибрация", "вибрирует",
        "не работает", "не качает", "перегревается", "греется"
    ]
    if any(keyword in message_lower for keyword in diagnostics_keywords):
        return {
            "intent": Intent.DIAGNOSTICS,
            "data": {}
        }
    
    # Запрос на сравнение двух насосов (например, "Сравнить насосы 14101003 и 14101004")
    compare_pattern = re.search(r"сравн[иь]?\s+(?:насос[ы]?|артикул[ы]?)\s+(\d{6,12})\s+(?:и|с)\s+(\d{6,12})", message_lower)
    if compare_pattern:
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {
                "action": "compare",
                "articul1": compare_pattern.group(1),
                "articul2": compare_pattern.group(2)
            }
        }
    
    # Запрос на построение графика
    plot_keywords = ["построй", "построить", "график", "кривая", "покажи график", "нарисуй"]
    if any(keyword in message_lower for keyword in plot_keywords):
        return {
            "intent": Intent.DOCUMENTATION,  # Используем DOCUMENTATION для графиков
            "data": {"action": "plot"}
        }
    
    # Документация
    doc_keywords = [
        "паспорт", "характеристика", "лист данных",
        "datasheet", "manual", "инструкция", "руководство"
    ]
    if any(keyword in message_lower for keyword in doc_keywords):
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {}
        }
    
    # Проверяем, является ли сообщение артикулом (только цифры, 6-12 символов)
    articul_pattern = re.match(r"^\d{6,12}$", message.strip())
    if articul_pattern:
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {"articul": message.strip(), "action": "by_articul"}
        }
    
    # Проверяем запросы на аналоги с артикулом (например, "аналоги насоса Кометта 11101013" или "аналог насоса 14101003")
    # Улучшенный паттерн: учитывает различные варианты формулировок
    analog_with_articul = re.search(r"аналог[и]?\s+(?:насос[а]?\s+)?(?:кометта\s+)?(\d{6,12})", message_lower)
    if analog_with_articul:
        articul = analog_with_articul.group(1)
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {"articul": articul, "action": "analog_by_articul"}
        }
    
    # Проверяем запросы на аналоги по бренду (например, "аналоги Grundfos")
    analog_by_brand = re.search(r"аналог[и]?\s+(?:насос[а]?|для)\s+(grundfos|cnp|wilo|pedrollo)", message_lower)
    if analog_by_brand:
        brand = analog_by_brand.group(1).upper()
        return {
            "intent": Intent.ANALOG_BY_MODEL,
            "data": {"brand": brand, "action": "by_brand"}
        }
    
    # Проверяем, есть ли артикул в тексте (например, "Артикул насоса 11101048")
    articul_in_text = re.search(r"(?:артикул|articul)[\s\w]*?(\d{6,12})", message_lower)
    if articul_in_text:
        articul = articul_in_text.group(1)
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {"articul": articul, "action": "by_articul"}
        }
    
    # СНАЧАЛА проверяем модель конкурента (чтобы не парсить CNP CDM 5-6 как Q=5, H=6)
    model_name = detect_model_name(message)
    # #region agent log
    import json
    import os
    from datetime import datetime
    log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "location": "intents.py:179",
                "message": "Model name detection",
                "data": {"detected_model": model_name, "message": message},
                "sessionId": "analysis",
                "runId": "analysis",
                "hypothesisId": "B"
            }) + "\n")
    except: pass
    # #endregion
    if model_name:
        # Проверяем, что это действительно модель, а не числа
        # Если в тексте есть ключевые слова для моделей
        model_keywords = ["модел", "аналог", "cnp", "grundfos", "wilo", "pedrollo", "конкурент"]
        if any(keyword in message_lower for keyword in model_keywords):
            # #region agent log
            import json
            import os
            from datetime import datetime
            log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "intents.py:186",
                        "message": "Intent set to ANALOG_BY_MODEL",
                        "data": {"model": model_name, "matched_keywords": [k for k in model_keywords if k in message_lower]},
                        "sessionId": "analysis",
                        "runId": "analysis",
                        "hypothesisId": "B"
                    }) + "\n")
            except: pass
            # #endregion
            return {
                "intent": Intent.ANALOG_BY_MODEL,
                "data": {"model": model_name}
            }
    
    # Подбор по рабочей точке
    qh_data = extract_qh_from_text(message)
    if qh_data:
        return {
            "intent": Intent.SELECTION_BY_POINT,
            "data": qh_data
        }
    
    # Ключевые слова для подбора
    selection_keywords = [
        "подбери", "подобрать", "подбор", "нужен насос",
        "рабочая точка", "точка работы", "q=", "h=", "подача", "расход"
    ]
    if any(keyword in message_lower for keyword in selection_keywords):
        # Пробуем извлечь Q и H ещё раз
        qh_data = extract_qh_from_text(message)
        return {
            "intent": Intent.SELECTION_BY_POINT,
            "data": qh_data or {}
        }
    
    # Аналог по модели (если не определили выше)
    if model_name and not qh_data:
        return {
            "intent": Intent.ANALOG_BY_MODEL,
            "data": {"model": model_name}
        }
    
    # По умолчанию - не по теме
    return {
        "intent": Intent.OFF_TOPIC,
        "data": {}
    }

