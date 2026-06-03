# =============================================================
# ПУТЬ        : src/weather_dashboard/calc/__init__.py
# ОБОЗНАЧЕНИЕ : WD.CALC.00
# НАИМЕНОВАНИЕ: Инициализация расчётного слоя
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : metrics, windows, thresholds, normalizer
# =============================================================
# Назначение:
#   Экспортирует публичный API расчётного слоя.
#   Проверка: from weather_dashboard.calc import normalize_forecast
# =============================================================

from __future__ import annotations

from weather_dashboard.calc.metrics import (
    ComfortCategory,
    ComfortIndex,
    DailyMetrics,
    calculate_comfort_index,
    calculate_daily_metrics,
)
from weather_dashboard.calc.normalizer import NormalizedForecast, normalize_forecast
from weather_dashboard.calc.thresholds import ThresholdAlert, check_thresholds
from weather_dashboard.calc.windows import WalkWindow, find_walk_window

__all__ = [
    "NormalizedForecast",
    "normalize_forecast",
    "DailyMetrics",
    "calculate_daily_metrics",
    "ComfortIndex",
    "ComfortCategory",
    "calculate_comfort_index",
    "WalkWindow",
    "find_walk_window",
    "ThresholdAlert",
    "check_thresholds",
]