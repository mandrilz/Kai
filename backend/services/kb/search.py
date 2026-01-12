"""
Поиск по базе знаний через SQLite FTS5.
"""
from services.kb.db import get_conn
from typing import List, Dict, Any
import re


def search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Выполняет полнотекстовый поиск по базе знаний.
    
    Args:
        query: поисковый запрос
        limit: максимальное количество результатов
        
    Returns:
        Список словарей с результатами:
        [
            {
                "url": "...",
                "title": "...",
                "source_id": "...",
                "text": "...",
                "score": float
            },
            ...
        ]
    """
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Нормализуем запрос для FTS5
        # FTS5 поддерживает операторы: AND, OR, NOT, кавычки для фраз
        # Убираем специальные символы и формируем простой запрос
        fts_query = normalize_fts_query(query)
        
        # Используем BM25 для ранжирования
        # bm25(table, title_weight, text_weight) - больше вес = выше релевантность
        # Здесь title_weight=5.0 означает, что совпадения в заголовке важнее чем в тексте
        sql = """
        SELECT
            kb_docs.url,
            kb_docs.title,
            kb_docs.source_id,
            kb_chunks.text,
            bm25(kb_chunks_fts, 5.0, 1.0) AS score
        FROM kb_chunks_fts
        JOIN kb_chunks ON kb_chunks_fts.chunk_id = kb_chunks.id
        JOIN kb_docs ON kb_chunks.doc_id = kb_docs.id
        WHERE kb_chunks_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """
        
        cur.execute(sql, (fts_query, limit))
        results = []
        
        for row in cur.fetchall():
            results.append({
                "url": row["url"],
                "title": row["title"],
                "source_id": row["source_id"],
                "text": row["text"],
                "score": row["score"]
            })
        
        return results
    
    except Exception as e:
        # Если поиск не удался, логируем и возвращаем пустой список
        import json
        import os
        from datetime import datetime
        log_path = os.getenv("DEBUG_LOG_PATH", "/var/www/kai/.cursor/debug.log")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "location": "kb/search.py:search",
                    "message": "Search error",
                    "error": str(e),
                    "query": query,
                    "sessionId": "search",
                    "runId": "search",
                    "hypothesisId": "ERROR"
                }) + "\n")
        except:
            pass
        
        return []
    
    finally:
        conn.close()


def normalize_fts_query(query: str) -> str:
    """
    Нормализует поисковый запрос для FTS5.
    
    FTS5 поддерживает:
    - Простые слова: "word"
    - Фразы в кавычках: "exact phrase"
    - Операторы: AND, OR, NOT
    - Префиксы: word*
    
    Args:
        query: исходный запрос
        
    Returns:
        Нормализованный запрос для FTS5
    """
    # Убираем специальные символы FTS5, которые могут сломать запрос
    # Но оставляем операторы AND, OR, NOT
    query = query.strip()
    
    # Если запрос пустой, возвращаем пустую строку
    if not query:
        return ""
    
    # Если запрос уже содержит операторы FTS5, используем его как есть (осторожно)
    if any(op in query.upper() for op in [" AND ", " OR ", " NOT ", '"']):
        return query
    
    # Простой запрос: каждое слово ищем через AND
    # Разбиваем на слова и соединяем через AND
    words = re.findall(r'\b\w+\b', query)
    
    if not words:
        return query
    
    # Объединяем слова через AND (все слова должны быть в результате)
    # Можно использовать OR для более мягкого поиска
    return " AND ".join(words)


def search_best_match(query: str) -> Dict[str, Any] | None:
    """
    Возвращает лучший результат поиска.
    
    Args:
        query: поисковый запрос
        
    Returns:
        Лучший результат или None
    """
    results = search(query, limit=1)
    return results[0] if results else None

