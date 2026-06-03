# =============================================================
# ПУТЬ        : tests/unit/test_normalizer.py
# ОБОЗНАЧЕНИЕ : WD.TEST.07
# НАИМЕНОВАНИЕ: Тесты нормализации временного ряда
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, weather_dashboard.calc.normalizer,
#               weather_dashboard.meteo.open_meteo
# =============================================================
# Назначение:
#   Покрывает ТЗ раздел 11.1 п.4 и 7.1:
#     - нормальная нормализация (все массивы одной длины)
#     - несоответствие длин → contradiction() + обрезка
#     - пустые массивы → безопасный возврат
#     - парсинг времени (ISO 8601 без TZ → UTC)
#   Проверка: pytest tests/unit/test_normalizer.py -v
# =============================================================

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.conftest import CapturingHandler, extract_extra
from weather_dashboard.calc.normalizer import (
    NormalizedForecast,
    _parse_times,
    _to_floats,
    _to_ints,
    normalize_forecast,
)
from weather_dashboard.meteo.open_meteo import ForecastResponse


# -------------------------------------------------------------
# Раздел 0. Фикстуры
# -------------------------------------------------------------


def _make_response(
    n_hourly: int = 4,
    n_daily: int = 2,
    temp_len: int | None = None,
) -> ForecastResponse:
    """Создать ForecastResponse с синтетическими данными."""
    times_h = [f"2026-06-0{1 + i // 24}T{i % 24:02d}:00" for i in range(n_hourly)]
    times_d = [f"2026-06-0{i + 1}" for i in range(n_daily)]
    t_len = temp_len if temp_len is not None else n_hourly

    return ForecastResponse(
        latitude=55.76,
        longitude=37.62,
        timezone="Europe/Moscow",
        hourly={
            "time": times_h,
            "temperature_2m": [float(i) for i in range(t_len)],
            "apparent_temperature": [float(i) + 1 for i in range(n_hourly)],
            "relative_humidity_2m": [60.0] * n_hourly,
            "dew_point_2m": [10.0] * n_hourly,
            "precipitation": [0.0] * n_hourly,
            "precipitation_probability": [20.0] * n_hourly,
            "weather_code": [0] * n_hourly,
            "wind_speed_10m": [5.0] * n_hourly,
            "wind_direction_10m": [180.0] * n_hourly,
            "wind_gusts_10m": [8.0] * n_hourly,
        },
        hourly_units={"temperature_2m": "°C", "wind_speed_10m": "km/h"},
        daily={
            "time": times_d,
            "temperature_2m_max": [25.0] * n_daily,
            "temperature_2m_min": [15.0] * n_daily,
            "apparent_temperature_max": [24.0] * n_daily,
            "apparent_temperature_min": [14.0] * n_daily,
            "precipitation_sum": [1.0] * n_daily,
            "precipitation_probability_max": [30.0] * n_daily,
            "sunrise": ["2026-06-01T04:00"] * n_daily,
            "sunset": ["2026-06-01T21:00"] * n_daily,
            "wind_gusts_10m_max": [10.0] * n_daily,
            "shortwave_radiation_sum": [20.0] * n_daily,
        },
        daily_units={"temperature_2m_max": "°C"},
        raw={},
    )


# -------------------------------------------------------------
# Раздел 1. Тесты вспомогательных функций
# -------------------------------------------------------------


@pytest.mark.unit()
def test_parse_times_valid_iso() -> None:
    """_parse_times корректно парсит ISO 8601 без TZ → UTC datetime."""
    result = _parse_times(["2026-06-03T00:00", "2026-06-03T01:00"])
    assert len(result) == 2
    assert result[0].tzinfo == timezone.utc
    assert result[0].hour == 0
    assert result[1].hour == 1


@pytest.mark.unit()
def test_parse_times_invalid_value_fallback() -> None:
    """_parse_times заменяет неразбираемое значение на datetime.min (не падает)."""
    result = _parse_times(["2026-06-03T00:00", "NOT_A_DATE"])
    assert len(result) == 2
    assert result[1] == datetime.min.replace(tzinfo=timezone.utc)


@pytest.mark.unit()
def test_parse_times_empty() -> None:
    """_parse_times с пустым списком → пустой список."""
    assert _parse_times([]) == []


@pytest.mark.unit()
def test_to_floats_converts_none() -> None:
    """_to_floats заменяет None на 0.0."""
    result = _to_floats([1.0, None, 3.0])
    assert result == [1.0, 0.0, 3.0]


@pytest.mark.unit()
def test_to_floats_converts_int() -> None:
    """_to_floats принимает int."""
    result = _to_floats([1, 2, 3])
    assert result == [1.0, 2.0, 3.0]


@pytest.mark.unit()
def test_to_ints_converts_none() -> None:
    """_to_ints заменяет None на 0."""
    result = _to_ints([1, None, 3])
    assert result == [1, 0, 3]


# -------------------------------------------------------------
# Раздел 2. Тесты normalize_forecast (нормальный путь)
# -------------------------------------------------------------


@pytest.mark.unit()
def test_normalize_returns_normalized_forecast() -> None:
    """normalize_forecast возвращает NormalizedForecast."""
    resp = _make_response(n_hourly=4, n_daily=2)
    result = normalize_forecast(resp)
    assert isinstance(result, NormalizedForecast)


@pytest.mark.unit()
def test_normalize_n_hourly_set() -> None:
    """n_hourly соответствует числу временных меток."""
    resp = _make_response(n_hourly=4, n_daily=2)
    result = normalize_forecast(resp)
    assert result.n_hourly == 4


@pytest.mark.unit()
def test_normalize_n_daily_set() -> None:
    """n_daily соответствует числу суточных меток."""
    resp = _make_response(n_hourly=4, n_daily=2)
    result = normalize_forecast(resp)
    assert result.n_daily == 2


@pytest.mark.unit()
def test_normalize_temperature_values() -> None:
    """temperature_2m содержит ожидаемые значения."""
    resp = _make_response(n_hourly=4)
    result = normalize_forecast(resp)
    assert result.temperature_2m == [0.0, 1.0, 2.0, 3.0]


@pytest.mark.unit()
def test_normalize_timezone_preserved() -> None:
    """timezone из ответа сохраняется в NormalizedForecast."""
    resp = _make_response()
    result = normalize_forecast(resp)
    assert result.timezone == "Europe/Moscow"


@pytest.mark.unit()
def test_normalize_hourly_units_preserved() -> None:
    """hourly_units из ответа сохраняются в NormalizedForecast."""
    resp = _make_response()
    result = normalize_forecast(resp)
    assert result.hourly_units.get("temperature_2m") == "°C"


# -------------------------------------------------------------
# Раздел 3. Тесты валидации длин (ТЗ 8.3)
# -------------------------------------------------------------


@pytest.mark.unit()
def test_normalize_mismatched_length_logs_contradiction(
    capturing_handler: CapturingHandler,
) -> None:
    """Несоответствие длин hourly-массивов → contradiction() в ledger (ТЗ 8.3)."""
    import logging
    from weather_dashboard.bootstrap.ledger import LedgerLogger

    ledger = LedgerLogger(corr_id="test-corr")
    # temperature_2m длиннее остальных на 10 — выходит за допуск
    resp = _make_response(n_hourly=4, temp_len=14)
    normalize_forecast(resp, ledger=ledger)

    contradiction_records = [
        r for r in capturing_handler.records
        if getattr(r, "kind", None) == "contradiction"
    ]
    assert contradiction_records, "contradiction() не вызван при расхождении длин"
    extra = extract_extra(contradiction_records[0])
    assert extra["subject"] == "normalizer.hourly_arrays"


@pytest.mark.unit()
def test_normalize_mismatched_length_truncates_to_min() -> None:
    """Несоответствие длин → все массивы обрезаются до минимума."""
    # temperature_2m длиннее — но все остальные длиной 4 → min=4
    resp = _make_response(n_hourly=4, temp_len=14)
    result = normalize_forecast(resp)
    # n_hourly = min всех длин = 4
    assert result.n_hourly <= 4
    assert len(result.temperature_2m) == result.n_hourly


@pytest.mark.unit()
def test_normalize_empty_hourly_safe() -> None:
    """Пустые hourly-данные → NormalizedForecast с n_hourly=0 (не падает)."""
    resp = ForecastResponse(
        latitude=0.0, longitude=0.0, timezone="UTC",
        hourly={}, hourly_units={}, daily={}, daily_units={}, raw={},
    )
    result = normalize_forecast(resp)
    assert result.n_hourly == 0
    assert result.temperature_2m == []