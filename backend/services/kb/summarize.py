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
    Форматирует ответ с кратким резюме, деталями и источниками.
    
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
            "Можете уточнить формулировку или задать вопрос по-другому?"
        )
    
    # Извлекаем тезисы
    bullets = summarize_to_bullets(query, hits, max_bullets)
    
    if not bullets:
        # Если не удалось извлечь тезисы, используем первые предложения из текста
        first_hit = hits[0]
        text = first_hit.get("text", "")
        first_sentences = re.split(r'[.!?]\s+', text)[:3]
        summary = ". ".join([s.strip() for s in first_sentences if len(s.strip()) > 20])[:200]
        if summary:
            summary = summary.rstrip('.') + "."
        else:
            summary = "Нашёл информацию по вашему запросу в базе знаний."
    else:
        # Формируем краткое резюме из первых 2-3 тезисов
        summary_bullets = bullets[:3]
        summary = ". ".join([b.rstrip('.') for b in summary_bullets])[:250]
        if len(bullets) > 3:
            summary = summary.rstrip('.') + "."
        else:
            summary = summary.rstrip('.') + "."
    
    # Формируем ответ
    answer_parts = []
    
    # 1. Краткое резюме (3-4 предложения)
    answer_parts.append(summary)
    answer_parts.append("")
    
    # 2. Детали (если есть дополнительные тезисы)
    if len(bullets) > 3:
        answer_parts.append("Дополнительные детали:")
        for bullet in bullets[3:]:
            answer_parts.append(f"• {bullet}")
        answer_parts.append("")
    
    # 3. Источники (уникальные URL)
    unique_sources = []
    seen_urls = set()
    for hit in hits[:3]:  # Максимум 3 источника
        url = hit.get("url", "")
        title = hit.get("title", "") or hit.get("doc_title", "") or "Источник"
        if url and url not in seen_urls:
            unique_sources.append({"title": title, "url": url})
            seen_urls.add(url)
    
    if unique_sources:
        answer_parts.append("**Источники:**")
        for source in unique_sources:
            answer_parts.append(f"• {source['title']}: {source['url']}")
        answer_parts.append("")
    
    # 4. Предложение дальнейших действий
    answer_parts.append("Могу помочь с уточнением параметров или подбором насоса. Что ещё интересует?")
    
    return "\n".join(answer_parts)

