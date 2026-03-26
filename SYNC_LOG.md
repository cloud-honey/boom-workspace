# SYNC_LOG.md — 양쪽 작업 동기화 로그

> 목적: XPS(붐/sonnet)와 맥미니(붐/gpt-5.4)가 병렬 운영 중인 기간 동안
> 머지 시 누락 없이 반영하기 위한 작업 이력 파일.
>
> 머지 완료 후 이 파일은 보관(archive)하고 운영 종료.

## 작성 규칙
- 형식: `## HH:MM KST [호스트/모델] 작업명`
- 호스트: `XPS` 또는 `MAC`
- 파일 변경 시: 반드시 경로 기록
- openclaw.json 변경 시: 변경 키/값 명시
- 머지 시 주의사항 있으면 `⚠️ 머지 주의:` 로 표기

---

## 2026-03-26 작업 이력

## 11:14 KST [XPS/sonnet] 맥미니 Phase 1 이전 작업
- `~/.openclaw/openclaw.json` → 맥미니로 복사 (경로 `/home/sykim/` → `/Users/sykim/` 치환)
- `SOUL.md, MEMORY.md, AGENTS.md, USER.md, IDENTITY.md, HEARTBEAT.md, TOOLS.md` 복사
- `memory/` 폴더 전체 복사
- `~/.openclaw/agents/main/agent/auth-profiles.json` 복사 (Anthropic/GitHub/Google/OpenAI 키)
- `~/.openclaw/credentials/github-copilot.token.json`, `telegram-default-allowFrom.json` 복사
- ⚠️ 머지 주의: 맥미니 openclaw.json은 별도 운영 — 머지 시 충돌 가능성 있음

## 12:12 KST [XPS/sonnet] 맥미니 텔레그램 봇 교체
- 맥미니 `channels.telegram.accounts.default.botToken` → `8675194468:AAFnBYNm2wQDdyxAuY3MX0K07lwynL_kiPA` (새 봇)
- XPS는 기존 봇 유지 (채널 분리 완료)

## 12:15 KST [XPS/sonnet] 맥미니 기본 모델 gpt-5.4로 변경
- 맥미니 `agents.defaults.model.primary` → `openai-codex/gpt-5.4`
- 맥미니 `agents.defaults.model.fallbacks` → `[google/gemini-3.1-pro-preview, anthropic/claude-opus-4-6]`
- XPS는 claude-sonnet-4-6 유지

## 12:15 KST [XPS/sonnet] 맥미니 → XPS 메모리 자동 동기화 설정
- 맥미니에 `/Users/sykim/sync-memory-to-xps.sh` 생성
- 맥미니 crontab: `*/5 * * * *` → `memory/` + `MEMORY.md` → XPS rsync
- 맥미니 SSH 키 → XPS `~/.ssh/authorized_keys` 등록
- ⚠️ 머지 주의: 맥미니 memory 파일이 5분 단위로 XPS에 덮어씌워짐 — 머지 시 양쪽 최신본 수동 확인 필요

## 13:10 KST [MAC/gpt-5.4] 맥미니 절전 방지 영구 고정 + 메모리/머지 규칙 확인
- 변경 파일/설정:
  - `~/Library/LaunchAgents/com.boom.caffeinate.plist` 생성
  - `launchctl load ~/Library/LaunchAgents/com.boom.caffeinate.plist` 적용
  - `/Users/sykim/.openclaw/workspace/memory/2026-03-26.md` 기록 추가
- 작업:
  - `Sleep Service Back to Sleep` 로그 확인 후 `caffeinate -dimsu` 상시 유지로 고정
  - 맥미니 crontab에서 `sync-memory-to-xps.sh` 5분 주기 동기화 확인
  - 맥미니 워크스페이스 git 상태 점검: memory/ 및 주요 md 파일이 맥미니 측에선 untracked로 보여 별도 머지 관리 필요 확인
- ⚠️ 머지 주의:
  - 맥미니 메모리 기록은 XPS로 rsync 되지만, git 추적 상태는 XPS와 다를 수 있음
  - 맥미니 작업은 계속 `[MAC/gpt-5.4]` 태그로 SYNC_LOG.md에 별도 기록 필요
