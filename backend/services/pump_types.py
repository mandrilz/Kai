"""
Модуль для распознавания типов насосов и определения наличия в линейке Кометта.
Содержит словарь типов, синонимы и логику детекции.
"""
import re
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum


class PumpTypeAvailability(Enum):
    """Доступность типа насоса в линейке Кометта"""
    AVAILABLE = "available"  # Есть у Кометта
    NOT_AVAILABLE = "not_available"  # Нет у Кометта


# ============================================================================
# СЛОВАРЬ ТИПОВ НАСОСОВ КОМЕТТА
# ============================================================================

KOMETTA_PUMP_TYPES = {
    "monoblock_centrifugal": {
        "series": ["К144"],
        "name": "Моноблочные центробежные",
        "description": "Одноступенчатые центробежные насосы с двигателем на одном валу",
        "synonyms": [
            "моноблочный насос",
            "насос моноблочный",
            "моноблочный",
            "консольно-моноблочный",
            "консольно моноблочный",
            "моноблок",
            "моноблочная центробежка",
            "одноступенчатый центробежный",
            "поверхностный центробежный насос",
            "surface pump",
            "end suction pump",
            "консольный насос моноблок",
            "насос с двигателем на одном валу",
            "к144",
            "k144",
        ],
    },
    "multistage_horizontal": {
        "series": ["К233"],
        "name": "Многоступенчатые горизонтальные",
        "description": "Горизонтальные многоступенчатые насосы высокого давления",
        "synonyms": [
            "многоступенчатый горизонтальный",
            "горизонтальный многоступенчатый насос",
            "горизонтальная многоступенка",
            "многоступенчатый насос лежачий",
            "horizontal multistage pump",
            "high pressure horizontal pump",
            "высоконапорный горизонтальный насос",
            "насос повышения давления горизонтальный",
            "к233",
            "k233",
        ],
    },
    "multistage_vertical": {
        "series": ["К377"],
        "name": "Многоступенчатые вертикальные",
        "description": "Вертикальные многоступенчатые насосы повышения давления",
        "synonyms": [
            "многоступенчатый вертикальный",
            "вертикальный многоступенчатый",
            "вертикальная многоступенка",
            "вертикальный многоступенчатый насос",
            "насос вертикальный многоступенчатый",
            "многоступенчатый насос вертикальный",
            "vertical multistage pump",
            "насос повышения давления вертикальный",
            "вертикальный насос повышения давления",
            "in-line многоступенчатый вертикальный",
            "вертикальный насос в линию многоступ",
            "к377",
            "k377",
        ],
    },
    "open_impeller": {
        "series": ["К610"],
        "name": "Одноступенчатые с открытым рабочим колесом",
        "description": "Насосы для воды с примесями (без волокон и фекалий)",
        "synonyms": [
            "насос с открытым рабочим колесом",
            "открытое рабочее колесо",
            "насос для грязной воды",
            "насос для воды с примесями",
            "грязевой насос",
            "насос для загрязненной воды",
            "open impeller pump",
            "semi-open impeller pump",
            "насос для шлама",
            "насос для воды с включениями",
            "к610",
            "k610",
        ],
    },
    "inline_circulation": {
        "series": ["К987"],
        "name": "Циркуляционные inline",
        "description": "Насосы для систем отопления, ГВС, ХВС, циркуляции",
        "synonyms": [
            "циркуляционный насос",
            "насос в линию",
            "inline насос",
            "in-line pump",
            "насос отопления",
            "насос для отопления",
            "насос для гвс",
            "насос для хвс",
            "насос циркуляции",
            "насос для котельной",
            "hvac pump",
            "насос для теплоснабжения",
            "циркуляционка",
            "к987",
            "k987",
        ],
    },
}

# ============================================================================
# ТИПЫ НАСОСОВ, КОТОРЫХ НЕТ У КОМЕТТА
# ============================================================================

UNSUPPORTED_PUMP_TYPES = {
    "submersible_borehole": {
        "name": "Погружные скважинные",
        "description": "Погружные насосы для скважин и артезианских источников",
        "synonyms": [
            "погружной насос",
            "скважинный насос",
            "глубинный насос",
            "насос в скважину",
            "submersible borehole pump",
            "насос для артезианской скважины",
            "погружной скважинный",
            "насос для скважины",
            "глубинка",
        ],
        "clarifying_questions": [
            "Какая глубина скважины и диаметр обсадной трубы?",
            "Каков динамический уровень воды?",
            "Какие требуемые Q (м³/ч) и H (м)?",
            "Есть ли в воде песок, железо или другие примеси?",
        ],
        "alternative_suggestion": "Кометта производит поверхностные насосы. Если задача — повышение давления из накопительной ёмкости, могу подобрать К377 или К233 по Q/H.",
    },
    "submersible_drainage": {
        "name": "Дренажные погружные",
        "description": "Погружные насосы для откачки воды из подвалов, котлованов",
        "synonyms": [
            "дренажный насос",
            "погружной дренажный",
            "насос для подвала",
            "насос для котлована",
            "насос для откачки воды",
            "submersible drainage pump",
            "дренажник",
        ],
        "clarifying_questions": [
            "Какой объём воды нужно откачивать?",
            "Есть ли твёрдые включения (песок, мусор)?",
            "Какая глубина погружения?",
        ],
        "alternative_suggestion": "Если нужен поверхностный насос для перекачки воды с примесями, могу предложить К610 (открытое рабочее колесо).",
    },
    "sewage_fecal": {
        "name": "Канализационные/фекальные",
        "description": "Насосы для сточных вод с измельчителем",
        "synonyms": [
            "канализационный насос",
            "фекальный насос",
            "насос для сточных вод",
            "насос с измельчителем",
            "fecal pump",
            "sewage pump",
            "насос для канализации",
            "фекальник",
        ],
        "clarifying_questions": [
            "Какой размер твёрдых включений (мм)?",
            "Какая температура стоков?",
            "Какой режим работы (постоянный/периодический)?",
        ],
        "alternative_suggestion": "Если это просто загрязнённая вода без волокон и фекалий, К610 может подойти. Для настоящих канализационных стоков нужен специализированный фекальный насос.",
    },
    "self_priming": {
        "name": "Самовсасывающие",
        "description": "Насосы с возможностью самостоятельного всасывания",
        "synonyms": [
            "самовсасывающий насос",
            "самовсасывающий",
            "jet pump",
            "эжекторный насос",
            "насос с эжектором",
            "self priming pump",
            "самовсас",
        ],
        "clarifying_questions": [
            "Какая высота всасывания (м)?",
            "Какая длина всасывающей линии?",
            "Есть ли возможность установить насос ниже уровня жидкости (с подпором)?",
        ],
        "alternative_suggestion": "Если можно организовать залив/подпор, подойдут К144 или К233 по Q/H. Самовсасывающих насосов в линейке Кометта нет.",
    },
    "dosing": {
        "name": "Дозировочные",
        "description": "Насосы для точного дозирования химических реагентов",
        "synonyms": [
            "дозировочный насос",
            "насос дозатор",
            "мембранный насос",
            "плунжерный дозировочный",
            "chemical dosing pump",
            "дозатор",
        ],
        "clarifying_questions": [
            "Какой химсостав и концентрация дозируемой жидкости?",
            "Какая температура?",
            "Какие требования к материалам и уплотнениям?",
        ],
        "alternative_suggestion": "Для циркуляции растворов без точного дозирования могут подойти К377/К233 (если совместимы по материалам). Для точного дозирования нужен специализированный дозировочный насос.",
    },
    "gear": {
        "name": "Шестерёнчатые",
        "description": "Насосы для вязких жидкостей и масел",
        "synonyms": [
            "шестеренчатый насос",
            "шестерёнчатый насос",
            "gear pump",
            "насос для масла",
            "масляный насос",
        ],
        "clarifying_questions": [
            "Какая вязкость жидкости?",
            "Какая температура?",
            "Какой требуемый расход?",
        ],
        "alternative_suggestion": "Кометта производит центробежные насосы для воды и маловязких жидкостей. Для масел и вязких сред нужен шестерёнчатый или винтовой насос.",
    },
    "screw": {
        "name": "Винтовые",
        "description": "Насосы для вязких и неоднородных сред",
        "synonyms": [
            "винтовой насос",
            "шнековый насос",
            "progressive cavity pump",
            "pc pump",
        ],
        "clarifying_questions": [
            "Какая вязкость и состав перекачиваемой среды?",
            "Какая температура?",
            "Есть ли абразивные частицы?",
        ],
        "alternative_suggestion": "Кометта — центробежные насосы. Для вязких и неоднородных сред нужен винтовой насос.",
    },
    "peristaltic": {
        "name": "Перистальтические",
        "description": "Шланговые насосы для агрессивных и абразивных сред",
        "synonyms": [
            "перистальтический насос",
            "шланговый насос",
            "hose pump",
            "peristaltic pump",
        ],
        "clarifying_questions": [
            "Какой состав перекачиваемой среды?",
            "Какой требуемый расход и давление?",
        ],
        "alternative_suggestion": "Перистальтических насосов в линейке Кометта нет.",
    },
    "vacuum": {
        "name": "Вакуумные",
        "description": "Насосы для создания вакуума",
        "synonyms": [
            "вакуумный насос",
            "насос вакуумный",
            "vacuum pump",
        ],
        "clarifying_questions": [
            "Какой требуемый уровень вакуума?",
            "Какой объём откачиваемого пространства?",
        ],
        "alternative_suggestion": "Вакуумных насосов в линейке Кометта нет.",
    },
    "fire_pump": {
        "name": "Пожарные насосы",
        "description": "Сертифицированные комплекты для пожаротушения",
        "synonyms": [
            "пожарный насос",
            "насос пожаротушения",
            "fire fighting pump",
            "fire pump",
            "насос для пожаротушения",
        ],
        "clarifying_questions": [
            "Какие требования по сертификации?",
            "Какие Q и H для системы пожаротушения?",
        ],
        "alternative_suggestion": "Насосы Кометта могут использоваться в системах водоснабжения, но сертифицированных пожарных комплектов в линейке нет. Могу подобрать насос по Q/H для технических нужд.",
    },
}


def normalize_text_for_type(text: str) -> str:
    """Нормализует текст для поиска типа насоса"""
    text = text.lower()
    # Убираем лишние пробелы
    text = re.sub(r'\s+', ' ', text)
    # Заменяем ё на е
    text = text.replace('ё', 'е')
    return text.strip()


def detect_pump_type(text: str) -> Optional[Dict[str, Any]]:
    """
    Определяет тип насоса из текста.
    
    Returns:
        {
            "type_key": str,  # ключ типа
            "type_name": str,  # название типа
            "availability": PumpTypeAvailability,  # доступность
            "series": List[str] | None,  # серии Кометта (если есть)
            "confidence": float,  # уверенность
            "matched_synonym": str,  # какой синоним сработал
            "clarifying_questions": List[str] | None,  # вопросы (если типа нет)
            "alternative_suggestion": str | None,  # альтернатива (если типа нет)
        } или None
    """
    normalized = normalize_text_for_type(text)
    
    best_match = None
    best_confidence = 0.0
    best_synonym_len = 0
    
    # Сначала проверяем типы Кометта
    for type_key, type_data in KOMETTA_PUMP_TYPES.items():
        for synonym in type_data["synonyms"]:
            synonym_lower = synonym.lower().replace('ё', 'е')
            
            # Улучшенная проверка: для многословных синонимов проверяем наличие всех слов
            # независимо от порядка и других слов между ними
            synonym_words = synonym_lower.split()
            if len(synonym_words) > 1:
                # Для многословных синонимов проверяем наличие всех слов (независимо от порядка)
                # Это важно для фраз типа "насос вертикальный многоступенчатый" - 
                # должно найтись, даже если слова разделены словом "насос"
                if all(word in normalized for word in synonym_words):
                    # Все слова найдены - это хорошее совпадение
                    found = True
                elif synonym_lower in normalized:
                    # Или точная подстрока (без дополнительных слов)
                    found = True
                else:
                    found = False
            else:
                # Однословный синоним - просто проверяем вхождение
                found = synonym_lower in normalized
            
            if found:
                # Уверенность зависит от длины синонима (более специфичные = выше)
                confidence = min(1.0, 0.5 + len(synonym_lower) / 50)
                
                # Для многословных синонимов повышаем уверенность
                if len(synonym_words) > 1:
                    confidence = min(1.0, confidence + 0.1)
                
                # Приоритет более длинным синонимам
                if confidence > best_confidence or (confidence == best_confidence and len(synonym_lower) > best_synonym_len):
                    best_confidence = confidence
                    best_synonym_len = len(synonym_lower)
                    best_match = {
                        "type_key": type_key,
                        "type_name": type_data["name"],
                        "description": type_data["description"],
                        "availability": PumpTypeAvailability.AVAILABLE,
                        "series": type_data["series"],
                        "confidence": confidence,
                        "matched_synonym": synonym,
                        "clarifying_questions": None,
                        "alternative_suggestion": None,
                    }
    
    # Затем проверяем неподдерживаемые типы
    for type_key, type_data in UNSUPPORTED_PUMP_TYPES.items():
        for synonym in type_data["synonyms"]:
            synonym_lower = synonym.lower().replace('ё', 'е')
            
            # Улучшенная проверка для неподдерживаемых типов
            synonym_words = synonym_lower.split()
            if len(synonym_words) > 1:
                found = all(word in normalized for word in synonym_words) or synonym_lower in normalized
            else:
                found = synonym_lower in normalized
            
            if found:
                # Уверенность зависит от длины синонима
                confidence = min(1.0, 0.5 + len(synonym_lower) / 50)
                
                # Для многословных синонимов повышаем уверенность
                if len(synonym_words) > 1:
                    confidence = min(1.0, confidence + 0.1)
                
                # Приоритет более длинным синонимам
                if confidence > best_confidence or (confidence == best_confidence and len(synonym_lower) > best_synonym_len):
                    best_confidence = confidence
                    best_synonym_len = len(synonym_lower)
                    best_match = {
                        "type_key": type_key,
                        "type_name": type_data["name"],
                        "description": type_data["description"],
                        "availability": PumpTypeAvailability.NOT_AVAILABLE,
                        "series": None,
                        "confidence": confidence,
                        "matched_synonym": synonym,
                        "clarifying_questions": type_data.get("clarifying_questions", []),
                        "alternative_suggestion": type_data.get("alternative_suggestion"),
                    }
    
    # Логирование
    if best_match:
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "pump_types.py:detect_pump_type",
                    "message": "Pump type detected",
                    "data": {
                        "input_text": text[:200],
                        "type_key": best_match["type_key"],
                        "type_name": best_match["type_name"],
                        "availability": best_match["availability"].value,
                        "confidence": best_match["confidence"],
                        "matched_synonym": best_match["matched_synonym"],
                    },
                    "sessionId": "analysis",
                    "runId": "analysis",
                    "hypothesisId": "A"
                }, ensure_ascii=False) + "\n")
        except: pass
    
    return best_match


def get_kometta_series_info(series_code: str) -> Optional[Dict[str, Any]]:
    """
    Возвращает информацию о серии Кометта.
    """
    series_map = {
        "К144": {
            "name": "К144",
            "full_name": "Моноблочные центробежные насосы",
            "description": "Одноступенчатые центробежные насосы с двигателем на одном валу. Применяются для чистой воды в системах водоснабжения, отопления, кондиционирования.",
            "type_key": "monoblock_centrifugal",
        },
        "К233": {
            "name": "К233",
            "full_name": "Многоступенчатые горизонтальные насосы",
            "description": "Горизонтальные многоступенчатые насосы высокого давления. Применяются для повышения давления, водоснабжения высотных зданий.",
            "type_key": "multistage_horizontal",
        },
        "К377": {
            "name": "К377",
            "full_name": "Многоступенчатые вертикальные насосы",
            "description": "Вертикальные многоступенчатые насосы повышения давления. Компактные, устанавливаются в линию.",
            "type_key": "multistage_vertical",
        },
        "К610": {
            "name": "К610",
            "full_name": "Насосы с открытым рабочим колесом",
            "description": "Одноступенчатые насосы для воды с примесями (без волокон и фекалий). Открытое рабочее колесо позволяет перекачивать загрязнённую воду.",
            "type_key": "open_impeller",
        },
        "К987": {
            "name": "К987",
            "full_name": "Циркуляционные насосы inline",
            "description": "Насосы для систем отопления, ГВС, ХВС. Устанавливаются непосредственно в трубопровод (inline).",
            "type_key": "inline_circulation",
        },
    }
    return series_map.get(series_code)


def generate_type_response(type_info: Dict[str, Any]) -> str:
    """
    Генерирует ответ бота на запрос о типе насоса.
    
    Args:
        type_info: результат detect_pump_type() (может содержать Enum или строку для availability)
        
    Returns:
        Текст ответа
    """
    import random
    
    # ВАЖНО: availability может быть как Enum, так и строкой (если загружен из состояния)
    availability = type_info.get("availability")
    is_available = (
        availability == PumpTypeAvailability.AVAILABLE or
        (isinstance(availability, str) and availability == "available")
    )
    
    if is_available:
        # Тип есть у Кометта
        # Безопасно извлекаем series
        series_raw = type_info.get("series")
        if isinstance(series_raw, list):
            series_list = ", ".join(str(s) for s in series_raw)
        elif isinstance(series_raw, str):
            series_list = series_raw
        else:
            series_list = "не указано"
        
        intro_variants = [
            f"Да, у Кометта есть такой тип насосов.",
            f"Отлично, этот тип есть в линейке Кометта.",
            f"Понял, такие насосы у Кометта есть.",
        ]
        
        type_name = type_info.get("type_name", "этого типа")
        description = type_info.get("description", "")
        
        response_parts = [
            random.choice(intro_variants),
            f"\n\n**{type_name}** — серия **{series_list}**",
        ]
        
        if description:
            response_parts.append(f"\n{description}")
        
        response_parts.extend([
            "\n\nДля подбора конкретного насоса мне нужно уточнить:",
            "\n1. Какая жидкость, температура, есть ли примеси?",
            "\n2. Какие требуемые Q (м³/ч) и H (м)?",
            "\n3. Какие условия монтажа (вертикально/горизонтально, место установки)?",
            "\n\nСкажите параметры — подберу подходящий артикул.",
        ])
        
        return "".join(response_parts)
    
    else:
        # Типа нет у Кометта
        type_name = type_info.get("type_name", "этого типа")
        type_name_lower = type_name.lower() if isinstance(type_name, str) else "этого типа"
        
        intro_variants = [
            f"Понял, вы ищете {type_name_lower}.",
            f"Вижу, нужен {type_name_lower}.",
        ]
        
        response_parts = [
            random.choice(intro_variants),
            f"\n\n**В текущей линейке Кометта такого типа нет.**",
            f"\n\nНо я могу помочь:",
        ]
        
        # Добавляем варианты решения
        response_parts.append("\n\n**Вариант 1:** Если важен результат (а не конкретный тип), давайте подберём насос Кометта по рабочей точке Q/H и условиям эксплуатации.")
        
        alternative_suggestion = type_info.get("alternative_suggestion")
        if alternative_suggestion:
            response_parts.append(f"\n\n**Вариант 2:** {alternative_suggestion}")
        
        response_parts.append("\n\n**Вариант 3:** Если критична именно конструкция, уточните параметры — подскажу, что из Кометта максимально близко.")
        
        # Уточняющие вопросы
        clarifying_questions = type_info.get("clarifying_questions")
        if clarifying_questions and isinstance(clarifying_questions, list):
            response_parts.append("\n\n**Уточняющие вопросы:**")
            for i, q in enumerate(clarifying_questions[:3], 1):
                response_parts.append(f"\n{i}. {q}")
        
        response_parts.append("\n\n**Что важнее: именно конструкция или решение задачи (Q/H + условия)?**")
        
        # Фильтруем пустые строки перед объединением
        filtered_parts = [part for part in response_parts if part]
        return "".join(filtered_parts)


def list_available_pump_types() -> List[str]:
    """
    Возвращает список доступных типов насосов Кометта с кратким описанием.
    """
    items = []
    for type_key, type_data in KOMETTA_PUMP_TYPES.items():
        series_str = ", ".join(type_data.get("series", []))
        items.append(f"**{type_data['name']}** (серии: {series_str})\n{type_data['description']}")
    return items


def get_pump_components_description() -> str:
    """
    Возвращает описание основных компонентов насоса Кометта.
    """
    return (
        "**Основные компоненты насоса Кометта:**\n\n"
        "1. **Корпус (статор)** — основная часть насоса, в которой происходит перекачивание жидкости\n"
        "2. **Рабочее колесо (импеллер)** — вращающаяся часть, создающая напор и расход\n"
        "3. **Вал** — передает вращение от двигателя к рабочему колесу\n"
        "4. **Уплотнения** — предотвращают утечки (сальниковое уплотнение или торцевое уплотнение)\n"
        "5. **Подшипники** — обеспечивают вращение вала\n"
        "6. **Двигатель** — электрический двигатель (в моноблочных насосах — на одном валу)\n"
        "7. **Фланец всасывания и нагнетания** — для подключения к трубопроводу\n\n"
        "В зависимости от типа насоса (моноблочный, многоступенчатый и т.д.) конструкция может отличаться."
    )

