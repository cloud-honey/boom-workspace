# MEMORY.md — 핵심 요약 (붐1 장기 메모리)

## 2026-03-28 18:00 KST 오후 일일 리포트 생성 완료
- 크론 자동 실행: daily-reporter-18:00-KST (jobId: 82a58f09-d662-4ff6-a440-2e9a34ab4c15)
- 생성 에이전트: 붐2(deepseek/deepseek-chat)
- 리포트 파일: 
  - HTML: /Users/sykim/workspace/openclaw-dashboard/reports/2026-03-28-afternoon.html
  - MD: /Users/sykim/workspace/openclaw-dashboard/reports/2026-03-28-afternoon.md
- 주요 내용: 날씨(14.6°C), 시장(코스피 5,438.87), 경제(한국은행 금리 인상), AI(OpenAI 상장 준비), 반도체(삼성전자 HBM4)
- 텔레그램 발송 완료 (마스터 47980209)
- index.json 업데이트 완료

## 핵심 정보
- 이름: 승영 김 (마스터)
- 언어: 한국어
- 위치: 오류2동 (천왕동), Seoul · lat 37.4956, lon 126.8900
- 성향: 비개발자 · 모바일 우선 · 자동화 선호

## 2026-03-28 저녁 맥미니 정리 작업
- SOUL.md / AGENTS.md / TOOLS.md 맥미니 기준 전면 정리
- 붐4 역할 QA/테스트로 변경, 모델명 하드코딩 제거
- dashboard.abamti.com XPS DevTeam 코드 제거 + 날씨 기온 null 버그 수정
- 붐4 모델 qwen3-coder:30b-a3b-q4_K_M 확정, 토큰 속도 33.6 t/s
- VSE Sprint 6 QA 완료 (붐4, 8태스크 전체 PASS)
- 붐스/붐 분리 확정: XPS→붐스, 맥미니→붐(@abamtibot)
- rsync 크론 중단 (맥미니 메인 전환 완료)
- 작업 시작 전 컨펌 규칙 추가 (담당/모델/난이도/예상시간)
- 게이트웨이 재시작 반드시 컨펌 후 실행 규칙 추가

## 에이전트 구조
### 메인 그룹 (게이트웨이 18789)
- **붐**: claude-sonnet-4-6 — 마스터 메인 파트너 (@abamtibot, 맥미니)
- **붐스(Booms)**: claude-sonnet-4-6 — XPS 전담, 별도 텔레그램 봇
- **밤티**: openai-codex/gpt-5.4 — 오래 걸리는 반복 작업
- **붐2**: deepseek/deepseek-chat — 복잡한 코딩
- **붐3**: google/gemini-2.5-flash — 단순 수정, 문서, 자동화
- **붐4**: ollama/qwen3-coder:30b-a3b-q4_K_M — QA/테스트 (맥미니, sandbox 없음, 33.6 t/s)
  - 성능 지표 파일: `workspace/reports/boom4-model-performance.md` (모델 교체 시 업데이트)
  - 모델 변경 시: Modelfile FROM 수정 → `ollama create boom4 -f Modelfile` (게이트웨이 재시작 불필요)

### DevTeam 그룹 (게이트웨이 18790, PM2: devteam-gateway)
- 접속: Boomti_bot → devteam-bot(PM2) → 게이트웨이(18790)
- pm(claude-sonnet), analyst(gpt-4o), dev(deepseek-reasoner), qa(gpt-4o)
- arch 비활성 — PM이 설계 직접 처리
- 에스컬레이션: `reports/devteam-escalation.md` (PENDING → 붐 heartbeat 감지)

## XPS 노드 연결 (2026-03-29 확정 / 2026-03-30 서비스 재설치)
- XPS → Tailscale → 맥미니 게이트웨이(18789) 노드로 연결
- systemd 서비스: `~/.config/systemd/user/openclaw-node.service` (user unit, 자동 시작)
- ⚠️ sudo로 `/etc/systemd/system/`에 수동 설치 금지 — 반드시 `openclaw node install` 사용
- 설치/재설치: `openclaw node install --force && openclaw node restart`
- 상태 확인: `openclaw nodes status` / `openclaw node status`
- 어디서든 인터넷만 되면 자동 재연결
- HEARTBEAT에 XPS 게이트웨이 다운 감지 추가됨

## 운영 인프라
- 대시보드: React+Express (5173), proxy: real_openclaw_proxy.js → 5175
- 외부: Cloudflare Quick Tunnel (재시작 시 URL 변경)
- 일일 리포트: 붐3 크론, 매일 07:50 KST, 텔레그램 자동 발송
- 게이트웨이 힙: 메인 4GB, devteam 3.5GB
- CF DNS: abamti.com Zone→DNS Edit 권한 있음 (`~/.openclaw2/deploy/config.env`)

## 프로젝트 현황
| 프로젝트 | 상태 | URL/경로 |
|---|---|---|
| 미래교역 홈페이지 시안-A | ✅ 완료 | aidev.abamti.com/MRT2026/ |
| 미래교역 시안-B/C | ⏳ 진행 중 | mrtrading-project2/sinan-a-v2/ |
| MRHT 마케팅툴 | ✅ v0.1 배포 | mrht.abamti.com |
| T-Board 태블릿 대시보드 | ✅ 배포 | aidev.abamti.com/t-board |
| EV Highway | ✅ v0.2.0 | evn.abamti.com |
| TeslaMate 커스텀 대시보드 | ⏳ 진행 중 | localhost:4002 (PM2 등록 필요) |
| **VSE Platform — Tower Tycoon** | ⏳ Sprint 1 진행 중 | github.com/cloud-honey/vse-platform |

## VSE Platform 현황 (2026-03-25 16:22 KST 업데이트)
### Sprint 1 ✅ 완료
- 10/10 태스크 완료, 142/142 테스트 통과
- Windows 실행 확인 완료 (dist-win/TowerTycoon-Sprint1-Windows.zip)
- 3모델 교차 검증 완료 (DeepSeek V3, GPT-5.4 Thinking, Gemini 3 Flash)
- 보고서: vse-platform/reports/ (SPRINT1_Final_Review_Report.md 포함)

### Sprint 2 ⏳ 진행 중 (4/9 완료)
- TASK-02-001: Bootstrapper 분리 ✅ (붐, 147/147)
- TASK-02-002: 통합 테스트 3종 ✅ (붐2, 150/150)
- TASK-02-003: EconomyEngine int64_t ✅ (붐2, 170/170)
- TASK-02-004: StarRatingSystem ✅ (붐2, 174/174)
- TASK-02-005: NPC 엘리베이터 이동 ✅ (187/187, 3모델 Pass)
- TASK-02-006: SaveLoad MessagePack ✅ (201/201, 3모델 Pass)
- TASK-02-007: ContentRegistry 핫 리로드 ⏳ 붐2 진행 중
- TASK-02-008: 비주얼 개선 (P1, 붐2)
- TASK-02-009: 통합 확인 (8개 누적 액션 있음)

### 공통
- VSE 경로: `/home/sykim/.openclaw/workspace/vse-platform`
- GitHub PAT: `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`
- 대시보드: aidev.abamti.com/vse-dashboard/ (Sprint 탭 S1~S4)

## 붐4 운용 규칙 (2026-03-27 확정)
- 기본 모델: ollama/qwen3-coder:30b-a3b-q4_K_M (sandbox 없음)
- qwen2.5-coder:32b-instruct-q8_0은 서브에이전트 환경 작동 불가 (출력 토큰 극소)
- 테스트 시 원본 파일 절대 수정 금지 — 붐4 산출물은 별도 파일명으로 생성 (예: index-boom4.html)
- 지시 언어: 반드시 영어

## ⚠️ 붐2 운용 교훈 (2026-03-24 확정)
- 붐2 작업 후 반드시: 기존 헤더 파일 손상 여부 git diff 확인
- abstract interface 변경 여부 점검 (EventBus, ConfigManager 피해 선례)
- 복잡한 구현은 붐2 타임아웃 위험 → 붐 직접 처리가 더 빠름

## DevTeam 프로젝트 번호
- 1: MRT2026, 2: MRHT, 3: T-Board
- 명령: `/fix 1 내용`, `/bug 2 내용`, `/feature 3 내용`

## 기술 메모 (핵심)
- 경로: `homepage-project`(원본) · `sinan-preview`(빌드·프리뷰)
- cloudflared 실행파일: `~/.openclaw/workspace/openclaw-dashboard/cloudflared/cloudflared.bin`
- OpenClaw 버전: 2026.3.12
- 메모리 임베딩: Ollama `nomic-embed-text` (로컬, 무료) — 이미 작동 중
- DevTeam PM 워크스페이스: `/home/sykim/.openclaw2/workspace-pm/`
- DevTeam subagents.maxConcurrent: 1 (순차 실행)
- bot_server.py 타임아웃: 3600초

## 일일 리포트 시스템 (2026-03-28 업데이트)
- 크론: daily-reporter-07:30-KST (jobId: d98aa0fc-8089-43ee-92d3-67061b436b91)
- 실행 시간: 매일 07:30 KST 자동 실행
- 생성 에이전트: 붐2(deepseek/deepseek-chat)
- 데이터 수집: KMA 날씨 API, Brave Search 시장/뉴스/AI/반도체 정보
- 출력: HTML 리포트, 마크다운 리포트, index.json 업데이트, 텔레그램 발송
- 리포트 URL: https://dashboard.abamti.com/reports/YYYY-MM-DD.html

## 필수 규칙
1) openclaw.json 수정 전 백업 필수
2) 변경 전 마스터 컨펌
3) 큰 변경은 `memory/YYYY-MM-DD.md` 기록
4) 선택지 나열 금지 — 판단 후 실행
5) 1분 이상 소요 작업은 예상 시간 보고
6) OpenClawDashboard.jsx: Claude로만 수정, 작업 전 컨펌 필수


## aidev.abamti.com 배포 구조 (2026-03-25 확정)
- VSE_Dashboard.html 수정 → vse-platform push → 자동 배포 (boom-master-dashboard 파이프라인)
- 수동 배포: /tmp/ai-devteam-outputs-deploy/ 에서 wrangler 직접 실행
- CF_API_TOKEN: V7ZN9q2_Fupt99Y2nWqjCXeM8wnllkNJemEHlW_o (config.env)
- CF_ACCOUNT_ID: 7a7da39e9a6efc1f56d334c47e4e6b9d
- /tmp 디렉터리 초기화 시: git clone https://GH_PAT@github.com/cloud-honey/ai-devteam-outputs.git /tmp/ai-devteam-outputs-deploy

## 🚨 배포 작업 전 필수 확인 (반복 사고 방지)

### CF Pages 배포 구조
| 도메인 | CF Pages 프로젝트 | 리포 | 서빙 내용 |
|--------|-----------------|------|----------|
| aidev.abamti.com | ai-devteam-outputs | cloud-honey/ai-devteam-outputs | AI DevTeam 허브 + MRT2026/t-board/chess/vse-dashboard |
| dashboard.abamti.com | boom-master-dashboard | cloud-honey/boom-master-dashboard | 붐 마스터 대시보드 (React 빌드) |

### wrangler pages deploy 사용 시 절대 규칙
- `wrangler pages deploy dist --project-name=ai-devteam-outputs` **절대 금지**
  → boom-master-dashboard의 React dist가 ai-devteam-outputs CF Pages를 덮어써서 aidev.abamti.com 전체가 대시보드로 바뀜
- ai-devteam-outputs 배포 시 반드시 **ai-devteam-outputs 리포를 클론 후 해당 폴더만 수정**하여 배포
- 배포 전 `--project-name` 값이 의도한 CF Pages 프로젝트와 일치하는지 반드시 확인

### ai-devteam-outputs 리포 직접 수정 시 주의
- ai-devteam-outputs 리포를 클론/push할 때 **vse-dashboard/ 폴더는 반드시 vse-platform 최신본으로 교체**
  - `VSE_Sprint_Status.json` → `/home/sykim/.openclaw/workspace/vse-platform/VSE_Sprint_Status.json`
  - `index.html` → `/home/sykim/.openclaw/workspace/vse-platform/VSE_Dashboard.html`
- 리포의 vse-dashboard는 구버전일 수 있음 — 그냥 push하면 초기화됨

### 자동 배포 파이프라인 (2026-03-25 수정 완료)
- vse-platform push → boom-master-dashboard `deploy-vse-dashboard.yml` 트리거
- **수정 후**: ai-devteam-outputs 리포 체크아웃 → vse-dashboard/ 파일만 업데이트 → 전체 사이트 배포
- **수정 전 문제**: boom-master-dashboard dist/ 전체를 ai-devteam-outputs에 배포 → 사이트 덮어쓰기

## ⚠️ 미완료 (마스터 직접 필요)
- [ ] **GitHub Pro 요금제 검토** — macOS CI → ubuntu 교체 시 Free 전환 가능. Steam 출시 전까지는 ubuntu로 충분. 나중에 결정 예정.
- [ ] MRHT .env API 키 입력
- [ ] MRHT 네이버 apicenter IP 182.215.36.110 등록
- [ ] UFW 방화벽 활성화 (sudo)
- [ ] TeslaMate PM2 등록 (api:4001, frontend:4002)
- [ ] 게이트웨이 재시작 (밤티 haiku-4-5 적용 + Docker 권한)

## 보관(아카이브)
- `memory/MEMORY-backup-20260321.md` (오늘 압축 전 원본)
- `/home/sykim/backups/openclaw-memory-backup-20260305200859.tar.gz`

## VSE Sprint 2 완료 (2026-03-25 19:52 KST)
- 태스크: 9/9 완료
- 테스트: 215/215
- 최신 커밋: 99856f5
- Windows 빌드: dist-win/TowerTycoon-Sprint2-Windows.zip (27MB)
- 3모델 교차 검증 전 태스크 Pass

## VSE Sprint 3 계획 (2026-03-25 확정)
- 9태스크, 목표: NPC AI 고도화 + 렌더링 품질 + 게임 루프 완성
- 다음 태스크: TASK-03-001 Design Spec v1.5 동기화 (⭐⭐)

## 보고서/교차검증 프로세스 (2026-03-25 확정)
- 완료 보고서: 붐2가 직접 작성 (VSE_AI_Team.md v2.3 양식)
- 교차검증 리뷰: GPT/Gemini/DeepSeek — 문제만 기록, md 파일 결과물
- 붐: 리뷰 수신 → reports/ 저장 → Cross-Validation 표 업데이트 → 이슈 처리
- 예시 파일: reports/TASK-02-003_Review_Report.md

## DeepSeek 모델명 오기입 패턴
- DeepSeek이 리뷰어 필드에 "Claude" 또는 "deepseek (AI)"로 오기입하는 경향 있음
- 마스터가 직접 수정 후 전달하거나 붐이 수신 시 파일명으로 정정

## 2026-03-29 주요 작업 요약
- **HAOS VM** (UTM): IP 192.168.219.177, 외부 접속: https://ha.abamti.com ✅
- **Core HA (PM2)** 제거 완료 — Python venv 삭제
- **XPS 노드** 맥미니 게이트웨이에 연결 (Tailscale, systemd 자동 시작)
- **데일리 리포트** 시장지수 Yahoo Finance API로 교체 (실시간 정확)
- **붐4 벤치마크**: qwen3-coder:30b 46 t/s / 25/30 PASS — 최선 모델 확정
- **deepseek-r1:32b**: 9.1 t/s (단독 GPU), 70b보다 2배 빠름 — 벤치마크 진행 중
- **CF Tunnel**: ha.abamti.com 추가 (cfut 토큰 필요 — MEMORY에 저장 필요)
- **CF cfut 토큰**: cfut_tKJLAKpbXgsqiOEUt729P426qKgrs0CnTpfMNjbv82cfbac4 (Zero Trust 편집 권한)
- **deepseek-r1:32b**: 9.1 t/s (단독 GPU), 70b보다 2배 빠름 — 벤치마크 진행 중

## 2026-03-30 Ollama WebUI + 외부 주소 연결 완료
- Open WebUI 설치 경로: `/Users/sykim/workspace/open-webui`
- 실행 방식: Python 3.12 venv + launchctl 자동 실행
- 로컬 접속: `http://127.0.0.1:8081`
- 외부 접속: `https://ollama.abamti.com`
- cloudflared ingress 추가 완료: `ollama.abamti.com -> http://localhost:8081`
- 붐4 시작 규칙 변경: 작업 전 `ollama ps` 확인, 무관한 무거운 모델 정리 후 진행
- 붐4 기본 모델 준비 확인 기준: `qwen2.5vl-32b-32k`

## 2026-03-31 Cloudflare Tunnel 근본 정리 + paperclip 외부 접속
- **paperclip 설치**: `/Users/sykim/.paperclip/instances/default/`, 포트 3100
- **프록시**: 포트 3101 (`paperclip-proxy.js`, `0.0.0.0` 바인딩)
- **근본 문제 해결**: 원격 관리 터널 → 로컬 관리 터널로 교체
- **새 터널**: `abamti-local` (ID: `7328e0f3-f992-4e84-b28a-4073be403823`)
- **config**: `/Users/sykim/workspace/openclaw-dashboard/cloudflared/config-local.yml`
- **credentials**: `/Users/sykim/.cloudflared/7328e0f3-f992-4e84-b28a-4073be403823.json`
- **cert**: `/Users/sykim/.cloudflared/cert.pem`
- **PM2**: `cloudflared` (config-local.yml 사용)
- **ingress 추가 방법**: config-local.yml 수정 → `pm2 restart cloudflared`
- 기존 터널 `17a5a6f2`, `65c96982`는 폐기 (원격 관리 모드, 로컬 config 무시 문제)

## 2026-04-01 맥미니 DarkWake 잠자기 문제 해결
- 증상: 모든 서버 다운, SSH 접속 불가 (2시간+)
- 원인: macOS DarkWake — caffeinate만으로는 방지 불가
- 해결: `sudo pmset -a displaysleep 10 sleep 0 disksleep 0 powernap 0 womp 1 ttyskeepawake 1 tcpkeepalive 1`
- 모니터는 10분 후 꺼지고, 시스템은 항상 깨어있음

## 2026-04-01 데일리 리포트 시장 데이터 소스 교체
- 코스피: Yahoo Finance → 네이버 금융 API (정확도 높음)
- 미국지수/WTI/금: Yahoo chartPreviousClose → close 배열 기반 전일 종가 계산
- 비트코인: CoinGecko API 신규 추가
- 시장 항목: 5개 → 7개 (코스피, S&P, 나스닥, 다우, WTI, 금, BTC)
- 아침(07:30) + 오후(18:00) 크론 모두 업데이트

## 메모리 작업 기록 규칙 (2026-04-01 추가)
- 매 작업 기록 시 실제 사용 모델명을 `[모델명]` 태그로 표시
- 형식: `## HH:MM KST [모델명] 작업명`
- 예: `## 14:00 KST [opus] 대시보드 버그 수정`
- 폴백 상태에서 코드 수정 시 어떤 모델이 작업했는지 추적 가능

## 2026-03-31 하트비트 비활성화
- **설정**: `agents.defaults.heartbeat.every: "0"` (openclaw.json)
- **이유**: 토큰 누수 — 30분마다 ~57k 토큰 소모 (하루 ~2.7M), 진행 작업 없어도 계속 실행
- **재활성화**: `every: "30m"` → config.patch → 게이트웨이 재시작lare 서버에서 설정 캐시 → 로컬 config 변경 무시
- **해결책**: Node.js 프록시 서버 생성 (포트 3101, `0.0.0.0` 바인딩)
- **프록시 파일**: `/Users/sykim/workspace/openclaw-dashboard/paperclip-proxy.js`
- **cloudflared 설정**: `paperclip.abamti.com -> http://localhost:3101` (config-new.yml)
- **현재 상태**: 
  - ✅ paperclip: 로컬 3100에서 실행 (`127.0.0.1`)
  - ✅ 프록시: 3101에서 실행 (`0.0.0.0`, paperclip 프록시)
  - ⚠️ Cloudflare DNS: API 토큰 권한 문제로 추가 불가 (대시보드 수동 필요)
  - ⚠️ Tunnel ingress: cloudflared가 변경 인식 못함 (대시보드 수동 필요)
- **테스트**: `http://localhost:3101` → ✅ 200 OK
- **담당 에이전트**: DeepSeek (붐2)
