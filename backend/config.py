"""Load settings from environment. All secrets stay in .env (never committed)."""
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Groq (Llama 3.3)
    groq_api_key: str = ""

    # Hugging Face Inference API (Florence-2 / image caption)
    hf_token: str = ""

    # Gemini API (Google AI Studio)
    gemini_api_key: str = ""

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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
