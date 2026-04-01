# MEMORY.md — 핵심 요약 (붐1 장기 메모리)

## 핵심 정보
- **이름**: 승영 김 (마스터)
- **언어**: 한국어
- **위치**: 오류2동 (천왕동), Seoul · lat 37.4956, lon 126.8900
- **성향**: 비개발자 · 모바일 우선 · 자동화 선호

## 에이전트 구조 (2026-03-28 확정)
### 메인 그룹 (게이트웨이 18789)
- **붐**: claude-sonnet-4-6 — 마스터 메인 파트너 (@abamtibot, 맥미니)
- **붐스(Booms)**: claude-sonnet-4-6 — XPS 전담, 별도 텔레그램 봇
- **밤티**: openai-codex/gpt-5.4 — 오래 걸리는 반복 작업
- **붐2**: deepseek/deepseek-chat — 복잡한 코딩
- **붐3**: google/gemini-2.5-flash — 단순 수정, 문서, 자동화
- **붐4**: ollama/qwen3-coder:30b-a3b-q4_K_M — QA/테스트 (맥미니, sandbox 없음, 33.6 t/s)
- **붐엘(BoomL)**: MLX 전용 — Qwen3-14B-MLX-4bit + TurboQuant 4bit KV캐시 (✅ 텔레그램 봇 @boomllm_bot, 실시간 검색/날씨 지원)

### DevTeam 그룹 (게이트웨이 18790, PM2: devteam-gateway)
- 접속: Boomti_bot → devteam-bot(PM2) → 게이트웨이(18790)
- pm(claude-sonnet), analyst(gpt-4o), dev(deepseek-reasoner), qa(gpt-4o)
- 에스컬레이션: `reports/devteam-escalation.md` (PENDING → 붐 heartbeat 감지)

## 운영 인프라
- **대시보드**: React+Express (5173), proxy: real_openclaw_proxy.js → 5175
- **외부 접속**: Cloudflare Tunnel (abamti-local, ID: 7328e0f3-f992-4e84-b28a-4073be403823)
- **일일 리포트**: 붐2 크론, 매일 07:30 KST + 18:00 KST, 텔레그램 자동 발송
- **게이트웨이 힙**: 메인 4GB, devteam 3.5GB
- **MLX 최적화**: ✅ Qwen3-14B + TurboQuant 4bit KV캐시, 실시간 검색/날씨, 붐엘 @boomllm_bot

## XPS 노드 연결 (2026-03-29 확정)
- XPS → Tailscale → 맥미니 게이트웨이(18789) 노드로 연결
- systemd 서비스: `~/.config/systemd/user/openclaw-node.service` (user unit)
- 설치: `openclaw node install --force && openclaw node restart`
- HEARTBEAT에 XPS 게이트웨이 다운 감지 추가됨

## 프로젝트 현황
| 프로젝트 | 상태 | URL/경로 |
|---|---|---|
| 미래교역 홈페이지 시안-A | ✅ 완료 | aidev.abamti.com/MRT2026/ |
| 미래교역 시안-B/C | ⏳ 진행 중 | mrtrading-project2/sinan-a-v2/ |
| MRHT 마케팅툴 | ✅ v0.1 배포 | mrht.abamti.com |
| T-Board 태블릿 대시보드 | ✅ 배포 | aidev.abamti.com/t-board |
| EV Highway | ✅ v0.2.0 | evn.abamti.com |
| TeslaMate 커스텀 대시보드 | ⏳ 진행 중 | localhost:4002 (PM2 등록 필요) |
| **VSE Platform — Tower Tycoon** | ⏳ Sprint 3 진행 중 | github.com/cloud-honey/vse-platform |

## VSE Platform 현황 (2026-03-25)
- **Sprint 1**: ✅ 10/10 태스크 완료, 142/142 테스트 통과
- **Sprint 2**: ✅ 9/9 태스크 완료, 215/215 테스트 통과
- **Sprint 3**: ⏳ 9태스크 진행 중 (NPC AI 고도화 + 렌더링 품질 + 게임 루프 완성)
- **경로**: `/home/sykim/.openclaw/workspace/vse-platform`
- **대시보드**: aidev.abamti.com/vse-dashboard/

## 붐4 운용 규칙
- **기본 모델**: ollama/qwen3-coder:30b-a3b-q4_K_M (sandbox 없음)
- **지시 언어**: 반드시 영어
- **작업 전**: `ollama ps` 확인, 무관한 무거운 모델 정리 후 진행
- **테스트 시**: 원본 파일 절대 수정 금지 — 붐4 산출물은 별도 파일명으로 생성

## 필수 규칙
1. **openclaw.json 수정 전** 백업 필수
2. **변경 전** 마스터 컨펌
3. **작업 시작 전** 컨펌 보고 형식:
   ```
   담당: [에이전트명] ([실제 모델명])
   난이도: 하 / 중 / 상
   예상 시간: X분
   ```
4. **게이트웨이 재시작** 반드시 컨펌 후 실행
5. **폴백 발생 시**: 답변 맨 앞에 `⚠️[실제모델명]` 표시

## Cloudflare Tunnel (2026-03-31 정리 완료)
- **활성 터널**: `abamti-local` (ID: `7328e0f3-f992-4e84-b28a-4073be403823`)
- **관리 방식**: 로컬 (config-local.yml이 유일한 설정 소스)
- **PM2**: `cloudflared` (자동 실행)
- **ingress 추가**: config-local.yml 수정 → `pm2 restart cloudflared`

### 현재 ingress
| hostname | service |
|----------|---------|
| dashboard.abamti.com | http://localhost:5173 |
| evn.abamti.com (path: /api/) | http://localhost:3003 |
| evn.abamti.com | http://localhost:5174 |
| ha.abamti.com | http://192.168.219.177:8123 |
| ollama.abamti.com | http://localhost:8081 |
| paperclip.abamti.com | http://localhost:3101 |
| occ.abamti.com | http://localhost:18789 |
| ec.abamti.com | http://localhost:3001 |
| ec-dev.abamti.com | http://localhost:3002 |
| mrht.abamti.com | http://localhost:5000 |
| pj.abamti.com | http://localhost:8080 |
| tboard-api.abamti.com | http://localhost:5002 |

## 최근 주요 작업 (2026-03-29 ~ 2026-04-01)
### 2026-04-01
- **데일리 리포트 시장 데이터 소스 교체**: 코스피(네이버 금융), 비트코인(CoinGecko) 추가
- **맥미니 DarkWake 잠자기 문제 해결**: `sudo pmset -a displaysleep 10 sleep 0 disksleep 0 powernap 0 womp 1 ttyskeepawake 1 tcpkeepalive 1`
- **대시보드 히스토리 버그 수정**: content 파싱 빈줄 버그, __INITIAL_STATE__ 주입 수정
- **붐엘 Qwen3-14B 업그레이드 + TurboQuant + 실시간 검색**:
  - Qwen2.5-7B → Qwen3-14B-MLX-4bit (품질 대폭 향상)
  - KV캐시 4bit 양자화 (mlx-lm 네이티브 kv_bits, 4.6x 메모리 절약)
  - 실시간 웹 검색 (DuckDuckGo) + 날씨 (wttr.in) 추가
  - 시스템 프롬프트에 현재 날짜/시간 주입
  - 서버: `booml-mlx/server_v2.py`, 봇: `booml-telegram-bot/booml-bot-v2.py`
  - 속도: ~16 t/s (14B 모델 + KV양자화)

### 2026-03-31
- **Cloudflare Tunnel 근본 정리**: 원격 관리 터널 → 로컬 관리 터널 교체
- **paperclip 외부 접속**: 프록시 서버(3101) + cloudflared ingress 추가

### 2026-03-30
- **Ollama WebUI 외부 접속**: ollama.abamti.com → http://localhost:8081

### 2026-03-29
- **HAOS VM**: IP 192.168.219.177, 외부 접속: https://ha.abamti.com
- **XPS 노드**: 맥미니 게이트웨이에 연결 완료

## 메모리 작업 기록 규칙 (2026-04-01 추가)
- 매 작업 기록 시 실제 사용 모델명을 `[모델명]` 태그로 표시
- 형식: `## HH:MM KST [모델명] 작업명`
- 예: `## 14:00 KST [opus] 대시보드 버그 수정`

## ⚠️ 미완료 (마스터 직접 필요)
- [ ] MRHT .env API 키 입력
- [ ] MRHT 네이버 apicenter IP 182.215.36.110 등록
- [ ] UFW 방화벽 활성화 (sudo)
- [ ] TeslaMate PM2 등록 (api:4001, frontend:4002)

## 하트비트 설정 (2026-03-31)
- **모델**: ollama/Qwen3:8b (로컬, 무료)
- **간격**: 30분 (`agents.defaults.heartbeat.every: "30m"`)
- **로그**: `logs/heartbeat.log` (매 실행마다 1줄 append)
- **체크 항목**: XPS 노드 상태, 모델 폴백 감지, DevTeam 에스컬레이션