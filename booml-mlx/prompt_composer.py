#!/usr/bin/env python3
"""붐엘 프롬프트 조립기
- 슬롯 기반 프롬프트 조립
- 메모리 검색 통합
- 정책 엔진 연동
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
try:
    from .memory_store import memory_store, ConversationTurn
    from .policy_engine import policy_engine, PreferenceSlot
except ImportError:
    # 독립 실행을 위한 폴백
    from memory_store import memory_store, ConversationTurn
    from policy_engine import policy_engine, PreferenceSlot

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class PromptComposer:
    """프롬프트 조립기: 슬롯 기반 프롬프트 생성"""
    
    def __init__(self):
        self.system_policy_base = """붐엘(BoomL) · 붐(Boom)의 로컬 MLX 버전

📊 실시간 데이터:
{realtime_data}

## 규칙 (절대 준수)
1. 한국어로만 답변 (코드 제외)
2. 핵심만 — 설명/안내문 금지
3. 선택지 없음 — 판단하면 그대로 답변
4. 불확실한 정보는 '모르겠습니다'로 명확히 (추측/뻔한 답 금지)
5. 웹 검색 결과가 있으면 인용하고 없으면 모르겠습니다
6. 개인의견/철학/추측은 답하지 말 것
7. 기술 용어 최소화

## 시간 해석 규칙 (매우 중요)
- 사용자가 시간 표현을 따로 말하지 않으면 기본은 '현재/오늘/지금' 기준으로 해석한다.
- 날씨를 물으면 기본은 오늘 날씨 또는 현재 날씨로 해석한다.
- 주식/지수/환율/코인처럼 시간 민감한 정보도 기본은 현재 기준으로 해석한다.
- '어제/지난주/장마감/종가/시가/전일'처럼 명시한 경우에만 그 시점 기준으로 답한다.
- 현재 시점 데이터가 없으면 전일 종가를 현재처럼 말하지 않는다.
- 최신 시각을 알 수 있으면 답변에 기준 시각을 짧게 포함한다. 예: '14:45 기준'
- 장중이 아니거나 최신 체결가가 없으면 '현재가 없음', '전일 종가 기준', '장마감 기준'처럼 상태를 분명히 말한다.

## '모르겠습니다' 사용처 (필수)
- 사실 확인이 필요한데 검색 결과 없을 때
- 미래 예측 요구할 때 ('내일 BTC 가격' 등)
- 개인의견 요구할 때 ('뭐가 좋아?')
- 훈련 데이터에 없는 최신 정보"""
    
    def compose_prompt(self, user_id: str, user_message: str, 
                       realtime_data: str = "", project_id: Optional[str] = None) -> str:
        """완전한 프롬프트 조립"""
        # 1. 시스템 정책
        system_policy = self.system_policy_base.format(realtime_data=realtime_data)
        
        # 2. 사용자 선호 슬롯
        user_profile = policy_engine.get_user_profile(user_id, project_id)
        preference_section = self._format_preferences(user_profile)
        
        # 3. 현재 프로젝트 특성 (있을 경우)
        project_section = self._format_project_context(project_id) if project_id else ""
        
        # 4. 검색된 관련 기억
        memory_section = self._retrieve_and_format_memory(user_id, user_message, project_id)
        
        # 5. 긍정 예시 (1-2개)
        positive_examples = policy_engine.get_positive_examples_text(user_id, limit=2, project_id=project_id)
        examples_section = self._format_positive_examples(positive_examples)
        
        # 6. 회피 태그
        avoidance_tags = policy_engine.get_avoidance_tags(user_id, project_id)
        avoidance_section = self._format_avoidance_tags(avoidance_tags)
        
        # 7. 현재 질문
        question_section = f"## 현재 질문\n{user_message}"
        
        # 모든 섹션 조립
        prompt_parts = [
            system_policy,
            preference_section,
            project_section,
            memory_section,
            examples_section,
            avoidance_section,
            question_section
        ]
        
        # None이 아닌 부분만 포함
        final_prompt = "\n\n".join(filter(None, prompt_parts))
        
        logger.info(f"프롬프트 조립 완료: user={user_id}, 길이={len(final_prompt)}")
        return final_prompt
    
    def _format_preferences(self, profile: Dict[str, Any]) -> str:
        """사용자 선호도 포맷팅"""
        if not profile:
            return ""
        
        preference_texts = []
        
        # 답변 길이
        length_map = {
            "short": "매우 짧게 (1-2문장)",
            "medium": "보통 (2-3문장)",
            "long": "자세히 (3-5문장)"
        }
        if profile.get(PreferenceSlot.ANSWER_LENGTH.value):
            pref = length_map.get(profile[PreferenceSlot.ANSWER_LENGTH.value], "보통")
            preference_texts.append(f"- 답변 길이: {pref}")
        
        # 톤
        tone_map = {
            "concise": "간결하고 직접적으로",
            "plain": "평이하게",
            "warm": "따뜻하고 친절하게",
            "structured": "구조화되어"
        }
        if profile.get(PreferenceSlot.TONE.value):
            pref = tone_map.get(profile[PreferenceSlot.TONE.value], "평이하게")
            preference_texts.append(f"- 톤: {pref}")
        
        # 구조
        structure_map = {
            "plain": "일반적인 방식으로",
            "step_by_step": "단계별로",
            "compare": "비교하며"
        }
        if profile.get(PreferenceSlot.STRUCTURE.value):
            pref = structure_map.get(profile[PreferenceSlot.STRUCTURE.value], "일반적인 방식으로")
            preference_texts.append(f"- 구조: {pref}")
        
        # 기술 깊이
        depth_map = {
            "low": "기술 용어 최소화",
            "medium": "적당한 기술 수준",
            "high": "기술적으로 심층적으로"
        }
        if profile.get(PreferenceSlot.TECHNICAL_DEPTH.value):
            pref = depth_map.get(profile[PreferenceSlot.TECHNICAL_DEPTH.value], "기술 용어 최소화")
            preference_texts.append(f"- 기술 깊이: {pref}")
        
        # 형식
        format_map = {
            "paragraph": "문단 형식으로",
            "bullets": "불렛 포인트로",
            "markdown": "마크다운 형식으로",
            "table": "표 형식으로"
        }
        if profile.get(PreferenceSlot.FORMAT.value):
            pref = format_map.get(profile[PreferenceSlot.FORMAT.value], "문단 형식으로")
            preference_texts.append(f"- 형식: {pref}")
        
        if not preference_texts:
            return ""
        
        return "## 사용자 선호도\n" + "\n".join(preference_texts)
    
    def _format_project_context(self, project_id: str) -> str:
        """프로젝트 컨텍스트 포맷팅"""
        # 간단한 구현: 프로젝트 ID만 표시
        # 향후 확장 가능
        return f"## 현재 프로젝트\n- 프로젝트: {project_id}\n- 이 프로젝트와 관련된 정보를 우선적으로 참고하세요."
    
    def _retrieve_and_format_memory(self, user_id: str, query: str, 
                                    project_id: Optional[str] = None) -> str:
        """메모리 검색 및 포맷팅"""
        # 관련 대화 검색
        related_turns = memory_store.search_conversations(
            user_id, query, limit=3, project_id=project_id
        )
        
        if not related_turns:
            return ""
        
        memory_lines = ["## 관련 과거 대화"]
        for turn in related_turns:
            # 간단한 요약 (첫 100자)
            preview = turn.content[:100] + "..." if len(turn.content) > 100 else turn.content
            date_str = turn.timestamp.strftime("%m/%d %H:%M")
            memory_lines.append(f"- [{date_str}] {preview}")
        
        return "\n".join(memory_lines)
    
    def _format_positive_examples(self, examples: List[str]) -> str:
        """긍정 예시 포맷팅"""
        if not examples:
            return ""
        
        example_lines = ["## 좋은 답변 예시"]
        for i, example in enumerate(examples, 1):
            # 간단한 요약
            preview = example[:150] + "..." if len(example) > 150 else example
            example_lines.append(f"{i}. {preview}")
        
        return "\n".join(example_lines)
    
    def _format_avoidance_tags(self, tags: List[str]) -> str:
        """회피 태그 포맷팅"""
        if not tags:
            return ""
        
        # 태그 매핑 (사용자 친화적인 설명)
        tag_descriptions = {
            "too_long": "너무 긴 답변",
            "too_complex": "너무 복잡한 설명",
            "missing_core": "핵심 없는 답변",
            "needs_table": "표가 필요한 내용",
            "needs_bullets": "목록 형식이 필요한 내용",
            "needs_examples": "예시가 필요한 설명"
        }
        
        avoidance_lines = ["## 피해야 할 스타일"]
        for tag in tags[:5]:  # 최대 5개
            description = tag_descriptions.get(tag, tag)
            avoidance_lines.append(f"- {description}")
        
        return "\n".join(avoidance_lines)
    
    def create_session_summary(self, user_id: str, conversation_turns: List[Dict],
                               project_id: Optional[str] = None) -> str:
        """세션 요약 생성 (기본 휴리스틱)"""
        if not conversation_turns:
            return "대화 내용 없음"
        
        # 간단한 요약: 주제와 주요 질문 추출
        user_messages = [t for t in conversation_turns if t.get('role') == 'user']
        if not user_messages:
            return "사용자 질문 없음"
        
        # 첫 번째와 마지막 질문으로 요약
        first_q = user_messages[0].get('content', '')[:50]
        last_q = user_messages[-1].get('content', '')[:50] if len(user_messages) > 1 else ""
        
        summary_parts = []
        if first_q:
            summary_parts.append(f"시작: {first_q}")
        if last_q and last_q != first_q:
            summary_parts.append(f"최근: {last_q}")
        
        summary = " | ".join(summary_parts)
        return summary if summary else "다양한 주제 논의"


# 전역 프롬프트 조립기 인스턴스
prompt_composer = PromptComposer()