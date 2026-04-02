#!/usr/bin/env python3
"""붐엘 EXAONE 시험용 텔레그램 봇
- 기존 붐엘 봇과 분리
- 같은 토큰으로는 동시 polling 불가하므로 필요 시 단독 실행
- 목적: EXAONE 응답 품질 직접 체감 테스트
"""

import asyncio
import logging
import time
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = '8592906266:AAGA326kDs1pNXbVRWbwtWxIUR3n9VkKQYE'
EXAONE_SERVER_URL = 'http://localhost:8004'


async def query_exaone(prompt: str, timeout_sec: int = 180):
    start = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{EXAONE_SERVER_URL}/v1/chat/completions',
                json={
                    'messages': [{'role': 'user', 'content': prompt}],
                    'model': 'booml-exaone',
                    'max_tokens': 512,
                    'temperature': 0.5
                },
                timeout=aiohttp.ClientTimeout(total=timeout_sec)
            ) as resp:
                elapsed = time.time() - start
                if resp.status == 200:
                    data = await resp.json()
                    response = data['choices'][0]['message']['content']
                    metadata = data.get('metadata', {})
                    return response, elapsed, metadata
                err = await resp.text()
                return f'서버 오류 {resp.status}: {err[:200]}', elapsed, {}
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        return f'타임아웃 ({timeout_sec}초 초과)', elapsed, {}
    except Exception as e:
        elapsed = time.time() - start
        return f'연결 오류: {e}', elapsed, {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('🤖 EXAONE 시험용 붐엘입니다. 질문 보내주세요.')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{EXAONE_SERVER_URL}/health', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    h = await resp.json()
                    msg = (
                        f"📊 EXAONE 시험 상태\n\n"
                        f"• 모델: {h.get('model_id')}\n"
                        f"• 로드됨: {h.get('model_loaded')}\n"
                        f"• 업타임: {h.get('uptime_seconds', 0):.1f}초"
                    )
                else:
                    msg = '❌ 서버 응답 오류'
    except Exception as e:
        msg = f'❌ 서버 연결 실패: {e}'
    await update.message.reply_text(msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    processing = await update.message.reply_text('⚡ EXAONE 생각 중...')
    response, elapsed, metadata = await query_exaone(user_msg)
    try:
        await processing.delete()
    except:
        pass
    header = f"🤖 EXAONE 시험 _({elapsed:.1f}초)_\n\n"
    await update.message.reply_text(header + response)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('status', status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print('🤖 EXAONE 시험 봇 시작')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
