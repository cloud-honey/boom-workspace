# 히스토리 업데이트 가이드 (모든 에이전트)

## 📋 왜 기록해야 하나요?
1. **대시보드 히스토리 카드 표시** - `dashboard.abamti.com`에서 확인 가능
2. **작업 추적** - 누가 무엇을 했는지 기록
3. **문제 진단** - 오류 발생 시 원인 분석
4. **마스터 보고** - 진행 상황 투명하게 공유

## 📁 기록 위치
```
/Users/sykim/.openclaw/workspace/memory/YYYY-MM-DD.md
```
예: `/Users/sykim/.openclaw/workspace/memory/2026-04-05.md`

## ✏️ 기록 형식 (필수)
```markdown
## HH:MM KST [모델명] 작업명
- 지시: (마스터/붐이 요청한 내용)
- 작업: (실제 수행한 작업 - 파일 경로 포함)
- 결과: 성공/실패 (실패 시 이유)
```

## 🔤 모델명 매핑 테이블
| 에이전트 | 기록용 모델명 | 실제 모델 |
|---------|---------------|-----------|
| 붐 | `[sonnet]` | claude-sonnet-4-6 |
| 밤티 | `[gpt-5.4]` | openai-codex/gpt-5.4 |
| 붐2 | `[deepseek-chat]` | deepseek/deepseek-chat |
| 붐3 | `[gemini-2.5-flash]` | google/gemini-2.5-flash |
| 붐4 | `[qwen3-coder:30b]` | ollama/qwen3-coder:30b |
| 붐엘 | `[booml-mlx]` | booml-mlx/booml-mlx |

**중요**: 대괄호 안에 모델명을 정확히 기입해야 대시보드에서 모델별 필터링 가능

## ✅ 기록 예시

### 예시 1: 붐2 (코딩)
```markdown
## 14:30 KST [deepseek-chat] 사용자 인증 모듈 리팩토링
- 지시: JWT 토큰 검증 로직 개선 요청
- 작업: `/Users/sykim/workspace/vse-platform/src/auth.js` 수정 - verifyToken 함수 최적화
- 결과: 성공 - 응답 시간 40% 개선
```

### 예시 2: 붐3 (문서)
```markdown
## 15:45 KST [gemini-2.5-flash] API 문서 업데이트
- 지시: 대시보드 API 문서 보완
- 작업: `/Users/sykim/workspace/openclaw-dashboard/docs/api.md`에 3개 엔드포인트 추가
- 결과: 성공 - GET /api/status, GET /api/reports, GET /api/weather 문서화
```

### 예시 3: 붐4 (QA/테스트)
```markdown
## 16:20 KST [qwen3-coder:30b] VSE Platform 테스트
- 지시: Sprint 6 QA 테스트 실행 (영어 지시)
- 작업: `/Users/sykim/workspace/vse-platform/test/`에서 unit test 15개 실행
- 결과: 성공 - 14개 통과, 1개 실패 (이슈 #45 보고됨)
```

### 예시 4: 밤티 (반복 작업)
```markdown
## 17:10 KST [gpt-5.4] 데이터 크롤링 자동화
- 지시: 일일 뉴스 크롤링 스크립트 실행
- 작업: `/Users/sykim/workspace/crawled/`에 23개 기사 수집 및 번역
- 결과: 성공 - 모든 기사 정상 처리
```

## ⚠️ 주의사항
1. **파일 없으면 생성** - `touch memory/2026-04-05.md`
2. **헤더 유지** - 첫 줄: `# 2026-04-05 일일 기록`
3. **시간순 정렬** - 새로운 기록은 파일 하단에 추가
4. **파일 경로 필수** - 어떤 파일을 수정했는지 명시
5. **결과 명시** - 성공/실패 반드시 기록

## 🔄 대시보드 연동
- 히스토리 카드는 `memory/` 폴더의 `.md` 파일을 자동으로 읽음
- 리포트(`reports/`)와는 별도 시스템
- "일일 리포트" 제목의 항목은 필터링됨

## 📞 도움이 필요할 때
1. 파일 경로 불확실 → 붐에게 확인
2. 기록 형식 모름 → 이 가이드 참조
3. 기록 실패 → 붐에게 보고

## 🎯 핵심 원칙
> **"작업 완료 = 기록 완료"**
> 기록하지 않은 작업은 존재하지 않는 작업입니다.