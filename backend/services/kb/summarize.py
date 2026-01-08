"""
Тезисное резюме найденных документов.
Извлекает релевантные предложения без использования LLM.
"""
import re
from typing import List, Dict, Any


def summarize_to_bullets(query: str, hits: List[Dict[str, Any]], max_bullets: int = 7) -> List[str]:
    """
    Извлекает релевантные предложения из результатов поиска.
    
    Args:
        query: поисковый запрос
        hits: результаты поиска (из search.py)
        max_bullets: максимальное количество тезисов
        
    Returns:
        Список тезисов (предложений)
    """
    # Извлекаем ключевые слова из запроса
    keywords = set(re.findall(r'\b\w+\b', query.lower()))
    
    # Если нет ключевых слов, возвращаем первые предложения
    if not keywords:
        return extract_first_sentences(hits, max_bullets)
    
    bullets = []
    seen_sentences = set()  # Чтобы не дублировать предложения
    
    # Проходим по результатам поиска в порядке релевантности
    for hit in hits:
        text = hit.get("text", "")
        
        # Разбиваем на предложения
        sentences = re.split(r'[.!?]\s+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            
            # Пропускаем слишком короткие или длинные предложения
            if len(sentence) < 30 or len(sentence) > 300:
                continue
            
            # Пропускаем дубликаты
            sentence_lower = sentence.lower()
            if sentence_lower in seen_sentences:
                continue
            
            # Подсчитываем совпадения ключевых слов
            sentence_words = set(re.findall(r'\b\w+\b', sentence_lower))
            overlap = len(keywords & sentence_words)
            
            # Если есть совпадения, добавляем предложение
            if overlap >= 1:
                bullets.append(sentence)
                seen_sentences.add(sentence_lower)
            
            # Останавливаемся при достижении лимита
            if len(bullets) >= max_bullets:
                break
        
        if len(bullets) >= max_bullets:
            break
    
    # Если не набрали достаточно тезисов, добавляем первые предложения
    if len(bullets) < max_bullets:
        additional = extract_first_sentences(hits, max_bullets - len(bullets))
        for sentence in additional:
            sentence_lower = sentence.lower()
            if sentence_lower not in seen_sentences:
                bullets.append(sentence)
                seen_sentences.add(sentence_lower)
            if len(bullets) >= max_bullets:
                break
    
    return bullets[:max_bullets]


def extract_first_sentences(hits: List[Dict[str, Any]], max_count: int) -> List[str]:
    """
    Извлекает первые предложения из результатов поиска.
    
    Args:
        hits: результаты поиска
        max_count: максимальное количество предложений
        
    Returns:
        Список предложений
    """
    sentences = []
    
    for hit in hits:
        text = hit.get("text", "")
        first_sentences = re.split(r'[.!?]\s+', text)[:2]  # Берём первые 2 предложения
        
        for sentence in first_sentences:
            sentence = sentence.strip()
            if len(sentence) >= 30 and len(sentence) <= 300:
                sentences.append(sentence)
                if len(sentences) >= max_count:
                    return sentences
    
    return sentences


def format_answer(query: str, hits: List[Dict[str, Any]], max_bullets: int = 7) -> str:
    """
    Форматирует ответ с тезисами и ссылкой.
    
    Args:
        query: поисковый запрос
        hits: результаты поиска
        max_bullets: максимальное количество тезисов
        
    Returns:
        Отформатированный ответ
    """
    if not hits:
        return (
            "В подключённых базах знаний я не нашёл прямого материала по этому запросу.\n\n"
            "Можете чуть уточнить формулировку или контекст?"
        )
    
    # Извлекаем тезисы
    bullets = summarize_to_bullets(query, hits, max_bullets)
    
    if not bullets:
        return (
            f"Нашёл информацию по запросу, но не смог извлечь конкретные тезисы.\n\n"
            f"Источник: {hits[0]['url']}"
        )
    
    # Формируем ответ
    answer_parts = [
        "Я нашёл материал по вашему вопросу. Коротко по сути:",
        ""
    ]
    
    for bullet in bullets:
        answer_parts.append(f"• {bullet}")
    
    answer_parts.append("")
    
    # Добавляем ссылку на источник
    source_url = hits[0].get("url", "")
    source_title = hits[0].get("title", "")
    
    if source_url:
        answer_parts.append(f"**Источник:** [{source_title or 'Ссылка'}]({source_url})")
    
    # Если есть несколько источников, упоминаем это
    if len(hits) > 1:
        answer_parts.append(f"\n(Найдено {len(hits)} результатов, показан наиболее релевантный)")
    
    return "\n".join(answer_parts)

