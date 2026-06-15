"""Configuration loader.

Reads everything from environment variables. The s6 service runner
exports each add-on option as POOL_BRAIN_*. We coerce them here once
and freeze them on a module-level dataclass.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"POOL_BRAIN_{key}", default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    v = _env(key, str(default)).lower()
    return v in ("true", "1", "yes", "on")


def _env_int(key: str, default: int) -> int:
    try:
        return int(float(_env(key, str(default))))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # Logging
    log_level: str

    # Upstream capturer
    capturer_base_url: str

    # Pool spec
    pool_volume_m3: float
    target_turnovers_per_day: float

    # Pump / cleaner
    pump_switch_entity: str
    pump_power_entity: str
    cleaner_switch_entity: str
    cleaner_power_entity: str

    # Notify channels
    notify_telegram_service: str
    notify_email_service: str
    email_target: str

    # Weekly report
    weekly_report_enabled: bool
    weekly_report_day: str
    weekly_report_hour: int

    # Safety
    auto_emergency_stop: bool
    first_minutes_window_s: int

    # Bootstrap
    auto_bootstrap_package: bool

    # MQTT
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str

    # Supervisor (injected automatically)
    supervisor_token: str = ""
    hass_api: str = "http://supervisor/core/api"


def load_settings() -> Settings:
    return Settings(
        log_level=_env("LOG_LEVEL", "info"),
        capturer_base_url=_env("CAPTURER_BASE_URL", "http://localhost:8765"),
        pool_volume_m3=_env_float("POOL_VOLUME_M3", 37.0),
        target_turnovers_per_day=_env_float("TARGET_TURNOVERS_PER_DAY", 1.0),
        pump_switch_entity=_env("PUMP_SWITCH_ENTITY", "switch.depuradora"),
        pump_power_entity=_env(
            "PUMP_POWER_ENTITY",
            "sensor.shellypro4pm_30c6f7836a6c_power_3",
        ),
        cleaner_switch_entity=_env("CLEANER_SWITCH_ENTITY", ""),
        cleaner_power_entity=_env("CLEANER_POWER_ENTITY", ""),
        notify_telegram_service=_env("NOTIFY_TELEGRAM_SERVICE", ""),
        notify_email_service=_env("NOTIFY_EMAIL_SERVICE", ""),
        email_target=_env("EMAIL_TARGET", ""),
        weekly_report_enabled=_env_bool("WEEKLY_REPORT_ENABLED", True),
        weekly_report_day=_env("WEEKLY_REPORT_DAY", "sun"),
        weekly_report_hour=_env_int("WEEKLY_REPORT_HOUR", 20),
        auto_emergency_stop=_env_bool("AUTO_EMERGENCY_STOP", False),
        first_minutes_window_s=_env_int("FIRST_MINUTES_WINDOW_S", 300),
        auto_bootstrap_package=_env_bool("AUTO_BOOTSTRAP_PACKAGE", True),
        mqtt_host=_env("MQTT_HOST", ""),
        mqtt_port=_env_int("MQTT_PORT", 1883),
        mqtt_username=_env("MQTT_USERNAME", ""),
        mqtt_password=_env("MQTT_PASSWORD", ""),
        supervisor_token=os.environ.get("SUPERVISOR_TOKEN", ""),
    )


SETTINGS = load_settings()
