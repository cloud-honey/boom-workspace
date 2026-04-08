#!/bin/bash
# XPS에 Gemma 4 E2B 설치 스크립트

set -e

echo "🚀 XPS에 Gemma 4 E2B 설치 시작..."

# 작업 디렉토리
WORKDIR="/home/sykim/gemma4-e2b"
MODEL_NAME="google/gemma-4-E2B"
OLLAMA_MODEL_NAME="gemma4-e2b"

echo "📁 작업 디렉토리: $WORKDIR"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

# 1. 저장공간 확인
echo "💾 저장공간 확인..."
df -h .

# 2. Hugging Face에서 다운로드
echo "📥 Hugging Face에서 Gemma 4 E2B 다운로드..."

cat > download_gemma4_e2b.py << 'EOF'
from huggingface_hub import snapshot_download
import os

print("Gemma 4 E2B 다운로드 시작...")
model_dir = "./model"

# 모델 다운로드 (전체 파일)
snapshot_download(
    repo_id="google/gemma-4-E2B",
    local_dir=model_dir,
    local_dir_use_symlinks=False
)

print(f"✅ 다운로드 완료! 위치: {os.path.abspath(model_dir)}")

# 파일 크기 확인
total_size = 0
for root, dirs, files in os.walk(model_dir):
    for file in files:
        path = os.path.join(root, file)
        total_size += os.path.getsize(path)

print(f"📊 모델 크기: {total_size / 1024**3:.2f} GB")
EOF

python3 download_gemma4_e2b.py

# 3. Ollama Modelfile 생성
echo "📝 Ollama Modelfile 생성..."

cat > Modelfile << 'EOF'
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

SYSTEM """You are Gemma 4 E2B, a 2B parameter AI assistant created by Google.
You are helpful, concise, and respond in the user's preferred language (Korean preferred).
You are running on XPS-15 with NVIDIA GTX 1050 Ti (4GB VRAM)."""
EOF

# 4. Ollama 모델 생성
echo "🔧 Ollama 모델 생성: $OLLAMA_MODEL_NAME"
ollama create "$OLLAMA_MODEL_NAME" -f Modelfile

# 5. VRAM 테스트
echo "🎮 VRAM 사용량 테스트..."

# 테스트 실행 (백그라운드)
ollama run "$OLLAMA_MODEL_NAME" "테스트 메시지입니다. '성공'이라고만 답해주세요." &
TEST_PID=$!

# 3초 대기 후 VRAM 확인
sleep 3
echo "📊 VRAM 사용량:"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# 테스트 프로세스 종료
kill $TEST_PID 2>/dev/null || true
wait $TEST_PID 2>/dev/null || true

# 6. 본격적 테스트
echo "🧪 모델 테스트..."
TEST_PROMPT="안녕! 나는 붐이야. 너는 Gemma 4 E2B 모델이지? XPS에 설치된 거 맞아? 한국어로 간단히 답해줘."
ollama run "$OLLAMA_MODEL_NAME" "$TEST_PROMPT"

# 7. 정리 및 보고
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

echo ""
echo "✨ Gemma 4 E2B 설치 완료! XPS 4GB VRAM에 완벽 적합합니다."