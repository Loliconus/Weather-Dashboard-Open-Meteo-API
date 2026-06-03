# =============================================================
# ПУТЬ        : src/weather_dashboard/meteo/__init__.py
# ОБОЗНАЧЕНИЕ : WD.METEO.00
# НАИМЕНОВАНИЕ: Инициализация слоя клиентов Open-Meteo
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : open_meteo, geocoding
# =============================================================
# Назначение:
#   Экспортирует публичный API слоя meteo:
#   ForecastClient, GeocodingClient, их исключения.
#   Проверка: from weather_dashboard.meteo import ForecastClient
# =============================================================

from __future__ import annotations

from weather_dashboard.meteo.geocoding import (
    GeocodingClient,
    GeocodingError,
    GeocodingResult,
)
from weather_dashboard.meteo.open_meteo import (
    ForecastClient,
    ForecastError,
    ForecastResponse,
)

__all__ = [
    "ForecastClient",
    "ForecastError",
    "ForecastResponse",
    "GeocodingClient",
    "GeocodingError",
    "GeocodingResult",
]