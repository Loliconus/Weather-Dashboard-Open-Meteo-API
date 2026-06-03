# =============================================================
# ПУТЬ        : tests/unit/test_metrics.py
# ОБОЗНАЧЕНИЕ : WD.TEST.08
# НАИМЕНОВАНИЕ: Тесты расчёта суточных метрик и ComfortIndex
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, weather_dashboard.calc.metrics,
#               weather_dashboard.calc.normalizer
# =============================================================
# Назначение:
#   Покрывает ТЗ раздел 11.1 п.3:
#     - T_mean_day, T_amp_day, Rain_hours_50, Wind_gust_max
#     - ComfortIndex на синтетических данных (крайние случаи)
#     - категории ComfortIndex: комфортно / терпимо / тяжело
#   Все тесты на синтетических данных (без HTTP).
#   Проверка: pytest tests/unit/test_metrics.py -v
# =============================================================

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from weather_dashboard.calc.metrics import (
    ComfortCategory,
    ComfortIndex,
    DailyMetrics,
    calculate_comfort_index,
    calculate_daily_metrics,
    _ci_category,
)
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.config import DEFAULT_CONFIG


# -------------------------------------------------------------
# Раздел 0. Фикстуры
# -------------------------------------------------------------


def _make_norm(
    n: int = 24,
    temp: float = 20.0,
    apparent_temp: float = 20.0,
    humidity: float = 50.0,
    wind_speed: float = 3.0,
    wind_gusts: float = 5.0,
    precip_prob: float = 10.0,
    solar_sum: float = 15.0,
) -> NormalizedForecast:
    """Синтетический NormalizedForecast на n часов одного дня."""
    base = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    from datetime import timedelta

    return NormalizedForecast(
        hourly_times=[base + timedelta(hours=i) for i in range(n)],
        daily_times=[base],
        temperature_2m=[temp] * n,
        apparent_temperature=[apparent_temp] * n,
        relative_humidity_2m=[humidity] * n,
        dew_point_2m=[10.0] * n,
        precipitation=[0.0] * n,
        precipitation_probability=[precip_prob] * n,
        weather_code=[0] * n,
        wind_speed_10m=[wind_speed] * n,
        wind_direction_10m=[180.0] * n,
        wind_gusts_10m=[wind_gusts] * n,
        temperature_2m_max=[temp + 3.0],
        temperature_2m_min=[temp - 3.0],
        shortwave_radiation_sum=[solar_sum],
        n_hourly=n,
        n_daily=1,
    )


# -------------------------------------------------------------
# Раздел 1. Тесты DailyMetrics
# -------------------------------------------------------------


@pytest.mark.unit()
def test_t_mean_day_uniform() -> None:
    """T_mean_day = константная температура при однородном ряду."""
    norm = _make_norm(n=24, temp=20.0)
    metrics = calculate_daily_metrics(norm)
    assert len(metrics) == 1
    assert metrics[0].t_mean_day == pytest.approx(20.0, abs=0.01)


@pytest.mark.unit()
def test_t_mean_day_varied() -> None:
    """T_mean_day = среднее арифметическое (синтетические данные)."""
    from datetime import timedelta

    base = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    temps = list(range(24))  # 0..23
    norm = NormalizedForecast(
        hourly_times=[base + timedelta(hours=i) for i in range(24)],
        daily_times=[base],
        temperature_2m=temps,
        n_hourly=24, n_daily=1,
    )
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].t_mean_day == pytest.approx(sum(temps) / len(temps), abs=0.01)


@pytest.mark.unit()
def test_t_amp_day_constant_is_zero() -> None:
    """T_amp_day = 0 при постоянной температуре."""
    norm = _make_norm(n=24, temp=15.0)
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].t_amp_day == pytest.approx(0.0, abs=0.001)


@pytest.mark.unit()
def test_t_amp_day_varied() -> None:
    """T_amp_day = max - min при известных данных."""
    from datetime import timedelta

    base = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    temps = [10.0] * 12 + [25.0] * 12  # min=10, max=25, amp=15
    norm = NormalizedForecast(
        hourly_times=[base + timedelta(hours=i) for i in range(24)],
        daily_times=[base],
        temperature_2m=temps,
        n_hourly=24, n_daily=1,
    )
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].t_amp_day == pytest.approx(15.0, abs=0.01)


@pytest.mark.unit()
def test_rain_hours_50_none_above_threshold() -> None:
    """Rain_hours_50 = 0 когда все вероятности ниже 50%."""
    norm = _make_norm(n=24, precip_prob=30.0)
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].rain_hours_50 == 0


@pytest.mark.unit()
def test_rain_hours_50_all_above_threshold() -> None:
    """Rain_hours_50 = 24 когда все вероятности выше 50%."""
    norm = _make_norm(n=24, precip_prob=80.0)
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].rain_hours_50 == 24


@pytest.mark.unit()
def test_rain_hours_50_exactly_at_threshold() -> None:
    """Rain_hours_50 = 24 при вероятности ровно 50% (включительно)."""
    norm = _make_norm(n=24, precip_prob=50.0)
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].rain_hours_50 == 24


@pytest.mark.unit()
def test_wind_gust_max_correct() -> None:
    """Wind_gust_max = максимум порывов за сутки."""
    norm = _make_norm(n=24, wind_gusts=12.5)
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].wind_gust_max == pytest.approx(12.5, abs=0.01)


@pytest.mark.unit()
def test_solar_sum_from_daily() -> None:
    """Solar_sum берётся из daily shortwave_radiation_sum."""
    norm = _make_norm(solar_sum=18.7)
    metrics = calculate_daily_metrics(norm)
    assert metrics[0].solar_sum == pytest.approx(18.7, abs=0.01)


@pytest.mark.unit()
def test_empty_norm_returns_empty_list() -> None:
    """Пустой NormalizedForecast → пустой список метрик."""
    norm = NormalizedForecast()
    metrics = calculate_daily_metrics(norm)
    assert metrics == []


# -------------------------------------------------------------
# Раздел 2. Тесты ComfortIndex
# -------------------------------------------------------------


@pytest.mark.unit()
def test_comfort_ideal_conditions() -> None:
    """Идеальные условия (t=22, rh=50%, ws=0, pp=0) → CI ≈ 100."""
    norm = _make_norm(
        apparent_temp=22.0,
        humidity=50.0,
        wind_speed=0.0,
        precip_prob=0.0,
    )
    ci = calculate_comfort_index(norm)
    assert ci.value == pytest.approx(100.0, abs=1.0)
    assert ci.category == ComfortCategory.COMFORTABLE


@pytest.mark.unit()
def test_comfort_category_comfortable() -> None:
    """CI ≥ 70 → категория COMFORTABLE."""
    assert _ci_category(70.0) == ComfortCategory.COMFORTABLE
    assert _ci_category(100.0) == ComfortCategory.COMFORTABLE


@pytest.mark.unit()
def test_comfort_category_tolerable() -> None:
    """40 ≤ CI < 70 → категория TOLERABLE."""
    assert _ci_category(40.0) == ComfortCategory.TOLERABLE
    assert _ci_category(69.9) == ComfortCategory.TOLERABLE


@pytest.mark.unit()
def test_comfort_category_hard() -> None:
    """CI < 40 → категория HARD."""
    assert _ci_category(39.9) == ComfortCategory.HARD
    assert _ci_category(0.0) == ComfortCategory.HARD


@pytest.mark.unit()
def test_comfort_high_humidity_reduces_ci() -> None:
    """Высокая влажность (90%) снижает CI относительно нормальной (50%)."""
    norm_low = _make_norm(humidity=50.0, apparent_temp=22.0)
    norm_high = _make_norm(humidity=90.0, apparent_temp=22.0)
    ci_low = calculate_comfort_index(norm_low)
    ci_high = calculate_comfort_index(norm_high)
    assert ci_high.value < ci_low.value


@pytest.mark.unit()
def test_comfort_high_wind_reduces_ci() -> None:
    """Сильный ветер снижает CI относительно безветрия."""
    norm_calm = _make_norm(wind_speed=2.0, apparent_temp=22.0)
    norm_windy = _make_norm(wind_speed=20.0, apparent_temp=22.0)
    ci_calm = calculate_comfort_index(norm_calm)
    ci_windy = calculate_comfort_index(norm_windy)
    assert ci_windy.value < ci_calm.value


@pytest.mark.unit()
def test_comfort_high_precip_prob_reduces_ci() -> None:
    """Высокая вероятность осадков снижает CI."""
    norm_dry = _make_norm(precip_prob=0.0, apparent_temp=22.0)
    norm_wet = _make_norm(precip_prob=100.0, apparent_temp=22.0)
    ci_dry = calculate_comfort_index(norm_dry)
    ci_wet = calculate_comfort_index(norm_wet)
    assert ci_wet.value < ci_dry.value


@pytest.mark.unit()
def test_comfort_ci_never_below_zero() -> None:
    """CI никогда не опускается ниже 0 (clamped)."""
    norm = _make_norm(
        apparent_temp=-30.0,
        humidity=100.0,
        wind_speed=30.0,
        precip_prob=100.0,
    )
    ci = calculate_comfort_index(norm)
    assert ci.value >= 0.0


@pytest.mark.unit()
def test_comfort_ci_never_above_100() -> None:
    """CI никогда не превышает 100 (clamped)."""
    norm = _make_norm(
        apparent_temp=22.0,
        humidity=30.0,
        wind_speed=0.0,
        precip_prob=0.0,
    )
    ci = calculate_comfort_index(norm)
    assert ci.value <= 100.0


@pytest.mark.unit()
def test_comfort_hours_used() -> None:
    """hours_used равен числу реально использованных часов."""
    norm = _make_norm(n=24)
    ci = calculate_comfort_index(norm, hours=12)
    assert ci.hours_used == 12


@pytest.mark.unit()
def test_comfort_empty_norm_returns_hard() -> None:
    """Пустой NormalizedForecast → CI=0, HARD."""
    norm = NormalizedForecast()
    ci = calculate_comfort_index(norm)
    assert ci.value == 0.0
    assert ci.category == ComfortCategory.HARD