"""Конфигурация приложения.

Единственный источник истины для всех настроек.
Загружается из переменных окружения с fallback на дефолты.
Frozen dataclass — иммутабельность гарантирована на уровне типов.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_float(key: str, default: float) -> float:
    """Читает float из env или возвращает default."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    """Читает int из env или возвращает default."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(key: str, default: str) -> str:
    """Читает str из env или возвращает default."""
    return os.environ.get(key, default)


def _env_path(key: str, default: str) -> Path:
    """Читает Path из env или возвращает default."""
    return Path(os.environ.get(key, default))


def _default_snapshot_locations() -> list[dict[str, object]]:
    """Три крупных города РФ в разных часовых поясах.

    Демонстрирует корректную работу с timezone:
    - Москва      UTC+3  (европейская часть)
    - Новосибирск UTC+7  (Западная Сибирь)
    - Владивосток UTC+10 (Дальний Восток)
    """
    return [
        {
            "name": "Москва",
            "latitude": 55.7558,
            "longitude": 37.6173,
            "timezone": "Europe/Moscow",
        },
        {
            "name": "Новосибирск",
            "latitude": 54.9885,
            "longitude": 82.9207,
            "timezone": "Asia/Novosibirsk",
        },
        {
            "name": "Владивосток",
            "latitude": 43.1056,
            "longitude": 131.8735,
            "timezone": "Asia/Vladivostok",
        },
    ]


@dataclass(frozen=True)
class AppConfig:
    """Конфигурация приложения.

    Все параметры загружаются из переменных окружения.
    Иммутабельна после создания (frozen=True).

    Examples:
        >>> cfg = AppConfig()
        >>> cfg.DEFAULT_LATITUDE
        55.7558
        >>> cfg.DEFAULT_CITY_NAME
        'Москва'
    """

    # ── Дефолтная локация (Москва) ──────────────────────────────────────
    DEFAULT_LATITUDE: float = field(
        default_factory=lambda: _env_float("DEFAULT_LATITUDE", 55.7558)
    )
    DEFAULT_LONGITUDE: float = field(
        default_factory=lambda: _env_float("DEFAULT_LONGITUDE", 37.6173)
    )
    DEFAULT_CITY_NAME: str = field(
        default_factory=lambda: _env_str("DEFAULT_CITY_NAME", "Москва")
    )
    DEFAULT_TIMEZONE: str = field(
        default_factory=lambda: _env_str("DEFAULT_TIMEZONE", "Europe/Moscow")
    )

    # ── Параметры прогноза ──────────────────────────────────────────────
    FORECAST_DAYS: int = field(default_factory=lambda: _env_int("FORECAST_DAYS", 7))
    TEMPERATURE_UNIT: str = field(
        default_factory=lambda: _env_str("TEMPERATURE_UNIT", "celsius")
    )
    WIND_SPEED_UNIT: str = field(
        default_factory=lambda: _env_str("WIND_SPEED_UNIT", "ms")
    )

    # ── Пути ────────────────────────────────────────────────────────────
    CACHE_DIR: Path = field(default_factory=lambda: _env_path("CACHE_DIR", ".cache"))
    OUTPUT_DIR: Path = field(default_factory=lambda: _env_path("OUTPUT_DIR", "docs"))

    # ── Логирование ─────────────────────────────────────────────────────
    LOG_LEVEL: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO"))

    # ── Snapshot-локации (CI) ───────────────────────────────────────────
    SNAPSHOT_LOCATIONS: list[dict[str, object]] = field(
        default_factory=_default_snapshot_locations
    )

    # ── Base URLs (SSOT — не хардкодить в client.py) ────────────────────
    FORECAST_BASE_URL: str = field(
        default_factory=lambda: _env_str(
            "FORECAST_BASE_URL", "https://api.open-meteo.com/v1"
        )
    )
    GEOCODING_BASE_URL: str = field(
        default_factory=lambda: _env_str(
            "GEOCODING_BASE_URL", "https://geocoding-api.open-meteo.com/v1"
        )
    )
    AIR_QUALITY_BASE_URL: str = field(
        default_factory=lambda: _env_str(
            "AIR_QUALITY_BASE_URL", "https://air-quality-api.open-meteo.com/v1"
        )
    )

    # ── User-Agent ───────────────────────────────────────────────────────
    USER_AGENT: str = (
        "Weather-Dashboard-Open-Meteo-API/1.0 "
        "(Loliconus; github.com/Loliconus/Weather-Dashboard-Open-Meteo-API)"
    )


# Синглтон — импортировать этот объект везде
config = AppConfig()
