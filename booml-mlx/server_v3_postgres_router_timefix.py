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
PORT = 8004

KST = timezone(timedelta(hours=9))

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


async def get_realtime_data() -> str:
    """실시간 데이터 수집 (주식, 날씨, 뉴스)"""
    try:
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


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    feedback_type: str = Field(..., description="피드백 타입 (positive/negative/implicit)")
    content: str = Field(..., description="피드백 내용")
    context: Optional[str] = Field(None, description="피드백 컨텍스트")


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
    
    return HealthResponse(
        status="healthy",
        architecture_enabled=ARCHITECTURE_ENABLED,
        model_routing_enabled=MODEL_ROUTING_ENABLED,
        active_model=active_model,
        routing_strategy=routing_strategy,
        available_models=available_models,
        database_backend=db_backend,
        uptime_seconds=uptime
    )


@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """채팅 완성 (모델 라우팅 지원)"""
    try:
        # 실시간 데이터 수집 (첫 번째 사용자 메시지인 경우)
        realtime_data = ""
        user_messages = [m for m in request.messages if m.role == "user"]
        if user_messages and len(user_messages) == 1:
            realtime_data = await get_realtime_data()
        
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
        
        # 아키텍처 통합 모드
        if ARCHITECTURE_ENABLED:
            # 붐엘 코어를 통한 메시지 처리
            last_user_message = user_messages[-1].content if user_messages else ""
            response_text, metadata = booml_core.process_message(
                session_id, last_user_message, realtime_data,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            # 응답 메시지 구성
            response_message = Message(role="assistant", content=response_text)
            
            return ChatCompletionResponse(
                choices=[ChatCompletionChoice(message=response_message)],
                metadata={
                    "session_id": session_id,
                    "architecture_enabled": True,
                    "model_used": "booml-core",
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
            response_text, model_used = model_router.generate_with_strategy(
                messages_dict,
                strategy=routing_strategy,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            if not response_text:
                raise HTTPException(status_code=500, detail="모델 응답 생성 실패")
            
            # 응답 메시지 구성
            response_message = Message(role="assistant", content=response_text)
            
            return ChatCompletionResponse(
                choices=[ChatCompletionChoice(message=response_message)],
                metadata={
                    "session_id": session_id,
                    "architecture_enabled": False,
                    "model_routing_enabled": True,
                    "model_used": model_used,
                    "routing_strategy": routing_strategy.value if routing_strategy else "default"
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
        booml_core.process_feedback(
            request.session_id,
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