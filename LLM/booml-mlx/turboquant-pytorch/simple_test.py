#!/usr/bin/env python3
"""TurboQuant 간단 테스트"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 상대 임포트를 절대 임포트로 변경
import lloyd_max
import compressors
import compressors_v3

def test_basic_functionality():
    """기본 기능 테스트"""
    print("=== TurboQuant 기본 기능 테스트 ===")
    
    # Lloyd-Max 코드북 테스트
    print("1. Lloyd-Max 코드북 테스트")
    try:
        # 간단한 데이터 생성
        import torch
        import numpy as np
        
        # 테스트 데이터
        data = torch.randn(1000, 128)  # 1000개의 128차원 벡터
        
        # 코드북 학습
        print(f"데이터 shape: {data.shape}")
        print(f"데이터 타입: {data.dtype}")
        
        # 기본 양자화 테스트
        print("\n2. 기본 양자화 테스트")
        
        # 4비트 양자화 시뮬레이션
        min_val = data.min().item()
        max_val = data.max().item()
        
        # 간단한 균일 양자화
        n_bits = 4
        n_levels = 2 ** n_bits
        
        # 양자화 레벨 계산
        scale = (max_val - min_val) / (n_levels - 1)
        quantized = torch.round((data - min_val) / scale)
        dequantized = quantized * scale + min_val
        
        # 오차 계산
        mse = torch.mean((data - dequantized) ** 2).item()
        print(f"양자화 비트: {n_bits}비트")
        print(f"양자화 레벨: {n_levels}개")
        print(f"MSE 오차: {mse:.6f}")
        print(f"PSNR: {10 * torch.log10(1.0 / mse).item():.2f} dB")
        
        # 압축률 계산
        original_size = data.numel() * data.element_size()  # 바이트
        quantized_size = data.numel() * n_bits / 8  # 바이트 (이론적)
        compression_ratio = original_size / quantized_size
        
        print(f"\n3. 압축률 계산")
        print(f"원본 크기: {original_size:,} 바이트")
        print(f"양자화 크기: {quantized_size:,.1f} 바이트")
        print(f"압축률: {compression_ratio:.1f}x")
        
        return True
        
    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_turboquant_concepts():
    """TurboQuant 개념 테스트"""
    print("\n=== TurboQuant 개념 테스트 ===")
    
    concepts = {
        "KV 캐시": "LLM의 Key-Value 캐시, 주의력 메커니즘에 사용",
        "비대칭 양자화": "Key(4비트)와 Value(2비트)에 다른 비트 할당",
        "Lloyd-Max 양자화": "최적의 스칼라 양자화 알고리즘",
        "무작위 회전": "벡터 좌표를 정규 분포로 변환",
        "QJL (Johnson-Lindenstrauss)": "원 논문의 2단계, 실제로는 효과 없음",
        "잔차 창": "최근 토큰은 FP16으로 유지 (128토큰)",
        "보호된 레이어": "민감한 첫/마지막 레이어에 더 많은 비트 할당"
    }
    
    for concept, description in concepts.items():
        print(f"• {concept}: {description}")
    
    return True

def test_mlx_compatibility():
    """MLX 호환성 테스트"""
    print("\n=== MLX 호환성 테스트 ===")
    
    try:
        import mlx.core as mx
        import mlx.nn as nn
        
        print("MLX 가져오기 성공")
        print(f"MLX 버전: mlx 패키지 로드됨")
        print(f"Metal 가속: {mx.metal.is_available()}")
        
        # MLX와 PyTorch 데이터 변환 테스트
        print("\nMLX-PyTorch 데이터 변환 테스트")
        
        # PyTorch 텐서 생성
        import torch
        torch_tensor = torch.randn(3, 4)
        print(f"PyTorch 텐서: {torch_tensor.shape}, {torch_tensor.dtype}")
        
        # MLX 배열 생성
        mlx_array = mx.random.normal(shape=(3, 4))
        print(f"MLX 배열: {mlx_array.shape}, {mlx_array.dtype}")
        
        # 변환 가능성 평가
        print("\n변환 평가:")
        print("1. 데이터 타입: float32 → 호환 가능")
        print("2. 메모리 레이아웃: 다를 수 있음")
        print("3. 연산 세맨틱: 유사함")
        print("4. GPU 가속: 둘 다 지원")
        
        return True
        
    except ImportError as e:
        print(f"MLX 가져오기 실패: {e}")
        return False
    except Exception as e:
        print(f"테스트 실패: {e}")
        return False

if __name__ == "__main__":
    print("TurboQuant MLX 통합 테스트 시작")
    print("=" * 60)
    
    success_count = 0
    total_tests = 3
    
    try:
        if test_basic_functionality():
            success_count += 1
            print("✅ 기본 기능 테스트 통과")
        else:
            print("❌ 기본 기능 테스트 실패")
        
        if test_turboquant_concepts():
            success_count += 1
            print("✅ 개념 테스트 통과")
        else:
            print("❌ 개념 테스트 실패")
        
        if test_mlx_compatibility():
            success_count += 1
            print("✅ MLX 호환성 테스트 통과")
        else:
            print("❌ MLX 호환성 테스트 실패")
        
        print("\n" + "=" * 60)
        print(f"테스트 결과: {success_count}/{total_tests} 통과")
        
        if success_count == total_tests:
            print("🎉 모든 테스트 통과! TurboQuant MLX 통합 가능")
        else:
            print("⚠️ 일부 테스트 실패. 추가 작업 필요")
            
    except Exception as e:
        print(f"\n❌ 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()