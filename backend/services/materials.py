"""
Модуль для работы с материалами исполнения насосов в зависимости от типа жидкости.
Классифицирует жидкость, определяет подходящие материалы (A/E/X/H) и складские серии.
"""
import json
import os
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path


def load_materials_rules() -> Dict[str, Any]:
    """
    Загружает правила материалов из JSON файла.
    
    Returns:
        Словарь с правилами материалов
    """
    try:
        # Определяем путь к файлу правил
        current_dir = Path(__file__).parent
        rules_path = current_dir / "materials_rules.json"
        
        with open(rules_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        # Логируем ошибку
        import json as json_lib
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json_lib.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "materials.py:load_materials_rules",
                    "message": "ERROR loading materials rules",
                    "error": str(e),
                    "sessionId": "error",
                    "runId": "error",
                    "hypothesisId": "ERROR"
                }) + "\n")
        except:
            pass
        
        # Возвращаем пустую структуру
        return {
            "materials": {},
            "stock_by_series": {},
            "liquid_categories": {}
        }


def classify_liquid(text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Классифицирует жидкость по тексту пользователя.
    
    Args:
        text: текст пользователя
        
    Returns:
        (category_key, category_data) или ("unknown", unknown_category)
    """
    rules = load_materials_rules()
    categories = rules.get("liquid_categories", {})
    
    text_lower = text.lower()
    best_category = "unknown"
    best_score = 0
    
    # Проходим по всем категориям (кроме unknown)
    for cat_key, cat_data in categories.items():
        if cat_key == "unknown":
            continue
        
        keywords = cat_data.get("keywords_any", [])
        score = 0
        
        # Подсчитываем совпадения ключевых слов
        for keyword in keywords:
            if keyword in text_lower:
                score += len(keyword)  # Более длинные ключевые слова = больше вес
        
        if score > best_score:
            best_score = score
            best_category = cat_key
    
    # Возвращаем лучшую категорию или unknown
    if best_score == 0:
        return "unknown", categories.get("unknown", {})
    else:
        return best_category, categories.get(best_category, {})


def decide_materials(
    category: str,
    has_abrasive: Optional[bool] = None,
    temp_c: Optional[float] = None
) -> Dict[str, Any]:
    """
    Определяет подходящие материалы исполнения на основе категории жидкости.
    
    Args:
        category: ключ категории жидкости
        has_abrasive: есть ли абразив (None = не указано)
        temp_c: температура (°C), None = не указана
        
    Returns:
        {
            "allowed_materials": ["E", "X"],
            "not_allowed_materials": ["A", "H"],
            "preferred_materials": ["X"],  # с учетом абразива
            "materials_info": {  # подробная информация о материалах
                "E": {"seal": "...", "elastomer": "..."},
                ...
            }
        }
    """
    rules = load_materials_rules()
    categories = rules.get("liquid_categories", {})
    materials_info = rules.get("materials", {})
    
    cat_data = categories.get(category, categories.get("unknown", {}))
    
    allowed = cat_data.get("allowed_materials", [])
    not_allowed = cat_data.get("not_allowed_materials", [])
    
    # Определяем предпочтительные материалы с учетом абразива
    preferred = []
    if has_abrasive is not None:
        abrasive_prefer = cat_data.get("abrasive_prefer", {})
        preferred = abrasive_prefer.get(str(has_abrasive).lower(), allowed)
    else:
        preferred = allowed
    
    return {
        "allowed_materials": allowed,
        "not_allowed_materials": not_allowed,
        "preferred_materials": preferred,
        "materials_info": {
            mat: materials_info.get(mat, {})
            for mat in allowed
        }
    }


def get_stock_series_by_materials(allowed_materials: List[str]) -> Dict[str, List[str]]:
    """
    Определяет, какие серии доступны со склада для данных материалов.
    
    Args:
        allowed_materials: список допустимых материалов (например, ["E", "X"])
        
    Returns:
        {
            "stock_series": ["K377", "K987"],  # серии со склада
            "non_stock_series": ["K144", "K233", "K610"],  # серии не со склада
            "series_details": {
                "K377": {"material": "E", "available": true},
                ...
            }
        }
    """
    rules = load_materials_rules()
    stock_by_series = rules.get("stock_by_series", {})
    
    stock_series = []
    non_stock_series = []
    series_details = {}
    
    # Проходим по всем сериям
    for series, series_material in stock_by_series.items():
        is_available = series_material in allowed_materials
        
        series_details[series] = {
            "material": series_material,
            "available": is_available
        }
        
        if is_available:
            stock_series.append(series)
        else:
            non_stock_series.append(series)
    
    return {
        "stock_series": stock_series,
        "non_stock_series": non_stock_series,
        "series_details": series_details
    }


def generate_materials_response(
    category: str,
    liquid_description: str = "",
    has_abrasive: Optional[bool] = None,
    temp_c: Optional[float] = None
) -> str:
    """
    Генерирует ответ бота о материалах исполнения.
    
    Args:
        category: категория жидкости
        liquid_description: описание жидкости от пользователя
        has_abrasive: есть ли абразив
        temp_c: температура
        
    Returns:
        Текст ответа бота
    """
    rules = load_materials_rules()
    categories = rules.get("liquid_categories", {})
    
    cat_data = categories.get(category, categories.get("unknown", {}))
    cat_title = cat_data.get("title", "Неизвестная среда")
    
    # Определяем материалы
    materials_result = decide_materials(category, has_abrasive, temp_c)
    allowed = materials_result["allowed_materials"]
    not_allowed = materials_result["not_allowed_materials"]
    preferred = materials_result["preferred_materials"]
    
    # Определяем складские серии
    stock_result = get_stock_series_by_materials(allowed)
    stock_series = stock_result["stock_series"]
    non_stock_series = stock_result["non_stock_series"]
    
    response_parts = []
    
    # Заголовок
    if liquid_description:
        response_parts.append(f"**Среда:** {liquid_description}")
    else:
        response_parts.append(f"**Среда:** {cat_title}")
    
    if temp_c is not None:
        response_parts.append(f"**Температура:** {temp_c} °C")
    
    if has_abrasive is not None:
        response_parts.append(f"**Примеси/абразив:** {'есть' if has_abrasive else 'нет'}")
    
    response_parts.append("")
    
    # Материалы
    if allowed:
        materials_descriptions = []
        for mat in allowed:
            mat_info = materials_result["materials_info"].get(mat, {})
            seal = mat_info.get("seal", "")
            elastomer = mat_info.get("elastomer", "")
            desc = f"**{mat}** (уплотнение: {seal}, эластомер: {elastomer})"
            if mat in preferred:
                desc += " ⭐ (предпочтительно)"
            materials_descriptions.append(desc)
        
        response_parts.append("**Подходят материалы исполнения:**")
        response_parts.append("\n".join(materials_descriptions))
    else:
        response_parts.append("**Подходящие материалы:** не определены (нужны уточнения)")
    
    response_parts.append("")
    
    if not_allowed:
        response_parts.append(f"**Не подходят:** {', '.join(not_allowed)}")
        response_parts.append("")
    
    # Складские серии
    if stock_series:
        response_parts.append(f"**Складские серии (доступны со склада):** {', '.join(stock_series)}")
    
    if non_stock_series:
        response_parts.append(
            f"**Серии не со склада:** {', '.join(non_stock_series)}. "
            "Могу уточнить возможность спец-комплектации/под заказ."
        )
    
    response_parts.append("")
    
    # Примечания
    notes = cat_data.get("notes", [])
    if notes:
        response_parts.append("**Примечания:**")
        for note in notes:
            response_parts.append(f"• {note}")
    
    response_parts.append("")
    
    # Уточняющие вопросы
    followup = cat_data.get("followup_questions", [])
    if followup:
        response_parts.append("**Уточняющие вопросы:**")
        for i, q in enumerate(followup, 1):
            response_parts.append(f"{i}. {q}")
    
    return "\n".join(response_parts)


def extract_liquid_info(text: str) -> Dict[str, Any]:
    """
    Извлекает информацию о жидкости из текста пользователя.
    
    Returns:
        {
            "category": "water_based",
            "has_abrasive": True/False/None,
            "temp_c": 40.0/None,
            "description": "вода",
            ...
        }
    """
    text_lower = text.lower()
    
    # Определяем категорию
    category, _ = classify_liquid(text)
    
    # Определяем наличие абразива
    has_abrasive = None
    abrasive_keywords = ["абразив", "песок", "окалина", "кристалл", "взвесь", "примес"]
    no_abrasive_keywords = ["нет", "без", "чист"]
    
    for keyword in abrasive_keywords:
        if keyword in text_lower:
            has_abrasive = True
            break
    
    if has_abrasive is None:
        for keyword in no_abrasive_keywords:
            if keyword in text_lower:
                has_abrasive = False
                break
    
    # Извлекаем температуру (с поддержкой минусовых и плюсовых значений)
    import re
    temp_c = None
    
    # Приоритет 1: Проверяем "минус" как слово
    minus_word_match = re.search(r'минус\s+(\d+(?:[.,]\d+)?)', text_lower)
    if minus_word_match:
        try:
            temp_c = -float(minus_word_match.group(1).replace(',', '.'))
            if not (-50 <= temp_c <= 200):
                temp_c = None
        except (ValueError, IndexError):
            pass
    
    # Приоритет 2: Проверяем "плюс" как слово (приравнивается к положительному)
    if temp_c is None:
        plus_word_match = re.search(r'плюс\s+(\d+(?:[.,]\d+)?)', text_lower)
        if plus_word_match:
            try:
                temp_c = float(plus_word_match.group(1).replace(',', '.'))
                if not (-50 <= temp_c <= 200):
                    temp_c = None
            except (ValueError, IndexError):
                pass
    
    # Приоритет 3: Паттерны с явным знаком (+, -)
    if temp_c is None:
        temp_patterns_with_sign = [
            r"температур[аы]\s*[:\-=]?\s*([+-]\d+(?:[.,]\d+)?)\s*°?c",
            r"([+-]\d+(?:[.,]\d+)?)\s*°?c",
            r"t\s*[=:]\s*([+-]\d+(?:[.,]\d+)?)"
        ]
        
        for pattern in temp_patterns_with_sign:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    temp_str = match.group(1).replace(',', '.')
                    temp_c = float(temp_str)
                    if -50 <= temp_c <= 200:
                        break
                    else:
                        temp_c = None
                except (ValueError, IndexError):
                    continue
    
    # Приоритет 4: Паттерны без знака (может быть положительное или отрицательное)
    # В этом модуле просто извлекаем, уточнение знака будет в slot_extractor
    if temp_c is None:
        temp_patterns = [
            r"температур[аы]\s*[:\-=]?\s*(\d+(?:[.,]\d+)?)\s*°?c",
            r"(\d+(?:[.,]\d+)?)\s*°?c",
            r"t\s*[=:]\s*(\d+(?:[.,]\d+)?)"
        ]
        
        for pattern in temp_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    temp_str = match.group(1).replace(',', '.')
                    temp_c = float(temp_str)
                    if -50 <= temp_c <= 200:
                        break
                    else:
                        temp_c = None
                except (ValueError, IndexError):
                    continue
    
    return {
        "category": category,
        "has_abrasive": has_abrasive,
        "temp_c": temp_c,
        "description": text[:100] if text else ""
    }

