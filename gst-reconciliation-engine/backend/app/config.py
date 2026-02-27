"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Central configuration for the GST Reconciliation Engine."""

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "gst_recon_2024"
    NEO4J_DATABASE: str = "neo4j"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    API_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Reconciliation
    MATCH_TOLERANCE_ABS: float = 1.0       # ±₹1
    MATCH_TOLERANCE_PCT: float = 0.001     # ±0.1%
    FUZZY_MATCH_THRESHOLD: int = 85

    # ML
    MODEL_PATH: str = "./models/vendor_risk_model.pkl"
    RETRAIN_INTERVAL_HOURS: int = 24

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.API_CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
