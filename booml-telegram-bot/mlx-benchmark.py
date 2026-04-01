#!/usr/bin/env python3
"""
붐엘 MLX 성능 벤치마크 스크립트
macOS M4 Pro Metal 가속 테스트
"""

import time
import sys
import subprocess
import json
from datetime import datetime

def check_mlx_installation():
    """MLX 설치 상태 확인"""
    try:
        import mlx.core as mx
        import mlx.nn as nn
        return True, "✅ MLX 설치됨"
    except ImportError as e:
        return False, f"❌ MLX 설치 안됨: {e}"

def check_metal_support():
    """Metal 가속 지원 확인"""
    try:
        result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                              capture_output=True, text=True)
        if 'Metal' in result.stdout:
            return True, "✅ Metal 가속 지원됨"
        else:
            return False, "❌ Metal 가속 미지원"
    except Exception as e:
        return False, f"❌ Metal 확인 실패: {e}"

def run_matrix_multiplication_benchmark():
    """행렬 곱셈 벤치마크"""
    try:
        import mlx.core as mx
        
        # 큰 행렬 생성 (Metal 가속 테스트)
        size = 4096
        print(f"행렬 크기: {size}x{size}")
        
        # CPU 모드
        mx.set_default_device(mx.cpu)
        a_cpu = mx.random.uniform(shape=(size, size))
        b_cpu = mx.random.uniform(shape=(size, size))
        
        start = time.time()
        result_cpu = mx.matmul(a_cpu, b_cpu)
        mx.eval(result_cpu)
        cpu_time = time.time() - start
        
        # GPU 모드 (Metal)
        mx.set_default_device(mx.gpu)
        a_gpu = mx.random.uniform(shape=(size, size))
        b_gpu = mx.random.uniform(shape=(size, size))
        
        start = time.time()
        result_gpu = mx.matmul(a_gpu, b_gpu)
        mx.eval(result_gpu)
        gpu_time = time.time() - start
        
        speedup = cpu_time / gpu_time if gpu_time > 0 else 0
        
        return {
            "cpu_time": round(cpu_time, 3),
            "gpu_time": round(gpu_time, 3),
            "speedup": round(speedup, 1),
            "status": "✅ 성공"
        }
    except Exception as e:
        return {
            "cpu_time": 0,
            "gpu_time": 0,
            "speedup": 0,
            "status": f"❌ 실패: {e}"
        }

def run_inference_benchmark():
    """추론 속도 벤치마크 (Qwen2.5-7B 시뮬레이션)"""
    try:
        import mlx.core as mx
        import mlx.nn as nn
        
        # 간단한 신경망 생성 (LLM 추론 시뮬레이션)
        class SimpleLLM(nn.Module):
            def __init__(self, hidden_size=512):
                super().__init__()
                self.embedding = nn.Embedding(10000, hidden_size)
                self.layers = nn.Sequential(
                    nn.Linear(hidden_size, hidden_size),
                    nn.ReLU(),
                    nn.Linear(hidden_size, hidden_size),
                    nn.ReLU(),
                    nn.Linear(hidden_size, 10000)
                )
            
            def __call__(self, x):
                x = self.embedding(x)
                return self.layers(x)
        
        model = SimpleLLM()
        mx.eval(model.parameters())
        
        # 배치 크기별 추론 시간 측정
        batch_sizes = [1, 4, 8, 16]
        results = {}
        
        for batch_size in batch_sizes:
            inputs = mx.array([[i % 1000 for i in range(32)] for _ in range(batch_size)])
            
            # 워밍업
            for _ in range(2):
                output = model(inputs)
                mx.eval(output)
            
            # 실제 측정
            start = time.time()
            for _ in range(10):
                output = model(inputs)
                mx.eval(output)
            elapsed = (time.time() - start) / 10
            
            tokens_per_second = (batch_size * 32) / elapsed
            results[batch_size] = {
                "time_per_batch": round(elapsed, 3),
                "tokens_per_second": round(tokens_per_second, 1)
            }
        
        return results
    except Exception as e:
        return {"error": f"추론 벤치마크 실패: {e}"}

def get_system_info():
    """시스템 정보 수집"""
    info = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": sys.platform,
        "python_version": sys.version.split()[0]
    }
    
    try:
        # macOS 버전
        result = subprocess.run(['sw_vers', '-productVersion'], 
                              capture_output=True, text=True)
        info["macos_version"] = result.stdout.strip()
        
        # 하드웨어 정보
        result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                              capture_output=True, text=True)
        mem_gb = int(result.stdout.strip()) / (1024**3)
        info["memory_gb"] = round(mem_gb, 1)
        
        # CPU 정보
        result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                              capture_output=True, text=True)
        info["cpu"] = result.stdout.strip()
        
        # GPU 정보
        result = subprocess.run(['system_profiler', 'SPDisplaysDataType', '-json'], 
                              capture_output=True, text=True)
        gpu_info = json.loads(result.stdout)
        if gpu_info.get('SPDisplaysDataType'):
            for display in gpu_info['SPDisplaysDataType']:
                if 'sppci_device_type' in display and 'GPU' in display['sppci_device_type']:
                    info["gpu"] = display.get('_name', 'Unknown')
                    info["vram_mb"] = display.get('spdisplays_vram', 'Unknown')
                    break
        
    except Exception as e:
        info["error"] = f"시스템 정보 수집 실패: {e}"
    
    return info

def main():
    """메인 벤치마크 실행"""
    print("🚀 붐엘 MLX 성능 벤치마크 시작")
    print("=" * 50)
    
    # 시스템 정보
    print("\n📊 시스템 정보:")
    system_info = get_system_info()
    for key, value in system_info.items():
        print(f"  {key}: {value}")
    
    # MLX 설치 확인
    print("\n🔧 MLX 설치 상태:")
    mlx_installed, mlx_msg = check_mlx_installation()
    print(f"  {mlx_msg}")
    
    # Metal 지원 확인
    print("\n🎯 Metal 가속 지원:")
    metal_supported, metal_msg = check_metal_support()
    print(f"  {metal_msg}")
    
    if not mlx_installed:
        print("\n❌ MLX가 설치되지 않았습니다. 벤치마크를 종료합니다.")
        return
    
    # 행렬 곱셈 벤치마크
    print("\n🧮 행렬 곱셈 벤치마크:")
    matmul_result = run_matrix_multiplication_benchmark()
    print(f"  CPU 시간: {matmul_result['cpu_time']}초")
    print(f"  GPU 시간: {matmul_result['gpu_time']}초")
    print(f"  가속화: {matmul_result['speedup']}배")
    print(f"  상태: {matmul_result['status']}")
    
    # 추론 벤치마크
    print("\n🤖 추론 속도 벤치마크 (LLM 시뮬레이션):")
    inference_results = run_inference_benchmark()
    
    if "error" in inference_results:
        print(f"  {inference_results['error']}")
    else:
        for batch_size, result in inference_results.items():
            print(f"  배치 {batch_size}: {result['time_per_batch']}초/배치, {result['tokens_per_second']} 토큰/초")
    
    # 요약
    print("\n" + "=" * 50)
    print("📈 벤치마크 요약:")
    print(f"  플랫폼: macOS {system_info.get('macos_version', 'Unknown')}")
    print(f"  CPU: {system_info.get('cpu', 'Unknown')}")
    print(f"  GPU: {system_info.get('gpu', 'Unknown')}")
    print(f"  메모리: {system_info.get('memory_gb', 'Unknown')}GB")
    
    if matmul_result['speedup'] > 1:
        print(f"  Metal 가속: {matmul_result['speedup']}배 향상")
    else:
        print(f"  Metal 가속: 테스트 필요")
    
    print("\n✅ 벤치마크 완료")

if __name__ == "__main__":
    main()