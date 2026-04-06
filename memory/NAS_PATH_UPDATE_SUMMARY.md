# NAS 경로 변경 작업 요약 (2026-04-06)

## 문제
붐엘이 `/Volumes/seot401/torrent` 경로에 접근할 수 없어 자막추출 작업 실패

## 해결
모든 NAS 경로를 `/Users/sykim/nas/torrent`로 변경

## 수정된 파일

### 1. 붐엘 서버 (`booml-mlx/server_v3_postgres_router.py`)
- `/v1/transcribe` 엔드포인트: 파일 경로 자동 변환 추가
- `/v1/translate_srt` 엔드포인트: 파일 경로 자동 변환 추가  
- `/v1/clean_srt` 엔드포인트: 파일 경로 자동 변환 추가
- 변환 로직: `/Volumes/seot401/torrent` → `/Users/sykim/nas/torrent`

### 2. 붐엘 봇 스크립트들
#### `booml-bot-v2-chat.py` (booml-chat-bot)
- `WORK_LOG_FILE` 경로 변경: `/Volumes/seot401/subtitle-work-log.md` → `/Users/sykim/nas/subtitle-work-log.md`
- 기본 NAS 경로 변경: `/Volumes/seot401/torrent` → `/Users/sykim/nas/torrent`
- 도움말 메시지 경로 수정
- `clean`, `translate`, `transcribe`, `자막추출` 명령어에 경로 변환 로직 추가
- `PIPELINE_STATE_FILE` 관련 함수(`load_pipeline_state`, `save_pipeline_state`)에 경로 변환 로직 추가

#### `booml-bot-v2-enhanced.py` (booml-telegram-bot)
- 동일한 수정사항 적용

### 3. 데이터 파일
- `logs/transcribe_pipeline.json`: 73개 경로 변환 (70개 done, 3개 failed)
- 백업 파일 생성: `transcribe_pipeline.json.backup`

## 재시작된 프로세스
1. `booml-mlx-server` (붐엘 서버)
2. `booml-chat-bot` (붐엘 채팅 봇)
3. `booml-telegram-bot` (붐엘 텔레그램 봇)

## Git 커밋
- 커밋 해시: `5e9979a`
- 메시지: "fix: 붐엘 NAS 경로 변경 (/Volumes/seot401/torrent → /Users/sykim/nas/torrent)"
- 푸시 완료: 원격 저장소에 반영됨

## 테스트
이제 `/transcribe`, `/clean`, `/translate`, `자막추출` 명령어가 새 NAS 경로에서 정상 작동합니다.

