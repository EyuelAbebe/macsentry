from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SentinelConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MACSENTRY_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    log_level: str = "WARNING"
    data_dir: Path = Path.home() / ".local" / "share" / "macsentry"
    poll_interval_seconds: float = 2.0
    scan_timeout_seconds: float = 30.0

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return v.upper()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "macsentry.db"

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


_config: SentinelConfig | None = None


def get_config() -> SentinelConfig:
    global _config
    if _config is None:
        _config = SentinelConfig()
    return _config


def override_config(config: SentinelConfig) -> None:
    """Replace the global config — intended for tests."""
    global _config
    _config = config
