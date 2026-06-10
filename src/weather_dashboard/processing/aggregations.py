"""Агрегации почасовых данных в суточные.

Все функции — pure functions.
Входные данные: HourlyForecast.
Выходные данные: DailyAggregate (frozen dataclass).

Принципы:
- Генераторы и itertools для временных рядов
- Все числа float, не int
- None-safe: None в исходных данных заменяется на 0.0 или пропускается
- Неполные сутки (<24 записей) вызывают warnings.warn, результат не None
"""

from __future__ import annotations

import itertools
import math
import warnings
from dataclasses import dataclass
from typing import Iterator

from weather_dashboard.api.models import HourlyForecast


# ---------------------------------------------------------------------------
# Результирующий dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class DailyAggregate:
    """Агрегированные суточные показатели, вычисленные из hourly-данных.

    Args:
        date: Дата в формате YYYY-MM-DD.
        temp_min: Минимальная температура за сутки, °C.
        temp_max: Максимальная температура за сутки, °C.
        temp_mean: Средняя температура за сутки, °C.
        total_precipitation: Суммарные осадки, мм.
        dominant_wind_direction: Доминирующее направление ветра, °.
        max_uv_index: Максимальный УФ-индекс дневных часов.
        sunshine_hours: Часы солнечного сияния (shortwave > 120 Вт/м²).
        precipitation_type: Тип осадков: "rain" | "snow" | "mixed" | "none".
    """

    date: str
    temp_min: float
    temp_max: float
    temp_mean: float
    total_precipitation: float
    dominant_wind_direction: float
    max_uv_index: float
    sunshine_hours: float
    precipitation_type: str


# ---------------------------------------------------------------------------
# Вспомогательные генераторы
# ---------------------------------------------------------------------------
def _day_slices(
    hourly: HourlyForecast,
) -> Iterator[tuple[str, list[int]]]:
    """Генерирует пары (дата, список_индексов_часов) для каждых суток.

    Группирует индексы почасового массива по дате (первые 10 символов
    ISO 8601 timestamp: "YYYY-MM-DD").

    Args:
        hourly: Почасовой прогноз.

    Yields:
        Кортеж (date_str, [idx, ...]) — дата и список индексов.
    """
    for date, group in itertools.groupby(
        enumerate(hourly.time), key=lambda x: x[1][:10]
    ):
        indices = [idx for idx, _ in group]
        yield date, indices


def _safe_float(value: float | None, fallback: float = 0.0) -> float:
    """Заменяет None на fallback.

    Args:
        value: Значение или None.
        fallback: Значение по умолчанию.

    Returns:
        float-значение или fallback.
    """
    return value if value is not None else fallback


# ---------------------------------------------------------------------------
# Агрегирующие функции
# ---------------------------------------------------------------------------
def daily_temperature_range(
    hourly: HourlyForecast,
) -> list[tuple[str, float, float, float]]:
    """Вычисляет температурный диапазон для каждых суток.

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Список кортежей (date, t_min, t_max, t_mean) для каждого дня.
        t_mean — среднеарифметическое доступных часовых значений.

    Notes:
        Неполные сутки (<24 записей) обрабатываются с предупреждением.
        None-значения исключаются из расчёта.

    Examples:
        >>> # Результат содержит по одной записи на каждые сутки в данных
    """
    results: list[tuple[str, float, float, float]] = []

    for date, indices in _day_slices(hourly):
        if len(indices) < 24:
            warnings.warn(
                f"Неполные суточные данные для {date}: "
                f"{len(indices)} часов из 24. Результат может быть неточным.",
                UserWarning,
                stacklevel=2,
            )

        temps = [
            hourly.temperature_2m[i]
            for i in indices
            if hourly.temperature_2m[i] is not None
        ]

        if not temps:
            warnings.warn(
                f"Нет данных температуры для {date}.",
                UserWarning,
                stacklevel=2,
            )
            continue

        t_min = float(min(temps))
        t_max = float(max(temps))
        t_mean = float(sum(temps) / len(temps))
        results.append((date, t_min, t_max, t_mean))

    return results


def total_precipitation(hourly: HourlyForecast) -> dict[str, float]:
    """Суммирует осадки по суткам.

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Словарь {date: total_mm} — суммарные осадки в мм за каждые сутки.

    Notes:
        None в исходных данных заменяется на 0.0.

    Examples:
        >>> # {"2026-06-10": 2.5, "2026-06-11": 0.0, ...}
    """
    result: dict[str, float] = {}

    for date, indices in _day_slices(hourly):
        daily_sum = sum(
            _safe_float(hourly.precipitation[i]) for i in indices
        )
        result[date] = float(daily_sum)

    return result


def dominant_wind_direction(hourly: HourlyForecast) -> dict[str, float]:
    """Вычисляет доминирующее направление ветра для каждых суток.

    Использует векторное среднее через тригонометрию:
    mean_dir = atan2(mean(sin(dir)), mean(cos(dir)))

    Это корректно обрабатывает переход через 0°/360°:
    среднее [350°, 10°] = 0°, а не 180°.

    Formula:
        θ̄ = atan2(Σsin(θᵢ) / n, Σcos(θᵢ) / n), результат в [0, 360)

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Словарь {date: direction_degrees} — направление в градусах [0, 360).

    Notes:
        None-значения исключаются из расчёта.
        Если нет данных — возвращает 0.0.

    Examples:
        >>> # dominant_wind_direction([350°, 350°, 10°, 10°]) → ≈ 0°
    """
    result: dict[str, float] = {}

    for date, indices in _day_slices(hourly):
        dirs = [
            hourly.wind_direction_10m[i]
            for i in indices
            if hourly.wind_direction_10m[i] is not None
        ]

        if not dirs:
            result[date] = 0.0
            continue

        sin_sum = sum(math.sin(math.radians(d)) for d in dirs)
        cos_sum = sum(math.cos(math.radians(d)) for d in dirs)

        mean_dir = math.degrees(math.atan2(sin_sum, cos_sum))
        # atan2 возвращает [-180, 180] → нормализуем в [0, 360)
        result[date] = float(mean_dir % 360.0)

    return result


def max_uv_index(hourly: HourlyForecast) -> dict[str, float]:
    """Максимальный УФ-индекс дневных часов для каждых суток.

    Дневные часы: 06:00–20:00 (включительно) по метке timestamp.

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Словарь {date: max_uv} — максимальный УФ-индекс дня.

    Notes:
        None заменяется на 0.0.
        Если нет дневных данных — возвращает 0.0.
    """
    result: dict[str, float] = {}

    for date, indices in _day_slices(hourly):
        daytime_uv = [
            _safe_float(hourly.uv_index[i])
            for i in indices
            # Дневные часы: HH в метке времени "YYYY-MM-DDTHH:MM"
            if len(hourly.time[i]) >= 13
            and 6 <= int(hourly.time[i][11:13]) <= 20
            and hourly.uv_index[i] is not None
        ]

        result[date] = float(max(daytime_uv)) if daytime_uv else 0.0

    return result


def sunshine_hours(hourly: HourlyForecast) -> dict[str, float]:
    """Подсчёт часов солнечного сияния для каждых суток.

    Час считается солнечным если shortwave_radiation > 120 Вт/м².
    Порог 120 Вт/м² соответствует определению WMO.

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Словарь {date: hours} — количество солнечных часов.

    Notes:
        None-значения пропускаются (не считаются ни солнечными, ни пасмурными).
    """
    _THRESHOLD = 120.0  # Вт/м²
    result: dict[str, float] = {}

    for date, indices in _day_slices(hourly):
        count = sum(
            1
            for i in indices
            if hourly.shortwave_radiation[i] is not None
            and hourly.shortwave_radiation[i] > _THRESHOLD  # type: ignore[operator]
        )
        result[date] = float(count)

    return result


def precipitation_type(hourly: HourlyForecast) -> dict[str, str]:
    """Определяет преобладающий тип осадков для каждых суток.

    Классификация по соотношению rain/snowfall к total:
    - "none"   — total < 0.1 мм (следовые осадки)
    - "rain"   — доля дождя > 70%
    - "snow"   — доля снега > 70%
    - "mixed"  — всё остальное

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Словарь {date: type_str}.

    Notes:
        None-значения заменяются на 0.0.
    """
    result: dict[str, str] = {}

    for date, indices in _day_slices(hourly):
        total = sum(_safe_float(hourly.precipitation[i]) for i in indices)
        rain = sum(_safe_float(hourly.rain[i]) for i in indices)
        snow = sum(_safe_float(hourly.snowfall[i]) for i in indices)

        if total < 0.1:
            result[date] = "none"
        elif total > 0.0:
            rain_ratio = rain / total
            snow_ratio = snow / total
            if rain_ratio > 0.7:
                result[date] = "rain"
            elif snow_ratio > 0.7:
                result[date] = "snow"
            else:
                result[date] = "mixed"
        else:
            result[date] = "none"

    return result


# ---------------------------------------------------------------------------
# Оркестратор
# ---------------------------------------------------------------------------
def compute_all(hourly: HourlyForecast) -> list[DailyAggregate]:
    """Вычисляет все суточные агрегаты из почасовых данных.

    Оркестрирует все агрегирующие функции и собирает результат
    в список DailyAggregate (по одному на каждые сутки).

    Args:
        hourly: Почасовой прогноз Open-Meteo.

    Returns:
        Список DailyAggregate, отсортированный по дате.
    """
    temp_ranges = {
        date: (t_min, t_max, t_mean)
        for date, t_min, t_max, t_mean in daily_temperature_range(hourly)
    }
    precip = total_precipitation(hourly)
    wind_dirs = dominant_wind_direction(hourly)
    uv = max_uv_index(hourly)
    sun = sunshine_hours(hourly)
    precip_types = precipitation_type(hourly)

    dates = sorted(set(precip.keys()) | set(temp_ranges.keys()))

    aggregates: list[DailyAggregate] = []
    for date in dates:
        t_min, t_max, t_mean = temp_ranges.get(date, (0.0, 0.0, 0.0))
        aggregates.append(
            DailyAggregate(
                date=date,
                temp_min=t_min,
                temp_max=t_max,
                temp_mean=t_mean,
                total_precipitation=precip.get(date, 0.0),
                dominant_wind_direction=wind_dirs.get(date, 0.0),
                max_uv_index=uv.get(date, 0.0),
                sunshine_hours=sun.get(date, 0.0),
                precipitation_type=precip_types.get(date, "none"),
            )
        )

    return aggregates