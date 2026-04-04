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
- **붐엘(BoomL)**: MLX 전용 — Gemma 4 26B A4B MoE MLX 4bit + mlx-vlm 0.4.3 (✅ 텔레그램 봇 @boomllm_bot, 69-72 t/s, ~16.8GB VRAM, TurboQuant 3.5bit 활성)

### DevTeam 그룹 (게이트웨이 18790, PM2: devteam-gateway)
- 접속: Boomti_bot → devteam-bot(PM2) → 게이트웨이(18790)
- pm(claude-sonnet), analyst(gpt-4o), dev(deepseek-reasoner), qa(gpt-4o)
- 에스컬레이션: `reports/devteam-escalation.md` (PENDING → 붐 heartbeat 감지)

## 운영 인프라
- **대시보드**: React+Express (5173), proxy: real_openclaw_proxy.js → 5175
- **외부 접속**: Cloudflare Tunnel (abamti-local, ID: 7328e0f3-f992-4e84-b28a-4073be403823)
- **일일 리포트**: 붐2 크론, 매일 07:30 KST + 18:00 KST, 텔레그램 자동 발송
- **게이트웨이 힙**: 메인 4GB, devteam 3.5GB
- **MLX 최적화**: ✅ Gemma 4 26B A4B MoE MLX + mlx-vlm 0.4.3, 69-72 t/s (TurboQuant 3.5bit), 붐엘 @boomllm_bot

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

## 최근 주요 작업 (2026-03-29 ~ 2026-04-04)

### 2026-04-04
- **붐엘 자막 추출 완료**: ssis-313-C 일본어 → 한국어 번역 (ssis-313-C_KO.srt, 9,319줄)
- **붐엘 TurboQuant 3.5bit 활성화**: mlx_vlm 내장 TurboQuant (kv_bits=3.5, kv_quant_scheme="turboquant"), KV 캐시 4.6x 압축
- **붐엘 토큰 통계 수집 수정**: MLXAdapter.generate() → (text, token_stats) 튜플 반환, usage 정상 수집
- **붐엘 /status TurboQuant 표시 수정**: HealthResponse에 turboquant/model_loaded/performance 필드 추가
- **붐엘 번역 웹검색 오라우팅 버그 수정**: 번역 프롬프트가 DuckDuckGo 검색으로 빠지던 버그 → is_system_prompt 조건 추가
- **토큰 절약 설정**:
  - bootstrapTotalMaxChars: 150k → 50k / bootstrapMaxChars → 15k
  - 백업/로그 파일 archives 이동 (~55KB), AGENTS.md 슬림화 (10KB→2KB)
  - 미사용 도구 비활성화: image_generate, tts, canvas, pdf
- **워크스페이스 정리**: 구버전 봇/스크립트/Modelfile/아카이브 → memory/archives/
### 2026-04-03
- **붐엘 Gemma 4 26B A4B MoE MLX 모델 업그레이드 완료**:
  - 모델: `mlx-community/gemma-4-26b-a4b-it-4bit` (26B Mixture of Experts)
  - 용량: 14GB 다운로드 완료 (3개 safetensors 파일)
  - 라이브러리: mlx-vlm 0.4.3 설치 (mlx-lm 0.31.1은 Gemma 4 미지원)
  - 성능: 74.354 tokens/sec, 16.5GB VRAM 사용
  - 아키텍처: 8개 전문가 MoE, 2개 활성화
  - 서버: `booml-mlx/server_v3_postgres_router.py` (포트 8000)
  - 봇: `booml-telegram-bot/booml-bot-v2-enhanced.py` (@boomllm_bot)
  - 응답 품질: 한국어 지원, 고품질 MoE 아키텍처

- **붐엘 피드백 시스템 구현 완료**:
  - 피드백 API: `/v1/feedback` 엔드포인트
  - 버튼 피드백: 👍 좋아요 / 👎 싫어요
  - 텍스트 피드백: 키워드 기반 자동 감지
  - 세션 관리: `user_id` → `session_id` 자동 매핑

- **붐엘 실시간 웹 검색 기능 추가**:
  - 검색 엔진: DuckDuckGo HTML 파싱
  - 검색 감지: 키워드 기반 자동 실행
  - 실시간 데이터: 주식, 날씨, 뉴스 통합
  - 검색 키워드: "검색", "찾아", "알려", "뭐야", 질문 형태 등

### 2026-04-01
- **데일리 리포트 시장 데이터 소스 교체**: 코스피(네이버 금융), 비트코인(CoinGecko) 추가
- **맥미니 DarkWake 잠자기 문제 해결**: `sudo pmset -a displaysleep 10 sleep 0 disksleep 0 powernap 0 womp 1 ttyskeepawake 1 tcpkeepalive 1`
- **대시보드 히스토리 버그 수정**: content 파싱 빈줄 버그, __INITIAL_STATE__ 주입 수정

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

## 하트비트 설정 (2026-04-01 MLX 전환)
- **모델**: booml-mlx/booml-mlx (Qwen3-14B-MLX-4bit, 로컬, 무료)
- **간격**: 30분 (`agents.defaults.heartbeat.every: "30m"`)
- **로그**: `logs/heartbeat.log` (매 실행마다 1줄 append)
- **체크 항목**: XPS 노드 상태, 모델 폴백 감지, DevTeam 에스컬레이션
- **MLX 서버**: localhost:8000 (server_v2.py)

## 로컬 LLM 전략 (2026-04-03)
- **MLX (mlx-vlm)**: Gemma 4 26B A4B MoE 모델 (붐엘 메인)
- **Ollama**: 임베딩 전용 (nomic-embed-text, memorySearch)
- **booml-mlx 프로바이더**: openclaw.json에 등록됨 (localhost:8000/v1)
- **성능**: 74.354 tokens/sec (Gemma 4 26B MoE MLX)
- **기능**: 실시간 검색, 피드백 시스템, 텔레그램 통합

## 붐엘 공통 규칙 (2026-04-02 추가)
- 붐엘 규칙은 세션 대화로만 두지 말고 장기 메모리와 구현 로직에 함께 남길 것.
- 새 규칙이 생길 때마다 문장을 계속 덧붙이는 방식은 지양.
- 우선 **상위 원칙**으로 묶고, 세부 차이는 **데이터 처리 로직**에서 해결하는 구조를 유지.
- 시간 민감 정보(주식/지수/환율/코인/날씨 등)는 사용자가 시간을 따로 말하지 않으면 기본을 **현재/오늘/지금 기준**으로 해석.
- 전일 종가/장마감 수치/오래된 데이터를 현재처럼 말하면 안 됨.
- 최신 시각을 알 수 있으면 답변에 짧게 기준 시각을 붙일 것. 예: `14:45 기준`
- 장중/장마감/프리마켓/애프터마켓/현재가 없음 같은 상태를 숨기지 말고 명시.
- 특정 자산(코스피만 등) 개별 규칙으로 늘리지 말고, **시장 데이터 전반 공통 규칙**으로 관리.
- 날씨도 동일 원칙 적용: 시간 표현이 없으면 오늘 날씨 또는 현재 날씨로 해석.