#!/usr/bin/env python3
"""
Test script for Ollama UI model loading
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ollama_model_loading():
    """Test the Ollama model loading logic from UI components."""

    print("Testing Ollama model loading for UI...")

    try:
        import ollama

        # Simulate the UI logic for loading Ollama models
        available_models = ollama.list()
        model_items = []
        vision_models = []

        print(f"Raw Ollama list response: {available_models}")

        for model_info in available_models.get('models', []):
            model_name = model_info.get('model', model_info.get('name', ''))
            if not model_name:
                continue
                
            # Remove tag if present (e.g., "llama3.2:latest" -> "llama3.2")
            base_name = model_name.split(':')[0]

            # Check if this model supports vision by looking at the name
            # Common vision-capable model patterns
            vision_supported = any(pattern in base_name.lower() for pattern in [
                'vision', 'llava', 'bakllava', 'minicpm-v', 'moondream', 'gemma3', 'llama4', 'qwen2.5vl'
            ])

            # Add local indicator and vision indicator
            display_name = f"{model_name}(local)"
            if vision_supported:
                display_name += " 👁️"
                vision_models.append(display_name)

            model_items.append(display_name)

        print(f"\nAvailable models for UI dropdown:")
        for i, model in enumerate(model_items, 1):
            print(f"{i}. {model}")

        print(f"\nVision-capable models: {vision_models}")

        # Test model name extraction
        from model_adapters import OllamaAdapter

        print(f"\nTesting model name extraction:")
        for display_name in model_items:
            adapter = OllamaAdapter("http://localhost:11434", display_name)
            # Initialize the adapter to set vision_supported properly
            adapter.initialize({
                'generation_config': {'temperature': 0.7, 'top_p': 0.95, 'max_output_tokens': 1024}
            })
            print(f"Display: '{display_name}' -> Actual: '{adapter.model_name}' (Vision: {adapter.vision_supported})")

    except ImportError:
        print("❌ Ollama package not installed")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_ollama_model_loading()
