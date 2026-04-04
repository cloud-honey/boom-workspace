#!/usr/bin/env python3
"""붐엘 텔레그램 봇 v2 - 아키텍처 통합 버전
- Phase 1-2 아키텍처 통합
- 피드백 수집 기능 추가
- 사용자 통계 조회 기능
"""
import asyncio
import logging
import aiohttp
import time
import json
from collections import deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = '8592906266:AAGA326kDs1pNXbVRWbwtWxIUR3n9VkKQYE'
MLX_SERVER_URL = 'http://localhost:8000'

# 사용자별 대화 히스토리 (최근 10개 메시지 유지)
user_histories = {}
MAX_HISTORY_PER_USER = 10

# 피드백 버튼 상태 관리
user_feedback_state = {}

# 작업 취소 플래그
_cancel_requested = False

def request_cancel():
    global _cancel_requested
    _cancel_requested = True

def clear_cancel():
    global _cancel_requested
    _cancel_requested = False

def is_cancelled():
    return _cancel_requested

def get_user_history(user_id: int) -> deque:
    """사용자의 대화 히스토리 반환 (없으면 생성)"""
    if user_id not in user_histories:
        user_histories[user_id] = deque(maxlen=MAX_HISTORY_PER_USER)
    return user_histories[user_id]

def format_history_for_api(history: deque) -> list:
    """히스토리를 API 메시지 형식으로 변환"""
    messages = []
    for item in history:
        if item['role'] in ['user', 'assistant']:
            messages.append(item)
    return messages


async def query_mlx(prompt: str, user_id: int = None, project_id: str = None, timeout_sec: int = 120) -> tuple[str, float, dict]:
    """MLX 서버 쿼리 — 아키텍처 통합 버전"""
    start = time.time()
    try:
        # 사용자 ID 문자열 변환
        user_id_str = str(user_id) if user_id else "anonymous"
        
        # 아키텍처 통합 요청
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MLX_SERVER_URL}/v1/chat/completions',
                json={
                    'messages': [{'role': 'user', 'content': prompt}],
                    'model': 'booml-mlx',
                    'max_tokens': 512,
                    'temperature': 0.5,
                    'user_id': user_id_str,
                    'project_id': project_id
                },
                timeout=aiohttp.ClientTimeout(total=timeout_sec)
            ) as resp:
                elapsed = time.time() - start
                if resp.status == 200:
                    data = await resp.json()
                    if 'choices' in data and data['choices']:
                        response = data['choices'][0]['message']['content']
                        metadata = data.get('metadata', {})
                        
                        # 히스토리에 저장 (user_id 있을 때만)
                        if user_id:
                            history = get_user_history(user_id)
                            history.append({"role": "user", "content": prompt})
                            history.append({"role": "assistant", "content": response})
                        
                        return response, elapsed, metadata
                    return '응답 생성 실패', elapsed, {}
                else:
                    err = await resp.text()
                    return f'서버 오류 {resp.status}: {err[:100]}', elapsed, {}
    except asyncio.TimeoutError:
        return '⏰ 응답 시간 초과 (120초)', time.time() - start, {}
    except Exception as e:
        return f'연결 오류: {str(e)}', time.time() - start, {}


async def submit_feedback(user_id: int, feedback_type: str, content: str, context: str = None, project_id: str = None):
    """피드백 제출"""
    try:
        user_id_str = str(user_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MLX_SERVER_URL}/v1/feedback',
                json={
                    'user_id': user_id_str,
                    'feedback_type': feedback_type,
                    'content': content,
                    'context': context,
                    'project_id': project_id
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"피드백 제출 성공: user={user_id}, type={feedback_type}")
                    return True
                else:
                    logger.warning(f"피드백 제출 실패: {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"피드백 제출 오류: {e}")
        return False


async def get_user_stats(user_id: int, days: int = 7):
    """사용자 통계 조회"""
    try:
        user_id_str = str(user_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MLX_SERVER_URL}/v1/user/stats',
                json={
                    'user_id': user_id_str,
                    'days': days
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                else:
                    logger.warning(f"통계 조회 실패: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        return None


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/h — 도움말"""
    msg = (
        "🤖 *붐엘 명령어 도움말*\n\n"
        "💬 *대화*\n"
        "• 그냥 메시지 입력 → 붐엘 AI 응답\n\n"
        "🎬 *자막 추출*\n"
        "• `자막추출 [파일경로]` — 단일 파일 자막 추출\n"
        "• `/transcribe` — 기본 나스 폴더 전체 처리\n"
        "• `/transcribe [폴더경로]` — 지정 폴더 전체 처리\n"
        "• `/transcribe [폴더경로] base` — base 모델로 처리\n\n"
        "📊 *상태 & 통계*\n"
        "• `/status` — 서버 상태 확인\n"
        "• `/stats` — 사용 통계\n"
        "• `/benchmark` — 성능 테스트\n\n"
        "👍 *피드백*\n"
        "• `/feedback` — 피드백 안내\n"
        "• '좋아', '별로' 등 키워드로 자동 피드백\n\n"
        "❓ `/h` — 이 도움말"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # 히스토리 초기화
    if user_id in user_histories:
        user_histories[user_id].clear()
    
    # 서버 상태 체크
    status_str = "❌ 오프라인"
    model_name = "알 수 없음"
    turboquant = False
    architecture_enabled = False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{MLX_SERVER_URL}/health', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    health = await resp.json()
                    status_str = "✅ 온라인" if health.get('model_loaded') else "⏳ 로딩 중"
                    model_name = health.get('performance', {}).get('model_id', 'Qwen3-14B')
                    turboquant = health.get('turboquant', False)
                    architecture_enabled = health.get('architecture_enabled', False)
    except:
        pass

    tq_str = "✅ 활성 (4.6x 메모리 절약)" if turboquant else "❌ 비활성"
    arch_str = "✅ 통합됨" if architecture_enabled else "❌ 기본 모드"
    
    msg = (
        f"🤖 *붐엘 (BoomL) v2 - 아키텍처 통합*\n"
        f"안녕하세요 {user.first_name}님!\n\n"
        f"📊 *시스템 상태*\n"
        f"• 플랫폼: macOS M4 Pro (64GB)\n"
        f"• 모델: {model_name}\n"
        f"• 엔진: MLX (Metal 가속)\n"
        f"• TurboQuant: {tq_str}\n"
        f"• 아키텍처: {arch_str}\n"
        f"• 서버: {status_str}\n\n"
        f"🔧 *명령어*\n"
        f"/start - 대화 초기화\n"
        f"/status - 시스템 상태\n"
        f"/stats - 내 통계 보기\n"
        f"/feedback - 피드백 방법\n"
        f"/benchmark - 성능 테스트\n\n"
        f"🔍 *기능*\n"
        f"• 실시간 웹 검색 (자동)\n"
        f"• 날씨 조회 (자동)\n"
        f"• 대화 맥락 유지\n"
        f"• 사용자 선호도 학습\n"
        f"• 피드백 기반 개선\n\n"
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
                    arch = "✅ 통합됨" if h.get('architecture_enabled') else "❌ 기본 모드"
                    kv_bits = perf.get('kv_cache_bits', '?')
                    msg = (
                        f"📊 *붐엘 시스템 상태*\n\n"
                        f"• 🤖 모델: {perf.get('model_id', '?')}\n"
                        f"• ⚡ 로드 시간: {perf.get('load_time', 0):.1f}초\n"
                        f"• 🗜️ TurboQuant: {tq} ({kv_bits}bit KV캐시)\n"
                        f"• 🏗️ 아키텍처: {arch}\n"
                        f"• 🔧 MLX: ✅ 실행 중\n"
                        f"• 🚀 Metal 가속: 활성화\n"
                        f"• 🔍 실시간 검색: 활성화"
                    )
                else:
                    msg = "❌ 서버 응답 오류"
    except Exception as e:
        msg = f"❌ 서버 연결 실패: {str(e)}"
    await update.message.reply_text(msg, parse_mode='Markdown')


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사용자 통계 조회"""
    user = update.effective_user
    user_id = user.id
    
    await update.message.reply_text("📊 *통계 조회 중...*", parse_mode='Markdown')
    
    stats_data = await get_user_stats(user_id, days=7)
    
    if not stats_data:
        await update.message.reply_text("❌ 통계 조회 실패. 서버를 확인해주세요.")
        return
    
    # 통계 포맷팅
    msg = (
        f"📈 *{user.first_name}님의 붐엘 통계 (7일)*\n\n"
        f"• 💬 총 대화 턴: {stats_data.get('conversation_turns', 0)}회\n"
        f"• 👍 긍정 예시: {stats_data.get('positive_examples_count', 0)}개\n"
        f"• 👎 회피 태그: {stats_data.get('negative_tags_count', 0)}개\n"
        f"• 🏷️ 프로필: {'✅ 설정됨' if stats_data.get('profile_summary', {}).get('has_global_profile') else '❌ 없음'}\n\n"
    )
    
    # KPI 통계 추가
    kpi_stats = stats_data.get('kpi_stats', {})
    if kpi_stats.get('session_count', 0) > 0:
        msg += f"📊 *활동 요약*\n"
        msg += f"• 세션: {kpi_stats.get('session_count', 0)}회\n"
        msg += f"• 피드백: 👍{kpi_stats.get('feedback_summary', {}).get('positive', 0)} 👎{kpi_stats.get('feedback_summary', {}).get('negative', 0)}\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def feedback_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """피드백 방법 안내"""
    msg = (
        f"📝 *붐엘 피드백 시스템*\n\n"
        f"붐엘은 당신의 피드백을 통해 더 나은 답변을 학습합니다.\n\n"
        f"*피드백 방법:*\n"
        f"1. 답변에 반응하기:\n"
        f"   - 좋아요 버튼: 긍정 피드백\n"
        f"   - 싫어요 버튼: 부정 피드백\n\n"
        f"2. 직접 피드백:\n"
        f"   - \"이 스타일 좋아\" → 긍정 피드백\n"
        f"   - \"너무 길어\" → 부정 피드백\n"
        f"   - \"더 짧게\" → 암묵적 피드백\n\n"
        f"*학습 내용:*\n"
        f"• 답변 길이, 톤, 구조 선호도\n"
        f"• 회피해야 할 스타일\n"
        f"• 좋은 답변 예시 저장\n\n"
        f"피드백은 익명으로 처리되며, 더 나은 서비스를 위해 사용됩니다."
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cancel_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """진행 중인 작업 취소"""
    request_cancel()
    await update.message.reply_text("⛔ 취소 요청됨. 현재 파일 처리 후 중단됩니다.", parse_mode='Markdown')


async def benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧪 *성능 테스트 중...*", parse_mode='Markdown')

    response, elapsed, metadata = await query_mlx("대한민국의 수도는 어디인가요? 간단히 답해주세요.")

    tokens_approx = len(response) / 2
    tps = tokens_approx / elapsed if elapsed > 0 else 0
    
    arch_info = " (아키텍처 통합)" if metadata.get('architecture_enabled', False) else ""

    msg = (
        f"📊 *벤치마크 결과{arch_info}*\n\n"
        f"• ⏱️ 응답 시간: {elapsed:.1f}초\n"
        f"• 📝 응답 길이: {len(response)}자\n"
        f"• ⚡ 예상 속도: {tps:.0f} tokens/s\n\n"
        f"*응답:*\n{response[:300]}"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


MASTER_CHAT_ID = 47980209

async def notify_master(text: str):
    """마스터에게 텔레그램 알림 발송 (봇 토큰 직접 사용)"""
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": MASTER_CHAT_ID, "text": text, "parse_mode": "Markdown"},
                timeout=aiohttp.ClientTimeout(total=10)
            )
    except Exception as e:
        logger.error(f"마스터 알림 실패: {e}")


async def transcribe_file(file_path: str, model: str = "base", language: str = "ja", max_retries: int = 3) -> dict:
    """붐엘 서버에 자막 추출 요청 (최대 max_retries회 재시도)"""
    import os
    fname = os.path.basename(file_path)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{MLX_SERVER_URL}/v1/transcribe",
                    json={"file_path": file_path, "model": model, "language": language, "output_format": "srt"},
                    timeout=aiohttp.ClientTimeout(total=3600)
                ) as resp:
                    result = await resp.json()
                    if result.get("status") in ("done", "skipped"):
                        return result
                    # 서버가 오류 응답 반환
                    last_error = result.get("error", f"status={result.get('status')}")
                    logger.warning(f"자막추출 시도 {attempt}/{max_retries} 실패: {fname} — {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"자막추출 시도 {attempt}/{max_retries} 예외: {fname} — {last_error}")
        if attempt < max_retries:
            await asyncio.sleep(5 * attempt)  # 5초, 10초 대기 후 재시도
    # 최대 재시도 초과 — 마스터 알림
    msg = f"⚠️ *붐엘 자막추출 실패* ({max_retries}회 시도)\n📄 `{fname}`\n❌ `{str(last_error)[:300]}`"
    await notify_master(msg)
    return {"status": "error", "error": last_error}


async def translate_srt_file(srt_path: str, max_retries: int = 3) -> dict:
    """붐엘 서버에 SRT 한국어 번역 요청 (최대 max_retries회 재시도)"""
    import os
    fname = os.path.basename(srt_path)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{MLX_SERVER_URL}/v1/translate_srt",
                    json={"srt_path": srt_path, "batch_size": 10},
                    timeout=aiohttp.ClientTimeout(total=7200)
                ) as resp:
                    result = await resp.json()
                    if result.get("status") == "done":
                        return result
                    last_error = result.get("error", f"status={result.get('status')}")
                    logger.warning(f"번역 시도 {attempt}/{max_retries} 실패: {fname} — {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"번역 시도 {attempt}/{max_retries} 예외: {fname} — {last_error}")
        if attempt < max_retries:
            await asyncio.sleep(5 * attempt)
    # 최대 재시도 초과 — 마스터 알림
    msg = f"⚠️ *붐엘 번역 실패* ({max_retries}회 시도)\n📄 `{fname}`\n❌ `{str(last_error)[:300]}`"
    await notify_master(msg)
    return {"status": "error", "error": last_error}


async def scan_nas_videos(folder: str) -> list:
    """나스 폴더 하위 영상 파일 목록 반환 (srt 없는 것만)"""
    import os
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv'}
    videos = []
    for root, dirs, files in os.walk(folder):
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext in video_exts:
                full_path = os.path.join(root, f)
                srt_path = os.path.splitext(full_path)[0] + '.srt'
                if not os.path.exists(srt_path):
                    videos.append(full_path)
    return videos


PIPELINE_STATE_FILE = "/Users/sykim/.openclaw/workspace/logs/transcribe_pipeline.json"
WORK_LOG_FILE = "/Volumes/seot401/subtitle-work-log.md"

def load_pipeline_state() -> dict:
    """파이프라인 상태 불러오기"""
    import json, os
    if os.path.exists(PIPELINE_STATE_FILE):
        try:
            with open(PIPELINE_STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"done": [], "failed": []}

def save_pipeline_state(state: dict):
    """파이프라인 상태 저장"""
    import json, os
    os.makedirs(os.path.dirname(PIPELINE_STATE_FILE), exist_ok=True)
    with open(PIPELINE_STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def append_work_log(video_path: str, srt_path: str, ko_srt_path: str,
                    started_at: str, transcribe_sec: float, translate_sec: float,
                    model: str, blocks: int):
    """자막 작업 일지에 항목 추가"""
    import os
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fname = os.path.basename(video_path)
    srt_fname = os.path.basename(srt_path) if srt_path else "-"
    ko_fname = os.path.basename(ko_srt_path) if ko_srt_path else "-"
    size_gb = round(os.path.getsize(video_path) / 1024**3, 2) if os.path.exists(video_path) else 0

    # ko srt 글자 수
    total_chars = 0
    if ko_srt_path and os.path.exists(ko_srt_path):
        try:
            with open(ko_srt_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            # 타임코드·번호 제외 순수 텍스트만
            import re
            lines = content.split('\n')
            text_lines = [l for l in lines if l.strip()
                          and not l.strip().isdigit()
                          and '-->' not in l]
            total_chars = sum(len(l) for l in text_lines)
        except:
            pass

    entry = (
        f"\n---\n"
        f"## {fname}\n"
        f"- **등록일**: {now}\n"
        f"- **작업 시작**: {started_at}\n"
        f"- **모델**: {model}\n"
        f"- **파일 크기**: {size_gb} GB\n"
        f"- **자막 블록 수**: {blocks}개\n"
        f"- **한국어 자막 글자 수**: {total_chars:,}자\n"
        f"- **소요 시간**: 추출 {transcribe_sec}초 + 번역 {translate_sec}초\n"
        f"- **원본 SRT**: `{srt_fname}`\n"
        f"- **한국어 SRT**: `{ko_fname}`\n"
    )

    # 파일 없으면 헤더 생성
    if not os.path.exists(WORK_LOG_FILE):
        header = "# 📋 자막 작업 일지\n\n붐엘이 처리한 자막 작업 기록입니다.\n"
        with open(WORK_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(header)

    with open(WORK_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(entry)


async def cmd_transcribe_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/transcribe [폴더경로] [모델] [N개] — 나스 폴더 영상 N개씩 순차 자막 추출 (이어서 처리)"""
    args = list(context.args) if context.args else []

    # 모델 파싱
    valid_models = {"tiny", "base", "small", "medium", "large-v3"}
    model = "base"
    if args and args[-1].lower() in valid_models:
        model = args[-1].lower()
        args = args[:-1]

    # 개수 파싱
    limit = 5
    if args and args[-1].isdigit():
        limit = int(args[-1])
        args = args[:-1]

    folder = ' '.join(args) if args else '/Volumes/seot401/torrent'

    import os
    if not os.path.exists(folder):
        await update.message.reply_text(f"❌ 경로 없음: `{folder}`", parse_mode='Markdown')
        return

    # 파일 경로를 직접 준 경우 단일 파일 처리
    video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv'}
    if os.path.isfile(folder) and os.path.splitext(folder)[1].lower() in video_exts:
        srt_path = os.path.splitext(folder)[0] + '.srt'
        if os.path.exists(srt_path):
            await update.message.reply_text(f"⏭️ 이미 자막 있음: `{os.path.basename(srt_path)}`", parse_mode='Markdown')
            return
        msg = await update.message.reply_text(f"⏳ `{os.path.basename(folder)}` 처리 중...", parse_mode='Markdown')
        from datetime import datetime
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        result = await transcribe_file(folder, model=model)
        status_val = result.get("status", "")
        if status_val == "done":
            srt_out = result.get("srt_path", "")
            elapsed = result.get("elapsed_sec", 0)
            await msg.edit_text(f"✅ 자막 추출 완료!\n`{os.path.basename(srt_out)}`\n🔄 번역 중...", parse_mode='Markdown')
            if srt_out and os.path.exists(srt_out):
                tr = await translate_srt_file(srt_out)
                if tr.get("status") == "done":
                    ko_path = tr.get("output", tr.get("ko_srt_path", ""))
                    tr_elapsed = tr.get("elapsed_sec", 0)
                    await update.message.reply_text(
                        f"🇰🇷 번역 완료!\n`{os.path.basename(ko_path)}`\n⏱ 추출 {elapsed}초 + 번역 {tr_elapsed}초",
                        parse_mode='Markdown'
                    )
                    append_work_log(
                        video_path=folder, srt_path=srt_out, ko_srt_path=ko_path,
                        started_at=started_at, transcribe_sec=elapsed, translate_sec=tr_elapsed,
                        model=model, blocks=tr.get("blocks", 0)
                    )
        elif status_val == "skipped":
            await msg.edit_text(f"⏭️ 이미 처리됨: `{os.path.basename(folder)}`", parse_mode='Markdown')
        else:
            await msg.edit_text(f"❌ 실패: {result.get('error', '알 수 없는 오류')}", parse_mode='Markdown')
        return

    msg = await update.message.reply_text(f"🔍 스캔 중: `{folder}`", parse_mode='Markdown')
    all_videos = await scan_nas_videos(folder)

    if not all_videos:
        await msg.edit_text("✅ 자막 없는 영상 파일 없음 (모두 처리 완료)")
        return

    # 파이프라인 상태 로드 — 이미 처리된 파일 제외
    state = load_pipeline_state()
    done_set = set(state.get("done", []))
    pending = [v for v in all_videos if v not in done_set]

    total_remaining = len(pending)
    batch = pending[:limit]

    list_text = (
        f"📋 *자막 추출 파이프라인*\n\n"
        f"• 전체 미처리: {total_remaining}개\n"
        f"• 이번 배치: {len(batch)}개 (모델: {model})\n\n"
    )
    for i, v in enumerate(batch, 1):
        list_text += f"{i}. `{os.path.basename(v)}`\n"
    if total_remaining > limit:
        list_text += f"\n_나머지 {total_remaining - limit}개는 다음 /transcribe 실행 시 처리_"

    await msg.edit_text(list_text, parse_mode='Markdown')

    success, skipped, failed = 0, 0, 0
    clear_cancel()
    for i, video_path in enumerate(batch, 1):
        if is_cancelled():
            await update.message.reply_text(f"⛔ 작업 취소됨 ({i-1}/{len(batch)} 완료)", parse_mode='Markdown')
            clear_cancel()
            return
        fname = os.path.basename(video_path)
        prog_msg = await update.message.reply_text(
            f"⏳ [{i}/{len(batch)}] `{fname}` 처리 중...", parse_mode='Markdown'
        )

        try:
            result = await transcribe_file(video_path, model=model)
            status_val = result.get("status", "")

            if status_val == "done":
                elapsed = result.get("elapsed_sec", 0)
                srt_path = result.get("srt_path", "")
                state["done"].append(video_path)
                save_pipeline_state(state)
                await prog_msg.edit_text(
                    f"✅ [{i}/{len(batch)}] 자막 추출 완료!\n"
                    f"📄 `{fname}` ({elapsed}초)\n"
                    f"🔄 한국어 번역 중...",
                    parse_mode='Markdown'
                )
                # 자동 한국어 번역
                try:
                    tr = await translate_srt_file(srt_path)
                    ko_path = tr.get("output", "")
                    tr_elapsed = tr.get("elapsed_sec", 0)
                    tr_blocks = tr.get("blocks", 0)
                    await prog_msg.edit_text(
                        f"✅ [{i}/{len(batch)}] 완료!\n"
                        f"📄 `{fname}`\n"
                        f"⏱ 추출 {elapsed}초 + 번역 {tr_elapsed}초\n"
                        f"🇯🇵 `{os.path.basename(srt_path)}`\n"
                        f"🇰🇷 `{os.path.basename(ko_path)}`",
                        parse_mode='Markdown'
                    )
                    from datetime import datetime
                    append_work_log(
                        video_path=video_path, srt_path=srt_path, ko_srt_path=ko_path,
                        started_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                        transcribe_sec=elapsed, translate_sec=tr_elapsed,
                        model=model, blocks=tr_blocks
                    )
                except Exception as te:
                    await prog_msg.edit_text(
                        f"✅ [{i}/{len(batch)}] 자막 완료 (번역 실패)\n"
                        f"📄 `{fname}`\n`{str(te)[:100]}`",
                        parse_mode='Markdown'
                    )
                success += 1
            elif status_val == "skipped":
                state["done"].append(video_path)
                save_pipeline_state(state)
                await prog_msg.edit_text(
                    f"⏭ [{i}/{len(batch)}] 스킵 (이미 있음): `{fname}`", parse_mode='Markdown'
                )
                skipped += 1
            else:
                state.setdefault("failed", []).append(video_path)
                save_pipeline_state(state)
                await prog_msg.edit_text(
                    f"❌ [{i}/{len(batch)}] 실패: `{fname}`", parse_mode='Markdown'
                )
                failed += 1

        except Exception as e:
            state.setdefault("failed", []).append(video_path)
            save_pipeline_state(state)
            err_text = str(e)[:200]
            await prog_msg.edit_text(
                f"❌ [{i}/{len(batch)}] 오류: `{fname}`\n`{err_text}`", parse_mode='Markdown'
            )
            await notify_master(
                f"⚠️ *자막 파이프라인 오류* [{i}/{len(batch)}]\n📄 `{fname}`\n❌ `{err_text}`\n\n작업을 대기합니다."
            )
            failed += 1
            # 예외 발생 시 대기 (다음 파일 진행 중단)
            break

    remaining_after = total_remaining - len(batch)
    summary = (
        f"🎬 배치 완료!\n"
        f"✅ 성공: {success}개  ⏭ 스킵: {skipped}개  ❌ 실패: {failed}개\n\n"
    )
    if failed > 0:
        summary += f"⛔ 실패로 인해 작업이 중단됐습니다. 실패 사유를 확인 후 `/transcribe` 재실행하세요."
    elif remaining_after > 0:
        summary += f"📌 남은 파일: {remaining_after}개\n`/transcribe {limit}` 으로 이어서 처리하세요"
    else:
        summary += "🏁 전체 완료!"

    await update.message.reply_text(summary, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text
    user_name = update.effective_user.first_name
    user_id = update.effective_user.id

    logger.info(f"📨 {user_name}({user_id}): '{user_msg[:50]}'")

    # 자막추출 명령 처리
    if user_msg.strip().startswith("자막추출"):
        parts = user_msg.strip().split(None, 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ 사용법: `자막추출 /Volumes/seot401/torrent/폴더명/파일.mp4`", parse_mode='Markdown')
            return

        file_path = parts[1].strip()
        import os
        if not os.path.exists(file_path):
            await update.message.reply_text(f"❌ 파일 없음: `{file_path}`", parse_mode='Markdown')
            return

        srt_path = os.path.splitext(file_path)[0] + '.srt'
        if os.path.exists(srt_path):
            await update.message.reply_text(f"⏭ 이미 자막 있음: `{srt_path}`", parse_mode='Markdown')
            return

        fname = os.path.basename(file_path)
        size_gb = os.path.getsize(file_path) / 1024**3
        msg = await update.message.reply_text(
            f"⏳ 자막 추출 시작\n📄 `{fname}` ({size_gb:.1f}GB)\n모델: base",
            parse_mode='Markdown'
        )

        try:
            result = await transcribe_file(file_path, model="base")
            status = result.get("status", "")
            if status == "done":
                elapsed = result.get("elapsed_sec", 0)
                await msg.edit_text(
                    f"✅ 자막 추출 완료!\n📄 `{fname}` ({elapsed}초)\n🔄 한국어 번역 중...",
                    parse_mode='Markdown'
                )
                try:
                    tr = await translate_srt_file(srt_path)
                    ko_path = tr.get("output", "")
                    tr_elapsed = tr.get("elapsed_sec", 0)
                    await msg.edit_text(
                        f"✅ 완료!\n📄 `{fname}`\n"
                        f"⏱ 추출 {elapsed}초 + 번역 {tr_elapsed}초\n"
                        f"🇯🇵 `{os.path.basename(srt_path)}`\n"
                        f"🇰🇷 `{os.path.basename(ko_path)}`",
                        parse_mode='Markdown'
                    )
                    from datetime import datetime
                    append_work_log(
                        video_path=file_path, srt_path=srt_path, ko_srt_path=ko_path,
                        started_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                        transcribe_sec=elapsed, translate_sec=tr_elapsed,
                        model="base", blocks=tr.get("blocks", 0)
                    )
                except Exception as te:
                    await msg.edit_text(
                        f"✅ 자막 완료 (번역 실패)\n📄 `{fname}`\n`{str(te)[:100]}`",
                        parse_mode='Markdown'
                    )
            else:
                await msg.edit_text(f"❌ 실패: `{result}`", parse_mode='Markdown')
        except Exception as e:
            await msg.edit_text(f"❌ 오류: `{str(e)[:300]}`", parse_mode='Markdown')
        return

    # 피드백 처리 (특정 키워드)
    feedback_keywords = {
        "positive": ["좋아", "good", "잘했", "이 스타일 좋", "perfect"],
        "negative": ["별로", "bad", "못했", "너무 길", "어려워", "이해 안 가"],
        "implicit": ["더 짧게", "더 쉽게", "다시 정리", "표로", "단계별로"]
    }
    
    # 피드백 키워드 체크
    feedback_type = None
    feedback_content = None
    
    user_msg_lower = user_msg.lower()
    for f_type, keywords in feedback_keywords.items():
        for kw in keywords:
            if kw in user_msg_lower:
                feedback_type = f_type
                feedback_content = user_msg
                break
        if feedback_type:
            break
    
    # 피드백이면 처리하고 종료
    if feedback_type and feedback_content:
        # 마지막 응답 컨텍스트 가져오기
        last_response = None
        if user_id in user_histories and user_histories[user_id]:
            for item in reversed(user_histories[user_id]):
                if item['role'] == 'assistant':
                    last_response = item['content']
                    break
        
        # 피드백 제출
        success = await submit_feedback(
            user_id, feedback_type, feedback_content, 
            context=last_response
        )
        
        if success:
            await update.message.reply_text(f"✅ 피드백 감사합니다! ({feedback_type})")
        else:
            await update.message.reply_text("❌ 피드백 처리 실패")
        return

    processing = await update.message.reply_text("⚡ 생각 중...")

    response, elapsed, metadata = await query_mlx(user_msg, user_id=user_id)

    logger.info(f"✅ 응답: {len(response)}자, {elapsed:.1f}초")

    await processing.delete()

    # 피드백 버튼 생성
    keyboard = [
        [
            InlineKeyboardButton("👍 좋아요", callback_data=f"feedback_positive_{user_id}"),
            InlineKeyboardButton("👎 싫어요", callback_data=f"feedback_negative_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 마지막 응답 저장 (피드백 컨텍스트용)
    user_feedback_state[user_id] = response

    # 응답 전송
    header = f"🤖 *붐엘* _({elapsed:.1f}초)_\n\n"
    full = header + response

    if len(full) > 4000:
        chunks = [response[i:i+3800] for i in range(0, len(response), 3800)]
        for i, chunk in enumerate(chunks):
            prefix = header if i == 0 else ""
            try:
                if i == 0 and len(chunks) == 1:
                    await update.message.reply_text(f"{prefix}{chunk}", parse_mode='Markdown', reply_markup=reply_markup)
                else:
                    await update.message.reply_text(f"{prefix}{chunk}", parse_mode='Markdown')
            except:
                if i == 0 and len(chunks) == 1:
                    await update.message.reply_text(f"{prefix}{chunk}", reply_markup=reply_markup)
                else:
                    await update.message.reply_text(f"{prefix}{chunk}")
    else:
        try:
            await update.message.reply_text(full, parse_mode='Markdown', reply_markup=reply_markup)
        except:
            await update.message.reply_text(f"🤖 붐엘 ({elapsed:.1f}초)\n\n{response}", reply_markup=reply_markup)

    logger.info(f"📤 전송 완료: {user_name}({user_id})")


async def handle_feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """피드백 버튼 콜백 처리"""
    query = update.callback_query
    await query.answer()
    
    # 콜백 데이터 파싱: feedback_{type}_{user_id}
    data = query.data
    if not data.startswith("feedback_"):
        return
    
    parts = data.split("_")
    if len(parts) != 3:
        return
    
    feedback_type = parts[1]  # positive or negative
    target_user_id = int(parts[2])
    
    # 현재 사용자 확인
    current_user_id = query.from_user.id
    if current_user_id != target_user_id:
        await query.edit_message_text("❌ 다른 사용자의 피드백은 처리할 수 없습니다.")
        return
    
    # 피드백 컨텍스트 가져오기
    feedback_context = user_feedback_state.get(target_user_id, "알 수 없음")
    
    # 피드백 내용 생성
    feedback_content = f"버튼 {feedback_type} 피드백"
    
    # 피드백 제출
    success = await submit_feedback(
        target_user_id, feedback_type, feedback_content,
        context=feedback_context
    )
    
    if success:
        # 버튼 제거
        try:
            message_text = query.message.text_markdown_v2 or query.message.text
            await query.edit_message_text(
                text=message_text,
                parse_mode='Markdown' if query.message.text_markdown_v2 else None
            )
        except:
            pass
        
        # 확인 메시지
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"✅ {feedback_type} 피드백 감사합니다!",
            reply_to_message_id=query.message.message_id
        )
    else:
        await query.edit_message_text("❌ 피드백 처리 실패")


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/번역 [srt파일경로] — SRT 파일 한국어 번역"""
    import os
    args = context.args
    if not args:
        await update.message.reply_text(
            "사용법: `/번역 /Volumes/seot401/torrent/파일명.srt`\n\n"
            "SRT 파일을 한국어로 번역합니다.",
            parse_mode='Markdown'
        )
        return

    srt_path = ' '.join(args).strip()
    if not os.path.exists(srt_path):
        await update.message.reply_text(f"❌ 파일 없음: `{srt_path}`", parse_mode='Markdown')
        return

    if not srt_path.endswith('.srt'):
        await update.message.reply_text("❌ .srt 파일만 지원합니다.", parse_mode='Markdown')
        return

    fname = os.path.basename(srt_path)
    msg = await update.message.reply_text(f"🔄 번역 중...\n📄 `{fname}`", parse_mode='Markdown')

    result = await translate_srt_file(srt_path)
    if result.get("status") == "done":
        ko_path = result.get("output", result.get("ko_srt_path", ""))
        elapsed = result.get("elapsed_sec", 0)
        blocks = result.get("blocks", 0)
        ko_fname = os.path.basename(ko_path) if ko_path else "-"
        await msg.edit_text(
            f"🇰🇷 번역 완료!\n"
            f"📄 `{ko_fname}`\n"
            f"⏱ {elapsed}초  📝 {blocks}블록",
            parse_mode='Markdown'
        )
    else:
        err = result.get("error", "알 수 없는 오류")
        await msg.edit_text(f"❌ 번역 실패\n`{str(err)[:300]}`", parse_mode='Markdown')


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # 명령어 핸들러
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("feedback", feedback_info))
    app.add_handler(CommandHandler("benchmark", benchmark))
    app.add_handler(CommandHandler("transcribe", cmd_transcribe_scan))
    app.add_handler(CommandHandler("translate", cmd_translate))
    app.add_handler(CommandHandler("cancel", cancel_task))
    app.add_handler(CommandHandler("h", help_cmd))
    
    # 메시지 핸들러
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 콜백 쿼리 핸들러 (피드백 버튼)
    app.add_handler(CallbackQueryHandler(handle_feedback_callback))
    
    # "/" 메뉴 등록
    from telegram import BotCommand
    commands = [
        BotCommand("h", "도움말"),
        BotCommand("transcribe", "나스 폴더 자막 추출 [폴더경로] [모델]"),
        BotCommand("translate", "SRT 파일 한국어 번역 [srt경로]"),
        BotCommand("cancel", "진행 중인 작업 취소"),
        BotCommand("status", "서버 상태 확인"),
        BotCommand("stats", "사용 통계"),
        BotCommand("benchmark", "성능 테스트"),
        BotCommand("feedback", "피드백 안내"),
        BotCommand("start", "봇 시작"),
    ]

    async def post_init(application):
        await application.bot.set_my_commands(commands)
        print("✅ 봇 명령어 메뉴 등록 완료")

    app.post_init = post_init

    print("🤖 붐엘 봇 v2 아키텍처 통합 시작: @boomllm_bot")
    print(f"서버 URL: {MLX_SERVER_URL}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()