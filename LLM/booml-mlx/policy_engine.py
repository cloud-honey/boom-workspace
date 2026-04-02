#!/usr/bin/env python3
"""붐엘 정책 엔진
- 사용자 선호도 슬롯 관리
- 프로필 기반 프롬프트 조정
- 피드백 기반 선호도 업데이트
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
try:
    from .memory_store import (
        memory_store, UserProfile, ProfileScope, FeedbackEvent, 
        FeedbackType, PositiveExample, NegativeTag
    )
except ImportError:
    # 독립 실행을 위한 폴백
    from memory_store import (
        memory_store, UserProfile, ProfileScope, FeedbackEvent, 
        FeedbackType, PositiveExample, NegativeTag
    )

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class PreferenceSlot(Enum):
    """선호도 슬롯 정의"""
    ANSWER_LENGTH = "answer_length"  # short, medium, long
    TONE = "tone"  # concise, plain, warm, structured
    STRUCTURE = "structure"  # plain, step_by_step, compare
    TECHNICAL_DEPTH = "technical_depth"  # low, medium, high
    FORMAT = "format"  # paragraph, bullets, markdown
    REASONING_MODE = "reasoning_mode"  # off, light, deep


class PolicyEngine:
    """정책 엔진: 사용자 선호도 관리 및 적용"""
    
    def __init__(self):
        self.default_profile = {
            PreferenceSlot.ANSWER_LENGTH.value: "medium",
            PreferenceSlot.TONE.value: "plain",
            PreferenceSlot.STRUCTURE.value: "step_by_step",
            PreferenceSlot.TECHNICAL_DEPTH.value: "low",
            PreferenceSlot.FORMAT.value: "markdown",
            PreferenceSlot.REASONING_MODE.value: "off"
        }
    
    def get_user_profile(self, user_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """사용자 프로필 조회 (계층적: session → project → global)"""
        profiles = []
        
        # 세션 프로필 (가장 높은 우선순위)
        session_profile = memory_store.get_user_profile(
            user_id, ProfileScope.SESSION.value, project_id
        )
        if session_profile:
            profiles.append(session_profile.profile_data)
        
        # 프로젝트 프로필
        if project_id:
            project_profile = memory_store.get_user_profile(
                user_id, ProfileScope.PROJECT.value, project_id
            )
            if project_profile:
                profiles.append(project_profile.profile_data)
        
        # 글로벌 프로필
        global_profile = memory_store.get_user_profile(
            user_id, ProfileScope.GLOBAL.value, None
        )
        if global_profile:
            profiles.append(global_profile.profile_data)
        
        # 기본값으로 시작
        merged_profile = self.default_profile.copy()
        
        # 계층적 병합 (높은 우선순위가 낮은 우선순위 덮어씀)
        for profile in profiles:
            for key, value in profile.items():
                if value:  # 값이 있는 경우만 업데이트
                    merged_profile[key] = value
        
        return merged_profile
    
    def update_user_preference(self, user_id: str, slot: str, value: str, 
                               confidence: float = 0.5, scope: str = ProfileScope.GLOBAL.value,
                               project_id: Optional[str] = None):
        """사용자 선호도 업데이트"""
        # 기존 프로필 조회
        profile = memory_store.get_user_profile(user_id, scope, project_id)
        
        if profile:
            # 기존 프로필 업데이트
            profile.profile_data[slot] = value
            profile.confidence = max(profile.confidence, confidence)
            profile.updated_at = datetime.now(KST)
        else:
            # 새 프로필 생성
            profile_data = self.default_profile.copy()
            profile_data[slot] = value
            
            profile = UserProfile(
                user_id=user_id,
                scope=scope,
                profile_data=profile_data,
                confidence=confidence,
                project_id=project_id
            )
        
        memory_store.save_user_profile(profile)
        logger.info(f"프로필 업데이트: user={user_id}, scope={scope}, slot={slot}={value}, conf={confidence}")
    
    def process_feedback(self, user_id: str, feedback_type: str, content: str,
                         context: Optional[str] = None, project_id: Optional[str] = None):
        """피드백 처리 및 선호도 업데이트"""
        # 피드백 이벤트 저장
        event = FeedbackEvent(
            user_id=user_id,
            feedback_type=feedback_type,
            content=content,
            metadata={"context": context} if context else {},
            project_id=project_id
        )
        memory_store.save_feedback_event(event)
        
        # 피드백 타입별 처리
        if feedback_type == FeedbackType.POSITIVE.value:
            self._process_positive_feedback(user_id, content, context, project_id)
        elif feedback_type == FeedbackType.NEGATIVE.value:
            self._process_negative_feedback(user_id, content, context, project_id)
        elif feedback_type == FeedbackType.IMPLICIT.value:
            self._process_implicit_feedback(user_id, content, context, project_id)
    
    def _process_positive_feedback(self, user_id: str, content: str, 
                                   context: Optional[str], project_id: Optional[str]):
        """긍정 피드백 처리"""
        # 긍정 예시 저장
        example = PositiveExample(
            user_id=user_id,
            example_text=content,
            tags=self._extract_tags_from_feedback(content),
            context=context or "",
            project_id=project_id
        )
        memory_store.save_positive_example(example)
        
        # 피드백에서 선호도 추출
        preferences = self._extract_preferences_from_feedback(content)
        for slot, value in preferences.items():
            self.update_user_preference(
                user_id, slot, value, 
                confidence=0.7,  # 긍정 피드백은 높은 신뢰도
                scope=ProfileScope.GLOBAL.value,
                project_id=project_id
            )
    
    def _process_negative_feedback(self, user_id: str, content: str,
                                   context: Optional[str], project_id: Optional[str]):
        """부정 피드백 처리"""
        # 부정 태그 저장
        tags = self._extract_negative_tags(content)
        for tag in tags:
            negative_tag = NegativeTag(
                user_id=user_id,
                tag=tag,
                context=context or "",
                project_id=project_id
            )
            memory_store.save_negative_tag(negative_tag)
        
        # 피드백에서 선호도 추출 (반대값 적용)
        preferences = self._extract_preferences_from_feedback(content, invert=True)
        for slot, value in preferences.items():
            self.update_user_preference(
                user_id, slot, value,
                confidence=0.8,  # 부정 피드백은 매우 높은 신뢰도
                scope=ProfileScope.GLOBAL.value,
                project_id=project_id
            )
    
    def _process_implicit_feedback(self, user_id: str, content: str,
                                   context: Optional[str], project_id: Optional[str]):
        """암묵적 피드백 처리"""
        # 암묵적 피드백은 낮은 신뢰도로 선호도 업데이트
        preferences = self._extract_preferences_from_feedback(content)
        for slot, value in preferences.items():
            self.update_user_preference(
                user_id, slot, value,
                confidence=0.3,  # 암묵적 피드백은 낮은 신뢰도
                scope=ProfileScope.SESSION.value,  # 세션 범위로 제한
                project_id=project_id
            )
    
    def _extract_tags_from_feedback(self, feedback: str) -> List[str]:
        """피드백에서 태그 추출"""
        tags = []
        feedback_lower = feedback.lower()
        
        tag_mapping = {
            "clear_structure": ["구조", "정리", "체계", "clear", "structured"],
            "concise": ["짧게", "간결", "요약", "concise", "brief"],
            "plain_language": ["쉽게", "간단", "평이", "plain", "simple"],
            "practical": ["실용", "실제", "적용", "practical", "useful"],
            "detailed": ["자세히", "상세", "세부", "detailed", "thorough"],
            "step_by_step": ["단계", "순서", "절차", "step", "procedure"]
        }
        
        for tag, keywords in tag_mapping.items():
            for keyword in keywords:
                if keyword in feedback_lower:
                    tags.append(tag)
                    break
        
        return tags
    
    def _extract_negative_tags(self, feedback: str) -> List[str]:
        """부정 피드백에서 태그 추출"""
        tags = []
        feedback_lower = feedback.lower()
        
        negative_mapping = {
            "too_long": ["너무 길", "장황", "길게", "too long", "verbose"],
            "too_complex": ["어렵", "복잡", "난해", "complex", "complicated"],
            "missing_core": ["핵심 없", "중심 없", "요점 없", "missing core", "off topic"],
            "needs_table": ["표로", "테이블", "표 형식", "table", "tabular"],
            "needs_bullets": ["불렛", "목록", "항목", "bullet", "list"],
            "needs_examples": ["예시", "사례", "보여줘", "example", "demonstrate"]
        }
        
        for tag, keywords in negative_mapping.items():
            for keyword in keywords:
                if keyword in feedback_lower:
                    tags.append(tag)
                    break
        
        return tags
    
    def _extract_preferences_from_feedback(self, feedback: str, invert: bool = False) -> Dict[str, str]:
        """피드백에서 선호도 슬롯 값 추출"""
        preferences = {}
        feedback_lower = feedback.lower()
        
        # 답변 길이
        if any(kw in feedback_lower for kw in ["짧게", "짧은", "간결", "short", "brief"]):
            preferences[PreferenceSlot.ANSWER_LENGTH.value] = "short" if not invert else "long"
        elif any(kw in feedback_lower for kw in ["길게", "자세히", "상세", "long", "detailed"]):
            preferences[PreferenceSlot.ANSWER_LENGTH.value] = "long" if not invert else "short"
        
        # 톤
        if any(kw in feedback_lower for kw in ["간결", "직접", "concise", "direct"]):
            preferences[PreferenceSlot.TONE.value] = "concise" if not invert else "warm"
        elif any(kw in feedback_lower for kw in ["따뜻", "친절", "warm", "friendly"]):
            preferences[PreferenceSlot.TONE.value] = "warm" if not invert else "concise"
        
        # 구조
        if any(kw in feedback_lower for kw in ["단계별", "순서", "step", "procedure"]):
            preferences[PreferenceSlot.STRUCTURE.value] = "step_by_step" if not invert else "plain"
        elif any(kw in feedback_lower for kw in ["비교", "대조", "compare", "contrast"]):
            preferences[PreferenceSlot.STRUCTURE.value] = "compare" if not invert else "plain"
        
        # 기술 깊이
        if any(kw in feedback_lower for kw in ["쉽게", "간단", "simple", "easy"]):
            preferences[PreferenceSlot.TECHNICAL_DEPTH.value] = "low" if not invert else "high"
        elif any(kw in feedback_lower for kw in ["기술", "심층", "technical", "deep"]):
            preferences[PreferenceSlot.TECHNICAL_DEPTH.value] = "high" if not invert else "low"
        
        # 형식
        if any(kw in feedback_lower for kw in ["표", "테이블", "table", "tabular"]):
            preferences[PreferenceSlot.FORMAT.value] = "table" if not invert else "paragraph"
        elif any(kw in feedback_lower for kw in ["목록", "불렛", "bullet", "list"]):
            preferences[PreferenceSlot.FORMAT.value] = "bullets" if not invert else "paragraph"
        
        return preferences
    
    def get_avoidance_tags(self, user_id: str, project_id: Optional[str] = None) -> List[str]:
        """회피해야 할 태그 목록 조회"""
        tags = memory_store.get_negative_tags(user_id, limit=20, project_id=project_id)
        return [tag.tag for tag in tags]
    
    def get_positive_examples_text(self, user_id: str, limit: int = 2,
                                   project_id: Optional[str] = None) -> List[str]:
        """긍정 예시 텍스트 조회"""
        examples = memory_store.get_positive_examples(user_id, limit, project_id)
        return [example.example_text for example in examples]


# 전역 정책 엔진 인스턴스
policy_engine = PolicyEngine()