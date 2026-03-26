# AI Usage Dashboard 기획/설계/실행 문서

작성일: 2026-03-26 KST  
작성자: 붐(Boom)

---

# 1. 개발 목표

## 1-1. 프로젝트 한 줄 정의
여러 AI 서비스(Codex, Claude, Gemini, Copilot 등)의 사용량, 리셋 시간, 상태, 정확도 출처를 **한눈에 볼 수 있는 신뢰 가능한 대시보드**를 만든다.

## 1-2. 왜 만드는가
기존 툴(ccusage, CodexBar 등)은 각각 장점이 있지만, 마스터가 원하는 기준에는 아쉬움이 있다.

### 기존 툴의 아쉬움
- 숫자가 예쁘게 보여도 **정확도 신뢰가 낮을 수 있음**
- 출처가 섞여 있어도 사용자에게 명확히 구분되지 않음
- 쿠키/키체인/광범위 권한이 필요한 방식은 찝찝함
- 여러 제공자를 한 화면에서 보더라도 **운영용 기준판**으로 쓰기에는 불안정할 수 있음

## 1-3. 이 프로젝트의 핵심 가치
이 프로젝트는 단순한 “예쁜 사용량 앱”이 아니라 아래를 만족해야 한다.

1. **정확도 우선**
   - 공식 API 기반이면 공식이라고 표시
   - 로컬 로그 기반이면 로컬이라고 표시
   - 추정치면 추정이라고 표시
2. **출처 투명성**
   - 각 숫자가 어디서 왔는지 보여야 함
3. **권한 최소화**
   - 처음부터 브라우저 쿠키/키체인/Full Disk Access에 의존하지 않음
4. **모바일 우선 대시보드**
   - 마스터가 한눈에 보기 쉬운 카드형 UI
5. **확장 가능 구조**
   - 처음엔 몇 개 provider만 붙이고 나중에 쉽게 늘릴 수 있어야 함

## 1-4. 최종 목표
최종적으로는 다음을 달성한다.

- 메인 홈 화면에서 provider별 사용량 상태를 카드로 표시
- provider별로 세션/주간/월간 제한 정보를 구분 표시
- 리셋 시간을 한국 시간 기준으로 보여줌
- 데이터마다 “공식 / 로컬 / 추정 / 불확실” 배지 표시
- 일부 데이터가 불가능할 경우 “확인 불가”로 정직하게 표시
- 추후 메뉴바, 웹 대시보드, 모바일 홈 화면 스타일로 확장 가능하도록 설계

---

# 2. 제품 방향

## 2-1. 기본 원칙

### 원칙 A. 거짓 정밀도 금지
정확하지 않은 숫자를 그럴듯하게 보여주지 않는다.

예:
- 나쁨: `주간 사용량 61% 남음` (근거 불명)
- 좋음: `주간 사용량: 추정 61% (로컬 로그 기반)`

### 원칙 B. 권한은 늦게, 최소로
처음 버전은 가능한 한 아래 순서로 진행한다.
1. 공개/공식 API
2. 로컬 CLI/로그
3. 수동 입력
4. 마지막 수단으로 쿠키/브라우저 기반

### 원칙 C. 데이터와 UI 분리
수집 로직과 대시보드는 강하게 분리한다.
- 수집층이 바뀌어도 UI는 유지
- UI를 바꿔도 수집층은 그대로 사용 가능

### 원칙 D. “실사용 운영판” 지향
이 프로젝트는 장식용보다 운영용이다.

---

# 3. 범위 정의

## 3-1. 1차 목표 범위 (MVP)
1차는 아래 정도만 잡는다.

### 포함
- 대시보드 홈 화면
- provider 카드 목록
- 사용량 바 UI
- 리셋 시간 표시
- 상태 배지
- 출처 배지
- 정확도/신뢰도 표시
- 샘플 데이터 기반 렌더링
- 나중에 실제 데이터 연결 가능한 구조

### 제외
- 브라우저 쿠키 크롤링
- 키체인 직접 접근
- 메뉴바 앱 변환
- 복잡한 백그라운드 sync
- 알림 시스템
- 계정 설정 UI

## 3-2. 우선 대상 provider
1차에서 고려할 provider 후보:
- Codex
- Claude
- Gemini
- Copilot

초기 개발은 2~3개만 붙여도 충분하다.

---

# 4. 전체 설계서

## 4-1. 상위 아키텍처
프로젝트는 크게 4층으로 나눈다.

1. **수집층 (Collectors)**
2. **정규화층 (Normalizers)**
3. **저장층 (Store/Cache)**
4. **표시층 (Dashboard UI)**

### 개념 흐름
Collector → Normalizer → Store → Dashboard UI

---

## 4-2. 수집층 설계
수집층은 provider별 데이터 취득 방식을 담당한다.

### 역할
- provider 원본 데이터 가져오기
- 실패/지연/미지원 여부 명시
- 원본 출처 메타데이터 함께 제공

### provider collector 예시
- `codexCollector`
- `claudeCollector`
- `geminiCollector`
- `copilotCollector`

### 수집 방식 우선순위
1. 공식 API
2. 공식 CLI 출력
3. 로컬 로그/JSON/캐시 파일
4. 수동 입력/설정 파일
5. 쿠키/비공식 접근 (후순위)

### collector 출력 예시
```json
{
  "provider": "codex",
  "sourceType": "local-log",
  "fetchedAt": "2026-03-26T13:00:00Z",
  "raw": {
    "sessionUsed": 12345,
    "sessionLimit": 50000,
    "weeklyUsed": 180000,
    "weeklyLimit": 350000,
    "resetAt": "2026-03-27T00:00:00Z"
  },
  "status": "ok",
  "errors": []
}
```

---

## 4-3. 정규화층 설계
각 provider별 raw 데이터 형식이 다르기 때문에 UI가 공통으로 쓰는 형태로 변환한다.

### 공통 데이터 모델
```ts
export type UsageSourceType = 'official-api' | 'official-cli' | 'local-log' | 'manual' | 'estimated' | 'unknown'
export type UsageConfidence = 'high' | 'medium' | 'low' | 'unknown'
export type ProviderStatus = 'ok' | 'warning' | 'error' | 'stale' | 'unsupported'

export interface UsageMetric {
  label: string
  used?: number
  limit?: number
  unit?: 'tokens' | 'requests' | 'credits' | 'percent' | 'unknown'
  remaining?: number
  resetAt?: string
}

export interface ProviderUsageCardData {
  providerId: string
  providerName: string
  status: ProviderStatus
  sourceType: UsageSourceType
  confidence: UsageConfidence
  fetchedAt: string
  primaryMetric?: UsageMetric
  secondaryMetric?: UsageMetric
  notes?: string[]
  warnings?: string[]
  rawAvailable: boolean
}
```

### 정규화층의 핵심 책임
- 단위를 통일
- 없는 데이터는 `undefined` 또는 `확인 불가` 처리
- UI에서 안전하게 렌더링 가능하게 변환
- 출처/신뢰도/상태를 명시적으로 붙이기

---

## 4-4. 저장층 설계
1차 MVP에서는 아주 가볍게 간다.

### 목적
- 최근 데이터 snapshot 보관
- 렌더링 성능 확보
- 장애 시 마지막 정상 데이터 표시

### 저장 옵션
1차는 아래 중 하나면 충분하다.
- `JSON file`
- `SQLite`

### MVP 추천
- 처음은 **JSON file**
- 이유: 구현 빠름, 디버깅 쉬움, 마스터가 보기 쉬움

### 예시 파일
- `data/providers.json`
- `data/history.json`

---

## 4-5. 표시층(UI) 설계

## 메인 화면 구성
1. 상단 헤더
2. 전체 상태 요약 바
3. provider 카드 목록
4. 마지막 갱신 시간
5. 상태 설명/배지 범례

### 카드에 들어갈 정보
- provider 이름
- 상태 배지 (`정상`, `경고`, `불확실`, `미지원`)
- 출처 배지 (`공식`, `로컬`, `추정`)
- 신뢰도 배지 (`높음`, `중간`, `낮음`)
- 메인 사용량 바
- 서브 사용량 바
- 리셋 시간
- 메모/경고 문구

### 카드 예시 텍스트
- Codex
- 공식 CLI
- 신뢰도 높음
- 세션 62% 사용
- 주간 41% 사용
- 리셋: 오늘 23:00
- 메모: 지난 갱신 2분 전

---

# 5. 데이터 신뢰도 정책

## 5-1. sourceType 정의
- `official-api`: 공식 API
- `official-cli`: 공식 CLI나 공식 명령 결과
- `local-log`: 로컬 로그/캐시/로컬 파일 기반
- `manual`: 사용자가 직접 넣은 값
- `estimated`: 추정 계산값
- `unknown`: 출처 불명

## 5-2. confidence 정의
- `high`: 공식 API/공식 CLI + 검증 가능
- `medium`: 로컬 로그 기반이나 구조가 안정적
- `low`: 일부 추정 또는 불완전한 데이터
- `unknown`: 판단 불가

## 5-3. 절대 규칙
1. `estimated`는 절대 `high`로 표시하지 않는다.
2. raw 데이터가 불완전하면 숫자 대신 `확인 불가`를 허용한다.
3. resetAt이 불명확하면 가짜 리셋 시간을 만들지 않는다.
4. provider별 계산식은 문서화한다.

---

# 6. 계획서

## 6-1. 단계별 계획

### Phase 0 — 기획/설계
목표:
- 요구사항 정리
- 카드 구조 확정
- 출처/정확도 정책 확정
- provider 공통 데이터 모델 정의

산출물:
- 이 설계 문서
- 붐4용 프롬프트

### Phase 1 — UI 목업
목표:
- 샘플 데이터 기반 대시보드 화면 제작
- 모바일 우선 카드형 UI 검증
- 배지/경고/리셋 정보 배치 검증

산출물:
- HTML/CSS/JS 또는 간단한 React mockup
- 더미 provider 데이터

### Phase 2 — 프론트 구조화
목표:
- 컴포넌트 분리
- 타입 정의
- mock 데이터 분리
- 상태별 UI 정리

산출물:
- `ProviderCard`
- `SourceBadge`
- `ConfidenceBadge`
- `UsageBar`
- `DashboardHeader`

### Phase 3 — 데이터 어댑터 골격
목표:
- provider collector 인터페이스 정의
- mock adapter와 실제 adapter 분리 가능 구조 준비

산출물:
- adapter interface
- mock adapters

### Phase 4 — 실제 데이터 연결(후속)
목표:
- Codex/Claude/Gemini 중 연결 쉬운 것부터 붙이기
- 출처별 정확도 검증
- 실패/미지원 상태 처리

---

## 6-2. 성공 기준
1차 성공 기준은 아래다.
- 모바일에서 보기 쉬운가
- provider 상태가 한눈에 들어오는가
- 숫자와 출처가 헷갈리지 않는가
- 거짓 정밀도가 없는가
- 실제 데이터 연결 전 mock만으로도 설계 검증이 되는가

---

# 7. 기술 제안

## 7-1. 추천 스택
1차 mockup 기준:
- HTML/CSS/Vanilla JS 또는 React
- 정적 JSON mock data
- 로컬 브라우저 실행 가능 형태

## 7-2. 왜 이 스택을 추천하나
- 빠르게 시각 검증 가능
- 붐4에게 좁은 범위로 맡기기 쉬움
- 나중에 React/대시보드 시스템으로 확장 가능

## 7-3. 파일 구조 예시
```text
usage-dashboard/
  README.md
  index.html
  style.css
  app.js
  data/
    providers.json
  docs/
    plan.md
```

또는 React 버전이면
```text
usage-dashboard/
  src/
    components/
      ProviderCard.tsx
      UsageBar.tsx
      SourceBadge.tsx
      ConfidenceBadge.tsx
    data/
      mockProviders.ts
    types/
      usage.ts
    App.tsx
```

---

# 8. UX 지침

## 8-1. 마스터 맞춤 UX 원칙
- 모바일 폭에서도 읽기 쉬워야 함
- 숫자보다 상태가 먼저 들어와야 함
- 긴 설명보다 카드형 요약 우선
- 이상 상태는 색으로 바로 구분 가능해야 함
- `정확도`, `출처`, `리셋 시간`이 핵심

## 8-2. 컬러 규칙 예시
- 정상: 녹색
- 경고: 주황색
- 오류: 빨간색
- 불확실/추정: 회색 또는 보라색 계열

## 8-3. 배지 규칙
예:
- 출처: `공식`, `로컬`, `추정`
- 신뢰도: `높음`, `중간`, `낮음`
- 상태: `정상`, `지연`, `경고`, `오류`, `미지원`

---

# 9. 붐4 테스트 작업 적합성

## 붐4에게 적합한 범위
- 정적인 UI 목업
- 컴포넌트 단위 구현
- mock data 렌더링
- 카드 레이아웃 개선
- 반복 스타일링 작업

## 붐4에게 부적합한 범위
- 제품 방향 판단
- provider 수집 전략 결정
- 정확도 정책 설계
- 민감 권한/보안 판단
- 실제 인증 흐름 설계

즉 붐4는 “디자인된 설계서에 맞춰 화면을 구현하는 역할”이 적합하다.

---

# 10. 붐4용 상세 영어 프롬프트 (주석 포함)

아래 프롬프트는 붐4에게 바로 전달하기 위한 초안이다.  
**주석 포함 버전**으로 작성한다. 실제 전달 시 주석을 남겨도 되고, 필요하면 간단히 줄여도 된다.

```text
You are Boom4.
Follow workspace rules strictly.
Use English only.

# Context
# We are building an internal prototype dashboard for AI usage visibility.
# This is NOT a real data integration task yet.
# Your task is ONLY to build a high-quality front-end mockup using static mock data.

Task folder:
/Users/sykim/.openclaw/workspace/experiments/usage-dashboard-mock

# Goal
# Create a mobile-first dashboard mockup that shows AI provider usage in a trustworthy, operational style.
# The dashboard must emphasize not only usage numbers, but also source transparency and confidence.

Requirements:
- Create a front-end only mockup.
- No real API calls.
- No cookies, no keychain access, no auth logic.
- Local files only.
- Do not touch files outside the task folder.
- Keep the scope focused and visually polished.

Design direction:
- Mobile-first layout.
- Clean, modern dashboard feel.
- Easy to scan at a glance.
- Card-based UI.
- Should look useful for real operations, not like a toy demo.

Required sections:
1. Header area
   - App/project title
   - Last updated time
   - A short summary chip or status row

2. Provider cards list
   - Show at least 4 providers (example: Codex, Claude, Gemini, Copilot)
   - Each card must include:
     - provider name
     - status badge (examples: OK, Warning, Stale, Error)
     - source badge (examples: Official, Local, Estimated)
     - confidence badge (examples: High, Medium, Low)
     - primary usage bar
     - optional secondary usage bar
     - reset time label
     - short notes or warning text

3. Legend/help section
   - Brief explanation of what source badge means
   - Brief explanation of confidence badge meaning

4. Optional bottom summary section
   - Example: providers with issues, stale data count, next reset window

Mock data rules:
- Use realistic but fake sample data.
- Include variation across cards:
  - one card with high confidence official source
  - one card with local-log medium confidence
  - one card with estimated/low confidence
  - one card with warning or stale state
- Make sure the UI clearly communicates these differences.

Visual rules:
- Strong spacing and clean typography.
- Good contrast.
- Rounded cards.
- Progress bars should be readable.
- Badges should be visually distinct.
- Avoid overcomplicated effects.
- Prioritize clarity over decoration.

Implementation notes:
- You may use plain HTML/CSS/JS or a minimal local front-end setup.
- Prefer the simplest setup that is easy to open locally.
- Include mock data in a clearly separated structure.
- Keep file organization tidy.

Required deliverables:
- A working local mockup.
- A short README explaining how to open it.
- A concise summary of what you built.
- A list of changed files.

Important constraints:
- Do NOT implement real provider integrations.
- Do NOT invent security-sensitive features.
- Do NOT add unnecessary dependencies.
- Do NOT touch any files outside the assigned folder.

Output format when finished:
1. Short summary
2. Changed files
3. How to open locally
4. Notes about visual structure
```

---

# 11. 붐4 프롬프트 주석 설명

## 왜 이렇게 썼는가
이 프롬프트는 붐4가 흔히 범위를 넘는 걸 막기 위해 아래를 명확히 고정한다.

### a) “front-end only mockup” 반복
실데이터 연동으로 튀는 걸 막기 위함

### b) “no cookies, no keychain, no auth logic” 명시
민감 권한/인증 흐름으로 새지 않게 하기 위함

### c) “card-based, operational style” 명시
장난감 데모처럼 만들지 않고 운영용 UI 감각을 요구하기 위함

### d) variation across cards 요구
모든 카드가 똑같은 상태로 복붙되지 않게 하기 위함

### e) simplest local setup 요구
테스트 속도와 확인 편의성을 높이기 위함

---

# 12. 붐4에게 추가로 줄 수 있는 후속 작업
1차 mockup이 괜찮으면 다음 작업도 붐4 테스트용으로 적합하다.

## 후속 작업 A
`ProviderCard` 컴포넌트 분리

## 후속 작업 B
`SourceBadge`, `ConfidenceBadge`, `StatusBadge` 공통 컴포넌트 분리

## 후속 작업 C
mock data 파일 분리 + 타입 정리

## 후속 작업 D
모바일/태블릿 반응형 개선

이 순서가 안전하다.

---

# 13. 최종 판단
이 프로젝트는 마스터 취향과 실제 운영 목적에 맞는다.

특히 중요한 점은:
- 보기 좋은 대시보드이면서
- 숫자 출처와 신뢰도를 같이 보여주고
- 권한을 최소화하며
- 나중에 실제 데이터 연결로 확장 가능한 구조를 가지는 것

즉, 이 프로젝트는 단순 유틸보다 **마스터 맞춤 운영 대시보드**로 발전시킬 가치가 충분하다.
