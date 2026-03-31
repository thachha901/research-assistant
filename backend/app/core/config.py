# backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    ARXIV_BASE_URL: str = "https://export.arxiv.org/api/query"
    SEMANTIC_SCHOLAR_API: str = "https://api.semanticscholar.org/graph/v1"

    # Railway inject PORT automatically
    PORT: int = 8000 
    
    # CORS - add domain Vercel later
    ALLOWED_ORIGINS: str = "https://localhost:3000"
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"       # bỏ qua các biến lạ trong .env
    }

settings = Settings()