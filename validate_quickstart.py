#!/usr/bin/env python3
"""
Test script to validate quickstart configuration examples.
"""

import os
import tempfile
from traverser_ai_api.config import Config

def test_config_defaults():
    """Test that config defaults match quickstart documentation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = os.path.join(temp_dir, 'test_config.json')
        with open(config_file, 'w') as f:
            f.write('{}')

        try:
            cfg = Config(user_config_json_path=config_file)

            # Check MCP defaults
            assert cfg.get("MCP_SERVER_URL") == "http://localhost:3000/mcp", f"MCP_SERVER_URL mismatch: {cfg.get('MCP_SERVER_URL')}"
            assert cfg.get("MCP_CONNECTION_TIMEOUT") == 5.0, f"MCP_CONNECTION_TIMEOUT mismatch: {cfg.get('MCP_CONNECTION_TIMEOUT')}"
            assert cfg.get("MCP_REQUEST_TIMEOUT") == 30.0, f"MCP_REQUEST_TIMEOUT mismatch: {cfg.get('MCP_REQUEST_TIMEOUT')}"
            assert cfg.get("MCP_MAX_RETRIES") == 3, f"MCP_MAX_RETRIES mismatch: {cfg.get('MCP_MAX_RETRIES')}"
            
            # Check AI provider defaults
            assert cfg.get("AI_PROVIDER") == "gemini", f"AI_PROVIDER mismatch: {cfg.get('AI_PROVIDER')}"
            assert cfg.get("DEFAULT_MODEL_TYPE") == "gemini-2.5-flash-image", f"DEFAULT_MODEL_TYPE mismatch: {cfg.get('DEFAULT_MODEL_TYPE')}"

            print("SUCCESS: All config defaults match quickstart documentation")
            return True

        except Exception as e:
            print(f"ERROR: Config validation failed: {e}")
            return False

if __name__ == "__main__":
    success = test_config_defaults()
    exit(0 if success else 1)