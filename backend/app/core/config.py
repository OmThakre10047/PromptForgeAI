"""Application settings, loaded from environment variables / `.env`."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # ----- Provider credentials -----
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    # "auto" -> use the mock provider only when no API key is configured.
    # "true" -> always mock (offline, deterministic; used by the test-suite).
    # "false" -> never mock.
    MOCK_MODE: str = "auto"

    # Comma separated Groq model ids exposed to the router.
    GROQ_MODELS: str = "llama-3.3-70b-versatile,qwen/qwen3-32b,openai/gpt-oss-120b"

    # ----- LLM routing -----
    ROUTING_STRATEGY: str = "adaptive"  # "adaptive" | "static"
    ROUTER_TOP_K: int = 3  # fallback chain length per call
    ROUTER_EXPLORATION: float = 0.08  # UCB exploration weight
    CIRCUIT_BREAKER_THRESHOLD: int = 3  # consecutive failures before cooldown
    CIRCUIT_BREAKER_COOLDOWN_S: float = 60.0
    LLM_TIMEOUT_S: float = 60.0
    LLM_MAX_TOKENS: int = 4096

    # ----- Pipeline defaults -----
    DEFAULT_LANGUAGE: str = "cpp"  # "cpp" | "python"
    ACCEPTANCE_SCORE: int = 85
    MAX_REPAIRS: int = 4
    MAX_REPLANS: int = 1
    MAX_REFINEMENTS: int = 1

    # ----- Sandbox -----
    RUN_TIMEOUT_S: float = 2.0
    COMPILE_TIMEOUT_S: float = 30.0
    MEMORY_LIMIT_MB: int = 512
    MAX_OUTPUT_BYTES: int = 64_000
    ORACLE_TIMEOUT_S: float = 4.0

    # ----- Storage -----
    DATA_DIR: Path = BACKEND_DIR / "data"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        extra="ignore",
    )

    @property
    def mock_enabled(self) -> bool:
        mode = self.MOCK_MODE.strip().lower()
        if mode in ("1", "true", "yes", "on"):
            return True
        if mode in ("0", "false", "no", "off"):
            return False
        return not (self.OPENROUTER_API_KEY or self.GROQ_API_KEY)

    @property
    def telemetry_file(self) -> Path:
        return self.DATA_DIR / "telemetry.json"

    @property
    def history_file(self) -> Path:
        return self.DATA_DIR / "history.json"

    @property
    def model_cache_file(self) -> Path:
        return self.DATA_DIR / "models_cache.json"


settings = Settings()
