from pydantic import BaseSettings


class Settings(BaseSettings):
    PORT: int = 3000

    # Boce API credentials
    BOCE_API_URL: str = "https://api.boce.com/v3"   # base URL (no trailing slash)
    BOCE_API_KEY: str = ""                            # leave empty → use mock

    # Which Boce node IDs to include in every detection task
    # Comma-separated string in .env, e.g.  BOCE_NODE_IDS=6,31,32,55
    # Default is a small representative set used by the built-in mock too.
    BOCE_NODE_IDS: str = "6,31,32"

    # HTTP request timeout for a single Boce HTTP call (seconds)
    BOCE_TIMEOUT_SECONDS: float = 15.0

    # Polling: how long to wait between result polls (seconds)
    BOCE_POLL_INTERVAL_SECONDS: float = 10.0

    # Polling: give up after this many seconds (Boce recommends 2 minutes)
    BOCE_POLL_TIMEOUT_SECONDS: float = 120.0

    # Redis Configuration (for ARQ task queue)
    REDIS_URL: str = "redis://localhost:6379"

    # Database Configuration
    DATABASE_NAME: str = "boce_api.db"

    # Concurrency Throttling (Internal)
    MAX_CONCURRENT_TASKS: int = 20

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
