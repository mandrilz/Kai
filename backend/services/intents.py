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
    PUMP_TYPE = "pump_type"  # Запрос по типу насоса (циркуляционный, погружной и т.д.)
    MATERIALS_QUERY = "materials_query"  # Запрос о материалах исполнения для жидкости
    TECH_QA = "tech_qa"  # Технический вопрос для поиска в базе знаний
    OFF_TOPIC = "off_topic"  # Не по теме


def extract_qh_from_text(text: str) -> Optional[Dict[str, float]]:
    """
    Извлекает Q и H из текста.
    
    ВАЖНО: 
    - Все единицы расхода автоматически пересчитываются в м³/ч!
    - Все единицы напора автоматически пересчитываются в метры!
    Это необходимо, так как база данных насосов использует м³/ч для расхода и метры для напора.
    
    ИСПРАВЛЕНО: Использует улучшенные парсеры из q_extractor.py и h_extractor.py
    для поддержки различных единиц измерения и вариантов записи.
    
    Ищет паттерны типа:
    - Q=10, H=20
    - расход 10 м³/ч, напор 20 м
    - 10 м³/ч, 20 м
    - подача 10 м³/ч и напор 30 м
    - 180 л/мин, 20 м (Q автоматически пересчитается в м³/ч)
    - 50 кубов/ч, давление 3 бар (H автоматически пересчитается в метры: 3*10.197=30.59 м)
    - 12,5 л/с, 250 кПа (Q и H автоматически пересчитаются)
    - Q=30 м³/ч, напор 0.4 МПа (H автоматически пересчитается в метры: 0.4*101.97=40.79 м)
    
    Returns:
        {"q": float, "h": float} где:
        - q ВСЕГДА в м³/ч (пересчитано из любой единицы)
        - h ВСЕГДА в метрах (пересчитано из любой единицы: бар, кПа, МПа, атм и т.д.)
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
    
    # ИСПРАВЛЕНО: Используем улучшенные парсеры расхода и напора
    from services.q_extractor import extract_q_from_text
    from services.h_extractor import extract_h_from_text
    
    # Сначала пробуем извлечь Q через улучшенный парсер
    # ВАЖНО: extract_q_from_text всегда возвращает q_m3h в м³/ч (после пересчета)
    q_result = extract_q_from_text(text)
    if q_result and q_result.get("confidence", 0) > 0.5:
        # q_m3h уже пересчитан в м³/ч из любой единицы (л/с, л/мин, м3/сут и т.д.)
        q_value = q_result["q_m3h"]
        
        # Логируем пересчет для отладки
        if q_result.get("q_unit") != "m3/h":
            import json
            import os
            from datetime import datetime
            log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "intents.py:extract_qh_from_text",
                        "message": "Q unit conversion",
                        "data": {
                            "q_raw": q_result.get("q_raw"),
                            "q_unit": q_result.get("q_unit"),
                            "q_m3h": q_value,
                            "conversion_applied": True
                        },
                        "sessionId": "analysis",
                        "runId": "analysis",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
        
        # Теперь ищем H рядом с найденным Q используя улучшенный парсер
        # ИСПРАВЛЕНО: Используем улучшенный парсер напора для пересчета единиц
        # (импорт уже выполнен выше)
        
        # Сначала ищем H в контексте рядом с Q
        # ИСПРАВЛЕНО: Используем нормализованный текст для поиска Q
        q_raw_normalized = q_result["q_raw"].replace(" ", "")  # Убираем пробелы для поиска
        text_normalized_for_search = text.replace(" ", "")  # Убираем пробелы из текста для поиска
        q_pos_normalized = text_normalized_for_search.lower().find(q_raw_normalized.lower())
        
        # Если не нашли в нормализованном тексте, пробуем найти в оригинальном
        if q_pos_normalized == -1:
            q_pos = text.lower().find(q_result["q_raw"].lower())
        else:
            # Нашли в нормализованном - переводим позицию обратно в оригинальный текст
            # Приблизительно: ищем позицию в оригинальном тексте
            q_pos = text.lower().find(q_result["q_raw"].lower())
            if q_pos == -1:
                # Если все еще не нашли, используем позицию из нормализованного текста как приблизительную
                # Считаем количество пробелов до позиции в нормализованном тексте
                spaces_before = text_normalized_for_search[:q_pos_normalized].count(" ")
                q_pos = q_pos_normalized + spaces_before
        
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
                    "location": "intents.py:extract_qh_from_text",
                    "message": "Searching H near Q",
                    "data": {
                        "q_raw": q_result["q_raw"],
                        "q_pos": q_pos,
                        "text_length": len(text),
                        "h_context_preview": text[max(0, q_pos - 50):min(len(text), q_pos + 150)][:100] if q_pos >= 0 else "Q not found"
                    },
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        
        if q_pos >= 0:
            search_start = max(0, q_pos - 50)
            search_end = min(len(text), q_pos + 150)
            h_context = text[search_start:search_end]
        else:
            # Если Q не найден, ищем H во всем тексте
            h_context = text
        
        h_result = extract_h_from_text(h_context)
        
        # #region agent log
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "intents.py:extract_qh_from_text",
                    "message": "H extraction result",
                    "data": {
                        "h_result": h_result,
                        "h_context": h_context[:200] if h_context else None,
                        "confidence": h_result.get("confidence", 0) if h_result else 0
                    },
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }) + "\n")
        except: pass
        # #endregion
        
        if h_result and h_result.get("confidence", 0) > 0.5:
            # h_m уже пересчитан в метры из любой единицы (бар, кПа, МПа и т.д.)
            h_value = h_result["h_m"]
            
            # Логируем пересчет для отладки
            if h_result.get("h_unit") != "m":
                import json
                import os
                from datetime import datetime
                log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
                try:
                    os.makedirs(os.path.dirname(log_path), exist_ok=True)
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "location": "intents.py:extract_qh_from_text",
                            "message": "H unit conversion",
                            "data": {
                                "h_raw": h_result.get("h_raw"),
                                "h_unit": h_result.get("h_unit"),
                                "h_m": h_value,
                                "conversion_applied": True
                            },
                            "sessionId": "analysis",
                            "runId": "analysis",
                            "hypothesisId": "A"
                        }) + "\n")
                except: pass
            
            if 0.1 < h_value < 500:  # Валидация H
                # ИСПРАВЛЕНО: Используем точные значения из q_result и h_result, НЕ округляем
                # q_result содержит точное значение q_m3h (например, 144.306)
                # h_value уже точное из h_result (например, 45.87)
                q_exact = q_result.get("q_m3h", q_value)  # Используем точное значение из q_result
                h_exact = h_value  # h_value уже точное из h_result
                # Возвращаем точные значения (округление будет только при отображении)
                result = {"q": q_exact, "h": h_exact}
                # #region agent log
                import json
                import os
                from datetime import datetime
                log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "location": "intents.py:extract_qh_from_text",
                            "message": "Q and H extracted (improved parser)",
                            "data": {"extracted": result, "q_result": q_result},
                            "sessionId": "analysis",
                            "runId": "analysis",
                            "hypothesisId": "A"
                        }) + "\n")
                except: pass
                # #endregion
                return result
    
    # Если новый парсер нашел Q, но не нашел H - ищем H во всем тексте
    if q_result and q_result.get("confidence", 0) > 0.5:
        q_value = q_result["q_m3h"]
        # ИСПРАВЛЕНО: Используем улучшенный парсер напора для всего текста
        # (импорт уже выполнен выше)
        
        h_result = extract_h_from_text(text)
        if h_result and h_result.get("confidence", 0) > 0.5:
            h_value = h_result["h_m"]
            
            # Логируем пересчет для отладки
            if h_result.get("h_unit") != "m":
                import json
                import os
                from datetime import datetime
                log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
                try:
                    os.makedirs(os.path.dirname(log_path), exist_ok=True)
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "location": "intents.py:extract_qh_from_text",
                            "message": "H unit conversion (full text)",
                            "data": {
                                "h_raw": h_result.get("h_raw"),
                                "h_unit": h_result.get("h_unit"),
                                "h_m": h_value,
                                "conversion_applied": True
                            },
                            "sessionId": "analysis",
                            "runId": "analysis",
                            "hypothesisId": "A"
                        }) + "\n")
                except: pass
            
            if 0.1 < h_value < 500:  # Валидация H
                # Округляем до 2 знаков после запятой
                q_value = round(q_value, 2)
                h_value = round(h_value, 2)
                result = {"q": q_value, "h": h_value}
                # #region agent log
                import json
                import os
                from datetime import datetime
                log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "location": "intents.py:extract_qh_from_text",
                            "message": "Q and H extracted (Q and H from improved parsers)",
                            "data": {"extracted": result, "q_result": q_result, "h_result": h_result},
                            "sessionId": "analysis",
                            "runId": "analysis",
                            "hypothesisId": "A"
                        }) + "\n")
                except: pass
                # #endregion
                return result
    
    # Если новый парсер не нашел Q или H, используем старые паттерны как fallback
    text_lower = text.lower()
    
    # Паттерн 2: расход/подача ... напор ... (улучшенный)
    # ВАЖНО: Всегда пытаемся использовать улучшенный парсер для пересчета единиц
    pattern2 = r"(?:расход[а]?|подач[аи]?)\s*(\d+\.?\d*)\s*(?:м[³3]/ч|м3/ч|л/с|л/мин|л/ч|м3/сут)?\s*(?:и|с|,)\s*напор[а]?\s*(\d+\.?\d*)\s*м"
    match2 = re.search(pattern2, text_lower)
    if match2:
        h_value = float(match2.group(2).replace(',', '.'))
        
        # ВАЖНО: Всегда используем улучшенный парсер для пересчета Q в м³/ч
        # Это гарантирует правильный пересчет из любой единицы
        q_result_fallback = extract_q_from_text(text)
        if q_result_fallback and q_result_fallback.get("confidence", 0) > 0.3:
            # Используем пересчитанное значение в м³/ч
            q_value = q_result_fallback["q_m3h"]
        else:
            # Fallback: если парсер не нашел, берем сырое значение
            # Предполагаем, что оно уже в м³/ч (может быть неточно, но лучше чем ничего)
            q_raw = float(match2.group(1).replace(',', '.'))
            q_value = q_raw
            
            # Логируем предупреждение
            import json
            import os
            from datetime import datetime
            log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "intents.py:extract_qh_from_text:pattern2",
                        "message": "WARNING: Using raw Q value without unit conversion",
                        "data": {"q_raw": q_raw, "text": text[:100]},
                        "sessionId": "analysis",
                        "runId": "analysis",
                        "hypothesisId": "WARNING"
                    }) + "\n")
            except: pass
        
        # Округляем до 2 знаков после запятой
        q_value = round(q_value, 2)
        h_value = round(h_value, 2)
        return {"q": q_value, "h": h_value}
    
    # Паттерн 3: числа с единицами измерения (улучшенный)
    # ВАЖНО: Этот паттерн ищет только м³/ч, поэтому пересчет не нужен
    pattern3 = r"(\d+\.?\d*)\s*м[³3]/ч\s*(?:и|с|,)\s*(\d+\.?\d*)\s*м"
    match3 = re.search(pattern3, text_lower)
    if match3:
        # Уже в м³/ч, пересчет не требуется
        q_value = round(float(match3.group(1).replace(',', '.')), 2)
        h_value = round(float(match3.group(2).replace(',', '.')), 2)
        result = {"q": q_value, "h": h_value}
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
    # ВАЖНО: "кубов" означает м³/ч, H может быть в разных единицах
    pattern3_5 = r"(\d+\.?\d*)\s*куб[ов]?\s+на\s+(\d+\.?\d*)\s*(?:метр[ов]?|м\b|bar|бар|kpa|кпа|mpa|мпа|atm|атм)?"
    match3_5 = re.search(pattern3_5, text_lower)
    if match3_5:
        q_value = float(match3_5.group(1).replace(',', '.'))  # Уже в м³/ч
        
        # Используем улучшенный парсер для H
        h_text = match3_5.group(0)
        h_result = extract_h_from_text(h_text)
        if h_result and h_result.get("confidence", 0) > 0.3:
            h_value = h_result["h_m"]  # Уже в метрах
        else:
            # Fallback: предполагаем метры
            h_value = float(match3_5.group(2).replace(',', '.'))
        
        # Округляем до 2 знаков после запятой
        q_value = round(q_value, 2)
        h_value = round(h_value, 2)
        result = {"q": q_value, "h": h_value}
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
    # ВАЖНО: Q уже в м³/ч, но H может быть в разных единицах
    pattern4 = r"(?:подач[аи]|расход)\s+(\d+\.?\d*)\s*м[³3]/ч\s+(?:и\s+)?напор\s+(\d+\.?\d*)\s*(?:м|m|метр[ов]?|bar|бар|kpa|кпа|mpa|мпа|atm|атм)?"
    match4 = re.search(pattern4, text_lower)
    if match4:
        q_value = float(match4.group(1).replace(',', '.'))  # Уже в м³/ч
        
        # Используем улучшенный парсер для H
        h_text = match4.group(0)
        h_result = extract_h_from_text(h_text)
        if h_result and h_result.get("confidence", 0) > 0.3:
            h_value = h_result["h_m"]  # Уже в метрах
        else:
            # Fallback: предполагаем метры
            h_value = float(match4.group(2).replace(',', '.'))
        
        # Округляем до 2 знаков после запятой
        q_value = round(q_value, 2)
        h_value = round(h_value, 2)
        result = {"q": q_value, "h": h_value}
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
        pattern5_qh = r"(\d+\.?\d*)\s*(?:м[³3]/ч|м3/ч)\s*[,\s]+(?:и\s+)?(\d+\.?\d*)\s*(?:м|m|метр[ов]?|bar|бар|kpa|кпа|mpa|мпа|atm|атм)?"
        match5_qh = re.search(pattern5_qh, text_lower)
        if match5_qh:
            q_value = float(match5_qh.group(1).replace(',', '.'))  # Уже в м³/ч
            
            # Используем улучшенный парсер для H
            h_text = match5_qh.group(0)
            h_result = extract_h_from_text(h_text)
            if h_result and h_result.get("confidence", 0) > 0.3:
                h_value = h_result["h_m"]  # Уже в метрах
            else:
                # Fallback: предполагаем метры
                h_value = float(match5_qh.group(2).replace(',', '.'))
            
            # Округляем до 2 знаков после запятой
            q_value = round(q_value, 2)
            h_value = round(h_value, 2)
            result = {"q": q_value, "h": h_value}
            return result
        
        # Если не нашли специфичный паттерн, пробуем общий поиск чисел
        # ВАЖНО: Без явных единиц предполагаем м³/ч, но это может быть неточно
        numbers = re.findall(r"\d+\.?\d*", text)
        if len(numbers) >= 2:
            # Пробуем интерпретировать как Q и H
            try:
                q = float(numbers[0].replace(',', '.'))
                h = float(numbers[1].replace(',', '.'))
                # Более строгие проверки: Q обычно меньше 1000, H может быть до 500
                # НО: если H слишком маленький (< 5), возможно это ошибка парсинга
                # ВАЖНО: Предполагаем, что Q уже в м³/ч (без единиц)
                if 0.1 < q < 1000 and 0.1 < h < 500 and h >= 5:  # Минимальный H = 5м
                    # Округляем до 2 знаков после запятой
                    q = round(q, 2)
                    h = round(h, 2)
                    result = {"q": q, "h": h}  # Предполагаем м³/ч
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
    
    # Проверяем запрос о материалах исполнения / жидкости
    # Ключевые слова: материал, исполнение, жидкость, среда, для воды, для масла и т.д.
    materials_keywords = [
        "материал", "исполнение", "жидкость", "среда", "для воды", "для масла",
        "для масла", "для топлива", "для гликоля", "для раствора", "для антифриза",
        "какое исполнение", "какой материал", "подходит материал", "материал a",
        "материал e", "материал x", "материал h", "исполнение a", "исполнение e",
        "исполнение x", "исполнение h", "epdm", "fpm", "силикон", "graphite",
        "sic", "уплотнение", "эластомер"
    ]
    if any(keyword in message_lower for keyword in materials_keywords):
        # Извлекаем информацию о жидкости
        from services.materials import extract_liquid_info
        liquid_info = extract_liquid_info(message)
        return {
            "intent": Intent.MATERIALS_QUERY,
            "data": liquid_info
        }
    
    # Проверяем технический вопрос для поиска в базе знаний
    # Детектируем как TECH_QA если:
    # - содержит вопросительные слова
    # - запрос длиннее 10 символов
    # - не является конкретным техническим запросом (Q/H, модель, артикул)
    # ВАЖНО: Проверяем только если ещё не определили более специфичные интенты
    question_keywords = ["как", "что", "почему", "зачем", "где", "когда", "кто", "чем", "какой", "какая", "какое", "какие"]
    is_question = any(keyword in message_lower for keyword in question_keywords) or "?" in message
    
    # Проверяем, что это не конкретный технический запрос
    # (Q/H уже проверили выше, модель тоже, артикул тоже)
    if is_question and len(message.strip()) > 10:
        # Дополнительная проверка: не содержит ли запрос конкретных технических параметров
        has_technical_params = (
            "q=" in message_lower or "h=" in message_lower or
            "м3/ч" in message_lower or "м³/ч" in message_lower or
            re.search(r'\d{6,12}', message) is not None  # артикул
        )
        
        if not has_technical_params:
            # Это потенциально технический вопрос для базы знаний
            return {
                "intent": Intent.TECH_QA,
                "data": {"query": message}
            }
    
    # Проверяем запрос по типу насоса (циркуляционный, погружной, моноблочный и т.д.)
    # Это важно делать после Q/H и модели, чтобы не перехватывать более специфичные запросы
    from services.pump_types import detect_pump_type
    pump_type_info = detect_pump_type(message)
    if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
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
                    "location": "intents.py:detect_intent",
                    "message": "Intent set to PUMP_TYPE",
                    "data": {
                        "type_key": pump_type_info["type_key"],
                        "type_name": pump_type_info["type_name"],
                        "availability": pump_type_info["availability"].value,
                        "confidence": pump_type_info["confidence"],
                    },
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }, ensure_ascii=False) + "\n")
        except: pass
        # #endregion
        return {
            "intent": Intent.PUMP_TYPE,
            "data": {"pump_type_info": pump_type_info}
        }
    
    # По умолчанию - не по теме
    return {
        "intent": Intent.OFF_TOPIC,
        "data": {}
    }

