#!/usr/bin/env python3
"""모델 어댑터 및 라우터 계층
- 다중 모델 핫-스위칭 및 오케스트레이션 지원
- 모델 어댑터 인터페이스
- 모델 레지스트리 및 라우터
- 라우팅 정책: default, fast, quality
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """라우팅 전략"""
    DEFAULT = "default"      # 기본 모델
    FAST = "fast"           # 빠른 응답 (경량 모델)
    QUALITY = "quality"     # 고품질 응답 (대형 모델)


@dataclass
class ModelMetadata:
    """모델 메타데이터"""
    name: str                      # 모델 이름 (예: "qwen3-14b-mlx")
    display_name: str              # 표시 이름 (예: "Qwen3 14B MLX")
    adapter_type: str              # 어댑터 타입 (예: "mlx", "openai", "ollama")
    capabilities: List[str]        # 지원 기능 (예: ["text", "reasoning"])
    priority: int = 0              # 우선순위 (높을수록 우선)
    is_loaded: bool = False        # 현재 로드 여부
    load_time_ms: float = 0        # 로드 시간 (밀리초)
    avg_response_time_ms: float = 0  # 평균 응답 시간
    token_per_second: float = 0    # 토큰/초 성능
    memory_usage_mb: float = 0     # 메모리 사용량 (MB)
    last_used: float = 0           # 마지막 사용 시간 (timestamp)
    usage_count: int = 0           # 사용 횟수


class ModelAdapter(ABC):
    """모델 어댑터 추상화 인터페이스"""
    
    @abstractmethod
    def load(self):
        """모델 로드"""
        pass
    
    @abstractmethod
    def unload(self):
        """모델 언로드 (메모리 해제)"""
        pass
    
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], 
                 max_tokens: int = 512, 
                 temperature: float = 0.7) -> str:
        """응답 생성"""
        pass
    
    @abstractmethod
    def get_metadata(self) -> ModelMetadata:
        """모델 메타데이터 조회"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """모델 사용 가능 여부"""
        pass


class MLXAdapter(ModelAdapter):
    """MLX 모델 어댑터 (현재 구현) - mlx_vlm 사용"""
    
    def __init__(self, model_id: str = "mlx-community/gemma-4-26b-a4b-it-4bit", 
                 display_name: str = "Gemma 4 26B A4B MoE MLX"):
        self.model_id = model_id
        self.display_name = display_name
        self.model = None
        self.tokenizer = None
        self.loaded = False
        self.load_time = 0
        self.usage_count = 0
        self.total_response_time = 0
        self.lock = threading.RLock()
    
    def load(self):
        """MLX 모델 로드 - mlx_vlm 사용"""
        with self.lock:
            if self.loaded:
                return
            
            logger.info(f"MLX 모델 로드 중 (mlx_vlm): {self.model_id}")
            start = time.time()
            
            try:
                # mlx_vlm으로 모델 로드
                from mlx_vlm import load
                self.model, self.tokenizer = load(self.model_id)
                self.loaded = True
                self.load_time = (time.time() - start) * 1000  # ms
                
                logger.info(f"MLX 모델 로드 완료 (mlx_vlm): {self.load_time:.2f}ms")
            except ImportError as e:
                logger.error(f"mlx_vlm 라이브러리 임포트 실패: {e}")
                # mlx_lm으로 폴백 시도
                try:
                    from mlx_lm import load as load_lm
                    self.model, self.tokenizer = load_lm(self.model_id)
                    self.loaded = True
                    self.load_time = (time.time() - start) * 1000
                    logger.info(f"MLX 모델 로드 완료 (mlx_lm 폴백): {self.load_time:.2f}ms")
                except Exception as e2:
                    logger.error(f"MLX 모델 로드 실패 (폴백도 실패): {e2}")
                    raise
            except Exception as e:
                logger.error(f"MLX 모델 로드 실패: {e}")
                raise
    
    def unload(self):
        """MLX 모델 언로드"""
        with self.lock:
            if not self.loaded:
                return
            
            # MLX 모델은 Python GC에 의해 자동으로 메모리 해제됨
            self.model = None
            self.tokenizer = None
            self.loaded = False
            logger.info(f"MLX 모델 언로드: {self.model_id}")
    
    def generate(self, messages: List[Dict[str, str]], 
                 max_tokens: int = 512, 
                 temperature: float = 0.7) -> Tuple[str, Dict]:
        """응답 생성 - mlx_vlm 사용
        
        Returns:
            Tuple[응답_텍스트, 토큰_통계]
            토큰_통계: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int,
                       "prompt_tps": float, "generation_tps": float, "peak_memory_gb": float}
        """
        with self.lock:
            if not self.loaded:
                self.load()
            
            start_time = time.time()
            
            try:
                # mlx_vlm 또는 mlx_lm으로 생성 시도
                try:
                    from mlx_vlm import generate as generate_vlm
                    generate_func = generate_vlm
                    logger.debug("mlx_vlm.generate 사용")
                except ImportError:
                    from mlx_lm import generate as generate_lm
                    generate_func = generate_lm
                    logger.debug("mlx_lm.generate 사용 (폴백)")
                
                # 메시지 포맷팅
                if self.tokenizer.chat_template is not None:
                    prompt = self.tokenizer.apply_chat_template(
                        messages,
                        add_generation_prompt=True,
                        tokenize=False,
                        enable_thinking=False,
                    )
                else:
                    prompt = self._format_messages_fallback(messages)
                
                # 생성 파라미터
                kwargs = {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "verbose": False,
                    "temperature": temperature,
                }
                
                # TurboQuant KV 캐시 압축 활성화
                # kv_quant_scheme="turboquant" 필수 — 없으면 uniform으로 폴백됨
                # 3.5비트: 메모리 절약 + 품질 균형 (4.6x 압축)
                kwargs["kv_bits"] = 3.5
                kwargs["kv_quant_scheme"] = "turboquant"
                
                # 응답 생성
                response = generate_func(self.model, self.tokenizer, **kwargs)
                
                # GenerationResult에서 텍스트 및 토큰 통계 추출
                token_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                               "prompt_tps": 0.0, "generation_tps": 0.0, "peak_memory_gb": 0.0}
                
                if hasattr(response, 'text'):
                    response_text = response.text
                    # GenerationResult 토큰 통계 수집
                    token_stats["prompt_tokens"] = getattr(response, 'prompt_tokens', 0)
                    token_stats["completion_tokens"] = getattr(response, 'generation_tokens', 0)
                    token_stats["total_tokens"] = getattr(response, 'total_tokens', 0) or (
                        token_stats["prompt_tokens"] + token_stats["completion_tokens"]
                    )
                    token_stats["prompt_tps"] = getattr(response, 'prompt_tps', 0.0)
                    token_stats["generation_tps"] = getattr(response, 'generation_tps', 0.0)
                    token_stats["peak_memory_gb"] = getattr(response, 'peak_memory', 0.0)
                elif hasattr(response, 'generated_text'):
                    response_text = response.generated_text
                elif isinstance(response, str):
                    response_text = response
                else:
                    response_text = str(response)
                    if 'GenerationResult(text=' in response_text:
                        import re
                        match = re.search(r"GenerationResult\(text='(.*?)',", response_text)
                        if match:
                            response_text = match.group(1)
                
                # 성능 통계 업데이트
                response_time = (time.time() - start_time) * 1000  # ms
                self.total_response_time += response_time
                self.usage_count += 1
                
                logger.info(
                    f"MLX 응답 생성 완료: {response_time:.2f}ms, {len(response_text)}자 | "
                    f"prompt={token_stats['prompt_tokens']}tok "
                    f"gen={token_stats['completion_tokens']}tok "
                    f"({token_stats['generation_tps']:.1f} t/s)"
                )
                return response_text, token_stats
                
            except Exception as e:
                logger.error(f"MLX 응답 생성 실패: {e}")
                raise
    
    def _format_messages_fallback(self, messages: List[Dict[str, str]]) -> str:
        """폴백 메시지 포맷팅"""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"<|im_start|>system\n{content}<|im_end|>")
            elif role == "user":
                parts.append(f"<|im_start|>user\n{content}<|im_end|>")
            elif role == "assistant":
                parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)
    
    def get_metadata(self) -> ModelMetadata:
        """MLX 모델 메타데이터"""
        avg_response_time = 0
        if self.usage_count > 0:
            avg_response_time = self.total_response_time / self.usage_count
        
        return ModelMetadata(
            name=self.model_id.split("/")[-1].lower(),
            display_name=self.display_name,
            adapter_type="mlx",
            capabilities=["text", "reasoning", "korean"],
            priority=50,  # 중간 우선순위
            is_loaded=self.loaded,
            load_time_ms=self.load_time,
            avg_response_time_ms=avg_response_time,
            token_per_second=57.2,  # 측정된 성능
            memory_usage_mb=4500,   # 4.5GB (4비트 양자화)
            last_used=time.time() if self.usage_count > 0 else 0,
            usage_count=self.usage_count
        )
    
    def is_available(self) -> bool:
        """MLX 모델 사용 가능 여부"""
        try:
            import mlx_lm
            return True
        except ImportError:
            return False


class DummyAdapter(ModelAdapter):
    """더미 어댑터 (테스트용)"""
    
    def __init__(self, name: str = "dummy", display_name: str = "Dummy Model"):
        self.name = name
        self.display_name = display_name
        self.usage_count = 0
    
    def load(self):
        logger.info(f"더미 모델 로드: {self.name}")
    
    def unload(self):
        logger.info(f"더미 모델 언로드: {self.name}")
    
    def generate(self, messages: List[Dict[str, str]], 
                 max_tokens: int = 512, 
                 temperature: float = 0.7) -> Tuple[str, Dict]:
        self.usage_count += 1
        text = f"이것은 {self.display_name}의 더미 응답입니다. 메시지: {len(messages)}개, 최대 토큰: {max_tokens}"
        stats = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30,
                 "prompt_tps": 0.0, "generation_tps": 0.0, "peak_memory_gb": 0.0}
        return text, stats
    
    def get_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            name=self.name,
            display_name=self.display_name,
            adapter_type="dummy",
            capabilities=["text"],
            priority=10,  # 낮은 우선순위
            is_loaded=True,
            load_time_ms=1,
            avg_response_time_ms=10,
            token_per_second=1000,
            memory_usage_mb=1,
            last_used=time.time(),
            usage_count=self.usage_count
        )
    
    def is_available(self) -> bool:
        return True


class ModelRegistry:
    """모델 레지스트리 (모델 등록 및 관리)"""
    
    def __init__(self):
        self.adapters: Dict[str, ModelAdapter] = {}
        self.active_model: Optional[str] = None
        self.lock = threading.RLock()
    
    def register(self, name: str, adapter: ModelAdapter, set_active: bool = False):
        """모델 어댑터 등록"""
        with self.lock:
            self.adapters[name] = adapter
            logger.info(f"모델 등록: {name} ({adapter.__class__.__name__})")
            
            if set_active or not self.active_model:
                self.active_model = name
                logger.info(f"활성 모델 설정: {name}")
    
    def unregister(self, name: str):
        """모델 어댑터 등록 해제"""
        with self.lock:
            if name in self.adapters:
                if self.active_model == name:
                    self.active_model = None
                
                # 모델 언로드
                try:
                    self.adapters[name].unload()
                except:
                    pass
                
                del self.adapters[name]
                logger.info(f"모델 등록 해제: {name}")
    
    def get_adapter(self, name: Optional[str] = None) -> Optional[ModelAdapter]:
        """모델 어댑터 조회"""
        with self.lock:
            if not name:
                name = self.active_model
            
            if not name or name not in self.adapters:
                return None
            
            return self.adapters[name]
    
    def set_active_model(self, name: str) -> bool:
        """활성 모델 설정 (핫-스위치)"""
        with self.lock:
            if name not in self.adapters:
                logger.error(f"활성 모델 설정 실패: 등록되지 않은 모델 '{name}'")
                return False
            
            old_model = self.active_model
            self.active_model = name
            
            logger.info(f"활성 모델 변경: {old_model} -> {name}")
            return True
    
    def get_active_model(self) -> Optional[str]:
        """활성 모델 이름 조회"""
        with self.lock:
            return self.active_model
    
    def list_models(self) -> List[Dict[str, Any]]:
        """등록된 모델 목록 조회"""
        with self.lock:
            models = []
            for name, adapter in self.adapters.items():
                metadata = adapter.get_metadata()
                models.append({
                    "name": name,
                    "display_name": metadata.display_name,
                    "adapter_type": metadata.adapter_type,
                    "is_active": name == self.active_model,
                    "is_loaded": metadata.is_loaded,
                    "capabilities": metadata.capabilities,
                    "priority": metadata.priority,
                    "usage_count": metadata.usage_count,
                    "avg_response_time_ms": metadata.avg_response_time_ms,
                })
            
            # 우선순위 순 정렬
            models.sort(key=lambda x: x["priority"], reverse=True)
            return models
    
    def get_model_metadata(self, name: str) -> Optional[ModelMetadata]:
        """모델 메타데이터 조회"""
        adapter = self.get_adapter(name)
        if adapter:
            return adapter.get_metadata()
        return None


class ModelRouter:
    """모델 라우터 (라우팅 전략 기반 모델 선택)"""
    
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self.strategy = RoutingStrategy.DEFAULT
    
    def set_routing_strategy(self, strategy: RoutingStrategy):
        """라우팅 전략 설정"""
        self.strategy = strategy
        logger.info(f"라우팅 전략 설정: {strategy.value}")
    
    def get_routing_strategy(self) -> RoutingStrategy:
        """현재 라우팅 전략 조회"""
        return self.strategy
    
    def route(self, strategy: Optional[RoutingStrategy] = None) -> Optional[ModelAdapter]:
        """라우팅 전략에 따른 모델 선택"""
        if not strategy:
            strategy = self.strategy
        
        with self.registry.lock:
            available_models = self.registry.list_models()
            if not available_models:
                logger.warning("라우팅 실패: 사용 가능한 모델 없음")
                return None
            
            # 전략별 모델 선택
            if strategy == RoutingStrategy.DEFAULT:
                # 기본: 활성 모델 또는 가장 높은 우선순위 모델
                active_name = self.registry.get_active_model()
                if active_name:
                    return self.registry.get_adapter(active_name)
                else:
                    # 가장 높은 우선순위 모델 선택
                    return self.registry.get_adapter(available_models[0]["name"])
            
            elif strategy == RoutingStrategy.FAST:
                # 빠른 응답: 가장 빠른 응답 시간의 모델
                fast_model = min(
                    available_models,
                    key=lambda m: m.get("avg_response_time_ms", float('inf'))
                )
                return self.registry.get_adapter(fast_model["name"])
            
            elif strategy == RoutingStrategy.QUALITY:
                # 고품질: 가장 높은 우선순위 + 로드된 모델
                # 현재는 기본 전략과 동일 (향후 개선)
                quality_models = [m for m in available_models if m.get("is_loaded", False)]
                if quality_models:
                    return self.registry.get_adapter(quality_models[0]["name"])
                else:
                    # 로드된 모델이 없으면 기본 전략 사용
                    return self.route(RoutingStrategy.DEFAULT)
            
            else:
                logger.warning(f"알 수 없는 라우팅 전략: {strategy}")
                return self.route(RoutingStrategy.DEFAULT)
    
    def generate_with_strategy(self, messages: List[Dict[str, str]], 
                               strategy: Optional[RoutingStrategy] = None,
                               max_tokens: int = 512, 
                               temperature: float = 0.7) -> Tuple[Optional[str], str, Dict]:
        """라우팅 전략에 따른 응답 생성
        
        Returns:
            Tuple[응답_텍스트, 사용된_모델_이름, 토큰_통계]
        """
        empty_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                       "prompt_tps": 0.0, "generation_tps": 0.0, "peak_memory_gb": 0.0}
        adapter = self.route(strategy)
        if not adapter:
            return None, "no_model_available", empty_stats
        
        model_name = adapter.get_metadata().name
        try:
            result = adapter.generate(messages, max_tokens, temperature)
            # MLXAdapter는 (text, token_stats) 튜플 반환, DummyAdapter는 문자열 반환
            if isinstance(result, tuple):
                response_text, token_stats = result
            else:
                response_text, token_stats = result, empty_stats
            return response_text, model_name, token_stats
        except Exception as e:
            logger.error(f"모델 응답 생성 실패 ({model_name}): {e}")
            return None, model_name, empty_stats


# 전역 모델 레지스트리 및 라우터 인스턴스
model_registry = ModelRegistry()
model_router = ModelRouter(model_registry)


def initialize_default_models():
    """기본 모델 초기화"""
    # MLX 모델 등록 (사용 가능한 경우)
    try:
        mlx_adapter = MLXAdapter()
        if mlx_adapter.is_available():
            model_registry.register("gemma-4-26b-a4b-it-4bit", mlx_adapter, set_active=True)
            logger.info("Gemma 4 26B A4B MoE MLX 모델 등록 완료 (활성 모델로 설정)")
        else:
            logger.warning("MLX 모델 사용 불가, 등록 건너뜀")
    except Exception as e:
        logger.warning(f"MLX 모델 등록 실패: {e}")
    
    # 더미 모델 등록 (항상 사용 가능)
    dummy_adapter = DummyAdapter()
    model_registry.register("dummy", dummy_adapter)
    logger.info("더미 모델 등록 완료")
    
    # 초기 라우팅 전략 설정
    model_router.set_routing_strategy(RoutingStrategy.DEFAULT)
    
    return model_registry.list_models()


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 모델 라우터 테스트")
    print("=" * 40)
    
    # 1. 기본 모델 초기화
    print("1. 기본 모델 초기화...")
    models = initialize_default_models()
    print(f"   ✅ 등록된 모델: {len(models)}개")
    for model in models:
        print(f"      - {model['name']} ({model['display_name']})")
    
    # 2. 모델 목록 조회
    print("\n2. 모델 목록 조회...")
    model_list = model_registry.list_models()
    for model in model_list:
        status = "활성" if model["is_active"] else "대기"
        print(f"   - {model['name']}: {status}, 사용횟수={model['usage_count']}")
    
    # 3. 라우팅 전략 테스트
    print("\n3. 라우팅 전략 테스트...")
    test_messages = [{"role": "user", "content": "테스트 메시지입니다."}]
    
    # 기본 전략
    response, model_name = model_router.generate_with_strategy(
        test_messages, RoutingStrategy.DEFAULT, max_tokens=50
    )
    print(f"   ✅ 기본 전략: 모델={model_name}, 응답={response[:50]}...")
    
    # 빠른 전략
    response, model_name = model_router.generate_with_strategy(
        test_messages, RoutingStrategy.FAST, max_tokens=50
    )
    print(f"   ✅ 빠른 전략: 모델={model_name}, 응답={response[:50]}...")
    
    # 고품질 전략
    response, model_name = model_router.generate_with_strategy(
        test_messages, RoutingStrategy.QUALITY, max_tokens=50
    )
    print(f"   ✅ 고품질 전략: 모델={model_name}, 응답={response[:50]}...")
    
    # 4. 핫-스위칭 테스트
    print("\n4. 핫-스위칭 테스트...")
    old_active = model_registry.get_active_model()
    print(f"   현재 활성 모델: {old_active}")
    
    # 더미 모델로 전환
    if model_registry.set_active_model("dummy"):
        new_active = model_registry.get_active_model()
        print(f"   ✅ 활성 모델 변경: {old_active} -> {new_active}")
        
        # 변경 확인
        response, model_name = model_router.generate_with_strategy(
            test_messages, RoutingStrategy.DEFAULT, max_tokens=50
        )
        print(f"   변경 후 응답: 모델={model_name}")
    else:
        print("   ❌ 활성 모델 변경 실패")
    
    # 5. 모델 메타데이터 조회
    print("\n5. 모델 메타데이터 조회...")
    for model_name in ["qwen3-14b-mlx", "dummy"]:
        metadata = model_registry.get_model_metadata(model_name)
        if metadata:
            print(f"   {model_name}:")
            print(f"     - 표시 이름: {metadata.display_name}")
            print(f"     - 어댑터 타입: {metadata.adapter_type}")
            print(f"     - 로드 여부: {metadata.is_loaded}")
            print(f"     - 사용 횟수: {metadata.usage_count}")
            print(f"     - 평균 응답 시간: {metadata.avg_response_time_ms:.2f}ms")
    
    print("\n" + "=" * 40)
    print("모델 라우터 테스트 완료")
    print("=" * 40)
