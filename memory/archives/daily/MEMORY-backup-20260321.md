# MEMORY.md — 핵심 요약 (붐1 장기 메모리)

## 핵심 정보
- 이름: 승영 김 (마스터)
- 언어: 한국어
- 위치: 오류2동 (천왕동), Seoul
- 성향: 비개발자 · 모바일 우선 · 자동화 선호

## 운영 요약
- 대시보드: React + Express (포트 5173), proxy: real_openclaw_proxy.js → 5175
- 외부 접속: Cloudflare Quick Tunnel (임시 URL, 재시작 시 변경)
- 일일 리포트: 텔레그램 자동 발송 (매일 07:50) — 2026-03-07부터 매일로 변경
- 리포트 HTML: 다크 테마 카드/테이블 디자인, 대시보드 모달에서 iframe 렌더링
- 주요 프로젝트: 미래교역 홈페이지 (시안 A/B/C) — 시안-A 완료, B/C 작업 중
- 경로: `~/workspace/homepage-project/` · 프리뷰: `~/workspace/openclaw-dashboard/dist/sinan-preview/`

## 에이전트 구조 (2026-03-13 마스터 확정, 23:48 업데이트)

### 메인 그룹 (게이트웨이 18789)
- **붐**: claude-sonnet-4.6 — 마스터 메인 파트너, 조율/결정/감수
- **밤티**: gemini-2.5-flash — 붐과 동급 협업 에이전트 (서브 아님)
- **붐2**: DeepSeek-chat — 붐·밤티가 쓰는 서브에이전트, 복잡한 코딩
- **붐3**: gpt-4o / gpt-5-mini — 붐·밤티가 쓰는 서브에이전트, QA·단순작업
- **붐4**: ollama/qwen2.5-coder:7b (로컬) — 붐·밤티가 쓰는 서브에이전트, 로컬 코딩

### DevTeam 그룹 (게이트웨이 18790, PM2: devteam-gateway)
- **완전히 별도 팀** — 붐/밤티와 독립적으로 운영
- **pm**: PM 에이전트 (팀장, 마스터와 Boomti_bot으로 소통)
- **analyst**: 요구사항 분석
- **arch**: 아키텍처 설계
- **dev**: 개발 구현
- **qa**: 품질 보증
- **접속**: Boomti_bot(텔레그램) → devteam-bot(PM2) → DevTeam 게이트웨이(18790)
- 외부 서비스: GitHub Copilot, DeepSeek, Google Gemini (토큰/잔액은 별도 확인)

## 필수 규칙 (짧게)
1) openclaw.json 수정 전 백업: `cp ~/.openclaw/openclaw.json ~/.openclaw.openclaw.json.bak.$(date +%Y%m%d%H%M%S)`
2) 변경 전 반드시 마스터 컨펌
3) 큰 변경(설정·배포)은 `memory/YYYY-MM-DD.md`에 기록
4) 선택지 나열 금지 — 판단 후 실행
5) 1분 이상 소요 작업은 예상 시간 보고

## 2026-03-13 주요 변경사항

### Cloudflare DNS 권한
- CF API 토큰에 Zone→DNS Edit 권한 추가됨
- 이제 붐이 abamti.com DNS 직접 컨트롤 가능
- 설정: `/home/sykim/.openclaw2/deploy/config.env` (CF_ZONE_ID 포함)

### Boom AI DevTeam 정식 명칭 확정
- 풀 네임: **Boom AI DevTeam** (마스터 확인)
- DevTeam 서브도메인: aidev.abamti.com
- GitHub 레포: cloud-honey/ai-devteam-outputs
- PM이 작업 완료 시 aidev.abamti.com/[폴더명]/ 으로 배포 후 보고

### Boom AI DevTeam 운영 개선 (2026-03-13)
- arch 에이전트 비활성화 → PM(claude-sonnet)이 설계 직접 처리
- subagents.maxConcurrent: 2 → 1 (순차 실행 강제, rate limit 방지)
- PM bot_server.py 타임아웃: 300초 → 3600초 (밤새 작업 대비)
- 분업 실패 에스컬레이션 프로세스 구축:
  - PM → Boomti_bot 보고 + reports/devteam-escalation.md 기록
  - 붐이 heartbeat에서 감지 → 해결책 → 마스터 보고
- QA 의무화: 배포 전 반드시 qa 에이전트 테스트 후 배포
- DevTeam 에이전트 모델:
  - pm: anthropic/claude-sonnet-4-6
  - analyst: github-copilot/gpt-4o
  - arch: github-copilot/gpt-4o (비활성, PM 직접 처리)
  - dev: deepseek/deepseek-reasoner
  - qa: github-copilot/gpt-4o

### 밤티 모델 변경
- 변경: github-copilot/gpt-4o → anthropic/claude-haiku-4-5
- 폴백: google/gemini-2.5-flash (유지)

## 기술 메모 (핵심)
- 디렉토리: `homepage-project`(원본) / `sinan-preview`(빌드·프리뷰)
- sinan-a 모바일 헤더: 전 페이지 `@media(max-width:768px){nav{display:none}.header-right{display:none}}` 적용 완료
- mask_products.html: pj.abamti.com/sinan-a/mask_products.html (Mask 카테고리 6개 제품)
- cloudflared 실행파일: `~/.openclaw/workspace/openclaw-dashboard/cloudflared/cloudflared.bin`
- cloudflared 로그: `~/.openclaw/workspace/openclaw-dashboard/cloudflared/cloudflared_quick.log`
- heartbeat: 밤티 HEARTBEAT_OK/ANNOUNCE_SKIP 상태엔 무응답 알림 없음 (2026-03-07 수정)
- **밤티 모델: anthropic/claude-haiku-4-5** (2026-03-13 변경, 폴백: gemini-2.5-flash) ← 메인 게이트웨이 재시작 아직 미완료
- 일일 리포트 크론: 매일 07:50 KST (2026-03-07부터 평일→매일 변경)
- OpenClaw 버전: 2026.3.12 (2026-03-13 업데이트 완료)

## Boom AI DevTeam 핵심 설정 (2026-03-13 확정)
- PM 워크스페이스: `/home/sykim/.openclaw2/workspace-pm/`
- PM SOUL.md 규칙:
  - `/fix` → dev 직행 (단순 버그)
  - `/bug` → dev+qa (분석 필요)
  - `/feature` → analyst→dev→qa
  - 완료 보고 시 파일 경로+수정전후 증거 필수, 없으면 반려
  - arch 호출 금지 — PM이 직접 설계
  - 서브에이전트 순차 실행 (동시 호출 금지)
- bot_server.py 타임아웃: 3600초 (1시간)
- subagents.maxConcurrent: 1
- 에스컬레이션 파일: `/home/sykim/.openclaw/workspace/reports/devteam-escalation.md`
- MRT2026 배포 URL: https://aidev.abamti.com/MRT2026/
- CF DNS 토큰: Zone→DNS Edit 권한 있음 (config.env)

## 2026-03-14 주요 변경사항

### 작업 컨펌 규칙 전면 적용
- 붐·밤티·데브팀 PM 공통: 작업 전 계획 보고 → 컨펌 후 시작 → 완료 보고 필수
- 밤티 SOUL.md, PM SOUL.md 수정 완료

### 데브팀 완료 보고 구조 수정
- PM 완료 보고: stdout 포함 방식 (curl 타이밍 문제 해결)
- bot_server.py: 완료 키워드 감지 시 붐 메인 채팅으로도 포워딩
- Boomti_bot /명령어 오인식 수정 (경로·URL이 명령어로 처리되던 버그)

### 대시보드 개선
- 세션 데이터: CLI 타임아웃 → 파일 직접 읽기 (에이전트 카드 정상화)
- 리포트/히스토리: 2뎁스 아코디언 → 1뎁스 + 모달 방식으로 변경

### MRHT 자동화 마케팅 툴 (신규 프로젝트)
- 경로: ~/mrht-auto/
- 배포: https://mrht.abamti.com (v0.1.00)
- 기능: 쿠팡/네이버 API + Claude AI 상품명 최적화 + 경쟁사 크롤링
- ⚠️ 마스터 직접: .env API키 입력, 네이버 IP 182.215.36.110 등록

## 내일 할 일 (2026-03-15)
- [ ] 체스앱 AI 기능 완료 여부 검증 (pj.abamti.com/chess/)
- [ ] MRHT .env API 키 입력 (마스터 직접)
- [ ] MRHT 네이버 apicenter에서 IP 182.215.36.110 등록 (마스터 직접)
- [ ] 메인 게이트웨이 재시작 (밤티 haiku-4-5 적용)
- [ ] UFW 방화벽 활성화 (sudo 필요, 마스터 직접 실행)

---
(오래된 중복 로그 및 상세 일시별 작업 메모는 `memory/YYYY-MM-DD.md`에 보관됩니다.)

## 보관(아카이브)
- 아카이브 파일(원본 삭제됨): `memory/archives/memory-backup-20260305200859.tar.gz`
- 보관(영구 백업, OpenClaw 삭제 영향 없음): `/home/sykim/backups/openclaw-memory-backup-20260305200859.tar.gz`

<!--
보관된 파일 목록:
- memory/2026-03-02.md
- memory/2026-03-03.md
- memory/2026-03-04.md
- memory/2026-03-05-0915.md
- memory/2026-03-05-1053.md
- memory/2026-03-05-bug-fix.md

압축 해제(복구) 명령 예시: (마스터가 요청할 때만 실행)
```bash
# 작업 디렉토리로 이동 후 압축 해제
cd ~/workspace/memory
tar -xzf archives/memory-backup-20260305200859.tar.gz -C .
```

주의: 위 명령은 아카이브를 현재 memory 폴더로 풀어 원본 파일을 복원합니다. 설정 초기화나 검토가 필요할 때만 실행하세요.
-->


## 2026-03-05 20:56 KST — 대시보드 복구 지침 (수정)

주의: OpenClawDashboard.jsx 는 Gemini 수정 금지, Claude로만 작업, 작업전에 마스터에게 시작해도 될지 확인후 시작

Source: user request 2026-03-05 20:56 KST

## 2026-03-15 주요 변경사항

### 크론 정리
- 하트비트 크론 삭제 (밤티 세션 누적 방지, 붐 하트비트로 통합)
- 일일 리포트 크론: 붐3 고정, 동적 모델명(session_status), 실패 분석 보고, bestEffort

### 붐3 모델 변경
- github-copilot/gpt-5-mini → github-copilot/gpt-4o (21:27 재시작으로 적용됨)

### 게이트웨이 힙 메모리 4GB 설정
- 메인 게이트웨이: systemd 서비스에 --max-old-space-size=4096 추가
- devteam-gateway: PM2 --max-old-space-size=4096, 한도 3.5GB
- 원인: 힙 부족 → GC 압박 → 세션 락 타임아웃 / 반복 재시작

### DevTeam run_devteam.sh 수정
- call_agent(): OPENCLAW_HOME → OPENCLAW_CONFIG_PATH=~/.openclaw2/openclaw2.json
- 원인: openclaw2.json 파일명 불일치로 메인 게이트웨이로 fallback → analyst/arch 없음 오류

### DevTeam 프로젝트 번호 시스템
- 1: MRT2026, 2: MRHT, 3: T-Board
- /fix 1 내용, /bug 2 내용, /feature 3 내용 형식
- bot_server.py 수정, devteam-bot 재시작

### T-Board 프로젝트 신규 시작 (2026-03-15)
- URL: aidev.abamti.com/t-board
- 태블릿 상시 모니터링 대시보드 (11인치 안드로이드)
- 밤 화면 꺼짐, Wake Lock, 전체화면, 새로고침 간격 선택
- 백엔드: mrht-auto Flask 서버 /tboard/* 라우트

## 2026-03-18 EV Highway v0.2.0 완료

- SK일렉링크 실시간 연동 완료 (전국 고속도로 60개 충전소 KEY 매핑)
- route-chargers API 신설 (`/api/highway/route-chargers`)
- 충전기 팝업: 전체화면 레이어 방식으로 전환 (스크롤 해결)
- KECO 캐시 TTL: 개발 중 1시간 / 프로덕션 60초
- 429 한도 초과 시: SK 실데이터 + 얼럿 표시 (isMock 제거)
- dataSources + cacheInfo + 갱신 시각 팝업 표시
- 배포: evn.abamti.com v0.2.0 / git: 1bc3dee
- ⚠️ 환경공단 API 일일 한도 소진 → 자정 리셋 후 정상
