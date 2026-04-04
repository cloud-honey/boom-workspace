#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone

# 붐2 세션 파일 경로
sessions_file = "/Users/sykim/.openclaw/agents/boom2/sessions/sessions.json"
backup_file = f"{sessions_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def cleanup_old_sessions(days_threshold=4):
    # 백업 생성
    print(f"📁 백업 생성: {backup_file}")
    with open(sessions_file, 'r') as f:
        data = json.load(f)
    
    with open(backup_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    # 현재 시간 (밀리초)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    
    # N일 전 시간 (밀리초)
    threshold_ms = now_ms - (days_threshold * 24 * 60 * 60 * 1000)
    
    # 정리할 세션 키 목록
    to_delete = []
    to_keep = []
    
    print(f"\n📊 세션 분석 시작 (총 {len(data)}개)")
    print(f"기준 시간: {datetime.fromtimestamp(now_ms/1000).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"삭제 기준: {days_threshold}일 이상 ({datetime.fromtimestamp(threshold_ms/1000).strftime('%Y-%m-%d %H:%M:%S')} 이전)")
    
    for session_key, session_data in data.items():
        updated_at = session_data.get('updatedAt', 0)
        
        # 크론 작업은 무조건 유지
        if 'cron' in session_key:
            to_keep.append(session_key)
            continue
            
        # 직접 세션(telegram:direct)은 유지
        if 'telegram:direct' in session_key:
            to_keep.append(session_key)
            continue
            
        # N일 이상된 세션 체크
        if updated_at < threshold_ms:
            to_delete.append(session_key)
            last_update = datetime.fromtimestamp(updated_at/1000).strftime('%Y-%m-%d %H:%M:%S')
            days_old = (now_ms - updated_at) / (24 * 60 * 60 * 1000)
            print(f"🗑️ 삭제 대상: {session_key[:60]}...")
            print(f"     마지막 업데이트: {last_update} ({days_old:.1f}일 전)")
        else:
            to_keep.append(session_key)
    
    print(f"\n📈 분석 결과:")
    print(f"  총 세션: {len(data)}개")
    print(f"  크론 작업: {len([k for k in data.keys() if 'cron' in k])}개")
    print(f"  직접 세션: {len([k for k in data.keys() if 'telegram:direct' in k])}개")
    print(f"  서브에이전트: {len([k for k in data.keys() if 'subagent' in k])}개")
    print(f"  삭제 대상: {len(to_delete)}개")
    print(f"  유지 대상: {len(to_keep)}개")
    
    # 삭제 실행
    if to_delete:
        print(f"\n🔧 세션 삭제 중...")
        for key in to_delete:
            del data[key]
            print(f"  ✅ 삭제됨: {key[:60]}...")
        
        # 파일 저장
        with open(sessions_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n🎯 {len(to_delete)}개 세션 삭제 완료")
        
        # 삭제된 세션 파일도 정리
        cleanup_session_files(data)
    else:
        print(f"\n🎯 삭제할 세션이 없습니다.")
    
    return len(to_delete)

def cleanup_session_files(remaining_sessions):
    """삭제된 세션의 파일도 정리"""
    sessions_dir = "/Users/sykim/.openclaw/agents/boom2/sessions"
    
    # 남아있는 세션 ID 목록
    remaining_ids = set()
    for session_data in remaining_sessions.values():
        session_id = session_data.get('sessionId')
        if session_id:
            remaining_ids.add(session_id)
    
    # .jsonl 파일 검사
    jsonl_files = [f for f in os.listdir(sessions_dir) if f.endswith('.jsonl')]
    deleted_files = []
    
    print(f"\n📁 세션 파일 정리 중... (총 {len(jsonl_files)}개 파일)")
    
    for filename in jsonl_files:
        file_path = os.path.join(sessions_dir, filename)
        session_id = filename.replace('.jsonl', '')
        
        # 세션 ID가 남아있는 세션에 없으면 삭제
        if session_id not in remaining_ids:
            try:
                os.remove(file_path)
                deleted_files.append(filename)
                print(f"  🗑️ 파일 삭제: {filename}")
            except Exception as e:
                print(f"  ❌ 파일 삭제 실패: {filename} - {e}")
    
    if deleted_files:
        print(f"\n✅ {len(deleted_files)}개 세션 파일 삭제 완료")
    else:
        print(f"\n✅ 삭제할 세션 파일이 없습니다.")

if __name__ == "__main__":
    print("🧹 붐2 오래된 세션 정리 시작")
    print("=" * 60)
    
    # 기준일 수 입력 (기본값: 4일)
    days_threshold = 4
    if len(sys.argv) > 1:
        try:
            days_threshold = int(sys.argv[1])
        except ValueError:
            print(f"⚠️ 잘못된 입력: {sys.argv[1]}, 기본값 4일 사용")
    
    print(f"🗓️ 기준: {days_threshold}일 이상된 세션 삭제")
    
    try:
        deleted_count = cleanup_old_sessions(days_threshold)
        
        if deleted_count > 0:
            print(f"\n🎉 붐2 세션 정리 완료! {deleted_count}개 세션 삭제됨")
            print(f"💾 백업 파일: {backup_file}")
            
            # 현재 세션 수 확인
            with open(sessions_file, 'r') as f:
                current_data = json.load(f)
            print(f"📊 현재 세션 수: {len(current_data)}개")
        else:
            print(f"\n✅ 삭제할 오래된 세션이 없습니다.")
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)