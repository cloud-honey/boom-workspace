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

## 13:12 KST [MAC/gpt-5.4] 맥미니 운영 규칙 5줄 AGENTS 반영
- 변경 파일/설정:
  - `/Users/sykim/.openclaw/workspace/AGENTS.md`
- 작업:
  - XPS ↔ 맥미니 병렬 운영용 5줄 규칙 추가
  - 규칙 항목에 언제(2026-03-26 13:12 KST), 누가(붐), 왜(나중 머지 충돌 최소화) 추가했는지 명시
- ⚠️ 머지 주의:
  - AGENTS.md는 맥미니 쪽 변경 사항이므로 XPS 머지 시 동일 섹션 중복 삽입 여부 확인 필요

## 14:23 KST [MAC/gpt-5.4] 붐4 영어 지시 규칙 명시
- 변경 파일/설정:
  - `/Users/sykim/.openclaw/workspace/AGENTS.md`
- 작업:
  - 비Claude 서브에이전트 영어 지시 규칙에 `Ollama/Qwen` 명시 추가
  - 붐4 항목에 `지시 언어: 반드시 영어` 명시
  - 붐4 모델 설명을 `ollama/qwen2.5-coder:32b` 기준으로 업데이트
- ⚠️ 머지 주의:
  - XPS 쪽 AGENTS.md에도 같은 규칙이 이미 부분적으로 있을 수 있으니, 머지 시 중복 문장과 모델 버전 표기를 함께 정리할 것

## 16:17 KST [MAC/gpt-5.4] OrbStack 설치 및 XPS 장애 진단 기록
- 변경 파일/설정:
  - `/Users/sykim/.openclaw/workspace/memory/2026-03-26.md`
  - `/Users/sykim/.openclaw/workspace/SYNC_LOG.md`
- 작업:
  - OrbStack 적합성 확인 후 `brew install --cask orbstack` 설치 완료
  - 이후 OrbStack 활성화가 마무리되어 `docker version` 정상 확인
  - Node.js 설치 상태 확인 (`v22.22.2`)
  - 붐4 테스트를 `ollama/qwen2.5-coder:32b`로 재실행해 뉴스 PWA 목업 초안 생성 완료
  - XPS `100.116.65.86` SSH timeout 확인, `occ.abamti.com`은 Cloudflare Tunnel 1033 확인
  - `aidev.abamti.com/vse-dashboard/`는 정적 배포라 정상임을 구분 정리
  - 재난 대비용 이중 진입점/자동 재시작/전원 복구 필요성 정리
- ⚠️ 머지 주의:
  - XPS 복구 후 같은 장애 원인(절전, SSH 미응답, 터널 미기동, OpenClaw 비자동복구)을 실제 설정 파일/서비스 기준으로 다시 문서화해야 함

## 17:41 KST [XPS/sonnet] 게이트웨이 설정 오류 복구
- 변경 파일/설정:
  - `/home/sykim/.openclaw/openclaw.json` (`gateway.heapMb` 제거)
  - `/home/sykim/.openclaw/openclaw.json.bak.20260326174111` 백업 생성
- 작업:
  - OOM 이후 투입된 `gateway.heapMb`가 현재 OpenClaw 버전에서 미지원이라 부팅 실패하는 점 확인
  - 문제 키 제거 후 `openclaw-gateway.service` 정상 기동 확인
- ⚠️ 머지 주의:
  - 메모리 제한은 config 키가 아니라 systemd ExecStart의 Node 옵션 방식으로 정리해야 함

## 20:43 KST [MAC/gpt-5.4] 화면 꺼짐 허용 + 잠자기만 방지로 조정
- 변경 파일/설정:
  - `/Users/sykim/Library/LaunchAgents/com.boom.caffeinate.plist`
  - caffeinate 옵션: `-dimsu` → `-isu`
- 작업:
  - LaunchAgent unload/load로 재적용
  - 설정 위치를 문서화: `~/Library/LaunchAgents/com.boom.caffeinate.plist`
  - 결과적으로 화면은 꺼지고, 시스템 잠자기만 막도록 조정
- ⚠️ 머지 주의:
  - 맥미니 절전 정책 관련 변경은 LaunchAgent 기준으로 관리되고 있으니, 추후 다른 전원 설정과 충돌 여부 확인 필요
