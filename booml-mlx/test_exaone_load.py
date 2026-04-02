#!/usr/bin/env python3
"""Test EXAONE model loading on Mac mini"""

import time
import sys
import os

def test_exaone_load():
    print("Testing EXAONE model loading...")
    print(f"Python version: {sys.version}")
    
    # Try to import mlx_lm
    try:
        from mlx_lm import load, generate
        print("✅ mlx_lm imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import mlx_lm: {e}")
        return False
    
    model_id = "mlx-community/EXAONE-3.5-7.8B-Instruct-4bit"
    print(f"\nAttempting to load model: {model_id}")
    print("This may take several minutes and download ~4GB of data...")
    
    try:
        start_time = time.time()
        model, tokenizer = load(model_id)
        load_time = time.time() - start_time
        
        print(f"✅ Model loaded successfully in {load_time:.2f} seconds")
        
        # Test a simple generation
        print("\nTesting generation...")
        test_prompt = "Hello, how are you?"
        start_gen = time.time()
        response = generate(model, tokenizer, prompt=test_prompt, max_tokens=20, verbose=False)
        gen_time = time.time() - start_gen
        
        print(f"✅ Generation successful in {gen_time:.2f} seconds")
        print(f"Prompt: {test_prompt}")
        print(f"Response: {response[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading/generating: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_exaone_load()
    sys.exit(0 if success else 1)