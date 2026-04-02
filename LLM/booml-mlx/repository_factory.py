#!/usr/bin/env python3
"""저장소 팩토리 및 선택 메커니즘
- PostgreSQL을 기본 프로덕션 백엔드로 사용
- SQLite는 로컬/개발/테스트용 폴백
- 환경 변수 또는 설정 파일 기반 선택
"""

import os
import logging
from typing import Optional
from memory_store import MemoryRepository, SQLiteMemoryRepository

logger = logging.getLogger(__name__)


class RepositoryFactory:
    """저장소 팩토리 클래스"""
    
    @staticmethod
    def create_repository(config_path: Optional[str] = None) -> MemoryRepository:
        """저장소 생성 (환경 변수 또는 설정 파일 기반)
        
        우선순위:
        1. 환경 변수 BOOML_DB_BACKEND
        2. 설정 파일 (config_path)
        3. 기본값: PostgreSQL 시도 후 실패 시 SQLite 폴백
        
        Args:
            config_path: 설정 파일 경로 (선택사항)
            
        Returns:
            MemoryRepository 인스턴스
        """
        # 환경 변수 확인
        backend = os.getenv("BOOML_DB_BACKEND", "").lower().strip()
        
        # 설정 파일 확인 (간단한 구현)
        config = RepositoryFactory._load_config(config_path)
        if not backend and config:
            backend = config.get("db_backend", "").lower().strip()
        
        # 백엔드 선택
        if backend == "postgresql":
            logger.info("PostgreSQL 백엔드 선택됨")
            return RepositoryFactory._create_postgres_repository()
        elif backend == "sqlite":
            logger.info("SQLite 백엔드 선택됨 (명시적)")
            return RepositoryFactory._create_sqlite_repository()
        else:
            # 기본: PostgreSQL 시도 후 SQLite 폴백
            logger.info("백엔드 명시적 선택 없음, PostgreSQL 시도 후 SQLite 폴백")
            return RepositoryFactory._create_default_repository()
    
    @staticmethod
    def _load_config(config_path: Optional[str]) -> dict:
        """설정 파일 로드 (간단한 JSON 구현)"""
        if not config_path or not os.path.exists(config_path):
            return {}
        
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"설정 파일 로드 실패: {e}")
            return {}
    
    @staticmethod
    def _create_postgres_repository() -> MemoryRepository:
        """PostgreSQL 저장소 생성"""
        try:
            from postgres_repository import create_postgres_repository
            return create_postgres_repository()
        except ImportError as e:
            logger.error(f"PostgreSQL 저장소 생성 실패: {e}")
            logger.warning("PostgreSQL 클라이언트 라이브러리(psycopg2)가 설치되지 않았습니다.")
            logger.warning("설치: pip install psycopg2-binary")
            logger.info("SQLite로 폴백합니다.")
            return RepositoryFactory._create_sqlite_repository()
        except Exception as e:
            logger.error(f"PostgreSQL 저장소 초기화 실패: {e}")
            logger.warning("PostgreSQL 연결에 실패했습니다. SQLite로 폴백합니다.")
            return RepositoryFactory._create_sqlite_repository()
    
    @staticmethod
    def _create_sqlite_repository() -> MemoryRepository:
        """SQLite 저장소 생성"""
        try:
            # SQLite 저장소는 항상 사용 가능
            db_path = os.getenv("BOOML_SQLITE_PATH", "booml_memory.db")
            logger.info(f"SQLite 저장소 생성: {db_path}")
            return SQLiteMemoryRepository(db_path)
        except Exception as e:
            logger.error(f"SQLite 저장소 생성 실패: {e}")
            raise
    
    @staticmethod
    def _create_default_repository() -> MemoryRepository:
        """기본 저장소 생성 (PostgreSQL 시도 후 SQLite 폴백)"""
        # PostgreSQL 먼저 시도
        try:
            from postgres_repository import create_postgres_repository
            repo = create_postgres_repository()
            logger.info("PostgreSQL 저장소 생성 성공 (기본 백엔드)")
            return repo
        except ImportError:
            logger.info("PostgreSQL 클라이언트 라이브러리 없음, SQLite 사용")
        except Exception as e:
            logger.warning(f"PostgreSQL 저장소 생성 실패, SQLite로 폴백: {e}")
        
        # SQLite 폴백
        return RepositoryFactory._create_sqlite_repository()


# 전역 저장소 인스턴스 (애플리케이션 전체에서 사용)
def get_memory_store(config_path: Optional[str] = None) -> MemoryRepository:
    """전역 메모리 저장소 인스턴스 획득
    
    이 함수는 애플리케이션 전체에서 일관된 저장소 인스턴스를 제공합니다.
    PostgreSQL이 사용 가능하면 PostgreSQL을, 그렇지 않으면 SQLite를 사용합니다.
    
    Args:
        config_path: 설정 파일 경로 (선택사항)
        
    Returns:
        MemoryRepository 인스턴스
    """
    # 싱글톤 패턴 (필요 시)
    if not hasattr(get_memory_store, "_instance"):
        get_memory_store._instance = RepositoryFactory.create_repository(config_path)
    
    return get_memory_store._instance


# 설정 파일 예제 생성 함수
def create_example_config(config_path: str = "booml_config.json"):
    """설정 파일 예제 생성"""
    config = {
        "db_backend": "postgresql",  # 또는 "sqlite"
        "postgresql": {
            "url": "postgresql://postgres:postgres@localhost:5432/booml",
            "pool_min": 1,
            "pool_max": 10
        },
        "sqlite": {
            "path": "booml_memory.db"
        },
        "model_routing": {
            "default_strategy": "quality",
            "available_strategies": ["default", "fast", "quality"]
        }
    }
    
    try:
        import json
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"설정 파일 예제 생성됨: {config_path}")
        return True
    except Exception as e:
        logger.error(f"설정 파일 생성 실패: {e}")
        return False


if __name__ == "__main__":
    # 테스트 실행
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 저장소 팩토리 테스트")
    print("-" * 40)
    
    # 1. 기본 저장소 생성 테스트
    print("1. 기본 저장소 생성 테스트...")
    try:
        repo = RepositoryFactory.create_repository()
        print(f"   ✅ 저장소 생성 성공: {type(repo).__name__}")
        
        # 간단한 기능 테스트
        from memory_store import ConversationTurn
        test_turn = ConversationTurn(
            conversation_id="test_factory",
            user_id="test_user",
            role="user",
            content="테스트 메시지"
        )
        turn_id = repo.save_conversation_turn(test_turn)
        print(f"   ✅ 대화 턴 저장 테스트: ID={turn_id}")
        
        turns = repo.get_conversation_turns("test_user", limit=1)
        print(f"   ✅ 대화 턴 조회 테스트: {len(turns)}개 발견")
        
    except Exception as e:
        print(f"   ❌ 저장소 생성 실패: {e}")
    
    # 2. 환경 변수 기반 선택 테스트
    print("\n2. 환경 변수 기반 선택 테스트...")
    os.environ["BOOML_DB_BACKEND"] = "sqlite"
    try:
        repo2 = RepositoryFactory.create_repository()
        print(f"   ✅ SQLite 저장소 생성 성공: {type(repo2).__name__}")
    except Exception as e:
        print(f"   ❌ SQLite 저장소 생성 실패: {e}")
    
    # 3. 설정 파일 예제 생성
    print("\n3. 설정 파일 예제 생성...")
    if create_example_config():
        print("   ✅ 설정 파일 예제 생성 완료: booml_config.json")
    else:
        print("   ❌ 설정 파일 예제 생성 실패")
    
    print("\n" + "=" * 40)
    print("저장소 팩토리 테스트 완료")
    print("=" * 40)