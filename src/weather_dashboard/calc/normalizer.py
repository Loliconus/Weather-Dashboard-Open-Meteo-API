# =============================================================
# ПУТЬ        : src/weather_dashboard/calc/normalizer.py
# ОБОЗНАЧЕНИЕ : WD.CALC.01
# НАИМЕНОВАНИЕ: Нормализация временного ряда Open-Meteo
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : dataclasses, datetime, weather_dashboard.meteo.open_meteo,
#               weather_dashboard.bootstrap.ledger
# =============================================================
# Назначение:
#   normalize_forecast() приводит ForecastResponse к NormalizedForecast:
#     - единая шкала времени (список datetime)
#     - все hourly-массивы одинаковой длины (ТЗ 7.1)
#     - явные единицы измерения из hourly_units / daily_units
#     - contradiction() при несоответствии длин (ТЗ 8.3)
#   Проверка: pytest tests/unit/test_normalizer.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.meteo.open_meteo import ForecastResponse


# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_EXPECTED_HOURLY_LEN: int = 168          # 7 дней × 24 часа (ТЗ 4.1)
_LENGTH_MISMATCH_TOLERANCE: int = 1      # допуск в 1 элемент


# -------------------------------------------------------------
# Раздел 1. Структура нормализованных данных
# -------------------------------------------------------------


@dataclass
class NormalizedForecast:
    """Нормализованный прогноз — внутренний формат расчётного слоя.

    Все массивы hourly гарантированно одной длины.
    Временная шкала — список datetime с tzinfo UTC.
    Единицы измерения доступны через hourly_units / daily_units.
    """

    # Временная шкала
    hourly_times: list[datetime] = field(default_factory=list)
    daily_times: list[datetime] = field(default_factory=list)

    # Почасовые данные (ТЗ 4.1)
    temperature_2m: list[float] = field(default_factory=list)
    apparent_temperature: list[float] = field(default_factory=list)
    relative_humidity_2m: list[float] = field(default_factory=list)
    dew_point_2m: list[float] = field(default_factory=list)
    precipitation: list[float] = field(default_factory=list)
    precipitation_probability: list[float] = field(default_factory=list)
    weather_code: list[int] = field(default_factory=list)
    wind_speed_10m: list[float] = field(default_factory=list)
    wind_direction_10m: list[float] = field(default_factory=list)
    wind_gusts_10m: list[float] = field(default_factory=list)

    # Суточные данные (ТЗ 4.1)
    temperature_2m_max: list[float] = field(default_factory=list)
    temperature_2m_min: list[float] = field(default_factory=list)
    apparent_temperature_max: list[float] = field(default_factory=list)
    apparent_temperature_min: list[float] = field(default_factory=list)
    precipitation_sum: list[float] = field(default_factory=list)
    precipitation_probability_max: list[float] = field(default_factory=list)
    sunrise: list[str] = field(default_factory=list)
    sunset: list[str] = field(default_factory=list)
    wind_gusts_10m_max: list[float] = field(default_factory=list)
    shortwave_radiation_sum: list[float] = field(default_factory=list)

    # Метаданные
    timezone: str = ""
    hourly_units: dict[str, str] = field(default_factory=dict)
    daily_units: dict[str, str] = field(default_factory=dict)
    n_hourly: int = 0   # итоговая длина hourly-ряда
    n_daily: int = 0    # итоговая длина daily-ряда


# -------------------------------------------------------------
# Раздел 2. Нормализация
# -------------------------------------------------------------


def normalize_forecast(
    response: ForecastResponse,
    ledger: LedgerLogger | None = None,
) -> NormalizedForecast:
    """Нормализовать ForecastResponse в NormalizedForecast.

    Шаги:
        1. Парсинг временных меток из hourly["time"] и daily["time"].
        2. Извлечение числовых массивов с приведением типов.
        3. Проверка длин всех hourly-массивов (ТЗ 7.1, 8.3).
        4. Обрезка до минимальной длины при рассогласовании.

    Args:
        response: Ответ ForecastClient.fetch().
        ledger:   Опциональный LedgerLogger для фиксации событий.

    Returns:
        NormalizedForecast с согласованными массивами.
    """
    norm = NormalizedForecast(
        timezone=response.timezone,
        hourly_units=dict(response.hourly_units),
        daily_units=dict(response.daily_units),
    )

    # -- Шаг 1: временные метки --------------------------------
    norm.hourly_times = _parse_times(response.hourly.get("time", []))
    norm.daily_times = _parse_times(response.daily.get("time", []))

    # -- Шаг 2: извлечение hourly-массивов ---------------------
    h = response.hourly
    norm.temperature_2m = _to_floats(h.get("temperature_2m", []))
    norm.apparent_temperature = _to_floats(h.get("apparent_temperature", []))
    norm.relative_humidity_2m = _to_floats(h.get("relative_humidity_2m", []))
    norm.dew_point_2m = _to_floats(h.get("dew_point_2m", []))
    norm.precipitation = _to_floats(h.get("precipitation", []))
    norm.precipitation_probability = _to_floats(h.get("precipitation_probability", []))
    norm.weather_code = _to_ints(h.get("weather_code", []))
    norm.wind_speed_10m = _to_floats(h.get("wind_speed_10m", []))
    norm.wind_direction_10m = _to_floats(h.get("wind_direction_10m", []))
    norm.wind_gusts_10m = _to_floats(h.get("wind_gusts_10m", []))

    # -- Шаг 3: извлечение daily-массивов ---------------------
    d = response.daily
    norm.temperature_2m_max = _to_floats(d.get("temperature_2m_max", []))
    norm.temperature_2m_min = _to_floats(d.get("temperature_2m_min", []))
    norm.apparent_temperature_max = _to_floats(d.get("apparent_temperature_max", []))
    norm.apparent_temperature_min = _to_floats(d.get("apparent_temperature_min", []))
    norm.precipitation_sum = _to_floats(d.get("precipitation_sum", []))
    norm.precipitation_probability_max = _to_floats(d.get("precipitation_probability_max", []))
    norm.sunrise = [str(x) for x in d.get("sunrise", [])]
    norm.sunset = [str(x) for x in d.get("sunset", [])]
    norm.wind_gusts_10m_max = _to_floats(d.get("wind_gusts_10m_max", []))
    norm.shortwave_radiation_sum = _to_floats(d.get("shortwave_radiation_sum", []))

    # -- Шаг 4: проверка и выравнивание длин hourly ------------
    norm = _validate_and_align_lengths(norm, ledger)

    norm.n_hourly = len(norm.hourly_times)
    norm.n_daily = len(norm.daily_times)

    return norm


# -------------------------------------------------------------
# Раздел 3. Вспомогательные функции
# -------------------------------------------------------------


def _parse_times(raw: list[Any]) -> list[datetime]:
    """Разобрать список строк ISO 8601 в список datetime (UTC).

    Неразбираемые строки заменяются на datetime.min (не ломают ряд).
    """
    result: list[datetime] = []
    for item in raw:
        try:
            # Open-Meteo отдаёт формат "2026-06-03T00:00" (без TZ)
            # Трактуем как UTC согласно документации
            dt = datetime.fromisoformat(str(item))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            result.append(dt)
        except (ValueError, TypeError):
            result.append(datetime.min.replace(tzinfo=timezone.utc))
    return result


def _to_floats(raw: list[Any]) -> list[float]:
    """Привести список значений к list[float]. None → 0.0."""
    result: list[float] = []
    for v in raw:
        try:
            result.append(float(v) if v is not None else 0.0)
        except (TypeError, ValueError):
            result.append(0.0)
    return result


def _to_ints(raw: list[Any]) -> list[int]:
    """Привести список значений к list[int]. None → 0."""
    result: list[int] = []
    for v in raw:
        try:
            result.append(int(v) if v is not None else 0)
        except (TypeError, ValueError):
            result.append(0)
    return result


def _validate_and_align_lengths(
    norm: NormalizedForecast,
    ledger: LedgerLogger | None,
) -> NormalizedForecast:
    """Проверить длины hourly-массивов и выровнять при расхождении.

    Ожидаемая длина: len(hourly_times).
    При расхождении > _LENGTH_MISMATCH_TOLERANCE фиксирует
    contradiction() и обрезает ВСЕ массивы до min_len (ТЗ 8.3).

    Обрабатывает оба случая:
      - массив КОРОЧЕ ref_len (min_len < ref_len → обрезаем остальных до него)
      - массив ДЛИННЕЕ ref_len (min_len = ref_len, но массив нужно обрезать)
    В обоих случаях условие срабатывания — наличие mismatched (не min_len < ref_len).
    """
    ref_len = len(norm.hourly_times)
    if ref_len == 0:
        return norm

    hourly_arrays: dict[str, list[Any]] = {
        "temperature_2m": norm.temperature_2m,
        "apparent_temperature": norm.apparent_temperature,
        "relative_humidity_2m": norm.relative_humidity_2m,
        "dew_point_2m": norm.dew_point_2m,
        "precipitation": norm.precipitation,
        "precipitation_probability": norm.precipitation_probability,
        "weather_code": norm.weather_code,
        "wind_speed_10m": norm.wind_speed_10m,
        "wind_direction_10m": norm.wind_direction_10m,
        "wind_gusts_10m": norm.wind_gusts_10m,
    }

    mismatched: list[str] = []
    min_len = ref_len

    for name, arr in hourly_arrays.items():
        if len(arr) == 0:
            continue
        if abs(len(arr) - ref_len) > _LENGTH_MISMATCH_TOLERANCE:
            mismatched.append(f"{name}(len={len(arr)})")
        min_len = min(min_len, len(arr))

    if mismatched and ledger:
        ledger.contradiction(
            subject="normalizer.hourly_arrays",
            thesis=f"hourly[time] имеет длину {ref_len}",
            antithesis=f"массивы имеют другую длину: {', '.join(mismatched)}",
            invariant="все hourly-массивы должны быть одинаковой длины (ТЗ 7.1)",
            resolution=f"все массивы обрезаны до длины {min_len}",
            mismatched_fields=mismatched,
        )

    # ИСПРАВЛЕНИЕ: обрезаем при любом несоответствии (mismatched),
    # а не только когда min_len < ref_len.
    # Это покрывает случай когда массив ДЛИННЕЕ ref_len:
    # min_len остаётся равным ref_len, но сам массив нужно усечь до ref_len.
    if mismatched:
        norm.hourly_times = norm.hourly_times[:min_len]
        norm.temperature_2m = norm.temperature_2m[:min_len]
        norm.apparent_temperature = norm.apparent_temperature[:min_len]
        norm.relative_humidity_2m = norm.relative_humidity_2m[:min_len]
        norm.dew_point_2m = norm.dew_point_2m[:min_len]
        norm.precipitation = norm.precipitation[:min_len]
        norm.precipitation_probability = norm.precipitation_probability[:min_len]
        norm.weather_code = norm.weather_code[:min_len]
        norm.wind_speed_10m = norm.wind_speed_10m[:min_len]
        norm.wind_direction_10m = norm.wind_direction_10m[:min_len]
        norm.wind_gusts_10m = norm.wind_gusts_10m[:min_len]

    return norm