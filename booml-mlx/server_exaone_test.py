#!/usr/bin/env python3
"""붐엘 EXAONE 시험 서버
- 기존 붐엘은 건드리지 않음
- EXAONE-3.5-7.8B-Instruct를 별도 포트로 테스트
- 동일한 프롬프트 규칙을 최대한 재사용
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from prompt_composer import prompt_composer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = 8004
MAX_TOKENS_DEFAULT = 512
MODEL_ID = "mlx-community/EXAONE-3.5-7.8B-Instruct-4bit"


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str = Field("booml-exaone", description="모델")
    max_tokens: int = Field(MAX_TOKENS_DEFAULT, description="최대 토큰 수")
    temperature: float = Field(0.5, description="온도")
    stream: bool = Field(False, description="스트리밍 여부")


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: Message
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-exaone-{int(time.time())}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "booml-exaone"
    choices: List[ChatCompletionChoice]
    metadata: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    server_version: str = "exaone-test"
    model_id: str
    model_loaded: bool
    uptime_seconds: float


@dataclass
class ExaoneEngine:
    model_id: str = MODEL_ID
    model: Any = None
    tokenizer: Any = None
    loaded: bool = False
    load_time_s: float = 0.0

    def load(self):
        if self.loaded:
            return
        logger.info(f"EXAONE 모델 로드 중: {self.model_id}")
        started = time.time()
        try:
            from mlx_lm import load
            self.model, self.tokenizer = load(self.model_id)
            self.loaded = True
            self.load_time_s = round(time.time() - started, 2)
            logger.info(f"EXAONE 모델 로드 완료: {self.load_time_s}초")
        except Exception as e:
            logger.error(f"EXAONE 모델 로드 실패: {e}")
            self.loaded = False
            self.load_time_s = -1
            # Don't raise, just mark as not loaded

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.5) -> str:
        if not self.loaded:
            try:
                self.load()
            except Exception as e:
                logger.error(f"모델 로드 실패로 폴백 응답: {e}")
                return f"[EXAONE 모델 로드 실패: {e}] 테스트를 위해 이 메시지를 표시합니다. 실제 모델: {self.model_id}"
        
        if not self.loaded:
            return f"[EXAONE 모델 로드되지 않음] 테스트를 위해 이 메시지를 표시합니다. 모델 ID: {self.model_id}"
        
        try:
            from mlx_lm import generate

            if self.tokenizer.chat_template is not None:
                messages = [{"role": "user", "content": prompt}]
                formatted = self.tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=False
                )
            else:
                formatted = prompt

            kwargs = {
                "prompt": formatted,
                "max_tokens": max_tokens,
                "verbose": False,
                "temp": temperature,
                "kv_bits": 4,
                "kv_group_size": 64,
            }
            return generate(self.model, self.tokenizer, **kwargs)
        except Exception as e:
            logger.error(f"EXAONE 생성 실패: {e}")
            return f"[EXAONE 생성 오류: {e}] 원본 프롬프트: {prompt[:100]}..."


engine = ExaoneEngine()


async def get_weather_data() -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://wttr.in/Seoul?format=%C+%t+%h+%w", timeout=5) as resp:
                if resp.status == 200:
                    return f"서울 날씨: {(await resp.text()).strip()}"
    except Exception as e:
        logger.warning(f"날씨 조회 실패: {e}")
    return ""


async def get_realtime_data() -> str:
    weather = await get_weather_data()
    return weather or ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("EXAONE 시험 서버 시작")
    app.state.start_time = time.time()
    yield
    logger.info("EXAONE 시험 서버 종료")


app = FastAPI(title="BoomL EXAONE Test Server", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return {"message": "BoomL EXAONE test server", "health": "/health"}


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        model_id=MODEL_ID,
        model_loaded=engine.loaded,
        uptime_seconds=time.time() - app.state.start_time,
    )


@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    try:
        user_messages = [m for m in request.messages if m.role == "user"]
        last_user_message = user_messages[-1].content if user_messages else ""
        realtime_data = await get_realtime_data() if len(user_messages) == 1 else ""

        prompt = prompt_composer.compose_prompt(
            user_id="exaone_test_user",
            user_message=last_user_message,
            realtime_data=realtime_data,
            project_id=None,
        )

        started = time.time()
        response_text = await asyncio.to_thread(engine.generate, prompt, request.max_tokens, request.temperature)
        elapsed = round((time.time() - started) * 1000, 2)

        return ChatCompletionResponse(
            choices=[ChatCompletionChoice(message=Message(role="assistant", content=response_text))],
            metadata={
                "model_used": "exaone-3.5-7.8b-instruct-4bit-mlx",
                "generation_ms": elapsed,
                "prompt_length": len(prompt),
            }
        )
    except Exception as e:
        logger.error(f"EXAONE 응답 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
