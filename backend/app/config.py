from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_name: str = "Knowledge & Decision Assistant"
    public_url: str = ""
    data_dir: Path = BASE_DIR / "data"
    database_url: str = ""
    jwt_secret: str = "dev-only-secret-change-me-in-production-0123456789"
    jwt_hours: int = 24

    # Hosted demo: create the two sample organizations on start (see demo_seed.py)
    seed_demo: bool = False
    seed_base: str = "http://127.0.0.1:8000"
    sample_dir: Path = BASE_DIR.parent / "sample_data"

    # Hard limits from the assignment
    max_docs: int = 10
    max_pages: int = 20
    max_pdf_mb: int = 10

    # LLM: ollama (free, local) | openai_compat (Groq/OpenRouter/Gemini-compat free tiers) | mock
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_api_key: str = ""
    openai_model: str = "qwen/qwen3.8-27b"
    # tried in order when the main model is rate-limited (free tiers allow few tokens a minute per model) or unavailable
    openai_fallback_models: str = "openai/gpt-oss-20b,openai/gpt-oss-120b"
    llm_timeout: float = 120.0
    rules_llm: bool = False  # opt-in: enable with a strong model (e.g. Groq 70B); small local models over-generate
    rules_llm_max_pages: int = 6

    # System 1 models: fastembed (bge-small + MiniLM cross-encoder) | hash (offline test fallback)
    embed_backend: str = "fastembed"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"

    # Retrieval / grounding thresholds
    top_k: int = 5
    min_support: float = 0.12
    rate_limit_per_minute: int = 30

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'app.db').as_posix()}"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
