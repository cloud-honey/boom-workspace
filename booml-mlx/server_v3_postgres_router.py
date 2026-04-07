#!/usr/bin/env python3
"""붐엘(BoomL) MLX API 서버 v3 - PostgreSQL + 다중 모델 라우팅
- PostgreSQL을 기본 프로덕션 백엔드로 사용 (SQLite 폴백)
- 다중 모델 핫-스위칭 및 라우팅 지원
- 기존 기능 유지 (웹 검색, 날씨, 주식/뉴스)
- Qwen3-14B-MLX-4bit + TurboQuant + 모델 라우터
"""

import asyncio
import json
import time
import logging
import re
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import aiohttp

# ──────────────────────────────────────────────
# 로깅
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 붐엘 아키텍처 모듈 임포트
try:
    from memory_store import memory_store, ConversationTurn, SessionSummary, ProfileScope
    from policy_engine import policy_engine, FeedbackType
    from prompt_composer import prompt_composer
    from kpi_logger import kpi_logger
    from booml_core import booml_core
    from model_router import (
        model_registry, model_router, initialize_default_models,
        RoutingStrategy, ModelAdapter
    )
    from repository_factory import RepositoryFactory, get_memory_store
    
    ARCHITECTURE_ENABLED = True
    MODEL_ROUTING_ENABLED = True
    logger.info("붐엘 v3 아키텍처 모듈 로드 성공")
except ImportError as e:
    logger.warning(f"붐엘 v3 아키텍처 모듈 로드 실패: {e}. 기본 모드로 실행됩니다.")
    ARCHITECTURE_ENABLED = False
    MODEL_ROUTING_ENABLED = False

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
MAX_TOKENS_DEFAULT = 512  # 짧은 답변을 강제하기 위해 감소
PORT = int(os.environ.get("PORT", 8000))

# NAS 경로 설정 - 환경 변수 또는 기본값
NAS_BASE_PATH = os.environ.get("NAS_BASE_PATH", "/Users/sykim/nas")
NAS_TORRENT_PATH = os.path.join(NAS_BASE_PATH, "torrent")
OLD_NAS_PATH = "/Volumes/seot401/torrent"

logger.info(f"NAS 경로 설정: 기본={NAS_TORRENT_PATH}, 이전={OLD_NAS_PATH}")

KST = timezone(timedelta(hours=9))

# ──────────────────────────────────────────────
# NAS 경로 유틸리티
# ──────────────────────────────────────────────
def convert_nas_path(file_path: str) -> tuple[str, bool]:
    """
    NAS 경로 변환: 이전 경로 → 새 경로
    Returns: (변환된_경로, 변환_여부)
    """
    if file_path.startswith(OLD_NAS_PATH):
        new_path = file_path.replace(OLD_NAS_PATH, NAS_TORRENT_PATH, 1)
        logger.info(f"[NAS 경로 변환] {file_path} → {new_path}")
        return new_path, True
    return file_path, False

def resolve_nas_path(file_path: str) -> str:
    """
    NAS 경로 해결: 존재하는 경로 반환
    우선순위: 1. 변환된 경로, 2. 원본 경로, 3. 다른 가능한 경로
    """
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

# 세션 관리 (사용자 ID -> 세션 ID 매핑)
user_sessions = {}

# ──────────────────────────────────────────────
# 실시간 데이터 도구 (기존 유지)
# ──────────────────────────────────────────────
async def get_stock_data() -> str:
    """실시간 주식/지수 정보.
    시간 표현이 없으면 현재 기준으로 해석할 수 있도록 상태를 분명히 적는다.
    전일 종가를 현재가처럼 말하지 않는다.
    """
    try:
        results = []

        async with aiohttp.ClientSession() as session:
            # 1. 코스피 (네이버 금융)
            try:
                async with session.get("https://m.stock.naver.com/api/index/KOSPI/basic", timeout=4) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = float(str(data.get("closePrice", "0")).replace(",", ""))
                        diff = float(str(data.get("compareToPreviousClosePrice", "0")).replace(",", "") or 0)
                        direction = data.get("compareToPreviousPrice", {}).get("name", "")
                        if direction == "FALLING":
                            diff = -abs(diff)
                        ratio = data.get("fluctuationsRatio", "0")
                        sign = "+" if diff > 0 else ""
                        market_state = data.get("marketStatusName") or data.get("marketState") or "현재 기준"
                        time_text = data.get("localTradedAt") or data.get("tradeTime") or data.get("businessDate") or "현재 기준"
                        results.append(f"코스피: {current:,.2f} ({sign}{ratio}%) · {market_state} · {time_text}")
            except Exception as e:
                logger.warning(f"코스피 조회 실패: {e}")

            # 2. 미국 지수 + BTC (Yahoo Finance)
            symbols = {"S&P500": "^GSPC", "나스닥": "^IXIC", "비트코인": "BTC-USD"}
            for name, sym in symbols.items():
                try:
                    async with session.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=1d", timeout=4) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                            price = meta.get("regularMarketPrice")
                            prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                            market_state = meta.get("marketState", "CURRENT").lower()
                            currency = meta.get("currency", "USD")
                            if price is None:
                                continue
                            chg = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
                            sign = "+" if chg > 0 else ""
                            state_map = {
                                'regular': '장중',
                                'pre': '프리마켓',
                                'prepre': '프리마켓',
                                'post': '애프터마켓',
                                'postpost': '애프터마켓',
                                'closed': '장마감',
                                'current': '현재 기준'
                            }
                            state_text = state_map.get(market_state, market_state)
                            results.append(f"{name}: {price:,.2f} {currency} ({sign}{chg}%) · {state_text}")
                except Exception as e:
                    logger.warning(f"{name} 조회 실패: {e}")

        return "\n".join(results) if results else "현재 기준 시장 정보를 가져오지 못했습니다."
    except Exception as e:
        logger.error(f"주식 데이터 조회 실패: {e}")
        return "시장 정보 조회 중 오류가 발생했습니다."


async def get_weather_data() -> str:
    """실시간 날씨 정보 (wttr.in)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://wttr.in/Seoul?format=%C+%t+%h+%w", timeout=5) as resp:
                if resp.status == 200:
                    weather = await resp.text()
                    return f"서울 날씨: {weather.strip()}"
                else:
                    return "날씨 정보를 가져오지 못했습니다."
    except Exception as e:
        logger.error(f"날씨 데이터 조회 실패: {e}")
        return "날씨 정보 조회 중 오류가 발생했습니다."


async def get_news_summary() -> str:
    """뉴스 요약 (더미 구현)"""
    return "[뉴스]\n1. AI 기술 발전 속도 가속화\n2. 애플 실리콘 기반 ML 연구 활발\n3. 오픈소스 LLM 생태계 성장"


async def web_search(query: str) -> str:
    """DuckDuckGo 웹 검색 (duckduckgo-search 라이브러리)"""
    try:
        from duckduckgo_search import DDGS
        import asyncio

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(query, max_results=5))
        )

        if results:
            summary = []
            for i, r in enumerate(results[:5]):
                title = r.get("title", "").strip()
                body = r.get("body", "").strip()
                if body:
                    summary.append(f"{i+1}. [{title}] {body[:200]}")
            if summary:
                return "[웹 검색 결과]\n" + "\n".join(summary)

        return "웹 검색 결과를 찾을 수 없습니다."
    except Exception as e:
        logger.error(f"웹 검색 실패: {e}")
        return f"웹 검색 중 오류 발생: {str(e)}"


# ──────────────────────────────────────────────
# Tool Calling 실행 함수들
# ──────────────────────────────────────────────

async def tool_read_file(path: str) -> str:
    """로컬 파일 읽기 툴 (보안: /Users/sykim/ 하위만 허용)"""
    try:
        import os

        # 절대 경로 변환
        abs_path = os.path.abspath(path)

        # 보안 체크: /Users/sykim/ 하위만 허용
        if not abs_path.startswith("/Users/sykim/"):
            return f"Error: Access denied. Only /Users/sykim/ directory is allowed."

        # 파일 존재 확인
        if not os.path.exists(abs_path):
            return f"Error: File not found: {abs_path}"

        if not os.path.isfile(abs_path):
            return f"Error: Not a file: {abs_path}"

        # 파일 크기 체크 (최대 1MB)
        file_size = os.path.getsize(abs_path)
        if file_size > 1024 * 1024:  # 1MB
            return f"Error: File too large ({file_size} bytes). Max 1MB."

        # 파일 읽기
        with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return f"File: {abs_path}\n\n{content}"

    except Exception as e:
        logger.error(f"tool_read_file 실패: {e}")
        return f"Error reading file: {e}"


async def tool_write_file(path: str, content: str) -> str:
    """로컬 파일 쓰기 툴 (보안: /Users/sykim/ 하위만 허용)"""
    try:
        import os

        # 절대 경로 변환
        abs_path = os.path.abspath(path)

        # 보안 체크: /Users/sykim/ 하위만 허용
        if not abs_path.startswith("/Users/sykim/"):
            return f"Error: Access denied. Only /Users/sykim/ directory is allowed."

        # 디렉토리 생성 (필요시)
        dir_path = os.path.dirname(abs_path)
        os.makedirs(dir_path, exist_ok=True)

        # 파일 쓰기
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to {abs_path}"

    except Exception as e:
        logger.error(f"tool_write_file 실패: {e}")
        return f"Error writing file: {e}"


async def tool_list_dir(path: str) -> str:
    """디렉토리 목록 조회 툴 (보안: /Users/sykim/ 하위만 허용)"""
    try:
        import os

        # 절대 경로 변환
        abs_path = os.path.abspath(path)

        # 보안 체크: /Users/sykim/ 하위만 허용
        if not abs_path.startswith("/Users/sykim/"):
            return f"Error: Access denied. Only /Users/sykim/ directory is allowed."

        # 디렉토리 존재 확인
        if not os.path.exists(abs_path):
            return f"Error: Directory not found: {abs_path}"

        if not os.path.isdir(abs_path):
            return f"Error: Not a directory: {abs_path}"

        # 디렉토리 목록 조회
        entries = os.listdir(abs_path)

        # 파일/디렉토리 구분하여 정렬
        files = []
        dirs = []
        for entry in entries:
            full_path = os.path.join(abs_path, entry)
            if os.path.isdir(full_path):
                dirs.append(f"[DIR]  {entry}")
            else:
                size = os.path.getsize(full_path)
                files.append(f"[FILE] {entry} ({size} bytes)")

        result = f"Directory: {abs_path}\n\n"
        result += "\n".join(sorted(dirs) + sorted(files))

        return result

    except Exception as e:
        logger.error(f"tool_list_dir 실패: {e}")
        return f"Error listing directory: {e}"


async def tool_get_weather(city: str) -> str:
    """날씨 조회 툴 (open-meteo.com 무료 API 사용)"""
    try:
        # 1. 도시명 → 좌표 변환
        geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ko"

        async with aiohttp.ClientSession() as session:
            async with session.get(geocoding_url, timeout=10) as resp:
                if resp.status != 200:
                    return f"Error: Failed to geocode city '{city}'"

                geo_data = await resp.json()

                if not geo_data.get("results"):
                    return f"Error: City '{city}' not found"

                location = geo_data["results"][0]
                lat = location["latitude"]
                lon = location["longitude"]
                location_name = location.get("name", city)
                country = location.get("country", "")

            # 2. 날씨 조회
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&hourly=temperature_2m,precipitation_probability"
                f"&timezone=auto"
            )

            async with session.get(weather_url, timeout=10) as resp:
                if resp.status != 200:
                    return f"Error: Failed to fetch weather data"

                weather_data = await resp.json()
                current = weather_data.get("current", {})

                # 날씨 코드 → 한국어 설명
                weather_code = current.get("weather_code", 0)
                weather_desc = {
                    0: "맑음", 1: "대체로 맑음", 2: "부분 흐림", 3: "흐림",
                    45: "안개", 48: "서리 안개",
                    51: "이슬비", 53: "이슬비", 55: "이슬비",
                    61: "비", 63: "비", 65: "강한 비",
                    71: "눈", 73: "눈", 75: "강설",
                    80: "소나기", 81: "소나기", 82: "강한 소나기",
                    95: "뇌우", 96: "뇌우", 99: "뇌우"
                }.get(weather_code, "알 수 없음")

                result = f"[{location_name}, {country} 날씨]\n"
                result += f"온도: {current.get('temperature_2m', 'N/A')}°C\n"
                result += f"습도: {current.get('relative_humidity_2m', 'N/A')}%\n"
                result += f"날씨: {weather_desc}\n"
                result += f"풍속: {current.get('wind_speed_10m', 'N/A')} km/h"

                return result

    except asyncio.TimeoutError:
        return "Error: Weather API timeout"
    except Exception as e:
        logger.error(f"tool_get_weather 실패: {e}")
        return f"Error fetching weather: {e}"


async def get_realtime_data(user_message: str = None) -> str:
    """실시간 데이터 수집 (주식, 날씨, 뉴스) + 웹 검색"""
    try:
        # 기본 실시간 데이터
        stock_task = asyncio.create_task(get_stock_data())
        weather_task = asyncio.create_task(get_weather_data())
        news_task = asyncio.create_task(get_news_summary())

        stock, weather, news = await asyncio.gather(
            stock_task, weather_task, news_task, return_exceptions=True
        )

        parts = []
        if not isinstance(stock, Exception):
            parts.append(stock)
        if not isinstance(weather, Exception):
            parts.append(weather)
        if not isinstance(news, Exception):
            parts.append(news)

        # 사용자 메시지가 있고 검색이 필요한 경우 웹 검색 추가
        search_results = ""
        if user_message:
            # 검색 키워드 감지
            search_keywords = [
                "검색", "찾아", "알려", "뭐야", "무엇", "어떻게", "방법",
                "최신", "새소식", "뉴스", "정보", "조회", "확인"
            ]
            
            # 질문 형태 감지 (5W1H)
            question_words = ["누구", "어디", "언제", "왜", "어떻게", "무엇"]
            
            # 내부 시스템 프롬프트 (번역, 코드 등 영어 지시문) 검색 제외
            is_system_prompt = (
                user_message.startswith("You are") or
                user_message.startswith("Translate") or
                user_message.startswith("As a") or
                len(user_message) > 500  # 긴 배치 프롬프트는 검색 불필요
            )

            needs_search = not is_system_prompt and (
                any(keyword in user_message for keyword in search_keywords) or
                any(user_message.endswith(word + "?") or user_message.endswith(word + "?")
                    for word in question_words) or
                "?" in user_message  # 질문 형태
            )
            
            if needs_search:
                logger.info(f"웹 검색 실행: {user_message[:50]}...")
                search_task = asyncio.create_task(web_search(user_message))
                search_results = await search_task
                if search_results and "웹 검색 결과" in search_results:
                    parts.append(search_results)

        return "\n\n".join(parts) if parts else "실시간 데이터를 가져오지 못했습니다."
    except Exception as e:
        logger.error(f"실시간 데이터 수집 실패: {e}")
        return "실시간 데이터 수집 중 오류가 발생했습니다."


# ──────────────────────────────────────────────
# Pydantic 모델
# ──────────────────────────────────────────────
class Message(BaseModel):
    role: str = Field(..., description="역할 (system/user/assistant)")
    content: str = Field(..., description="메시지 내용")


class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str = Field("booml-mlx", description="모델")
    max_tokens: int = Field(MAX_TOKENS_DEFAULT, description="최대 토큰 수")
    temperature: float = Field(0.7, description="온도")
    stream: bool = Field(False, description="스트리밍 여부")
    routing_strategy: Optional[str] = Field(None, description="라우팅 전략 (default/fast/quality)")
    tools: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calling 지원")


class FeedbackRequest(BaseModel):
    user_id: str = Field(..., description="사용자 ID")
    feedback_type: str = Field(..., description="피드백 타입 (positive/negative/implicit)")
    content: str = Field(..., description="피드백 내용")
    context: Optional[str] = Field(None, description="피드백 컨텍스트")
    session_id: Optional[str] = Field(None, description="세션 ID (옵셔널)")
    project_id: Optional[str] = Field(None, description="프로젝트 ID (옵셔널)")


class UserStatsRequest(BaseModel):
    user_id: str = Field(..., description="사용자 ID")
    days: int = Field(7, description="조회 기간 (일)")


class ModelSwitchRequest(BaseModel):
    model_name: str = Field(..., description="모델 이름")
    routing_strategy: Optional[str] = Field(None, description="라우팅 전략")


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "booml-mlx"
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    metadata: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    server_version: str = "v3-postgres-router"
    architecture_enabled: bool
    model_routing_enabled: bool
    active_model: Optional[str] = None
    routing_strategy: Optional[str] = None
    available_models: List[Dict[str, Any]] = []
    database_backend: str = "unknown"
    uptime_seconds: float = 0
    # 봇 호환 필드
    model_loaded: bool = False
    turboquant: bool = True          # TurboQuant 3.5bit 항상 활성 상태
    performance: Dict[str, Any] = {}


class UserStatsResponse(BaseModel):
    user_id: str
    period_days: int
    conversation_turns: int
    positive_examples_count: int
    negative_tags_count: int
    profile_summary: Dict[str, Any]
    kpi_stats: Dict[str, Any]


class ModelSwitchResponse(BaseModel):
    success: bool
    message: str
    active_model: Optional[str] = None
    routing_strategy: Optional[str] = None


# ──────────────────────────────────────────────
# 세션 관리 헬퍼
# ──────────────────────────────────────────────
def get_or_create_session(user_id: str, project_id: Optional[str] = None) -> str:
    """사용자 세션 조회 또는 생성"""
    if user_id in user_sessions:
        return user_sessions[user_id]
    
    if ARCHITECTURE_ENABLED:
        session_id = booml_core.start_session(user_id, project_id)
    else:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    user_sessions[user_id] = session_id
    return session_id


# ──────────────────────────────────────────────
# FastAPI
# ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("붐엘 v3 PostgreSQL + 다중 모델 라우팅 서버 시작...")
    start_time = time.time()
    
    # 데이터베이스 백엔드 정보 로깅
    try:
        from memory_store import memory_store
        db_backend = type(memory_store).__name__
        logger.info(f"데이터베이스 백엔드: {db_backend}")
        
        if "PostgreSQL" in db_backend:
            logger.info("✅ PostgreSQL 백엔드 활성화 (프로덕션 모드)")
        else:
            logger.info("ℹ️ SQLite 백엔드 활성화 (개발/테스트 모드)")
    except:
        logger.warning("데이터베이스 백엔드 정보를 확인할 수 없습니다.")
    
    # 모델 라우팅 초기화
    if MODEL_ROUTING_ENABLED:
        logger.info("모델 라우팅 초기화 중...")
        models = initialize_default_models()
        logger.info(f"모델 라우팅 초기화 완료: {len(models)}개 모델 등록")
        
        # 등록된 모델 정보 로깅
        for model in model_registry.list_models():
            status = "✅ 활성" if model["is_active"] else "⚠️ 대기"
            logger.info(f"  {status} {model['name']} ({model['display_name']})")
    else:
        logger.warning("모델 라우팅 비활성화됨")
    
    # 아키텍처 모듈 초기화
    if ARCHITECTURE_ENABLED:
        logger.info("붐엘 아키텍처 초기화 완료")
    
    app.state.start_time = start_time
    yield
    
    logger.info("붐엘 v3 서버 종료...")


app = FastAPI(
    title="붐엘(BoomL) MLX API v3 - PostgreSQL + 다중 모델 라우팅",
    description="PostgreSQL을 기본 백엔드로 사용하는 다중 모델 핫-스위칭 지원 서버",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "붐엘(BoomL) MLX API v3 - PostgreSQL + 다중 모델 라우팅",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health() -> HealthResponse:
    """서버 상태 확인"""
    uptime = time.time() - app.state.start_time
    
    # 데이터베이스 백엔드 확인
    db_backend = "unknown"
    try:
        from memory_store import memory_store
        db_backend = type(memory_store).__name__.replace("MemoryRepository", "").replace("SQLite", "SQLite").replace("PostgreSQL", "PostgreSQL")
    except:
        pass
    
    # 모델 정보
    active_model = None
    routing_strategy = None
    available_models = []
    
    if MODEL_ROUTING_ENABLED:
        active_model = model_registry.get_active_model()
        routing_strategy = model_router.get_routing_strategy().value
        available_models = model_registry.list_models()
    
    # 모델 로드 여부 및 성능 정보
    model_loaded = False
    performance = {}
    if MODEL_ROUTING_ENABLED and active_model:
        adapter = model_registry.get_adapter(active_model)
        if adapter:
            meta = adapter.get_metadata()
            model_loaded = meta.is_loaded
            performance = {
                "model_id": meta.display_name,
                "load_time": meta.load_time_ms / 1000,
                "avg_response_ms": meta.avg_response_time_ms,
                "token_per_second": meta.token_per_second,
                "kv_cache_bits": 3.5,
                "kv_quant_scheme": "turboquant",
            }

    return HealthResponse(
        status="healthy",
        architecture_enabled=ARCHITECTURE_ENABLED,
        model_routing_enabled=MODEL_ROUTING_ENABLED,
        active_model=active_model,
        routing_strategy=routing_strategy,
        available_models=available_models,
        database_backend=db_backend,
        uptime_seconds=uptime,
        model_loaded=model_loaded,
        turboquant=True,
        performance=performance,
    )


@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """채팅 완성 (모델 라우팅 지원 + Tool Calling)"""
    try:
        # ──────────────────────────────────────────────
        # Tool Calling 처리
        # ──────────────────────────────────────────────
        if request.tools:
            logger.info(f"Tool calling 모드 활성화: {len(request.tools)}개 툴 제공됨")

            # 툴 실행 함수 매핑
            tool_functions = {
                "web_search": lambda args: web_search(args.get("query", "")),
                "read_file": lambda args: tool_read_file(args.get("path", "")),
                "write_file": lambda args: tool_write_file(args.get("path", ""), args.get("content", "")),
                "list_dir": lambda args: tool_list_dir(args.get("path", "")),
                "get_weather": lambda args: tool_get_weather(args.get("city", "")),
            }

            # 최대 5회 tool call 루프 (무한 루프 방지)
            max_iterations = 5
            current_messages = [{"role": m.role, "content": m.content} for m in request.messages]

            # 시스템 프롬프트가 없으면 툴 사용 유도 주입
            has_system = any(m.get("role") == "system" for m in current_messages)
            if not has_system:
                tool_names = [t.get("function", {}).get("name", "") for t in request.tools]
                system_content = (
                    f"You have access to the following tools: {', '.join(tool_names)}. "
                    "When the user asks for real-time information (weather, news, stock prices, files, etc.) "
                    "that you cannot reliably answer from training data, you MUST call the appropriate tool. "
                    "Do not fabricate or guess real-time data — use the tools instead. "
                    "Respond in the same language as the user."
                )
                current_messages = [{"role": "system", "content": system_content}] + current_messages

            for iteration in range(max_iterations):
                # 모델 호출
                if MODEL_ROUTING_ENABLED:
                    response_text, model_used, token_stats = model_router.generate_with_strategy(
                        current_messages,
                        strategy=None,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                        tools=request.tools,
                    )
                else:
                    # 기본 MLX 어댑터 사용
                    from model_router import model_registry
                    adapter = model_registry.get_adapter("gemma-4-26b-mlx")
                    if not adapter:
                        raise HTTPException(status_code=500, detail="모델 어댑터 없음")
                    response_text, token_stats = adapter.generate(
                        current_messages, request.max_tokens, request.temperature
                    )
                    model_used = "gemma-4-26b-mlx"

                # tool_call 파싱 (Gemma 4 포맷: <|tool_call>call:함수명{인자}<tool_call|>)
                import re
                tool_call_pattern = r'<\|tool_call>(.*?)<tool_call\|>'
                tool_calls = re.findall(tool_call_pattern, response_text, re.DOTALL)

                if not tool_calls:
                    # 툴 호출 없음 → 최종 응답 반환
                    logger.info(f"Tool calling 완료 (반복 {iteration+1}회)")
                    response_message = Message(role="assistant", content=response_text)

                    usage = {
                        "prompt_tokens": token_stats.get("prompt_tokens", 0),
                        "completion_tokens": token_stats.get("completion_tokens", 0),
                        "total_tokens": token_stats.get("total_tokens", 0),
                    }

                    return ChatCompletionResponse(
                        choices=[ChatCompletionChoice(message=response_message)],
                        usage=usage,
                        metadata={
                            "tool_calling_enabled": True,
                            "tool_call_iterations": iteration + 1,
                            "model_used": model_used,
                            "generation_tps": token_stats.get("generation_tps", 0.0),
                        }
                    )

                # 툴 호출 파싱 및 실행
                tool_results = []
                for tool_call_str in tool_calls:
                    # Gemma 4 포맷 파싱: call:함수명{인자1:<|"|>값<|"|>,인자2:<|"|>값<|"|>}
                    # 예: call:web_search{query:<|"|>날씨<|"|>}
                    func_match = re.match(r'call:(\w+)\{(.*?)\}', tool_call_str, re.DOTALL)
                    if not func_match:
                        logger.warning(f"툴 호출 파싱 실패: {tool_call_str}")
                        continue

                    func_name = func_match.group(1)
                    args_str = func_match.group(2)

                    # 인자 파싱
                    args = {}
                    arg_pattern = r'(\w+):<\|"\|>(.*?)<\|"\|>'
                    for arg_match in re.finditer(arg_pattern, args_str):
                        key = arg_match.group(1)
                        value = arg_match.group(2)
                        args[key] = value

                    logger.info(f"툴 실행: {func_name}({args})")

                    # 툴 실행
                    if func_name in tool_functions:
                        try:
                            result = await tool_functions[func_name](args)
                            tool_results.append(f"<|tool_response|>{func_name}: {result}<|tool_response|>")
                        except Exception as e:
                            logger.error(f"툴 실행 실패 ({func_name}): {e}")
                            tool_results.append(f"<|tool_response|>{func_name}: Error - {e}<|tool_response|>")
                    else:
                        logger.warning(f"알 수 없는 툴: {func_name}")
                        tool_results.append(f"<|tool_response|>{func_name}: Unknown tool<|tool_response|>")

                # tool_response를 메시지에 추가
                current_messages.append({"role": "assistant", "content": response_text})
                current_messages.append({"role": "tool", "content": "\n".join(tool_results)})

                logger.info(f"Tool call 반복 {iteration+1}: {len(tool_calls)}개 툴 실행됨")

            # 최대 반복 도달
            logger.warning(f"Tool calling 최대 반복 도달 ({max_iterations}회)")
            response_message = Message(role="assistant", content="Tool calling 최대 반복 초과")
            return ChatCompletionResponse(
                choices=[ChatCompletionChoice(message=response_message)],
                metadata={"tool_calling_error": "max_iterations_reached"}
            )

        # ──────────────────────────────────────────────
        # 일반 채팅 완성 (Tool Calling 비활성화)
        # ──────────────────────────────────────────────
        # 실시간 데이터 수집 (첫 번째 사용자 메시지인 경우)
        realtime_data = ""
        user_messages = [m for m in request.messages if m.role == "user"]
        if user_messages:
            # 마지막 사용자 메시지 가져오기
            last_user_message = user_messages[-1].content
            # 웹 검색 포함 실시간 데이터 수집
            realtime_data = await get_realtime_data(last_user_message)
        
        # 세션 관리 (간단한 구현)
        user_id = "default_user"  # 실제 구현에서는 인증에서 가져옴
        session_id = get_or_create_session(user_id)
        
        # 라우팅 전략 결정
        routing_strategy = None
        if request.routing_strategy:
            try:
                routing_strategy = RoutingStrategy(request.routing_strategy)
            except ValueError:
                logger.warning(f"알 수 없는 라우팅 전략: {request.routing_strategy}")
        
        # 아키텍처 통합 모드 (routing_strategy="direct"이면 메모리 없이 모델 직접 호출)
        if ARCHITECTURE_ENABLED and request.routing_strategy != "direct":
            # 붐엘 코어를 통한 메시지 처리
            last_user_message = user_messages[-1].content if user_messages else ""
            response_text, metadata = booml_core.process_message(
                session_id, last_user_message, realtime_data,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            # 토큰 통계 추출
            token_stats = metadata.pop("token_stats", {})
            usage = {
                "prompt_tokens": token_stats.get("prompt_tokens", 0),
                "completion_tokens": token_stats.get("completion_tokens", 0),
                "total_tokens": token_stats.get("total_tokens", 0),
            }
            
            # 응답 메시지 구성
            response_message = Message(role="assistant", content=response_text)
            
            return ChatCompletionResponse(
                choices=[ChatCompletionChoice(message=response_message)],
                usage=usage,
                metadata={
                    "session_id": session_id,
                    "architecture_enabled": True,
                    "model_used": metadata.get("model_used", "booml-core"),
                    "generation_tps": token_stats.get("generation_tps", 0.0),
                    "prompt_tps": token_stats.get("prompt_tps", 0.0),
                    "peak_memory_gb": token_stats.get("peak_memory_gb", 0.0),
                    **metadata
                }
            )
        
        # 모델 라우팅 모드
        elif MODEL_ROUTING_ENABLED:
            # 메시지 포맷 변환
            messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]
            
            # 실시간 데이터를 시스템 메시지로 추가
            if realtime_data:
                messages_dict.insert(0, {
                    "role": "system",
                    "content": f"실시간 데이터:\n{realtime_data}\n\n이 데이터를 참고하여 답변해주세요."
                })
            
            # 모델 라우팅을 통한 응답 생성
            response_text, model_used, token_stats = model_router.generate_with_strategy(
                messages_dict,
                strategy=routing_strategy,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            if not response_text:
                raise HTTPException(status_code=500, detail="모델 응답 생성 실패")
            
            usage = {
                "prompt_tokens": token_stats.get("prompt_tokens", 0),
                "completion_tokens": token_stats.get("completion_tokens", 0),
                "total_tokens": token_stats.get("total_tokens", 0),
            }
            
            # 응답 메시지 구성
            response_message = Message(role="assistant", content=response_text)
            
            return ChatCompletionResponse(
                choices=[ChatCompletionChoice(message=response_message)],
                usage=usage,
                metadata={
                    "session_id": session_id,
                    "architecture_enabled": False,
                    "model_routing_enabled": True,
                    "model_used": model_used,
                    "routing_strategy": routing_strategy.value if routing_strategy else "default",
                    "generation_tps": token_stats.get("generation_tps", 0.0),
                    "prompt_tps": token_stats.get("prompt_tps", 0.0),
                    "peak_memory_gb": token_stats.get("peak_memory_gb", 0.0),
                }
            )
        
        # 기본 모드 (기존 MLX 모델)
        else:
            # 기존 MLX 모델 사용 (하위 호환성)
            from server_v2_enhanced import mlx_model
            
            # 실시간 데이터를 시스템 메시지로 추가
            messages = list(request.messages)
            if realtime_data:
                messages.insert(0, Message(
                    role="system",
                    content=f"실시간 데이터:\n{realtime_data}\n\n이 데이터를 참고하여 답변해주세요."
                ))
            
            # MLX 모델 응답 생성
            response_text = await asyncio.to_thread(
                mlx_model.generate, messages, request.max_tokens, request.temperature
            )
            
            response_message = Message(role="assistant", content=response_text)
            
            return ChatCompletionResponse(
                choices=[ChatCompletionChoice(message=response_message)],
                metadata={
                    "session_id": session_id,
                    "architecture_enabled": False,
                    "model_routing_enabled": False,
                    "model_used": "mlx-v2"
                }
            )
    
    except Exception as e:
        logger.error(f"채팅 완성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    """피드백 제출"""
    if not ARCHITECTURE_ENABLED:
        raise HTTPException(status_code=501, detail="아키텍처 모드가 비활성화되어 있습니다.")
    
    try:
        # session_id가 없으면 user_id로 세션 생성 또는 찾기
        session_id = request.session_id
        if not session_id:
            # user_id로 활성 세션 찾기
            for sid, data in user_sessions.items():
                if data.get("user_id") == request.user_id:
                    session_id = sid
                    break
            
            # 활성 세션이 없으면 새로 생성
            if not session_id:
                session_id = f"feedback_session_{uuid.uuid4().hex[:8]}"
                user_sessions[session_id] = {
                    "user_id": request.user_id,
                    "project_id": request.project_id,
                    "created_at": datetime.now(KST)
                }
        
        booml_core.process_feedback(
            session_id,
            request.feedback_type,
            request.content,
            request.context
        )
        
        return {"success": True, "message": "피드백이 처리되었습니다."}
    except Exception as e:
        logger.error(f"피드백 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/user/stats")
async def get_user_stats(request: UserStatsRequest) -> UserStatsResponse:
    """사용자 통계 조회"""
    if not ARCHITECTURE_ENABLED:
        raise HTTPException(status_code=501, detail="아키텍처 모드가 비활성화되어 있습니다.")
    
    try:
        stats = booml_core.get_user_stats(request.user_id, request.days)
        return UserStatsResponse(**stats)
    except Exception as e:
        logger.error(f"사용자 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/models/switch")
async def switch_model(request: ModelSwitchRequest) -> ModelSwitchResponse:
    """모델 전환 (핫-스위칭)"""
    if not MODEL_ROUTING_ENABLED:
        raise HTTPException(status_code=501, detail="모델 라우팅이 비활성화되어 있습니다.")
    
    try:
        # 모델 전환
        success = model_registry.set_active_model(request.model_name)
        
        if not success:
            return ModelSwitchResponse(
                success=False,
                message=f"모델 전환 실패: '{request.model_name}' 모델을 찾을 수 없습니다."
            )
        
        # 라우팅 전략 업데이트 (제공된 경우)
        if request.routing_strategy:
            try:
                strategy = RoutingStrategy(request.routing_strategy)
                model_router.set_routing_strategy(strategy)
                routing_msg = f", 라우팅 전략={strategy.value}"
            except ValueError:
                routing_msg = f", 라우팅 전략 업데이트 실패: '{request.routing_strategy}'"
        else:
            routing_msg = ""
        
        return ModelSwitchResponse(
            success=True,
            message=f"모델 전환 성공: {request.model_name}{routing_msg}",
            active_model=request.model_name,
            routing_strategy=request.routing_strategy
        )
    except Exception as e:
        logger.error(f"모델 전환 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """등록된 모델 목록 조회"""
    if not MODEL_ROUTING_ENABLED:
        raise HTTPException(status_code=501, detail="모델 라우팅이 비활성화되어 있습니다.")
    
    try:
        models = model_registry.list_models()
        return {
            "success": True,
            "models": models,
            "active_model": model_registry.get_active_model(),
            "routing_strategy": model_router.get_routing_strategy().value
        }
    except Exception as e:
        logger.error(f"모델 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def clean_srt(srt_path: str) -> dict:
    """SRT 파일 환각 제거 + 검증
    - 연속 동일 블록 최대 2회로 제한
    - 블록 내 반복 문장 정리
    - 검증 리포트 반환
    """
    import os, re

    with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    pattern = re.compile(
        r'(\d+)\r?\n(\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3})\r?\n([\s\S]*?)(?=\r?\n\d+\r?\n|\Z)',
        re.MULTILINE
    )
    blocks = pattern.findall(content)
    if not blocks:
        return {"cleaned": False, "reason": "파싱 실패", "blocks_original": 0, "blocks_removed": 0}

    cleaned_blocks = []
    removed_count = 0
    prev_texts = []  # 최근 2개 텍스트 기록

    for num, timecode, text in blocks:
        text_stripped = text.strip().replace('\n', ' ')

        # 1. 블록 내 반복 줄 정리 (같은 문장 3번 이상 반복 → 2번으로)
        lines = text.strip().split('\n')
        if len(lines) > 2:
            new_lines = [lines[0]]
            for line in lines[1:]:
                if new_lines.count(line) < 2:
                    new_lines.append(line)
            text = '\n'.join(new_lines)
            text_stripped = text.replace('\n', ' ')

        # 2. 연속 동일 블록 최대 2회
        if prev_texts.count(text_stripped) >= 2:
            removed_count += 1
            continue

        prev_texts.append(text_stripped)
        if len(prev_texts) > 5:
            prev_texts.pop(0)

        cleaned_blocks.append((num, timecode, text))

    # 번호 재정렬 + 재조립
    output_lines = []
    for i, (_, timecode, text) in enumerate(cleaned_blocks, 1):
        output_lines.append(f"{i}\n{timecode}\n{text.strip()}\n")
    output_content = "\n".join(output_lines)

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(output_content)

    # 검증 리포트
    warnings = []
    if removed_count > 0:
        warnings.append(f"반복 블록 {removed_count}개 제거")
    if len(cleaned_blocks) == 0:
        warnings.append("⚠️ 블록 0개 — 추출 실패 의심")
    elif len(cleaned_blocks) < 10:
        warnings.append(f"⚠️ 블록 수 매우 적음 ({len(cleaned_blocks)}개) — 내용 확인 필요")

    return {
        "cleaned": True,
        "blocks_original": len(blocks),
        "blocks_after": len(cleaned_blocks),
        "blocks_removed": removed_count,
        "warnings": warnings,
        "srt_path": srt_path
    }


@app.post("/v1/clean_srt")
async def clean_srt_endpoint(request: dict):
    """SRT 클리닝 + 검증 엔드포인트"""
    import os
    srt_path = request.get("srt_path", "")
    if not srt_path:
        raise HTTPException(status_code=400, detail="srt_path is required")
    
    # NAS 경로 해결
    srt_path = resolve_nas_path(srt_path)
    
    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail=f"File not found: {srt_path}")
    
    result = clean_srt(srt_path)
    return {"status": "done", **result}


@app.post("/v1/transcribe")
async def transcribe_video(request: dict):
    """영상/음성 파일 자막 추출 (mlx-whisper)
    
    Request body:
        file_path: str — 절대 경로
        model: str — tiny/base/small/medium/large-v3 (기본: tiny)
        language: str — 언어 코드 (기본: auto)
        output_format: str — srt/txt/json (기본: srt)
    """
    import subprocess
    import os

    file_path = request.get("file_path", "")
    model = request.get("model", "tiny")
    language = request.get("language", None)
    output_format = request.get("output_format", "srt")

    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required")
    
    # NAS 경로 해결
    file_path = resolve_nas_path(file_path)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    output_dir = os.path.dirname(file_path)
    file_basename = os.path.basename(file_path)

    # mlx_whisper는 파일명에서 확장자를 직접 파싱함
    # 예: "foo.com.mp4" → "foo.com.srt" (splitext 기준)
    # 예: "bar.Uncen.mov" → "bar.Uncen.srt"
    # 따라서 서버도 동일하게 splitext 1회만 적용해야 함
    base_name = os.path.splitext(file_basename)[0]
    output_srt = os.path.join(output_dir, f"{base_name}.srt")

    def find_actual_srt(directory: str, before_mtime: float) -> str | None:
        """추출 후 새로 생긴 SRT 파일을 찾음 (파일명 예측 실패 시 폴백)"""
        try:
            for f in os.listdir(directory):
                if f.endswith('.srt'):
                    fpath = os.path.join(directory, f)
                    if os.path.getmtime(fpath) >= before_mtime - 1:
                        return fpath
        except Exception:
            pass
        return None

    # 이미 srt 있으면 스킵 (예측 경로 + 실제 폴더 내 srt 존재 여부 모두 확인)
    existing_srts = [
        f for f in os.listdir(output_dir)
        if f.endswith('.srt') and os.path.splitext(f)[0] == base_name
    ] if os.path.isdir(output_dir) else []
    if os.path.exists(output_srt) or existing_srts:
        actual = output_srt if os.path.exists(output_srt) else os.path.join(output_dir, existing_srts[0])
        return {
            "status": "skipped",
            "message": "SRT already exists",
            "srt_path": actual
        }

    whisper_bin = os.path.join(os.path.dirname(__file__), "venv/bin/mlx_whisper")
    cmd = [
        whisper_bin,
        file_path,
        "--model", f"mlx-community/whisper-{model}-mlx",
        "--output-format", output_format,
        "--output-dir", output_dir,
        "--condition-on-previous-text", "False",
        "--compression-ratio-threshold", "1.8",
        "--logprob-threshold", "-0.8",
        "--no-speech-threshold", "0.6",
        "--word-timestamps", "True",
        "--hallucination-silence-threshold", "2",
    ]
    if language:
        cmd += ["--language", language]

    logger.info(f"[transcribe] 시작: {file_path} (model={model})")
    start_time = time.time()
    before_mtime = start_time

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        elapsed = round(time.time() - start_time, 1)

        if proc.returncode != 0:
            logger.error(f"[transcribe] 실패: {stderr.decode()}")
            raise HTTPException(status_code=500, detail=f"Whisper error: {stderr.decode()[-500:]}")

        # 실제 생성된 SRT 확인 (예측 경로 우선, 없으면 폴더 스캔)
        actual_srt = output_srt if os.path.exists(output_srt) else find_actual_srt(output_dir, before_mtime)
        if not actual_srt:
            raise FileNotFoundError(f"SRT 파일을 찾을 수 없음 (예상: {output_srt})")

        logger.info(f"[transcribe] 완료: {actual_srt} ({elapsed}s)")

        # 자동 클리닝 + 검증
        clean_result = clean_srt(actual_srt)
        if clean_result.get("blocks_removed", 0) > 0:
            logger.info(f"[transcribe] 클리닝: {clean_result['blocks_removed']}개 반복 블록 제거")
        if clean_result.get("warnings"):
            for w in clean_result["warnings"]:
                logger.warning(f"[transcribe] 검증 경고: {w}")

        return {
            "status": "done",
            "file": file_path,
            "srt_path": actual_srt,
            "model": model,
            "elapsed_sec": elapsed,
            "clean": clean_result
        }
    except Exception as e:
        logger.error(f"[transcribe] 예외: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/translate_srt")
async def translate_srt(request: dict):
    """SRT 자막 한국어 번역 (붐엘 Gemma 4 26B)
    
    Request body:
        srt_path: str — 번역할 srt 파일 경로
        output_path: str — 저장 경로 (기본: 원본_KO.srt)
        batch_size: int — 한 번에 번역할 자막 수 (기본: 10)
    """
    import os, re

    srt_path = request.get("srt_path", "")
    batch_size = request.get("batch_size", 10)

    if not srt_path:
        raise HTTPException(status_code=400, detail="srt_path is required")
    
    # NAS 경로 해결
    srt_path = resolve_nas_path(srt_path)
    
    if not os.path.exists(srt_path):
        raise HTTPException(status_code=404, detail=f"File not found: {srt_path}")

    base = os.path.splitext(srt_path)[0]
    output_path = request.get("output_path", f"{base}_KO.srt")

    # SRT 파싱
    with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # 자막 블록 파싱 (번호, 타임코드, 텍스트)
    pattern = re.compile(
        r'(\d+)\r?\n(\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,\.]\d{3})\r?\n([\s\S]*?)(?=\r?\n\d+\r?\n|\Z)',
        re.MULTILINE
    )
    blocks = pattern.findall(content)

    if not blocks:
        raise HTTPException(status_code=400, detail="SRT 파싱 실패 — 형식 확인 필요")

    logger.info(f"[translate_srt] {len(blocks)}개 자막 블록 번역 시작: {srt_path}")
    start_time = time.time()

    translated_blocks = []

    # 배치 단위 번역
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i+batch_size]
        texts = [b[2].strip().replace('\n', ' ') for b in batch]

        # 빈 텍스트 스킵
        non_empty = [(j, t) for j, t in enumerate(texts) if t]
        if not non_empty:
            for b in batch:
                translated_blocks.append((b[0], b[1], b[2]))
            continue

        numbered = "\n".join(f"[{j+1}] {t}" for j, t in non_empty)
        prompt = (
            "You are a professional Japanese-to-Korean subtitle translator.\n"
            "Translate each numbered subtitle naturally, preserving the nuance and context.\n"
            "Do NOT translate literally — use natural Korean expressions.\n"
            "Keep the same numbering format [N] in your response.\n"
            "Output ONLY the translated lines, nothing else.\n\n"
            f"{numbered}"
        )

        try:
            # 자기 자신의 chat/completions 엔드포인트로 번역 요청
            import aiohttp as _aiohttp
            async with _aiohttp.ClientSession() as _sess:
                async with _sess.post(
                    f"http://localhost:{PORT}/v1/chat/completions",
                    json={
                        "model": "booml-mlx",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2048,
                        "temperature": 0.3,
                        "stream": False
                    },
                    timeout=_aiohttp.ClientTimeout(total=180)
                ) as _resp:
                    _data = await _resp.json()
                    translated_text = _data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # 번역 결과 파싱
            trans_map = {}
            for line in translated_text.strip().split('\n'):
                m = re.match(r'\[(\d+)\]\s*(.*)', line.strip())
                if m:
                    trans_map[int(m.group(1))] = m.group(2).strip()

            for k, (j, orig) in enumerate(non_empty):
                texts[j] = trans_map.get(k+1, orig)

        except Exception as e:
            logger.warning(f"[translate_srt] 배치 {i//batch_size+1} 번역 실패: {e}")

        for idx, b in enumerate(batch):
            translated_blocks.append((b[0], b[1], texts[idx]))

    # SRT 재조립
    output_lines = []
    for num, timecode, text in translated_blocks:
        output_lines.append(f"{num}\n{timecode}\n{text}\n")
    output_content = "\n".join(output_lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_content)

    elapsed = round(time.time() - start_time, 1)
    logger.info(f"[translate_srt] 완료: {output_path} ({elapsed}s)")

    return {
        "status": "done",
        "source": srt_path,
        "output": output_path,
        "blocks": len(translated_blocks),
        "elapsed_sec": elapsed
    }


@app.get("/v1/architecture/status")
async def architecture_status():
    """아키텍처 상태 확인"""
    return {
        "architecture_enabled": ARCHITECTURE_ENABLED,
        "model_routing_enabled": MODEL_ROUTING_ENABLED,
        "database_backend": type(memory_store).__name__ if ARCHITECTURE_ENABLED else "unknown",
        "available_models": model_registry.list_models() if MODEL_ROUTING_ENABLED else []
    }


# ──────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"붐엘 v3 서버 시작 (포트: {PORT})")
    logger.info("데이터베이스 백엔드: PostgreSQL-first (SQLite 폴백)")
    logger.info("모델 라우팅: 활성화 (다중 모델 핫-스위칭 지원)")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )