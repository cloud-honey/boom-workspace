# =============================================================================
# Filename: wiki_query.py
# Role: Wiki keyword search + LLM synthesis for read-only query (P3a)
# Author: boom-developer | 2026-04-08
# =============================================================================

import asyncio
import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
WIKI_DB_PATH = "/Users/sykim/workspace/booml-wiki/wiki.db"
WIKI_DIR = "/Users/sykim/workspace/booml-wiki"
LLM_BASE_URL = "http://localhost:8000"
LLM_MODEL = "gemma-4-26b-a4b-it-4bit"


async def _search_wiki_db(query: str) -> list[dict]:
    """
    Search wiki database for pages matching the query keyword.

    Args:
        query: Search keyword to match against title, tags, and summary

    Returns:
        List of dicts with keys: title, path, tags, summary (max 5 results)
    """
    def _search():
        try:
            conn = sqlite3.connect(WIKI_DB_PATH)
            cursor = conn.cursor()

            # Search in title, tags, or summary
            cursor.execute("""
                SELECT title, path, tags, summary
                FROM wiki_pages
                WHERE title LIKE ? OR tags LIKE ? OR summary LIKE ?
                ORDER BY updated_at DESC
                LIMIT 5
            """, (f'%{query}%', f'%{query}%', f'%{query}%'))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "title": row[0] or "Untitled",
                    "path": row[1],
                    "tags": row[2] or "",
                    "summary": row[3] or ""
                })

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Wiki DB search failed: {e}")
            return []

    return await asyncio.to_thread(_search)


async def _load_page_content(path: str) -> Optional[str]:
    """
    Load markdown content from wiki page file.

    Args:
        path: Relative path to wiki page (e.g., "topics/llm.md")

    Returns:
        Markdown content as string, or None if file doesn't exist
    """
    def _read():
        try:
            filepath = Path(WIKI_DIR) / path
            if not filepath.exists():
                logger.warning(f"Wiki page not found: {filepath}")
                return None
            return filepath.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
            return None

    return await asyncio.to_thread(_read)


async def _call_llm_with_retry(query: str, page_contents: str, max_retries: int = 2) -> str:
    """
    Call local LLM to synthesize answer based on wiki pages.

    Args:
        query: User's search query
        page_contents: Concatenated wiki page contents
        max_retries: Number of retry attempts (total attempts = max_retries + 1)

    Returns:
        LLM generated answer string

    Raises:
        Exception: If all retry attempts fail
    """
    system_prompt = (
        "You are a helpful assistant. Answer the user's question based ONLY on the "
        "provided wiki pages. If the wiki pages don't contain enough information, "
        "say so clearly. Be concise."
    )

    user_prompt = f"Question: {query}\n\nWiki pages:\n\n{page_contents}"

    request_body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7
    }

    last_error = None

    # Retry loop: max_retries=2 means 3 total attempts (0, 1, 2)
    for attempt in range(max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{LLM_BASE_URL}/v1/chat/completions",
                    json=request_body,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise Exception(f"LLM returned status {resp.status}: {error_text}")

                    data = await resp.json()
                    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                    if not answer:
                        raise Exception("LLM returned empty response")

                    return answer

        except Exception as e:
            last_error = e
            logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
            if attempt < max_retries:
                # Wait briefly before retry
                await asyncio.sleep(1)
            continue

    # All attempts failed
    raise Exception(f"LLM call failed after {max_retries + 1} attempts: {last_error}")


async def query_wiki(query: str) -> dict:
    """
    Main wiki query function: search wiki DB, load pages, and synthesize LLM answer.

    Args:
        query: User's search query string

    Returns:
        Dict with keys:
            - answer: str (LLM answer or fallback message)
            - sources: list[dict] (wiki pages used as sources)
            - wiki_found: bool (True if wiki pages were found)
            - fallback_suggested: bool (True if no wiki pages found)
            - error: str (optional, only present if error occurred)
    """
    try:
        # Step 1: Search wiki database
        logger.info(f"Searching wiki for query: '{query}'")
        search_results = await _search_wiki_db(query)

        if not search_results:
            logger.info("No wiki pages found for query")
            return {
                "answer": "Wiki에 관련 내용이 없습니다. 웹 검색을 사용하시겠습니까?",
                "sources": [],
                "wiki_found": False,
                "fallback_suggested": True
            }

        # Step 2: Load page content (limit to 3 pages to avoid context overflow)
        logger.info(f"Found {len(search_results)} wiki pages, loading content...")
        page_contents_list = []
        sources = []

        for idx, result in enumerate(search_results[:3]):  # Limit to 3 pages
            content = await _load_page_content(result["path"])
            if content:
                # Format page content for LLM
                page_header = f"--- Page {idx + 1}: {result['title']} ---\n"
                page_contents_list.append(page_header + content)

                # Add to sources list
                sources.append({
                    "title": result["title"],
                    "path": result["path"],
                    "summary": result["summary"]
                })

        if not page_contents_list:
            logger.warning("Wiki pages found in DB but no content could be loaded")
            return {
                "answer": "Wiki 페이지를 찾았으나 내용을 읽을 수 없습니다.",
                "sources": [],
                "wiki_found": False,
                "fallback_suggested": True
            }

        # Step 3: Call LLM to synthesize answer
        logger.info(f"Calling LLM with {len(page_contents_list)} pages...")
        combined_content = "\n\n".join(page_contents_list)

        try:
            answer = await _call_llm_with_retry(query, combined_content)
        except Exception as llm_error:
            logger.error(f"LLM synthesis failed: {llm_error}")
            # Return fallback with sources still available
            return {
                "answer": f"Wiki 페이지를 찾았으나 답변 생성에 실패했습니다. 페이지를 직접 확인해 주세요.",
                "sources": sources,
                "wiki_found": True,
                "fallback_suggested": False,
                "error": str(llm_error)
            }

        # Step 4: Return successful result
        logger.info("Wiki query completed successfully")
        return {
            "answer": answer,
            "sources": sources,
            "wiki_found": True,
            "fallback_suggested": False
        }

    except Exception as e:
        logger.error(f"Wiki query error: {e}")
        return {
            "error": str(e),
            "wiki_found": False,
            "sources": [],
            "fallback_suggested": False
        }
