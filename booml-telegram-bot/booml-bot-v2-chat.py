#!/usr/bin/env python3
"""붐엘 텔레그램 봇 v2 - 아키텍처 통합 버전
- Phase 1-2 아키텍처 통합
- 피드백 수집 기능 추가
- 사용자 통계 조회 기능
"""
import asyncio
import logging
import os
import aiohttp
import httpx
import time
import json
import re
from collections import deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = '8721289461:AAHVUQEbVw7SsSCF9gDQbYCw_qUe2pNg0iw'
MLX_SERVER_URL = 'http://localhost:8001'
TOKEN_DASHBOARD_URL = 'http://localhost:8080'

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

async def log_to_token_dashboard(
    platform: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    success: bool,
    source: str = "telegram"
):
    """
    Send token usage data to token dashboard (fire-and-forget).
    Args:
        platform: Platform identifier (e.g., "booml2-telegram")
        model: Model name used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        duration_ms: Request duration in milliseconds
        success: Whether the request was successful
        source: Source of the request (default: "telegram")
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            payload = {
                "platform": platform,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": duration_ms,
                "success": success,
                "source": source
            }
            await client.post(f"{TOKEN_DASHBOARD_URL}/api/log", json=payload)
    except Exception as e:
        # Silently catch all exceptions (fire-and-forget)
        logger.debug(f"Token dashboard logging failed: {e}")


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


# ──────────────────────────────────────────────
# NAS 경로 유틸리티
# ──────────────────────────────────────────────
NAS_BASE_PATH = "/Users/sykim/nas"
NAS_TORRENT_PATH = os.path.join(NAS_BASE_PATH, "torrent")
OLD_NAS_PATH = "/Volumes/seot401/torrent"

def convert_nas_path(file_path: str) -> tuple[str, bool]:
    """NAS 경로 변환: 이전 경로 → 새 경로"""
    if file_path.startswith(OLD_NAS_PATH):
        new_path = file_path.replace(OLD_NAS_PATH, NAS_TORRENT_PATH, 1)
        logger.info(f"[NAS 경로 변환] {file_path} → {new_path}")
        return new_path, True
    return file_path, False

def resolve_nas_path(file_path: str) -> str:
    """NAS 경로 해결: 존재하는 경로 반환"""
    # 먼저 변환 시도
    converted_path, was_converted = convert_nas_path(file_path)

    if os.path.exists(converted_path):
        return converted_path

    # 변환된 경로가 없으면 원본 확인
    if was_converted and os.path.exists(file_path):
        logger.info(f"[NAS 경로] 변환된 경로 없음, 원본 사용: {file_path}")
        return file_path

    # 다른 가능한 경로 시도
    possible_paths = [
        converted_path,
        file_path,
        file_path.replace("/Volumes/seot401", NAS_BASE_PATH, 1) if "/Volumes/seot401" in file_path else None,
        file_path.replace("/nas", NAS_BASE_PATH, 1) if file_path.startswith("/nas") else None,
    ]

    for path in possible_paths:
        if path and os.path.exists(path):
            logger.info(f"[NAS 경로] 대체 경로 발견: {path}")
            return path

    # 어느 경로도 존재하지 않음
    return converted_path if was_converted else file_path


# ──────────────────────────────────────────────
# Tool Calling 정의 (OpenAI 포맷)
# ──────────────────────────────────────────────
BOOML_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information using DuckDuckGo",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a local file. Only /Users/sykim/ directory is allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to read"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a local file. Only /Users/sykim/ directory is allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List contents of a directory. Only /Users/sykim/ directory is allowed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the directory"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather information for a city using open-meteo.com API",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name (e.g., Seoul, Tokyo, New York)"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exec",
            "description": "Execute allowed shell commands on the system. Only safe read-only commands are allowed (ls, cat, grep, find, cd, pwd, date, echo, head, tail, wc, git, npm, etc.). No destructive commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for the command (default: /Users/sykim)"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "Read Boom's memory files (daily logs). Use 'today' for today's memory, 'yesterday', 'week' for recent 7 days, 'all' for all memory, or specify a date like '2026-04-07'",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Memory path: 'today', 'yesterday', 'week', 'all', or specific date 'YYYY-MM-DD'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_write",
            "description": "Write content to Boom's memory file. Automatically appends with timestamp. Use this to save important information, decisions, or notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to save to memory"
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional path override (default: today's memory file)"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch and extract readable content from a URL (HTML to text conversion). Returns title, description, and content preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "HTTP or HTTPS URL to fetch"
                    }
                },
                "required": ["url"]
            }
        }
    }
]


async def query_mlx(prompt: str, user_id: int = None, project_id: str = None, timeout_sec: int = 120, routing_strategy: str = None, messages: list = None, enable_tools: bool = True) -> tuple[str, float, dict]:
    """MLX 서버 쿼리 — 아키텍처 통합 + Tool Calling"""
    start = time.time()
    try:
        # 사용자 ID 문자열 변환
        user_id_str = str(user_id) if user_id else "anonymous"

        # 히스토리 포함 메시지 구성 (없으면 단일 메시지)
        api_messages = messages if messages else [{'role': 'user', 'content': prompt}]

        # API 요청 바디 구성
        json_body = {
            'messages': api_messages,
            'model': 'booml-mlx',
            'max_tokens': 2048,
            'temperature': 0.5,
            'user_id': user_id_str,
            'project_id': project_id,
        }

        # routing_strategy 추가
        if routing_strategy:
            json_body['routing_strategy'] = routing_strategy

        # Tool calling 활성화 시 tools 추가
        if enable_tools:
            json_body['tools'] = BOOML_TOOLS
            logger.info(f"Tool calling 활성화: {len(BOOML_TOOLS)}개 툴 전달")

        # 아키텍처 통합 요청
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{MLX_SERVER_URL}/v1/chat/completions',
                json=json_body,
                timeout=aiohttp.ClientTimeout(total=timeout_sec)
            ) as resp:
                elapsed = time.time() - start
                if resp.status == 200:
                    data = await resp.json()
                    if 'choices' in data and data['choices']:
                        response = data['choices'][0]['message']['content']
                        metadata = data.get('metadata', {})
                        usage = data.get('usage', {})

                        # 히스토리에 저장 (user_id 있을 때만)
                        if user_id:
                            history = get_user_history(user_id)
                            history.append({"role": "user", "content": prompt})
                            history.append({"role": "assistant", "content": response})

                        # Log token usage to dashboard (fire-and-forget)
                        duration_ms = int(elapsed * 1000)
                        input_tokens = usage.get('prompt_tokens', len(prompt) // 4)
                        output_tokens = usage.get('completion_tokens', len(response) // 4)
                        model_used = metadata.get('model_used', 'booml-mlx')
                        asyncio.create_task(log_to_token_dashboard(
                            platform="booml2-telegram",
                            model=model_used,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            duration_ms=duration_ms,
                            success=True,
                            source="telegram"
                        ))

                        return response, elapsed, metadata

                    # Log failure
                    duration_ms = int(elapsed * 1000)
                    asyncio.create_task(log_to_token_dashboard(
                        platform="booml2-telegram",
                        model="booml-mlx",
                        input_tokens=0,
                        output_tokens=0,
                        duration_ms=duration_ms,
                        success=False,
                        source="telegram"
                    ))
                    return '응답 생성 실패', elapsed, {}
                else:
                    # Log failure
                    duration_ms = int(elapsed * 1000)
                    asyncio.create_task(log_to_token_dashboard(
                        platform="booml2-telegram",
                        model="booml-mlx",
                        input_tokens=0,
                        output_tokens=0,
                        duration_ms=duration_ms,
                        success=False,
                        source="telegram"
                    ))
                    err = await resp.text()
                    return f'서버 오류 {resp.status}: {err[:100]}', elapsed, {}
    except asyncio.TimeoutError:
        duration_ms = int((time.time() - start) * 1000)
        asyncio.create_task(log_to_token_dashboard(
            platform="booml2-telegram",
            model="booml-mlx",
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
            success=False,
            source="telegram"
        ))
        return '⏰ 응답 시간 초과 (120초)', time.time() - start, {}
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        asyncio.create_task(log_to_token_dashboard(
            platform="booml2-telegram",
            model="booml-mlx",
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
            success=False,
            source="telegram"
        ))
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
        "📰 *이란 뉴스*\n"
        "• `/news` — 이란 매체 vs 서방 매체 교차검증 리포트\n"
        "• 자동: 매일 아침 8시 KST 전송\n\n"
        "🌐 *크롤링*\n"
        "• `/crawl [URL]` — 사이트/PDF 크롤링 + 한국어 번역 + 파일 저장\n\n"
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


def get_video_duration(file_path: str) -> float:
    """ffprobe로 영상 길이(초) 반환. 실패 시 -1"""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return -1.0


def estimate_transcribe_time(duration_sec: float, model: str = "base") -> str:
    """모델별 예상 추출 시간 문자열 반환"""
    # 경험치: base 모델 기준 영상 1분 → 약 10~15초 처리 (맥미니 M2 MLX)
    speed_factor = {"tiny": 5, "base": 12, "small": 20, "medium": 40, "large-v3": 90}.get(model, 12)
    est_sec = int((duration_sec / 60) * speed_factor)
    if est_sec < 60:
        return f"~{est_sec}초"
    return f"~{est_sec // 60}분 {est_sec % 60}초"


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
WORK_LOG_FILE = "/Users/sykim/nas/subtitle-work-log.md"

def load_pipeline_state() -> dict:
    """파이프라인 상태 불러오기 (NAS 경로 변환 포함)"""
    import json, os
    if os.path.exists(PIPELINE_STATE_FILE):
        try:
            with open(PIPELINE_STATE_FILE, 'r') as f:
                state = json.load(f)
            
            # NAS 경로 변환: /Volumes/seot401/torrent → /Users/sykim/nas/torrent
            converted_state = {"done": [], "failed": []}
            for key in ["done", "failed"]:
                if key in state:
                    for path in state[key]:
                        if path.startswith("/Volumes/seot401/torrent"):
                            new_path = path.replace("/Volumes/seot401/torrent", "/Users/sykim/nas/torrent", 1)
                            converted_state[key].append(new_path)
                            logger.info(f"[pipeline] 경로 변환: {path} → {new_path}")
                        else:
                            converted_state[key].append(path)
            
            return converted_state
        except Exception as e:
            logger.error(f"[pipeline] 상태 로드 오류: {e}")
            pass
    return {"done": [], "failed": []}

def save_pipeline_state(state: dict):
    """파이프라인 상태 저장 (NAS 경로 변환 포함)"""
    import json, os
    os.makedirs(os.path.dirname(PIPELINE_STATE_FILE), exist_ok=True)
    
    # 저장할 상태 복사
    save_state = {"done": [], "failed": []}
    for key in ["done", "failed"]:
        if key in state:
            for path in state[key]:
                # 이미 변환된 경로인지 확인
                if path.startswith("/Users/sykim/nas/torrent"):
                    save_state[key].append(path)
                elif path.startswith("/Volumes/seot401/torrent"):
                    # 변환 필요
                    new_path = path.replace("/Volumes/seot401/torrent", "/Users/sykim/nas/torrent", 1)
                    save_state[key].append(new_path)
                    logger.info(f"[pipeline] 저장 전 경로 변환: {path} → {new_path}")
                else:
                    save_state[key].append(path)
    
    with open(PIPELINE_STATE_FILE, 'w') as f:
        json.dump(save_state, f, ensure_ascii=False, indent=2)


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

    folder = ' '.join(args) if args else '/Users/sykim/nas/torrent'

    import os
    
    # NAS 경로 해결
    folder = resolve_nas_path(folder)
    
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
        dur = get_video_duration(v)
        if dur > 0:
            est = estimate_transcribe_time(dur, model)
            dur_min = int(dur // 60)
            list_text += f"{i}. `{os.path.basename(v)}` ({dur_min}분, 예상 {est})\n"
        else:
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
        duration = get_video_duration(video_path)
        if duration > 0:
            est = estimate_transcribe_time(duration, model)
            dur_min = int(duration // 60)
            prog_msg = await update.message.reply_text(
                f"⏳ [{i}/{len(batch)}] `{fname}`\n"
                f"🎬 영상 길이: {dur_min}분 | 예상 추출: {est}",
                parse_mode='Markdown'
            )
        else:
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

    # 슬래시 명령은 CommandHandler에서 처리 — 혹시 여기 도달하면 무시
    if user_msg.strip().startswith("/"):
        return

    # 자막추출 명령 처리
    if user_msg.strip().startswith("자막추출"):
        parts = user_msg.strip().split(None, 1)
        if len(parts) < 2:
            await update.message.reply_text("❌ 사용법: `자막추출 /Users/sykim/nas/torrent/폴더명/파일.mp4`", parse_mode='Markdown')
            return

        file_path = parts[1].strip()
        import os
        
        # NAS 경로 해결
        file_path = resolve_nas_path(file_path)
        
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

    # 대화 히스토리 포함해서 API 호출
    history = get_user_history(user_id)
    history_msgs = format_history_for_api(history)
    full_messages = history_msgs + [{'role': 'user', 'content': user_msg}]
    response, elapsed, metadata = await query_mlx(user_msg, user_id=user_id, messages=full_messages)

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


async def cmd_clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/clean [srt경로] — SRT 환각 제거 + 검증"""
    import os
    raw_text = update.message.text or ""
    srt_path = raw_text.split(' ', 1)[1].strip() if ' ' in raw_text else ""

    if not srt_path:
        await update.message.reply_text(
            "사용법: `/clean /Users/sykim/nas/torrent/파일명.srt`\n\n"
            "반복 자막 제거 + 검증 리포트를 출력합니다.",
            parse_mode='Markdown'
        )
        return
    
    # NAS 경로 해결
    srt_path = resolve_nas_path(srt_path)

    if not os.path.exists(srt_path):
        await update.message.reply_text(f"❌ 파일 없음: `{srt_path}`", parse_mode='Markdown')
        return

    msg = await update.message.reply_text(f"🧹 클리닝 중...\n`{os.path.basename(srt_path)}`", parse_mode='Markdown')

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{MLX_SERVER_URL}/v1/clean_srt",
                json={"srt_path": srt_path},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                result = await resp.json()

        fname = os.path.basename(srt_path)
        removed = result.get("blocks_removed", 0)
        original = result.get("blocks_original", 0)
        after = result.get("blocks_after", 0)
        warnings = result.get("warnings", [])

        text = (
            f"✅ 클리닝 완료: `{fname}`\n"
            f"📊 {original}개 → {after}개 (제거: {removed}개)\n"
        )
        if warnings:
            text += "\n⚠️ 경고:\n" + "\n".join(f"• {w}" for w in warnings)
        else:
            text += "✔️ 이상 없음"

        await msg.edit_text(text, parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ 오류: `{str(e)[:200]}`", parse_mode='Markdown')


async def cmd_translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/translate [srt파일경로] — SRT 파일 한국어 번역"""
    import os
    # context.args가 한글 경로를 잘못 파싱할 수 있으므로 직접 파싱
    raw_text = update.message.text or ""
    # "/translate " 이후 전체 경로
    if ' ' in raw_text:
        srt_path = raw_text.split(' ', 1)[1].strip()
    else:
        srt_path = ' '.join(context.args).strip() if context.args else ""

    if not srt_path:
        await update.message.reply_text(
            "사용법: `/translate /Users/sykim/nas/torrent/파일명.srt`\n\n"
            "SRT 파일을 한국어로 번역합니다.",
            parse_mode='Markdown'
        )
        return
    
    # NAS 경로 해결
    srt_path = resolve_nas_path(srt_path)

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


# ── 이란 뉴스 교차검증 ────────────────────────────────────────────────────────

IRAN_SOURCES = {
    "이란측": [
        {"name": "PressTV (Iran)",  "rss": "https://www.presstv.ir/rss/rss-101.xml"},   # Iran 섹션 전용
        {"name": "PressTV (World)", "rss": "https://www.presstv.ir/rss.xml"},            # 전체 뉴스
    ],
    "서방/중립": [
        {"name": "Reuters Iran", "rss": "https://news.google.com/rss/search?q=iran+reuters&hl=en-US&gl=US&ceid=US:en"},
        {"name": "AP News Iran", "rss": "https://news.google.com/rss/search?q=iran+ap+news&hl=en-US&gl=US&ceid=US:en"},
        {"name": "BBC Iran",     "rss": "https://news.google.com/rss/search?q=iran+bbc&hl=en-US&gl=US&ceid=US:en"},
        {"name": "Iran Ceasefire", "rss": "https://news.google.com/rss/search?q=iran+ceasefire+OR+truce+OR+gaza&hl=en-US&gl=US&ceid=US:en"},
    ],
}

async def fetch_iran_news(max_per_source: int = 5, max_hours: int = 0) -> dict:
    """RSS 피드에서 이란 관련 최신 기사 수집 (최근 max_hours 시간 이내, 중복 제외)"""
    import os
    import feedparser
    import email.utils
    from datetime import datetime, timezone, timedelta
    keywords = ["iran", "tehran", "khamenei", "khomeini", "rouhani", "raisi", "irgc",
                "nuclear", "sanctions", "persian", "islamic republic",
                "ceasefire", "cease-fire", "truce", "gaza", "hostage", "hamas", "hezbollah",
                "missile", "drone", "attack", "strait of hormuz"]
    # 서방측은 Google RSS가 이미 이란 관련이므로, 키워드 없이 수거 (title/summary에 iran 관련 단어 포함만 확인)
    west_keywords = ["iran", "tehran", "khamenei", "irgc", "nuclear", "sanction", "persian",
                     "ceasefire", "cease-fire", "truce", "gaza", "hamas", "hezbollah", "hormuz"]

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours) if max_hours > 0 else None
    now_utc = datetime.now(timezone.utc)
    dedup_window = timedelta(hours=1)  # 1시간 이내 수집된 링크만 중복으로 간주

    # ── 중복 추적 파일 ({link: iso_timestamp} 형식) ────────────────────────
    seen_file = "/Users/sykim/workspace/crawled/iran-news-seen.json"
    seen_links = set()
    if os.path.exists(seen_file):
        try:
            with open(seen_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # 구형(list) 포맷 호환 처리
            if isinstance(raw, list):
                raw = {}
            # 1시간 이내 수집된 링크만 중복 대상으로
            seen_links = {
                link for link, ts_str in raw.items()
                if now_utc - datetime.fromisoformat(ts_str) < dedup_window
            }
        except Exception:
            seen_links = set()

    results = {"이란측": [], "서방/중립": []}

    def parse_pub_date(entry) -> datetime | None:
        """RSS 발행시간 파싱 → UTC datetime. 실패 시 None."""
        # feedparser가 파싱한 struct_time 우선
        for field in ("published_parsed", "updated_parsed"):
            t = entry.get(field)
            if t:
                try:
                    return datetime(*t[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
        # raw 문자열 fallback
        for field in ("published", "updated", "pubDate"):
            raw = entry.get(field, "")
            if raw:
                try:
                    return email.utils.parsedate_to_datetime(raw).astimezone(timezone.utc)
                except Exception:
                    pass
        return None

    def fmt_kst(dt: datetime | None) -> str:
        """UTC → KST 문자열 (없으면 '시간 미상')"""
        if dt is None:
            return "시간 미상"
        kst = dt + timedelta(hours=9)
        return kst.strftime("%m/%d %H:%M KST")

    async def fetch_feed(session, src_name, rss_url, side):
        try:
            async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=15),
                                   headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status != 200:
                    return
                text = await resp.text()
            feed = feedparser.parse(text)
            count = 0
            for entry in feed.entries:
                if count >= max_per_source:
                    break
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))[:300]
                link = entry.get("link", "")
                pub_dt = parse_pub_date(entry)

                # 시간 필터: 파싱 성공 시 cutoff 이후만, 실패 시 통과
                if cutoff and pub_dt and pub_dt < cutoff:
                    continue

                # 이란측은 모든 기사, 서방측은 이란 관련 키워드 필터 (브로드 매치)
                # 중복 필터: 이미 수집된 링크 제외
                if not link or link in seen_links:
                    continue
                kw_list = keywords if side == "이란측" else west_keywords
                if side == "이란측" or any(k in (title + summary).lower() for k in kw_list):
                    results[side].append({
                        "source": src_name,
                        "title": title,
                        "summary": re.sub(r'<[^>]+>', '', summary).strip(),
                        "link": link,
                        "pub_dt": pub_dt,
                        "pub_str": fmt_kst(pub_dt),
                    })
                    count += 1
        except Exception as e:
            logger.warning(f"RSS 수집 실패 {src_name}: {e}")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for side, sources in IRAN_SOURCES.items():
            for src in sources:
                tasks.append(fetch_feed(session, src["name"], src["rss"], side))
        await asyncio.gather(*tasks)

    # 최신순 정렬 (pub_dt 없는 기사는 뒤로)
    for side in results:
        results[side].sort(key=lambda a: a["pub_dt"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return results


async def analyze_iran_news(news: dict, user_id: int = None) -> str:
    """붐엘에게 교차검증 분석 요청"""
    iran_text = "\n".join(
        f"[{a['source']}|{a['pub_str']}] {a['title']}\n{a['summary']}" for a in news["이란측"][:8]
    ) or "기사 없음"
    west_text = "\n".join(
        f"[{a['source']}|{a['pub_str']}] {a['title']}\n{a['summary']}" for a in news["서방/중립"][:8]
    ) or "기사 없음"

    prompt = f"""아래는 오늘의 이란 관련 뉴스입니다. 이란 매체와 서방/중립 매체의 보도를 비교 분석해서 한국어로 리포트를 작성해주세요.

## 이란 매체 기사
{iran_text}

## 서방/중립 매체 기사
{west_text}

다음 형식으로 작성해주세요:
1. **주요 이슈 요약** (오늘 가장 중요한 이란 관련 이슈 2~3개)
2. **공통 보도 내용** (양쪽 모두 동의하는 사실)
3. **시각 차이** (이란 측 주장 vs 서방 측 주장이 다른 부분)
4. **신뢰도 평가** (어느 쪽 보도가 더 균형잡혀 보이는지, 이유 포함)

간결하고 명확하게 작성해주세요."""

    # routing_strategy="direct" → 메모리/히스토리 주입 없이 순수 모델 직접 호출
    response, elapsed, _ = await query_mlx(prompt, user_id=None, timeout_sec=300, routing_strategy="direct")
    return response, elapsed


XPS_IRAN_API = "http://100.116.65.86:3004/api/iran-news/latest"


async def fetch_iran_news_xps() -> dict:
    """XPS API에서 이란 뉴스 가져오기"""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(XPS_IRAN_API, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    logger.warning(f"XPS API 응답 오류: {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"XPS 뉴스 수집 실패: {e}")
        return None


async def send_iran_news_report(bot, chat_id: int, user_id: int = None):
    """XPS API 기반 이란 뉴스 리포트 — 스펙 형식"""
    try:
        await bot.send_message(chat_id=chat_id, text="📡 이란 뉴스 수집 중 (XPS)...")
        news_data = await fetch_iran_news_xps()

        if not news_data:
            await bot.send_message(chat_id=chat_id, text="❌ 뉴스를 가져올 수 없습니다 (XPS API 응답 없음)")
            return

        articles = news_data.get("articles", [])
        metadata = news_data.get("metadata", {})
        collected_at = metadata.get("collectedAt", "")

        if not articles:
            await bot.send_message(chat_id=chat_id, text="❌ 수집된 기사가 없습니다.")
            return

        # ── 스펙 형식: 🇮🇷 이란 뉴스 (수집 {collectedAt} 기준) ──
        lines = []
        lines.append(f"🇮🇷 *이란 뉴스* (수집 {collected_at[:16]} 기준)\n")

        for art in articles[:15]:
            title = art.get("title", "")
            source_name = art.get("sourceName", art.get("source", ""))
            published = art.get("publishedAt", "")[:16]
            summary = art.get("summary", "")[:300]
            url = art.get("url", "")
            cv = art.get("crossValidation", {})
            has_western = cv.get("hasWesternCoverage", False)
            confidence = cv.get("confidenceScore", 0)

            lines.append(f"[{source_name}] {title}")
            lines.append(f"⏰ {published} | 신뢰도: {confidence}%")

            if has_western:
                lines.append("🔄 *CROSS-VALIDATED*")
                western_sources = cv.get("westernSources", [])
                if western_sources:
                    lines.append(f"🌐 서방 확인: {', '.join(western_sources[:3])}")

            lines.append(f"_{summary}_")
            if url and url != "#":
                lines.append(f"🔗 {url}")
            lines.append("")

        full_text = "\n".join(lines).strip()

        # 저장
        from datetime import datetime
        import os
        ts = datetime.now().strftime("%Y%m%d-%H%M")
        save_dir = "/Users/sykim/workspace/crawled"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"iran-news-xps-{ts}.md")

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(f"# 이란 뉴스 리포트\n\n")
            f.write(f"- **생성:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"- **수집:** {len(articles)}건\n\n---\n\n")
            f.write(full_text)
            f.write(f"\n\n---\n\n## 원본 데이터\n\n```json\n{json.dumps(news_data, ensure_ascii=False, indent=2)}\n```\n")

        # 전송 (4000자 초과 시 분할)
        if len(full_text) > 4000:
            await bot.send_message(chat_id=chat_id, text=full_text[:3900] + "\n_(계속)_", parse_mode="Markdown")
            await bot.send_message(chat_id=chat_id, text=full_text[3900:], parse_mode="Markdown")
        else:
            try:
                await bot.send_message(chat_id=chat_id, text=full_text, parse_mode="Markdown")
            except Exception:
                await bot.send_message(chat_id=chat_id, text=full_text)

        await bot.send_message(chat_id=chat_id, text=f"💾 저장: `{save_path}`", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"이란 뉴스 리포트 오류: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ 오류: {str(e)[:200]}")


async def send_news_report(bot, chat_id: int, user_id: int = None, save_seen: bool = False):
    """호환성 유지 — /news는 iran_news_report로 위임"""
    await send_iran_news_report(bot, chat_id, user_id)


async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/news — 이란 뉴스 리포트 (XPS API)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await send_iran_news_report(update.get_bot(), chat_id, user_id)


async def cmd_iran_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/irannews — 이란 뉴스 리포트 (XPS API)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await send_iran_news_report(update.get_bot(), chat_id, user_id)


async def scheduled_news_report(context):
    """매일 아침 자동 뉴스 리포트"""
    await send_iran_news_report(context.bot, MASTER_CHAT_ID)


async def cmd_crawl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/crawl [URL] — 사이트 크롤링 → 정리 → 한국어 번역 → 파일 저장"""
    import os
    from datetime import datetime
    from urllib.parse import urlparse

    raw_text = update.message.text or ""
    url = raw_text.split(' ', 1)[1].strip() if ' ' in raw_text else ""

    if not url:
        await update.message.reply_text(
            "사용법: `/crawl https://example.com/page`\n\n"
            "웹페이지를 크롤링해서 마크다운으로 정리 및 한국어 번역합니다.",
            parse_mode='Markdown'
        )
        return

    if not url.startswith('http'):
        await update.message.reply_text("❌ 유효한 URL을 입력해주세요 (http:// 또는 https://로 시작)", parse_mode='Markdown')
        return

    is_pdf = url.lower().split('?')[0].endswith('.pdf')
    msg = await update.message.reply_text(
        f"{'📄 PDF' if is_pdf else '🌐 크롤링'} 처리 중...\n`{url}`", parse_mode='Markdown'
    )

    try:
        from bs4 import BeautifulSoup
        import html2text
        import tempfile, os as _os

        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        truncated = False
        MAX_CHARS = 6000

        if is_pdf:
            # ── PDF 처리 ──────────────────────────────────────────────────
            from pdfminer.high_level import extract_text as pdf_extract_text

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        await msg.edit_text(f"❌ PDF 응답 오류: {resp.status}", parse_mode='Markdown')
                        return
                    pdf_bytes = await resp.read()

            # 임시 파일로 저장 후 텍스트 추출
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            try:
                raw_text = pdf_extract_text(tmp_path)
            finally:
                _os.unlink(tmp_path)

            # 정리
            markdown_content = re.sub(r'\n{3,}', '\n\n', raw_text).strip()
            # URL에서 파일명을 제목으로
            fname = url.split('/')[-1].split('?')[0].replace('_', ' ').replace('-', ' ')
            title_text = fname if fname else "PDF 문서"

            size_kb = round(len(pdf_bytes) / 1024)
            await msg.edit_text(
                f"✅ PDF 추출 완료 ({size_kb}KB, {len(markdown_content)}자)\n🤖 붐엘이 번역 중...",
                parse_mode='Markdown'
            )

        else:
            # ── HTML 크롤링 ───────────────────────────────────────────────
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        await msg.edit_text(f"❌ 페이지 응답 오류: {resp.status}", parse_mode='Markdown')
                        return
                    html = await resp.text()

            soup = BeautifulSoup(html, 'lxml')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe']):
                tag.decompose()

            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else "제목 없음"

            content_el = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|main|article', re.I)) or soup.body
            if not content_el:
                content_el = soup

            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.body_width = 0
            h.unicode_snob = True
            markdown_content = h.handle(str(content_el))
            markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content).strip()

            await msg.edit_text(
                f"✅ 크롤링 완료 ({len(markdown_content)}자)\n🤖 붐엘이 번역 중...",
                parse_mode='Markdown'
            )

        total_len = len(markdown_content)
        CHUNK_SIZE = 5000
        chunks = [markdown_content[i:i+CHUNK_SIZE] for i in range(0, total_len, CHUNK_SIZE)]
        total_chunks = len(chunks)

        await msg.edit_text(
            f"✅ 추출 완료 ({total_len:,}자 · {total_chunks}청크)\n🤖 번역 시작 (1/{total_chunks})...",
            parse_mode='Markdown'
        )

        # 3. 청크별 번역 → 결과 합치기
        translated_parts = []
        elapsed_total = 0.0
        chunk_type = "PDF 문서" if is_pdf else "웹페이지"

        for idx, chunk in enumerate(chunks, 1):
            if total_chunks > 1:
                try:
                    await msg.edit_text(
                        f"🔄 번역 중... ({idx}/{total_chunks})\n📄 `{title_text[:40]}`",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            prompt = (
                f"아래는 {chunk_type} 내용입니다 ({idx}/{total_chunks}파트). "
                f"한국어로 번역하고 마크다운 형식으로 정리해주세요.\n"
                f"제목: {title_text}\n\n"
                f"--- 내용 ---\n{chunk}\n---\n\n"
                f"번역된 내용:"
            )
            part, elapsed, _ = await query_mlx(prompt, user_id=update.effective_user.id, timeout_sec=300)
            translated_parts.append(part)
            elapsed_total += elapsed

        response = "\n\n---\n\n".join(translated_parts) if len(translated_parts) > 1 else translated_parts[0]
        elapsed = elapsed_total
        truncated = False  # 청크 처리로 전체 처리됨

        # 4. 파일 저장
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        path_slug = parsed.path.strip('/').replace('/', '-')[:50] if parsed.path.strip('/') else 'index'
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        type_tag = "pdf" if is_pdf else "web"
        filename = f"{type_tag}_{domain}_{path_slug}_{timestamp}.md"

        save_dir = "/Users/sykim/workspace/crawled"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        file_content = (
            f"# {title_text}\n\n"
            f"- **출처:** {url}\n"
            f"- **크롤링:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"- **번역:** 붐엘 (MLX)\n\n"
            f"---\n\n"
            f"{response}"
        )
        if truncated:
            file_content += "\n\n_⚠️ 원본 내용이 너무 길어 일부만 처리됨_"

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(file_content)

        # 5. 텔레그램 전송
        preview = response[:1500] if len(response) > 1500 else response
        if len(response) > 1500:
            preview += "\n\n_...(파일에서 전체 확인)_"

        summary = (
            f"✅ *크롤링 완료*\n\n"
            f"📄 *{title_text}*\n"
            f"🔗 {url}\n"
            f"⏱ {elapsed:.1f}초\n"
            f"💾 저장: `{save_path}`\n\n"
            f"---\n\n"
            f"{preview}"
        )

        # 메시지가 너무 길면 분할
        if len(summary) > 4000:
            await msg.edit_text(
                f"✅ *크롤링 완료*\n📄 *{title_text}*\n⏱ {elapsed:.1f}초\n💾 `{save_path}`",
                parse_mode='Markdown'
            )
            # 내용 분할 전송
            chunks = [response[i:i+3500] for i in range(0, min(len(response), 7000), 3500)]
            for chunk in chunks:
                try:
                    await update.message.reply_text(chunk, parse_mode='Markdown')
                except:
                    await update.message.reply_text(chunk)
        else:
            try:
                await msg.edit_text(summary, parse_mode='Markdown')
            except:
                await msg.edit_text(
                    f"✅ 크롤링 완료\n{title_text}\n{elapsed:.1f}초\n저장: {save_path}"
                )

    except ImportError as e:
        await msg.edit_text(f"❌ 라이브러리 누락: `{e}`\n`pip install beautifulsoup4 lxml html2text`", parse_mode='Markdown')
    except Exception as e:
        await msg.edit_text(f"❌ 크롤링 오류: `{str(e)[:300]}`", parse_mode='Markdown')


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
    app.add_handler(CommandHandler("clean", cmd_clean))
    app.add_handler(CommandHandler("cancel", cancel_task))
    app.add_handler(CommandHandler("crawl", cmd_crawl))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("irannews", cmd_iran_news))
    app.add_handler(CommandHandler("iran", cmd_iran_news))
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
        BotCommand("clean", "SRT 환각 제거 + 검증 [srt경로]"),
        BotCommand("news", "이란 뉴스 리포트 (XPS API)"),
        BotCommand("irannews", "이란 뉴스 리포트 (동일)"),
        BotCommand("iran", "이란 뉴스 리포트 (동일)"),
        BotCommand("crawl", "사이트 크롤링 + 번역 [URL]"),
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
        # 매일 아침 8시 (KST = UTC+9) 자동 뉴스 리포트
        from telegram.ext import JobQueue
        import datetime as dt
        application.job_queue.run_daily(
            scheduled_news_report,
            time=dt.time(hour=8, minute=0, tzinfo=dt.timezone(dt.timedelta(hours=9))),
            name="iran_daily_news"
        )

    app.post_init = post_init

    print("🤖 붐엘2 봇 시작: @boomllm2_bot")
    print(f"서버 URL: {MLX_SERVER_URL}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()