# MEMORY.md — 핵심 요약

## 마스터
- 승영 김 · 한국어 · 오류2동(천왕동) lat 37.4956, lon 126.8900
- 비개발자 · 모바일 우선 · 자동화 선호 · Claude Max 요금제 (토큰 절약 중요)
- **맥미니: Apple M4 Pro · 64GB 통합 메모리**

## 에이전트
| 에이전트 | 모델 | 역할 |
|---------|------|------|
| 붐 | claude-sonnet-4-6 | 메인 (@abamtibot, 맥미니) |
| 붐스 | claude-sonnet-4-6 | XPS 전담 |
| 밤티 | gpt-5.4 | 반복 작업 |
| 붐2 | deepseek-chat | 코딩 구현 |
| 붐3 | gemini-2.5-flash | 단순 수정/문서 |
| 붐4 | qwen3-coder:30b | QA/테스트 (영어 지시) |
| 붐엘 | booml-mlx (Gemma 4 26B MoE) | 로컬 LLM @boomllm_bot |

DevTeam: 게이트웨이 18790, PM2: devteam-gateway

## 붐엘 현황 (2026-04-04)
- 모델: `mlx-community/gemma-4-26b-a4b-it-4bit` · mlx-vlm 0.4.3
- 속도: 69-72 t/s · VRAM ~16.8GB · TurboQuant 3.5bit (4.6x 압축) · max_tokens 2048

| 에이전트 | 봇 | PM2 | 포트 | 봇 스크립트 |
|---------|-----|-----|------|-----------|
| 붐엘 | @boomllm_bot | booml-telegram-bot(18) / booml-mlx-server(17) | 8000 | booml-bot-v2-enhanced.py |
| 붐엘2 | (별도) | booml-chat-bot(22) / booml-mlx-chat(21) | 8001 | booml-bot-v2-chat.py |

- 서버 스크립트(공통): `booml-mlx/server_v3_postgres_router.py`
- 붐엘 기능: 채팅, 웹검색, 피드백, 자막추출(/transcribe), 번역(/translate), 환각제거(/clean)
- 붐엘2 기능: 채팅, 웹검색, 피드백, 크롤링(/crawl — HTML+PDF 지원, 청크 번역)
- 크롤링 저장: `/Users/sykim/workspace/crawled/` → 대시보드 "🌐 크롤링 목록" 카드 연동
- 상세 문서: `booml-mlx/README.md`

## 인프라
- 대시보드: React+Express (5173) · dashboard.abamti.com
- CF Tunnel: abamti-local (7328e0f3) · config-local.yml → pm2 restart cloudflared
- XPS 노드: Tailscale → 맥미니 게이트웨이(18789)
- HAOS: 192.168.219.177 · ha.abamti.com
- 하트비트: 30분 · booml-mlx/booml-mlx · logs/heartbeat.log

## 주요 ingress
dashboard.abamti.com→5173 · evn.abamti.com→5174/3003 · ha.abamti.com→8123
ollama.abamti.com→8081 · mrht.abamti.com→5000 · occ.abamti.com→18789

## 프로젝트
| 프로젝트 | 상태 |
|---------|------|
| 미래교역 시안-A | ✅ aidev.abamti.com/MRT2026/ |
| 미래교역 시안-B/C | ⏳ mrtrading-project2/sinan-a-v2/ |
| MRHT 마케팅툴 | ✅ mrht.abamti.com |
| EV Highway | ✅ v0.2.0 evn.abamti.com |
| VSE Platform Sprint 3 | ⏳ github.com/cloud-honey/vse-platform |
| TeslaMate 대시보드 | ⏳ localhost:4002 |

## 필수 규칙
- openclaw.json 수정: 마스터 컨펌 필수
- 게이트웨이 재시작: 컨펌 필수
- 붐4 지시: 영어만
- 폴백 발생: `⚠️[모델명]` 앞에 표시
- 작업 전 컨펌: `담당/난이도/예상시간`
- **히스토리 기록: 작업 완료 시 반드시 `memory/YYYY-MM-DD.md`에 기록**

## ⚠️ 미완료 (마스터 직접)
- MRHT .env API 키 입력
- MRHT 네이버 apicenter IP 등록
- UFW 방화벽 활성화 (sudo)
- TeslaMate PM2 등록

## 🔄 재부팅 후 확인 필요 (2026-04-04)
- PM2 자동시작 테스트 — `pm2 list` 로 붐엘/붐엘2 살아있는지 확인
- 실패 시: 터미널에서 아래 명령 실행
  ```bash
  pm2 resurrect && pm2 save
  # plist 재작성도 필요 시 붐에게 요청
  ```

## 최근 작업 요약
- **04-04 저녁**: 붐엘2 /crawl 기능 추가(HTML+PDF), 청크 번역, 대시보드 크롤링 카드, README 업데이트
- **04-04 오전**: 붐엘 TurboQuant 활성화, 토큰 통계 수집, /status 수정, 번역 버그 수정, 토큰 절약 설정, 워크스페이스 정리, 붐엘2 봇 추가(포트 8001)
- **04-03**: 붐엘 Gemma 4 업그레이드, 피드백/검색/자막추출 기능 추가
- **04-01**: 데일리 리포트 개선, 대시보드 버그 수정
- **03-31**: CF Tunnel 로컬 관리로 교체
- **03-29**: HAOS VM, XPS 노드 연결
