#!/usr/bin/env python3
"""붐엘 코어 통합 모듈
- 메모리 저장소, 정책 엔진, 프롬프트 조립기, KPI 로거 통합
- Phase 1-2 구현의 주요 진입점
"""

import logging
import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
try:
    from .memory_store import (
        memory_store, ConversationTurn, SessionSummary, UserProfile,
        ProfileScope, FeedbackEvent, PositiveExample, NegativeTag
    )
    from .policy_engine import policy_engine, FeedbackType
    from .prompt_composer import prompt_composer
    from .kpi_logger import kpi_logger, KPIMetric
    from .model_router import model_router
except ImportError:
    # 독립 실행을 위한 폴백
    from memory_store import (
        memory_store, ConversationTurn, SessionSummary, UserProfile,
        ProfileScope, FeedbackEvent, PositiveExample, NegativeTag
    )
    from policy_engine import policy_engine, FeedbackType
    from prompt_composer import prompt_composer
    from kpi_logger import kpi_logger, KPIMetric
    from model_router import model_router

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class BoomLCore:
    """붐엘 코어 시스템"""
    
    def __init__(self):
        self.active_sessions = {}  # session_id -> user_id 매핑
    
    def start_session(self, user_id: str, project_id: Optional[str] = None) -> str:
        """새 세션 시작"""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "project_id": project_id,
            "start_time": datetime.now(KST),
            "turns": []
        }
        
        # KPI 로깅
        kpi_logger.start_session(session_id, user_id)
        
        logger.info(f"세션 시작: {session_id} for user={user_id}, project={project_id}")
        return session_id
    
    def end_session(self, session_id: str):
        """세션 종료 및 요약 저장"""
        if session_id not in self.active_sessions:
            logger.warning(f"존재하지 않는 세션 종료 시도: {session_id}")
            return
        
        session_data = self.active_sessions.pop(session_id)
        user_id = session_data["user_id"]
        project_id = session_data["project_id"]
        turns = session_data["turns"]
        
        # 세션 요약 생성
        summary_text = prompt_composer.create_session_summary(user_id, turns, project_id)
        
        # 세션 요약 저장
        summary = SessionSummary(
            session_id=session_id,
            user_id=user_id,
            summary=summary_text,
            project_id=project_id,
            metadata={
                "turn_count": len(turns),
                "start_time": session_data["start_time"].isoformat(),
                "end_time": datetime.now(KST).isoformat()
            }
        )
        memory_store.save_session_summary(summary)
        
        # KPI: 세션 성공률 계산 및 로깅
        success_rate = kpi_logger.calculate_session_success_rate(session_id)
        kpi_logger.log_kpi_event(user_id, session_id, 
                               KPIMetric.SESSION_SUCCESS_RATE.value, success_rate)
        
        # KPI: 세션 종료
        kpi_logger.end_session(session_id)
        
        logger.info(f"세션 종료: {session_id}, 성공률={success_rate:.2f}, 요약={summary_text[:50]}...")
    
    def process_message(self, session_id: str, user_message: str, 
                        realtime_data: str = "", max_tokens: int = 512,
                        temperature: float = 0.7) -> Tuple[str, Dict[str, Any]]:
        """메시지 처리 및 응답 생성"""
        if session_id not in self.active_sessions:
            # 자동으로 세션 시작
            user_id = "unknown"  # 실제 구현에서는 사용자 ID 필요
            session_id = self.start_session(user_id)
        
        session_data = self.active_sessions[session_id]
        user_id = session_data["user_id"]
        project_id = session_data["project_id"]
        
        # 1. 대화 턴 저장 (사용자 메시지)
        user_turn = ConversationTurn(
            conversation_id=session_id,
            user_id=user_id,
            role="user",
            content=user_message,
            project_id=project_id,
            metadata={"realtime_data_included": bool(realtime_data)}
        )
        memory_store.save_conversation_turn(user_turn)
        
        # 세션 턴 기록 업데이트
        session_data["turns"].append({"role": "user", "content": user_message})
        
        # KPI: 턴 완료 로깅
        kpi_logger.log_turn_completion(user_id, session_id)
        
        # 2. 프롬프트 조립
        prompt = prompt_composer.compose_prompt(
            user_id, user_message, realtime_data, project_id
        )
        
        # 3. 메모리 사용 로깅 (간단한 검사)
        # 프롬프트에 메모리 관련 섹션이 있는지 확인
        if "관련 과거 대화" in prompt or "좋은 답변 예시" in prompt:
            kpi_logger.log_memory_usage(user_id, session_id, usefulness_score=0.7)
        
        # 4. 응답 생성 (실제 모델 라우터 사용)
        started = time.time()
        response_text, model_used, token_stats = self._generate_response(prompt, max_tokens=max_tokens, temperature=temperature)
        generation_ms = round((time.time() - started) * 1000, 2)
        
        # 5. 대화 턴 저장 (어시스턴트 응답)
        assistant_turn = ConversationTurn(
            conversation_id=session_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            project_id=project_id
        )
        memory_store.save_conversation_turn(assistant_turn)
        
        # 세션 턴 기록 업데이트
        session_data["turns"].append({"role": "assistant", "content": response_text})
        
        # 6. 메타데이터 구성
        metadata = {
            "session_id": session_id,
            "user_id": user_id,
            "project_id": project_id,
            "prompt_length": len(prompt),
            "response_length": len(response_text),
            "timestamp": datetime.now(KST).isoformat(),
            "model_used": model_used,
            "generation_ms": generation_ms,
            "token_stats": token_stats,
        }
        
        logger.info(f"메시지 처리 완료: session={session_id}, prompt_len={len(prompt)}, response_len={len(response_text)}")
        return response_text, metadata
    
    def process_feedback(self, session_id: str, feedback_type: str, 
                         content: str, context: Optional[str] = None):
        """피드백 처리"""
        # 세션이 없으면 user_id 추출 시도 (session_id 형식: feedback_session_{uuid} 또는 session_{uuid})
        user_id = None
        project_id = None
        
        if session_id in self.active_sessions:
            session_data = self.active_sessions[session_id]
            user_id = session_data["user_id"]
            project_id = session_data["project_id"]
        else:
            # session_id에서 user_id 추출 시도 (형식: feedback_session_{user_id}_{uuid})
            import re
            match = re.search(r'feedback_session_([^_]+)', session_id)
            if match:
                user_id = match.group(1)
            else:
                # 기본 user_id 사용
                user_id = "unknown_user"
                logger.warning(f"세션 정보 없음, 기본 user_id 사용: {session_id}")
        
        # 정책 엔진을 통한 피드백 처리
        policy_engine.process_feedback(user_id, feedback_type, content, context, project_id)
        
        # KPI 로깅
        kpi_logger.log_feedback(user_id, session_id, feedback_type)
        
        logger.info(f"피드백 처리: session={session_id}, user={user_id}, type={feedback_type}, content={content[:50]}...")
    
    def process_edit_request(self, session_id: str, original_message: str, 
                             edit_instruction: str):
        """수정 요청 처리"""
        if session_id not in self.active_sessions:
            logger.warning(f"존재하지 않는 세션 수정 요청: {session_id}")
            return
        
        session_data = self.active_sessions[session_id]
        user_id = session_data["user_id"]
        
        # KPI 로깅
        kpi_logger.log_edit_request(user_id, session_id)
        
        # 암묵적 피드백으로 처리
        self.process_feedback(session_id, FeedbackType.IMPLICIT.value, edit_instruction)
        
        logger.info(f"수정 요청 처리: session={session_id}, instruction={edit_instruction[:50]}...")
    
    def process_retry(self, session_id: str, original_message: str):
        """재시도 처리"""
        if session_id not in self.active_sessions:
            logger.warning(f"존재하지 않는 세션 재시도: {session_id}")
            return
        
        session_data = self.active_sessions[session_id]
        user_id = session_data["user_id"]
        
        # KPI 로깅
        kpi_logger.log_retry(user_id, session_id)
        
        logger.info(f"재시도 처리: session={session_id}")
    
    def get_user_stats(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """사용자 통계 조회"""
        # KPI 통계
        kpi_stats = kpi_logger.get_recent_kpis(user_id, days)
        
        # 메모리 통계
        conversation_count = len(memory_store.get_conversation_turns(user_id, limit=1000))
        session_summaries = []
        
        # 프로필 정보
        global_profile = memory_store.get_user_profile(user_id, ProfileScope.GLOBAL.value)
        profile_summary = {
            "has_global_profile": global_profile is not None,
            "preference_count": len(global_profile.profile_data) if global_profile else 0,
            "confidence": global_profile.confidence if global_profile else 0.0
        }
        
        # 긍정/부정 예시 수
        positive_examples = memory_store.get_positive_examples(user_id, limit=100)
        negative_tags = memory_store.get_negative_tags(user_id, limit=100)
        
        result = {
            "user_id": user_id,
            "period_days": days,
            "conversation_turns": conversation_count,
            "positive_examples_count": len(positive_examples),
            "negative_tags_count": len(negative_tags),
            "profile_summary": profile_summary,
            "kpi_stats": kpi_stats
        }
        
        return result
    
    def _generate_response(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> Tuple[str, str, Dict]:
        """응답 생성: 기본적으로 활성 모델 라우터를 통해 실제 MLX 생성 수행
        
        Returns:
            Tuple[응답_텍스트, 모델명, 토큰_통계]
        """
        messages = [{"role": "user", "content": prompt}]
        empty_stats = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                       "prompt_tps": 0.0, "generation_tps": 0.0, "peak_memory_gb": 0.0}
        try:
            response_text, model_used, token_stats = model_router.generate_with_strategy(
                messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            if response_text:
                return response_text, model_used, token_stats
        except Exception as e:
            logger.error(f"모델 라우터 응답 생성 실패: {e}")
        
        # 최후 폴백
        return "현재 실제 모델 응답 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", "fallback-error", empty_stats
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """오래된 세션 정리"""
        now = datetime.now(KST)
        sessions_to_remove = []
        
        for session_id, session_data in self.active_sessions.items():
            session_age = now - session_data["start_time"]
            if session_age.total_seconds() > max_age_hours * 3600:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            self.end_session(session_id)
            logger.info(f"오래된 세션 정리: {session_id}")


# 전역 코어 인스턴스
booml_core = BoomLCore()