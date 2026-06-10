"""SSOT для всех URL и переменных Open-Meteo API.

Содержит:
- StrEnum-перечисления переменных (Forecast, AirQuality, единицы)
- Константы URL (дублируют config.py для статического доступа)
- Предопределённые наборы переменных DEFAULT_HOURLY, DEFAULT_DAILY, DEFAULT_CURRENT
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# URL-константы (дублируют config.py — для статических проверок / тестов)
# ---------------------------------------------------------------------------
FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
AIR_QUALITY_URL: str = "https://air-quality-api.open-meteo.com/v1/air-quality"
ELEVATION_URL: str = "https://api.open-meteo.com/v1/elevation"


# ---------------------------------------------------------------------------
# Единицы измерения
# ---------------------------------------------------------------------------
class WindUnit(StrEnum):
    """Единицы скорости ветра Open-Meteo API."""

    MS = "ms"  # м/с (дефолт для РФ-рынка)
    KMH = "kmh"  # км/ч
    MPH = "mph"  # мили/час
    KN = "kn"  # узлы


class TempUnit(StrEnum):
    """Единицы температуры Open-Meteo API."""

    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class PrecipUnit(StrEnum):
    """Единицы осадков Open-Meteo API."""

    MM = "mm"
    INCH = "inch"


# ---------------------------------------------------------------------------
# Hourly-переменные прогноза
# ---------------------------------------------------------------------------
class HourlyVariable(StrEnum):
    """Все доступные hourly-переменные endpoint /forecast."""

    TEMPERATURE_2M = "temperature_2m"
    APPARENT_TEMPERATURE = "apparent_temperature"
    PRECIPITATION = "precipitation"
    RAIN = "rain"
    SNOWFALL = "snowfall"
    PRECIPITATION_PROBABILITY = "precipitation_probability"
    WIND_SPEED_10M = "wind_speed_10m"
    WIND_DIRECTION_10M = "wind_direction_10m"
    WIND_GUSTS_10M = "wind_gusts_10m"
    RELATIVE_HUMIDITY_2M = "relative_humidity_2m"
    DEW_POINT_2M = "dew_point_2m"
    SURFACE_PRESSURE = "surface_pressure"
    SHORTWAVE_RADIATION = "shortwave_radiation"
    UV_INDEX = "uv_index"
    CLOUD_COVER = "cloud_cover"
    VISIBILITY = "visibility"


# ---------------------------------------------------------------------------
# Daily-переменные прогноза
# ---------------------------------------------------------------------------
class DailyVariable(StrEnum):
    """Все доступные daily-переменные endpoint /forecast."""

    TEMPERATURE_2M_MAX = "temperature_2m_max"
    TEMPERATURE_2M_MIN = "temperature_2m_min"
    PRECIPITATION_SUM = "precipitation_sum"
    WIND_SPEED_10M_MAX = "wind_speed_10m_max"
    UV_INDEX_MAX = "uv_index_max"
    SUNRISE = "sunrise"
    SUNSET = "sunset"


# ---------------------------------------------------------------------------
# Current-переменные прогноза
# ---------------------------------------------------------------------------
class CurrentVariable(StrEnum):
    """Все доступные current-переменные endpoint /forecast."""

    TEMPERATURE_2M = "temperature_2m"
    APPARENT_TEMPERATURE = "apparent_temperature"
    WIND_SPEED_10M = "wind_speed_10m"
    RELATIVE_HUMIDITY_2M = "relative_humidity_2m"
    PRECIPITATION = "precipitation"
    WEATHER_CODE = "weather_code"


# ---------------------------------------------------------------------------
# Air Quality переменные
# ---------------------------------------------------------------------------
class AirQualityVariable(StrEnum):
    """Переменные endpoint /air-quality."""

    PM10 = "pm10"
    PM2_5 = "pm2_5"
    CARBON_MONOXIDE = "carbon_monoxide"
    NITROGEN_DIOXIDE = "nitrogen_dioxide"
    OZONE = "ozone"
    EUROPEAN_AQI = "european_aqi"
    US_AQI = "us_aqi"


# ---------------------------------------------------------------------------
# Предопределённые наборы (SSOT — менять только здесь)
# ---------------------------------------------------------------------------
DEFAULT_HOURLY: tuple[HourlyVariable, ...] = (
    HourlyVariable.TEMPERATURE_2M,
    HourlyVariable.APPARENT_TEMPERATURE,
    HourlyVariable.PRECIPITATION,
    HourlyVariable.RAIN,
    HourlyVariable.SNOWFALL,
    HourlyVariable.PRECIPITATION_PROBABILITY,
    HourlyVariable.WIND_SPEED_10M,
    HourlyVariable.WIND_DIRECTION_10M,
    HourlyVariable.WIND_GUSTS_10M,
    HourlyVariable.RELATIVE_HUMIDITY_2M,
    HourlyVariable.DEW_POINT_2M,
    HourlyVariable.SURFACE_PRESSURE,
    HourlyVariable.SHORTWAVE_RADIATION,
    HourlyVariable.UV_INDEX,
    HourlyVariable.CLOUD_COVER,
    HourlyVariable.VISIBILITY,
)

DEFAULT_DAILY: tuple[DailyVariable, ...] = (
    DailyVariable.TEMPERATURE_2M_MAX,
    DailyVariable.TEMPERATURE_2M_MIN,
    DailyVariable.PRECIPITATION_SUM,
    DailyVariable.WIND_SPEED_10M_MAX,
    DailyVariable.UV_INDEX_MAX,
    DailyVariable.SUNRISE,
    DailyVariable.SUNSET,
)

DEFAULT_CURRENT: tuple[CurrentVariable, ...] = (
    CurrentVariable.TEMPERATURE_2M,
    CurrentVariable.APPARENT_TEMPERATURE,
    CurrentVariable.WIND_SPEED_10M,
    CurrentVariable.RELATIVE_HUMIDITY_2M,
    CurrentVariable.PRECIPITATION,
    CurrentVariable.WEATHER_CODE,
)

DEFAULT_AIR_QUALITY: tuple[AirQualityVariable, ...] = (
    AirQualityVariable.PM10,
    AirQualityVariable.PM2_5,
    AirQualityVariable.CARBON_MONOXIDE,
    AirQualityVariable.NITROGEN_DIOXIDE,
    AirQualityVariable.OZONE,
    AirQualityVariable.EUROPEAN_AQI,
    AirQualityVariable.US_AQI,
)
