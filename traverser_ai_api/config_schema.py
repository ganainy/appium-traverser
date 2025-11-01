from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

class TraverserDefaults(BaseSettings):
    # Path settings
    output_dir: str = Field(default="output_data", description="Output directory for data")
    cache_dir: str = Field(default=".cache", description="Cache directory")
    log_dir: str = Field(default="logs", description="Log directory")

    # Model settings
    AI_PROVIDER: str = Field(default="gemini", description="Default AI provider")
    default_model_type: str = Field(default="gemini-2.5-flash-image", description="Default AI model provider")
    max_tokens: int = Field(default=4000, gt=0, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")

    # Crawler settings
    xml_snippet_max_len: int = Field(default=10000, gt=0, description="Max XML snippet length")
    enable_image_context: bool = Field(default=True, description="Enable image context in prompts")

    # Complex data
    focus_areas: List[str] = Field(default_factory=lambda: ["navigation", "content", "actions"], description="Default focus areas")

    # MCP settings
    MCP_SERVER_URL: str = Field(default="http://localhost:3000/mcp", description="MCP server URL")
    MCP_CONNECTION_TIMEOUT: float = Field(default=5.0, description="MCP connection timeout (seconds)")
    MCP_REQUEST_TIMEOUT: float = Field(default=30.0, description="MCP request timeout (seconds)")
    MCP_MAX_RETRIES: int = Field(default=3, description="MCP max retries")

    class PydanticConfig:
        env_prefix = ""
        case_sensitive = True
    Config = PydanticConfig
