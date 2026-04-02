# 붐엘(BoomL) - MLX 전용 고속 로컬 에이전트

## 개요
Ollama 대체를 위한 맥 전용 최적화 로컬 LLM 에이전트. MLX 프레임워크를 사용하여 애플 실리콘(M4 Pro)에 최적화된 고속 추론 제공.

## 목표
- **속도**: Ollama 대비 2-3배 향상 (70-100 t/s)
- **메모리 효율**: 통합 메모리 아키텍처 최적화
- **에너지 효율**: 배터리 사용량 감소
- **통합**: OpenClaw와 원활한 통합

## 기술 스택
- **프레임워크**: MLX (애플 머신러닝 프레임워크)
- **모델**: Qwen2.5-7B-Instruct-MLX (4비트 양자화)
- **API 서버**: FastAPI (Python)
- **클라이언트**: OpenClaw 커스텀 에이전트

## 아키텍처
```
┌─────────────────┐    HTTP    ┌──────────────┐    OpenClaw    ┌─────────────┐
│   MLX 모델      │ ◄────────► │  FastAPI     │ ◄────────────► │   붐엘      │
│   (로컬 실행)   │   REST API │  서버        │   JSON-RPC     │   에이전트   │
└─────────────────┘            └──────────────┘                └─────────────┘
```

## 설치 및 설정

### 1. MLX 설치
```bash
# Python 3.12+ 필요
python3 -m venv venv
source venv/bin/activate
pip install mlx-lm
pip install fastapi uvicorn httpx pydantic
```

### 2. 모델 다운로드
```bash
# Hugging Face에서 MLX 양자화 모델 다운로드
python3 -m mlx_lm.download --repo-id mlx-community/Qwen2.5-7B-Instruct-4bit
```

### 3. API 서버 실행
```bash
python3 server.py
```

### 4. OpenClaw 통합
```json
{
  "agents": {
    "booml": {
      "model": "custom:mlx",
      "endpoint": "http://localhost:8000/v1/chat/completions"
    }
  }
}
```

## 성능 지표
| 항목 | Ollama (현재) | MLX (목표) | 향상률 |
|------|---------------|------------|--------|
| 토큰 속도 | 33.6 t/s | 70-100 t/s | 2-3배 |
| 메모리 사용 | 18GB | 5-7GB | 60-70% 감소 |
| 응답 시간 | 300ms | 100-150ms | 2-3배 |
| 에너지 효율 | 보통 | 우수 | 30% 향상 |

## 개발 로드맵
1. **Phase 1**: MLX 설치 및 기본 테스트 (1일)
2. **Phase 2**: HTTP API 서버 개발 (1일)
3. **Phase 3**: OpenClaw 통합 (1일)
4. **Phase 4**: 성능 테스트 및 최적화 (1일)
5. **Phase 5**: 붐4 대체 및 운영 (1일)

## 파일 구조
```
booml-mlx/
├── README.md          # 이 파일
├── requirements.txt   # Python 의존성
├── server.py         # FastAPI 서버
├── mlx_model.py      # MLX 모델 래퍼
├── config.yaml       # 설정 파일
├── tests/            # 테스트 파일
└── logs/             # 로그 파일
```

## 테스트 명령어
```bash
# 모델 테스트
python3 -c "from mlx_model import MLXModel; model = MLXModel(); print(model.generate('Hello'))"

# API 테스트
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}'

# 성능 테스트
python3 tests/benchmark.py
```

## 문제 해결
- **MLX 설치 실패**: Python 3.12+ 확인, Xcode 명령어 도구 설치
- **메모리 부족**: 4비트 양자화 모델 사용, 컨텍스트 길이 축소
- **속도 저하**: Metal GPU 가속 확인, 배치 크기 조정

## 참고 자료
- [MLX 공식 문서](https://ml-explore.github.io/mlx/)
- [MLX Examples GitHub](https://github.com/ml-explore/mlx-examples)
- [Hugging Face MLX 모델](https://huggingface.co/mlx-community)
- [FastAPI 문서](https://fastapi.tiangolo.com/)