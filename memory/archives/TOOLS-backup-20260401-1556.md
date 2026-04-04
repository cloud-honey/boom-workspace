# TOOLS.md - 시스템 설정 메모

## 붐 마스터 대시보드

- **URL (내부):** http://localhost:5173
- **URL (외부):** https://dashboard.abamti.com (Cloudflare Tunnel)
- **PM2 프로세스:** `boom-dashboard` (port 5173), `cloudflared` (로컬 관리 터널)
- **터널 config:** `/Users/sykim/workspace/openclaw-dashboard/cloudflared/config-local.yml`

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
- **cloudflared config:** `/Users/sykim/workspace/openclaw-dashboard/cloudflared/config-local.yml`
- **cloudflared credentials:** `/Users/sykim/.cloudflared/7328e0f3-f992-4e84-b28a-4073be403823.json`
- **cloudflared cert:** `/Users/sykim/.cloudflared/cert.pem`
- **cloudflared bin:** `/opt/homebrew/bin/cloudflared`

## PM2 프로세스 현황 (맥미니)

| 이름 | 포트 | 역할 |
|------|------|------|
| boom-dashboard | 5173 | 대시보드 서버 |
| cloudflared | - | CF Tunnel 로컬관리 (config-local.yml) |
| ev-highway | 5174 | EV Highway 프론트 |
| ev-highway-api | 3003 | EV Highway API |

## Cloudflare Tunnel (로컬 관리 — 2026-03-31 정리 완료)

### 터널 정보
- **활성 터널:** `abamti-local` (ID: `7328e0f3-f992-4e84-b28a-4073be403823`)
- **관리 방식:** 로컬 (config-local.yml이 유일한 설정 소스)
- **PM2:** `cloudflared` (자동 실행)
- **폐기 터널:** `17a5a6f2` (abamti-tunnel), `65c96982` (boom-master-tunnel) — 원격 관리 모드, 사용 안 함

### 현재 ingress (config-local.yml)

| hostname | service | 비고 |
|----------|---------|------|
| dashboard.abamti.com | http://localhost:5173 | 붐 마스터 대시보드 |
| evn.abamti.com (path: /api/) | http://localhost:3003 | EV Highway API |
| evn.abamti.com | http://localhost:5174 | EV Highway 프론트 |
| ha.abamti.com | http://192.168.219.177:8123 | Home Assistant |
| ollama.abamti.com | http://localhost:8081 | Open WebUI |
| paperclip.abamti.com | http://localhost:3101 | paperclip (프록시 경유) |
| occ.abamti.com | http://localhost:18789 | OpenClaw 게이트웨이 |
| ec.abamti.com | http://localhost:3001 | EC 프로젝트 |
| ec-dev.abamti.com | http://localhost:3002 | EC 개발 |
| mrht.abamti.com | http://localhost:5000 | MRHT 마케팅툴 |
| pj.abamti.com | http://localhost:8080 | PJ 사이트 |
| tboard-api.abamti.com | http://localhost:5002 | T-Board API |
| (catch-all) | http_status:404 | 미등록 호스트 → 404 |

### ⚠️ 새 서비스 추가/변경 시 필수 절차

```bash
# 1. config 수정
vi /Users/sykim/workspace/openclaw-dashboard/cloudflared/config-local.yml

# 2. DNS CNAME 추가 (새 서브도메인인 경우)
# API 토큰: V7ZN9q2_Fupt99Y2nWqjCXeM8wnllkNJemEHlW_o
# Zone ID: c11c0d3d41695c14bc0ac42bffc72432
curl -X POST "https://api.cloudflare.com/client/v4/zones/c11c0d3d41695c14bc0ac42bffc72432/dns_records" \
  -H "Authorization: Bearer V7ZN9q2_Fupt99Y2nWqjCXeM8wnllkNJemEHlW_o" \
  -H "Content-Type: application/json" \
  --data '{"type":"CNAME","name":"NEW_NAME.abamti.com","content":"7328e0f3-f992-4e84-b28a-4073be403823.cfargotunnel.com","proxied":true,"ttl":1}'

# 3. cloudflared 재시작
pm2 restart cloudflared

# 4. 확인
curl -s -o /dev/null -w "%{http_code}" https://NEW_NAME.abamti.com
```

### 🚨 절대 하면 안 되는 것
- `config.yml` 또는 `config-new.yml` 사용 금지 — 이건 폐기된 원격 관리 터널 설정
- `65c96982` 또는 `17a5a6f2` 터널 ID로 실행 금지 — 원격 설정이 로컬을 덮어씀
- **반드시 `config-local.yml`만 사용**

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

# cloudflared 상태/재시작
pm2 show cloudflared
pm2 restart cloudflared

# 터널 ingress 설정 확인
cat /Users/sykim/workspace/openclaw-dashboard/cloudflared/config-local.yml

# 터널 연결 상태 확인
/opt/homebrew/bin/cloudflared tunnel list
```

## Git (버전 관리)

- **대시보드 리모트:** `git@github.com:cloud-honey/boom-master-dashboard.git`
- **Push 명령어:**
  ```bash
  GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa" git push
  ```
