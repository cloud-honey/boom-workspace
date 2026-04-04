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
- 속도: 69-72 t/s · VRAM ~16.8GB · TurboQuant 3.5bit (4.6x 압축)
- 서버: `booml-mlx/server_v3_postgres_router.py` (포트 8000)
- 봇: `booml-telegram-bot/booml-bot-v2-enhanced.py`
- 기능: 실시간 검색, 피드백, 자막 추출(/transcribe), 한국어 번역

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

## ⚠️ 미완료 (마스터 직접)
- MRHT .env API 키 입력
- MRHT 네이버 apicenter IP 등록
- UFW 방화벽 활성화 (sudo)
- TeslaMate PM2 등록

## 최근 작업 요약
- **04-04**: 붐엘 TurboQuant 활성화, 토큰 통계 수집, /status 수정, 번역 버그 수정, 토큰 절약 설정, 워크스페이스 정리
- **04-03**: 붐엘 Gemma 4 업그레이드, 피드백/검색/자막추출 기능 추가
- **04-01**: 데일리 리포트 개선, 대시보드 버그 수정
- **03-31**: CF Tunnel 로컬 관리로 교체
- **03-29**: HAOS VM, XPS 노드 연결
