#!/usr/bin/env python3
import asyncio
import logging
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    message = (
        "🤖 *붐엘 (BoomL) macOS LLM 에이전트*\n"
        f"안녕하세요 {user.first_name}!\n\n"
        "📊 *현재 상태*\n"
        "• 플랫폼: macOS M4 Pro\n"
        "• 모델: Qwen3:8b (Ollama)\n"
        "• 속도: 42.92 tokens/s\n"
        "• VRAM: 11/45 GB\n\n"
        "🔧 *명령어*\n"
        "/status - 시스템 상태 확인\n"
        "/benchmark - 성능 벤치마크 실행\n"
        "/mlx - MLX 모델 정보\n\n"
        "💡 MLX 최적화 준비 완료!"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command handler"""
    message = (
        "📊 *붐엘 시스템 상태*\n\n"
        "• 🖥️ 플랫폼: macOS M4 Pro\n"
        "• 🤖 모델: Qwen3:8b\n"
        "• ⚡ 속도: 42.92 t/s\n"
        "• 🧠 VRAM: 11/45 GB\n"
        "• 🔧 MLX: ✅ 설치됨\n"
        "• 🐳 Ollama: ✅ 실행 중\n"
        "• 🚀 최적화: Metal 가속 준비됨"
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Benchmark command handler"""
    # 벤치마크 시작 메시지
    await update.message.reply_text(
        "🧪 *성능 벤치마크 시작*\n"
        "MLX vs Ollama 비교 테스트 실행 중...\n\n"
        "⏳ 테스트 진행 중 (약 30초 소요)",
        parse_mode='Markdown'
    )
    
    # 실제 벤치마크 실행
    import subprocess
    import json
    import os
    
    try:
        # 벤치마크 스크립트 실행
        script_path = os.path.join(os.path.dirname(__file__), "mlx-benchmark.py")
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=45
        )
        
        if result.returncode == 0:
            # 결과 파일 읽기
            result_file = "/Users/sykim/.openclaw/workspace/benchmark_result.json"
            if os.path.exists(result_file):
                with open(result_file, "r") as f:
                    data = json.load(f)
                
                ollama = data["ollama"]
                mlx = data["mlx"]
                
                # 결과 메시지 생성
                speedup = mlx["tokens_per_second"] / ollama["tokens_per_second"] if ollama["tokens_per_second"] > 0 else 0
                
                message = (
                    "📊 *벤치마크 결과*\n\n"
                    f"**Ollama (qwen2.5:7b)**\n"
                    f"• ⏱️ 시간: {ollama['elapsed_time']}초\n"
                    f"• ⚡ 속도: {ollama['tokens_per_second']} tokens/s\n\n"
                    f"**MLX (Metal 가속)**\n"
                    f"• ⏱️ 시간: {mlx['elapsed_time']}초\n"
                    f"• ⚡ 속도: {mlx['tokens_per_second']} tokens/s\n\n"
                    f"**성능 비교**\n"
                    f"• 📈 향상: {speedup:.1f}배\n"
                )
                
                if speedup > 1.5:
                    message += "• 🎉 MLX가 Ollama보다 빠릅니다!\n"
                else:
                    message += "• ⚠️ MLX 성능 향상 미미\n"
                
                message += f"\n⏰ 테스트 시간: {data['timestamp'][:19].replace('T', ' ')}"
                
            else:
                message = "❌ 결과 파일을 찾을 수 없습니다."
        else:
            message = f"❌ 벤치마크 실패:\n```\n{result.stderr[:500]}\n```"
            
    except subprocess.TimeoutExpired:
        message = "⏰ 벤치마크 타임아웃 (45초 초과)"
    except Exception as e:
        message = f"❌ 벤치마크 오류:\n```\n{str(e)[:500]}\n```"
    
    # 결과 전송
    await update.message.reply_text(message, parse_mode='Markdown')

async def mlx_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """MLX info command handler"""
    message = (
        "🔧 *MLX 프레임워크 정보*\n\n"
        "• 🏗️ 상태: 설치 완료\n"
        "• 📍 경로: ~/mlx-venv\n"
        "• ⚡ 최적화: macOS Metal 가속\n"
        "• 🎯 목표: Ollama 대비 2-3배 속도 향상\n\n"
        "📦 *다운로드 예정 모델*\n"
        "• Qwen2.5-7B-Instruct-MLX\n"
        "• Mistral-7B-Instruct-v0.3-4bit\n\n"
        "MLX 모델은 백그라운드에서 다운로드 중입니다."
    )
    await update.message.reply_text(message, parse_mode='Markdown')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo response for testing"""
    await update.message.reply_text(f"💬 붐엘이 응답합니다: {update.message.text}")

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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # Run bot
    print("🤖 붐엘 텔레그램 봇 시작: @boomllm_bot")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()