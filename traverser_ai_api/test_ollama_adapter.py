#!/usr/bin/env python3
"""
Test script for OllamaAdapter functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from model_adapters import OllamaAdapter

def test_ollama_adapter():
    """Test the OllamaAdapter with both text-only and vision models."""

    print("Testing OllamaAdapter...")

    # Test text-only model
    print("\n1. Testing text-only model (llama3.2)...")
    try:
        adapter_text = OllamaAdapter("http://localhost:11434", "llama3.2")
        adapter_text.initialize({
            'generation_config': {'temperature': 0.7, 'top_p': 0.95, 'max_output_tokens': 1024},
            'vision_supported': False
        })

        response_text, metadata_text = adapter_text.generate_response(
            "Hello, can you tell me what you are?"
        )

        print(f"✅ Text model response: {response_text[:100]}...")
        print(f"   Processing time: {metadata_text['processing_time']:.2f}s")
        print(f"   Token count: {metadata_text['token_count']}")

    except Exception as e:
        print(f"❌ Text model test failed: {e}")

    # Test vision-capable model
    print("\n2. Testing vision-capable model (llama3.2-vision)...")
    try:
        adapter_vision = OllamaAdapter("http://localhost:11434", "llama3.2-vision")
        adapter_vision.initialize({
            'generation_config': {'temperature': 0.7, 'top_p': 0.95, 'max_output_tokens': 1024},
            'vision_supported': True
        })

        response_vision, metadata_vision = adapter_vision.generate_response(
            "Hello, can you describe what you see in this image? (Note: No image provided for this test)"
        )

        print(f"✅ Vision model response: {response_vision[:100]}...")
        print(f"   Processing time: {metadata_vision['processing_time']:.2f}s")
        print(f"   Token count: {metadata_vision['token_count']}")

    except Exception as e:
        print(f"❌ Vision model test failed: {e}")

    print("\n✅ OllamaAdapter tests completed!")

if __name__ == "__main__":
    test_ollama_adapter()
