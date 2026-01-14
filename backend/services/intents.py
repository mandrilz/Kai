"""
Определение интентов пользовательских сообщений.

PR3: Теперь является тонким фасадом над модульным роутером intent_router.
Вся логика определения интентов вынесена в модульные правила в nlu/intent_rules/.
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
    
    PR1: Использует preprocess.normalize_text() для предобработки текста.
    
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
    # PR1: Нормализуем текст перед обработкой
    from services.nlu.preprocess import normalize_text
    text = normalize_text(text)
    text_lower = text.lower()  # Для использования в паттернах
    
    # Логирование удалено - избыточно для успешных операций
    
    # ИСПРАВЛЕНО: Используем улучшенные парсеры расхода и напора
    from services.q_extractor import extract_q_from_text
    from services.h_extractor import extract_h_from_text
    
    # Сначала пробуем извлечь Q через улучшенный парсер
    # ВАЖНО: extract_q_from_text всегда возвращает q_m3h в м³/ч (после пересчета)
    q_result = extract_q_from_text(text)
    if q_result and q_result.get("confidence", 0) > 0.5:
        # q_m3h уже пересчитан в м³/ч из любой единицы (л/с, л/мин, м3/сут и т.д.)
        q_value = q_result["q_m3h"]
        
        # Логирование успешных операций (конверсия единиц Q) удалено - избыточно
        
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
        
        # Логирование успешных операций удалено - избыточно
        
        if q_pos >= 0:
            search_start = max(0, q_pos - 50)
            search_end = min(len(text), q_pos + 150)
            h_context = text[search_start:search_end]
        else:
            # Если Q не найден, ищем H во всем тексте
            h_context = text
        
        # ИСПРАВЛЕНО: Используем улучшенный парсер напора
        h_result = extract_h_from_text(h_context)
        if h_result and h_result.get("confidence", 0) > 0.3:
            # h_m уже пересчитан в метры из любой единицы (бар, кПа, МПа, атм и т.д.)
            h_value = h_result["h_m"]
            
            # Логирование успешных операций (конверсия единиц H) удалено - избыточно
            
            # Валидируем Q и H
            from services.parsing_validator import validate_qh
            is_valid, q_error, h_error = validate_qh(q_value, h_value, "m3/h", "m")
            
            if is_valid:
                # Округляем до 2 знаков после запятой
                q_value = round(q_value, 2)
                h_value = round(h_value, 2)
                return {"q": q_value, "h": h_value}
            else:
                # Логирование ошибок валидации
                import json
                import os
                from datetime import datetime
                log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
                try:
                    os.makedirs(os.path.dirname(log_path), exist_ok=True)
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "location": "intents.py:extract_qh_from_text:validation",
                            "message": "WARNING: Q/H validation failed",
                            "data": {"q": q_value, "h": h_value, "q_error": q_error, "h_error": h_error},
                            "sessionId": "analysis",
                            "runId": "analysis",
                            "hypothesisId": "WARNING"
                        }) + "\n")
                except: pass
    
    # Паттерн 2: "Q=10, H=20" или "Q 10, H 20" (с возможными единицами)
    pattern2 = r"q\s*[=:]\s*(\d+\.?\d*)\s*(?:м[³3]?/ч|м3/ч|куб[ов]?)?\s*[,]?\s*h\s*[=:]\s*(\d+\.?\d*)\s*(?:м|метр[ов]?|m|bar|бар|kpa|кпа|mpa|мпа|atm|атм)?"
    match2 = re.search(pattern2, text, re.IGNORECASE)
    if match2:
        q_raw = match2.group(1)
        h_raw = match2.group(2)
        
        # Используем улучшенные парсеры для пересчета единиц
        q_text = f"{q_raw} м³/ч"  # Предполагаем м³/ч, если единица не указана
        h_text = f"{h_raw} м"  # Предполагаем метры, если единица не указана
        
        q_result = extract_q_from_text(q_text)
        h_result = extract_h_from_text(h_text)
        
        if q_result and q_result.get("confidence", 0) > 0.3 and h_result and h_result.get("confidence", 0) > 0.3:
            q_value = q_result["q_m3h"]
            h_value = h_result["h_m"]
            
            # Валидируем Q и H
            from services.parsing_validator import validate_qh
            is_valid, q_error, h_error = validate_qh(q_value, h_value, "m3/h", "m")
            
            if is_valid:
                # Округляем до 2 знаков после запятой
                q_value = round(q_value, 2)
                h_value = round(h_value, 2)
                return {"q": q_value, "h": h_value}
        else:
            # Fallback: если парсеры не сработали, пробуем интерпретировать как числа
            try:
                q_value = float(q_raw.replace(',', '.'))
                h_value = float(h_raw.replace(',', '.'))
                
                # Валидируем Q и H
                from services.parsing_validator import validate_qh
                is_valid, q_error, h_error = validate_qh(q_value, h_value, "m3/h", "m")
                
                if is_valid:
                    # Округляем до 2 знаков после запятой
                    q_value = round(q_value, 2)
                    h_value = round(h_value, 2)
                    return {"q": q_value, "h": h_value}
            except ValueError:
                pass
            
            # Логирование предупреждений
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
        # Логирование успешных операций удалено - избыточно
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
        # Логирование успешных операций удалено - избыточно
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
        # Логирование успешных операций удалено - избыточно
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
        
        # ИСПРАВЛЕНО: Если не нашли специфичный паттерн, пробуем общий поиск чисел
        # Но теперь учитываем контекстные слова для правильной интерпретации
        numbers = re.findall(r"\d+\.?\d*", text)
        if len(numbers) >= 2:
            # ИСПРАВЛЕНО: Ищем контекстные слова для Q и H
            q_context_words = ["кубов", "куб", "м3", "м³", "расход", "подача", "производительность"]
            h_context_words = ["напор", "метров", "м", "метр", "высота", "подъем", "подъём", "перепад"]
            temp_context_words = ["градусов", "°c", "°с", "c", "с", "температура", "темп"]
            
            # Находим позиции чисел и их контекст
            q_candidate = None
            h_candidate = None
            
            for i, num_str in enumerate(numbers):
                num = float(num_str.replace(',', '.'))
                num_pos = text_lower.find(num_str)
                if num_pos == -1:
                    continue
                
                # Проверяем контекст вокруг числа (50 символов до и после)
                context_start = max(0, num_pos - 50)
                context_end = min(len(text_lower), num_pos + len(num_str) + 50)
                context = text_lower[context_start:context_end]
                
                # Проверяем, не является ли это температурой
                is_temperature = any(word in context for word in temp_context_words)
                if is_temperature:
                    continue  # Пропускаем температуру
                
                # Проверяем контекст для Q
                if any(word in context for word in q_context_words):
                    if q_candidate is None or num > q_candidate:
                        q_candidate = num
                # Проверяем контекст для H
                elif any(word in context for word in h_context_words):
                    if h_candidate is None or num > h_candidate:
                        h_candidate = num
            
            # Если нашли Q и H по контексту - используем их
            if q_candidate is not None and h_candidate is not None:
                if 0.1 < q_candidate < 1000 and 0.1 < h_candidate < 500 and h_candidate >= 5:
                    q = round(q_candidate, 2)
                    h = round(h_candidate, 2)
                    result = {"q": q, "h": h}
                    # Логирование успешных операций удалено - избыточно
                    return result
            
            # Fallback: если не нашли по контексту, пробуем интерпретировать как Q и H
            # НО только если нет явных признаков температуры
            if not any(word in text_lower for word in temp_context_words):
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
                        # Логирование успешных операций удалено - избыточно
                        return result
                except:
                    pass
    
    # Логирование "Q/H not found" удалено - это debug/trace, не warning/error
    # Если нужно debug-логирование, включить по флагу DEBUG_QH_EXTRACTION
    
    return None


def normalize_model_text(text: str) -> str:
    """
    Нормализует текст модели насоса для сравнения.
    Приводит к единому формату: убирает пробелы, приводит к нижнему регистру.
    """
    text = text.lower().strip()
    text = re.sub(r'\s+', '', text)  # Убираем все пробелы
    return text


def _looks_like_pump_model(model: Optional[str]) -> bool:
    """
    Проверяет, похоже ли строка на модель насоса.
    """
    if not model:
        return False
    
    model_normalized = normalize_model_text(model)
    
    # Проверяем паттерны моделей насосов
    # CNP: CDM, CDL, CDLF, CDM-F, CDL-F и т.д.
    # ИСПРАВЛЕНО: Используем группы с альтернативами вместо квадратных скобок
    # Убрали \b, т.к. normalize_model_text() удаляет пробелы, и после модели сразу идут цифры (cdm1-3)
    if re.match(r'^(cdm|cdl|cdlf|cdmf|cdl-f|cdm-f)', model_normalized):
        return True
    
    # Grundfos: CR, CRE, CRN, CRNE, CRN-E и т.д.
    if re.match(r'^(cr|cre|crn|crne|crn-e)', model_normalized):
        return True
    
    # Wilo: Stratos, Stratos-Z, Stratos-PICO и т.д.
    if re.match(r'^stratos', model_normalized):
        return True
    
    # Pedrollo: различные модели
    if re.match(r'^[a-z]{2,}\d+', model_normalized):
        return True
    
    return False


def extract_brand_and_model(text: str) -> Dict[str, Optional[str]]:
    """
    Извлекает бренд и модель насоса из текста.
    
    Returns:
        {"brand": str | None, "model": str | None}
    """
    text_lower = text.lower()
    
    # Список известных брендов
    brands = {
        "cnp": "CNP",
        "grundfos": "Grundfos",
        "wilo": "Wilo",
        "pedrollo": "Pedrollo"
    }
    
    brand = None
    model = None
    
    # Ищем бренд в тексте
    for brand_key, brand_name in brands.items():
        if brand_key in text_lower:
            brand = brand_name
            break
    
    # Ищем модель (обычно после бренда или отдельно)
    # Паттерны моделей
    model_patterns = [
        r'\b(cdm[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',  # CNP CDM
        r'\b(cdl[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',  # CNP CDL
        r'\b(cdlf[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',  # CNP CDLF
        r'\b(cr[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',  # Grundfos CR
        r'\b(cre[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',  # Grundfos CRE
        r'\b(crn[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',  # Grundfos CRN
        r'\b(stratos[\s\-]?[a-z]?[\s\-]?\d*)\b',  # Wilo Stratos
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            model = match.group(1).strip()
            break
    
    return {"brand": brand, "model": model}


def detect_model_name(text: str) -> Optional[str]:
    """
    Определяет название модели насоса конкурента из текста.
    
    Returns:
        Название модели или None
    """
    text_lower = text.lower()
    
    # Паттерны для моделей насосов конкурентов
    model_patterns = [
        # CNP
        r'\b(cdm[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
        r'\b(cdl[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
        r'\b(cdlf[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
        # Grundfos
        r'\b(cr[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
        r'\b(cre[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
        r'\b(crn[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
        # Wilo
        r'\b(stratos[\s\-]?[a-z]?[\s\-]?\d*)\b',
        # Pedrollo
        r'\b([a-z]{2,}[\s\-]?\d+[\s\-]?\d*[\s\-]?[a-z]?)\b',
    ]
    
    for pattern in model_patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            model = match.group(1).strip()
            # Проверяем, что это действительно модель насоса
            if _looks_like_pump_model(model):
                return model
    
    return None


def detect_intent(
    message: str,
    has_attachments: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Определяет интент сообщения с учетом контекста истории диалога.
    
    PR3: Использует модульный роутер на основе правил.
    Этот метод теперь является тонким фасадом над intent_router.route_intent().
    
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
    # PR3: Используем модульный роутер
    # Роутер сам нормализует сообщение, поэтому передаем оригинал
    from services.nlu.intent_router import route_intent
    
    if context is None:
        context = {}
    
    # Вызываем роутер (нормализация происходит внутри)
    result = route_intent(message, has_attachments, context)
    
    # Преобразуем IntentResult в старый формат для обратной совместимости
    return {
        "intent": result.intent.value if hasattr(result.intent, 'value') else result.intent,
        "data": result.data
    }
