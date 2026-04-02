#!/usr/bin/env python3
"""붐엘 메모리 저장소 추상화 계층
- Phase 1-2 구현: 파일 기반 저장소 (PostgreSQL 교체 가능 구조)
- 저장 대상: 대화, 세션 요약, 사용자 프로필, 긍정 예시, 부정 태그, 피드백 이벤트
"""

import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class ProfileScope(Enum):
    GLOBAL = "global"
    PROJECT = "project"
    SESSION = "session"


class FeedbackType(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    IMPLICIT = "implicit"


@dataclass
class ConversationTurn:
    """대화 턴 저장 모델"""
    id: Optional[int] = None
    conversation_id: str = ""
    user_id: str = ""
    role: str = ""  # "user" or "assistant"
    content: str = ""
    timestamp: datetime = None
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(KST)
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SessionSummary:
    """세션 요약 저장 모델"""
    id: Optional[int] = None
    session_id: str = ""
    user_id: str = ""
    summary: str = ""
    created_at: datetime = None
    updated_at: datetime = None
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        now = datetime.now(KST)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if self.metadata is None:
            self.metadata = {}


@dataclass
class UserProfile:
    """사용자 프로필 저장 모델"""
    id: Optional[int] = None
    user_id: str = ""
    scope: str = ProfileScope.GLOBAL.value
    profile_data: Dict[str, Any] = None
    confidence: float = 0.0
    created_at: datetime = None
    updated_at: datetime = None
    project_id: Optional[str] = None
    
    def __post_init__(self):
        now = datetime.now(KST)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if self.profile_data is None:
            self.profile_data = {
                "answer_length": "medium",
                "tone": "plain",
                "structure": "step_by_step",
                "technical_depth": "low",
                "format": "markdown"
            }


@dataclass
class PositiveExample:
    """긍정 예시 저장 모델"""
    id: Optional[int] = None
    user_id: str = ""
    example_text: str = ""
    tags: List[str] = None
    context: str = ""
    created_at: datetime = None
    project_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(KST)
        if self.tags is None:
            self.tags = []


@dataclass
class NegativeTag:
    """부정 태그 저장 모델"""
    id: Optional[int] = None
    user_id: str = ""
    tag: str = ""
    context: str = ""
    created_at: datetime = None
    project_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(KST)


@dataclass
class FeedbackEvent:
    """피드백 이벤트 저장 모델"""
    id: Optional[int] = None
    user_id: str = ""
    feedback_type: str = FeedbackType.POSITIVE.value
    content: str = ""
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    project_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(KST)
        if self.metadata is None:
            self.metadata = {}


class MemoryRepository:
    """메모리 저장소 추상화 인터페이스"""
    
    def save_conversation_turn(self, turn: ConversationTurn) -> int:
        """대화 턴 저장"""
        raise NotImplementedError
    
    def get_conversation_turns(self, user_id: str, limit: int = 50, 
                               project_id: Optional[str] = None) -> List[ConversationTurn]:
        """사용자 대화 턴 조회"""
        raise NotImplementedError
    
    def save_session_summary(self, summary: SessionSummary) -> int:
        """세션 요약 저장"""
        raise NotImplementedError
    
    def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        """세션 요약 조회"""
        raise NotImplementedError
    
    def save_user_profile(self, profile: UserProfile) -> int:
        """사용자 프로필 저장"""
        raise NotImplementedError
    
    def get_user_profile(self, user_id: str, scope: str = ProfileScope.GLOBAL.value,
                         project_id: Optional[str] = None) -> Optional[UserProfile]:
        """사용자 프로필 조회"""
        raise NotImplementedError
    
    def save_positive_example(self, example: PositiveExample) -> int:
        """긍정 예시 저장"""
        raise NotImplementedError
    
    def get_positive_examples(self, user_id: str, limit: int = 10,
                              project_id: Optional[str] = None) -> List[PositiveExample]:
        """긍정 예시 조회"""
        raise NotImplementedError
    
    def save_negative_tag(self, tag: NegativeTag) -> int:
        """부정 태그 저장"""
        raise NotImplementedError
    
    def get_negative_tags(self, user_id: str, limit: int = 10,
                          project_id: Optional[str] = None) -> List[NegativeTag]:
        """부정 태그 조회"""
        raise NotImplementedError
    
    def save_feedback_event(self, event: FeedbackEvent) -> int:
        """피드백 이벤트 저장"""
        raise NotImplementedError
    
    def get_feedback_events(self, user_id: str, limit: int = 20,
                            project_id: Optional[str] = None) -> List[FeedbackEvent]:
        """피드백 이벤트 조회"""
        raise NotImplementedError
    
    def search_conversations(self, user_id: str, query: str, limit: int = 5,
                             project_id: Optional[str] = None) -> List[ConversationTurn]:
        """대화 검색 (키워드 + 최근성)"""
        raise NotImplementedError


class SQLiteMemoryRepository(MemoryRepository):
    """SQLite 기반 메모리 저장소 구현"""
    
    def __init__(self, db_path: str = "booml_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 대화 턴 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                project_id TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 세션 요약 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                project_id TEXT,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES conversation_turns(conversation_id)
            )
        """)
        
        # 사용자 프로필 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                profile_data TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                project_id TEXT,
                UNIQUE(user_id, scope, project_id)
            )
        """)
        
        # 긍정 예시 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positive_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                example_text TEXT NOT NULL,
                tags TEXT,
                context TEXT,
                created_at DATETIME NOT NULL,
                project_id TEXT
            )
        """)
        
        # 부정 태그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS negative_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                context TEXT,
                created_at DATETIME NOT NULL,
                project_id TEXT
            )
        """)
        
        # 피드백 이벤트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at DATETIME NOT NULL,
                project_id TEXT
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_turns(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_timestamp ON conversation_turns(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversation_project ON conversation_turns(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON session_summaries(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile_user_scope ON user_profiles(user_id, scope)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positive_user ON positive_examples(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_negative_user ON negative_tags(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_events(user_id)")
        
        conn.commit()
        conn.close()
    
    def _dict_to_json(self, data: Dict) -> str:
        """딕셔너리를 JSON 문자열로 변환"""
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def _json_to_dict(self, json_str: str) -> Dict:
        """JSON 문자열을 딕셔너리로 변환"""
        if not json_str:
            return {}
        return json.loads(json_str)
    
    def save_conversation_turn(self, turn: ConversationTurn) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversation_turns 
            (conversation_id, user_id, role, content, timestamp, project_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            turn.conversation_id,
            turn.user_id,
            turn.role,
            turn.content,
            turn.timestamp.isoformat(),
            turn.project_id,
            self._dict_to_json(turn.metadata)
        ))
        
        turn_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return turn_id
    
    def get_conversation_turns(self, user_id: str, limit: int = 50, 
                               project_id: Optional[str] = None) -> List[ConversationTurn]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT * FROM conversation_turns 
                WHERE user_id = ? AND project_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (user_id, project_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM conversation_turns 
                WHERE user_id = ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (user_id, limit))
        
        turns = []
        for row in cursor.fetchall():
            turn = ConversationTurn(
                id=row['id'],
                conversation_id=row['conversation_id'],
                user_id=row['user_id'],
                role=row['role'],
                content=row['content'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                project_id=row['project_id'],
                metadata=self._json_to_dict(row['metadata'])
            )
            turns.append(turn)
        
        conn.close()
        return turns
    
    def save_session_summary(self, summary: SessionSummary) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # UPSERT 처리
        cursor.execute("""
            INSERT OR REPLACE INTO session_summaries 
            (session_id, user_id, summary, created_at, updated_at, project_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.session_id,
            summary.user_id,
            summary.summary,
            summary.created_at.isoformat(),
            summary.updated_at.isoformat(),
            summary.project_id,
            self._dict_to_json(summary.metadata)
        ))
        
        # ID 조회
        cursor.execute("SELECT id FROM session_summaries WHERE session_id = ?", (summary.session_id,))
        row = cursor.fetchone()
        summary_id = row[0] if row else cursor.lastrowid
        
        conn.commit()
        conn.close()
        return summary_id
    
    def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM session_summaries WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return SessionSummary(
            id=row['id'],
            session_id=row['session_id'],
            user_id=row['user_id'],
            summary=row['summary'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            project_id=row['project_id'],
            metadata=self._json_to_dict(row['metadata'])
        )
    
    def save_user_profile(self, profile: UserProfile) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # UPSERT 처리
        cursor.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_id, scope, profile_data, confidence, created_at, updated_at, project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.user_id,
            profile.scope,
            self._dict_to_json(profile.profile_data),
            profile.confidence,
            profile.created_at.isoformat(),
            profile.updated_at.isoformat(),
            profile.project_id
        ))
        
        # ID 조회
        cursor.execute("SELECT id FROM user_profiles WHERE user_id = ? AND scope = ? AND project_id = ?",
                      (profile.user_id, profile.scope, profile.project_id))
        row = cursor.fetchone()
        profile_id = row[0] if row else cursor.lastrowid
        
        conn.commit()
        conn.close()
        return profile_id
    
    def get_user_profile(self, user_id: str, scope: str = ProfileScope.GLOBAL.value,
                         project_id: Optional[str] = None) -> Optional[UserProfile]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM user_profiles 
            WHERE user_id = ? AND scope = ? AND project_id = ?
            ORDER BY updated_at DESC LIMIT 1
        """, (user_id, scope, project_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return UserProfile(
            id=row['id'],
            user_id=row['user_id'],
            scope=row['scope'],
            profile_data=self._json_to_dict(row['profile_data']),
            confidence=row['confidence'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            project_id=row['project_id']
        )
    
    def save_positive_example(self, example: PositiveExample) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO positive_examples 
            (user_id, example_text, tags, context, created_at, project_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            example.user_id,
            example.example_text,
            json.dumps(example.tags),
            example.context,
            example.created_at.isoformat(),
            example.project_id
        ))
        
        example_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return example_id
    
    def get_positive_examples(self, user_id: str, limit: int = 10,
                              project_id: Optional[str] = None) -> List[PositiveExample]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT * FROM positive_examples 
                WHERE user_id = ? AND project_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, project_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM positive_examples 
                WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        
        examples = []
        for row in cursor.fetchall():
            example = PositiveExample(
                id=row['id'],
                user_id=row['user_id'],
                example_text=row['example_text'],
                tags=json.loads(row['tags']) if row['tags'] else [],
                context=row['context'],
                created_at=datetime.fromisoformat(row['created_at']),
                project_id=row['project_id']
            )
            examples.append(example)
        
        conn.close()
        return examples
    
    def save_negative_tag(self, tag: NegativeTag) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO negative_tags 
            (user_id, tag, context, created_at, project_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            tag.user_id,
            tag.tag,
            tag.context,
            tag.created_at.isoformat(),
            tag.project_id
        ))
        
        tag_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return tag_id
    
    def get_negative_tags(self, user_id: str, limit: int = 10,
                          project_id: Optional[str] = None) -> List[NegativeTag]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT * FROM negative_tags 
                WHERE user_id = ? AND project_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, project_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM negative_tags 
                WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        
        tags = []
        for row in cursor.fetchall():
            tag = NegativeTag(
                id=row['id'],
                user_id=row['user_id'],
                tag=row['tag'],
                context=row['context'],
                created_at=datetime.fromisoformat(row['created_at']),
                project_id=row['project_id']
            )
            tags.append(tag)
        
        conn.close()
        return tags
    
    def save_feedback_event(self, event: FeedbackEvent) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO feedback_events 
            (user_id, feedback_type, content, metadata, created_at, project_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.user_id,
            event.feedback_type,
            event.content,
            self._dict_to_json(event.metadata),
            event.created_at.isoformat(),
            event.project_id
        ))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id
    
    def get_feedback_events(self, user_id: str, limit: int = 20,
                            project_id: Optional[str] = None) -> List[FeedbackEvent]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT * FROM feedback_events 
                WHERE user_id = ? AND project_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, project_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM feedback_events 
                WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
        
        events = []
        for row in cursor.fetchall():
            event = FeedbackEvent(
                id=row['id'],
                user_id=row['user_id'],
                feedback_type=row['feedback_type'],
                content=row['content'],
                metadata=self._json_to_dict(row['metadata']),
                created_at=datetime.fromisoformat(row['created_at']),
                project_id=row['project_id']
            )
            events.append(event)
        
        conn.close()
        return events
    
    def search_conversations(self, user_id: str, query: str, limit: int = 5,
                             project_id: Optional[str] = None) -> List[ConversationTurn]:
        """간단한 키워드 검색 + 최근성 가중치"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 키워드 검색 (LIKE 기반)
        keywords = query.lower().split()
        
        if project_id:
            base_query = """
                SELECT * FROM conversation_turns 
                WHERE user_id = ? AND project_id = ? AND role = 'assistant'
            """
            params = [user_id, project_id]
        else:
            base_query = """
                SELECT * FROM conversation_turns 
                WHERE user_id = ? AND role = 'assistant'
            """
            params = [user_id]
        
        # 키워드 조건 추가
        keyword_conditions = []
        for keyword in keywords:
            if len(keyword) > 2:  # 2글자 이상만 검색
                keyword_conditions.append("content LIKE ?")
                params.append(f"%{keyword}%")
        
        if keyword_conditions:
            base_query += " AND (" + " OR ".join(keyword_conditions) + ")"
        
        # 최근성 가중치를 위해 최근 순 정렬
        base_query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit * 3)  # 더 많이 가져와서 필터링
        
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        conn.close()
        
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
            timestamp = datetime.fromisoformat(row['timestamp'])
            days_ago = (datetime.now(KST) - timestamp).days
            if days_ago <= 7:
                score += 1
            
            if score > 0:
                turn = ConversationTurn(
                    id=row['id'],
                    conversation_id=row['conversation_id'],
                    user_id=row['user_id'],
                    role=row['role'],
                    content=row['content'],
                    timestamp=timestamp,
                    project_id=row['project_id'],
                    metadata=self._json_to_dict(row['metadata'])
                )
                scored_turns.append((score, turn))
        
        # 점수 높은 순 정렬
        scored_turns.sort(key=lambda x: x[0], reverse=True)
        
        # 상위 limit개 반환
        return [turn for _, turn in scored_turns[:limit]]


# 전역 메모리 저장소 인스턴스
memory_store = SQLiteMemoryRepository()