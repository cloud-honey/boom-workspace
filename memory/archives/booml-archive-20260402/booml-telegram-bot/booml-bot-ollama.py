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
# Ollama 서버 URL
OLLAMA_SERVER_URL = 'http://localhost:11434'

async def query_ollama(prompt: str) -> str:
    """Ollama 서버에 쿼리 보내기"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{OLLAMA_SERVER_URL}/api/generate',
                json={
                    'model': 'qwen2.5:7b',
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.7,
                        'num_predict': 500
                    }
                },
                timeout=60
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('response', '응답을 생성하지 못했습니다.')
                else:
                    error_text = await response.text()
                    return f'Ollama 서버 오류: {response.status} - {error_text[:100]}'
    except Exception as e:
        logger.error(f'Ollama 서버 쿼리 오류: {e}')
        return f'Ollama 서버 연결 오류: {str(e)}'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    message = (
        "🤖 *붐엘 (BoomL) macOS LLM 에이전트*\n"
        f"안녕하세요 {user.first_name}!\n\n"
        "📊 *현재 상태*\n"
        "• 플랫폼: macOS M4 Pro\n"
        "• 모델: Qwen2.5-7B (Ollama)\n"
        "• 엔진: Ollama 로컬 서버\n"
        "• 상태: ✅ Ollama 연결됨\n\n"
        "🔧 *명령어*\n"
        "/status - 시스템 상태 확인\n"
        "/benchmark - 성능 벤치마크 실행\n"
        "/info - 모델 정보\n\n"
        "💬 이제 질문을 하시면 Qwen2.5 모델이 답변합니다!"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command handler"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{OLLAMA_SERVER_URL}/api/tags', timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get('models', [])
                    model_list = "\n".join([f"• {m.get('name', 'unknown')}" for m in models[:3]])
                    
                    message = (
                        "📊 *붐엘 시스템 상태*\n\n"
                        "• 🖥️ 플랫폼: macOS M4 Pro\n"
                        "• 🤖 모델: Qwen2.5-7B (Ollama)\n"
                        "• ⚡ 엔진: Ollama 로컬 서버\n"
                        "• 📡 연결: ✅ 정상\n\n"
                        f"**로드된 모델:**\n{model_list}"
                    )
                else:
                    message = "❌ Ollama 서버 상태 확인 실패"
    except Exception as e:
        message = f"❌ 서버 연결 오류: {str(e)}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Benchmark command handler"""
    await update.message.reply_text(
        "🧪 *성능 테스트 시작*\n"
        "Ollama 모델 응답 속도 테스트 중...",
        parse_mode='Markdown'
    )
    
    # 테스트 프롬프트
    test_prompt = "안녕하세요! 반갑습니다. 오늘 날씨가 좋네요."
    
    try:
        import time
        start_time = time.time()
        
        response = await query_ollama(test_prompt)
        
        elapsed_time = time.time() - start_time
        
        message = (
            "📊 *성능 테스트 결과*\n\n"
            f"• ⏱️ 응답 시간: {elapsed_time:.2f}초\n"
            f"• 📝 응답 길이: {len(response)}자\n\n"
            f"**테스트 응답:**\n{response[:200]}..."
        )
        
    except Exception as e:
        message = f"❌ 테스트 실패: {str(e)}"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Info command handler"""
    message = (
        "🔧 *붐엘 모델 정보*\n\n"
        "• 🏗️ 플랫폼: Ollama\n"
        "• 🤖 모델: Qwen2.5-7B\n"
        "• 📊 파라미터: 70억\n"
        "• 🌐 언어: 한국어/영어/중국어\n"
        "• 🎯 용도: 일반 대화, 질문 답변\n\n"
        "Qwen2.5은 Alibaba에서 개발한 다국어 LLM으로,\n"
        "한국어 이해도와 생성 능력이 우수합니다."
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages with Ollama model"""
    user_message = update.message.text
    
    # 처리 중 메시지
    processing_msg = await update.message.reply_text(
        "⚡ Qwen2.5 모델이 생각 중...",
        parse_mode='Markdown'
    )
    
    # Ollama 서버에 쿼리
    response = await query_ollama(user_message)
    
    # 처리 중 메시지 삭제
    await processing_msg.delete()
    
    # 응답 전송 (너무 길면 분할)
    if len(response) > 4000:
        chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for i, chunk in enumerate(chunks):
            await update.message.reply_text(
                f"🤖 *붐엘 (Qwen2.5):*\n\n{chunk}",
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            f"🤖 *붐엘 (Qwen2.5):*\n\n{response}",
            parse_mode='Markdown'
        )

def main():
    """Run the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("benchmark", benchmark))
    application.add_handler(CommandHandler("info", info))
    
    # Add message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run bot
    print("🤖 붐엘 텔레그램 봇 시작: @boomllm_bot (Ollama 통합 버전)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()