"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Analyx backend settings, loaded from environment variables."""

    # LLM
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    analyx_llm_model: str = "gemini-2.5-flash"
    analyx_llm_provider: str = "gemini"

    # Solana
    solana_cluster: str = "devnet"
    solana_rpc_url: str = "https://api.devnet.solana.com"
    onchain_offline_mode: bool = False
    onchain_max_signatures: int = 1000

    # Backend
    database_url: str = "sqlite:///./data/analyx.db"
    data_dir: str = "./data"
    jwt_secret: str = "change-me"
    allowed_origins: list[str] = ["http://localhost:3000"]
    privacy_min_group: int = 10

    # Budgets (per request)
    budget_lookup_tool_calls: int = 8
    budget_analysis_tool_calls: int = 15
    budget_investigation_tool_calls: int = 25
    budget_max_output_tokens: int = 4000

    # Feature flags
    feature_tee: bool = True
    feature_x402: bool = False
    feature_pdf: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
