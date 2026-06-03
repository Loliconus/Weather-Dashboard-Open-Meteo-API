# =============================================================
# ПУТЬ        : src/weather_dashboard/calc/metrics.py
# ОБОЗНАЧЕНИЕ : WD.CALC.02
# НАИМЕНОВАНИЕ: Расчёт метрик и индекса комфортности
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : dataclasses, math, weather_dashboard.calc.normalizer,
#               weather_dashboard.config
# =============================================================
# Назначение:
#   Реализует метрики раздела 7.2 ТЗ:
#     A) Суточные: T_mean_day, T_amp_day, Rain_hours_50,
#                  Wind_gust_max, Solar_sum
#     C) ComfortIndex (0..100) с категорией (ТЗ 7.2 C)
#   Формула ComfortIndex документирована в DashboardConfig.ComfortIndexConfig.
#   Все формулы покрыты unit-тестами на синтетических данных.
#   Проверка: pytest tests/unit/test_metrics.py
# =============================================================

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.config import ComfortIndexConfig, DashboardConfig, DEFAULT_CONFIG


# -------------------------------------------------------------
# Раздел 0. Типы
# -------------------------------------------------------------


class ComfortCategory(str, Enum):
    """Категория комфортности (ТЗ 7.2 C)."""

    COMFORTABLE = "комфортно"   # CI ≥ 70
    TOLERABLE = "терпимо"       # 40 ≤ CI < 70
    HARD = "тяжело"             # CI < 40


# -------------------------------------------------------------
# Раздел 1. Датаклассы результатов
# -------------------------------------------------------------


@dataclass
class DailyMetrics:
    """Суточные метрики для одного дня (ТЗ 7.2 A).

    Все значения рассчитываются по hourly-данным за данные сутки.
    """

    date: str = ""                  # ISO-дата суток "YYYY-MM-DD"
    t_mean_day: float = 0.0         # Средняя температура (по hourly)
    t_amp_day: float = 0.0          # Амплитуда (max - min по hourly)
    rain_hours_50: int = 0          # Часов с precipitation_probability ≥ 50%
    wind_gust_max: float = 0.0      # Максимум порывов ветра за сутки
    solar_sum: float = 0.0          # Суммарная радиация (из daily)


@dataclass
class ComfortIndex:
    """Индекс комфортности за ближайшие сутки (ТЗ 7.2 C).

    Формула (авторская, документирована в config.ComfortIndexConfig):
        CI = 100
           − k_t  · |AT − t_opt|
           − k_h  · max(0, RH − rh_ok)
           − k_w  · max(0, WS − ws_ok)
           − k_p  · PP / 100
        CI = clamp(CI, 0, 100)

    Где AT = apparent_temperature, RH = relative_humidity_2m,
    WS = wind_speed_10m, PP = precipitation_probability.
    Коэффициенты k_* задаются в ComfortIndexConfig.
    """

    value: float = 0.0              # Значение 0..100
    category: ComfortCategory = ComfortCategory.HARD
    t_penalty: float = 0.0          # Штраф за температуру
    h_penalty: float = 0.0          # Штраф за влажность
    w_penalty: float = 0.0          # Штраф за ветер
    p_penalty: float = 0.0          # Штраф за осадки
    hours_used: int = 0             # Число часов участвовавших в расчёте


# -------------------------------------------------------------
# Раздел 2. Расчёт суточных метрик
# -------------------------------------------------------------


def calculate_daily_metrics(
    norm: NormalizedForecast,
    config: DashboardConfig = DEFAULT_CONFIG,
) -> list[DailyMetrics]:
    """Рассчитать суточные метрики для каждого дня прогноза.

    Разбивает hourly-ряд на суточные срезы по дате из hourly_times.
    Для shortwave_radiation_sum использует daily-данные напрямую.

    Args:
        norm:   Нормализованный прогноз.
        config: Конфиг проекта (пороги, коэффициенты).

    Returns:
        Список DailyMetrics (по одному на каждый день в ряду).
    """
    if not norm.hourly_times:
        return []

    # Группировка hourly индексов по дате
    day_indices: dict[str, list[int]] = {}
    for i, dt in enumerate(norm.hourly_times):
        date_key = dt.strftime("%Y-%m-%d")
        day_indices.setdefault(date_key, []).append(i)

    results: list[DailyMetrics] = []

    for day_idx, (date_key, indices) in enumerate(day_indices.items()):
        metrics = DailyMetrics(date=date_key)

        # T_mean_day — средняя температура (ТЗ 7.2 A1)
        temps = [norm.temperature_2m[i] for i in indices if i < len(norm.temperature_2m)]
        if temps:
            metrics.t_mean_day = sum(temps) / len(temps)

        # T_amp_day — амплитуда (ТЗ 7.2 A2)
        if temps:
            metrics.t_amp_day = max(temps) - min(temps)

        # Rain_hours_50 — часов с prob ≥ 50% (ТЗ 7.2 A3)
        probs = [norm.precipitation_probability[i] for i in indices
                 if i < len(norm.precipitation_probability)]
        metrics.rain_hours_50 = sum(1 for p in probs if p >= 50.0)

        # Wind_gust_max — максимум порывов (ТЗ 7.2 A4)
        gusts = [norm.wind_gusts_10m[i] for i in indices
                 if i < len(norm.wind_gusts_10m)]
        if gusts:
            metrics.wind_gust_max = max(gusts)

        # Solar_sum — из daily (ТЗ 7.2 A5)
        if day_idx < len(norm.shortwave_radiation_sum):
            metrics.solar_sum = norm.shortwave_radiation_sum[day_idx]

        results.append(metrics)

    return results


# -------------------------------------------------------------
# Раздел 3. ComfortIndex
# -------------------------------------------------------------


def calculate_comfort_index(
    norm: NormalizedForecast,
    config: DashboardConfig = DEFAULT_CONFIG,
    hours: int = 24,
) -> ComfortIndex:
    """Рассчитать ComfortIndex за первые `hours` часов прогноза.

    Усредняет штрафы по всем доступным часам в горизонте.
    Возвращает 0/HARD если данных нет.

    Args:
        norm:   Нормализованный прогноз.
        config: Конфиг проекта.
        hours:  Горизонт расчёта в часах (по умолчанию 24).

    Returns:
        ComfortIndex с итоговым значением и категорией.
    """
    cfg = config.comfort
    n = min(hours, norm.n_hourly, len(norm.apparent_temperature))

    if n == 0:
        return ComfortIndex(value=0.0, category=ComfortCategory.HARD)

    total_t = total_h = total_w = total_p = 0.0

    for i in range(n):
        at = norm.apparent_temperature[i] if i < len(norm.apparent_temperature) else cfg.t_opt
        rh = norm.relative_humidity_2m[i] if i < len(norm.relative_humidity_2m) else 0.0
        ws = norm.wind_speed_10m[i] if i < len(norm.wind_speed_10m) else 0.0
        pp = norm.precipitation_probability[i] if i < len(norm.precipitation_probability) else 0.0

        total_t += cfg.k_t * abs(at - cfg.t_opt)
        total_h += cfg.k_h * max(0.0, rh - cfg.rh_ok)
        total_w += cfg.k_w * max(0.0, ws - cfg.ws_ok)
        total_p += cfg.k_p * (pp / 100.0)

    t_pen = total_t / n
    h_pen = total_h / n
    w_pen = total_w / n
    p_pen = total_p / n

    raw_ci = 100.0 - t_pen - h_pen - w_pen - p_pen
    ci_value = max(0.0, min(100.0, raw_ci))

    return ComfortIndex(
        value=round(ci_value, 1),
        category=_ci_category(ci_value),
        t_penalty=round(t_pen, 2),
        h_penalty=round(h_pen, 2),
        w_penalty=round(w_pen, 2),
        p_penalty=round(p_pen, 2),
        hours_used=n,
    )


def _ci_category(value: float) -> ComfortCategory:
    """Определить категорию по значению CI."""
    if value >= 70.0:
        return ComfortCategory.COMFORTABLE
    if value >= 40.0:
        return ComfortCategory.TOLERABLE
    return ComfortCategory.HARD