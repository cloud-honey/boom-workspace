#!/usr/bin/env python3
"""붐엘 텔레그램 봇 v2
- Qwen3-14B + TurboQuant 서버 연동
- 실시간 검색/날씨 지원 (서버 사이드)
"""
import asyncio
import logging
import aiohttp
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = '8592906266:AAGA326kDs1pNXbVRWbwtWxIUR3n9VkKQYE'
MLX_SERVER_URL = 'http://localhost:8000'


async def query_mlx(prompt: str, timeout_sec: int = 120) -> tuple[str, float]:
    """MLX 서버 쿼리 — (응답, 소요시간) 반환"""
    start = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MLX_SERVER_URL}/v1/chat/completions',
                json={
                    'messages': [{"role": "user", "content": prompt}],
                    'model': 'booml-mlx',
                    'max_tokens': 512,
                    'temperature': 0.5
                },
                timeout=aiohttp.ClientTimeout(total=timeout_sec)
            ) as resp:
                elapsed = time.time() - start
                if resp.status == 200:
                    data = await resp.json()
                    if 'choices' in data and data['choices']:
                        return data['choices'][0]['message']['content'], elapsed
                    return '응답 생성 실패', elapsed
                else:
                    err = await resp.text()
                    return f'서버 오류 {resp.status}: {err[:100]}', elapsed
    except asyncio.TimeoutError:
        return '⏰ 응답 시간 초과 (120초)', time.time() - start
    except Exception as e:
        return f'연결 오류: {str(e)}', time.time() - start


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # 서버 상태 체크
    status_str = "❌ 오프라인"
    model_name = "알 수 없음"
    turboquant = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{MLX_SERVER_URL}/health', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    health = await resp.json()
                    status_str = "✅ 온라인" if health.get('model_loaded') else "⏳ 로딩 중"
                    model_name = health.get('performance', {}).get('model_id', 'Qwen3-14B')
                    turboquant = health.get('turboquant', False)
    except:
        pass

    tq_str = "✅ 활성 (4.6x 메모리 절약)" if turboquant else "❌ 비활성"
    msg = (
        f"🤖 *붐엘 (BoomL) v2*\n"
        f"안녕하세요 {user.first_name}님!\n\n"
        f"📊 *시스템 상태*\n"
        f"• 플랫폼: macOS M4 Pro (64GB)\n"
        f"• 모델: {model_name}\n"
        f"• 엔진: MLX (Metal 가속)\n"
        f"• TurboQuant: {tq_str}\n"
        f"• 서버: {status_str}\n\n"
        f"🔧 *명령어*\n"
        f"/status - 시스템 상태\n"
        f"/benchmark - 성능 테스트\n\n"
        f"🔍 *기능*\n"
        f"• 실시간 웹 검색\n"
        f"• 날씨 조회\n"
        f"• 한국어 대화\n\n"
        f"💬 질문을 보내주세요!"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{MLX_SERVER_URL}/health', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    h = await resp.json()
                    perf = h.get('performance', {})
                    tq = "✅ 활성" if h.get('turboquant') else "❌ 비활성"
                    kv_bits = perf.get('kv_cache_bits', '?')
                    msg = (
                        f"📊 *붐엘 시스템 상태*\n\n"
                        f"• 🤖 모델: {perf.get('model_id', '?')}\n"
                        f"• ⚡ 로드 시간: {perf.get('load_time', 0):.1f}초\n"
                        f"• 🗜️ TurboQuant: {tq} ({kv_bits}bit KV캐시)\n"
                        f"• 🔧 MLX: ✅ 실행 중\n"
                        f"• 🚀 Metal 가속: 활성화\n"
                        f"• 🔍 실시간 검색: 활성화"
                    )
                else:
                    msg = "❌ 서버 응답 오류"
    except Exception as e:
        msg = f"❌ 서버 연결 실패: {str(e)}"
    await update.message.reply_text(msg, parse_mode='Markdown')


async def benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧪 *성능 테스트 중...*", parse_mode='Markdown')

    response, elapsed = await query_mlx("대한민국의 수도는 어디인가요? 간단히 답해주세요.")

    tokens_approx = len(response) / 2  # 한국어 근사
    tps = tokens_approx / elapsed if elapsed > 0 else 0

    msg = (
        f"📊 *벤치마크 결과*\n\n"
        f"• ⏱️ 응답 시간: {elapsed:.1f}초\n"
        f"• 📝 응답 길이: {len(response)}자\n"
        f"• ⚡ 예상 속도: {tps:.0f} tokens/s\n\n"
        f"*응답:*\n{response[:300]}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    user_name = update.effective_user.first_name
    user_id = update.effective_user.id

    logger.info(f"📨 {user_name}({user_id}): '{user_msg[:50]}'")

    processing = await update.message.reply_text("⚡ 생각 중...")

    response, elapsed = await query_mlx(user_msg)

    logger.info(f"✅ 응답: {len(response)}자, {elapsed:.1f}초")

    await processing.delete()

    # 응답 전송 (분할)
    header = f"🤖 *붐엘* _({elapsed:.1f}초)_\n\n"
    full = header + response

    if len(full) > 4000:
        chunks = [response[i:i+3800] for i in range(0, len(response), 3800)]
        for i, chunk in enumerate(chunks):
            prefix = header if i == 0 else ""
            try:
                await update.message.reply_text(f"{prefix}{chunk}", parse_mode='Markdown')
            except:
                await update.message.reply_text(f"{prefix}{chunk}")
    else:
        try:
            await update.message.reply_text(full, parse_mode='Markdown')
        except:
            await update.message.reply_text(f"🤖 붐엘 ({elapsed:.1f}초)\n\n{response}")

    logger.info(f"📤 전송 완료: {user_name}({user_id})")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("benchmark", benchmark))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 붐엘 봇 v2 시작: @boomllm_bot (Qwen3-14B + TurboQuant)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
