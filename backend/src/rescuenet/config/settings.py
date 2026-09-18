"""Typed, validated configuration (docs/07 T-05/T-16, docs/12 M1).

Every value arrives from the environment. Nothing sensitive is hard-coded, and
secrets are held in ``SecretStr`` so they cannot leak through ``repr``, logs or
tracebacks.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    """Backend configuration.

    Fields for components that do not exist yet are optional by design:
    the event store lands at M3 and the MQTT publisher at M10 (docs/12).
    They are declared here so configuration has one home, not so M1 uses them.
    """

    model_config = SettingsConfigDict(
        env_prefix="RESCUENET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEV
    log_level: str = "INFO"
    backend_port: int = Field(default=8000, ge=1, le=65535)

    # --- M3: PostgreSQL event store (docs/07 T-06). Unused at M1. ---
    database_url: SecretStr | None = None

    # --- M10: MQTT publisher (docs/07 T-09, docs/09 AP-23). Unused at M1. ---
    mqtt_host: str | None = None
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_username: str | None = None
    mqtt_password: SecretStr | None = None

    @model_validator(mode="after")
    def _production_requires_backing_services(self) -> Settings:
        """In production the store and broker must be configured.

        This validates configuration; it does not connect to anything. Wiring
        arrives with the components themselves at M3 and M10.
        """
        if self.app_env is AppEnv.PROD:
            missing = [
                name
                for name, value in (
                    ("RESCUENET_DATABASE_URL", self.database_url),
                    ("RESCUENET_MQTT_HOST", self.mqtt_host),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"app_env=prod requires: {', '.join(missing)}"
                )
        return self

    @model_validator(mode="after")
    def _log_level_is_known(self) -> Settings:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if self.log_level.upper() not in allowed:
            raise ValueError(
                f"log_level must be one of {sorted(allowed)}, got {self.log_level!r}"
            )
        self.log_level = self.log_level.upper()
        return self


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings. Cached so configuration is read once."""
    return Settings()
