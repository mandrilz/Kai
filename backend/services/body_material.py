"""
Определение материала корпуса насосов Кометта по коду исполнения в модели.

Коды в модели (перед буквой исполнения уплотнения):
- /04*/ -> нержавеющая сталь 304 (AISI/SUS 304)
- /16*/ -> нержавеющая сталь 316 (AISI/SUS 316)
- /25*/ -> чугун (HT250)
"""

from __future__ import annotations

import re
from typing import Optional, Dict


BODY_MATERIAL_BY_CODE: Dict[str, str] = {
    "04": "нержавеющая сталь AISI 304 (SUS 304)",
    "16": "нержавеющая сталь AISI 316 (SUS 316)",
    "25": "чугун HT250",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    t = t.replace("ё", "е")
    # унифицируем "aisi"/"sus"
    t = re.sub(r"\s+", " ", t)
    return t


def detect_body_material_code_from_text(text: str) -> Optional[str]:
    """
    Извлекает требование материала корпуса из пользовательского текста.
    Возвращает код: "04" | "16" | "25" | None
    """
    t = normalize_text(text)

    # Чугун
    if any(k in t for k in ["чугун", "чугунный", "чугунina", "чугунь", "ht250", "ht 250"]):
        return "25"

    # Нержавейка 316
    if ("316" in t) and any(k in t for k in ["нерж", "нержав", "aisi", "sus", "сталь"]):
        return "16"
    if any(k in t for k in ["aisi 316", "aisi316", "sus 316", "sus316", "нерж 316", "нержав 316", "нержа 316"]):
        return "16"

    # Нержавейка 304
    if ("304" in t) and any(k in t for k in ["нерж", "нержав", "aisi", "sus", "сталь"]):
        return "04"
    if any(k in t for k in ["aisi 304", "aisi304", "sus 304", "sus304", "нерж 304", "нержав 304", "нержа 304"]):
        return "04"

    return None


def extract_body_material_code_from_model(model: str) -> Optional[str]:
    """
    Извлекает код материала корпуса из модели Кометта.
    Пример: "К144 32-50/16Е/040Т2" -> "16"
    """
    if not model:
        return None

    # Нормализуем кириллицу/латиницу для K/К
    m = str(model).strip()

    # Ищем сегмент "/04X/" или "/16Е/" или "/25A/" и т.п.
    # Буква исполнения может быть латиницей или кириллицей.
    match = re.search(r"/\s*(04|16|25)\s*([A-Za-zА-Яа-я])\s*/", m)
    if match:
        return match.group(1)

    # Иногда могут писать без закрывающего слеша в тексте: "/16Е"
    match2 = re.search(r"/\s*(04|16|25)\s*([A-Za-zА-Яа-я])\b", m)
    if match2:
        return match2.group(1)

    return None


def describe_body_material(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    code2 = str(code).strip()
    return BODY_MATERIAL_BY_CODE.get(code2)

