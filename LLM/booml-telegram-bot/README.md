# 붐엘 텔레그램 봇 🤖

MLX 최적화 전용 에이전트를 위한 텔레그램 봇입니다. macOS M4 Pro에서 MLX 프레임워크의 성능을 모니터링하고 Ollama와 비교합니다.

## 🎯 특징

- **MLX 성능 벤치마크** - Metal 가속 성능 측정
- **Ollama vs MLX 비교** - 토큰 속도, 메모리 사용량 비교
- **실시간 모니터링** - 성능 변화 추적
- **macOS 전용** - Metal 가속 최적화

## 📋 요구사항

- Node.js 18+
- Python 3.8+
- macOS (Metal 가속 지원)
- 텔레그램 봇 토큰

## 🚀 설치

### 1. 봇 토큰 생성

1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 찾기
2. `/newbot` 명령어로 새 봇 생성
3. 봇 이름: `BoomL Bot`
4. 봇 사용자명: `booml_mlx_bot` (또는 원하는 이름)
5. 생성된 토큰 복사

### 2. 환경 변수 설정

```bash
# .env 파일 생성
echo "BOOML_BOT_TOKEN=여기에_토큰_입력" > /Users/sykim/.openclaw/workspace/booml-telegram-bot/.env
```

### 3. 의존성 설치

```bash
cd /Users/sykim/.openclaw/workspace/booml-telegram-bot

# Node.js 패키지 설치
npm install

# Python 패키지 설치 (선택사항 - MLX 벤치마크용)
pip3 install mlx mlx.nn
```

### 4. MLX 설치 (선택사항)

MLX 벤치마크를 실행하려면 MLX 설치가 필요합니다:

```bash
# MLX 설치
pip3 install mlx

# 또는 개발 버전 설치
pip3 install git+https://github.com/ml-explore/mlx.git
```

## 🔧 사용법

### 봇 시작

```bash
cd /Users/sykim/.openclaw/workspace/booml-telegram-bot
npm start
```

### PM2로 데몬 실행 (권장)

```bash
# PM2 설치 (아직 안 된 경우)
npm install -g pm2

# 봇 데몬으로 실행
pm2 start booml-bot.js --name booml-bot

# 자동 시작 설정
pm2 startup
pm2 save
```

### 명령어

텔레그램 봇에서 사용 가능한 명령어:

| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 시작 및 환영 메시지 |
| `/status` | MLX 및 시스템 상태 확인 |
| `/benchmark` | MLX 성능 벤치마크 실행 |
| `/compare` | Ollama vs MLX 비교 분석 |
| `/help` | 도움말 표시 |

## 📊 기능 상세

### 1. MLX 상태 확인 (`/status`)
- MLX 설치 상태 확인
- Metal 가속 지원 여부
- 시스템 리소스 정보
- Ollama 실행 상태

### 2. MLX 성능 벤치마크 (`/benchmark`)
- 행렬 곱셈 성능 (CPU vs GPU)
- 추론 속도 측정 (LLM 시뮬레이션)
- 배치 크기별 성능 비교
- Metal 가속 효과 측정

### 3. Ollama vs MLX 비교 (`/compare`)
- Ollama 모델 응답 시간 측정
- MLX 추론 속도 측정
- 토큰/초 성능 비교
- 메모리 사용량 분석
- 권장사항 제공

## 🏗️ 아키텍처

```
붐엘 텔레그램 봇 아키텍처:
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   텔레그램      │    │   붐엘 봇       │    │   MLX 엔진     │
│   (사용자)      │◄──►│   (Node.js)     │◄──►│   (Python)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                      │                      │
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   명령어 처리   │    │   성능 데이터   │    │   벤치마크     │
│   (Telegraf)    │    │   수집/분석     │    │   실행         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔄 OpenClaw 통합

붐엘 봇은 OpenClaw 에이전트 시스템과 통합될 수 있습니다:

1. **붐엘 에이전트 생성**: OpenClaw 설정에 붐엘 에이전트 추가
2. **자동 보고**: MLX 테스트 결과를 붐 대시보드로 전송
3. **알림 통합**: 중요한 성능 변화 시 마스터에게 알림

## 📈 성능 메트릭

봇이 수집하는 주요 메트릭:

1. **토큰 속도**: 토큰/초 (tokens/second)
2. **응답 시간**: 초 단위 응답 시간
3. **메모리 사용량**: VRAM 및 시스템 메모리
4. **Metal 가속 효과**: CPU 대비 GPU 성능 향상률
5. **배치 효율성**: 배치 크기별 성능 변화

## 🚨 문제 해결

### 일반적인 문제

1. **MLX 설치 실패**
   ```bash
   # Python 버전 확인
   python3 --version
   
   # pip 업그레이드
   pip3 install --upgrade pip
   
   # 시스템 종속성 설치
   brew install cmake
   ```

2. **봇 토큰 오류**
   - `.env` 파일 확인
   - 토큰 재생성
   - 봇 비활성화 확인

3. **PM2 실행 오류**
   ```bash
   # PM2 재설치
   npm uninstall -g pm2
   npm install -g pm2
   
   # 프로세스 재시작
   pm2 delete booml-bot
   pm2 start booml-bot.js --name booml-bot
   ```

### 로그 확인

```bash
# PM2 로그
pm2 logs booml-bot

# 파일 로그
tail -f /Users/sykim/.openclaw/workspace/booml-telegram-bot/booml-bot.log
```

## 📝 라이선스

MIT License

## 🤝 기여

버그 리포트 및 기능 제안은 이슈 트래커를 이용해주세요.

## 📞 연락처

- 마스터: 승영 김 (텔레그램 @abamtibot)
- 붐엘: MLX 최적화 전용 에이전트