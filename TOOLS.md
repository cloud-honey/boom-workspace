# TOOLS.md - 시스템 설정 메모

## 붐 마스터 대시보드
- **URL (내부):** http://localhost:5173
- **URL (외부):** https://dashboard.abamti.com
- **PM2 프로세스:** `boom-dashboard` (port 5173), `cloudflared` (터널 관리)

## 에이전트 역할
- **붐 (나):** claude-sonnet-4-6 — 방향 판단, 지시, 감수
- **밤티:** openai-codex/gpt-5.4 — QA, 반복 작업 전담
- **붐2:** deepseek/deepseek-chat — 복잡한 코딩, 로직 분석
- **붐3:** google/gemini-2.5-flash — 단순 수정, 문서, 자동화
- **붐4:** ollama/qwen3-coder:30b-a3b-q4_K_M — QA/테스트 (sandbox 없음, 영어 지시 필수)
- **붐엘:** booml-mlx/booml-mlx (Qwen3-14B-MLX-4bit) — 하트비트, 로컬 LLM 전용 (localhost:8000)

## API / 잔액
- **DeepSeek 잔액:** ~$47.29 (2026-03-27 기준) — API: `https://api.deepseek.com/user/balance`
- **Google Gemini:** gemini-2.5-flash (붐3 기본) / gemini-2.5-flash-lite (폴백)
- **GitHub Copilot:** 해지됨

## 서버 경로 (맥미니 기준)
- **대시보드:** `/Users/sykim/workspace/openclaw-dashboard/`
- **일일 리포터:** `/Users/sykim/workspace/openclaw-dashboard/daily-reporter.js`
- **리포트 저장:** `/Users/sykim/workspace/openclaw-dashboard/reports/`
- **cloudflared config:** `/Users/sykim/workspace/openclaw-dashboard/cloudflared/config-local.yml`

## PM2 프로세스 현황
| 이름 | 포트 | 역할 |
|------|------|------|
| boom-dashboard | 5173 | 대시보드 서버 |
| cloudflared | - | CF Tunnel 로컬관리 |
| ev-highway | 5174 | EV Highway 프론트 |
| ev-highway-api | 3003 | EV Highway API |

## Cloudflare Tunnel (로컬 관리)
- **활성 터널:** `abamti-local` (ID: `7328e0f3-f992-4e84-b28a-4073be403823`)
- **관리 방식:** 로컬 (config-local.yml이 유일한 설정 소스)
- **ingress 추가:** config-local.yml 수정 → `pm2 restart cloudflared`

### 주요 ingress
| hostname | service |
|----------|---------|
| dashboard.abamti.com | http://localhost:5173 |
| evn.abamti.com | http://localhost:5174 |
| ha.abamti.com | http://192.168.219.177:8123 |
| ollama.abamti.com | http://localhost:8081 |
| paperclip.abamti.com | http://localhost:3101 |
| occ.abamti.com | http://localhost:18789 |

## Telegram
- **마스터 chat_id:** 47980209
- **붐 봇 (@abamtibot):** 맥미니 게이트웨이 연결
- **붐2 봇 (occ2_bot):** XPS 붐스 게이트웨이 연결

## 홈페이지 프로젝트 (미래교역)
- **경로:** `/Users/sykim/workspace/mrtrading-project2/`
- **시안-A:** ✅ 완료 — aidev.abamti.com/MRT2026/
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

# Ollama 모델 상태
ollama ps

# cloudflared 재시작
pm2 restart cloudflared
```

## Git
- **대시보드 리모트:** `git@github.com:cloud-honey/boom-master-dashboard.git`
- **Push 명령어:** `GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa" git push`