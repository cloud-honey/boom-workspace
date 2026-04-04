#!/usr/bin/env python3
import asyncio
import logging
import aiohttp
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 봇 토큰
BOT_TOKEN = '8592906266:AAGA326kDs1pNXbVRWbwtWxIUR3n9VkKQYE'
# MLX 서버 URL
MLX_SERVER_URL = 'http://localhost:8000'

async def query_mlx_server(prompt: str) -> str:
    """MLX 서버에 쿼리 보내기"""
    try:
        # OpenAI 호환 형식으로 요청
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MLX_SERVER_URL}/v1/chat/completions',
                json={
                    'messages': messages,
                    'model': 'booml-mlx',
                    'max_tokens': 500,
                    'temperature': 0.7
                },
                timeout=60
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # OpenAI 호환 응답에서 텍스트 추출
                    if 'choices' in data and len(data['choices']) > 0:
                        return data['choices'][0]['message']['content']
                    else:
                        return '응답을 생성하지 못했습니다.'
                else:
                    error_text = await response.text()
                    return f'MLX 서버 오류: {response.status} - {error_text[:100]}'
    except Exception as e:
        logger.error(f'MLX 서버 쿼리 오류: {e}')
        return f'MLX 서버 연결 오류: {str(e)}'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    message = (
        "🤖 *붐엘 (BoomL) macOS LLM 에이전트*\n"
        f"안녕하세요 {user.first_name}!\n\n"
        "📊 *현재 상태*\n"
        "• 플랫폼: macOS M4 Pro\n"
        "• 모델: Qwen2.5-7B-Instruct-MLX\n"
        "• 엔진: MLX (Metal 가속)\n"
        "• 상태: ✅ MLX 서버 연결됨\n\n"
        "🔧 *명령어*\n"
        "/status - 시스템 상태 확인\n"
        "/benchmark - 성능 벤치마크 실행\n"
        "/mlx - MLX 모델 정보\n\n"
        "💬 이제 질문을 하시면 MLX 모델이 답변합니다!"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command handler"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{MLX_SERVER_URL}/health', timeout=5) as response:
                if response.status == 200:
                    health = await response.json()
                    model_info = health.get('performance', {})
                    
                    message = (
                        "📊 *붐엘 시스템 상태*\n\n"
                        "• 🖥️ 플랫폼: macOS M4 Pro\n"
                        f"• 🤖 모델: {model_info.get('model_id', 'Qwen2.5-7B-Instruct-MLX')}\n"
                        f"• ⚡ 로드 시간: {model_info.get('load_time', 0):.2f}초\n"
                        "• 🔧 MLX: ✅ 실행 중\n"
                        "• 🚀 최적화: Metal 가속 활성화\n"
                        "• 📡 서버: ✅ 연결됨"
                    )
                else:
                    message = "❌ MLX 서버 상태 확인 실패"
    except Exception as e:
        message = f"❌ 서버 연결 오류: {str(e)}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Benchmark command handler"""
    await update.message.reply_text(
        "🧪 *성능 테스트 시작*\n"
        "MLX 모델 응답 속도 테스트 중...",
        parse_mode='Markdown'
    )
    
    # 테스트 프롬프트
    test_prompt = "안녕하세요! 반갑습니다. 오늘 날씨가 좋네요."
    
    try:
        import time
        start_time = time.time()
        
        response = await query_mlx_server(test_prompt)
        
        elapsed_time = time.time() - start_time
        
        # 응답 길이 계산 (대략적인 토큰 수)
        approx_tokens = len(response.split()) * 1.3
        
        if elapsed_time > 0:
            tokens_per_second = approx_tokens / elapsed_time
        else:
            tokens_per_second = 0
        
        message = (
            "📊 *성능 테스트 결과*\n\n"
            f"• ⏱️ 응답 시간: {elapsed_time:.2f}초\n"
            f"• 📝 응답 길이: {len(response)}자\n"
            f"• ⚡ 예상 속도: {tokens_per_second:.1f} tokens/s\n\n"
            f"**테스트 응답:**\n{response[:200]}..."
        )
        
    except Exception as e:
        message = f"❌ 테스트 실패: {str(e)}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def mlx_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MLX info command handler"""
    message = (
        "🔧 *MLX 프레임워크 정보*\n\n"
        "• 🏗️ 상태: 설치 완료\n"
        "• 📍 경로: ~/mlx-venv\n"
        "• ⚡ 최적화: macOS Metal 가속\n"
        "• 🎯 목표: Ollama 대비 2-3배 속도 향상\n"
        "• 🤖 모델: Qwen2.5-7B-Instruct-4bit\n\n"
        "MLX는 Apple Silicon을 위한 머신러닝 프레임워크로,\n"
        "통합 메모리 아키텍처를 활용해 고속 추론이 가능합니다."
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages with MLX model"""
    user_message = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    logger.info(f"📨 메시지 수신: {user_name}({user_id}) - '{user_message[:50]}...'")
    
    # 처리 중 메시지
    processing_msg = await update.message.reply_text(
        "⚡ MLX 모델이 생각 중...",
        parse_mode='Markdown'
    )
    
    # MLX 서버에 쿼리
    logger.info(f"🔗 MLX 서버 쿼리 시작: '{user_message[:30]}...'")
    response = await query_mlx_server(user_message)
    logger.info(f"✅ MLX 서버 응답 받음: {len(response)}자")
    
    # 처리 중 메시지 삭제
    await processing_msg.delete()
    
    # 응답 전송 (너무 길면 분할)
    if len(response) > 4000:
        chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for i, chunk in enumerate(chunks):
            await update.message.reply_text(
                f"🤖 *붐엘 (MLX):*\n\n{chunk}",
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            f"🤖 *붐엘 (MLX):*\n\n{response}",
            parse_mode='Markdown'
        )
    
    logger.info(f"📤 응답 전송 완료: {user_name}({user_id})")

def main():
    """Run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("benchmark", benchmark))
    application.add_handler(CommandHandler("mlx", mlx_info))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run bot
    print("🤖 붐엘 텔레그램 봇 시작: @boomllm_bot (MLX 통합 버전 - 수정)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()