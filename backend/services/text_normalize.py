"""
Модуль для нормализации и исправления опечаток в пользовательском тексте.
Включает словарную замену и fuzzy matching по целевым словам.
Безопасно обрабатывает модели, артикулы и числа - не трогает их.
"""
import re
from typing import Tuple, List, Dict, Any, Optional

# Импортируем словарь опечаток и целевые слова
try:
    from services.typos import TYPO_DICT, PUMP_TARGET_WORDS
except ImportError:
    # Fallback если модуль не найден
    TYPO_DICT = {}
    PUMP_TARGET_WORDS = []


# Регулярное выражение для "запрещённых" символов (не трогать такие слова)
BAD_CHARS_RE = re.compile(r"[0-9/=\\\-_:]")


def damerau_levenshtein(a: str, b: str, max_dist: int = 2) -> int:
    """
    Быстрый Damerau-Levenshtein с ранним выходом.
    Возвращает расстояние, либо max_dist+1 если уже хуже порога.
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1

    # DP матрица (la+1) x (lb+1)
    # используем списки для скорости
    prev_prev = list(range(lb + 1))
    prev = [0] * (lb + 1)
    cur = [0] * (lb + 1)

    for i in range(1, la + 1):
        cur[0] = i
        # минимальное значение в строке для раннего выхода
        row_min = cur[0]

        ca = a[i - 1]
        for j in range(1, lb + 1):
            cb = b[j - 1]
            cost = 0 if ca == cb else 1

            # операции: удаление, вставка, замена
            deletion = prev[j] + 1
            insertion = cur[j - 1] + 1
            substitution = prev[j - 1] + cost
            best = min(deletion, insertion, substitution)

            # транспозиция соседних символов
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                best = min(best, prev_prev[j - 2] + 1)

            cur[j] = best
            row_min = min(row_min, best)

        if row_min > max_dist:
            return max_dist + 1

        prev_prev, prev, cur = prev, cur, prev_prev  # переиспользуем массивы

    dist = prev[lb]
    return dist


def should_skip_token(token: str) -> bool:
    """
    Определяет, нужно ли пропускать токен (не трогать его).
    Пропускаем:
    - ALL CAPS (бренды типа CNP, WILO)
    - слова с цифрами/дефисами/слэшами/= (модели, артикулы)
    - слишком короткие слова (< 4 символов)
    """
    if not token:
        return True
    
    # ALL CAPS (бренды типа CNP, WILO)
    if token.isupper() and len(token) >= 2:
        return True
    
    # содержит цифры/дефисы/слэши/=
    if BAD_CHARS_RE.search(token):
        return True
    
    # слишком короткое
    if len(token) < 4:
        return True
    
    return False


def fuzzy_correct_word(word: str, targets: List[str], max_dist: int = 2) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Исправляет одно слово через fuzzy matching по целевым словам.
    
    Returns:
        (исправленное_слово, correction_info|None)
    """
    original = word
    w = word.lower()

    if should_skip_token(original):
        return original, None

    # порог зависит от длины
    # 4-5 символов: максимум 1 ошибка
    # 6+ символов: до 2 ошибок
    limit = 1 if len(w) <= 5 else max_dist

    best = None
    best_dist = limit + 1

    for t in targets:
        # не сравниваем с составными фразами
        if " " in t:
            continue
        if abs(len(t) - len(w)) > limit:
            continue

        d = damerau_levenshtein(w, t, max_dist=limit)
        if d < best_dist:
            best_dist = d
            best = t
            if best_dist == 0:
                break

    # если нашли достаточно близко — исправляем
    if best is not None and best_dist <= limit and best != w:
        return best, {
            "from": original,
            "to": best,
            "method": "fuzzy",
            "distance": best_dist
        }

    return original, None


def normalize_user_text(
    text: str,
    typo_dict: Optional[Dict[str, str]] = None,
    enable_fuzzy: bool = True
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Нормализует пользовательский текст: исправляет опечатки через словарь и fuzzy matching.
    
    ВАЖНО: Не трогает слова с цифрами, дефисами, ALL CAPS (модели, артикулы, бренды).
    
    Args:
        text: исходный текст пользователя
        typo_dict: словарь опечаток (если None, используется TYPO_DICT)
        enable_fuzzy: включать ли fuzzy matching
        
    Returns:
        (normalized_text, corrections)
        corrections: список исправлений вида [{"from": "...", "to": "...", "method": "dict/fuzzy", ...}]
    """
    typo_dict = typo_dict or TYPO_DICT
    corrections = []

    # базовая нормализация: убираем лишние пробелы, но сохраняем структуру
    s = text.strip()

    # токенизация: сохраняем знаки пунктуации как отдельные токены
    # Используем более точное регулярное выражение
    tokens = re.findall(r"\w+|[^\w\s]", s, flags=re.UNICODE)

    out = []
    for tok in tokens:
        low = tok.lower()

        # 1) словарные замены (быстро и безопасно)
        if low in typo_dict:
            fixed = typo_dict[low]
            if fixed != tok:
                corrections.append({
                    "from": tok,
                    "to": fixed,
                    "method": "dict"
                })
            out.append(fixed)
            continue

        # 2) fuzzy только для "слов" (не пунктуация) и если включено
        elif enable_fuzzy and re.match(r"^\w+$", tok, flags=re.UNICODE):
            fixed, corr = fuzzy_correct_word(tok, PUMP_TARGET_WORDS)
            if corr:
                corrections.append(corr)
            out.append(fixed)
        else:
            # не трогаем пунктуацию и специальные символы
            out.append(tok)

    # сборка обратно: простое правило пробелов
    normalized = ""
    for i, tok in enumerate(out):
        if i == 0:
            normalized += tok
            continue
        # не ставим пробел перед пунктуацией
        if re.match(r"^[,.;:!?)\]\)]$", tok):
            normalized += tok
        # не ставим пробел после открывающей скобки
        elif i > 0 and out[i - 1] == "(":
            normalized += tok
        else:
            normalized += " " + tok

    # Логирование исправлений
    if corrections:
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "text_normalize.py:normalize_user_text",
                    "message": "Text normalization applied",
                    "data": {
                        "original": text[:200],  # ограничиваем длину
                        "normalized": normalized[:200],
                        "corrections": corrections,
                        "corrections_count": len(corrections)
                    },
                    "sessionId": "normalization",
                    "runId": "normalization",
                    "hypothesisId": "A"
                }, ensure_ascii=False) + "\n")
        except:
            pass

    return normalized, corrections

