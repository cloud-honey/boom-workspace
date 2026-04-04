# OpenClaw 세션 인수인계 문서
> 작성일: 2026-03-06 (최종 수정: 2026-03-06) / 다음 세션에서 이 파일 먼저 읽을 것

---

## 시스템 구성

| 항목 | 내용 |
|------|------|
| OS | Ubuntu (sykim-XPS-15-9570) |
| OpenClaw | 2026.3.2 |
| 접속 | PuTTY SSH |
| 붐 모델 | anthropic/claude-sonnet-4-6 |
| 밤티 모델 | google/gemini-2.5-flash |

---

## 에이전트 구성

### 붐 (main)
- workspace: `~/.openclaw/workspace`
- 텔레그램 봇: @Occboom_bot
- 하트비트: 30분 (cron 감시, main 세션 systemEvent 방식)
- 모델: claude-sonnet-4-6 (Claude Max/Pro OAuth 토큰)

### 밤티 (bamti)
- workspace: `~/.openclaw/workspace-bamti`
- 텔레그램 봇: @bamti_bot
- 하트비트: 붐이 자기 체크 시 밤티도 같이 확인 (별도 크론 없음)
- 모델: gemini-2.5-flash

### 유령 폴더 (무시)
- `~/.openclaw/agents/boom` — 예전 잔재, 등록 안 됨
- `~/.openclaw/agents/boom2` — 예전 잔재, 등록 안 됨

---

## PM2 프로세스

```bash
pm2 list
# boom-dashboard (id:0) — 포트 5173
# cloudflared (id:4) — dashboard/occ/pj.abamti.com 터널
```

### cloudflared
- 바이너리: `~/.openclaw/workspace/openclaw-dashboard/cloudflared.bin`
- 래퍼: `~/.cloudflared/start.sh`
- 설정: `~/.cloudflared/config.yml`
- 터널 도메인:
  - dashboard.abamti.com → localhost:5173
  - occ.abamti.com → localhost:18789
  - pj.abamti.com → localhost:8080

---

## 중요 파일 경로

| 파일 | 경로 |
|------|------|
| OpenClaw 설정 | `~/.openclaw/openclaw.json` |
| Cron 작업 | `~/.openclaw/cron/jobs.json` |
| 붐 auth | `~/.openclaw/agents/main/agent/auth-profiles.json` |
| Cleanup 스크립트 | `~/.openclaw/scripts/cleanup.sh` |
| 붐 memory | `~/.openclaw/workspace/memory/YYYY-MM-DD.md` |
| 밤티 memory | `~/.openclaw/workspace-bamti/memory/YYYY-MM-DD.md` |

---

## API 키 / 인증

| 서비스 | 비고 |
|--------|------|
| Anthropic | Claude Max/Pro OAuth 토큰 (anthropic:manual), 유효기간 1년 |
| Google | API 키 (google:default) |
| GitHub Copilot | 토큰 (github-copilot:github) — GPT 모델 전용 (Claude 경유 아님) |
| DeepSeek | env DEEPSEEK_API_KEY (openclaw.json) |
| KMA 날씨 | 공공데이터포털, nx=57 ny=125 (서울 오류2동) |

> **주의**: GitHub Copilot은 GPT 모델(gpt-5-mini 등) 전용. Claude는 별도 Max/Pro OAuth 사용.

### Claude 토큰 만료 시 재발급
```bash
claude setup-token
openclaw models auth paste-token --provider anthropic
# auth-profiles.json 쿨다운 초기화
python3 -c "
import json,time
path='/home/sykim/.openclaw/agents/main/agent/auth-profiles.json'
d=json.load(open(path))
d['usageStats']['anthropic:manual']={'errorCount':0,'lastUsed':int(time.time()*1000)}
json.dump(d,open(path,'w'),indent=2)
print('완료')
"
openclaw gateway restart
```

---

## Cron 작업 목록

| ID | 이름 | 에이전트 | 스케줄 | 방식 |
|----|------|----------|--------|------|
| 53329f9e | 붐 heartbeat 감시 | main | */30 7-23 * * * (KST) | main 세션 systemEvent |
| 4c8705aa | daily-reporter-weekday-07:50-KST | main | 평일 07:50 KST | isolated, gpt-5-mini |

> **변경 이력**: 기존 크론(12c84635 붐, 408ee0be 밤티) 삭제. isolated → main 세션으로 변경하여 세션 누적 방지. 주기 10분 → 30분으로 변경.

---

## 자동화

### 매시간 cleanup cron
```bash
crontab -l | grep cleanup
# 0 * * * * ~/.openclaw/scripts/cleanup.sh
```
- 좀비 프로세스 정리
- PM2 죽은 프로세스 재시작
- fallback.lock 24시간 이상 시 제거
- 30일 이상 로그 정리
- **완료된 OpenClaw 세션 정리** (`openclaw sessions cleanup --all-agents`) ← 2026-03-06 추가

---

## openclaw.json 수정 규칙 (중요!)

1. **반드시 백업 먼저**
```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak.$(date +%Y%m%d%H%M%S)
```
2. python3으로 JSON 파싱 후 수정 (직접 편집 금지)
3. `openclaw doctor` 실행 시 파일 덮어쓸 수 있음 주의
4. 수정 후 `openclaw gateway restart` 필요

---

## 알려진 문제 / 주의사항

### 붐 이름 변경 문제
- 붐이 세션 시작 시 IDENTITY.md를 템플릿으로 인식해 이름 바꾸려 함
- AGENTS.md, IDENTITY.md에 수정 금지 규칙 추가로 완화
- 붐이 또 이름 바꾸면: 직접 텔레그램에서 "이름 바꾸지 마라" 지시

### PM2 환경변수
- KMA_API_KEY는 pm2 start 시점에 주입됨
- `pm2 restart`로는 환경변수 안 바뀜
- 재등록 필요 시: `pm2 delete boom-dashboard` 후 KMA_API_KEY=... pm2 start ...

### cloudflared 재시작
```bash
pm2 restart cloudflared
```

### 하트비트 비활성화 시
```bash
openclaw system heartbeat enable
```

### 세션 누적 주의
- heartbeat 크론은 반드시 `sessionTarget: main` (systemEvent) 방식 사용
- isolated 방식은 매 실행마다 새 세션 생성 → 세션/토큰 누적됨
- 밤티처럼 non-default 에이전트는 main 세션 불가 → 붐이 대신 감시

---

## 미완료 작업

- [ ] occ.abamti.com 페어링 (openclaw dashboard 접속 시 페어링 필요)
- [ ] 붐2/붐3 서브에이전트 실제 테스트
- [ ] 붐 `<tool_code>` 날것 출력 문제 (Gemini 폴백 시 발생하는 버그)
- [ ] daily-reporter.js 스크립트 없음 — 4c8705aa 크론이 매일 실패 중

---

## 빠른 상태 확인 명령어

```bash
# 전체 상태
pm2 list
openclaw gateway health
openclaw models status | grep -E "Default|anthropic|cooldown"

# 크론 상태
openclaw cron list

# 세션 현황
openclaw sessions --all-agents

# 하트비트
openclaw system heartbeat last

# 로그
openclaw logs 2>/dev/null | tail -20
```
