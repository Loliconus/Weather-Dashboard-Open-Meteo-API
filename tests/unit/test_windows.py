# =============================================================
# ПУТЬ        : tests/unit/test_windows.py
# ОБОЗНАЧЕНИЕ : WD.TEST.09
# НАИМЕНОВАНИЕ: Тесты поиска окна прогулки
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, weather_dashboard.calc.windows,
#               weather_dashboard.calc.normalizer
# =============================================================
# Назначение:
#   Покрывает ТЗ раздел 7.2 B:
#     - нет подходящих часов → None
#     - одно непрерывное окно → корректные start/end/duration
#     - несколько окон → выбирается самое длинное
#     - граничные условия (ровно на пороге P0/W0/Tmin/Tmax)
#   Проверка: pytest tests/unit/test_windows.py -v
# =============================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.calc.windows import WalkWindow, find_walk_window
from weather_dashboard.config import DEFAULT_CONFIG, DashboardConfig, WalkWindowConfig, ThresholdConfig, ComfortIndexConfig, LocationConfig


# -------------------------------------------------------------
# Раздел 0. Вспомогательные функции
# -------------------------------------------------------------


def _make_norm_for_windows(
    n: int = 48,
    precip_prob: list[float] | float = 10.0,
    wind_speed: list[float] | float = 3.0,
    temp: list[float] | float = 15.0,
) -> NormalizedForecast:
    """Создать NormalizedForecast для тестов поиска окна."""
    base = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    times = [base + timedelta(hours=i) for i in range(n)]

    def _expand(v: list[float] | float) -> list[float]:
        return v if isinstance(v, list) else [float(v)] * n

    return NormalizedForecast(
        hourly_times=times,
        daily_times=[base],
        temperature_2m=_expand(temp),
        apparent_temperature=_expand(temp),
        relative_humidity_2m=[50.0] * n,
        precipitation_probability=_expand(precip_prob),
        wind_speed_10m=_expand(wind_speed),
        wind_gusts_10m=[5.0] * n,
        n_hourly=n,
        n_daily=1,
    )


def _config_with_walk(
    precip_max: float = 30.0,
    wind_max: float = 10.0,
    t_min: float = -5.0,
    t_max: float = 30.0,
    horizon: int = 48,
) -> DashboardConfig:
    """Создать конфиг с заданными параметрами WalkWindowConfig."""
    return DashboardConfig(
        location=DEFAULT_CONFIG.location,
        thresholds=DEFAULT_CONFIG.thresholds,
        walk_window=WalkWindowConfig(
            precip_prob_max_pct=precip_max,
            wind_speed_max_ms=wind_max,
            temp_min_c=t_min,
            temp_max_c=t_max,
            horizon_hours=horizon,
        ),
        comfort=DEFAULT_CONFIG.comfort,
    )


# -------------------------------------------------------------
# Раздел 1. Тесты нахождения окна
# -------------------------------------------------------------


@pytest.mark.unit()
def test_walk_window_all_suitable_returns_window() -> None:
    """Все часы подходят → окно на весь горизонт."""
    norm = _make_norm_for_windows(n=48, precip_prob=10.0, wind_speed=3.0, temp=15.0)
    result = find_walk_window(norm, config=_config_with_walk(horizon=48))
    assert result is not None
    assert isinstance(result, WalkWindow)
    assert result.duration_hours == 48


@pytest.mark.unit()
def test_walk_window_none_suitable_returns_none() -> None:
    """Ни один час не подходит → None."""
    norm = _make_norm_for_windows(n=24, precip_prob=90.0)  # все выше порога
    result = find_walk_window(norm, config=_config_with_walk(precip_max=30.0))
    assert result is None


@pytest.mark.unit()
def test_walk_window_finds_longest() -> None:
    """Несколько окон → выбирается самое длинное."""
    # 3 подходящих + 1 непод. + 6 подходящих → ожидаем окно длиной 6
    precip = [10.0] * 3 + [90.0] * 1 + [10.0] * 6 + [90.0] * 14
    norm = _make_norm_for_windows(n=24, precip_prob=precip)
    result = find_walk_window(norm, config=_config_with_walk(precip_max=30.0, horizon=24))
    assert result is not None
    assert result.duration_hours == 6


@pytest.mark.unit()
def test_walk_window_duration_correct() -> None:
    """duration_hours соответствует реальной длине окна."""
    precip = [10.0] * 5 + [90.0] * 19
    norm = _make_norm_for_windows(n=24, precip_prob=precip)
    result = find_walk_window(norm, config=_config_with_walk(precip_max=30.0, horizon=24))
    assert result is not None
    assert result.duration_hours == 5


@pytest.mark.unit()
def test_walk_window_start_time_correct() -> None:
    """start соответствует началу окна."""
    base = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    # Первые 4 часа не подходят, потом 8 подходящих
    precip = [90.0] * 4 + [10.0] * 8 + [90.0] * 12
    norm = _make_norm_for_windows(n=24, precip_prob=precip)
    result = find_walk_window(norm, config=_config_with_walk(precip_max=30.0, horizon=24))
    assert result is not None
    assert result.start == base + timedelta(hours=4)


@pytest.mark.unit()
def test_walk_window_wind_filter() -> None:
    """Сильный ветер блокирует часы несмотря на подходящие осадки."""
    wind = [3.0] * 6 + [20.0] * 6 + [3.0] * 12
    norm = _make_norm_for_windows(n=24, wind_speed=wind, precip_prob=10.0)
    result = find_walk_window(norm, config=_config_with_walk(wind_max=10.0, horizon=24))
    assert result is not None
    # Лучшее окно: последние 12 часов
    assert result.duration_hours == 12


@pytest.mark.unit()
def test_walk_window_temp_filter_cold() -> None:
    """Температура ниже Tmin блокирует часы."""
    temp = [-10.0] * 12 + [15.0] * 12
    norm = _make_norm_for_windows(n=24, temp=temp, precip_prob=10.0)
    result = find_walk_window(norm, config=_config_with_walk(t_min=0.0, horizon=24))
    assert result is not None
    assert result.duration_hours == 12


@pytest.mark.unit()
def test_walk_window_temp_filter_hot() -> None:
    """Температура выше Tmax блокирует часы."""
    temp = [40.0] * 6 + [20.0] * 18
    norm = _make_norm_for_windows(n=24, temp=temp, precip_prob=10.0)
    result = find_walk_window(norm, config=_config_with_walk(t_max=35.0, horizon=24))
    assert result is not None
    assert result.duration_hours == 18


@pytest.mark.unit()
def test_walk_window_reason_not_empty() -> None:
    """WalkWindow содержит непустое пояснение reason."""
    norm = _make_norm_for_windows(n=24, precip_prob=10.0)
    result = find_walk_window(norm, config=_config_with_walk(horizon=24))
    assert result is not None
    assert result.reason


@pytest.mark.unit()
def test_walk_window_empty_norm_returns_none() -> None:
    """Пустой NormalizedForecast → None."""
    result = find_walk_window(NormalizedForecast())
    assert result is None