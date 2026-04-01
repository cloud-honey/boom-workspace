#!/usr/bin/env python3
"""붐엘(BoomL) MLX HTTP API 서버 - 수정 버전"""

import asyncio
import json
import time
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic 모델
class Message(BaseModel):
    role: str = Field(..., description="메시지 역할 (system, user, assistant)")
    content: str = Field(..., description="메시지 내용")

class ChatCompletionRequest(BaseModel):
    messages: List[Message] = Field(..., description="대화 메시지 목록")
    model: str = Field("booml-mlx", description="모델 이름")
    max_tokens: int = Field(1024, description="최대 생성 토큰 수")
    temperature: float = Field(0.7, description="생성 온도")
    top_p: float = Field(0.9, description="Top-p 샘플링")
    stream: bool = Field(False, description="스트리밍 여부")

class ChatCompletionChoice(BaseModel):
    index: int = Field(0, description="선택지 인덱스")
    message: Message = Field(..., description="응답 메시지")
    finish_reason: str = Field("stop", description="완료 이유")

class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="응답 ID")
    object: str = Field("chat.completion", description="객체 타입")
    created: int = Field(..., description="생성 시간")
    model: str = Field(..., description="모델 이름")
    choices: List[ChatCompletionChoice] = Field(..., description="선택지 목록")
    usage: Dict[str, int] = Field(..., description="사용량 통계")

class HealthResponse(BaseModel):
    status: str = Field(..., description="상태")
    model_loaded: bool = Field(..., description="모델 로드 여부")
    performance: Dict[str, Any] = Field(..., description="성능 정보")

# MLX 모델 래퍼
class MLXModel:
    def __init__(self, model_id: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"):
        self.model_id = model_id
        self.model = None
        self.tokenizer = None
        self.loaded = False
        self.load_time = 0
        
    def load(self):
        """모델 로드"""
        if self.loaded:
            return
            
        logger.info(f"모델 로드 중: {self.model_id}")
        start_time = time.time()
        
        try:
            # MLX-LM 모델 로드
            from mlx_lm import load
            self.model, self.tokenizer = load(self.model_id)
            self.loaded = True
            self.load_time = time.time() - start_time
            logger.info(f"모델 로드 완료: {self.load_time:.2f}초")
            
        except Exception as e:
            logger.error(f"모델 로드 실패: {e}")
            raise e
    
    def generate(self, messages: List[Message], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """텍스트 생성 - MLX-LM generate 함수 사용"""
        if not self.loaded:
            self.load()
        
        # 메시지를 프롬프트로 변환
        prompt = self._format_messages(messages)
        
        logger.info(f"생성 시작: {len(prompt)}자, max_tokens={max_tokens}")
        start_time = time.time()
        
        try:
            # MLX-LM generate 함수 임포트
            from mlx_lm import generate
            
            # 실제 생성
            response = generate(
                self.model,
                self.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                verbose=False
            )
            
            gen_time = time.time() - start_time
            
            # 토큰 계산
            tokens = self.tokenizer.encode(response)
            token_count = len(tokens)
            tokens_per_second = token_count / gen_time if gen_time > 0 else 0
            
            logger.info(f"생성 완료: {gen_time:.2f}초, {token_count}토큰, {tokens_per_second:.1f}t/s")
            
            return response
            
        except Exception as e:
            logger.error(f"생성 실패: {e}")
            return f"Error: {str(e)}"
    
    def _format_messages(self, messages: List[Message]) -> str:
        """메시지 목록을 프롬프트 문자열로 변환"""
        formatted = []
        for msg in messages:
            if msg.role == "system":
                formatted.append(f"System: {msg.content}")
            elif msg.role == "user":
                formatted.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                formatted.append(f"Assistant: {msg.content}")
        
        return "\n".join(formatted) + "\nAssistant: "

# 전역 모델 인스턴스
mlx_model = MLXModel()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 수명주기 관리"""
    # 시작 시
    logger.info("붐엘(BoomL) API 서버 시작 중...")
    
    # 모델 비동기 로드
    await asyncio.to_thread(mlx_model.load)
    
    yield
    
    # 종료 시
    logger.info("붐엘(BoomL) API 서버 종료 중...")

# FastAPI 앱 생성
app = FastAPI(
    title="붐엘(BoomL) MLX API",
    description="MLX 기반 고속 로컬 LLM API 서버",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "붐엘(BoomL) MLX API",
        "version": "0.1.0",
        "status": "running",
        "model": mlx_model.model_id,
        "model_loaded": mlx_model.loaded
    }

@app.get("/health")
async def health() -> HealthResponse:
    """헬스 체크"""
    return HealthResponse(
        status="healthy" if mlx_model.loaded else "loading",
        model_loaded=mlx_model.loaded,
        performance={
            "load_time": mlx_model.load_time,
            "model_id": mlx_model.model_id
        }
    )

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """채팅 완성 엔드포인트 (OpenAI 호환)"""
    if not mlx_model.loaded:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    # 생성
    response_text = await asyncio.to_thread(
        mlx_model.generate,
        request.messages,
        request.max_tokens,
        request.temperature
    )
    
    # 응답 구성
    response_message = Message(role="assistant", content=response_text)
    
    # 토큰 계산 (간단한 추정)
    prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
    completion_tokens = len(response_text.split())
    
    return ChatCompletionResponse(
        id=f"chatcmpl-{int(time.time())}",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=response_message,
                finish_reason="stop"
            )
        ],
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)