# 붐엘 Wiki 파이프라인 — 구현 기획안

> 작성일: 2026-04-08
> 상태: 교차 검증용

---

## 한 줄 결론

붐엘에 Karpathy 패턴을 적용하여 **LLM이 wiki를 스스로 구축·유지하는 시스템**을 만든다.

---

## 기존 문제

```
현재:  /crawl [URL] → raw/*.md 저장 (끝)
목표:  /crawl [URL] → raw/*.md → LLM이 wiki page 생성 → index.md 갱신
```

---

## Wiki 구조

```
/Users/sykim/workspace/booml-wiki/
  _schema.md           # LLM에게 conventions告诉他 (생성 규칙)
  index.md            # 모든 페이지 카탈로그
  log.md              # chronological ingest/query/lint 기록
  topics/             # 주제별 wiki page
  entities/           # 인물/조직/제품별 page
  sources/            # 원본 소스 참고용
  synthesis/          # 종합 분석 page
```

---

## Phase 구분

| Phase | 내용 | 산출물 |
|-------|------|--------|
| P0 | Wiki 기반 구축 | _schema.md, index.md, log.md 디렉토리 |
| P1 | ingest pipeline | /ingest [URL] — raw → wiki page 변환 + 상호링크 |
| P2 | query + search | /query [질문] — wiki 기반 답변 |
| P3 | lint + health check | /lint — orphan/stale/contradiction 검사 |
| P4 | PostgreSQL 완전 연동 | repository_factory → postgres_repository |
| P5 | pgvector 검색 (장기) | 벡터 검색 도입 |

---

## P0-P1 핵심 설계

### _schema.md ( conventions)

```markdown
# 붐엘 Wiki Schema

## 생성 규칙
1. 모든 페이지는 markdown (.md)
2. 파일명: 영문 lowercase, hyphenated
3. 페이지 구조:
   - YAML frontmatter (title, tags, created, source_count)
   - H1 제목
   - ## Summary (3줄 이내)
   - ## Key Concepts
   - ## Source Notes
   - ## Related Pages (상호 링크)
4. 상호 링크: [[page-name]] 포맷 (Obsidian 호환)
5. 한 페이지 = 하나의 개념/주제/엔티티

## Ingest 규칙
- 원본 소스 읽기 → 핵심 정보 추출 → 기존 페이지 업데이트 또는 신규 생성
- 기존 페이지와 중복 시 통합 (연결된 페이지에 병합)
- 새로운 정보는 하단에 append

## Query 규칙
- index.md 먼저 읽기 → 관련 페이지 탐색 → 종합 답변
- 답변의 가치 있는 부분 → wiki에 새 page로 저장

## Lint 규칙
- orphan page 검사 (links from nowhere)
- contradiction 검사 (같은 주장의 다른 수치/결론)
- stale page 검사 (최신 소스에 비해 오래된 경우)
```

### Ingest 워크플로우 (P1)

```
1. /ingest [URL]
2. server가 원문 fetch (tool_fetch_url 또는 /crawl 결과 재사용)
3. LLM이 원문 분석:
   - 핵심 엔티티 추출 (이름, 날짜, 수치, 결론)
   - 주제 태그 결정 (3~5개)
   - 기존 wiki에서 관련 페이지 검색 (index.md 기반)
   - 새 wiki page draft 생성
4. wiki page 저장 (topics/ 또는 entities/)
5. 관련 페이지에 상호 링크 추가
6. index.md 갱신 (새 페이지 등록)
7. log.md에 ingest 기록
```

### 명령어 구성

| 명령 | 동작 |
|------|------|
| /ingest [URL] | wiki에 소스 추가 (crawl 자동 연동) |
| /query [질문] | wiki 기반 답변 |
| /lint | wiki 건강检查 |
| /wiki | recent pages + log 요약 |
| /wiki-stat | page count, orphan, stale 통계 |

### 기존 코드 활용

- tool_fetch_url() — 이미 server_v3에 있음
- /crawl 결과 (/Users/sykim/workspace/crawled/) 재활용 가능
- prompt_composer.py — wiki page 생성 프롬프트 조립에 재사용
- memory_store.py — ingest log 저장 (PostgreSQL 폴백)

---

## P0+P1 우선 실행 이유

1. 위험 낮음 — 기존 코드 수정 최소화, 새 디렉토리 추가만
2. 가치 높음 — Karpathy 패턴의 핵심을 가장 적은 effort로 구현
3. 반복 가능 — P0+P1 안정화 후 P2-P4 순차 진행

---

## 붐엘 현행 vs v3 아키텍처 비교

### 이미 구현된 模块

| v3 아키텍처 레이어 | 현재 상태 | 파일 |
|------------------|---------|------|
| Memory Store | SQLite 완전 구현 | memory_store.py (755줄) |
| Policy Engine | PreferenceSlot 시스템 | policy_engine.py (291줄) |
| Prompt Composer | 슬롯 조립형 프롬프트 | prompt_composer.py (253줄) |
| Model Adapter | 모델 라우팅 + 핫스위칭 | model_router.py (615줄) |
| KPI Logger | KPI 수집 시스템 | kpi_logger.py (317줄) |
| BoomL Core | 전체 통합 진입점 | booml_core.py (304줄) |
| Tool Calling | 10개 툴 내장 | server_v3 내장 |
| Realtime Data | 주식/날씨/뉴스/검색 | server_v3 내장 |

### 미구현

| 항목 | 상태 | 우선순위 |
|------|------|---------|
| PostgreSQL 완전 연동 | 파일만 있음, SQLite 사용 중 | P1 |
| Wiki 디렉토리 | 없음 | P2 |
| index.md / schema.md | 없음 | P2 |
| /ingest 명령 | 없음 | P2 |
| /query 명령 | 없음 | P2 |
| /lint 명령 | 없음 | P3 |
| Exploration ratio (10%) | 없음 | P3 |
| confidence/decay | 구조만 있음 | P3 |
| pgvector 검색 | 없음 (Phase 4) | 장기 |

---

## 실행 단계 (P0)

### Step 1: 디렉토리 생성

```bash
mkdir -p /Users/sykim/workspace/booml-wiki/{topics,entities,sources,synthesis}
```

### Step 2: _schema.md 작성

_schema.md 파일 생성 ( conventions 내용 포함)

### Step 3: index.md 작성

```markdown
# 붐엘 Wiki Index

## topics
_(주제별 페이지 목록)_

## entities
_(개체별 페이지 목록)_

## synthesis
_(종합 분석 페이지 목록)_

## recently updated
_(최신 갱신 페이지)_
```

### Step 4: log.md 작성

```markdown
# 붐엘 Wiki Log

## [2026-04-08] wiki initialized
- ingest: (initial setup)
```

### Step 5: server_v3_postgres_router.py 수정

- /ingest, /query, /lint, /wiki, /wiki-stat 명령 핸들러 추가
- wiki 디렉토리 경로常量 설정
- ingest용 프롬프트 조립 함수 작성

### Step 6: booml_bot_v2_enhanced.py (또는 _chat.py) 수정

- BotCommand에 새 명령어 등록
- /ingest, /query, /lint, /wiki, /wiki-stat 핸들러 연동

### Step 7: PM2 재시작 및 테스트

```bash
pm2 restart booml-mlx-server
pm2 restart booml-telegram-bot
```

---

## 검증 체크리스트

- [ ] /wiki 명령 → index.md 내용 반환
- [ ] /ingest [URL] → wiki page 생성 + index.md 갱신
- [ ] /query [질문] → wiki 기반 답변
- [ ] /lint → orphan/stale 목록 반환
- [ ] log.md에 ingest 기록 확인
- [ ] wiki page 상호 링크 작동 확인
