#!/usr/bin/env python3
"""붐엘(BoomL) MLX API 서버 v2 - 아키텍처 통합 버전
- Phase 1-2 아키텍처 통합 (메모리 저장소, 정책 엔진, 프롬프트 조립기, KPI 로거)
- 기존 기능 유지 (웹 검색, 날씨, 주식/뉴스)
- Qwen3-14B-MLX-4bit + TurboQuant
"""

import asyncio
import json
import time
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import aiohttp

# 붐엘 아키텍처 모듈 임포트
try:
    from memory_store import memory_store, ConversationTurn, SessionSummary, ProfileScope
    from policy_engine import policy_engine, FeedbackType
    from prompt_composer import prompt_composer
    from kpi_logger import kpi_logger
    from booml_core import booml_core
    ARCHITECTURE_ENABLED = True
    logger.info("붐엘 아키텍처 모듈 로드 성공")
except ImportError as e:
    logger.warning(f"붐엘 아키텍처 모듈 로드 실패: {e}. 기본 모드로 실행됩니다.")
    ARCHITECTURE_ENABLED = False

# ──────────────────────────────────────────────
# 로깅
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
MODEL_ID = "Qwen/Qwen3-14B-MLX-4bit"
TURBOQUANT_BITS = 4          # KV캐시 양자화 비트 (3 or 4)
TURBOQUANT_HEAD_DIM = 128    # Qwen3-14B head_dim
TURBOQUANT_NUM_LAYERS = 40   # Qwen3-14B layers
MAX_TOKENS_DEFAULT = 512  # 짧은 답변을 강제하기 위해 감소
PORT = 8000

KST = timezone(timedelta(hours=9))

# 세션 관리 (사용자 ID -> 세션 ID 매핑)
user_sessions = {}

# ──────────────────────────────────────────────
# 실시간 데이터 도구 (기존 유지)
# ──────────────────────────────────────────────
async def get_stock_data() -> str:
    """실시간 주식 정보 (코스피, S&P500, 나스닥, BTC)"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        results = []

        async with aiohttp.ClientSession() as session:
            # 1. 코스피 (네이버 금융)
            try:
                async with session.get("https://m.stock.naver.com/api/index/KOSPI/basic", timeout=3) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = float(data["closePrice"].replace(",", ""))
                        change = float(data["compareToPreviousClosePrice"].replace(",", ""))
                        if data.get("compareToPreviousPrice", {}).get("name") == "FALLING":
                            change = -change
                        ratio = data.get("fluctuationsRatio", "0%")
                        sign = "+" if change > 0 else ""
                        results.append(f"코스피: {current:,.0f} ({sign}{ratio}%)")
            except Exception as e:
                logger.warning(f"코스피 조회 실패: {e}")

            # 2. 미국 지수 + BTC (Yahoo Finance)
            symbols = {"S&P500": "^GSPC", "나스닥": "^IXIC", "비트코인": "BTC=X"}
            for name, sym in symbols.items():
                try:
                    async with session.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d", timeout=3) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                            price = meta.get("regularMarketPrice", 0)
                            prev_close = meta.get("chartPreviousClose", price)
                            chg = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
                            sign = "+" if chg > 0 else ""
                            results.append(f"{name}: ${price:,.0f} ({sign}{chg}%)")
                except Exception as e:
                    logger.warning(f"{name} 조회 실패: {e}")

        return " | ".join(results) if results else "주식 정보 조회 중..."
    except Exception as e:
        logger.error(f"주식 데이터 오류: {e}")
        return f"주식: 조회 중..."


async def get_news_summary() -> str:
    """뉴스 요약 (DuckDuckGo)"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        queries = [("경제 뉴스", "경제"), ("기술 뉴스", "기술")]
        results = []

        async with aiohttp.ClientSession() as session:
            for query, category in queries:
                try:
                    async with session.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=headers, timeout=2) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
                            if titles:
                                title = re.sub(r'<[^>]+>', '', titles[0]).strip()[:40]
                                results.append(f"【{category}】 {title}")
                except Exception:
                    pass

        return " | ".join(results) if results else "뉴스: 조회 중..."
    except Exception as e:
        logger.error(f"뉴스 오류: {e}")
        return "뉴스: 조회 중..."


async def search_duckduckgo(query: str, max_results: int = 3) -> str:
    """DuckDuckGo HTML 검색"""
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data={"q": query}, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return f"검색 실패 (HTTP {resp.status})"
                html = await resp.text()
                import re as _re
                results = []
                # 제목 추출
                titles = _re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, _re.DOTALL)
                # 스니펫 추출 (여러 패턴)
                snippets = _re.findall(r'result__snippet[^>]*>(.*?)</[atd]', html, _re.DOTALL)
                if not snippets:
                    snippets = _re.findall(r'class="result__snippet">(.*?)</a>', html, _re.DOTALL)
                # URL 추출
                urls = _re.findall(r'class="result__url"[^>]*>(.*?)</a>', html, _re.DOTALL)

                for i in range(min(max_results, max(len(titles), len(snippets)))):
                    title = _re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
                    snippet = _re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                    link = _re.sub(r'<[^>]+>', '', urls[i]).strip() if i < len(urls) else ""
                    if title or snippet:
                        results.append(f"[{title}] {snippet} ({link})")

                return "\n".join(results) if results else "검색 결과 없음"
    except Exception as e:
        logger.error(f"검색 오류: {e}")
        return f"검색 오류: {str(e)}"


async def get_weather(location: str = "Seoul") -> str:
    """wttr.in 날씨 조회"""
    try:
        url = f"https://wttr.in/{location}?format=j1&lang=ko"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return f"날씨 조회 실패 (HTTP {resp.status})"
                data = await resp.json()
                current = data.get("current_condition", [{}])[0]
                forecast = data.get("weather", [])

                now_desc = current.get("lang_ko", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", ""))
                now_temp = current.get("temp_C", "?")
                now_feels = current.get("FeelsLikeC", "?")
                now_humidity = current.get("humidity", "?")
                now_wind = current.get("windspeedKmph", "?")

                lines = [
                    f"📍 {location} 현재 날씨:",
                    f"  🌡️ {now_temp}°C (체감 {now_feels}°C)",
                    f"  🌤️ {now_desc}",
                    f"  💧 습도 {now_humidity}%",
                    f"  💨 바람 {now_wind}km/h",
                ]

                # 향후 3일 예보
                for day in forecast[:3]:
                    date = day.get("date", "")
                    max_t = day.get("maxtempC", "?")
                    min_t = day.get("mintempC", "?")
                    desc = day.get("hourly", [{}])[4].get("lang_ko", [{}])[0].get("value", "") if day.get("hourly") else ""
                    rain = day.get("hourly", [{}])[4].get("chanceofrain", "0") if day.get("hourly") else "0"
                    lines.append(f"  📅 {date}: {min_t}~{max_t}°C, {desc}, 강수확률 {rain}%")

                return "\n".join(lines)
    except Exception as e:
        logger.error(f"날씨 오류: {e}")
        return f"날씨 조회 오류: {str(e)}"


def needs_search(text: str) -> Optional[str]:
    """검색이 필요한 질문인지 판단"""
    search_keywords = [
        "검색", "찾아", "알려줘", "뉴스", "최신", "현재", "오늘",
        "어제", "내일", "가격", "환율", "주가", "결과", "소식",
        "누구", "언제", "어디", "무엇", "어떤", "어떻게", "왜", "몇",
        "how", "what", "when", "who", "where", "why",
        "search", "find", "latest", "news", "current", "price",
        "정보", "정의", "뜻", "의미", "요청", "취업", "채용", "공고",
    ]
    text_lower = text.lower()
    for kw in search_keywords:
        if kw in text_lower:
            return text
    return None


def needs_weather(text: str) -> Optional[str]:
    """날씨 관련 질문인지 판단"""
    weather_keywords = ["날씨", "기온", "비", "눈", "weather", "temperature", "forecast"]
    text_lower = text.lower()
    for kw in weather_keywords:
        if kw in text_lower:
            locations = re.findall(r'(서울|부산|대구|인천|광주|대전|울산|세종|오류동|천왕동|구로|금천|Seoul|Busan|[A-Z][a-z]+)', text)
            if locations:
                loc = locations[0]
                loc_map = {
                    "서울": "Seoul", "부산": "Busan", "대구": "Daegu",
                    "인천": "Incheon", "광주": "Gwangju", "대전": "Daejeon",
                    "울산": "Ulsan", "세종": "Sejong", "오류동": "Seoul",
                    "천왕동": "Seoul", "구로": "Seoul", "금천": "Seoul",
                }
                return loc_map.get(loc, loc)
            return "Seoul"
    return None


# ──────────────────────────────────────────────
# Pydantic 모델
# ──────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[Message] = Field(..., description="대화 메시지")
    model: str = Field("booml-mlx", description="모델")
    max_tokens: int = Field(MAX_TOKENS_DEFAULT)
    temperature: float = Field(0.5)
    top_p: float = Field(0.9)
    stream: bool = Field(False)
    user_id: Optional[str] = Field(None, description="사용자 ID (아키텍처 통합용)")
    project_id: Optional[str] = Field(None, description="프로젝트 ID (아키텍처 통합용)")

class FeedbackRequest(BaseModel):
    user_id: str = Field(..., description="사용자 ID")
    feedback_type: str = Field(..., description="피드백 타입: positive, negative, implicit")
    content: str = Field(..., description="피드백 내용")
    context: Optional[str] = Field(None, description="피드백 컨텍스트")
    project_id: Optional[str] = Field(None, description="프로젝트 ID")

class UserStatsRequest(BaseModel):
    user_id: str = Field(..., description="사용자 ID")
    days: int = Field(7, description="조회 기간 (일)")

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: str = "stop"

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Dict[str, int]
    metadata: Optional[Dict[str, Any]] = Field(None, description="아키텍처 메타데이터")

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    turboquant: bool
    performance: Dict[str, Any]
    architecture_enabled: bool = Field(ARCHITECTURE_ENABLED)

class UserStatsResponse(BaseModel):
    user_id: str
    period_days: int
    conversation_turns: int
    positive_examples_count: int
    negative_tags_count: int
    profile_summary: Dict[str, Any]
    kpi_stats: Dict[str, Any]


# ──────────────────────────────────────────────
# MLX 모델 + TurboQuant (기존 유지)
# ──────────────────────────────────────────────
class MLXModelV2:
    def __init__(self, model_id: str = MODEL_ID):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self.loaded = False
        self.load_time = 0
        self.turboquant_enabled = False

    def load(self):
        if self.loaded:
            return

        logger.info(f"모델 로드 중: {self.model_id}")
        start = time.time()

        from mlx_lm import load
        self.model, self.tokenizer = load(self.model_id)
        self.loaded = True
        self.load_time = time.time() - start
        logger.info(f"모델 로드 완료: {self.load_time:.2f}초")

        self.turboquant_enabled = True
        logger.info(f"KV캐시 양자화 활성화: {TURBOQUANT_BITS}bit, {len(self.model.layers)}레이어")

    def generate(self, messages: List[Message], max_tokens: int = MAX_TOKENS_DEFAULT, temperature: float = 0.7) -> str:
        if not self.loaded:
            self.load()

        from mlx_lm import generate

        chat_messages = [{"role": m.role, "content": m.content} for m in messages]

        if self.tokenizer.chat_template is not None:
            prompt = self.tokenizer.apply_chat_template(
                chat_messages,
                add_generation_prompt=True,
                tokenize=False,
                enable_thinking=False,
            )
        else:
            prompt = self._format_messages_fallback(messages)

        logger.info(f"생성 시작: prompt {len(prompt)}자, max_tokens={max_tokens}")
        start = time.time()

        kwargs = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "verbose": False,
        }

        if self.turboquant_enabled:
            kwargs["kv_bits"] = TURBOQUANT_BITS
            kwargs["kv_group_size"] = 64

        response = generate(self.model, self.tokenizer, **kwargs)

        gen_time = time.time() - start
        tokens = self.tokenizer.encode(response)
        tps = len(tokens) / gen_time if gen_time > 0 else 0
        logger.info(f"생성 완료: {gen_time:.2f}초, {len(tokens)}토큰, {tps:.1f}t/s")

        return response

    def _format_messages_fallback(self, messages: List[Message]) -> str:
        parts = []
        for m in messages:
            if m.role == "system":
                parts.append(f"<|im_start|>system\n{m.content}<|im_end|>")
            elif m.role == "user":
                parts.append(f"<|im_start|>user\n{m.content}<|im_end|>")
            elif m.role == "assistant":
                parts.append(f"<|im_start|>assistant\n{m.content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)


# 전역 모델
mlx_model = MLXModelV2()


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
    logger.info("붐엘 v2 아키텍처 통합 서버 시작...")
    await asyncio.to_thread(mlx_model.load)
    
    # 아키텍처 모듈 초기화
    if ARCHITECTURE_ENABLED:
        logger.info("붐엘 아키텍처 초기화 완료")
    
    yield
    
    # 세션 정리
    if ARCHITECTURE_ENABLED:
        booml_core.cleanup_old_sessions()
    
    logger.info("붐엘 v2 서버 종료")

app = FastAPI(
    title="붐엘(BoomL) MLX API v2 - 아키텍처 통합",
    description="Qwen3-14B + TurboQuant + Phase 1-2 아키텍처",
    version="2.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "service": "붐엘(BoomL) MLX API v2 - 아키텍처 통합",
        "model": mlx_model.model_id,
        "turboquant": mlx_model.turboquant_enabled,
        "architecture_enabled": ARCHITECTURE_ENABLED,
        "status": "running" if mlx_model.loaded else "loading"
    }


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy" if mlx_model.loaded else "loading",
        model_loaded=mlx_model.loaded,
        turboquant=mlx_model.turboquant_enabled,
        architecture_enabled=ARCHITECTURE_ENABLED,
        performance={
            "load_time": mlx_model.load_time,
            "model_id": mlx_model.model_id,
            "kv_cache_bits": TURBOQUANT_BITS if mlx_model.turboquant_enabled else 16,
        }
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    if not mlx_model.loaded:
        raise HTTPException(status_code=503, detail="모델 로드 중")
    
    # 사용자 ID 추출 (요청에서 또는 마지막 메시지에서)
    user_id = request.user_id or "anonymous"
    project_id = request.project_id
    
    # 마지막 사용자 메시지
    user_msg = ""
    for m in reversed(request.messages):
        if m.role == "user":
            user_msg = m.content
            break
    
    # 실시간 데이터 수집
    extra_context = []
    now_kst = datetime.now(KST)
    
    # 1. 날씨 체크
    weather_loc = needs_weather(user_msg)
    if weather_loc:
        weather_data = await get_weather(weather_loc)
        extra_context.append(f"[실시간 날씨 데이터]\n{weather_data}")
    
    # 2. 주식·뉴스 정보 (항상 포함)
    try:
        stock_data = await asyncio.wait_for(get_stock_data(), timeout=3)
        extra_context.append(f"[실시간 주식 정보]\n{stock_data}")
        
        news_data = await asyncio.wait_for(get_news_summary(), timeout=3)
        extra_context.append(f"[주요 뉴스]\n{news_data}")
    except asyncio.TimeoutError:
        logger.warning("주식/뉴스 데이터 조회 타임아웃")
    except Exception as e:
        logger.warning(f"주식/뉴스 데이터 조회 오류: {e}")
    
    # 3. 검색 체크
    search_query = needs_search(user_msg)
    if search_query:
        search_data = await search_duckduckgo(search_query)
        extra_context.append(f"[웹 검색 결과]\n{search_data}")
    
    # 실시간 데이터 문자열 생성
    realtime_data_str = "\n".join(extra_context) if extra_context else "실시간 데이터 없음"
    
    # 시스템 프롬프트 구성 (아키텍처 통합)
    if ARCHITECTURE_ENABLED:
        # 세션 관리
        session_id = get_or_create_session(user_id, project_id)
        
        # 아키텍처 기반 프롬프트 생성
        prompt = prompt_composer.compose_prompt(
            user_id, user_msg, realtime_data_str, project_id
        )
        
        # 코어를 통한 메시지 처리
        response_text, metadata = booml_core.process_message(
            session_id, user_msg, realtime_data_str
        )
        
        # 메타데이터에 세션 ID 추가
        metadata["session_id"] = session_id
        
    else:
        # 기존 방식 (아키텍처 비활성화 시)
        system_prompt = (
            f"붐엘(BoomL) · 붐(Boom)의 로컬 MLX 버전\n\n"
            f"시간: {now_kst.strftime('%Y년 %m월 %d일 %H:%M KST')}\n"
            f"플랫폼: macOS M4 Pro · MLX\n\n"
            f"📊 실시간 데이터:\n{realtime_data_str}\n\n"
            f"## 규칙 (절대 준수)\n"
            f"1. 한국어로만 답변 (코드 제외)\n"
            f"2. 최대 2-3문장 (매우 짧음)\n"
            f"3. 핵심만 — 설명/안내문 금지\n"
            f"4. 선택지 없음 — 판단하면 그대로 답변\n"
            f"5. 불확실한 정보는 '모르겠습니다'로 명확히 (추측/뻔한 답 금지)\n"
            f"6. 웹 검색 결과가 있으면 인용하고 없으면 모르겠습니다\n"
            f"7. 개인의견/철학/추측은 답하지 말 것\n"
            f"8. 기술 용어 최소화"
        )
        
        # 메시지 구성
        final_messages = [Message(role="system", content=system_prompt)]
        for m in request.messages:
            if m.role != "system":
                final_messages.append(m)
        
        # MLX 모델로 응답 생성
        response_text = await asyncio.to_thread(
            mlx_model.generate,
            final_messages,
            request.max_tokens,
            request.temperature
        )
        
        metadata = {
            "architecture_enabled": False,
            "user_id": user_id,
            "project_id": project_id
        }
    
    # 토큰 사용량 계산
    prompt_tokens = len(user_msg.split()) + len(realtime_data_str.split())
    completion_tokens = len(response_text.split())
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=Message(role="assistant", content=response_text),
                finish_reason="stop"
            )
        ],
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        },
        metadata=metadata if ARCHITECTURE_ENABLED else None
    )


@app.post("/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    """피드백 제출 엔드포인트"""
    if not ARCHITECTURE_ENABLED:
        raise HTTPException(status_code=501, detail="아키텍처 기능 비활성화")
    
    # 세션 조회
    session_id = get_or_create_session(request.user_id, request.project_id)
    
    # 피드백 처리
    booml_core.process_feedback(
        session_id, request.feedback_type, 
        request.content, request.context
    )
    
    return {
        "status": "success",
        "message": "피드백 처리 완료",
        "user_id": request.user_id,
        "feedback_type": request.feedback_type
    }


@app.post("/v1/user/stats")
async def get_user_stats(request: UserStatsRequest) -> UserStatsResponse:
    """사용자 통계 조회"""
    if not ARCHITECTURE_ENABLED:
        raise HTTPException(status_code=501, detail="아키텍처 기능 비활성화")
    
    stats = booml_core.get_user_stats(request.user_id, request.days)
    
    return UserStatsResponse(**stats)


@app.get("/v1/architecture/status")
async def architecture_status():
    """아키텍처 상태 확인"""
    return {
        "enabled": ARCHITECTURE_ENABLED,
        "modules": {
            "memory_store": ARCHITECTURE_ENABLED,
            "policy_engine": ARCHITECTURE_ENABLED,
            "prompt_composer": ARCHITECTURE_ENABLED,
            "kpi_logger": ARCHITECTURE_ENABLED,
            "booml_core": ARCHITECTURE_ENABLED
        },
        "database": {
            "memory_db": "booml_memory.db",
            "kpi_db": "booml_kpi.db"
        } if ARCHITECTURE_ENABLED else {}
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
