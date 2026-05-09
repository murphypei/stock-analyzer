"""Configuration management."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment."""

    TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
    BAOSTOCK_USER = os.getenv("BAOSTOCK_USER", "")
    BAOSTOCK_PASSWORD = os.getenv("BAOSTOCK_PASSWORD", "")

    CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
    CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "7"))

    # Financial thresholds aligned with the strategy guide
    ROE_THRESHOLD = 0.12
    GROSS_MARGIN_THRESHOLD = 0.15
    OCF_NETINCOME_THRESHOLD = 0.5
    DEBT_RATIO_THRESHOLD = 0.60
    CURRENT_RATIO_THRESHOLD = 1.0

    @classmethod
    def ensure_cache_dir(cls) -> Path:
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CACHE_DIR
