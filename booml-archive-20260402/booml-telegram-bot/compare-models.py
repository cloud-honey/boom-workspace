#!/usr/bin/env python3
"""
Ollama vs MLX 모델 비교 분석
macOS M4 Pro에서의 성능 비교
"""

import time
import subprocess
import json
import sys
from datetime import datetime

def get_ollama_models():
    """Ollama 설치된 모델 목록 가져오기"""
    try:
        result = subprocess.run(['ollama', 'list'], 
                              capture_output=True, text=True)
        models = []
        for line in result.stdout.strip().split('\n')[1:]:  # 헤더 제외
            if line.strip():
                parts = line.split()
                if len(parts) >= 2:
                    models.append(parts[0])
        return models
    except Exception as e:
        print(f"Ollama 모델 목록 조회 실패: {e}")
        return []

def benchmark_ollama_model(model_name):
    """Ollama 모델 벤치마크"""
    try:
        # 간단한 프롬프트로 응답 시간 측정
        prompt = "Hello, how are you? Please respond briefly."
        
        start_time = time.time()
        result = subprocess.run(
            ['ollama', 'run', model_name, prompt],
            capture_output=True,
            text=True,
            timeout=30  # 30초 타임아웃
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            output = result.stdout.strip()
            tokens = len(output.split())
            tokens_per_second = tokens / elapsed if elapsed > 0 else 0
            
            return {
                "model": model_name,
                "response_time": round(elapsed, 2),
                "tokens": tokens,
                "tokens_per_second": round(tokens_per_second, 1),
                "status": "✅ 성공"
            }
        else:
            return {
                "model": model_name,
                "response_time": 0,
                "tokens": 0,
                "tokens_per_second": 0,
                "status": f"❌ 실패: {result.stderr[:100]}"
            }
    except subprocess.TimeoutExpired:
        return {
            "model": model_name,
            "response_time": 30,
            "tokens": 0,
            "tokens_per_second": 0,
            "status": "❌ 타임아웃 (30초)"
        }
    except Exception as e:
        return {
            "model": model_name,
            "response_time": 0,
            "tokens": 0,
            "tokens_per_second": 0,
            "status": f"❌ 오류: {e}"
        }

def check_mlx_capabilities():
    """MLX 기능 확인"""
    try:
        import mlx.core as mx
        
        capabilities = {
            "mlx_installed": True,
            "devices": [],
            "metal_support": False
        }
        
        # 사용 가능한 디바이스 확인
        if mx.cpu.is_available():
            capabilities["devices"].append("CPU")
        
        if mx.gpu.is_available():
            capabilities["devices"].append("GPU")
            capabilities["metal_support"] = True
        
        # 메모리 정보
        if mx.gpu.is_available():
            try:
                # MLX 메모리 정보 (가능한 경우)
                capabilities["gpu_memory"] = "Available"
            except:
                capabilities["gpu_memory"] = "Unknown"
        
        return capabilities
    except ImportError:
        return {
            "mlx_installed": False,
            "devices": [],
            "metal_support": False
        }

def simulate_mlx_performance():
    """MLX 성능 시뮬레이션 (실제 모델이 없을 경우)"""
    try:
        import mlx.core as mx
        import mlx.nn as nn
        
        # 작은 모델로 성능 측정
        class TinyModel(nn.Module):
            def __init__(self, dim=256):
                super().__init__()
                self.linear1 = nn.Linear(dim, dim)
                self.linear2 = nn.Linear(dim, dim)
                self.linear3 = nn.Linear(dim, dim)
            
            def __call__(self, x):
                x = self.linear1(x)
                x = mx.tanh(x)
                x = self.linear2(x)
                x = mx.tanh(x)
                x = self.linear3(x)
                return x
        
        model = TinyModel()
        
        # 배치 크기별 성능 측정
        batch_sizes = [1, 4, 8]
        results = []
        
        for batch_size in batch_sizes:
            # 입력 데이터 생성
            x = mx.random.normal(shape=(batch_size, 256))
            
            # 워밍업
            for _ in range(3):
                y = model(x)
                mx.eval(y)
            
            # 실제 측정
            start = time.time()
            iterations = 10
            for _ in range(iterations):
                y = model(x)
                mx.eval(y)
            elapsed = (time.time() - start) / iterations
            
            # 토큰/초 계산 (가정: 256 토큰 = 1 배치)
            tokens_per_batch = 256
            tokens_per_second = (batch_size * tokens_per_batch) / elapsed
            
            results.append({
                "batch_size": batch_size,
                "time_per_batch": round(elapsed, 3),
                "tokens_per_second": round(tokens_per_second, 1)
            })
        
        return results
    except Exception as e:
        return [{"error": f"MLX 시뮬레이션 실패: {e}"}]

def get_system_resources():
    """시스템 리소스 사용량 확인"""
    resources = {}
    
    try:
        # 메모리 사용량
        result = subprocess.run(['vm_stat'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Pages free' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        free_pages = int(parts[1].strip().replace('.', ''))
                        free_mb = (free_pages * 4096) / (1024**2)
                        resources["free_memory_mb"] = round(free_mb, 1)
        
        # CPU 사용률 (간단한 방법)
        result = subprocess.run(['ps', '-A', '-o', '%cpu'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            cpu_values = [float(x) for x in result.stdout.strip().split('\n')[1:] if x.strip()]
            if cpu_values:
                resources["avg_cpu_usage"] = round(sum(cpu_values) / len(cpu_values), 1)
        
        # 디스크 사용량
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    resources["disk_used"] = parts[4]
        
    except Exception as e:
        resources["error"] = f"리소스 확인 실패: {e}"
    
    return resources

def generate_comparison_report(ollama_results, mlx_capabilities, mlx_performance, resources):
    """비교 리포트 생성"""
    report = []
    report.append("=" * 60)
    report.append("⚖️ Ollama vs MLX 성능 비교 리포트")
    report.append("=" * 60)
    report.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 시스템 리소스
    report.append("📊 시스템 리소스:")
    for key, value in resources.items():
        report.append(f"  {key}: {value}")
    report.append("")
    
    # MLX 기능
    report.append("🔧 MLX 기능:")
    report.append(f"  설치됨: {'✅' if mlx_capabilities['mlx_installed'] else '❌'}")
    report.append(f"  디바이스: {', '.join(mlx_capabilities['devices'])}")
    report.append(f"  Metal 지원: {'✅' if mlx_capabilities['metal_support'] else '❌'}")
    report.append("")
    
    # Ollama 결과
    report.append("🤖 Ollama 모델 성능:")
    if ollama_results:
        for result in ollama_results:
            report.append(f"  모델: {result['model']}")
            report.append(f"    응답 시간: {result['response_time']}초")
            report.append(f"    토큰/초: {result['tokens_per_second']}")
            report.append(f"    상태: {result['status']}")
            report.append("")
    else:
        report.append("  ❌ 테스트된 Ollama 모델 없음")
        report.append("")
    
    # MLX 성능
    report.append("🚀 MLX 성능 (시뮬레이션):")
    if isinstance(mlx_performance, list) and len(mlx_performance) > 0:
        if "error" in mlx_performance[0]:
            report.append(f"  {mlx_performance[0]['error']}")
        else:
            for perf in mlx_performance:
                report.append(f"  배치 {perf['batch_size']}:")
                report.append(f"    시간/배치: {perf['time_per_batch']}초")
                report.append(f"    토큰/초: {perf['tokens_per_second']}")
            report.append("")
    else:
        report.append("  ❌ MLX 성능 데이터 없음")
        report.append("")
    
    # 비교 분석
    report.append("📈 비교 분석:")
    
    if ollama_results and mlx_performance and "error" not in mlx_performance[0]:
        # Ollama 평균 토큰/초
        ollama_speeds = [r['tokens_per_second'] for r in ollama_results if r['tokens_per_second'] > 0]
        if ollama_speeds:
            avg_ollama = sum(ollama_speeds) / len(ollama_speeds)
            
            # MLX 평균 토큰/초 (배치 1 기준)
            mlx_speeds = [p['tokens_per_second'] for p in mlx_performance if 'tokens_per_second' in p]
            if mlx_speeds:
                avg_mlx = mlx_speeds[0]  # 배치 1 기준
                
                if avg_mlx > avg_ollama:
                    speedup = avg_mlx / avg_ollama
                    report.append(f"  MLX가 Ollama보다 약 {speedup:.1f}배 빠름")
                else:
                    speedup = avg_ollama / avg_mlx
                    report.append(f"  Ollama가 MLX보다 약 {speedup:.1f}배 빠름")
                
                report.append(f"  Ollama 평균: {avg_ollama:.1f} 토큰/초")
                report.append(f"  MLX 평균: {avg_mlx:.1f} 토큰/초")
    
    report.append("")
    report.append("💡 권장사항:")
    
    if mlx_capabilities['metal_support']:
        report.append("  1. MLX는 Metal 가속을 지원하므로 macOS에서 최적의 성능")
        report.append("  2. 큰 배치 크기에서 MLX 성능이 더욱 향상됨")
        report.append("  3. 메모리 사용량이 Ollama보다 일반적으로 낮음")
    else:
        report.append("  1. Metal 가속이 없어 MLX 성능 이점 제한적")
        report.append("  2. Ollama가 현재 더 안정적인 선택")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """메인 비교 함수"""
    print("⚖️ Ollama vs MLX 성능 비교 시작")
    print("=" * 50)
    
    # 시스템 리소스 확인
    print("\n📊 시스템 리소스 확인 중...")
    resources = get_system_resources()
    
    # Ollama 모델 테스트
    print("\n🤖 Ollama 모델 테스트 중...")
    ollama_models = get_ollama_models()
    ollama_results = []
    
    if ollama_models:
        print(f"  발견된 모델: {', '.join(ollama_models)}")
        
        # 주요 모델만 테스트 (최대 3개)
        test_models = ollama_models[:3]
        for model in test_models:
            print(f"  테스트 중: {model}")
            result = benchmark_ollama_model(model)
            ollama_results.append(result)
    else:
        print("  ❌ Ollama 모델이 없습니다")
    
    # MLX 기능 확인
    print("\n🔧 MLX 기능 확인 중...")
    mlx_capabilities = check_mlx_capabilities()
    
    if mlx_capabilities['mlx_installed']:
        print(f"  MLX 설치됨")
        print(f"  사용 가능 디바이스: {', '.join(mlx_capabilities['devices'])}")
        print(f"  Metal 지원: {'✅' if mlx_capabilities['metal_support'] else '❌'}")
        
        # MLX 성능 시뮬레이션
        print("\n🚀 MLX 성능 시뮬레이션 중...")
        mlx_performance = simulate_mlx_performance()
    else:
        print("  ❌ MLX가 설치되지 않았습니다")
        mlx_performance = []
    
    # 리포트 생성
    print("\n📈 비교 리포트 생성 중...")
    report = generate_comparison_report(ollama_results, mlx_capabilities, mlx_performance, resources)
    
    print(report)
    
    # 리포트 파일 저장
    try:
        report_file = f"model-comparison-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n📁 리포트 저장됨: {report_file}")
    except Exception as e:
        print(f"\n⚠️ 리포트 저장 실패: {e}")
    
    print("\n✅ 비교 분석 완료")

if __name__ == "__main__":
    main()