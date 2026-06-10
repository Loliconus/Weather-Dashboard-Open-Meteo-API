"""Общие фикстуры pytest для всех тестов."""

from __future__ import annotations

import pytest

from weather_dashboard.api.models import (
    AirQualityResponse,
    ForecastResponse,
    HourlyForecast,
)

# ---------------------------------------------------------------------------
# Фабрики сырых dict-ответов API (для respx-моков)
# ---------------------------------------------------------------------------


def make_forecast_dict(
    lat: float = 55.7558,
    lon: float = 37.6173,
    timezone: str = "Europe/Moscow",
    n_hours: int = 48,
    n_days: int = 7,
) -> dict:
    """Строит минимально корректный dict-ответ /v1/forecast."""
    # БЫЛО:   h % 24  → все timestamps = 2026-06-10T*  (один день!)
    # СТАЛО:  правильная дата = 10 + h//24
    hours = [f"2026-06-{10 + h // 24:02d}T{h % 24:02d}:00" for h in range(n_hours)]
    days = [f"2026-06-{10 + i:02d}" for i in range(n_days)]

    return {
        "latitude": lat,
        "longitude": lon,
        "timezone": timezone,
        "utc_offset_seconds": 10800,
        "generationtime_ms": 1.23,
        "current_units": {"temperature_2m": "°C"},
        "hourly_units": {
            "temperature_2m": "°C",
            "apparent_temperature": "°C",
            "precipitation": "mm",
            "rain": "mm",
            "snowfall": "cm",
            "precipitation_probability": "%",
            "wind_speed_10m": "m/s",
            "wind_direction_10m": "°",
            "wind_gusts_10m": "m/s",
            "relative_humidity_2m": "%",
            "dew_point_2m": "°C",
            "surface_pressure": "hPa",
            "shortwave_radiation": "W/m²",
            "uv_index": "",
            "cloud_cover": "%",
            "visibility": "m",
        },
        "daily_units": {
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_sum": "mm",
            "wind_speed_10m_max": "m/s",
            "uv_index_max": "",
            "sunrise": "iso8601",
            "sunset": "iso8601",
        },
        "current": {
            "time": "2026-06-10T12:00",
            "temperature_2m": 22.5,
            "apparent_temperature": 21.0,
            "wind_speed_10m": 4.5,
            "relative_humidity_2m": 55.0,
            "precipitation": 0.0,
            "weather_code": 1,
        },
        "hourly": {
            "time": hours,
            "temperature_2m": [20.0 + i * 0.1 for i in range(n_hours)],
            "apparent_temperature": [19.0 + i * 0.1 for i in range(n_hours)],
            "precipitation": [0.0] * n_hours,
            "rain": [0.0] * n_hours,
            "snowfall": [0.0] * n_hours,
            "precipitation_probability": [0] * n_hours,
            "wind_speed_10m": [4.0] * n_hours,
            "wind_direction_10m": [180.0] * n_hours,
            "wind_gusts_10m": [6.0] * n_hours,
            "relative_humidity_2m": [55.0] * n_hours,
            "dew_point_2m": [11.0] * n_hours,
            "surface_pressure": [1013.0] * n_hours,
            "shortwave_radiation": [
                200.0 if 6 <= (i % 24) <= 20 else 0.0 for i in range(n_hours)
            ],
            "uv_index": [3.0 if 6 <= (i % 24) <= 20 else 0.0 for i in range(n_hours)],
            "cloud_cover": [20.0] * n_hours,
            "visibility": [10000.0] * n_hours,
        },
        "daily": {
            "time": days,
            "temperature_2m_max": [25.0 + i for i in range(n_days)],
            "temperature_2m_min": [15.0 + i for i in range(n_days)],
            "precipitation_sum": [0.0] * n_days,
            "wind_speed_10m_max": [8.0] * n_days,
            "uv_index_max": [5.0] * n_days,
            "sunrise": [f"2026-06-{10 + i:02d}T04:30" for i in range(n_days)],
            "sunset": [f"2026-06-{10 + i:02d}T21:30" for i in range(n_days)],
        },
    }


def make_aq_dict(
    lat: float = 55.7558,
    lon: float = 37.6173,
    n_hours: int = 24,
) -> dict:
    """Строит минимально корректный dict-ответ /v1/air-quality."""
    hours = [f"2026-06-10T{h:02d}:00" for h in range(n_hours)]
    return {
        "latitude": lat,
        "longitude": lon,
        "timezone": "Europe/Moscow",
        "utc_offset_seconds": 10800,
        "generationtime_ms": 0.5,
        "hourly_units": {
            "pm10": "μg/m³",
            "pm2_5": "μg/m³",
            "carbon_monoxide": "μg/m³",
            "nitrogen_dioxide": "μg/m³",
            "ozone": "μg/m³",
            "european_aqi": "",
            "us_aqi": "",
        },
        "hourly": {
            "time": hours,
            "pm10": [15.0] * n_hours,
            "pm2_5": [8.0] * n_hours,
            "carbon_monoxide": [200.0] * n_hours,
            "nitrogen_dioxide": [12.0] * n_hours,
            "ozone": [60.0] * n_hours,
            "european_aqi": [22.0] * n_hours,
            "us_aqi": [25.0] * n_hours,
        },
    }


def make_elevation_dict(elevation: float = 144.0) -> dict:
    """Строит dict-ответ /v1/elevation."""
    return {"elevation": [elevation]}


def make_geocoding_dict(name: str = "Москва") -> dict:
    """Строит dict-ответ /v1/search."""
    return {
        "results": [
            {
                "id": 524901,
                "name": name,
                "latitude": 55.7558,
                "longitude": 37.6173,
                "country_code": "RU",
                "timezone": "Europe/Moscow",
                "elevation": 144.0,
                "admin1": "Москва",
            }
        ]
    }


# ---------------------------------------------------------------------------
# pytest-фикстуры dataclass-моделей
# ---------------------------------------------------------------------------


@pytest.fixture
def forecast_dict() -> dict:
    return make_forecast_dict()


@pytest.fixture
def forecast_response(forecast_dict) -> ForecastResponse:
    return ForecastResponse.from_dict(forecast_dict)


@pytest.fixture
def hourly_forecast(forecast_response) -> HourlyForecast:
    return forecast_response.hourly


@pytest.fixture
def aq_response() -> AirQualityResponse:
    return AirQualityResponse.from_dict(make_aq_dict())
