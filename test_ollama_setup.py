#!/usr/bin/env python3
"""
Ollama Setup and Testing Script
===============================

This script helps you set up and test Ollama with vision-capable models
for the Android app crawler.

Usage:
    python test_ollama_setup.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add the traverser_ai_api directory to the path
sys.path.insert(0, str(Path(__file__).parent / "traverser_ai_api"))

def check_ollama_installation():
    """Check if Ollama is installed and running."""
    print("🔍 Checking Ollama installation...")

    try:
        import ollama
        print("✅ Ollama Python SDK is installed")

        # Try to connect to Ollama
        try:
            models = ollama.list()
            print("✅ Ollama service is running")
            print(f"📋 Available models: {len(models.get('models', []))}")

            # List available models
            for model in models.get('models', []):
                name = model.get('name', 'Unknown')
                size = model.get('size', 0) / (1024**3)  # Convert to GB
                print(f"   - {name}: {size:.1f}GB")
            return True

        except Exception as e:
            print(f"❌ Cannot connect to Ollama: {e}")
            print("💡 Make sure Ollama is running: 'ollama serve'")
            return False

    except ImportError:
        print("❌ Ollama Python SDK not installed")
        print("💡 Install with: pip install ollama")
        return False

def check_vision_models():
    """Check for vision-capable models."""
    print("\n🔍 Checking for vision-capable models...")

    try:
        import ollama
        models = ollama.list()
        vision_models = []
        available_models = []

        for model in models.get('models', []):
            name = model.get('name', '')
            available_models.append(name)

            # Check if it's a vision-capable model by comparing with OLLAMA_MODELS config
            try:
                from traverser_ai_api.config import OLLAMA_MODELS
                # Find the model key that matches this model name
                for model_key, model_config in OLLAMA_MODELS.items():
                    if model_config.get('name') == name or model_key == name:
                        if model_config.get('vision_supported', False):
                            vision_models.append(name)
                        break
            except ImportError:
                # Fallback to keyword-based detection if config import fails
                if any(vision_keyword in name.lower() for vision_keyword in ['vision', 'llava', 'bakllava', 'moondream', 'gemma3', 'llama4', 'qwen2.5vl', 'granite3.2-vision', 'mistral-small3.1', 'mistral-small3.2', 'minicpm-v']):
                    vision_models.append(name)

        print(f"📋 Available models: {available_models}")
        print(f"👁️  Vision-capable models: {vision_models}")

        if vision_models:
            print("✅ Vision models found!")
            return vision_models
        else:
            print("⚠️  No vision-capable models found")
            print("💡 Pull a vision model with:")
            print("   ollama pull llama3.2-vision")
            print("   ollama pull llava")
            return []

    except Exception as e:
        print(f"❌ Error checking models: {e}")
        return []

def test_model(model_name):
    """Test a specific model with a simple prompt."""
    print(f"\n🧪 Testing model: {model_name}")

    try:
        import ollama

        # Simple text test
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": "Hello! Can you see images?"}]
        )

        print("✅ Text response works!")
        print(f"🤖 Response: {response.get('message', {}).get('content', '')[:100]}...")

        return True

    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def update_config(vision_models):
    """Update the user config to use Ollama with vision model."""
    print("\n⚙️  Updating configuration...")

    config_path = Path(__file__).parent / "traverser_ai_api" / "user_config.json"

    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Update to use Ollama
        config["AI_PROVIDER"] = "ollama"

        # Choose the best available vision model
        if vision_models:
            if "llama3.2-vision" in vision_models:
                config["DEFAULT_MODEL_TYPE"] = "llama3.2-vision(local) 👁️"
            elif "gemma3" in vision_models:
                config["DEFAULT_MODEL_TYPE"] = "gemma3(local) 👁️"
            elif "llava" in vision_models:
                config["DEFAULT_MODEL_TYPE"] = "llava(local) 👁️"
            else:
                # Use the first vision model found
                first_vision = vision_models[0]
                try:
                    from traverser_ai_api.config import OLLAMA_MODELS
                    # Find the display name for this model
                    for model_key, model_config in OLLAMA_MODELS.items():
                        if model_config.get('name') == first_vision or model_key == first_vision:
                            display_name = f"{model_config.get('name', first_vision)}(local)"
                            if model_config.get('vision_supported', False):
                                display_name += " 👁️"
                            config["DEFAULT_MODEL_TYPE"] = display_name
                            break
                    else:
                        config["DEFAULT_MODEL_TYPE"] = f"{first_vision}(local) 👁️"
                except ImportError:
                    config["DEFAULT_MODEL_TYPE"] = f"{first_vision}(local) 👁️"
        else:
            config["DEFAULT_MODEL_TYPE"] = "llama3.2(local)"  # Fallback to text-only

        # Set Ollama base URL
        config["OLLAMA_BASE_URL"] = "http://localhost:11434"

        # Write back
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)

        print("✅ Configuration updated!")
        print(f"🔧 AI_PROVIDER: {config['AI_PROVIDER']}")
        print(f"🔧 DEFAULT_MODEL_TYPE: {config['DEFAULT_MODEL_TYPE']}")
        print(f"🔧 OLLAMA_BASE_URL: {config['OLLAMA_BASE_URL']}")

        return True

    except Exception as e:
        print(f"❌ Failed to update config: {e}")
        return False

def main():
    """Main setup and testing function."""
    print("🚀 Ollama Setup and Testing for Android App Crawler")
    print("=" * 50)

    # Check installation
    if not check_ollama_installation():
        print("\n❌ Ollama setup incomplete. Please install Ollama and try again.")
        return

    # Check for vision models
    vision_models = check_vision_models()

    # Test a model
    if vision_models:
        test_model(vision_models[0])
    else:
        # Test text-only model
        try:
            import ollama
            models = ollama.list()
            if models.get('models'):
                test_model(models['models'][0]['name'])
        except:
            pass

    # Update configuration
    if update_config(vision_models):
        print("\n🎉 Setup complete!")
        print("💡 You can now run the Android app crawler with Ollama!")
        print("   python traverser_ai_api/ui_controller.py")
    else:
        print("\n⚠️  Setup completed with warnings.")

if __name__ == "__main__":
    main()
