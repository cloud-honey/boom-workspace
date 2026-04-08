# =============================================================================
# 파일명: wiki_ingest.py
# 역할: URL 수집 → LLM 분석 → 붐엘 Wiki 페이지 생성/업데이트 글루 코드 (P2)
# 작성: boom-developer | 2026-04-08
# =============================================================================

import asyncio
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 상수 정의
# ──────────────────────────────────────────────
WIKI_DIR = "/Users/sykim/workspace/booml-wiki"
WIKI_DB_PATH = "/Users/sykim/workspace/booml-wiki/wiki.db"
TOPICS_DIR = os.path.join(WIKI_DIR, "topics")
ENTITIES_DIR = os.path.join(WIKI_DIR, "entities")
INDEX_MD = os.path.join(WIKI_DIR, "index.md")
LOG_MD = os.path.join(WIKI_DIR, "log.md")
SCHEMA_MD = os.path.join(WIKI_DIR, "_schema.md")

LLM_BASE_URL = "http://localhost:8000"
LLM_MODEL = "gemma-4-26b-a4b-it-4bit"

# asyncio.Lock for concurrent write protection
_write_lock = asyncio.Lock()

KST = timezone(timedelta(hours=9))


def _today_kst() -> str:
    """
    Returns today's date string in KST (YYYY-MM-DD).
    Returns:
        str: Date string like "2026-04-08"
    """
    return datetime.now(KST).strftime("%Y-%m-%d")


def _now_kst() -> str:
    """
    Returns current datetime string in KST (YYYY-MM-DD HH:MM).
    Returns:
        str: Datetime string like "2026-04-08 13:45"
    """
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M")


def _load_schema_md() -> str:
    """
    Load _schema.md content for use in LLM system prompt.
    Returns:
        str: Schema file content, or empty string if not found
    """
    try:
        with open(SCHEMA_MD, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"_schema.md 로드 실패: {e}")
        return ""


def _slugify(title: str) -> str:
    """
    Convert title to filesystem-safe slug (lowercase, hyphenated).
    Args:
        title: Page title string
    Returns:
        str: Slugified filename (without .md extension)
    """
    # Convert to lowercase
    slug = title.lower()
    # Remove parentheses and their content
    slug = re.sub(r'\([^)]*\)', '', slug)
    # Replace non-alphanumeric with hyphens
    slug = re.sub(r'[^a-z0-9가-힣]+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    # Limit length
    if len(slug) > 60:
        slug = slug[:60].rstrip('-')
    return slug or "untitled"


# ──────────────────────────────────────────────
# Step 1: 중복 URL 확인
# ──────────────────────────────────────────────

def _check_duplicate_sync(url: str) -> Optional[dict]:
    """
    Synchronous DB query to check if URL already exists in wiki_pages.source_urls.
    Args:
        url: URL to check
    Returns:
        dict with keys (path, title, updated) if found, else None
    """
    try:
        conn = sqlite3.connect(WIKI_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT path, title, updated FROM wiki_pages WHERE source_urls LIKE ? LIMIT 1",
            (f"%{url}%",)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"path": row[0], "title": row[1], "updated": row[2]}
        return None
    except Exception as e:
        logger.error(f"check_duplicate_sync 실패: {e}")
        return None


async def check_duplicate(url: str) -> Optional[dict]:
    """
    Check if URL already exists in wiki.db (async wrapper).
    Args:
        url: URL string to check
    Returns:
        dict with existing page info if found, else None
    """
    return await asyncio.to_thread(_check_duplicate_sync, url)


# ──────────────────────────────────────────────
# Step 2: URL 콘텐츠 가져오기
# ──────────────────────────────────────────────

async def fetch_content(url: str) -> str:
    """
    Fetch URL content using the tool_fetch_url logic (inline reimplementation
    to avoid circular imports from server_v3_postgres_router).
    Args:
        url: HTTP/HTTPS URL to fetch
    Returns:
        str: Extracted text content with metadata header
    Raises:
        RuntimeError: on fetch failure
    """
    from html import unescape

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "Mozilla/5.0 (compatible; BoomlWikiBot/1.0)"}
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                html = await resp.text()

        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        # Extract meta description
        desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        )
        description = desc_match.group(1).strip() if desc_match else ""

        # Remove script/style tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Decode HTML entities and strip tags
        text = unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        result = f"[URL] {url}\n"
        if title:
            result += f"[Title] {title}\n"
        if description:
            result += f"[Description] {description}\n"
        result += f"\n[Content]\n{text[:12000]}"

        return result

    except asyncio.TimeoutError:
        raise RuntimeError("Request timed out (max 30 seconds)")
    except Exception as e:
        raise RuntimeError(f"fetch_content 실패: {e}")


# ──────────────────────────────────────────────
# Step 3: LLM 분석 호출
# ──────────────────────────────────────────────

def _build_system_prompt(schema_content: str) -> str:
    """
    Build system prompt for wiki page analysis LLM call.
    Args:
        schema_content: Content of _schema.md
    Returns:
        str: System prompt string
    """
    return (
        "You are a wiki page generator. Your ONLY output must be a raw JSON object.\n"
        "Do NOT use markdown code blocks. Do NOT write any text outside the JSON.\n\n"
        "Output this exact structure (fill in the values):\n"
        '{"title":"string","tags":["tag1","tag2","tag3"],"summary":"string","page_content":"string","page_type":"topic"}\n\n'
        "Field rules:\n"
        "- title: short descriptive title (Korean or English matching content)\n"
        "- tags: exactly 3-5 lowercase English single words like [\"llm\",\"ai\",\"nlp\"]\n"
        "- summary: 2-3 sentences on key insights\n"
        "- page_content: markdown with sections: ## Summary, ## Key Concepts, ## Source Notes, ## Related Pages\n"
        "- page_type: must be exactly the string 'topic' or 'entity'\n\n"
        "REMEMBER: Output ONLY the JSON object. Start your response with { and end with }."
    )


def _build_user_prompt(raw_content: str, existing_page: Optional[str] = None) -> str:
    """
    Build user prompt for LLM analysis.
    Args:
        raw_content: Fetched URL content
        existing_page: Existing markdown page content for update mode
    Returns:
        str: User prompt string
    """
    if existing_page:
        return (
            "EXISTING WIKI PAGE (to be updated/merged):\n"
            f"{existing_page}\n\n"
            "NEW SOURCE CONTENT (merge this into the existing page):\n"
            f"{raw_content}\n\n"
            "Instructions:\n"
            "1. Merge the new information into the existing page (do NOT just append)\n"
            "2. Update the summary with new insights\n"
            "3. Add a ## Change Log entry at the end of page_content\n"
            "4. Preserve existing source_urls and add the new URL\n"
            "5. Return the complete merged page as the 'page_content' field\n"
            "Return ONLY the JSON object."
        )
    else:
        return (
            f"Analyze this web content and generate a wiki page:\n\n{raw_content}\n\n"
            "Return ONLY the JSON object."
        )


def _extract_title_from_content(raw_content: str) -> str:
    """
    Extract page title from raw fetched content.
    Args:
        raw_content: Fetched URL content text
    Returns:
        str: Best available title
    """
    title_match = re.search(r'\[Title\]\s*(.+)', raw_content)
    if title_match:
        return title_match.group(1).strip()
    return "Untitled Page"


def _normalize_tags(tags_value) -> list:
    """
    Normalize tags from various LLM output formats to a list of strings.
    Args:
        tags_value: Raw tags field from LLM (str, list, dict, etc.)
    Returns:
        list: Normalized list of lowercase string tags
    """
    if isinstance(tags_value, str):
        return [t.strip().lower() for t in tags_value.split(",") if t.strip()][:5]
    if isinstance(tags_value, list):
        normalized = []
        for t in tags_value:
            if isinstance(t, str):
                normalized.append(t.lower())
            elif isinstance(t, dict):
                # Take first string value from dict
                for v in t.values():
                    if isinstance(v, str):
                        normalized.append(v.lower())
                        break
        return normalized[:5]
    if isinstance(tags_value, dict):
        return [str(v).lower() for v in list(tags_value.values())[:5]]
    return ["general"]


def _normalize_summary(summary_value) -> str:
    """
    Normalize summary from various LLM output formats to a plain string.
    Args:
        summary_value: Raw summary field (str, dict, list)
    Returns:
        str: Plain text summary
    """
    if isinstance(summary_value, str):
        return summary_value
    if isinstance(summary_value, dict):
        parts = []
        for v in summary_value.values():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, list):
                parts.extend(str(i) for i in v)
        return " ".join(parts)
    if isinstance(summary_value, list):
        return " ".join(str(i) for i in summary_value)
    return str(summary_value)


def _parse_llm_response(response_text: str, raw_content: str) -> dict:
    """
    Robustly parse LLM response into wiki page dict.
    Handles: code blocks, partial JSON, missing fields, non-standard formats.
    Falls back to constructing fields from raw_content if LLM output is malformed.
    Args:
        response_text: Raw LLM response string
        raw_content: Original fetched URL content (for fallback)
    Returns:
        dict: Normalized wiki page fields
    Raises:
        ValueError: if title cannot be extracted at all
    """
    # Step 1: Extract JSON from code blocks or raw text
    json_text = response_text

    # Try code block extraction first
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', json_text)
    if code_block_match:
        json_text = code_block_match.group(1).strip()

    # Extract JSON object boundaries
    brace_start = json_text.find('{')
    brace_end = json_text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        json_text = json_text[brace_start:brace_end + 1]

    # Step 2: Parse JSON (may partially succeed)
    raw_result = {}
    try:
        raw_result = json.loads(json_text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 파싱 실패 (fallback 모드): {e}")
        # Try to extract key fields via regex as last resort
        title_m = re.search(r'"title"\s*:\s*"([^"]+)"', json_text)
        if title_m:
            raw_result["title"] = title_m.group(1)
        summary_m = re.search(r'"summary"\s*:\s*"([^"]+)"', json_text)
        if summary_m:
            raw_result["summary"] = summary_m.group(1)

    # Step 3: Normalize each field with fallbacks
    # title
    title = raw_result.get("title", "")
    if not title:
        title = _extract_title_from_content(raw_content)
    if not title:
        raise ValueError("title을 추출할 수 없습니다")

    # tags
    raw_tags = raw_result.get("tags")
    if raw_tags:
        tags = _normalize_tags(raw_tags)
    else:
        # Derive tags from title words
        words = re.findall(r'[a-zA-Z]+', title.lower())
        tags = [w for w in words if len(w) > 2][:5] or ["general"]

    # summary
    raw_summary = raw_result.get("summary", "")
    summary = _normalize_summary(raw_summary) if raw_summary else f"Overview of {title}."

    # page_type
    page_type = raw_result.get("page_type", "topic")
    if page_type not in ("topic", "entity"):
        page_type = "topic"

    # page_content
    page_content = raw_result.get("page_content", "")
    if not page_content or not isinstance(page_content, str):
        # Build page_content from available data
        page_content = (
            f"## Summary\n{summary}\n\n"
            "## Key Concepts\n(auto-generated from LLM analysis)\n\n"
            "## Source Notes\n- Source: (see frontmatter source_urls)\n\n"
            "## Related Pages\n(to be linked)"
        )

    return {
        "title": title,
        "tags": tags,
        "summary": summary,
        "page_content": page_content,
        "page_type": page_type,
    }


async def call_llm_analyze(
    raw_content: str,
    existing_page: Optional[str] = None,
    retry_count: int = 0
) -> dict:
    """
    Call LLM to analyze content and generate wiki page JSON.
    Retries up to 2 times on JSON parse failure.
    Args:
        raw_content: Fetched URL content
        existing_page: Existing page content for update mode
        retry_count: Current retry attempt (0-based)
    Returns:
        dict: Parsed JSON with title, tags, summary, page_content, page_type
    Raises:
        RuntimeError: if all retries fail
    """
    schema_content = _load_schema_md()
    system_prompt = _build_system_prompt(schema_content)
    user_prompt = _build_user_prompt(raw_content, existing_page)

    # On retry, add stronger instruction
    if retry_count > 0:
        system_prompt = (
            "IMPORTANT: You MUST respond with ONLY valid JSON. No text before or after. "
            "No markdown code blocks. Just the raw JSON object.\n\n"
        ) + system_prompt

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.3,
        # No tools parameter — plain chat completion
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LLM_BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    raise RuntimeError(f"LLM API error {resp.status}: {err[:200]}")
                data = await resp.json()

        response_text = data["choices"][0]["message"]["content"].strip()
        logger.info(f"LLM 응답 길이: {len(response_text)} chars")
        logger.info(f"LLM 응답 앞부분: {response_text[:200]}")

        # Parse and normalize the LLM response with robust fallbacks
        result = _parse_llm_response(response_text, raw_content)
        return result

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"JSON 파싱 실패 (retry {retry_count}): {e}")
        if retry_count < 2:
            logger.info(f"재시도 {retry_count + 1}/2...")
            return await call_llm_analyze(raw_content, existing_page, retry_count + 1)
        raise RuntimeError(f"LLM JSON 파싱 3회 모두 실패: {e}")

    except asyncio.TimeoutError:
        raise RuntimeError("LLM 호출 타임아웃 (max 120s)")


# ──────────────────────────────────────────────
# Step 4: 페이지 쓰기
# ──────────────────────────────────────────────

def _build_markdown_frontmatter(
    draft: dict,
    url: str,
    today: str,
    existing_source_urls: Optional[list] = None,
    source_count: int = 1
) -> str:
    """
    Build full markdown page with YAML frontmatter.
    Args:
        draft: LLM-generated dict (title, tags, summary, page_content, page_type)
        url: Source URL
        today: Date string (YYYY-MM-DD)
        existing_source_urls: Existing source URLs (for update mode)
        source_count: Total source count
    Returns:
        str: Complete markdown page content
    """
    title = draft.get("title", "Untitled")
    tags = draft.get("tags", [])
    summary = draft.get("summary", "")
    page_content = draft.get("page_content", "")
    page_type = draft.get("page_type", "topic")

    # Build source_urls list
    source_urls = existing_source_urls if existing_source_urls else []
    if url not in source_urls:
        source_urls.append(url)
        source_count = len(source_urls)

    # Frontmatter
    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f"tags: {json.dumps(tags, ensure_ascii=False)}\n"
        f'created: "{today}"\n'
        f'updated: "{today}"\n'
        f"source_urls: {json.dumps(source_urls, ensure_ascii=False)}\n"
        f"source_count: {source_count}\n"
        "has_numbers: false\n"
        "key_metrics: []\n"
        "token_count: 0\n"
        "parent: null\n"
        "contradiction_flag: false\n"
        "verified: false\n"
        f'page_type: "{page_type}"\n'
        "---\n\n"
        f"# {title}\n\n"
        f"{page_content}\n"
    )
    return frontmatter


def _upsert_db_sync(
    path: str,
    draft: dict,
    url: str,
    today: str,
    source_urls: list
):
    """
    Upsert wiki page record into wiki.db (synchronous).
    Args:
        path: Relative wiki path (e.g., topics/large-language-model.md)
        draft: LLM-generated dict
        url: Source URL
        today: Date string
        source_urls: List of all source URLs for this page
    """
    conn = sqlite3.connect(WIKI_DB_PATH)
    cursor = conn.cursor()

    title = draft.get("title", "Untitled")
    tags = json.dumps(draft.get("tags", []), ensure_ascii=False)
    summary = draft.get("summary", "")
    page_type = draft.get("page_type", "topic")
    source_urls_json = json.dumps(source_urls, ensure_ascii=False)

    cursor.execute("""
        INSERT INTO wiki_pages
            (path, title, tags, summary, created, updated, source_urls,
             source_count, has_numbers, key_metrics, token_count, parent,
             contradiction_flag, verified, page_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '[]', 0, NULL, 0, 0, ?)
        ON CONFLICT(path) DO UPDATE SET
            title = excluded.title,
            tags = excluded.tags,
            summary = excluded.summary,
            updated = excluded.updated,
            source_urls = excluded.source_urls,
            source_count = excluded.source_count,
            page_type = excluded.page_type
    """, (
        path, title, tags, summary, today, today,
        source_urls_json, len(source_urls), page_type
    ))

    conn.commit()
    conn.close()


async def write_page(draft: dict, url: str, mode: str = "new") -> dict:
    """
    Atomically write wiki page: file → DB → index.md → log.md.
    Args:
        draft: LLM-generated dict (title, tags, summary, page_content, page_type)
        url: Source URL
        mode: "new" or "update"
    Returns:
        dict: Result info (path, title, mode, status)
    """
    async with _write_lock:
        today = _today_kst()
        now = _now_kst()
        title = draft.get("title", "Untitled")
        page_type = draft.get("page_type", "topic")
        slug = _slugify(title)

        # Determine directory
        if page_type == "entity":
            page_dir = ENTITIES_DIR
            rel_prefix = "entities"
        else:
            page_dir = TOPICS_DIR
            rel_prefix = "topics"

        os.makedirs(page_dir, exist_ok=True)
        filename = f"{slug}.md"
        filepath = os.path.join(page_dir, filename)
        rel_path = f"{rel_prefix}/{filename}"

        # For update mode: read existing source_urls from DB
        existing_source_urls = []
        source_count = 1
        if mode == "update":
            def _get_existing_urls():
                try:
                    conn = sqlite3.connect(WIKI_DB_PATH)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT source_urls, source_count FROM wiki_pages WHERE path = ?",
                        (rel_path,)
                    )
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        return json.loads(row[0] or "[]"), row[1] or 1
                    return [], 1
                except Exception:
                    return [], 1

            existing_source_urls, source_count = await asyncio.to_thread(_get_existing_urls)

        # Merge source_urls
        merged_source_urls = list(existing_source_urls)
        if url not in merged_source_urls:
            merged_source_urls.append(url)
        total_count = len(merged_source_urls)

        # a. Write markdown file
        md_content = _build_markdown_frontmatter(
            draft, url, today,
            existing_source_urls=existing_source_urls,
            source_count=total_count
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"Wiki 파일 저장: {filepath}")

        # b. Upsert into wiki.db
        await asyncio.to_thread(
            _upsert_db_sync, rel_path, draft, url, today, merged_source_urls
        )
        logger.info(f"Wiki DB upsert: {rel_path}")

        # c. Append to index.md
        index_line = f"- [{title}]({rel_path}) `{today}`\n"
        with open(INDEX_MD, "r", encoding="utf-8") as f:
            index_content = f.read()

        # Update the section for this page type in index.md
        section_header = f"## {rel_prefix}"
        empty_marker = "_(비어 있음)_"
        recently_header = "## recently updated"

        # Update recently updated section
        if recently_header in index_content:
            # Replace empty marker or append
            if empty_marker in index_content.split(recently_header)[1].split("##")[0]:
                index_content = index_content.replace(
                    recently_header + "\n" + empty_marker,
                    recently_header + "\n" + index_line.rstrip()
                )
            else:
                # Check if already listed
                if rel_path not in index_content:
                    insert_pos = index_content.find(recently_header) + len(recently_header) + 1
                    index_content = (
                        index_content[:insert_pos]
                        + index_line
                        + index_content[insert_pos:]
                    )

        # Update type-specific section
        if section_header in index_content:
            section_start = index_content.find(section_header)
            section_text = index_content[section_start:]
            if empty_marker in section_text.split("\n")[1]:
                index_content = index_content.replace(
                    section_header + "\n" + empty_marker,
                    section_header + "\n" + index_line.rstrip()
                )
            elif rel_path not in index_content[section_start:]:
                next_section = section_text.find("\n## ", 3)
                if next_section > 0:
                    insert_at = section_start + next_section
                    index_content = (
                        index_content[:insert_at]
                        + "\n" + index_line.rstrip()
                        + index_content[insert_at:]
                    )
                else:
                    index_content += "\n" + index_line

        with open(INDEX_MD, "w", encoding="utf-8") as f:
            f.write(index_content)
        logger.info("index.md 갱신 완료")

        # d. Append to log.md
        log_entry = (
            f"\n## [{today}] {mode}: {title}\n"
            f"- type: {mode}\n"
            f"- page: {rel_path}\n"
            f"- source: {url}\n"
            f"- time: {now} KST\n"
        )
        with open(LOG_MD, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logger.info("log.md 갱신 완료")

        return {
            "status": "ok",
            "mode": mode,
            "path": rel_path,
            "title": title,
            "page_type": page_type,
            "tags": draft.get("tags", []),
            "filename": filename,
        }


# ──────────────────────────────────────────────
# 메인 진입점: ingest_url
# ──────────────────────────────────────────────

async def ingest_url(url: str) -> dict:
    """
    Main entry point: ingest a URL into the wiki.
    Flow:
        1. check_duplicate(url) → mode = "new" or "update"
        2. fetch_content(url) → raw_content
        3. call_llm_analyze(raw_content, existing_page?) → draft
        4. write_page(draft, url, mode) → result
    Args:
        url: HTTP/HTTPS URL to ingest
    Returns:
        dict: Result with status, path, title, mode
    Raises:
        Exception: on unrecoverable error
    """
    logger.info(f"[ingest] 시작: {url}")

    # 1. 중복 확인
    existing = await check_duplicate(url)
    mode = "update" if existing else "new"
    logger.info(f"[ingest] 모드: {mode} (기존={existing})")

    # 2. URL 콘텐츠 가져오기
    raw_content = await fetch_content(url)
    logger.info(f"[ingest] 콘텐츠 가져오기 완료 ({len(raw_content)} chars)")

    # 3. LLM 분석
    existing_page_content = None
    if mode == "update" and existing:
        # Read existing markdown file for merge
        existing_path = os.path.join(WIKI_DIR, existing["path"])
        try:
            with open(existing_path, "r", encoding="utf-8") as f:
                existing_page_content = f.read()
        except Exception as e:
            logger.warning(f"기존 페이지 읽기 실패 (무시): {e}")

    draft = await call_llm_analyze(raw_content, existing_page_content)
    logger.info(f"[ingest] LLM 분석 완료: title={draft.get('title')}")

    # 4. 파일/DB 쓰기
    result = await write_page(draft, url, mode)
    logger.info(f"[ingest] 완료: {result}")

    return result
