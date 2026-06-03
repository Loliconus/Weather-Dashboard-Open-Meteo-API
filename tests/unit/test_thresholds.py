# =============================================================
# ПУТЬ        : tests/unit/test_thresholds.py
# ОБОЗНАЧЕНИЕ : WD.TEST.10
# НАИМЕНОВАНИЕ: Тесты пороговых предупреждений
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, weather_dashboard.calc.thresholds,
#               weather_dashboard.calc.normalizer
# =============================================================
# Назначение:
#   Покрывает ТЗ раздел 7.3:
#     - ветер ниже порога → нет alert
#     - ветер выше порога → ThresholdAlert + ledger.threshold()
#     - аналогично для осадков, мороза, жары
#     - несколько порогов одновременно → несколько alerts
#   Проверка: pytest tests/unit/test_thresholds.py -v
# =============================================================

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import CapturingHandler, extract_extra
from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.calc.thresholds import ThresholdAlert, check_thresholds
from weather_dashboard.config import (
    DEFAULT_CONFIG,
    DashboardConfig,
    LocationConfig,
    ThresholdConfig,
    WalkWindowConfig,
    ComfortIndexConfig,
)


# -------------------------------------------------------------
# Раздел 0. Вспомогательные функции
# -------------------------------------------------------------


def _norm_with(
    wind_gusts: float = 5.0,
    precip_prob: float = 20.0,
    precip_sum: float = 2.0,
    t_min: float = 5.0,
    t_max: float = 20.0,
    n_hourly: int = 24,
    n_daily: int = 1,
) -> NormalizedForecast:
    base = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    times_h = [base + timedelta(hours=i) for i in range(n_hourly)]
    times_d = [base + timedelta(days=i) for i in range(n_daily)]
    return NormalizedForecast(
        hourly_times=times_h,
        daily_times=times_d,
        wind_gusts_10m=[wind_gusts] * n_hourly,
        precipitation_probability=[precip_prob] * n_hourly,
        temperature_2m=[15.0] * n_hourly,
        precipitation_sum=[precip_sum] * n_daily,
        temperature_2m_min=[t_min] * n_daily,
        temperature_2m_max=[t_max] * n_daily,
        n_hourly=n_hourly,
        n_daily=n_daily,
    )


def _config_with_thresholds(
    wind_gust: float = 15.0,
    precip_prob: float = 70.0,
    precip_sum: float = 10.0,
    frost: float = -10.0,
    heat: float = 35.0,
) -> DashboardConfig:
    return DashboardConfig(
        location=DEFAULT_CONFIG.location,
        thresholds=ThresholdConfig(
            wind_gust_ms=wind_gust,
            precip_prob_pct=precip_prob,
            precip_sum_mm=precip_sum,
            frost_temp_c=frost,
            heat_temp_c=heat,
        ),
        walk_window=DEFAULT_CONFIG.walk_window,
        comfort=DEFAULT_CONFIG.comfort,
    )


# -------------------------------------------------------------
# Раздел 1. Нет срабатываний
# -------------------------------------------------------------


@pytest.mark.unit()
def test_no_alerts_when_all_below_thresholds() -> None:
    """Все метрики ниже порогов → пустой список alerts."""
    norm = _norm_with(wind_gusts=5.0, precip_prob=20.0,
                      precip_sum=2.0, t_min=5.0, t_max=20.0)
    config = _config_with_thresholds()
    alerts = check_thresholds(norm, config=config)
    assert alerts == []


# -------------------------------------------------------------
# Раздел 2. Ветер
# -------------------------------------------------------------


@pytest.mark.unit()
def test_wind_gust_above_threshold_creates_alert() -> None:
    """Порывы выше порога → ThresholdAlert с metric='wind_gust_ms'."""
    norm = _norm_with(wind_gusts=20.0)
    config = _config_with_thresholds(wind_gust=15.0)
    alerts = check_thresholds(norm, config=config)
    wind_alerts = [a for a in alerts if a.metric == "wind_gust_ms"]
    assert wind_alerts, "Ожидался alert по ветру"
    assert wind_alerts[0].value == pytest.approx(20.0, abs=0.1)
    assert wind_alerts[0].limit == pytest.approx(15.0)
    assert wind_alerts[0].new_regime == "alert"


@pytest.mark.unit()
def test_wind_gust_below_threshold_no_alert() -> None:
    """Порывы ниже порога → нет alert."""
    norm = _norm_with(wind_gusts=10.0)
    config = _config_with_thresholds(wind_gust=15.0)
    alerts = check_thresholds(norm, config=config)
    assert not any(a.metric == "wind_gust_ms" for a in alerts)


# -------------------------------------------------------------
# Раздел 3. Осадки
# -------------------------------------------------------------


@pytest.mark.unit()
def test_precip_prob_above_threshold_creates_alert() -> None:
    """Вероятность осадков выше порога → alert."""
    norm = _norm_with(precip_prob=80.0)
    config = _config_with_thresholds(precip_prob=70.0)
    alerts = check_thresholds(norm, config=config)
    assert any(a.metric == "precipitation_probability" for a in alerts)


@pytest.mark.unit()
def test_precip_sum_above_threshold_creates_alert() -> None:
    """Сумма осадков выше порога → alert."""
    norm = _norm_with(precip_sum=15.0)
    config = _config_with_thresholds(precip_sum=10.0)
    alerts = check_thresholds(norm, config=config)
    assert any(a.metric == "precipitation_sum_mm" for a in alerts)


# -------------------------------------------------------------
# Раздел 4. Температура
# -------------------------------------------------------------


@pytest.mark.unit()
def test_frost_below_threshold_creates_alert() -> None:
    """Температура ниже порога мороза → alert."""
    norm = _norm_with(t_min=-15.0)
    config = _config_with_thresholds(frost=-10.0)
    alerts = check_thresholds(norm, config=config)
    assert any(a.metric == "frost_temp_c" for a in alerts)


@pytest.mark.unit()
def test_frost_above_threshold_no_alert() -> None:
    """Температура выше порога мороза → нет alert."""
    norm = _norm_with(t_min=5.0)
    config = _config_with_thresholds(frost=-10.0)
    alerts = check_thresholds(norm, config=config)
    assert not any(a.metric == "frost_temp_c" for a in alerts)


@pytest.mark.unit()
def test_heat_above_threshold_creates_alert() -> None:
    """Температура выше порога жары → alert."""
    norm = _norm_with(t_max=38.0)
    config = _config_with_thresholds(heat=35.0)
    alerts = check_thresholds(norm, config=config)
    assert any(a.metric == "heat_temp_c" for a in alerts)


@pytest.mark.unit()
def test_heat_below_threshold_no_alert() -> None:
    """Температура ниже порога жары → нет alert."""
    norm = _norm_with(t_max=25.0)
    config = _config_with_thresholds(heat=35.0)
    alerts = check_thresholds(norm, config=config)
    assert not any(a.metric == "heat_temp_c" for a in alerts)


# -------------------------------------------------------------
# Раздел 5. Ledger-интеграция
# -------------------------------------------------------------


@pytest.mark.unit()
def test_threshold_logs_to_ledger(capturing_handler: CapturingHandler) -> None:
    """Каждое срабатывание → ledger.threshold() (ТЗ 7.3, 8.2)."""
    ledger = LedgerLogger(corr_id="test-threshold-id")
    norm = _norm_with(wind_gusts=20.0)
    config = _config_with_thresholds(wind_gust=15.0)

    check_thresholds(norm, config=config, ledger=ledger)

    threshold_records = [
        r for r in capturing_handler.records
        if getattr(r, "kind", None) == "threshold"
    ]
    assert threshold_records, "ledger.threshold() не вызван"
    extra = extract_extra(threshold_records[0])
    assert extra["metric"] == "wind_gust_ms"


@pytest.mark.unit()
def test_multiple_alerts_all_returned() -> None:
    """Несколько нарушений одновременно → несколько alerts."""
    norm = _norm_with(wind_gusts=20.0, precip_prob=80.0, t_max=38.0)
    config = _config_with_thresholds(wind_gust=15.0, precip_prob=70.0, heat=35.0)
    alerts = check_thresholds(norm, config=config)
    assert len(alerts) >= 3