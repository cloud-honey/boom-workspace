#!/bin/bash
# XPS에 Gemma 4 E4B 모델 설치 스크립트
# 실행: ssh sykim@xps-15 'bash -s' < setup-gemma4-e4b-xps.sh

set -e

echo "🔍 XPS 하드웨어 확인..."
nvidia-smi
free -h
df -h

echo ""
echo "📥 Gemma 4 E4B 모델 다운로드 준비..."

# 작업 디렉토리
WORKDIR="/home/sykim/gemma4-e4b"
MODEL_NAME="google/gemma-4-E4B"
OLLAMA_MODEL_NAME="gemma4-e4b"

echo "작업 디렉토리: $WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# 1. Hugging Face CLI 설치 (없을 경우)
if ! command -v huggingface-cli &> /dev/null; then
    echo "📦 Hugging Face CLI 설치..."
    pip install huggingface-hub
fi

# 2. 모델 다운로드
echo "📥 모델 다운로드 중: $MODEL_NAME"
echo "⚠️ 주의: 모델 크기 약 8GB (4비트 양자화 시 2.5GB), 다운로드 시간 오래 걸림"

huggingface-cli download "$MODEL_NAME" \
    --local-dir ./model \
    --local-dir-use-symlinks False \
    --resume-download

# 3. Ollama Modelfile 생성
echo "📝 Ollama Modelfile 생성..."
cat > Modelfile << EOF
FROM ./model

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 8192

TEMPLATE """{{ if .System }}<start_of_turn>system
{{ .System }}<end_of_turn>
{{ end }}{{ if .Prompt }}<start_of_turn>user
{{ .Prompt }}<end_of_turn>
{{ end }}<start_of_turn>model
{{ .Response }}"""

SYSTEM """You are Gemma 4 E4B, a 4B parameter AI assistant created by Google. 
You are helpful, concise, and respond in the user's preferred language.
You are running on XPS-15 with NVIDIA GTX 1050 Ti (4GB VRAM)."""
EOF

# 4. Ollama 모델 생성
echo "🔧 Ollama 모델 생성: $OLLAMA_MODEL_NAME"
ollama create "$OLLAMA_MODEL_NAME" -f Modelfile

# 5. 테스트
echo "🧪 모델 테스트..."
TEST_PROMPT="안녕! 나는 붐이야. 너는 누구니? 한국어로 간단히 소개해줘."
ollama run "$OLLAMA_MODEL_NAME" "$TEST_PROMPT"

# 6. 정리 및 보고
echo ""
echo "✅ 설치 완료!"
echo "📊 모델 정보:"
ollama list | grep "$OLLAMA_MODEL_NAME"
echo ""
echo "🚀 실행 명령어:"
echo "  ollama run $OLLAMA_MODEL_NAME \"프롬프트\""
echo ""
echo "📁 모델 위치: $WORKDIR"
echo "💾 사용 공간:"
du -sh "$WORKDIR"

# 7. VRAM 사용량 확인 (선택)
echo ""
echo "🎮 VRAM 사용량 테스트..."
timeout 10 ollama run "$OLLAMA_MODEL_NAME" "테스트 메시지" &
sleep 3
nvidia-smi --query-gpu=memory.used --format=csv
pkill -f "ollama run" 2>/dev/null || true

echo ""
echo "✨ Gemma 4 E4B 설치 완료!"