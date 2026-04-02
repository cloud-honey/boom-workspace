#!/usr/bin/env python3
"""붐엘 KPI 로거
- 성공 지표 수집 및 로깅
- Phase 2부터 시작하는 기본 구현
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from enum import Enum
try:
    from .memory_store import memory_store, FeedbackEvent, FeedbackType
except ImportError:
    # 독립 실행을 위한 폴백
    from memory_store import memory_store, FeedbackEvent, FeedbackType

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class KPIMetric(Enum):
    """KPI 지표 정의"""
    POSITIVE_FEEDBACK_RATE = "positive_feedback_rate"
    EDIT_REQUEST_PER_SESSION = "edit_request_per_session"
    STYLE_CORRECTION_RATE = "style_correction_rate"
    RETRY_AFTER_ANSWER_RATE = "retry_after_answer_rate"
    MEMORY_USEFULNESS_SCORE = "memory_usefulness_score"
    SESSION_SUCCESS_RATE = "session_success_rate"
    RESPONSE_REUSE_RATE = "response_reuse_rate"
    PREFERENCE_REFERENCE_RATE = "preference_reference_rate"


class KPILogger:
    """KPI 로거: 성공 지표 수집"""
    
    def __init__(self, db_path: str = "booml_kpi.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """KPI 데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # KPI 이벤트 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kpi_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 세션 통계 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                total_turns INTEGER DEFAULT 0,
                positive_feedback_count INTEGER DEFAULT 0,
                negative_feedback_count INTEGER DEFAULT 0,
                edit_request_count INTEGER DEFAULT 0,
                style_correction_count INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                memory_used_count INTEGER DEFAULT 0,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kpi_user ON kpi_events(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kpi_metric ON kpi_events(metric_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_kpi_time ON kpi_events(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_user ON session_stats(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_time ON session_stats(start_time)")
        
        conn.commit()
        conn.close()
    
    def log_kpi_event(self, user_id: str, session_id: str, metric_name: str, 
                      metric_value: float, metadata: Optional[Dict] = None):
        """KPI 이벤트 로깅"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO kpi_events 
            (user_id, session_id, metric_name, metric_value, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            session_id,
            metric_name,
            metric_value,
            json.dumps(metadata) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        logger.debug(f"KPI 이벤트 로깅: {metric_name}={metric_value} for user={user_id}")
    
    def start_session(self, session_id: str, user_id: str):
        """세션 시작 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO session_stats 
            (session_id, user_id, start_time)
            VALUES (?, ?, ?)
        """, (
            session_id,
            user_id,
            datetime.now(KST).isoformat()
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"세션 시작: {session_id} for user={user_id}")
    
    def end_session(self, session_id: str):
        """세션 종료 기록"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE session_stats 
            SET end_time = ?
            WHERE session_id = ?
        """, (
            datetime.now(KST).isoformat(),
            session_id
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"세션 종료: {session_id}")
    
    def increment_session_stat(self, session_id: str, field: str, increment: int = 1):
        """세션 통계 증가"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 안전한 필드 이름 검증
        valid_fields = [
            'total_turns', 'positive_feedback_count', 'negative_feedback_count',
            'edit_request_count', 'style_correction_count', 'retry_count',
            'memory_used_count'
        ]
        
        if field not in valid_fields:
            logger.warning(f"잘못된 세션 통계 필드: {field}")
            conn.close()
            return
        
        cursor.execute(f"""
            UPDATE session_stats 
            SET {field} = {field} + ?
            WHERE session_id = ?
        """, (increment, session_id))
        
        conn.commit()
        conn.close()
    
    def log_feedback(self, user_id: str, session_id: str, feedback_type: str):
        """피드백 로깅"""
        if feedback_type == FeedbackType.POSITIVE.value:
            self.increment_session_stat(session_id, 'positive_feedback_count')
            self.log_kpi_event(user_id, session_id, 
                             KPIMetric.POSITIVE_FEEDBACK_RATE.value, 1.0)
        elif feedback_type == FeedbackType.NEGATIVE.value:
            self.increment_session_stat(session_id, 'negative_feedback_count')
        elif feedback_type == FeedbackType.IMPLICIT.value:
            # 암묵적 피드백은 스타일 수정으로 간주
            self.increment_session_stat(session_id, 'style_correction_count')
            self.log_kpi_event(user_id, session_id,
                             KPIMetric.STYLE_CORRECTION_RATE.value, 1.0)
    
    def log_edit_request(self, user_id: str, session_id: str):
        """수정 요청 로깅"""
        self.increment_session_stat(session_id, 'edit_request_count')
        self.log_kpi_event(user_id, session_id,
                         KPIMetric.EDIT_REQUEST_PER_SESSION.value, 1.0)
    
    def log_retry(self, user_id: str, session_id: str):
        """재시도 로깅"""
        self.increment_session_stat(session_id, 'retry_count')
        self.log_kpi_event(user_id, session_id,
                         KPIMetric.RETRY_AFTER_ANSWER_RATE.value, 1.0)
    
    def log_memory_usage(self, user_id: str, session_id: str, usefulness_score: float = 0.5):
        """메모리 사용 로깅"""
        self.increment_session_stat(session_id, 'memory_used_count')
        self.log_kpi_event(user_id, session_id,
                         KPIMetric.MEMORY_USEFULNESS_SCORE.value, usefulness_score)
    
    def log_turn_completion(self, user_id: str, session_id: str):
        """턴 완료 로깅"""
        self.increment_session_stat(session_id, 'total_turns')
    
    def calculate_session_success_rate(self, session_id: str) -> float:
        """세션 성공률 계산"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                total_turns,
                positive_feedback_count,
                negative_feedback_count,
                edit_request_count,
                retry_count
            FROM session_stats 
            WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row['total_turns'] == 0:
            return 0.0
        
        total_turns = row['total_turns']
        positive_count = row['positive_feedback_count']
        
        # 부정적 요소 가중치
        negative_score = (
            row['negative_feedback_count'] * 0.5 +
            row['edit_request_count'] * 0.3 +
            row['retry_count'] * 0.2
        )
        
        # 성공률 계산
        success_rate = max(0.0, (positive_count - negative_score) / total_turns)
        return min(1.0, max(0.0, success_rate))
    
    def get_recent_kpis(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """최근 KPI 통계 조회"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        since_date = (datetime.now(KST) - timedelta(days=days)).isoformat()
        
        # 기본 통계
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT session_id) as session_count,
                SUM(total_turns) as total_turns,
                SUM(positive_feedback_count) as positive_feedback,
                SUM(negative_feedback_count) as negative_feedback,
                SUM(edit_request_count) as edit_requests,
                SUM(style_correction_count) as style_corrections,
                SUM(retry_count) as retries
            FROM session_stats 
            WHERE user_id = ? AND start_time >= ?
        """, (user_id, since_date))
        
        stats_row = cursor.fetchone()
        
        # KPI 이벤트 기반 계산
        cursor.execute("""
            SELECT 
                metric_name,
                AVG(metric_value) as avg_value,
                COUNT(*) as count
            FROM kpi_events 
            WHERE user_id = ? AND created_at >= ?
            GROUP BY metric_name
        """, (user_id, since_date))
        
        kpi_rows = cursor.fetchall()
        conn.close()
        
        # 결과 구성
        result = {
            "period_days": days,
            "since_date": since_date,
            "session_count": stats_row['session_count'] if stats_row else 0,
            "total_turns": stats_row['total_turns'] if stats_row else 0,
            "feedback_summary": {
                "positive": stats_row['positive_feedback'] if stats_row else 0,
                "negative": stats_row['negative_feedback'] if stats_row else 0
            },
            "correction_summary": {
                "edit_requests": stats_row['edit_requests'] if stats_row else 0,
                "style_corrections": stats_row['style_corrections'] if stats_row else 0,
                "retries": stats_row['retries'] if stats_row else 0
            }
        }
        
        # KPI 메트릭 추가
        kpi_metrics = {}
        for row in kpi_rows:
            kpi_metrics[row['metric_name']] = {
                "average": row['avg_value'],
                "count": row['count']
            }
        
        result["kpi_metrics"] = kpi_metrics
        
        return result


# 전역 KPI 로거 인스턴스
kpi_logger = KPILogger()