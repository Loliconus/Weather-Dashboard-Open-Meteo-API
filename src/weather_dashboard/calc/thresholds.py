# =============================================================
# ПУТЬ        : src/weather_dashboard/calc/thresholds.py
# ОБОЗНАЧЕНИЕ : WD.CALC.04
# НАИМЕНОВАНИЕ: Пороговые предупреждения погодных метрик
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : dataclasses, weather_dashboard.calc.normalizer,
#               weather_dashboard.bootstrap.ledger,
#               weather_dashboard.config
# =============================================================
# Назначение:
#   check_thresholds() проверяет метрики против порогов из конфига
#   и возвращает список ThresholdAlert.
#   Каждое срабатывание → ledger.threshold() (ТЗ 7.3, 8.2).
#   Проверки: ветер (hourly), осадки-вероятность (hourly),
#             осадки-сумма (daily), мороз (daily), жара (daily).
#   Проверка: pytest tests/unit/test_thresholds.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass

from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.config import DEFAULT_CONFIG, DashboardConfig


# -------------------------------------------------------------
# Раздел 1. Датакласс предупреждения
# -------------------------------------------------------------


@dataclass
class ThresholdAlert:
    """Одно пороговое предупреждение (ТЗ 7.3).

    Соответствует одному вызову ledger.threshold().
    """

    metric: str
    value: float
    limit: float
    new_regime: str     # "alert" | "warning" | "nominal"
    description: str
    date: str = ""      # Дата для суточных метрик, "" для текущих


# -------------------------------------------------------------
# Раздел 2. Проверка порогов
# -------------------------------------------------------------


def check_thresholds(
    norm: NormalizedForecast,
    config: DashboardConfig = DEFAULT_CONFIG,
    ledger: LedgerLogger | None = None,
) -> list[ThresholdAlert]:
    """Проверить все метрики против порогов конфигурации.

    Args:
        norm:   Нормализованный прогноз.
        config: Конфиг с порогами ThresholdConfig.
        ledger: Опциональный ledger для фиксации событий.

    Returns:
        Список ThresholdAlert (может быть пустым — всё в норме).
    """
    thr = config.thresholds
    alerts: list[ThresholdAlert] = []

    # ----------------------------------------------------------
    # 1. Порывы ветра (hourly, ближайшие 24 часа)
    # ----------------------------------------------------------
    if norm.wind_gusts_10m:
        max_gust = max(norm.wind_gusts_10m[:24])
        if max_gust >= thr.wind_gust_ms:
            alerts.append(_make_alert(
                metric="wind_gust_ms",
                value=max_gust,
                limit=thr.wind_gust_ms,
                regime="alert",
                desc=f"Порывы ветра {max_gust:.1f} м/с (порог {thr.wind_gust_ms} м/с)",
            ))
            _emit_threshold(ledger, "metric:wind_gust_ms",
                            "wind_gust_ms", max_gust, thr.wind_gust_ms, "alert")

    # ----------------------------------------------------------
    # 2. Вероятность осадков (hourly, ближайшие 24 часа)
    # ----------------------------------------------------------
    if norm.precipitation_probability:
        max_prob = max(norm.precipitation_probability[:24])
        if max_prob >= thr.precip_prob_pct:
            alerts.append(_make_alert(
                metric="precipitation_probability",
                value=max_prob,
                limit=thr.precip_prob_pct,
                regime="warning",
                desc=f"Вероятность осадков {max_prob:.0f}% (порог {thr.precip_prob_pct:.0f}%)",
            ))
            _emit_threshold(ledger, "metric:precipitation_probability",
                            "precipitation_probability",
                            max_prob, thr.precip_prob_pct, "warning")

    # ----------------------------------------------------------
    # 3. Сумма осадков (daily)
    # ----------------------------------------------------------
    for i, precip_sum in enumerate(norm.precipitation_sum):
        date = _date_str(norm, i)
        if precip_sum >= thr.precip_sum_mm:
            alerts.append(_make_alert(
                metric="precipitation_sum_mm",
                value=precip_sum,
                limit=thr.precip_sum_mm,
                regime="warning",
                desc=f"Осадков {precip_sum:.1f} мм за {date} (порог {thr.precip_sum_mm} мм)",
                date=date,
            ))
            _emit_threshold(ledger, f"metric:precipitation_sum.{date}",
                            "precipitation_sum_mm",
                            precip_sum, thr.precip_sum_mm, "warning",
                            date=date)

    # ----------------------------------------------------------
    # 4. Мороз (daily temperature_2m_min)
    # ----------------------------------------------------------
    for i, t_min in enumerate(norm.temperature_2m_min):
        date = _date_str(norm, i)
        if t_min <= thr.frost_temp_c:
            alerts.append(_make_alert(
                metric="frost_temp_c",
                value=t_min,
                limit=thr.frost_temp_c,
                regime="alert",
                desc=f"Мороз {t_min:.1f}°C за {date} (порог {thr.frost_temp_c}°C)",
                date=date,
            ))
            _emit_threshold(ledger, f"metric:frost_temp.{date}",
                            "frost_temp_c", t_min, thr.frost_temp_c, "alert",
                            date=date)

    # ----------------------------------------------------------
    # 5. Жара (daily temperature_2m_max)
    # ----------------------------------------------------------
    for i, t_max in enumerate(norm.temperature_2m_max):
        date = _date_str(norm, i)
        if t_max >= thr.heat_temp_c:
            alerts.append(_make_alert(
                metric="heat_temp_c",
                value=t_max,
                limit=thr.heat_temp_c,
                regime="alert",
                desc=f"Жара {t_max:.1f}°C за {date} (порог {thr.heat_temp_c}°C)",
                date=date,
            ))
            _emit_threshold(ledger, f"metric:heat_temp.{date}",
                            "heat_temp_c", t_max, thr.heat_temp_c, "alert",
                            date=date)

    return alerts


# -------------------------------------------------------------
# Раздел 3. Вспомогательные функции
# -------------------------------------------------------------


def _make_alert(
    metric: str,
    value: float,
    limit: float,
    regime: str,
    desc: str,
    date: str = "",
) -> ThresholdAlert:
    return ThresholdAlert(
        metric=metric,
        value=round(value, 2),
        limit=limit,
        new_regime=regime,
        description=desc,
        date=date,
    )


def _emit_threshold(
    ledger: LedgerLogger | None,
    subject: str,
    metric: str,
    value: float,
    limit: float,
    new_regime: str,
    **ctx: object,
) -> None:
    """Записать threshold в ledger если он подключён."""
    if ledger:
        ledger.threshold(
            subject=subject,
            metric=metric,
            value=value,
            limit=limit,
            new_regime=new_regime,
            **ctx,
        )


def _date_str(norm: NormalizedForecast, idx: int) -> str:
    """Получить строку даты для daily-индекса."""
    if idx < len(norm.daily_times):
        return norm.daily_times[idx].strftime("%Y-%m-%d")
    return ""