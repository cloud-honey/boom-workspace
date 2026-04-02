#!/usr/bin/env python3
"""PostgreSQL 기반 메모리 저장소 구현
- PostgreSQL을 기본 프로덕션 백엔드로 사용
- SQLite는 로컬/개발/테스트용 폴백
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("psycopg2 패키지가 설치되지 않았습니다. PostgreSQL 기능을 사용할 수 없습니다.")

from memory_store import (
    MemoryRepository, ConversationTurn, SessionSummary, UserProfile,
    ProfileScope, PositiveExample, NegativeTag, FeedbackEvent, KST
)

logger = logging.getLogger(__name__)


class PostgreSQLMemoryRepository(MemoryRepository):
    """PostgreSQL 기반 메모리 저장소 구현"""
    
    def __init__(self, connection_string: Optional[str] = None, 
                 min_connections: int = 1, max_connections: int = 10):
        """PostgreSQL 저장소 초기화
        
        Args:
            connection_string: PostgreSQL 연결 문자열 (예: postgresql://user:pass@host:port/db)
            min_connections: 최소 연결 풀 크기
            max_connections: 최대 연결 풀 크기
        """
        if not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 패키지가 설치되지 않았습니다. 설치: pip install psycopg2-binary")
        
        self.connection_string = connection_string or os.getenv(
            "BOOML_POSTGRES_URL",
            "postgresql://postgres:postgres@localhost:5432/booml"
        )
        self.pool = None
        self._init_pool(min_connections, max_connections)
        self._init_db()
    
    def _init_pool(self, min_conn: int, max_conn: int):
        """연결 풀 초기화"""
        try:
            self.pool = SimpleConnectionPool(
                min_conn, max_conn, self.connection_string
            )
            logger.info(f"PostgreSQL 연결 풀 초기화 완료: {min_conn}-{max_conn} connections")
        except Exception as e:
            logger.error(f"PostgreSQL 연결 풀 초기화 실패: {e}")
            raise
    
    def _get_connection(self):
        """연결 풀에서 연결 가져오기"""
        if not self.pool:
            raise RuntimeError("PostgreSQL 연결 풀이 초기화되지 않았습니다.")
        return self.pool.getconn()
    
    def _return_connection(self, conn):
        """연결 반환"""
        if self.pool:
            self.pool.putconn(conn)
    
    def _init_db(self):
        """데이터베이스 테이블 초기화"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 대화 턴 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id SERIAL PRIMARY KEY,
                        conversation_id VARCHAR(255) NOT NULL,
                        user_id VARCHAR(255) NOT NULL,
                        role VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        project_id VARCHAR(255),
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_conversation_user (user_id),
                        INDEX idx_conversation_timestamp (timestamp),
                        INDEX idx_conversation_project (project_id)
                    )
                """)
                
                # 세션 요약 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS session_summaries (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(255) NOT NULL UNIQUE,
                        user_id VARCHAR(255) NOT NULL,
                        summary TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        project_id VARCHAR(255),
                        metadata JSONB,
                        FOREIGN KEY (session_id) REFERENCES conversation_turns(conversation_id) ON DELETE CASCADE,
                        INDEX idx_session_user (user_id)
                    )
                """)
                
                # 사용자 프로필 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        scope VARCHAR(50) NOT NULL,
                        profile_data JSONB NOT NULL,
                        confidence REAL DEFAULT 0.0,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        project_id VARCHAR(255),
                        UNIQUE(user_id, scope, project_id),
                        INDEX idx_profile_user_scope (user_id, scope)
                    )
                """)
                
                # 긍정 예시 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS positive_examples (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        example_text TEXT NOT NULL,
                        tags JSONB,
                        context TEXT,
                        created_at TIMESTAMPTZ NOT NULL,
                        project_id VARCHAR(255),
                        INDEX idx_positive_user (user_id)
                    )
                """)
                
                # 부정 태그 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS negative_tags (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        tag VARCHAR(255) NOT NULL,
                        context TEXT,
                        created_at TIMESTAMPTZ NOT NULL,
                        project_id VARCHAR(255),
                        INDEX idx_negative_user (user_id)
                    )
                """)
                
                # 피드백 이벤트 테이블
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS feedback_events (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        feedback_type VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMPTZ NOT NULL,
                        project_id VARCHAR(255),
                        INDEX idx_feedback_user (user_id)
                    )
                """)
                
                conn.commit()
                logger.info("PostgreSQL 테이블 초기화 완료")
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL 테이블 초기화 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def save_conversation_turn(self, turn: ConversationTurn) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO conversation_turns 
                    (conversation_id, user_id, role, content, timestamp, project_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    turn.conversation_id,
                    turn.user_id,
                    turn.role,
                    turn.content,
                    turn.timestamp,
                    turn.project_id,
                    json.dumps(turn.metadata) if turn.metadata else None
                ))
                turn_id = cursor.fetchone()[0]
                conn.commit()
                return turn_id
        except Exception as e:
            conn.rollback()
            logger.error(f"대화 턴 저장 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def get_conversation_turns(self, user_id: str, limit: int = 50, 
                               project_id: Optional[str] = None) -> List[ConversationTurn]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if project_id:
                    cursor.execute("""
                        SELECT * FROM conversation_turns 
                        WHERE user_id = %s AND project_id = %s
                        ORDER BY timestamp DESC LIMIT %s
                    """, (user_id, project_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM conversation_turns 
                        WHERE user_id = %s 
                        ORDER BY timestamp DESC LIMIT %s
                    """, (user_id, limit))
                
                turns = []
                for row in cursor.fetchall():
                    turn = ConversationTurn(
                        id=row['id'],
                        conversation_id=row['conversation_id'],
                        user_id=row['user_id'],
                        role=row['role'],
                        content=row['content'],
                        timestamp=row['timestamp'],
                        project_id=row['project_id'],
                        metadata=row['metadata'] if row['metadata'] else {}
                    )
                    turns.append(turn)
                
                return turns
        except Exception as e:
            logger.error(f"대화 턴 조회 실패: {e}")
            return []
        finally:
            self._return_connection(conn)
    
    def save_session_summary(self, summary: SessionSummary) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO session_summaries 
                    (session_id, user_id, summary, created_at, updated_at, project_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    RETURNING id
                """, (
                    summary.session_id,
                    summary.user_id,
                    summary.summary,
                    summary.created_at,
                    summary.updated_at,
                    summary.project_id,
                    json.dumps(summary.metadata) if summary.metadata else None
                ))
                summary_id = cursor.fetchone()[0]
                conn.commit()
                return summary_id
        except Exception as e:
            conn.rollback()
            logger.error(f"세션 요약 저장 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM session_summaries WHERE session_id = %s
                """, (session_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return SessionSummary(
                    id=row['id'],
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    summary=row['summary'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    project_id=row['project_id'],
                    metadata=row['metadata'] if row['metadata'] else {}
                )
        except Exception as e:
            logger.error(f"세션 요약 조회 실패: {e}")
            return None
        finally:
            self._return_connection(conn)
    
    def save_user_profile(self, profile: UserProfile) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user_profiles 
                    (user_id, scope, profile_data, confidence, created_at, updated_at, project_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, scope, project_id) DO UPDATE SET
                        profile_data = EXCLUDED.profile_data,
                        confidence = EXCLUDED.confidence,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                """, (
                    profile.user_id,
                    profile.scope,
                    json.dumps(profile.profile_data),
                    profile.confidence,
                    profile.created_at,
                    profile.updated_at,
                    profile.project_id
                ))
                profile_id = cursor.fetchone()[0]
                conn.commit()
                return profile_id
        except Exception as e:
            conn.rollback()
            logger.error(f"사용자 프로필 저장 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def get_user_profile(self, user_id: str, scope: str = ProfileScope.GLOBAL.value,
                         project_id: Optional[str] = None) -> Optional[UserProfile]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM user_profiles 
                    WHERE user_id = %s AND scope = %s AND project_id = %s
                    ORDER BY updated_at DESC LIMIT 1
                """, (user_id, scope, project_id))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return UserProfile(
                    id=row['id'],
                    user_id=row['user_id'],
                    scope=row['scope'],
                    profile_data=row['profile_data'],
                    confidence=row['confidence'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    project_id=row['project_id']
                )
        except Exception as e:
            logger.error(f"사용자 프로필 조회 실패: {e}")
            return None
        finally:
            self._return_connection(conn)
    
    def save_positive_example(self, example: PositiveExample) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO positive_examples 
                    (user_id, example_text, tags, context, created_at, project_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    example.user_id,
                    example.example_text,
                    json.dumps(example.tags) if example.tags else None,
                    example.context,
                    example.created_at,
                    example.project_id
                ))
                example_id = cursor.fetchone()[0]
                conn.commit()
                return example_id
        except Exception as e:
            conn.rollback()
            logger.error(f"긍정 예시 저장 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def get_positive_examples(self, user_id: str, limit: int = 10,
                              project_id: Optional[str] = None) -> List[PositiveExample]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if project_id:
                    cursor.execute("""
                        SELECT * FROM positive_examples 
                        WHERE user_id = %s AND project_id = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, project_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM positive_examples 
                        WHERE user_id = %s 
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, limit))
                
                examples = []
                for row in cursor.fetchall():
                    example = PositiveExample(
                        id=row['id'],
                        user_id=row['user_id'],
                        example_text=row['example_text'],
                        tags=row['tags'] if row['tags'] else [],
                        context=row['context'],
                        created_at=row['created_at'],
                        project_id=row['project_id']
                    )
                    examples.append(example)
                
                return examples
        except Exception as e:
            logger.error(f"긍정 예시 조회 실패: {e}")
            return []
        finally:
            self._return_connection(conn)
    
    def save_negative_tag(self, tag: NegativeTag) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO negative_tags 
                    (user_id, tag, context, created_at, project_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    tag.user_id,
                    tag.tag,
                    tag.context,
                    tag.created_at,
                    tag.project_id
                ))
                tag_id = cursor.fetchone()[0]
                conn.commit()
                return tag_id
        except Exception as e:
            conn.rollback()
            logger.error(f"부정 태그 저장 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def get_negative_tags(self, user_id: str, limit: int = 10,
                          project_id: Optional[str] = None) -> List[NegativeTag]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if project_id:
                    cursor.execute("""
                        SELECT * FROM negative_tags 
                        WHERE user_id = %s AND project_id = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, project_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM negative_tags 
                        WHERE user_id = %s 
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, limit))
                
                tags = []
                for row in cursor.fetchall():
                    tag = NegativeTag(
                        id=row['id'],
                        user_id=row['user_id'],
                        tag=row['tag'],
                        context=row['context'],
                        created_at=row['created_at'],
                        project_id=row['project_id']
                    )
                    tags.append(tag)
                
                return tags
        except Exception as e:
            logger.error(f"부정 태그 조회 실패: {e}")
            return []
        finally:
            self._return_connection(conn)
    
    def save_feedback_event(self, event: FeedbackEvent) -> int:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO feedback_events 
                    (user_id, feedback_type, content, metadata, created_at, project_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    event.user_id,
                    event.feedback_type,
                    event.content,
                    json.dumps(event.metadata) if event.metadata else None,
                    event.created_at,
                    event.project_id
                ))
                event_id = cursor.fetchone()[0]
                conn.commit()
                return event_id
        except Exception as e:
            conn.rollback()
            logger.error(f"피드백 이벤트 저장 실패: {e}")
            raise
        finally:
            self._return_connection(conn)
    
    def get_feedback_events(self, user_id: str, limit: int = 20,
                            project_id: Optional[str] = None) -> List[FeedbackEvent]:
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if project_id:
                    cursor.execute("""
                        SELECT * FROM feedback_events 
                        WHERE user_id = %s AND project_id = %s
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, project_id, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM feedback_events 
                        WHERE user_id = %s 
                        ORDER BY created_at DESC LIMIT %s
                    """, (user_id, limit))
                
                events = []
                for row in cursor.fetchall():
                    event = FeedbackEvent(
                        id=row['id'],
                        user_id=row['user_id'],
                        feedback_type=row['feedback_type'],
                        content=row['content'],
                        metadata=row['metadata'] if row['metadata'] else {},
                        created_at=row['created_at'],
                        project_id=row['project_id']
                    )
                    events.append(event)
                
                return events
        except Exception as e:
            logger.error(f"피드백 이벤트 조회 실패: {e}")
            return []
        finally:
            self._return_connection(conn)
    
    def search_conversations(self, user_id: str, query: str, limit: int = 5,
                             project_id: Optional[str] = None) -> List[ConversationTurn]:
        """대화 검색 (PostgreSQL의 전체 텍스트 검색 활용)"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # PostgreSQL의 전체 텍스트 검색을 위한 쿼리
                keywords = query.lower().split()
                
                if project_id:
                    base_query = """
                        SELECT * FROM conversation_turns 
                        WHERE user_id = %s AND project_id = %s AND role = 'assistant'
                    """
                    params = [user_id, project_id]
                else:
                    base_query = """
                        SELECT * FROM conversation_turns 
                        WHERE user_id = %s AND role = 'assistant'
                    """
                    params = [user_id]
                
                # 키워드 검색 조건 (ILIKE로 대소문자 구분 없이)
                keyword_conditions = []
                for keyword in keywords:
                    if len(keyword) > 2:
                        keyword_conditions.append("content ILIKE %s")
                        params.append(f"%{keyword}%")
                
                if keyword_conditions:
                    base_query += " AND (" + " OR ".join(keyword_conditions) + ")"
                
                # 최근성 가중치를 위해 최근 순 정렬
                base_query += " ORDER BY timestamp DESC LIMIT %s"
                params.append(limit * 3)
                
                cursor.execute(base_query, params)
                rows = cursor.fetchall()
                
                # 간단한 스코어링: 키워드 매치 + 최근성
                scored_turns = []
                for row in rows:
                    content_lower = row['content'].lower()
                    score = 0
                    
                    # 키워드 매치 점수
                    for keyword in keywords:
                        if keyword in content_lower:
                            score += 1
                    
                    # 최근성 점수 (최근 7일 내면 추가 점수)
                    days_ago = (datetime.now(KST) - row['timestamp']).days
                    if days_ago <= 7:
                        score += 1
                    
                    if score > 0:
                        turn = ConversationTurn(
                            id=row['id'],
                            conversation_id=row['conversation_id'],
                            user_id=row['user_id'],
                            role=row['role'],
                            content=row['content'],
                            timestamp=row['timestamp'],
                            project_id=row['project_id'],
                            metadata=row['metadata'] if row['metadata'] else {}
                        )
                        scored_turns.append((score, turn))
                
                # 점수 높은 순 정렬
                scored_turns.sort(key=lambda x: x[0], reverse=True)
                
                # 상위 limit개 반환
                return [turn for _, turn in scored_turns[:limit]]
        except Exception as e:
            logger.error(f"대화 검색 실패: {e}")
            return []
        finally:
            self._return_connection(conn)
    
    def close(self):
        """연결 풀 종료"""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL 연결 풀 종료")


# PostgreSQL 저장소 팩토리 함수
def create_postgres_repository():
    """PostgreSQL 저장소 생성 (환경 변수 기반)"""
    if not POSTGRES_AVAILABLE:
        raise ImportError("psycopg2 패키지가 설치되지 않았습니다.")
    
    connection_string = os.getenv(
        "BOOML_POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/booml"
    )
    
    return PostgreSQLMemoryRepository(connection_string)