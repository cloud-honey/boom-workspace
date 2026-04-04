# 붐엘(BoomL) 프로젝트 — 현행 문서

> 마지막 업데이트: 2026-04-04 21:53 KST

---

## 에이전트 구조

| 에이전트 | 텔레그램 봇 | PM2 프로세스 | 서버 포트 | 역할 |
|---------|------------|-------------|---------|------|
| **붐엘** | @boomllm_bot | booml-telegram-bot (id:18) | 8000 | 자막/번역 전용 + 채팅 |
| **붐엘2** | (별도 봇) | booml-chat-bot (id:22) | 8001 | 채팅 전용 + 크롤링 |

### 공통 사항
- 모델: `mlx-community/gemma-4-26b-a4b-it-4bit` (Gemma 4 26B A4B MoE)
- 서버 스크립트: `booml-mlx/server_v3_postgres_router.py`
- 봇 스크립트:
  - 붐엘: `booml-telegram-bot/booml-bot-v2-enhanced.py`
  - 붐엘2: `booml-telegram-bot/booml-bot-v2-chat.py`
- DB는 별도 (대화 기록 분리됨)

---

## 현재 기능 목록

### 붐엘 (포트 8000) — @boomllm_bot
| 기능 | 명령/방법 | 상태 |
|------|---------|------|
| 일반 채팅 | 메시지 전송 | ✅ |
| 실시간 웹 검색 | 자동 감지 | ✅ |
| 피드백 시스템 | 버튼 / 키워드 | ✅ |
| 자막 추출 (mlx-whisper) | `/transcribe [경로] [모델] [N개]` | ✅ |
| 단일 파일 자막 추출 | `자막추출 [파일경로]` | ✅ |
| SRT 한국어 번역 | `/translate [srt경로]` | ✅ |
| SRT 환각 제거 | `/clean [srt경로]` | ✅ |
| 작업 취소 | `/cancel` | ✅ |
| 사용 통계 | `/stats` | ✅ |
| 성능 테스트 | `/benchmark` | ✅ |

### 붐엘2 (포트 8001) — 별도 봇
| 기능 | 명령/방법 | 상태 |
|------|---------|------|
| 일반 채팅 | 메시지 전송 | ✅ |
| 실시간 웹 검색 | 자동 감지 | ✅ |
| 피드백 시스템 | 버튼 / 키워드 | ✅ |
| 웹 크롤링 + 번역 | `/crawl [URL]` | ✅ |
| PDF 크롤링 + 번역 | `/crawl [PDF URL]` | ✅ |
| 사용 통계 | `/stats` | ✅ |
| 성능 테스트 | `/benchmark` | ✅ |

---

## 크롤링 기능 상세 (`/crawl`)

### 동작 방식
1. URL 입력 → `.pdf` 확장자 여부로 자동 분기
2. **HTML**: BeautifulSoup + html2text → 마크다운 변환
3. **PDF**: pdfminer.six → 텍스트 추출
4. 5,000자 청크 분할 → 붐엘(MLX)이 청크별 한국어 번역
5. 결과 파일 저장 → 대시보드에서 확인

### 저장 경로
```
/Users/sykim/workspace/crawled/
  web_도메인_경로_날짜.md   # 웹페이지
  pdf_도메인_경로_날짜.md   # PDF
```

### 대시보드 연동
- `dashboard.abamti.com` → "🌐 크롤링 목록" 카드
- 목록 클릭 → 파일 내용 팝업 뷰어

### ⚠️ 주의점
- 붐엘 서버(8001)가 살아있어야 번역 가능 — `pm2 status booml-mlx-chat` 확인
- 청크당 약 10~30초 소요, 긴 PDF는 수 분 걸림
- MLX 컨텍스트 한계로 청크당 5,000자 처리 (전체 번역됨, 잘리지 않음)
- 이미지/표 등 비텍스트 요소는 번역에서 제외됨

---

## 자막 추출 주의점 (`/transcribe`)

- 추출 중 서버/봇 재시작 금지 — `ps aux | grep mlx_whisper` 먼저 확인
- 파이프라인 오류 시 자동으로 마스터에게 텔레그램 알림 발송
- 환각 자막 자동 제거 (연속 동일 블록 2회 초과 시 삭제)
- 기본 모델: `base` (tiny보다 품질 좋음, 속도 약간 느림)
- 언어: `ja` (일본어) 기본값 — 필요 시 서버 수정

---

## 모델 & 성능

| 항목 | 값 |
|------|---|
| 모델 | mlx-community/gemma-4-26b-a4b-it-4bit |
| 아키텍처 | 26B MoE (8전문가, 2활성) |
| 생성 속도 | ~69-72 t/s |
| 프롬프트 처리 | ~500 t/s |
| 피크 메모리 | ~16.5-16.8 GB |
| KV 캐시 | TurboQuant 3.5bit (4.6x 압축) |
| max_tokens | 2048 (채팅/크롤링) |

---

## 주요 파일 경로

```
/Users/sykim/.openclaw/workspace/

booml-mlx/
  server_v3_postgres_router.py   # 메인 서버 (포트 8000/8001 ENV로 분리)
  model_router.py                # MLX 어댑터 + TurboQuant 설정
  booml_core.py                  # 코어 로직 (토큰 통계 포함)
  ecosystem.config.js            # PM2 env 설정
  venv/                          # Python 가상환경

booml-telegram-bot/
  booml-bot-v2-enhanced.py       # 붐엘 봇 (자막/번역 전용)
  booml-bot-v2-chat.py           # 붐엘2 봇 (채팅/크롤링 전용)

/Users/sykim/workspace/crawled/ # 크롤링 결과 저장 폴더
/Volumes/seot401/subtitle-work-log.md  # 자막 작업 일지
```

---

## PM2 관리 명령

```bash
pm2 list                          # 전체 상태
pm2 logs booml-chat-bot           # 붐엘2 봇 로그
pm2 logs booml-mlx-chat           # 붐엘2 서버 로그
pm2 restart booml-chat-bot        # 붐엘2 봇 재시작
pm2 restart booml-mlx-chat        # 붐엘2 서버 재시작
pm2 restart booml-telegram-bot    # 붐엘 봇 재시작
pm2 restart booml-mlx-server      # 붐엘 서버 재시작

# 서버 상태 확인
curl http://localhost:8000/health
curl http://localhost:8001/health
```

---

## 알려진 이슈

| 이슈 | 상태 | 비고 |
|------|------|------|
| 422 Unprocessable Content (하트비트 요청) | 미해결 | 기능 영향 없음 |
| model_loaded: False (첫 요청 전) | 정상 | 지연 로드 구조 |
| 자막 추출 중 봇 재시작 → 409 Conflict | 개선됨 | 3회 재시도 + 알림 추가 |
