"""Load settings from environment. All secrets stay in .env (never committed)."""
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """
    Pydantic v2: use model_config so .env is always loaded from the backend folder
    (not the process cwd), which fixes missing GEMINI_API_KEY when uvicorn is
    started from the repo root.
    """

    # Load `.env` first, then `env` (non-dot name some editors use). Missing files are ignored.
    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", _BACKEND_DIR / "env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Groq (Llama 3.3)
    groq_api_key: str = ""

    # Hugging Face Inference API (Florence-2 / image caption)
    hf_token: str = ""

    # Gemini API (Google AI Studio) — env: GEMINI_API_KEY, GEMINI_MODEL
    # Comma-separated list: first model is used for vision tagging; AI explanation tries each until one succeeds.
    gemini_model: str = "gemini-2.5-flash,gemini-2.0-flash,gemini-1.5-flash"
    gemini_api_key: str = ""

    # Outfits generation controls
    outfits_react_enabled: bool = True
    outfits_react_model: str = "gemini-2.0-flash"
    outfits_react_max_steps: int = 6
    outfits_judge_enabled: bool = True
    outfits_judge_model: str = "gemini-2.0-flash"
    outfits_judge_max_tokens: int = 512

    # Cloudinary (image storage)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def strip_str(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()
