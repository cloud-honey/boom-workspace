#!/bin/bash

# 붐엘 텔레그램 봇 설치 스크립트
# macOS M4 Pro 최적화

set -e

echo "🚀 붐엘 텔레그램 봇 설치 시작"
echo "=============================="

# 작업 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Node.js 패키지 설치
echo "📦 Node.js 패키지 설치 중..."
if [ ! -d "node_modules" ]; then
    npm install
    echo "✅ Node.js 패키지 설치 완료"
else
    echo "⚠️ node_modules 이미 존재 - 건너뜀"
fi

# 2. Python 가상환경 설정 (선택사항)
echo "🐍 Python 환경 확인 중..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python $PYTHON_VERSION 발견"
    
    # MLX 설치 확인
    if python3 -c "import mlx" &> /dev/null; then
        echo "✅ MLX 이미 설치됨"
    else
        echo "⚠️ MLX가 설치되지 않음 - 벤치마크 기능 제한됨"
        echo "   설치하려면: pip3 install mlx"
    fi
else
    echo "❌ Python3를 찾을 수 없음"
    echo "   설치 필요: brew install python@3.11"
fi

# 3. 환경 변수 파일 확인
echo "🔧 환경 설정 확인 중..."
if [ ! -f ".env" ]; then
    echo "❌ .env 파일이 없습니다"
    echo ""
    echo "텔레그램 봇 토큰을 설정해야 합니다:"
    echo "1. @BotFather에서 새 봇 생성"
    echo "2. 토큰 복사"
    echo "3. 아래 명령어 실행:"
    echo ""
    echo "echo 'BOOML_BOT_TOKEN=여기에_토큰_입력' > .env"
    echo ""
    exit 1
else
    # .env 파일에서 토큰 확인
    if grep -q "BOOML_BOT_TOKEN=" .env; then
        TOKEN=$(grep "BOOML_BOT_TOKEN=" .env | cut -d'=' -f2)
        if [ -z "$TOKEN" ] || [ "$TOKEN" = "여기에_토큰_입력" ]; then
            echo "❌ .env 파일에 유효한 토큰이 없습니다"
            echo "   BOOML_BOT_TOKEN=값 형식으로 설정하세요"
            exit 1
        else
            echo "✅ 유효한 봇 토큰 발견"
        fi
    else
        echo "❌ .env 파일에 BOOML_BOT_TOKEN이 없습니다"
        exit 1
    fi
fi

# 4. 실행 권한 설정
echo "🔐 실행 권한 설정 중..."
chmod +x booml-bot.js
chmod +x mlx-benchmark.py
chmod +x compare-models.py
chmod +x setup-bot.sh
echo "✅ 실행 권한 설정 완료"

# 5. PM2 설치 확인
echo "⚡ PM2 데몬 설정 확인 중..."
if command -v pm2 &> /dev/null; then
    echo "✅ PM2 설치됨"
    
    # PM2 프로세스 확인
    if pm2 list | grep -q "booml-bot"; then
        echo "⚠️ booml-bot이 이미 PM2에서 실행 중"
        echo "   재시작: pm2 restart booml-bot"
        echo "   중지: pm2 stop booml-bot"
    else
        echo "📋 PM2로 봇 시작:"
        echo "   pm2 start booml-bot.js --name booml-bot"
        echo "   pm2 save"
        echo "   pm2 startup"
    fi
else
    echo "⚠️ PM2가 설치되지 않음 - 수동 실행 필요"
    echo "   설치: npm install -g pm2"
    echo "   수동 실행: node booml-bot.js"
fi

# 6. Ollama 확인
echo "🤖 Ollama 상태 확인 중..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama 설치됨"
    
    # 실행 중인지 확인
    if ollama ps &> /dev/null; then
        echo "✅ Ollama 실행 중"
        
        # 모델 목록
        MODELS=$(ollama list 2>/dev/null | head -5)
        if [ -n "$MODELS" ]; then
            echo "📋 사용 가능 모델:"
            echo "$MODELS" | while read line; do
                echo "   $line"
            done
        fi
    else
        echo "⚠️ Ollama가 실행 중이지 않음"
        echo "   시작: ollama serve &"
    fi
else
    echo "⚠️ Ollama가 설치되지 않음 - 비교 기능 제한됨"
    echo "   설치: brew install ollama"
fi

# 7. 시스템 정보
echo "💻 시스템 정보:"
echo "   OS: $(sw_vers -productName) $(sw_vers -productVersion)"
echo "   아키텍처: $(uname -m)"
echo "   Node.js: $(node --version)"
echo "   npm: $(npm --version)"

# 8. 설치 완료
echo ""
echo "=========================================="
echo "✅ 붐엘 텔레그램 봇 설치 완료!"
echo ""
echo "📋 다음 단계:"
echo ""
echo "1. 봇 시작:"
echo "   node booml-bot.js"
echo ""
echo "2. 또는 PM2로 데몬 실행:"
echo "   pm2 start booml-bot.js --name booml-bot"
echo "   pm2 save"
echo "   pm2 startup"
echo ""
echo "3. 텔레그램에서 봇 테스트:"
echo "   /start - 봇 시작"
echo "   /status - 시스템 상태"
echo "   /benchmark - MLX 성능 테스트"
echo "   /compare - Ollama vs MLX 비교"
echo ""
echo "4. 문제 발생 시:"
echo "   로그 확인: pm2 logs booml-bot"
echo "   또는: node booml-bot.js (터미널에서 직접 실행)"
echo ""
echo "🚀 붐엘이 macOS M4 Pro를 최적화합니다!"
echo "=========================================="