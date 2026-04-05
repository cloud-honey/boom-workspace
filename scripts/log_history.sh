#!/bin/bash
# 히스토리 기록 도우미 스크립트
# 사용법: ./log_history.sh "에이전트명" "모델명" "작업명" "지시내용" "작업내용" "결과"

set -e

AGENT="$1"
MODEL="$2"
TASK="$3"
INSTRUCTION="$4"
WORK="$5"
RESULT="$6"

if [ $# -lt 6 ]; then
    echo "사용법: $0 에이전트명 모델명 작업명 지시내용 작업내용 결과"
    echo "예: $0 붐2 deepseek-chat 'API 문서화' '마스터가 API 문서 요청' '/path/to/file.js 수정' '성공'"
    echo ""
    echo "모델명 참고:"
    echo "  붐: sonnet"
    echo "  밤티: gpt-5.4"
    echo "  붐2: deepseek-chat"
    echo "  붐3: gemini-2.5-flash"
    echo "  붐4: qwen3-coder:30b"
    echo "  붐엘: booml-mlx"
    exit 1
fi

# 현재 날짜와 시간
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)
FILE="/Users/sykim/.openclaw/workspace/memory/${DATE}.md"

# 파일이 없으면 생성
if [ ! -f "$FILE" ]; then
    echo "# ${DATE} 일일 기록" > "$FILE"
    echo "" >> "$FILE"
fi

# 기록 추가 (모델명 대괄호 포함)
echo "## ${TIME} KST [${MODEL}] ${TASK}" >> "$FILE"
echo "- 지시: ${INSTRUCTION}" >> "$FILE"
echo "- 작업: ${WORK}" >> "$FILE"
echo "- 결과: ${RESULT}" >> "$FILE"
echo "" >> "$FILE"

echo "✅ 히스토리 기록 완료: ${FILE}"
echo "📝 내용: ${AGENT} ([${MODEL}]) - ${TASK} (${RESULT})"