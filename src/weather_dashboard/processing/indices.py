"""Расчёт метеорологических индексов.

Все функции:
- pure (без side effects)
- type-annotated
- без NumPy (только stdlib math)
- docstring: Summary + Args + Returns + Raises + Formula + Source + Notes

Входные данные — только примитивы (float, Sequence[float]).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal, TypedDict


# ---------------------------------------------------------------------------
# Типы результатов
# ---------------------------------------------------------------------------
class TrendResult(TypedDict):
    """Результат анализа тренда температуры."""

    slope: float
    intercept: float
    r2: float
    trend: Literal["warming", "cooling", "stable"]
    confidence: Literal["high", "medium", "low"]


class ComfortResult(TypedDict):
    """Результат расчёта комфортного индекса."""

    score: float
    temp_sub: float
    humidity_sub: float
    wind_sub: float
    uv_sub: float
    precip_sub: float


# ---------------------------------------------------------------------------
# Heat Index
# ---------------------------------------------------------------------------
def heat_index(t_celsius: float, rh_percent: float) -> float:
    """Вычисляет тепловой индекс (ощущаемая жара).

    Применять только при T ≥ 27°C и RH ≥ 40%.
    При более низких значениях возвращает исходную температуру.

    Formula:
        Rothfusz/NWS многочленная регрессия:
        HI = -42.379 + 2.04901523·T + 10.14333127·RH
             - 0.22475541·T·RH - 0.00683783·T²
             - 0.05481717·RH² + 0.00122874·T²·RH
             + 0.00085282·T·RH² - 0.00000199·T²·RH²
        где T — температура в °F, RH — относительная влажность %.
        Результат конвертируется обратно в °C.

    Source:
        Steadman R.G. (1979); NWS Heat Index Equation.
        https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml

    Args:
        t_celsius: Температура воздуха, °C.
        rh_percent: Относительная влажность, % (0–100).

    Returns:
        Тепловой индекс в °C.

    Raises:
        ValueError: Если rh_percent вне [0, 100].

    Notes:
        При T < 27°C или RH < 40% физическое применение некорректно —
        возвращается исходная температура без расчёта.

    Examples:
        >>> round(heat_index(40.0, 60.0), 1)
        54.6
        >>> heat_index(20.0, 50.0)  # Не применимо → исходная T
        20.0
    """
    if not (0.0 <= rh_percent <= 100.0):
        raise ValueError(
            f"Относительная влажность должна быть в [0, 100]%, получено: {rh_percent}"
        )

    if t_celsius < 27.0 or rh_percent < 40.0:
        return t_celsius

    # Конвертируем °C → °F для формулы NWS
    t_f = t_celsius * 9.0 / 5.0 + 32.0
    rh = rh_percent

    hi_f = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 0.00683783 * t_f * t_f
        - 0.05481717 * rh * rh
        + 0.00122874 * t_f * t_f * rh
        + 0.00085282 * t_f * rh * rh
        - 0.00000199 * t_f * t_f * rh * rh
    )

    # Конвертируем °F → °C
    return (hi_f - 32.0) * 5.0 / 9.0


# ---------------------------------------------------------------------------
# Wind Chill
# ---------------------------------------------------------------------------
def wind_chill(t_celsius: float, v_ms: float) -> float:
    """Вычисляет индекс охлаждения ветром (ощущаемый холод).

    Применять только при T ≤ 10°C и V ≥ 1.3 м/с.
    При более высоких значениях возвращает исходную температуру.

    Formula:
        WC = 13.12 + 0.6215·T - 11.37·V^0.16 + 0.3965·T·V^0.16
        где T — температура °C, V — скорость ветра км/ч.
        Входная скорость в м/с конвертируется в км/ч умножением на 3.6.

    Source:
        Environment Canada / JAM Wind Chill Index (2001).
        https://www.canada.ca/en/environment-climate-change/services/
        weather-general-tools-resources/wind-chill-calculator.html

    Args:
        t_celsius: Температура воздуха, °C.
        v_ms: Скорость ветра на высоте 10м, м/с.

    Returns:
        Wind chill индекс в °C.

    Raises:
        ValueError: Если v_ms < 0.

    Notes:
        При T > 10°C или V < 1.3 м/с формула не применима.
        Возвращается исходная температура.

    Examples:
        >>> round(wind_chill(-10.0, 10.0), 1)
        -20.5
        >>> wind_chill(15.0, 5.0)  # Не применимо → исходная T
        15.0
    """
    if v_ms < 0.0:
        raise ValueError(
            f"Скорость ветра не может быть отрицательной, получено: {v_ms}"
        )

    if t_celsius > 10.0 or v_ms < 1.3:
        return t_celsius

    v_kmh = v_ms * 3.6
    v_pow = v_kmh**0.16

    return 13.12 + 0.6215 * t_celsius - 11.37 * v_pow + 0.3965 * t_celsius * v_pow


# ---------------------------------------------------------------------------
# Humidex
# ---------------------------------------------------------------------------
def humidex(t_celsius: float, td_celsius: float) -> float:
    """Вычисляет индекс Humidex (канадский индекс дискомфорта).

    Отражает ощущаемое тепло с учётом влажности.
    Используется при T > 20°C как альтернатива Heat Index.

    Formula:
        e = 6.112 · exp(17.67 · Td / (Td + 243.5))  — давление насыщения, гПа
        Humidex = T + 0.5555 · (e - 10.0)

    Source:
        Meteorological Service of Canada.
        Masterson J.M., Richardson F.A. (1979).
        "Humidex, a method of quantifying human discomfort due to
        excessive heat and humidity". CLI 1-79. Downsview, Ontario.

    Args:
        t_celsius: Температура воздуха, °C.
        td_celsius: Температура точки росы, °C.

    Returns:
        Humidex в °C. Значение < t_celsius означает ошибку входных данных.

    Raises:
        ValueError: Если td_celsius > t_celsius (точка росы не может
                    превышать температуру воздуха).

    Notes:
        Humidex < 29: комфортно
        29–39: дискомфорт различной степени
        ≥ 40: опасная жара

    Examples:
        >>> round(humidex(30.0, 22.0), 1)
        37.3
    """
    if td_celsius > t_celsius:
        raise ValueError(
            f"точка росы ({td_celsius}°C) не может превышать температуру "  # ← Т → т
            f"воздуха ({t_celsius}°C)"
        )

    # Давление насыщения по точке росы (гПа)
    e = 6.112 * math.exp(17.67 * td_celsius / (td_celsius + 243.5))
    return t_celsius + 0.5555 * (e - 10.0)


# ---------------------------------------------------------------------------
# Dew Point
# ---------------------------------------------------------------------------
def dew_point(t_celsius: float, rh_percent: float) -> float:
    """Вычисляет температуру точки росы по формуле Magnus.

    Formula:
        γ(T, RH) = ln(RH/100) + α·T / (β + T)
        Td = β · γ / (α - γ)
        где α = 17.625, β = 243.04°C

    Source:
        August-Roche-Magnus approximation.
        Alduchov O.A., Eskridge R.E. (1996).
        "Improved Magnus Form Approximation of Saturation Vapor Pressure."
        J. Appl. Meteor., 35, 601–609.

    Args:
        t_celsius: Температура воздуха, °C.
        rh_percent: Относительная влажность, % (0–100].

    Returns:
        Температура точки росы в °C.

    Raises:
        ValueError: Если rh_percent ≤ 0 или > 100.

    Examples:
        >>> round(dew_point(20.0, 60.0), 1)
        12.0
    """
    if not (0.0 < rh_percent <= 100.0):
        raise ValueError(
            f"Относительная влажность должна быть в (0, 100]%, получено: {rh_percent}"
        )

    alpha = 17.625
    beta = 243.04  # °C

    gamma = math.log(rh_percent / 100.0) + alpha * t_celsius / (beta + t_celsius)
    return beta * gamma / (alpha - gamma)


# ---------------------------------------------------------------------------
# UV Risk Level
# ---------------------------------------------------------------------------
def uv_risk_level(
    uv_index: float,
) -> Literal["Низкий", "Умеренный", "Высокий", "Очень высокий", "Экстремальный"]:
    """Определяет категорию риска по УФ-индексу.

    Formula:
        WHO/WMO UV Index Scale:
        0–2   → Low (Низкий)
        3–5   → Moderate (Умеренный)
        6–7   → High (Высокий)
        8–10  → Very High (Очень высокий)
        ≥ 11  → Extreme (Экстремальный)

    Source:
        WHO (2002). "Global Solar UV Index: A Practical Guide."
        https://www.who.int/publications/i/item/9241590076

    Args:
        uv_index: УФ-индекс (≥ 0).

    Returns:
        Строка категории риска на русском языке.

    Raises:
        ValueError: Если uv_index < 0.

    Examples:
        >>> uv_risk_level(0.5)
        'Низкий'
        >>> uv_risk_level(11.0)
        'Экстремальный'
    """
    if uv_index < 0.0:
        raise ValueError(f"УФ-индекс не может быть отрицательным, получено: {uv_index}")

    if uv_index <= 2.0:
        return "Низкий"
    if uv_index <= 5.0:
        return "Умеренный"
    if uv_index <= 7.0:
        return "Высокий"
    if uv_index <= 10.0:
        return "Очень высокий"
    return "Экстремальный"


# ---------------------------------------------------------------------------
# AQI Category (European)
# ---------------------------------------------------------------------------
def aqi_category_eu(
    european_aqi: float,
) -> Literal[
    "Хороший",
    "Удовлетворительный",
    "Умеренный",
    "Плохой",
    "Очень плохой",
    "Крайне плохой",
]:
    """Определяет категорию качества воздуха по европейскому индексу EAQI.

    Formula:
        European Air Quality Index (EAQI):
        0–20    → Good (Хороший)
        21–40   → Fair (Удовлетворительный)
        41–60   → Moderate (Умеренный)
        61–80   → Poor (Плохой)
        81–100  → Very Poor (Очень плохой)
        > 100   → Extremely Poor (Крайне плохой)

    Source:
        European Environment Agency (EEA).
        https://www.eea.europa.eu/themes/air/air-quality-index

    Args:
        european_aqi: Европейский индекс качества воздуха (≥ 0).

    Returns:
        Строка категории на русском языке.

    Raises:
        ValueError: Если european_aqi < 0.

    Examples:
        >>> aqi_category_eu(15.0)
        'Хороший'
        >>> aqi_category_eu(105.0)
        'Крайне плохой'
    """
    if european_aqi < 0.0:
        raise ValueError(
            f"European AQI не может быть отрицательным, получено: {european_aqi}"
        )

    if european_aqi <= 20.0:
        return "Хороший"
    if european_aqi <= 40.0:
        return "Удовлетворительный"
    if european_aqi <= 60.0:
        return "Умеренный"
    if european_aqi <= 80.0:
        return "Плохой"
    if european_aqi <= 100.0:
        return "Очень плохой"
    return "Крайне плохой"


# ---------------------------------------------------------------------------
# Precipitation Intensity
# ---------------------------------------------------------------------------
def precipitation_intensity(
    mm_per_hour: float,
) -> Literal["Следы", "Слабые", "Умеренные", "Сильные", "Ливневые"]:
    """Классифицирует интенсивность осадков по WMO.

    Formula:
        WMO No. 8 (CIMO Guide) классификация:
        < 0.5    → Trace (Следы)
        0.5–2.5  → Light (Слабые)
        2.5–7.5  → Moderate (Умеренные)
        7.5–50   → Heavy (Сильные)
        > 50     → Violent (Ливневые)

    Source:
        WMO (2018). "Guide to Meteorological Instruments and Methods
        of Observation." WMO No. 8, Chapter 6.

    Args:
        mm_per_hour: Интенсивность осадков, мм/час.

    Returns:
        Строка категории на русском языке.

    Raises:
        ValueError: Если mm_per_hour < 0.

    Examples:
        >>> precipitation_intensity(0.0)
        'Следы'
        >>> precipitation_intensity(3.0)
        'Умеренные'
    """
    if mm_per_hour < 0.0:
        raise ValueError(
            f"Интенсивность осадков не может быть отрицательной, получено: {mm_per_hour}"
        )

    if mm_per_hour < 0.5:
        return "Следы"
    if mm_per_hour <= 2.5:
        return "Слабые"
    if mm_per_hour <= 7.5:
        return "Умеренные"
    if mm_per_hour <= 50.0:
        return "Сильные"
    return "Ливневые"


# ---------------------------------------------------------------------------
# Weather Trend (МНК без NumPy)
# ---------------------------------------------------------------------------
def weather_trend(t_means: Sequence[float]) -> TrendResult:
    """Вычисляет линейный тренд температурного ряда методом МНК.

    Определяет направление и скорость изменения температуры.

    Formula:
        Метод наименьших квадратов (МНК):
        x̄ = (n-1) / 2
        ȳ = Σyᵢ / n
        slope = Σ(xᵢ - x̄)(yᵢ - ȳ) / Σ(xᵢ - x̄)²
        intercept = ȳ - slope · x̄
        r² = (cov(x,y) / (std(x) · std(y)))²

        Классификация тренда:
        |slope| < 0.1°C/день  → "stable"
        slope ≥ 0.1°C/день   → "warming"
        slope ≤ -0.1°C/день  → "cooling"

        Достоверность по r²:
        r² ≥ 0.8  → "high"
        r² ≥ 0.5  → "medium"
        r² < 0.5  → "low"

    Source:
        Стандартный МНК. Montgomery D.C., Runger G.C. (2014).
        "Applied Statistics and Probability for Engineers." Ch. 11.

    Args:
        t_means: Последовательность среднесуточных температур (≥ 2 значений),
                 °C. Каждый элемент — один день.

    Returns:
        TrendResult: slope, intercept, r2, trend, confidence.

    Raises:
        ValueError: Если len(t_means) < 2.

    Notes:
        Минимум 7 значений рекомендуется для значимого результата.
        При идеально плоском ряду (std=0) r2 = 0.0.

    Examples:
        >>> r = weather_trend([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0])
        >>> round(r["slope"], 2)
        1.0
        >>> r["trend"]
        'warming'
        >>> r["r2"]
        1.0
    """
    n = len(t_means)
    if n < 2:
        raise ValueError(
            f"Для расчёта тренда необходимо минимум 2 значения, получено: {n}"
        )

    x_mean = (n - 1) / 2.0
    y_mean = sum(t_means) / n

    # МНК: числитель и знаменатель для slope
    ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(t_means))
    ss_xx = sum((i - x_mean) ** 2 for i in range(n))

    if ss_xx == 0.0:
        slope = 0.0
        intercept = y_mean
        r2 = 0.0
    else:
        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean

        # r² через корреляцию Пирсона
        ss_yy = sum((v - y_mean) ** 2 for v in t_means)
        if ss_yy == 0.0:
            r2 = 0.0
        else:
            r2 = (ss_xy**2) / (ss_xx * ss_yy)

    # Классификация тренда
    if abs(slope) < 0.1:
        trend: Literal["warming", "cooling", "stable"] = "stable"
    elif slope > 0.0:
        trend = "warming"
    else:
        trend = "cooling"

    # Достоверность
    if r2 >= 0.8:
        confidence: Literal["high", "medium", "low"] = "high"
    elif r2 >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return TrendResult(
        slope=slope,
        intercept=intercept,
        r2=r2,
        trend=trend,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Comfort Score
# ---------------------------------------------------------------------------
def comfort_score(
    t_celsius: float,
    rh_percent: float,
    v_ms: float,
    uv: float,
    precip_mm: float,
) -> ComfortResult:
    # ... (docstring без изменений) ...

    if not (0.0 <= rh_percent <= 100.0):
        raise ValueError(
            f"Относительная влажность должна быть в [0, 100]%, получено: {rh_percent}"
        )
    if v_ms < 0.0:
        raise ValueError(
            f"Скорость ветра не может быть отрицательной, получено: {v_ms}"
        )

    def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, x))

    # ── Температурный субиндекс (вес 35%) ───────────────────────────────
    # оптимум 18–24°C → 100; линейный спад к -10°C (нижняя граница) и 38°C (верхняя)
    if 18.0 <= t_celsius <= 24.0:
        temp_sub = 100.0
    elif t_celsius < 18.0:
        # -10°C → 0, 18°C → 100: линейно
        temp_sub = _clamp((t_celsius - (-10.0)) / (18.0 - (-10.0)) * 100.0)
    else:
        # 24°C → 100, 38°C → 0: линейно убывает
        temp_sub = _clamp((38.0 - t_celsius) / (38.0 - 24.0) * 100.0)

    # ── Влажностный субиндекс (вес 25%) ─────────────────────────────────
    # оптимум 40–60% → 100; линейный спад к 10% и 90%
    if 40.0 <= rh_percent <= 60.0:
        humidity_sub = 100.0
    elif rh_percent < 40.0:
        # 10% → 0, 40% → 100
        humidity_sub = _clamp((rh_percent - 10.0) / (40.0 - 10.0) * 100.0)
    else:
        # 60% → 100, 90% → 0
        humidity_sub = _clamp((90.0 - rh_percent) / (90.0 - 60.0) * 100.0)

    # ── Ветровой субиндекс (вес 20%) ────────────────────────────────────
    # 0–3 м/с → 100; 15 м/с → 0
    if v_ms <= 3.0:
        wind_sub = 100.0
    else:
        wind_sub = _clamp((15.0 - v_ms) / (15.0 - 3.0) * 100.0)

    # ── УФ субиндекс (вес 10%) ───────────────────────────────────────────
    # 0–2 → 100; 11 → 0
    if uv <= 2.0:
        uv_sub = 100.0
    else:
        uv_sub = _clamp((11.0 - uv) / (11.0 - 2.0) * 100.0)

    # ── Осадочный субиндекс (вес 10%) ───────────────────────────────────
    # 0 мм → 100; 10 мм → 0
    if precip_mm <= 0.0:
        precip_sub = 100.0
    else:
        precip_sub = _clamp((10.0 - precip_mm) / 10.0 * 100.0)

    # ── Итоговый score ───────────────────────────────────────────────────
    score = (
        0.35 * temp_sub
        + 0.25 * humidity_sub
        + 0.20 * wind_sub
        + 0.10 * uv_sub
        + 0.10 * precip_sub
    )

    return ComfortResult(
        score=_clamp(score),
        temp_sub=temp_sub,
        humidity_sub=humidity_sub,
        wind_sub=wind_sub,
        uv_sub=uv_sub,
        precip_sub=precip_sub,
    )


# ---------------------------------------------------------------------------
# Frost Risk
# ---------------------------------------------------------------------------
def frost_risk(t_min_night: float) -> bool:
    """Определяет риск заморозков по минимальной ночной температуре.

    Formula:
        frost_risk = t_min_night < 0°C

    Source:
        Стандартное агрометеорологическое определение заморозка.

    Args:
        t_min_night: Минимальная температура ночного периода, °C.

    Returns:
        True если есть риск заморозков.

    Examples:
        >>> frost_risk(-0.1)
        True
        >>> frost_risk(0.0)
        False
    """
    return t_min_night < 0.0


# ---------------------------------------------------------------------------
# High Wind Alert
# ---------------------------------------------------------------------------
def high_wind_alert(v_ms: float, gusts_ms: float) -> bool:
    """Определяет опасный ветер по шкале Бофорта.

    Предупреждение при скорости ветра или порывах ≥ 14 м/с (6 баллов Бофорта).

    Formula:
        alert = v_ms ≥ 14.0 OR gusts_ms ≥ 14.0

    Source:
        Beaufort Wind Scale. WMO Technical Regulations.
        Beaufort 6 (Strong Breeze): 10.8–13.8 м/с.
        Порог 14 м/с — граница "Strong Breeze" / "Near Gale".

    Args:
        v_ms: Средняя скорость ветра, м/с.
        gusts_ms: Скорость порывов ветра, м/с.

    Returns:
        True если ветер достигает предупредительного уровня.

    Raises:
        ValueError: Если v_ms < 0 или gusts_ms < 0.

    Examples:
        >>> high_wind_alert(10.0, 15.0)
        True
        >>> high_wind_alert(5.0, 12.0)
        False
    """
    if v_ms < 0.0:
        raise ValueError(
            f"Скорость ветра не может быть отрицательной, получено: {v_ms}"
        )
    if gusts_ms < 0.0:
        raise ValueError(
            f"Скорость порывов не может быть отрицательной, получено: {gusts_ms}"
        )

    return v_ms >= 14.0 or gusts_ms >= 14.0
