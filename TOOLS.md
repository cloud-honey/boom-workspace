# TOOLS.md - 시스템 설정 메모

## 붐 마스터 대시보드

- **URL (내부):** http://localhost:5173
- **URL (외부):** https://dashboard.abamti.com (Cloudflare Named Tunnel)
- **PM2 프로세스:** `boom-dashboard` (port 5173), `cloudflared` (Named Tunnel)
- **터널 config:** `~/workspace/openclaw-dashboard/cloudflared/config.yml`

## 에이전트 역할

- **붐 (나):** claude-sonnet-4-6 — 방향 판단, 지시, 감수
- **밤티:** openai-codex/gpt-5.4 — QA, 반복 작업 전담
- **붐2:** deepseek/deepseek-chat — 복잡한 코딩, 로직 분석
- **붐3:** google/gemini-2.5-flash — 단순 수정, 문서, QA
- **붐4:** ollama/qwen3-coder:30b-a3b-q4_K_M — 로컬 코딩 (sandbox 없음, 영어 지시 필수)

## API / 잔액

- **DeepSeek 잔액:** ~$47.29 (2026-03-27 기준)
  - API: `https://api.deepseek.com/user/balance`
- **Google Gemini:** gemini-2.5-flash (붐3 기본) / gemini-2.5-flash-lite (폴백)
- **Fallback 모델:** `google/gemini-2.5-flash-lite` (rate limit 시 자동 전환)
- **GitHub Copilot:** 해지됨

## 서버 경로 (맥미니 기준)

- **대시보드:** `/Users/sykim/workspace/openclaw-dashboard/`
- **일일 리포터:** `/Users/sykim/workspace/openclaw-dashboard/daily-reporter.js`
- **리포트 저장:** `/Users/sykim/workspace/openclaw-dashboard/reports/`
- **cloudflared config:** `/Users/sykim/workspace/openclaw-dashboard/cloudflared/config.yml`
- **cloudflared bin:** `/opt/homebrew/bin/cloudflared`

## PM2 프로세스 현황 (맥미니)

| 이름 | 포트 | 역할 |
|------|------|------|
| boom-dashboard | 5173 | 대시보드 서버 |
| cloudflared | - | Named Tunnel (dashboard + evn) |
| ev-highway | 5174 | EV Highway 프론트 |
| ev-highway-api | 3003 | EV Highway API |

## CF Named Tunnel ingress (65c96982)

- dashboard.abamti.com → http://localhost:5173
- evn.abamti.com → http://localhost:5174

## Telegram

- **마스터 chat_id:** 47980209
- **붐 봇 (@abamtibot):** 맥미니 게이트웨이 연결
- **붐2 봇 (occ2_bot):** XPS 붐스 게이트웨이 연결

## 홈페이지 프로젝트 (미래교역)

- **경로:** `/Users/sykim/workspace/mrtrading-project2/`
- **시안-A (sinan-a-v2):** ✅ 완료 (8페이지) — aidev.abamti.com/MRT2026/
- **관리툴 설계서:** mrtrading-admin-tool-*.md (2026-03-28 작성 완료)
- **프리뷰:** `/Users/sykim/workspace/openclaw-dashboard/dist/sinan-preview/`

## 위치 (날씨용)

- 오류2동 (천왕동) — lat 37.4956, lon 126.8900

## 명령어 모음

```bash
# PM2 상태
pm2 list

# 대시보드 재시작
pm2 restart boom-dashboard

# DeepSeek 잔액 확인
curl -s https://api.deepseek.com/user/balance -H "Authorization: Bearer $DEEPSEEK_API_KEY"

# Ollama 모델 목록
ollama list

# 붐4 모델 상태
ollama ps
```

## Git (버전 관리)

- **대시보드 리모트:** `git@github.com:cloud-honey/boom-master-dashboard.git`
- **Push 명령어:**
  ```bash
  GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa" git push
  ```
