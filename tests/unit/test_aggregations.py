"""Тесты aggregations.py."""

from __future__ import annotations

import warnings

import pytest

from tests.conftest import make_forecast_dict
from weather_dashboard.api.models import ForecastResponse, HourlyForecast
from weather_dashboard.processing.aggregations import (
    compute_all,
    daily_temperature_range,
    dominant_wind_direction,
    max_uv_index,
    precipitation_type,
    sunshine_hours,
    total_precipitation,
)


@pytest.fixture
def hourly_48h() -> HourlyForecast:
    return ForecastResponse.from_dict(make_forecast_dict(n_hours=48)).hourly


@pytest.fixture
def hourly_with_none() -> HourlyForecast:
    """HourlyForecast с None в температуре."""
    d = make_forecast_dict(n_hours=24)
    d["hourly"]["temperature_2m"][0] = None
    d["hourly"]["temperature_2m"][1] = None
    return ForecastResponse.from_dict(d).hourly


@pytest.fixture
def hourly_cross_zero_wind() -> HourlyForecast:
    """Ветер 350°/350°/10°/10° для теста векторного среднего."""
    d = make_forecast_dict(n_hours=24)
    dirs = [350.0, 350.0, 10.0, 10.0] + [0.0] * 20
    d["hourly"]["wind_direction_10m"] = dirs
    return ForecastResponse.from_dict(d).hourly


class TestDailyTemperatureRange:
    def test_returns_one_entry_per_day(self, hourly_48h):
        result = daily_temperature_range(hourly_48h)
        assert len(result) == 2  # 48 часов = 2 суток

    def test_min_less_than_max(self, hourly_48h):
        for _, t_min, t_max, _ in daily_temperature_range(hourly_48h):
            assert t_min <= t_max

    def test_mean_between_min_max(self, hourly_48h):
        for _, t_min, t_max, t_mean in daily_temperature_range(hourly_48h):
            assert t_min <= t_mean <= t_max

    def test_none_values_skipped(self, hourly_with_none):
        result = daily_temperature_range(hourly_with_none)
        assert len(result) >= 1
        for _, t_min, t_max, t_mean in result:
            assert t_min is not None
            assert t_max is not None

    def test_incomplete_day_warns(self):
        """Менее 24 часов → warnings.warn."""
        d = make_forecast_dict(n_hours=10)
        hourly = ForecastResponse.from_dict(d).hourly
        with pytest.warns(UserWarning, match="Неполные"):
            daily_temperature_range(hourly)

    def test_result_is_float(self, hourly_48h):
        for _, t_min, t_max, t_mean in daily_temperature_range(hourly_48h):
            assert isinstance(t_min, float)
            assert isinstance(t_max, float)
            assert isinstance(t_mean, float)


class TestTotalPrecipitation:
    def test_zero_precip(self, hourly_48h):
        result = total_precipitation(hourly_48h)
        for v in result.values():
            assert v == 0.0

    def test_none_treated_as_zero(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["precipitation"] = [None] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = total_precipitation(hourly)
        for v in result.values():
            assert v == 0.0

    def test_sums_correctly(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["precipitation"] = [1.0] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = total_precipitation(hourly)
        for v in result.values():
            assert abs(v - 24.0) < 0.01

    def test_returns_float(self, hourly_48h):
        for v in total_precipitation(hourly_48h).values():
            assert isinstance(v, float)


class TestDominantWindDirection:
    def test_cross_zero_degrees(self, hourly_cross_zero_wind):
        """
        [350°, 350°, 10°, 10°] → ≈ 0°, а не 180°.
        Векторное среднее корректно обрабатывает переход через 0°.
        """
        result = dominant_wind_direction(hourly_cross_zero_wind)
        assert result  # не пустой
        for v in result.values():
            # Результат должен быть близко к 0° (допуск ±30°)
            assert v <= 30.0 or v >= 330.0, (
                f"Ожидалось ≈ 0°, получено {v}°"
            )

    def test_uniform_south(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["wind_direction_10m"] = [180.0] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = dominant_wind_direction(hourly)
        for v in result.values():
            assert abs(v - 180.0) < 1.0

    def test_all_none_returns_zero(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["wind_direction_10m"] = [None] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = dominant_wind_direction(hourly)
        for v in result.values():
            assert v == 0.0

    def test_result_in_0_360(self, hourly_48h):
        for v in dominant_wind_direction(hourly_48h).values():
            assert 0.0 <= v < 360.0


class TestMaxUVIndex:
    def test_daytime_only(self, hourly_48h):
        """UV берётся только из дневных часов (06:00–20:00)."""
        result = max_uv_index(hourly_48h)
        for v in result.values():
            assert v >= 0.0

    def test_all_none_returns_zero(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["uv_index"] = [None] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = max_uv_index(hourly)
        for v in result.values():
            assert v == 0.0


class TestSunshineHours:
    def test_above_threshold_counted(self):
        """Часы с radiation > 120 считаются солнечными."""
        d = make_forecast_dict(n_hours=24)
        # Делаем 8 дневных часов солнечными (> 120 Вт/м²)
        radiation = [0.0] * 24
        for i in range(8, 16):
            radiation[i] = 300.0
        d["hourly"]["shortwave_radiation"] = radiation
        hourly = ForecastResponse.from_dict(d).hourly
        result = sunshine_hours(hourly)
        for v in result.values():
            assert v == 8.0

    def test_none_skipped(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["shortwave_radiation"] = [None] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = sunshine_hours(hourly)
        for v in result.values():
            assert v == 0.0


class TestPrecipitationType:
    def test_no_precipitation(self, hourly_48h):
        result = precipitation_type(hourly_48h)
        for v in result.values():
            assert v == "none"

    def test_rain_dominant(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["precipitation"] = [2.0] * 24
        d["hourly"]["rain"]          = [2.0] * 24
        d["hourly"]["snowfall"]      = [0.0] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = precipitation_type(hourly)
        for v in result.values():
            assert v == "rain"

    def test_snow_dominant(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["precipitation"] = [2.0] * 24
        d["hourly"]["rain"]          = [0.0] * 24
        d["hourly"]["snowfall"]      = [2.0] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = precipitation_type(hourly)
        for v in result.values():
            assert v == "snow"

    def test_mixed(self):
        d = make_forecast_dict(n_hours=24)
        d["hourly"]["precipitation"] = [2.0] * 24
        d["hourly"]["rain"]          = [1.0] * 24
        d["hourly"]["snowfall"]      = [1.0] * 24
        hourly = ForecastResponse.from_dict(d).hourly
        result = precipitation_type(hourly)
        for v in result.values():
            assert v == "mixed"


class TestComputeAll:
    def test_returns_list(self, hourly_48h):
        result = compute_all(hourly_48h)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_sorted_by_date(self, hourly_48h):
        result = compute_all(hourly_48h)
        dates = [a.date for a in result]
        assert dates == sorted(dates)

    def test_aggregate_fields(self, hourly_48h):
        result = compute_all(hourly_48h)
        for agg in result:
            assert agg.temp_min <= agg.temp_max
            assert agg.total_precipitation >= 0.0
            assert 0.0 <= agg.dominant_wind_direction < 360.0
            assert agg.sunshine_hours >= 0.0
            assert agg.precipitation_type in ("none","rain","snow","mixed")