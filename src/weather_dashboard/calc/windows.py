# =============================================================
# ПУТЬ        : src/weather_dashboard/calc/windows.py
# ОБОЗНАЧЕНИЕ : WD.CALC.03
# НАИМЕНОВАНИЕ: Поиск "окна прогулки" — лучшего непрерывного интервала
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : dataclasses, datetime, weather_dashboard.calc.normalizer,
#               weather_dashboard.config
# =============================================================
# Назначение:
#   find_walk_window() ищет самый длинный непрерывный интервал
#   в горизонте ближайших 24–48 часов, где одновременно:
#     - precipitation_probability < P0 (конфиг)
#     - wind_speed_10m < W0 (конфиг)
#     - temperature в диапазоне [Tmin, Tmax] (конфиг)
#   Возвращает WalkWindow с началом/концом/длительностью.
#   Если подходящего окна нет — возвращает None.
#   Проверка: pytest tests/unit/test_windows.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.config import DEFAULT_CONFIG, DashboardConfig


# -------------------------------------------------------------
# Раздел 1. Датакласс результата
# -------------------------------------------------------------


@dataclass
class WalkWindow:
    """Лучшее "окно прогулки" (ТЗ 7.2 B).

    Самый длинный непрерывный интервал в горизонте,
    удовлетворяющий всем условиям WalkWindowConfig.
    """

    start: datetime             # Начало окна
    end: datetime               # Конец окна (не включительно)
    duration_hours: int         # Длительность в часах
    reason: str = ""            # Пояснение почему это окно выбрано


# -------------------------------------------------------------
# Раздел 2. Алгоритм поиска
# -------------------------------------------------------------


def find_walk_window(
    norm: NormalizedForecast,
    config: DashboardConfig = DEFAULT_CONFIG,
) -> WalkWindow | None:
    """Найти лучшее окно прогулки в горизонте.

    Алгоритм скользящего окна O(n):
        1. Для каждого часа проверить условия (precipitation, wind, temp).
        2. Отслеживать текущую непрерывную полосу подходящих часов.
        3. Запомнить максимальную полосу.

    Args:
        norm:   Нормализованный прогноз.
        config: Конфиг с параметрами WalkWindowConfig.

    Returns:
        WalkWindow если найдено, None если нет подходящих часов.
    """
    cfg = config.walk_window
    horizon = min(cfg.horizon_hours, norm.n_hourly)

    if horizon == 0:
        return None

    best_start = -1
    best_len = 0
    cur_start = -1
    cur_len = 0

    for i in range(horizon):
        if _hour_is_suitable(i, norm, cfg):
            if cur_start == -1:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
        else:
            cur_start = -1
            cur_len = 0

    if best_len == 0 or best_start == -1:
        return None

    start_dt = norm.hourly_times[best_start]
    end_idx = min(best_start + best_len, len(norm.hourly_times) - 1)
    end_dt = norm.hourly_times[end_idx]

    reason = (
        f"Непрерывный интервал {best_len}ч: "
        f"осадки<{cfg.precip_prob_max_pct}%, "
        f"ветер<{cfg.wind_speed_max_ms}м/с, "
        f"температура [{cfg.temp_min_c}…{cfg.temp_max_c}]°C"
    )

    return WalkWindow(
        start=start_dt,
        end=end_dt,
        duration_hours=best_len,
        reason=reason,
    )


# -------------------------------------------------------------
# Раздел 3. Вспомогательные функции
# -------------------------------------------------------------


def _hour_is_suitable(
    idx: int,
    norm: NormalizedForecast,
    cfg: "WalkWindowConfig",  # type: ignore[name-defined]  # noqa: F821
) -> bool:
    """Проверить, подходит ли час с индексом idx для прогулки."""
    pp = norm.precipitation_probability[idx] if idx < len(norm.precipitation_probability) else 100.0
    ws = norm.wind_speed_10m[idx] if idx < len(norm.wind_speed_10m) else 999.0
    t = norm.temperature_2m[idx] if idx < len(norm.temperature_2m) else -999.0

    return (
        pp < cfg.precip_prob_max_pct
        and ws < cfg.wind_speed_max_ms
        and cfg.temp_min_c <= t <= cfg.temp_max_c
    )