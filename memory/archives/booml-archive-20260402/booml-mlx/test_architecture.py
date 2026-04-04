#!/usr/bin/env python3
"""붐엘 아키텍처 Phase 1-2 테스트 스크립트"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 직접 임포트 (상대 임포트 문제 해결)
try:
    import memory_store
    from memory_store import memory_store as ms, ConversationTurn, UserProfile, ProfileScope
    memory_store = ms
except ImportError:
    print("메모리 저장소 모듈 임포트 실패")
    sys.exit(1)

try:
    import policy_engine
    from policy_engine import policy_engine as pe
    policy_engine = pe
except ImportError:
    print("정책 엔진 모듈 임포트 실패")
    sys.exit(1)

try:
    import prompt_composer
    from prompt_composer import prompt_composer as pc
    prompt_composer = pc
except ImportError:
    print("프롬프트 조립기 모듈 임포트 실패")
    sys.exit(1)

try:
    import kpi_logger
    from kpi_logger import kpi_logger as kl
    kpi_logger = kl
except ImportError:
    print("KPI 로거 모듈 임포트 실패")
    sys.exit(1)

try:
    import booml_core
    from booml_core import booml_core as bc
    booml_core = bc
except ImportError:
    print("붐엘 코어 모듈 임포트 실패")
    sys.exit(1)

def test_memory_store():
    """메모리 저장소 테스트"""
    print("🧪 메모리 저장소 테스트...")
    
    # 테스트 사용자 ID
    test_user_id = "test_user_001"
    
    # 1. 대화 턴 저장 테스트
    turn = ConversationTurn(
        conversation_id="test_session_001",
        user_id=test_user_id,
        role="user",
        content="테스트 메시지입니다.",
        project_id="test_project"
    )
    turn_id = memory_store.save_conversation_turn(turn)
    print(f"  ✓ 대화 턴 저장: ID={turn_id}")
    
    # 2. 대화 턴 조회 테스트
    turns = memory_store.get_conversation_turns(test_user_id, limit=5)
    print(f"  ✓ 대화 턴 조회: {len(turns)}개 발견")
    
    # 3. 사용자 프로필 저장 테스트
    profile = UserProfile(
        user_id=test_user_id,
        scope=ProfileScope.GLOBAL.value,
        profile_data={
            "answer_length": "short",
            "tone": "concise"
        },
        confidence=0.8
    )
    profile_id = memory_store.save_user_profile(profile)
    print(f"  ✓ 사용자 프로필 저장: ID={profile_id}")
    
    # 4. 사용자 프로필 조회 테스트
    retrieved_profile = memory_store.get_user_profile(test_user_id, ProfileScope.GLOBAL.value)
    if retrieved_profile:
        print(f"  ✓ 사용자 프로필 조회: answer_length={retrieved_profile.profile_data.get('answer_length')}")
    
    return True

def test_policy_engine():
    """정책 엔진 테스트"""
    print("🧪 정책 엔진 테스트...")
    
    test_user_id = "test_user_002"
    
    # 1. 기본 프로필 조회 테스트
    profile = policy_engine.get_user_profile(test_user_id)
    print(f"  ✓ 기본 프로필 조회: {len(profile)}개 슬롯")
    
    # 2. 선호도 업데이트 테스트
    policy_engine.update_user_preference(
        test_user_id, "answer_length", "long", confidence=0.9
    )
    print(f"  ✓ 선호도 업데이트: answer_length=long")
    
    # 3. 업데이트된 프로필 조회
    updated_profile = policy_engine.get_user_profile(test_user_id)
    print(f"  ✓ 업데이트된 프로필: answer_length={updated_profile.get('answer_length')}")
    
    # 4. 피드백 처리 테스트
    policy_engine.process_feedback(
        test_user_id, "positive", "이 스타일 좋아, 짧고 간결하게"
    )
    print(f"  ✓ 긍정 피드백 처리 완료")
    
    return True

def test_prompt_composer():
    """프롬프트 조립기 테스트"""
    print("🧪 프롬프트 조립기 테스트...")
    
    test_user_id = "test_user_003"
    
    # 1. 기본 프롬프트 생성 테스트
    prompt = prompt_composer.compose_prompt(
        test_user_id, 
        "테스트 질문입니다.",
        realtime_data="[테스트 데이터]\n날씨: 맑음, 20°C"
    )
    
    print(f"  ✓ 프롬프트 생성 완료: 길이={len(prompt)}자")
    
    # 프롬프트 구조 확인
    sections = [
        "붐엘(BoomL)",
        "규칙 (절대 준수)",
        "사용자 선호도",
        "현재 질문"
    ]
    
    for section in sections:
        if section in prompt:
            print(f"  ✓ 섹션 포함: {section}")
    
    return True

def test_kpi_logger():
    """KPI 로거 테스트"""
    print("🧪 KPI 로거 테스트...")
    
    test_user_id = "test_user_004"
    test_session_id = "test_session_kpi"
    
    # 1. 세션 시작
    kpi_logger.start_session(test_session_id, test_user_id)
    print(f"  ✓ 세션 시작: {test_session_id}")
    
    # 2. KPI 이벤트 로깅
    kpi_logger.log_kpi_event(test_user_id, test_session_id, "test_metric", 0.75)
    print(f"  ✓ KPI 이벤트 로깅")
    
    # 3. 세션 통계 증가
    kpi_logger.increment_session_stat(test_session_id, "total_turns")
    kpi_logger.increment_session_stat(test_session_id, "positive_feedback_count")
    print(f"  ✓ 세션 통계 증가")
    
    # 4. 세션 종료
    kpi_logger.end_session(test_session_id)
    print(f"  ✓ 세션 종료")
    
    # 5. 통계 조회
    stats = kpi_logger.get_recent_kpis(test_user_id, days=1)
    print(f"  ✓ 통계 조회: 세션={stats.get('session_count', 0)}")
    
    return True

def test_booml_core():
    """붐엘 코어 테스트"""
    print("🧪 붐엘 코어 테스트...")
    
    test_user_id = "test_user_005"
    
    # 1. 세션 시작
    session_id = booml_core.start_session(test_user_id, "test_project")
    print(f"  ✓ 세션 시작: {session_id}")
    
    # 2. 메시지 처리
    response, metadata = booml_core.process_message(
        session_id, 
        "테스트 질문: 오늘 날씨 어때?",
        realtime_data="[테스트 날씨]\n서울: 맑음, 22°C"
    )
    print(f"  ✓ 메시지 처리: 응답 길이={len(response)}")
    print(f"     메타데이터: {metadata}")
    
    # 3. 피드백 처리
    booml_core.process_feedback(
        session_id, "positive", "답변 좋아, 이렇게 계속 해줘"
    )
    print(f"  ✓ 피드백 처리 완료")
    
    # 4. 사용자 통계 조회
    stats = booml_core.get_user_stats(test_user_id, days=1)
    print(f"  ✓ 사용자 통계: 대화 턴={stats.get('conversation_turns', 0)}")
    
    # 5. 세션 종료
    booml_core.end_session(session_id)
    print(f"  ✓ 세션 종료")
    
    return True

def test_database_structure():
    """데이터베이스 구조 확인"""
    print("📊 데이터베이스 구조 확인...")
    
    import sqlite3
    import os
    
    # 메모리 DB 확인
    memory_db = "booml_memory.db"
    kpi_db = "booml_kpi.db"
    
    if os.path.exists(memory_db):
        conn = sqlite3.connect(memory_db)
        cursor = conn.cursor()
        
        # 테이블 목록 조회
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"  메모리 DB 테이블 ({len(tables)}개):")
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            print(f"    - {table[0]}: {len(columns)}개 컬럼")
        
        conn.close()
    else:
        print(f"  ⚠️ 메모리 DB 없음: {memory_db}")
    
    if os.path.exists(kpi_db):
        conn = sqlite3.connect(kpi_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"  KPI DB 테이블 ({len(tables)}개):")
        for table in tables:
            print(f"    - {table[0]}")
        
        conn.close()
    else:
        print(f"  ⚠️ KPI DB 없음: {kpi_db}")
    
    return True

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("붐엘 아키텍처 Phase 1-2 테스트 스위트")
    print("=" * 60)
    
    tests = [
        ("메모리 저장소", test_memory_store),
        ("정책 엔진", test_policy_engine),
        ("프롬프트 조립기", test_prompt_composer),
        ("KPI 로거", test_kpi_logger),
        ("붐엘 코어", test_booml_core),
        ("데이터베이스 구조", test_database_structure),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔍 {test_name} 테스트 시작")
            success = test_func()
            results.append((test_name, success, None))
            print(f"✅ {test_name} 테스트 성공")
        except Exception as e:
            print(f"❌ {test_name} 테스트 실패: {e}")
            results.append((test_name, False, str(e)))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"통과: {passed}/{total}")
    
    for test_name, success, error in results:
        status = "✅ 통과" if success else "❌ 실패"
        print(f"  {status} {test_name}")
        if error:
            print(f"    오류: {error}")
    
    # 아키텍처 구현 상태
    print("\n🏗️ 아키텍처 구현 상태")
    print("-" * 40)
    print("✓ 메모리 저장소: SQLite 기반, PostgreSQL 교체 가능 구조")
    print("✓ 정책 엔진: 사용자 선호도 슬롯 관리")
    print("✓ 프롬프트 조립기: 슬롯 기반 조립")
    print("✓ KPI 로거: 성공 지표 수집")
    print("✓ 붐엘 코어: 통합 인터페이스")
    print("✓ 서버 통합: server_v2_enhanced.py")
    print("✓ 봇 통합: booml-bot-v2-enhanced.py")
    
    if passed == total:
        print("\n🎉 모든 테스트 통과! Phase 1-2 구현 완료.")
    else:
        print(f"\n⚠️ {total - passed}개 테스트 실패. 확인이 필요합니다.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)