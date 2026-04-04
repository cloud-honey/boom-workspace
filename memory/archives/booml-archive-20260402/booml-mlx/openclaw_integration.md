# 붐엘(BoomL) OpenClaw 통합 가이드

## 개요
MLX 기반 붐엘(BoomL) 에이전트를 OpenClaw에 통합하는 방법

## 통합 방식
1. **HTTP API 서버**: FastAPI 기반 REST API
2. **커스텀 에이전트**: OpenClaw의 custom 모델 지원 활용
3. **OpenAI 호환 API**: `/v1/chat/completions` 엔드포인트

## 설치 및 설정

### 1. MLX 서버 실행
```bash
cd /Users/sykim/.openclaw/workspace/booml-mlx
source venv/bin/activate
python3 server.py
```

서버가 다음 주소에서 실행됩니다:
- http://localhost:8000
- API 문서: http://localhost:8000/docs

### 2. OpenClaw 설정 (openclaw.json)

```json
{
  "agents": {
    "booml": {
      "model": "custom:mlx",
      "endpoint": "http://localhost:8000/v1/chat/completions",
      "apiKey": "not-required",
      "timeout": 120000,
      "maxTokens": 4096,
      "temperature": 0.7,
      "contextWindow": 8192
    }
  }
}
```

### 3. 에이전트 사용 예시

#### 서브에이전트로 호출
```javascript
// 붐이 붐엘을 호출하는 예시
const response = await spawnSubagent({
  agentId: "booml",
  task: "QA 테스트를 수행해주세요. 다음 코드를 검토하고 문제점을 찾아보세요: [코드 내용]",
  model: "custom:mlx"
});
```

#### 직접 세션 생성
```bash
# 커맨드라인에서 테스트
openclaw agents spawn --agent booml --task "간단한 테스트"
```

## 성능 최적화

### MLX 서버 설정 (server.py 수정)
```python
# 모델 로드 최적화
model, tokenizer = load(
    model_id,
    lazy=True,  # 지연 로딩
    trust_remote_code=True
)

# 생성 파라미터 최적화
generation_config = {
    "max_tokens": 1024,
    "temperature": 0.7,
    "top_p": 0.9,
    "repetition_penalty": 1.1
}
```

### OpenClaw 에이전트 설정
```json
{
  "booml": {
    "model": "custom:mlx",
    "endpoint": "http://localhost:8000/v1/chat/completions",
    "timeout": 30000,
    "retry": {
      "attempts": 3,
      "delay": 1000
    },
    "headers": {
      "Content-Type": "application/json"
    }
  }
}
```

## 테스트 명령어

### 1. 서버 상태 확인
```bash
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
```

### 2. API 테스트
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "booml-mlx",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_tokens": 100
  }'
```

### 3. OpenClaw 통합 테스트
```bash
# 붐엘 에이전트 테스트
openclaw agents list | grep booml

# 세션 생성 테스트
openclaw agents spawn --agent booml --task "간단한 질문 테스트"
```

## 문제 해결

### 1. 서버 연결 실패
```
문제: OpenClaw에서 붐엘에 연결할 수 없음
해결:
1. 서버가 실행 중인지 확인: ps aux | grep server.py
2. 포트 확인: netstat -an | grep 8000
3. 방화벽 확인: macOS 방화벽 설정
```

### 2. 모델 로드 실패
```
문제: MLX 모델 다운로드 실패
해결:
1. 인터넷 연결 확인
2. Hugging Face 토큰 설정 (선택사항)
3. 대체 모델 사용: 더 작은 모델로 테스트
```

### 3. 성능 문제
```
문제: 응답 속도가 느림
해결:
1. 모델 양자화 확인 (4bit 권장)
2. 컨텍스트 길이 축소 (8192 → 4096)
3. 배치 크기 조정
4. Metal GPU 가속 확인
```

## 모니터링

### 로그 파일
```
/Users/sykim/.openclaw/workspace/booml-mlx/logs/
├── server.log      # 서버 로그
├── access.log     # 접근 로그
└── error.log      # 오류 로그
```

### 성능 메트릭
```bash
# 토큰 속도 모니터링
curl -s http://localhost:8000/health | jq '.performance'

# 메모리 사용량
ps aux | grep server.py | awk '{print $5, $6}'

# 응답 시간
time curl -X POST http://localhost:8000/v1/chat/completions ...
```

## 업그레이드

### MLX 업데이트
```bash
cd /Users/sykim/.openclaw/workspace/booml-mlx
source venv/bin/activate
pip install --upgrade mlx-lm
```

### 모델 업데이트
```bash
# 새 모델 다운로드
python3 -m mlx_lm.download --repo-id mlx-community/NEW-MODEL-4bit

# 서버 설정 업데이트
# server.py에서 model_id 수정
```

## 보안 고려사항

### 1. 접근 제한
```python
# server.py에서 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 대시보드만 허용
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
```

### 2. API 키 (선택사항)
```python
# API 키 검증 미들웨어 추가
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key != "your-secret-key":
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key"}
        )
    return await call_next(request)
```

## 백업 및 복구

### 설정 백업
```bash
# 설정 파일 백업
cp /Users/sykim/.openclaw/workspace/booml-mlx/server.py server.py.backup
cp /Users/sykim/.openclaw/workspace/booml-mlx/requirements.txt requirements.txt.backup

# 모델 백업 (선택사항)
cp -r ~/.cache/huggingface/hub/models--mlx-community ~/backups/
```

### 복구 절차
```bash
# 1. 가상 환경 재생성
cd /Users/sykim/.openclaw/workspace/booml-mlx
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# 2. 패키지 재설치
pip install -r requirements.txt.backup

# 3. 설정 복원
cp server.py.backup server.py

# 4. 서버 재시작
python3 server.py
```

## 다음 단계

### 단기 목표
1. ✅ MLX 설치 및 기본 테스트
2. ✅ HTTP API 서버 개발
3. 🔄 OpenClaw 통합
4. 🔄 성능 테스트 및 최적화
5. 🔄 붐4 대체 평가

### 장기 목표
1. 더 큰 모델 지원 (13B, 32B)
2. 스트리밍 응답 지원
3. 배치 처리 최적화
4. 다중 모델 로드
5. 자동 확장 (로드 밸런싱)