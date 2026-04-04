#!/usr/bin/env python3
"""MLX-LM generate 테스트"""

from mlx_lm import load, generate
import time

print("모델 로드 중...")
model, tokenizer = load('mlx-community/Qwen2.5-7B-Instruct-4bit')
print("모델 로드 완료")

# 프롬프트 생성
prompt = "User: 안녕하세요\nAssistant: "

print(f"프롬프트: {prompt}")
print("생성 시작...")

start_time = time.time()
response = generate(
    model,
    tokenizer,
    prompt=prompt,
    max_tokens=50,
    temperature=0.7
)
elapsed_time = time.time() - start_time

print(f"응답: {response}")
print(f"소요 시간: {elapsed_time:.2f}초")
print(f"응답 길이: {len(response)}자")