# =============================================================================
# File: wiki_synthesize.py
# Role: Wiki page synthesis logic - combine multiple wiki pages into one
# Author: boom-developer | 2026-04-08
# =============================================================================

import asyncio
import json
import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
import aiohttp

logger = logging.getLogger(__name__)

# Constants
WIKI_DB_PATH = "/Users/sykim/workspace/booml-wiki/wiki.db"
WIKI_DIR = "/Users/sykim/workspace/booml-wiki"
TOPICS_DIR = "/Users/sykim/workspace/booml-wiki/topics"
INDEX_MD = "/Users/sykim/workspace/booml-wiki/index.md"
LOG_MD = "/Users/sykim/workspace/booml-wiki/log.md"
LLM_BASE_URL = "http://localhost:8000"
LLM_MODEL = "gemma-4-26b-a4b-it-4bit"
KST = timezone(timedelta(hours=9))

# Write lock for atomic operations
_write_lock = asyncio.Lock()


async def search_related_pages(topic: str) -> list[dict]:
    """
    Search wiki pages related to the given topic.

    Args:
        topic: The topic to search for

    Returns:
        List of dicts containing {title, path, tags, summary} for top 5 matches
    """
    def _search():
        conn = sqlite3.connect(WIKI_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Search in title, tags, and summary
        search_pattern = f"%{topic}%"
        cursor.execute("""
            SELECT title, path, tags, summary
            FROM wiki_pages
            WHERE title LIKE ? OR tags LIKE ? OR summary LIKE ?
            ORDER BY updated DESC
            LIMIT 5
        """, (search_pattern, search_pattern, search_pattern))

        rows = cursor.fetchall()
        conn.close()

        # Convert to list of dicts
        return [dict(row) for row in rows]

    try:
        results = await asyncio.to_thread(_search)
        logger.info(f"Found {len(results)} related pages for topic: {topic}")
        return results
    except Exception as e:
        logger.error(f"Error searching related pages: {e}")
        return []


async def load_pages_content(pages: list[dict]) -> list[dict]:
    """
    Load full markdown content for the given wiki pages.

    Args:
        pages: List of page dicts with 'path' field

    Returns:
        List of dicts containing {title, path, summary, content}
    """
    async def _load_one(page: dict) -> dict | None:
        file_path = Path(WIKI_DIR) / page["path"]

        def _read():
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                return None
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

        try:
            content = await asyncio.to_thread(_read)
            if content is None:
                return None

            return {
                "title": page["title"],
                "path": page["path"],
                "summary": page.get("summary", ""),
                "content": content
            }
        except Exception as e:
            logger.error(f"Error loading page {page['path']}: {e}")
            return None

    # Load up to 5 pages
    tasks = [_load_one(page) for page in pages[:5]]
    results = await asyncio.gather(*tasks)

    # Filter out None values
    loaded = [r for r in results if r is not None]
    logger.info(f"Loaded content for {len(loaded)} pages")
    return loaded


async def generate_synthesis_draft(topic: str, pages: list[dict]) -> str:
    """
    Generate synthesis draft by calling LLM with source pages content.

    Args:
        topic: The synthesis topic
        pages: List of page dicts with 'title' and 'content' fields

    Returns:
        Generated markdown string
    """
    # Build context from pages (limit total to 8000 chars to avoid overflow)
    context_parts = []
    total_chars = 0

    for page in pages:
        title = page["title"]
        content = page["content"]

        # Truncate if needed
        available = 8000 - total_chars
        if available <= 0:
            break

        if len(content) > available:
            content = content[:available] + "..."

        context_parts.append(f"## Source: {title}\n\n{content}\n\n")
        total_chars += len(context_parts[-1])

    context = "".join(context_parts)

    # Prepare LLM request
    system_prompt = (
        "You are a knowledge synthesis assistant. Create a comprehensive, well-structured markdown wiki page "
        "by synthesizing the provided source pages. The page must follow this exact format:\n\n"
        "# {Title}\n\n"
        "## 개요\n"
        "{summary paragraph}\n\n"
        "## 핵심 내용\n"
        "{bullet points}\n\n"
        "## 출처\n"
        "{list of source page titles}\n\n"
        "---\n"
        "*합성 생성: {date}*"
    )

    user_prompt = f"Topic to synthesize: {topic}\n\nSource pages:\n\n{context}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.7
    }

    # Retry logic (max 2 retries)
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{LLM_BASE_URL}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=150)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"LLM API error {resp.status}: {error_text}")

                    data = await resp.json()
                    draft = data["choices"][0]["message"]["content"]
                    logger.info(f"Generated synthesis draft ({len(draft)} chars)")
                    return draft

        except Exception as e:
            logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise
            await asyncio.sleep(2)

    raise Exception("Failed to generate synthesis draft after 3 attempts")


async def save_synthesis(topic: str, draft: str, source_paths: list[str]) -> dict:
    """
    Save the synthesis page to disk and database.

    Args:
        topic: The synthesis topic
        draft: The generated markdown content
        source_paths: List of source page paths

    Returns:
        Dict with {status, path, title, source_count}
    """
    # Generate slug from topic
    slug = re.sub(r'[^a-z0-9-]', '', topic.lower().replace(' ', '-').replace('/', '-'))
    if not slug:
        slug = "synthesis"

    # File path
    filename = f"synthesis-{slug}.md"
    rel_path = f"topics/{filename}"
    full_path = Path(TOPICS_DIR) / filename

    # Extract tags from topic words
    tags = [word for word in topic.lower().split() if len(word) >= 2]

    # Extract summary: first non-empty line after "## 개요" or first 150 chars
    summary = ""
    lines = draft.split('\n')
    found_overview = False
    for line in lines:
        if found_overview and line.strip():
            summary = line.strip()[:150]
            break
        if line.strip().startswith("## 개요"):
            found_overview = True

    if not summary:
        # Fallback: use first 150 chars
        summary = draft[:150].replace('\n', ' ').strip()

    # Extract title from draft (first # line)
    title = topic
    for line in lines:
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break

    # Current timestamp
    now = datetime.now(KST).isoformat()
    date_str = datetime.now(KST).strftime("%Y-%m-%d")

    async with _write_lock:
        def _write_file():
            # Ensure topics dir exists
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(draft)

        def _upsert_db():
            conn = sqlite3.connect(WIKI_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO wiki_pages
                (path, title, tags, summary, created, updated, source_urls, source_count, page_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rel_path,
                title,
                json.dumps(tags),
                summary,
                now,
                now,
                json.dumps(source_paths),
                len(source_paths),
                'synthesis'
            ))
            conn.commit()
            conn.close()

        def _append_index():
            with open(INDEX_MD, 'a', encoding='utf-8') as f:
                f.write(f"\n- [{title}]({rel_path}) — {summary[:80]} (합성 {date_str})")

        def _append_log():
            with open(LOG_MD, 'a', encoding='utf-8') as f:
                f.write(
                    f"\n## {now} KST\n"
                    f"- **합성**: {title}\n"
                    f"- 출처: {len(source_paths)}개 페이지\n"
                    f"- 경로: {rel_path}\n"
                )

        # Execute writes atomically in order
        try:
            await asyncio.to_thread(_write_file)
            await asyncio.to_thread(_upsert_db)
            await asyncio.to_thread(_append_index)
            await asyncio.to_thread(_append_log)

            logger.info(f"Saved synthesis page: {rel_path}")

            return {
                "status": "saved",
                "path": rel_path,
                "title": title,
                "source_count": len(source_paths)
            }

        except Exception as e:
            logger.error(f"Error saving synthesis: {e}")
            raise


async def prepare_synthesis(topic: str) -> dict:
    """
    Main function to prepare synthesis draft from related wiki pages.
    Does NOT save - returns draft for user confirmation.

    Args:
        topic: The topic to synthesize

    Returns:
        Dict with {synthesis_id, topic, draft, source_pages, source_count}
        or {error, message} on failure
    """
    # Step 1: Search related pages
    pages = await search_related_pages(topic)

    if not pages:
        return {
            "error": "no_wiki_pages",
            "message": "Wiki에 관련 페이지가 없습니다. 먼저 /ingest로 페이지를 수집하세요."
        }

    # Step 2: Load page content
    pages_with_content = await load_pages_content(pages)

    if not pages_with_content:
        return {
            "error": "no_content",
            "message": "페이지 내용을 읽을 수 없습니다."
        }

    # Step 3: Generate synthesis draft
    try:
        draft = await generate_synthesis_draft(topic, pages_with_content)
    except Exception as e:
        logger.error(f"Error generating synthesis: {e}")
        return {
            "error": "generation_failed",
            "message": f"합성 생성 실패: {str(e)}"
        }

    # Step 4: Generate synthesis ID and prepare response
    synthesis_id = str(uuid.uuid4())[:8]

    # Extract source pages info (title + path)
    source_pages = [
        {"title": p["title"], "path": p["path"]}
        for p in pages_with_content
    ]

    return {
        "synthesis_id": synthesis_id,
        "topic": topic,
        "draft": draft,
        "source_pages": source_pages,
        "source_count": len(source_pages)
    }
