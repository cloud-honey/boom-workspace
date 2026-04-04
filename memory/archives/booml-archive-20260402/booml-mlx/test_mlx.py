#!/usr/bin/env python3
"""MLX 기본 테스트 스크립트"""

import mlx.core as mx
import mlx.nn as nn
import time

def test_basic_operations():
    """기본 MLX 연산 테스트"""
    print("=== MLX 기본 연산 테스트 ===")
    
    # 간단한 텐서 연산
    a = mx.array([1.0, 2.0, 3.0, 4.0])
    b = mx.array([5.0, 6.0, 7.0, 8.0])
    
    print(f"a = {a}")
    print(f"b = {b}")
    print(f"a + b = {a + b}")
    print(f"a * b = {a * b}")
    
    # 매트릭스 곱셈
    x = mx.random.uniform(shape=(2, 3))
    y = mx.random.uniform(shape=(3, 2))
    z = mx.matmul(x, y)
    
    print(f"\nMatrix multiplication:")
    print(f"x shape: {x.shape}")
    print(f"y shape: {y.shape}")
    print(f"z shape: {z.shape}")
    
    # GPU 가속 확인
    print(f"\nMLX device: {mx.default_device()}")
    print(f"MLX Metal available: {mx.metal.is_available()}")
    
    return True

def test_neural_network():
    """간단한 신경망 테스트"""
    print("\n=== 간단한 신경망 테스트 ===")
    
    class SimpleNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.linear1 = nn.Linear(10, 20)
            self.linear2 = nn.Linear(20, 5)
            
        def __call__(self, x):
            x = self.linear1(x)
            x = nn.relu(x)
            x = self.linear2(x)
            return x
    
    # 모델 생성
    model = SimpleNN()
    
    # 더미 입력
    x = mx.random.uniform(shape=(1, 10))
    
    # 추론
    start_time = time.time()
    output = model(x)
    inference_time = time.time() - start_time
    
    print(f"Input shape: {x.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Inference time: {inference_time:.4f} seconds")
    
    return True

def test_performance():
    """성능 테스트"""
    print("\n=== 성능 테스트 ===")
    
    # 큰 매트릭스 곱셈 성능 테스트
    size = 1024
    a = mx.random.uniform(shape=(size, size))
    b = mx.random.uniform(shape=(size, size))
    
    # 워밍업
    _ = mx.matmul(a, b)
    mx.eval(_)
    
    # 실제 측정
    iterations = 10
    start_time = time.time()
    
    for i in range(iterations):
        c = mx.matmul(a, b)
        mx.eval(c)
    
    total_time = time.time() - start_time
    avg_time = total_time / iterations
    
    print(f"Matrix size: {size}x{size}")
    print(f"Iterations: {iterations}")
    print(f"Total time: {total_time:.4f} seconds")
    print(f"Average time per matmul: {avg_time:.4f} seconds")
    print(f"GFLOPS (estimated): {(2 * size**3 / avg_time) / 1e9:.2f}")
    
    return True

if __name__ == "__main__":
    print("붐엘(BoomL) MLX 테스트 시작")
    print("=" * 50)
    
    try:
        test_basic_operations()
        test_neural_network()
        test_performance()
        
        print("\n" + "=" * 50)
        print("✅ 모든 테스트 통과! MLX가 정상적으로 작동합니다.")
        print(f"MLX 버전 정보: mlx-lm 패키지 설치 완료")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()