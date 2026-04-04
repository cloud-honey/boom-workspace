#!/usr/bin/env python3
"""붐엘(BoomL) API 서버 테스트"""

import asyncio
import httpx
import json
import time

async def test_server():
    """API 서버 테스트"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=== 붐엘(BoomL) API 서버 테스트 ===")
        
        # 1. 루트 엔드포인트 테스트
        print("\n1. 루트 엔드포인트 테스트")
        try:
            response = await client.get(f"{base_url}/")
            print(f"상태 코드: {response.status_code}")
            print(f"응답: {response.json()}")
        except Exception as e:
            print(f"실패: {e}")
            return False
        
        # 2. 헬스 체크 테스트
        print("\n2. 헬스 체크 테스트")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"상태 코드: {response.status_code}")
            health_data = response.json()
            print(f"상태: {health_data['status']}")
            print(f"모델 로드: {health_data['model_loaded']}")
        except Exception as e:
            print(f"실패: {e}")
            return False
        
        # 3. 모델 목록 테스트
        print("\n3. 모델 목록 테스트")
        try:
            response = await client.get(f"{base_url}/v1/models")
            print(f"상태 코드: {response.status_code}")
            print(f"모델 목록: {response.json()}")
        except Exception as e:
            print(f"실패: {e}")
        
        # 4. 채팅 완성 테스트
        print("\n4. 채팅 완성 테스트")
        try:
            chat_request = {
                "model": "booml-mlx",
                "messages": [
                    {"role": "system", "content": "You are BoomL, a helpful AI assistant."},
                    {"role": "user", "content": "What is the capital of France?"}
                ],
                "max_tokens": 100,
                "temperature": 0.7
            }
            
            start_time = time.time()
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json=chat_request,
                timeout=60.0
            )
            response_time = time.time() - start_time
            
            print(f"상태 코드: {response.status_code}")
            print(f"응답 시간: {response_time:.2f}초")
            
            if response.status_code == 200:
                result = response.json()
                print(f"모델: {result['model']}")
                print(f"응답: {result['choices'][0]['message']['content']}")
                print(f"토큰 사용량: {result['usage']}")
            else:
                print(f"응답: {response.text}")
                
        except Exception as e:
            print(f"실패: {e}")
            return False
        
        # 5. 성능 테스트
        print("\n5. 성능 테스트 (간단한 질문)")
        try:
            test_prompts = [
                "Hello, how are you?",
                "What is machine learning?",
                "Explain Python in one sentence.",
                "What is Apple's M4 Pro chip?",
                "Tell me about MLX framework."
            ]
            
            for i, prompt in enumerate(test_prompts[:2]):  # 처음 2개만 테스트
                chat_request = {
                    "model": "booml-mlx",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 50,
                    "temperature": 0.7
                }
                
                start_time = time.time()
                response = await client.post(
                    f"{base_url}/v1/chat/completions",
                    json=chat_request,
                    timeout=30.0
                )
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    tokens = result['usage']['total_tokens']
                    tps = tokens / response_time if response_time > 0 else 0
                    
                    print(f"\n질문 {i+1}: {prompt}")
                    print(f"응답 시간: {response_time:.2f}초")
                    print(f"토큰 수: {tokens}")
                    print(f"토큰 속도: {tps:.1f} tokens/s")
                else:
                    print(f"\n질문 {i+1} 실패: {response.status_code}")
        
        except Exception as e:
            print(f"성능 테스트 실패: {e}")
        
        return True

async def main():
    """메인 함수"""
    print("붐엘(BoomL) API 서버 테스트 시작")
    print("=" * 60)
    
    # 서버가 실행 중인지 확인
    print("서버 연결 테스트 중...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/")
            print(f"서버 응답: {response.status_code}")
            
            # 테스트 실행
            success = await test_server()
            
            if success:
                print("\n" + "=" * 60)
                print("✅ 모든 테스트 통과!")
                print("\nOpenClaw 통합을 위한 설정:")
                print("""
openclaw.json에 다음을 추가:
{
  "agents": {
    "booml": {
      "model": "custom:mlx",
      "endpoint": "http://localhost:8000/v1/chat/completions",
      "apiKey": "not-required"
    }
  }
}
                """)
            else:
                print("\n⚠️ 일부 테스트 실패")
                
    except httpx.ConnectError:
        print("\n❌ 서버에 연결할 수 없습니다.")
        print("서버를 먼저 실행해주세요:")
        print("cd /Users/sykim/.openclaw/workspace/booml-mlx")
        print("source venv/bin/activate")
        print("python3 server.py")
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())