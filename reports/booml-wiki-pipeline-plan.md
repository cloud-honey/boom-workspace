# 붐엘 Wiki 파이프라인 — 구현 기획안 v6

> 작성일: 2026-04-08  
> 최종 수정: 2026-04-08 v6 (GPT + DeepSeek + Gemini + Opus 4사 교차검증 최종)  
> 상태: 구현 즉시 착수 가능  
> 참조: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## 한 줄 결론 (v6 — 최종)

아키텍처 비전은 맞다.  
**"SQLite 단일 진실 소스 + glue 코드 제어 + fetch_url 콘텐츠 충분히 + LLM은 분석만"** 이 핵심이다.  
MVP = P0 + P1 + P3a(간소화) 2일. 나머지는 이후 순차 추가.

---

## 기존 문제

```
현재:  /crawl [URL] → raw/*.md 저장 (끝)
목표:  /crawl [URL] → DB 등록 + wiki page 생성
                    → /query → 답변 → 사용자 확인 → synthesis/ 저장
```

---

## 핵심 아키텍처 결정 (v6 — 4사 교차검증 최종)

| 결정 사항 | 이전 | v6 | 근거 |
|---------|-------|-----|------|
| P1 POC 방식 | 코드 0줄 | **최소 glue 코드 50줄** | 다중 툴 순차 루프 미구현 (DeepSeek) |
| 관련 페이지 탐색 | index 직접 읽기 | **SQLite 전용 툴 검색** | 컨텍스트 절약 + 정확도 (DeepSeek) |
| current_context.md | v5에 추가됨 | **제거** | DeepSeek SQLite 방식과 설계 충돌 (Opus) |
| SQLite 단일 소스 | 불명확 | **wiki.db = 진실 소스, index.md = 파생 뷰** | 트랜잭션 원자성 해소 (Opus) |
| SQLite 도입 시점 | P5 | **P1 즉시** | memory_store.py 이미 있음 (DeepSeek) |
| DB 구조 | 불명확 | **wiki.db 독립 파일** (memory_store SQLite와 분리) | DB 3개 혼재 방지 (Opus) |
| fetch_url 제한 | 3,000자 (하드코딩) | **15,000자 이상으로 상향** | wiki pipeline 근본 병목 (Opus) |
| LLM 응답 포맷 | 미명세 | **JSON 스키마 명세 + 파싱 실패 2회 재시도** | structured output 신뢰도 (Opus) |
| synthesis 저장 | LLM 자율 | **사용자 확인 = 즉시 정식 편입** | verified 이중 확인 제거 (Opus) |
| /wiki-verify | 별도 명령 | **MVP에서 제거** — batch ingest 시 재도입 | 사용성 저하 방지 (Opus) |
| 재수집 처리 | append | **merge + Change Log** | 중복 방지 (DeepSeek) |
| 파일 동시 쓰기 | 없음 | **asyncio.Lock / filelock** | 운영 안정성 (DeepSeek) |
| /query fallback | 없음 | **wiki 없으면 web search 제안** | 사용자 경험 (DeepSeek) |
| index.md 갱신 실패 | critical | **/lint --rebuild-index로 복구** | 원자성 해소 (Opus) |
| MVP 범위 | P0~P3b | **P0 + P1 + P3a(간소화)만** | 2일 안에 완성 가능한 범위 (Opus) |

---

## Wiki 구조

```
/Users/sykim/workspace/booml-wiki/
  _schema.md              # LLM 생성 규칙 + golden example 2~3개
  index.md                # ⚠️ 파생 뷰(View) — DB에서 재생성 가능, 사람이 읽는 용
  log.md                  # chronological 기록 (human용)
  topics/                 # 주제별 wiki page
  entities/               # 인물/조직/제품별 page
  sources/                # 원본 소스 참고용
  synthesis/              # 종합 분석 page (사용자 확인 후 즉시 정식 편입)
  wiki.db                 # ✅ 단일 진실 소스 — 모든 검색/링크/lint 기준
```

**설계 원칙 (Opus):**
- `wiki.db` = 단일 진실 소스(Source of Truth)
- `index.md` = DB에서 재생성 가능한 파생 뷰 → 갱신 실패해도 `/lint --rebuild-index`로 복구
- `index.json`, `current_context.md` 제거 — SQLite 툴 검색으로 통일

**DB 분리 원칙 (Opus):**
- `wiki.db` — wiki 전용 (새로 생성)
- `memory_store.py의 booml_memory.db` — 기존 대화 메모리 (건드리지 않음)
- `PostgreSQL` — 기존 KPI/통계 (건드리지 않음)

---

## SQLite 스키마 (P1 즉시 구축)

```sql
CREATE TABLE wiki_pages (
  path        TEXT PRIMARY KEY,         -- topics/llm-wiki-pattern.md
  title       TEXT NOT NULL,
  tags        TEXT NOT NULL,            -- JSON array: ["llm","wiki"]
  summary     TEXT,                     -- 3줄 이내 요약
  created     TEXT NOT NULL,
  updated     TEXT NOT NULL,
  source_urls TEXT,                     -- JSON array
  source_count INTEGER DEFAULT 0,
  has_numbers BOOLEAN DEFAULT FALSE,
  key_metrics TEXT,                     -- JSON array: ["accuracy","latency"]
  token_count INTEGER DEFAULT 0,
  parent      TEXT,                     -- split된 경우 parent page
  contradiction_flag BOOLEAN DEFAULT FALSE,
  verified    BOOLEAN DEFAULT FALSE,    -- 사용자가 /wiki-verify로 컨펌한 경우만 TRUE
  page_type   TEXT DEFAULT 'topic'      -- 'topic'|'entity'|'synthesis'
);

CREATE INDEX idx_tags ON wiki_pages(tags);
CREATE INDEX idx_updated ON wiki_pages(updated);
CREATE INDEX idx_has_numbers ON wiki_pages(has_numbers);
CREATE INDEX idx_contradiction ON wiki_pages(contradiction_flag);
```

---

## Opus 지적 — fetch_url 콘텐츠 제한 상향 (즉시 수정 필요)

서버 코드 657번째 줄: `result += f"\n[Content Preview]\n{text[:3000]}"`

**3,000자 = wiki pipeline의 근본 병목.** 일반 웹페이지 본문의 극히 일부만 전달.

```python
# server_v3_postgres_router.py L657 수정
# 변경 전
result += f"\n[Content Preview]\n{text[:3000]}"

# 변경 후
MAX_WIKI_CONTENT = 15000  # wiki ingest용
result += f"\n[Content]\n{text[:MAX_WIKI_CONTENT]}"
```

긴 문서(15,000자 초과): glue 코드에서 청크 분할 후 순차 처리.

---

## LLM 응답 포맷 명세 (v6 신규)

glue 코드가 파싱할 JSON 스키마 + 재시도 로직:

```python
# wiki_ingest.py 내 LLM 호출 + 파싱
INGEST_RESPONSE_SCHEMA = {
    "title": "string",
    "tags": ["string"],        # 3~5개
    "summary": "string",       # 3줄 이내
    "page_content": "string"   # 전체 markdown 내용
}

async def llm_analyze_with_retry(raw_content: str, mode: str, max_retry=2):
    for attempt in range(max_retry + 1):
        response = await call_llm(raw_content, mode)
        try:
            parsed = parse_json_response(response)
            validate_schema(parsed, INGEST_RESPONSE_SCHEMA)
            return parsed
        except (JSONDecodeError, ValidationError) as e:
            if attempt == max_retry:
                raise WikiIngestError(f"LLM 응답 파싱 실패 {max_retry+1}회: {e}")
            # 재시도 시 "JSON으로만 응답하라" 강조 프롬프트 추가
```

---

## Wiki 전용 툴 (server_v3에 추가)

LLM이 index.md/index.json을 직접 읽지 않고 이 툴을 호출:

```python
tool_search_wiki_by_tag(tag: str) -> list[dict]
# SELECT path, title, summary FROM wiki_pages WHERE tags LIKE '%tag%'

tool_search_wiki_by_keyword(keyword: str) -> list[dict]  
# SELECT path, title, summary FROM wiki_pages WHERE title LIKE '%keyword%' OR summary LIKE '%keyword%'

tool_get_wiki_page(path: str) -> str
# read_file 대신 — DB 메타데이터 + 파일 내용 반환

tool_check_url_exists(url: str) -> dict
# SELECT path, updated FROM wiki_pages WHERE source_urls LIKE '%url%'
# 중복 ingest 감지용
```

---

## Phase 구분 (v4 최종)

| Phase | 내용 | 핵심 산출물 |
|-------|------|-----------|
| P0 | Wiki 디렉토리 + _schema + index.md + log.md | 구조 초기화 |
| P1 | SQLite 스키마 + wiki 전용 툴 4개 + glue 코드 | DB 기반 검색 동작 |
| P2 | /ingest 명령 코드화 (atomicity + 파일 락) | 단일 URL ingest 완성 |
| P3a | /query read-only (fallback 포함) | wiki 기반 답변 |
| P3b | /synthesize (사용자 확인 후 저장) | 조건부 synthesis |
| P4 | /lint (DB 기반 경량, O(N)) | 품질 유지 |
| P5 | PostgreSQL 마이그레이션 (필요 시) | 확장성 |

---

## P1 POC — 최소 glue 코드 방식 (v4 핵심 변경)

**v3 문제:** 코드 0줄로 다중 툴 순차 루프 → 붐엘에 에이전트 루프 미구현, 거의 확실히 실패.

**v4 방식:** 50줄 glue 코드로 워크플로우 구성, LLM은 분석/생성만 담당.

```python
# wiki_ingest.py (글루 코드 ~50줄)
async def ingest_url(url: str):
    # 1. URL 중복 체크 (DB)
    existing = db.query("SELECT path FROM wiki_pages WHERE source_urls LIKE ?", f"%{url}%")
    mode = "update" if existing else "new"
    
    # 2. 원문 fetch (tool_fetch_url 직접 호출)
    raw = await tool_fetch_url(url)
    
    # 3. LLM에게 분석만 요청 (write 없음)
    #    → title, tags, summary, page_content 생성
    draft = await llm_analyze(raw, mode=mode)
    
    # 4. 글루 코드가 write 순서 제어
    write_page(draft)           # step1: page 파일
    db.upsert(draft)            # step2: SQLite
    update_index_md(draft)      # step3: index.md
    append_log(url, mode)       # step4: log.md
```

**텔레그램에서:** `/test_ingest [URL]` 명령으로 수동 테스트.

---

## Ingest 워크플로우 (P2 코드화)

```
1. /ingest [URL]
2. tool_check_url_exists(url) → 중복 체크
   → 있으면 "업데이트 모드", 없으면 "신규 모드"

3. tool_fetch_url(url) → 원문 수집

4. 관련 페이지 탐색 (컨텍스트 절약):
   - LLM이 tool_search_wiki_by_tag(tag) 호출
   - shortlist 5~10개 → tool_get_wiki_page() 로 내용 로드

5. LLM 분석 (draft 생성만):
   - title, tags(3~5개), summary(3줄), page_content 생성
   - 신규: 새 page draft
   - 업데이트: 기존 내용과 merge + ## Change Log에 변경 기록
   - 모순 발견: ## Contradictions 즉시 append + contradiction_flag=TRUE

6. 글루 코드가 순서 보장 (파일 락):
   a. asyncio.Lock 획득
   b. wiki page 파일 write
   c. SQLite upsert
   d. index.md 갱신
   e. log.md append
   f. Lock 해제

7. 실패 복구:
   - 파일 있는데 DB에 없음 → /lint --repair 로 재등록
```

### 재수집 처리 (merge 방식)

```
동일 URL 재수집:
  1. 기존 page 읽기 + 새 원문 읽기
  2. LLM에게: "기존 내용과 새 내용을 비교해서 중복 제거 후 통합된 섹션 생성"
  3. ## Change Log에 기록:
     ### [2026-04-10] re-ingest
     - 변경: (새로 추가/수정된 내용 요약)
  4. updated 날짜 갱신
```

---

## Query 워크플로우 (P3a/b 분리)

### P3a — read-only query

```
1. /query [질문]
2. LLM이 tool_search_wiki_by_keyword(keyword) 호출
3. 결과 없으면 fallback:
   "wiki에 관련 내용이 없습니다. 웹 검색을 실행할까요? (/search [질문])"
4. 결과 있으면 tool_get_wiki_page() 로 내용 로드
5. LLM 종합 답변 생성
6. synthesis 저장 없음 — 답변만 출력
```

### P3b — synthesis 저장 (사용자 확인 필수)

```
1. /query 답변 출력 후 LLM이 판단:
   - 2개 이상 page cross-reference?
   - 단순 요약이 아닌 새로운 결론/비교 존재?

2. 조건 충족 시 사용자에게 확인 요청:
   "이 답변에 새로운 인사이트가 있어 보입니다.
    synthesis/에 저장할까요? [저장 / 건너뜀]"

3. 사용자가 "저장" 선택 시:
   - synthesis/[주제]-[날짜].md 생성
   - confidence, source_pages 기록
   - SQLite 등록 + index.md 갱신

4. 유사 synthesis 존재 시 → merge 제안
```

**synthesis frontmatter:**
```yaml
---
title: "LLM Wiki vs RAG 비교 분석"
tags: ["llm", "wiki", "rag"]
created: "2026-04-08"
confidence: 0.72
verified: false          # 기본값. /wiki-verify 후 true로 변경
source_pages:
  - topics/llm-wiki-pattern.md
  - topics/rag-overview.md
query: "LLM wiki와 RAG의 차이는?"
---
```

**verified 플래그 운용 (v6 — Opus 수정):**
```
MVP 단계:
  - 사용자가 텔레그램에서 "저장" 선택 → verified=TRUE로 즉시 정식 편입
  - /wiki-verify 별도 명령 없음 (사용성 저하, 이중 확인 불필요)

batch ingest 도입 이후 (P3b 이후 단계):
  - 자동 수집된 synthesis → verified=FALSE로 대기
  - /wiki-verify 명령으로 검토 후 정식 편입
```

---

## Lint 전략 (P4) — DB 기반 경량 O(N)

### 원칙
- **탐지는 ingest 시점** — contradiction_flag 즉시 기록
- **lint는 확인 + 샘플링** — 전체 비교 금지

### 검사 항목

```sql
-- 1. orphan 탐색 (파일은 있는데 DB에 없음)
SELECT file FROM filesystem WHERE file NOT IN (SELECT path FROM wiki_pages)

-- 2. contradiction 확인
SELECT path, title FROM wiki_pages WHERE contradiction_flag = TRUE

-- 3. stale 탐색
SELECT path, title, updated FROM wiki_pages 
WHERE updated < date('now', '-90 days')

-- 4. page 크기 초과
SELECT path, token_count FROM wiki_pages WHERE token_count > 800

-- 5. schema drift (frontmatter 필드 누락)
-- 파일 직접 스캔으로 확인
```

### anchor 기반 contradiction 비교 (O(N))

```
pairwise (❌ O(N²)):
  전체 페이지 쌍 비교

anchor 기반 (✅ O(N)):
  1. has_numbers=TRUE인 페이지 중 최근 updated 1개 = anchor
  2. 동일 태그 가진 나머지 페이지와만 1:1 비교
  3. 상위 5개 의심 쌍만 LLM 비교 (샘플링)
  4. contradiction_flag=TRUE 업데이트
```

### /lint --repair

```
DB에 없는 wiki page 파일 감지 → 자동으로 SQLite에 재등록
```

---

## 파일 동시 쓰기 보호

```python
# server_v3_postgres_router.py에 추가
import asyncio
from filelock import FileLock

wiki_lock = asyncio.Lock()
index_file_lock = FileLock("/Users/sykim/workspace/booml-wiki/index.md.lock")

async def safe_wiki_write(page_path, content, db_entry):
    async with wiki_lock:
        with index_file_lock:
            # 1. page 파일 write
            # 2. SQLite upsert
            # 3. index.md 갱신
            # 4. log.md append
```

---

## _schema.md (v4 — 사용자 확인 반영)

```markdown
# 붐엘 Wiki Schema v4

## 생성 규칙
1. 모든 페이지는 markdown (.md)
2. 파일명: 영문 lowercase, hyphenated
3. 페이지 구조:
   - YAML frontmatter (title, tags, created, updated, source_urls,
     source_count, has_numbers, key_metrics, token_count)
   - H1 제목
   - ## Summary (3줄 이내)
   - ## Key Concepts
   - ## Source Notes
   - ## Change Log (재수집 시 변경 이력)
   - ## Contradictions (모순 발생 시만)
   - ## Related Pages ([[page-name]])
4. page 크기: 500~800 tokens 권장, 초과 시 split

## Retrieval 규칙 (LLM)
- tool_search_wiki_by_tag() 또는 tool_search_wiki_by_keyword() 먼저 호출
- shortlist 5~10개 → tool_get_wiki_page() 로 내용 로드
- index.md 직접 읽기 금지 (사람용)

## Ingest 규칙
- URL 중복: tool_check_url_exists() → 있으면 merge 모드
- 모순 발견: ## Contradictions 즉시 append + DB contradiction_flag=TRUE
- 재수집: append 금지 → 중복 제거 merge + ## Change Log 기록

## Synthesis 저장 조건
- 자동 저장 금지 — 반드시 사용자 확인 후 저장
- 확인 조건 체크:
  1. 2개 이상 page cross-reference
  2. 단순 요약이 아닌 새로운 결론/비교 존재
  3. 유사 synthesis 없음 (있으면 merge 제안)

## Query Fallback
- wiki 관련 내용 없으면: "wiki에 없습니다. 웹 검색할까요?" 출력
```

---

## 명령어 구성 (v6)

| 명령 | 동작 | Phase |
|------|------|-------|
| /test_ingest [URL] | glue 코드로 단일 URL 수동 테스트 | P1 |
| /ingest [URL] | wiki에 소스 추가 (atomicity + 파일 락) | P2 |
| /query [질문] | wiki 기반 답변 + fallback | P3a |
| /synthesize [질문] | 답변 후 사용자 확인 → synthesis 저장 | P3b |
| /lint | orphan/stale/contradiction/schema drift (DB 기반) | P4 |
| /lint --repair | 누락 DB entry 재등록 | P4 |
| /wiki | recent pages + log 요약 | P2 |
| /wiki-stat | page count, orphan, stale, synthesis 통계, 전환 트리거 상태 | P2 |
| /wiki-verify [page] | synthesis page를 정식 지식으로 컨펌 — batch ingest 도입 후 (MVP 제외) | P3b+ |

---

## MVP 실행 계획 (2일 — Opus 조정)

v5 계획은 2일 안에 불가능. Opus 현실 추정 기반으로 범위 축소.

**MVP 범위: P0 + P1 + P3a(간소화)**  
merge, 파일 락, synthesis, /lint, Change Log → Day 3+ 이후

| 작업 | 시간 | 비고 |
|------|------|------|
| **Day 1** | | |
| P0: 디렉토리 + _schema + index.md + log.md | 30분 | |
| P0: fetch_url 제한 15,000자로 상향 (L657) | 10분 | 즉시 수정 |
| P1: wiki.db + wiki_pages 테이블 생성 | 1시간 | |
| P1: 툴 4개 server_v3 등록 | 2시간 | tool_functions 딕셔너리 확장 |
| P1: wiki_ingest.py glue 코드 | 3시간 | JSON 포맷 명세 + 파싱 재시도 포함 |
| P1: /test_ingest 텔레그램 명령 연동 | 1시간 | 봇 코드 수정 |
| **Day 2** | | |
| P3a: /query read-only + SQLite 검색 | 3시간 | tool_search_wiki_by_keyword 기반 |
| P3a: fallback 메시지 | 30분 | |
| 통합 테스트 (/test_ingest → /query) | 3시간 | LLM 비결정성 디버깅 시간 포함 |
| **Day 3+ (이후)** | | |
| P2: /ingest 코드화 + 파일 락 + merge | 1일 | |
| P3b: /synthesize 사용자 확인 저장 | 반일 | |
| P4: /lint DB 기반 | 1일 | |

---

## 기존 코드 활용

| 컴포넌트 | 활용 방법 |
|---------|---------|
| memory_store.py (SQLite) | wiki.db 기반으로 확장 |
| tool_fetch_url() | ingest 원문 수집 |
| tool_read_file() | page 내용 로드 |
| tool_write_file() | page 생성/업데이트 (락 감싸서 사용) |
| tool_list_dir() | orphan 탐색 |
| tool_exec() | token 카운트, 파일 크기 확인 |
| web_search() | /query fallback |
| prompt_composer.py | ingest/synthesis 프롬프트 조립 |

---

## 붐엘 현행 아키텍처 현황 (2026-04-08 실측)

> 소스코드 직접 확인 기준. 추정/기억 기반 아님.

### 구동 상태

| 항목 | 상태 |
|------|------|
| 붐엘 서버 (포트 8000) | ✅ 실행 중 (업타임 ~20h) |
| 붐엘2 서버 (포트 8001) | ✅ 실행 중 |
| booml-bot-v2-enhanced | ✅ 실행 중 |
| booml-bot-v2-chat | ✅ 실행 중 |
| 모델 | Gemma 4 26B A4B MoE 4bit (mlx) |
| TurboQuant KV 캐시 | 3.5bit |
| DB 백엔드 (실제) | SQLite (폴백) |
| 아키텍처 모듈 | ARCHITECTURE_ENABLED = True |

### 이미 구현된 모듈

| v3 레이어 | 현재 상태 | 파일 |
|----------|---------|------|
| Memory Store (SQLite) | 완전 구현 | memory_store.py (755줄) |
| Policy Engine | PreferenceSlot 시스템 | policy_engine.py (291줄) |
| Prompt Composer | 슬롯 조립형 프롬프트 | prompt_composer.py (253줄) |
| Model Adapter | 모델 라우팅 + 핫스위칭 + TurboQuant | model_router.py (615줄) |
| KPI Logger | KPI 수집 시스템 | kpi_logger.py (317줄) |
| BoomL Core | 전체 통합 진입점 | booml_core.py (304줄) |
| Repository Factory | PostgreSQL/SQLite 자동 선택 | repository_factory.py |
| PostgreSQL Repository | 코드 완성 (psycopg2 미설치로 미활성) | postgres_repository.py (27KB) |
| Token Dashboard 연동 | 응답 완료 시 fire-and-forget POST | server_v3 내장 |

### Tool Calling 현황 (실측 — 서버 코드 기준)

| 툴 이름 | 함수 | 설명 | 보안 제한 |
|---------|------|------|---------|
| web_search | web_search() | DuckDuckGo 검색 | — |
| read_file | tool_read_file() | 파일 읽기 | /Users/sykim/ 하위만 |
| write_file | tool_write_file() | 파일 쓰기/생성 | /Users/sykim/ 하위만 |
| list_dir | tool_list_dir() | 디렉토리 목록 | /Users/sykim/ 하위만 |
| get_weather | tool_get_weather() | wttr.in 3일 예보 | — |
| exec | tool_exec() | 셸 명령 실행 | ls/cat/grep/find/pwd/date/echo/head/tail/wc만 허용 |
| memory_read | tool_memory_read() | 붐엘 메모리 파일 읽기 | — |
| memory_write | tool_memory_write() | 붐엘 메모리 파일 쓰기 | — |
| fetch_url | tool_fetch_url() | URL 수집 (HTML→텍스트) | ⚠️ 3,000자 제한 (L657 즉시 수정 필요) |

- **tool calling 루프:** 최대 5회 (무한루프 방지, L984)
- **시스템프롬프트 자동 주입:** tools 제공 시 Few-shot 포함 tool 사용 유도 프롬프트 자동 삽입

### PostgreSQL 실제 현황 (소스 확인)

| 항목 | 상태 |
|------|------|
| PostgreSQL 프로세스 | ✅ 실행 중 (localhost:5432) |
| booml DB | ✅ 존재 (6개 테이블 완성) |
| postgres_repository.py | ✅ 코드 완전 구현 |
| psycopg2 (venv) | ❌ 미설치 |
| repository_factory.py L197 | ❌ `os.environ["BOOML_DB_BACKEND"] = "sqlite"` 하드코딩 |
| ecosystem.config.js | ❌ BOOML_DB_BACKEND env 없음 |

**PostgreSQL 활성화 3단계** (마이그레이션 불필요 — 이미 준비됨):
```bash
# 1. psycopg2 설치
/Users/sykim/.openclaw/workspace/booml-mlx/venv/bin/pip install psycopg2-binary

# 2. repository_factory.py L197 제거
# os.environ["BOOML_DB_BACKEND"] = "sqlite"  ← 이 줄 삭제

# 3. ecosystem.config.js env 추가
# env: { PORT: '8000', BOOML_DB_BACKEND: 'postgresql' }
```

### 미구현 (wiki pipeline 기준)

| 항목 | 우선순위 |
|------|---------|
| fetch_url 3,000→15,000자 상향 (L657) | **즉시** |
| Wiki 디렉토리 + _schema.md + index.md + log.md | P0 |
| wiki.db + wiki_pages 테이블 (verified 컬럼 포함) | P1 |
| wiki 전용 툴 4개 (search_by_tag, search_by_keyword, get_page, check_url) | P1 |
| wiki_ingest.py glue 코드 (JSON 스키마 + 파싱 재시도) | P1 |
| /test_ingest 텔레그램 명령 | P1 |
| /ingest 명령 (atomicity + filelock) | P2 |
| /query read-only + fallback | P3a |
| /synthesize 사용자 확인 저장 | P3b |
| /lint DB 기반 O(N) | P4 |
| /wiki-stat 전환 트리거 경고 (1,000페이지) | P4 |
| page split (token_count > 800) | P4 |
| PostgreSQL 활성화 (3단계) | P5 |
| pgvector 검색 | P6 장기 |

---

## 검증 체크리스트

### P0
- [ ] 디렉토리 구조 생성 확인
- [ ] _schema.md, index.md, log.md 존재

### P1
- [ ] wiki.db 생성 + wiki_pages 테이블 존재
- [ ] tool_search_wiki_by_tag() 동작
- [ ] tool_check_url_exists() 동작
- [ ] /test_ingest [URL] → draft 생성 + DB 등록 + 파일 생성

### P2
- [ ] /ingest [URL] → atomicity 보장 write 순서
- [ ] 동일 URL 재수집 → merge + Change Log (append 아님)
- [ ] 동시 /ingest 2개 → 파일 락으로 순차 처리

### P3a
- [ ] /query → tool_search_wiki_by_keyword 호출
- [ ] wiki 없으면 fallback 메시지 출력
- [ ] synthesis 자동 저장 없음 확인

### P3b
- [ ] /synthesize → 조건 체크 → 사용자 확인 메시지
- [ ] 사용자 거부 → 저장 없음
- [ ] 유사 synthesis → merge 제안

### P4
- [ ] /lint → orphan/stale/contradiction 목록 (DB 쿼리)
- [ ] /lint --repair → 누락 DB entry 재등록
- [ ] anchor 기반 비교 (상위 5쌍만)

---

## 교차 검증 이력

| 버전 | 검토자 | 주요 지적 |
|-----|--------|---------|
| v1 | 붐코 | 초기 설계 |
| v2 | 붐코 | Query→Wiki 루프 추가, POC 전략 신설 |
| v3 | GPT | write 권한 단계 분리, index.json 분리, synthesis 조건 강제, lint O(N) |
| v4 | DeepSeek | P1 glue 코드 방식으로 변경, SQLite P1 즉시 도입, wiki 전용 툴, 파일 락, synthesis 사용자 확인, 재수집 merge, query fallback |
| v5 | Gemini | current_context.md 경량 색인, verified 플래그 + /wiki-verify 환각 격리, index 전환 트리거 기준 명시 |
| v6 | Opus | current_context.md 제거(충돌), verified 이중 확인 제거, fetch_url 3,000→15,000자, LLM 응답 JSON 스키마 명세, index.md=파생뷰, wiki.db=단일 진실 소스, MVP 범위 P0+P1+P3a로 축소 |
| v6.1 | 붐코 (소스 실측) | 툴 9개 실측 확인 (exec 보안제한/memory_read·write 추가), tool loop max 5회, PostgreSQL 실행 중+DB 준비됨 확인, P5 마이그레이션→활성화 3단계로 수정, fetch_url L657 즉시 수정 항목 추가 |
