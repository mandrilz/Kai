"""
Индексация документов для базы знаний.
Извлекает текст из HTML, чанкует и индексирует в SQLite FTS5.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse, urlunparse
from typing import List, Tuple, Set
import time
import json
from pathlib import Path
from services.kb.db import get_conn, init_db
import os
from datetime import datetime
import re


# Константы
CHUNK_SIZE = 1000  # символов
CHUNK_OVERLAP = 150  # символов


def load_sources() -> dict:
    """
    Загружает конфигурацию источников из sources.json.
    
    Returns:
        Словарь с источниками
    """
    sources_path = Path(__file__).parent / "sources.json"
    with open(sources_path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_url(url: str) -> str:
    """
    Нормализует URL: убирает якоря, параметры запроса, приводит к каноническому виду.
    
    Args:
        url: исходный URL
        
    Returns:
        Нормализованный URL
    """
    parsed = urlparse(url)
    # Убираем fragment (#anchor)
    # Убираем query параметры для унификации
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip('/') or '/',  # Убираем trailing slash для унификации
        parsed.params,
        '',  # query всегда пустой
        ''  # fragment всегда пустой
    ))
    return normalized


def is_static_file(url: str) -> bool:
    """
    Проверяет, является ли URL статическим файлом.
    
    Args:
        url: URL для проверки
        
    Returns:
        True если это статический файл
    """
    static_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico',
        '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
        '.pdf', '.zip', '.rar', '.tar', '.gz',
        '.mp4', '.mp3', '.avi', '.mov',
        '.xml', '.json', '.txt'
    }
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    return any(path_lower.endswith(ext) for ext in static_extensions)


def is_url_allowed(url: str, source_config: dict) -> Tuple[bool, str]:
    """
    Проверяет, разрешено ли индексировать данный URL для данного источника.
    
    Args:
        url: URL для проверки
        source_config: конфигурация источника из sources.json
        
    Returns:
        (разрешено: bool, причина_отклонения: str)
    """
    # Нормализуем URL
    normalized_url = normalize_url(url)
    parsed = urlparse(normalized_url)
    
    # 1. Проверка домена
    allow_domains = source_config.get("allow_domains", [])
    # Поддержка старого формата для обратной совместимости
    if not allow_domains:
        allow_domains = source_config.get("allowed_domains", [])
    
    if not allow_domains:
        return False, "allow_domains не указан"
    
    domain_match = False
    for domain in allow_domains:
        if parsed.netloc == domain or parsed.netloc.endswith(f".{domain}"):
            domain_match = True
            break
    
    if not domain_match:
        return False, f"домен {parsed.netloc} не в allow_domains {allow_domains}"
    
    # 2. Проверка статических файлов
    if is_static_file(normalized_url):
        return False, "статический файл"
    
    # 3. Проверка include_prefixes (или entry_urls как fallback)
    include_prefixes = source_config.get("include_prefixes", [])
    if not include_prefixes:
        # Используем entry_urls как include_prefixes
        entry_urls = source_config.get("entry_urls", [])
        if not entry_urls:
            # Старый формат для обратной совместимости
            entry_urls = source_config.get("start_urls", [])
        include_prefixes = [normalize_url(u) for u in entry_urls]
    else:
        include_prefixes = [normalize_url(u) for u in include_prefixes]
    
    prefix_match = False
    for prefix in include_prefixes:
        if normalized_url.startswith(prefix):
            prefix_match = True
            break
    
    if not prefix_match:
        return False, f"URL не начинается ни с одного include_prefixes: {include_prefixes}"
    
    # 4. Проверка exclude_prefixes
    exclude_prefixes = source_config.get("exclude_prefixes", [])
    if exclude_prefixes:
        exclude_prefixes = [normalize_url(u) for u in exclude_prefixes]
        for exclude_prefix in exclude_prefixes:
            if normalized_url.startswith(exclude_prefix):
                return False, f"URL исключен по exclude_prefixes: {exclude_prefix}"
    
    return True, "OK"


def extract_text_from_html(html: str) -> Tuple[str, str]:
    """
    Извлекает текст из HTML.
    
    Args:
        html: HTML содержимое
        
    Returns:
        (title, text) - заголовок и чистый текст
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Извлекаем заголовок
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    
    # Удаляем служебные элементы
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    
    # Извлекаем основной текст
    text_parts = []
    
    # Ищем основные секции
    main_content = soup.find("main") or soup.find("article") or soup.find("body")
    
    if main_content:
        # Извлекаем текст из параграфов и заголовков
        for element in main_content.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"]):
            text = element.get_text(" ", strip=True)
            if text and len(text) > 20:  # Пропускаем очень короткие фрагменты
                text_parts.append(text)
    
    # Если ничего не нашли, извлекаем весь текст
    if not text_parts:
        text_parts.append(soup.get_text(" ", strip=True))
    
    text = " ".join(text_parts)
    
    # Очистка: удаляем лишние пробелы
    import re
    text = re.sub(r"\s+", " ", text)
    
    return title, text


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Разбивает текст на чанки с перекрытием.
    
    Args:
        text: текст для разбивки
        size: размер чанка (символов)
        overlap: перекрытие между чанками
        
    Returns:
        Список чанков
    """
    if len(text) <= size:
        return [text]
    
    chunks = []
    i = 0
    
    while i < len(text):
        chunk = text[i:i + size]
        
        # Пытаемся закончить на границе предложения
        if i + size < len(text):
            # Ищем последнюю точку/восклицательный/вопросительный знак
            last_punct = max(
                chunk.rfind("."),
                chunk.rfind("!"),
                chunk.rfind("?")
            )
            if last_punct > size * 0.5:  # Если знак не слишком близко к началу
                chunk = chunk[:last_punct + 1]
                i += last_punct + 1
            else:
                i += size - overlap
        else:
            i += size - overlap
        
        if chunk.strip():
            chunks.append(chunk.strip())
    
    return chunks if chunks else [text]


def upsert_doc(url: str, title: str, source_id: str, chunks: List[str]) -> int:
    """
    Сохраняет документ и его чанки в БД.
    
    Args:
        url: URL документа
        title: заголовок
        source_id: ID источника
        chunks: список текстовых чанков
        
    Returns:
        ID документа в БД
    """
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Вставляем или обновляем документ
        cur.execute("""
            INSERT INTO kb_docs (url, title, source_id, fetched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = excluded.title,
                source_id = excluded.source_id,
                fetched_at = excluded.fetched_at
        """, (url, title, source_id, datetime.now().isoformat()))
        
        # Получаем ID документа
        cur.execute("SELECT id FROM kb_docs WHERE url = ?", (url,))
        doc_row = cur.fetchone()
        doc_id = doc_row["id"] if doc_row else None
        
        if not doc_id:
            raise ValueError(f"Не удалось получить ID документа для {url}")
        
        # Удаляем старые чанки этого документа
        # Сначала получаем chunk_id для удаления из FTS5
        cur.execute("SELECT id FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        old_chunk_ids = [row["id"] for row in cur.fetchall()]
        
        # Удаляем из FTS5
        if old_chunk_ids:
            placeholders = ",".join("?" * len(old_chunk_ids))
            cur.execute(f"DELETE FROM kb_chunks_fts WHERE chunk_id IN ({placeholders})", old_chunk_ids)
        
        # Удаляем из kb_chunks
        cur.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        
        # Вставляем новые чанки
        for idx, chunk in enumerate(chunks):
            # Вставляем в kb_chunks
            cur.execute("""
                INSERT INTO kb_chunks (doc_id, chunk_index, text)
                VALUES (?, ?, ?)
            """, (doc_id, idx, chunk))
            
            chunk_id = cur.lastrowid
            
            # Вставляем в FTS5 (храним chunk_id для связи с kb_chunks)
            cur.execute("""
                INSERT INTO kb_chunks_fts (chunk_id, title, text)
                VALUES (?, ?, ?)
            """, (chunk_id, title, chunk))
        
        conn.commit()
        return doc_id
    
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def crawl_url(url: str, source_config: dict, visited: Set[str], max_depth: int, current_depth: int = 0) -> List[str]:
    """
    Рекурсивный краулинг URL с ограничением глубины.
    
    Args:
        url: URL для обработки
        source_config: конфигурация источника
        visited: множество посещённых URL
        max_depth: максимальная глубина
        current_depth: текущая глубина
        
    Returns:
        Список найденных URL для дальнейшего обхода
    """
    # Нормализуем URL для проверки
    normalized_url = normalize_url(url)
    
    if normalized_url in visited or current_depth > max_depth:
        return []
    
    # Проверяем, разрешён ли URL для этого источника
    allowed, reason = is_url_allowed(normalized_url, source_config)
    if not allowed:
        if current_depth == 0:
            # На стартовом уровне логируем отклонение
            print(f"[{current_depth}] Пропущен: {url} - {reason}")
        return []
    
    visited.add(normalized_url)
    found_urls = []
    
    try:
        # Задержка между запросами
        crawl_delay_ms = source_config.get("crawl_delay_ms", 1000)
        crawl_delay = crawl_delay_ms / 1000.0  # Конвертируем в секунды
        # Fallback на старый формат
        if crawl_delay_ms == 1000 and "crawl_delay" in source_config:
            crawl_delay = source_config.get("crawl_delay", 1.0)
        
        time.sleep(crawl_delay)
        
        # Получаем HTML
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        
        # Извлекаем текст
        title, text = extract_text_from_html(response.text)
        
        # Чанкуем текст
        chunks = chunk_text(text)
        
        # Сохраняем в БД
        source_id = source_config.get("id", "unknown")
        doc_id = upsert_doc(url, title, source_id, chunks)
        
        print(f"[{current_depth}] Индексирован: {url} ({len(chunks)} чанков) - {title[:50]}")
        
        # Если не достигли максимальной глубины, ищем ссылки
        if current_depth < max_depth:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for link in soup.find_all("a", href=True):
                href = link.get("href")
                absolute_url = urljoin(url, href)
                
                # Нормализуем найденный URL
                clean_url = normalize_url(absolute_url)
                
                # Проверяем, разрешён ли этот URL для индексации
                link_allowed, link_reason = is_url_allowed(clean_url, source_config)
                
                if link_allowed and clean_url not in visited:
                    found_urls.append(clean_url)
                elif not link_allowed and current_depth < 2:
                    # Логируем отклонение только на первых уровнях (чтобы не засорять логи)
                    pass  # Можно раскомментировать для отладки: print(f"  Пропущена ссылка: {clean_url} - {link_reason}")
        
        return found_urls
    
    except Exception as e:
        print(f"Ошибка при обработке {url}: {e}")
        return []


def rebuild_index():
    """
    Перестраивает весь индекс базы знаний.
    """
    print("Начинаю переиндексацию базы знаний...")
    
    # Инициализируем БД
    init_db()
    
    # Очищаем старые данные
    from services.kb.db import clear_db
    clear_db()
    
    # Загружаем источники
    sources_config = load_sources()
    sources = sources_config.get("sources", [])
    
    total_docs = 0
    
    for source_config in sources:
        # Пропускаем отключенные источники
        if not source_config.get("enabled", True):
            print(f"\nПропущен источник (enabled=false): {source_config.get('id', 'unknown')}")
            continue
        
        source_id = source_config.get("id", "unknown")
        source_title = source_config.get("title", source_config.get("name", source_id))
        print(f"\nОбрабатываю источник: {source_id} ({source_title})")
        
        # Получаем стартовые URL (поддерживаем оба формата для обратной совместимости)
        entry_urls = source_config.get("entry_urls", [])
        if not entry_urls:
            entry_urls = source_config.get("start_urls", [])
        
        if not entry_urls:
            print(f"  Нет entry_urls для источника {source_id}")
            continue
        
        max_depth = source_config.get("max_depth", 2)
        max_pages = source_config.get("max_pages", 1000)
        visited = set()
        
        # Добавляем entry_urls в очередь, предварительно проверив их
        urls_to_process = []
        for entry_url in entry_urls:
            normalized_entry = normalize_url(entry_url)
            allowed, reason = is_url_allowed(normalized_entry, source_config)
            if allowed:
                urls_to_process.append(normalized_entry)
            else:
                print(f"  Предупреждение: entry_url {entry_url} не прошел фильтр: {reason}")
        
        if not urls_to_process:
            print(f"  Нет валидных entry_urls для источника {source_id}")
            continue
        
        page_count = 0
        while urls_to_process and page_count < max_pages:
            url = urls_to_process.pop(0)
            
            if url in visited:
                continue
            
            found_urls = crawl_url(url, source_config, visited, max_depth)
            
            # Добавляем найденные URL в очередь
            for found_url in found_urls:
                if found_url not in visited and found_url not in urls_to_process:
                    urls_to_process.append(found_url)
            
            page_count += 1
            total_docs += 1
    
    print(f"\nПереиндексация завершена. Всего документов: {total_docs}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rebuild":
        rebuild_index()
    else:
        print("Использование: python -m services.kb.indexer rebuild")

