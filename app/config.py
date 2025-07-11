from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os

model_config = ConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="allow"
)

class Settings(BaseSettings):
    """
    Centralized configuration for LLMs and environment variables.
    Loads from .env and validates required fields.
    """
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # LM Studio
    LM_STUDIO_URL: str = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")
    LM_STUDIO_MODEL: str = os.getenv("LM_STUDIO_MODEL", "mistral-7b-instruct-v0.1:2")

    # Ollama
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")

    # Supabase (optional)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # App config (optional)
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    model_config = model_config

    def validate(self):
        errors = []
        if not self.LM_STUDIO_URL:
            errors.append("LM_STUDIO_URL is not set.")
        if not self.LM_STUDIO_MODEL:
            errors.append("LM_STUDIO_MODEL is not set.")
        if errors:
            raise ValueError("\n".join(errors))

settings = Settings()

"""
How to update LM Studio configuration:
- In LM Studio, check the model's API identifier (e.g., 'mistral-7b-instruct-v0.1:2') and set it in your .env as:
    LM_STUDIO_MODEL=mistral-7b-instruct-v0.1:2
- The local server address should be set as:
    LM_STUDIO_URL=http://127.0.0.1:1234/v1
""" 