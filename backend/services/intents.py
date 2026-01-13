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
            
            # ВАЛИДАЦИЯ: Используем централизованный валидатор
            from services.parsing_validator import validate_qh
            
            q_exact = q_result.get("q_m3h", q_value)  # Используем точное значение из q_result
            h_exact = h_value  # h_value уже точное из h_result
            
            # Валидируем Q и H
            is_valid, q_error, h_error = validate_qh(q_exact, h_exact, "m3/h", "m")
            
            if is_valid:
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
            
            # ВАЛИДАЦИЯ: Используем централизованный валидатор
            from services.parsing_validator import validate_qh
            
            q_exact = q_result.get("q_m3h", q_value)
            h_exact = h_value
            
            # Валидируем Q и H
            is_valid, q_error, h_error = validate_qh(q_exact, h_exact, "m3/h", "m")
            
            if is_valid:
                # ИСПРАВЛЕНО: Используем точные значения, НЕ округляем (округление только при отображении)
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
    
    # Паттерн 3.4: "q 10, h 20" или "q 10 h 20" без знака "=" (для запросов типа "нужен насос q 10, h 20")
    pattern3_4 = r"\bq\s+(\d+\.?\d*)\s*(?:м[³3]?/ч|м3/ч|куб[ов]?)?\s*[,]?\s*h\s+(\d+\.?\d*)\s*(?:м|метр[ов]?|m)?"
    match3_4 = re.search(pattern3_4, text_lower, re.IGNORECASE)
    if match3_4:
        # Используем улучшенные парсеры для пересчета единиц
        q_text = f"{match3_4.group(1)} м³/ч"  # Предполагаем м³/ч, если единица не указана
        h_text = f"{match3_4.group(2)} м"  # Предполагаем метры, если единица не указана
        
        q_result = extract_q_from_text(q_text)
        h_result = extract_h_from_text(h_text)
        
        if q_result and q_result.get("confidence", 0) > 0.3 and h_result and h_result.get("confidence", 0) > 0.3:
            q_value = q_result["q_m3h"]
            h_value = h_result["h_m"]
            
            # Валидируем Q и H
            from services.parsing_validator import validate_qh
            is_valid, q_error, h_error = validate_qh(q_value, h_value, "m3/h", "m")
            
            if is_valid:
                return {"q": q_value, "h": h_value}
    
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


def normalize_model_text(text: str) -> str:
    """
    Нормализует текст модели для парсинга.
    Обрабатывает различные варианты написания:
    - "cnp cdm 1 - 3" -> "cnp cdm 1-3"
    - "cnp cdm1-3" -> "cnp cdm 1-3"
    - "cnp cdm 1 3" -> "cnp cdm 1-3"
    - "cdm 1-3" -> "cdm 1-3"
    """
    # Убираем лишние пробелы и знаки препинания в конце
    text = text.strip().rstrip('!?.,;:')
    
    # Нормализуем пробелы вокруг дефисов: "1 - 3" -> "1-3", "1- 3" -> "1-3"
    text = re.sub(r'\s*-\s*', '-', text)

    # Нормализуем формат вида "2/2" в моделях: "2/2" -> "2-2"
    text = re.sub(r'(\d+)\s*/\s*(\d+)', r'\1-\2', text)
    
    # Нормализуем пробелы между буквами и цифрами: "cdm1-3" -> "cdm 1-3"
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text, flags=re.IGNORECASE)
    
    # Нормализуем пробелы между числами: "1 3" -> "1-3" (если это похоже на диапазон модели)
    # Но только если это не часть большого числа
    text = re.sub(r'(\d+)\s+(\d+)(?=\s|$)', r'\1-\2', text)
    
    return text.strip()


def _looks_like_pump_model(model: Optional[str]) -> bool:
    """
    Anti-false-positive: не считаем "ага/ок/ты идиот" моделью.

    Минимальные требования:
    - хотя бы одна цифра
    - хотя бы две латинские буквы (серия)
    """
    if model is None:
        return False
    s = str(model).strip().upper()
    if len(s) < 3:
        return False
    if not re.search(r"\d", s):
        return False
    if not re.search(r"[A-Z]{2,}", s):
        return False
    return True


def extract_brand_and_model(text: str) -> Dict[str, Optional[str]]:
    """
    Извлекает бренд и модель из текста.
    
    Обрабатывает случаи:
    - "cnp cdm 1-3" -> brand="CNP", model="CDM 1-3"
    - "cdm 1-3" -> brand=None, model="CDM 1-3"
    - "grundfos cr 10-10" -> brand="GRUNDFOS", model="CR 10-10"
    
    Returns:
        {"brand": str|None, "model": str|None}
    """
    text_normalized = normalize_model_text(text)
    text_upper = text_normalized.upper()
    text_lower = text_normalized.lower()
    
    # Известные бренды
    known_brands = ["CNP", "GRUNDFOS", "WILO", "PEDROLLO", "EBARA", "KSB", "FLYGT"]
    
    # Ищем бренд в начале текста
    brand = None
    model = None
    
    for known_brand in known_brands:
        if text_upper.startswith(known_brand):
            brand = known_brand
            # Убираем бренд из текста
            model_text = text_normalized[len(known_brand):].strip()
            break
    
    # Если бренд не найден, пробуем найти его в тексте
    if not brand:
        for known_brand in known_brands:
            if known_brand in text_upper:
                # Проверяем, что бренд стоит в начале или после ключевых слов
                brand_pos = text_upper.find(known_brand)
                if brand_pos <= 20:  # Бренд в начале текста
                    brand = known_brand
                    # Извлекаем модель после бренда
                    model_text = text_normalized[brand_pos + len(known_brand):].strip()
                    break
    
    # Если бренд найден, извлекаем модель
    if brand:
        # Убираем ключевые слова из начала модели
        model_text = re.sub(r'^(МОДЕЛ[ИЬ]?|АНАЛОГ|НАСОС[А]?)\s+', '', model_text, flags=re.IGNORECASE)
        candidate = model_text.strip() if model_text.strip() else None
        model = candidate if _looks_like_pump_model(candidate) else None
    else:
        # Бренд не найден - ищем модель без бренда
        # Убираем ключевые слова
        model_text = re.sub(r'^(модел[иь]?|аналог|насос[а]?)\s+', '', text_lower, flags=re.IGNORECASE)
        model_text = model_text.strip()
        
        # Пробуем найти паттерн модели: буквы + цифры + дефис + цифры
        # Например: "cdm 1-3", "cdmf 2-2", "cdm 2/2" (после normalize_model_text станет "2-2")
        model_pattern = r'([a-z]{2,8})\s*(\d+)\s*-\s*(\d+)'
        match = re.search(model_pattern, model_text, re.IGNORECASE)
        if match:
            model = f"{match.group(1).upper()} {match.group(2)}-{match.group(3)}"
        else:
            # Пробуем найти просто буквы + цифры
            model_pattern2 = r'([a-z]{2,8})\s*(\d+)'
            match2 = re.search(model_pattern2, model_text, re.IGNORECASE)
            if match2:
                model = f"{match2.group(1).upper()} {match2.group(2)}"
            else:
                # ВАЖНО: не используем "fallback = весь текст", чтобы не ловить "АГА/Ы/..." как модель
                model = None
    
    return {"brand": brand, "model": model}


def detect_model_name(text: str) -> Optional[str]:
    """
    Определяет, есть ли в тексте название модели насоса.
    
    Ищет паттерны типа:
    - CNP CDMF 1-3
    - CNP CDM 5-6
    - CDM 1-3 (без бренда)
    - Grundfos CR
    - модель ...
    - аналог насоса CNP CDMF 2-2
    
    Returns:
        название модели (с брендом или без) или None
    """
    text_normalized = normalize_model_text(text)
    text_upper = text_normalized.upper()
    text_lower = text_normalized.lower()
    
    # Сначала проверяем ключевые слова для моделей
    model_keywords = ["модел", "аналог", "насос", "cnp", "grundfos", "wilo", "pedrollo"]
    has_model_keyword = any(keyword in text_lower for keyword in model_keywords)
    
    # Используем новую функцию извлечения бренда и модели
    brand_model = extract_brand_and_model(text)
    brand = brand_model.get("brand")
    model = brand_model.get("model")
    
    if model and _looks_like_pump_model(model):
        # Если есть бренд, возвращаем "BRAND MODEL", иначе просто "MODEL"
        if brand:
            return f"{brand} {model}"
        else:
            return model
    
    # Fallback: старые паттерны (для обратной совместимости)
    # СНАЧАЛА проверяем короткие модели типа "cdm 2-2" (без бренда)
    short_model_pattern = r"\b([a-z]{2,8})\s*(\d+)\s*-\s*(\d+)\b"
    match_short = re.search(short_model_pattern, text_lower)
    if match_short:
        model = f"{match_short.group(1).upper()} {match_short.group(2)}-{match_short.group(3)}"
        return model if _looks_like_pump_model(model) else None
    
    # Паттерны моделей с брендом
    model_patterns = [
        r"(CNP)\s+([A-Z0-9]+)\s+(\d+)\s*-\s*(\d+)",  # CNP CDMF 1-3
        r"(CNP)\s+([A-Z0-9]+)\s+(\d+)",  # CNP CDM 5
        r"(CNP)\s+([A-Z0-9]+)",  # CNP CDMF
        r"(GRUNDFOS)\s+([A-Z0-9\s\-]+)",
        r"(WILO)\s+([A-Z0-9\s\-]+)",
        r"(PEDROLLO)\s+([A-Z0-9\s\-]+)",
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, text_upper)
        if match:
            if match.lastindex >= 2:
                brand_part = match.group(1)
                model_part = match.group(2)
                if match.lastindex >= 3:
                    model_part += f" {match.group(3)}"
                if match.lastindex >= 4:
                    model_part += f"-{match.group(4)}"
                return f"{brand_part} {model_part.strip()}"
            else:
                model = match.group(0).strip()
                model = re.sub(r"^(МОДЕЛ[ИЬ]?|АНАЛОГ|НАСОС[А]?)\s+", "", model, flags=re.IGNORECASE)
                if len(model) >= 3:
                    return model
    
    # Если есть ключевые слова, но паттерн не сработал
    if has_model_keyword:
        general_pattern = r"([A-Z]{2,}\s+[A-Z0-9]+(?:\s*-\s*[0-9]+)?)"
        match = re.search(general_pattern, text_upper)
        if match:
            model = match.group(1).strip()
            if len(model) >= 3:
                return model
    
    return None


def detect_intent(
    message: str,
    has_attachments: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Определяет интент сообщения с учетом контекста истории диалога.
    
    Args:
        message: текст сообщения
        has_attachments: есть ли вложения
        context: контекст диалога (state, recent_messages, dialog_summary)
        
    Returns:
        {
            "intent": str,
            "data": dict  # дополнительные данные (Q, H, модель и т.д.)
        }
    """
    if context is None:
        context = {}
    
    message_lower = message.lower().strip()
    
    # Получаем контекст из истории для улучшения понимания
    recent_messages = context.get("recent_messages", [])
    dialog_summary = context.get("dialog_summary", "")
    state = context.get("state", {})
    
    # Формируем расширенный контекст для анализа
    # Объединяем последние сообщения пользователя для понимания контекста
    context_text = ""
    if recent_messages:
        user_messages = [msg.get("content", "") for msg in recent_messages[-5:] if msg.get("role") == "user"]
        if user_messages:
            context_text = " ".join(user_messages)
    
    # Объединяем текущее сообщение с контекстом для анализа
    full_context = f"{context_text} {message}".strip() if context_text else message
    full_context_lower = full_context.lower()
    
    # Если есть вложения
    if has_attachments:
        return {
            "intent": Intent.FILE_UPLOAD,
            "data": {}
        }
    
    # Используем расширенный контекст для поиска паттернов
    # Это позволяет понимать контекстные вопросы типа "а что насчет этого насоса?"
    search_text = full_context_lower if full_context_lower else message_lower
    
    # Диагностика (проверяем в контексте, может быть вопрос о ранее выбранном насосе)
    diagnostics_keywords = [
        "шумит", "шум", "кавитация", "вибрация", "вибрирует",
        "не работает", "не качает", "перегревается", "греется"
    ]
    if any(keyword in search_text for keyword in diagnostics_keywords):
        # Если в состоянии есть информация о выбранном насосе, добавляем её в data
        selected_pump_data = {}
        if state.get("last_selected_pump"):
            selected_pump_data["last_selected_pump"] = state.get("last_selected_pump")
        return {
            "intent": Intent.DIAGNOSTICS,
            "data": selected_pump_data
        }
    
    # Запрос на сравнение двух насосов (например, "Сравнить насосы 14101003 и 14101004")
    compare_pattern = re.search(r"сравн[иь]?\s+(?:насос[ы]?|артикул[ы]?)\s+(\d{6,12})\s+(?:и|с)\s+(\d{6,12})", search_text)
    if compare_pattern:
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {
                "action": "compare",
                "articul1": compare_pattern.group(1),
                "articul2": compare_pattern.group(2)
            }
        }
    
    # Запрос на построение графика (может быть о ранее выбранном насосе)
    plot_keywords = ["построй", "построить", "график", "кривая", "покажи график", "нарисуй"]
    if any(keyword in search_text for keyword in plot_keywords):
        # Проверяем, есть ли в контексте информация о выбранном насосе
        plot_data = {}
        if state.get("last_selected_pump"):
            plot_data["last_selected_pump"] = state.get("last_selected_pump")
        return {
            "intent": Intent.DOCUMENTATION,  # Используем DOCUMENTATION для графиков
            "data": {"action": "plot"}
        }
    
    # Документация (может быть вопрос о ранее выбранном насосе)
    doc_keywords = [
        "паспорт", "характеристика", "лист данных",
        "datasheet", "manual", "инструкция", "руководство"
    ]
    if any(keyword in search_text for keyword in doc_keywords):
        # Проверяем, есть ли модель Кометта в запросе (К/K + 3 цифры)
        # Примеры: "К144 65-80/04А/055Т2", "K377 32-50", "к233-160"
        kometta_model_pattern = r"\b[кk]\s*\d{3}[\w\s\-\/\.]*"
        match = re.search(kometta_model_pattern, message, re.IGNORECASE)
        if match:
            model_text = match.group(0).strip()
            return {
                "intent": Intent.DOCUMENTATION,
                "data": {"model": model_text, "action": "by_model"}
            }
        
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
    # Используем расширенный контекст для поиска
    analog_with_articul = re.search(r"аналог[и]?\s+(?:насос[а]?\s+)?(?:кометта\s+)?(\d{6,12})", search_text)
    if analog_with_articul:
        articul = analog_with_articul.group(1)
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {"articul": articul, "action": "analog_by_articul"}
        }

    # Материал корпуса насоса по модели/артикулу (Кометта)
    # Примеры: "из чего сделан насос К144 32-50/16Е/040Т2", "материал корпуса 13101252"
    # Используем расширенный контекст
    if any(k in search_text for k in ["из чего сделан", "материал корпуса", "корпус насоса", "из какого материала"]):
        # По артикулу
        articul_any = re.search(r"\b\d{6,12}\b", message)
        if articul_any:
            return {
                "intent": Intent.DOCUMENTATION,
                "data": {"action": "body_material_by_articul", "articul": articul_any.group(0)}
            }

        # По модели (ищем "К144 .../16Е/..." и т.п.)
        model_match = re.search(r"\b[КK]\s*\d{3}[^\n]{0,80}", message, re.IGNORECASE)
        if model_match:
            model_text = model_match.group(0).strip()
            return {
                "intent": Intent.DOCUMENTATION,
                "data": {"action": "body_material_by_model", "model": model_text}
            }
    
    # Проверяем запросы на аналоги по бренду (например, "аналоги Grundfos")
    # Используем расширенный контекст
    analog_by_brand = re.search(r"аналог[и]?\s+(?:насос[а]?|для)\s+(grundfos|cnp|wilo|pedrollo)", search_text)
    if analog_by_brand:
        brand = analog_by_brand.group(1).upper()
        return {
            "intent": Intent.ANALOG_BY_MODEL,
            "data": {"brand": brand, "action": "by_brand"}
        }
    
    # Проверяем, есть ли артикул в тексте (например, "Артикул насоса 11101048")
    # Используем расширенный контекст
    articul_in_text = re.search(r"(?:артикул|articul)[\s\w]*?(\d{6,12})", search_text)
    if articul_in_text:
        articul = articul_in_text.group(1)
        return {
            "intent": Intent.DOCUMENTATION,
            "data": {"articul": articul, "action": "by_articul"}
        }
    
    # СНАЧАЛА проверяем модель конкурента (чтобы не парсить CNP CDM 5-6 как Q=5, H=6)
    model_name = detect_model_name(message)
    brand_model = extract_brand_and_model(message) if model_name else None
    
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
                "message": "Model name detection",
                "data": {
                    "detected_model": model_name,
                    "brand": brand_model.get("brand") if brand_model else None,
                    "model": brand_model.get("model") if brand_model else None,
                    "message": message
                },
                "sessionId": "analysis",
                "runId": "analysis",
                "hypothesisId": "B"
            }) + "\n")
    except: pass
    # #endregion
    
    # Проверяем контекстные вопросы о ранее выбранном насосе
    # Например: "а что насчет этого насоса?", "расскажи про него", "какие у него характеристики"
    context_question_keywords = [
        "этот насос", "этот", "его", "него", "насос", "про него", "про этот",
        "характеристики", "параметры", "мощность", "артикул"
    ]
    if (any(keyword in message_lower for keyword in context_question_keywords) and 
        state.get("last_selected_pump")):
        # Если есть выбранный насос в состоянии, возвращаем его информацию
        last_pump = state.get("last_selected_pump")
        if isinstance(last_pump, dict) and last_pump.get("articul"):
            return {
                "intent": Intent.DOCUMENTATION,
                "data": {
                    "articul": last_pump.get("articul"),
                    "action": "by_articul",
                    "from_context": True
                }
            }
    
    if model_name:
        # Проверяем, что это действительно модель, а не числа
        # Если в тексте есть ключевые слова для моделей
        model_keywords = ["модел", "аналог", "cnp", "grundfos", "wilo", "pedrollo", "конкурент"]
        if any(keyword in search_text for keyword in model_keywords):
            # #region agent log
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "location": "intents.py:detect_intent",
                        "message": "Intent set to ANALOG_BY_MODEL",
                        "data": {
                            "model": model_name,
                            "brand": brand_model.get("brand") if brand_model else None,
                            "model_only": brand_model.get("model") if brand_model else None,
                            "matched_keywords": [k for k in model_keywords if k in message_lower]
                        },
                        "sessionId": "analysis",
                        "runId": "analysis",
                        "hypothesisId": "B"
                    }) + "\n")
            except: pass
            # #endregion
            return {
                "intent": Intent.ANALOG_BY_MODEL,
                "data": {
                    "model": model_name,
                    "brand": brand_model.get("brand") if brand_model else None,
                    "model_only": brand_model.get("model") if brand_model else None
                }
            }
    
    # Подбор по рабочей точке
    # Используем расширенный контекст для поиска Q и H (может быть в предыдущих сообщениях)
    qh_data = extract_qh_from_text(full_context) if full_context else extract_qh_from_text(message)
    if qh_data:
        # ВАЖНО: если пользователь одновременно указал тип насоса (вертикальный многоступенчатый и т.п.),
        # добавляем это в data, чтобы подбор мог сразу фильтровать по серии.
        try:
            from services.pump_types import detect_pump_type
            pump_type_info = detect_pump_type(message)
        except Exception:
            pump_type_info = None

        data = dict(qh_data)
        if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
            # ВАЖНО: Конвертируем Enum в строку для сериализации
            pump_type_info_serializable = pump_type_info.copy()
            if "availability" in pump_type_info_serializable:
                from services.pump_types import PumpTypeAvailability
                availability = pump_type_info_serializable["availability"]
                if isinstance(availability, PumpTypeAvailability):
                    pump_type_info_serializable["availability"] = availability.value
            data["pump_type_info"] = pump_type_info_serializable

        return {
            "intent": Intent.SELECTION_BY_POINT,
            "data": data
        }
    
    # Ключевые слова для подбора
    # Используем расширенный контекст
    selection_keywords = [
        "подбери", "подобрать", "подбор", "нужен насос",
        "рабочая точка", "точка работы", "q=", "h=", "подача", "расход"
    ]
    if any(keyword in search_text for keyword in selection_keywords):
        # Пробуем извлечь Q и H ещё раз
        qh_data = extract_qh_from_text(message)
        try:
            from services.pump_types import detect_pump_type
            pump_type_info = detect_pump_type(message)
        except Exception:
            pump_type_info = None

        data = dict(qh_data or {})
        if pump_type_info and pump_type_info.get("confidence", 0) > 0.5:
            # ВАЖНО: Конвертируем Enum в строку для сериализации
            pump_type_info_serializable = pump_type_info.copy()
            if "availability" in pump_type_info_serializable:
                from services.pump_types import PumpTypeAvailability
                availability = pump_type_info_serializable["availability"]
                if isinstance(availability, PumpTypeAvailability):
                    pump_type_info_serializable["availability"] = availability.value
            data["pump_type_info"] = pump_type_info_serializable
        return {
            "intent": Intent.SELECTION_BY_POINT,
            "data": data
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
    # Детектируем общие вопросы о типах насосов и компонентах как TECH_QA
    message_lower = message.lower()
    if any(phrase in message_lower for phrase in [
        "какие типы насосов", "какие типы есть", "типы насосов в ассортименте",
        "какие насосы есть", "какие насосы в линейке", "ассортимент насосов",
        "из чего состоит насос", "компоненты насоса", "части насоса",
        "состав насоса", "устройство насоса", "конструкция насоса"
    ]):
        return {
            "intent": Intent.TECH_QA,
            "data": {"query": message}
        }
    
    # Детектируем как TECH_QA если:
    # - содержит вопросительные слова
    # - запрос длиннее 10 символов
    # - не является конкретным техническим запросом (Q/H, модель, артикул)
    # ВАЖНО: Проверяем только если ещё не определили более специфичные интенты
    # Используем улучшенную функцию определения вопросов
    from services.question_detection import is_question as detect_question
    is_question, question_reason = detect_question(message)
    
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
        
        # ВАЖНО: Конвертируем Enum в строку перед возвратом для избежания проблем с сериализацией
        # Это необходимо, так как pump_type_info содержит PumpTypeAvailability (Enum), который не сериализуется в JSON
        if pump_type_info and isinstance(pump_type_info, dict):
            pump_type_info_serializable = pump_type_info.copy()
            # Конвертируем Enum availability в строку
            if "availability" in pump_type_info_serializable:
                from services.pump_types import PumpTypeAvailability
                availability = pump_type_info_serializable["availability"]
                if isinstance(availability, PumpTypeAvailability):
                    pump_type_info_serializable["availability"] = availability.value
            # Убеждаемся, что все остальные поля тоже сериализуемы
            # series уже должен быть списком строк
        else:
            pump_type_info_serializable = pump_type_info
        
        return {
            "intent": Intent.PUMP_TYPE,
            "data": {"pump_type_info": pump_type_info_serializable}
        }
    
    # По умолчанию - не по теме
    return {
        "intent": Intent.OFF_TOPIC,
        "data": {}
    }

