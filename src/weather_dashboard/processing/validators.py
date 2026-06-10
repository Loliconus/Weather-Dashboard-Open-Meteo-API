"""Валидаторы входных данных.

Все функции бросают ValueError с ru-RU сообщениями.
validate_temperature использует warnings.warn (не ValueError) —
физически допустимые экстремальные значения предупреждают, но не блокируют.
"""

from __future__ import annotations

import warnings


def validate_coordinates(lat: float, lon: float) -> None:
    """Проверяет корректность географических координат.

    Args:
        lat: Широта в градусах (WGS84).
        lon: Долгота в градусах (WGS84).

    Raises:
        ValueError: Если широта вне [-90, 90] или долгота вне [-180, 180].

    Examples:
        >>> validate_coordinates(55.7558, 37.6173)  # Москва — OK
        >>> validate_coordinates(91.0, 0.0)
        Traceback (most recent call last):
            ...
        ValueError: Широта должна быть в диапазоне [-90, 90], получено: 91.0
    """
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Широта должна быть в диапазоне [-90, 90], получено: {lat}")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(
            f"Долгота должна быть в диапазоне [-180, 180], получено: {lon}"
        )


def validate_forecast_days(n: int) -> None:
    """Проверяет количество дней прогноза.

    Open-Meteo поддерживает от 1 до 16 дней включительно.

    Args:
        n: Количество дней прогноза.

    Raises:
        ValueError: Если n вне [1, 16].

    Examples:
        >>> validate_forecast_days(7)   # OK
        >>> validate_forecast_days(0)
        Traceback (most recent call last):
            ...
        ValueError: Количество дней прогноза должно быть от 1 до 16, получено: 0
    """
    if not (1 <= n <= 16):
        raise ValueError(
            f"Количество дней прогноза должно быть от 1 до 16, получено: {n}"
        )


def validate_temperature(t: float) -> None:
    """Проверяет физическую правдоподобность температуры.

    Не бросает исключение — только предупреждает, так как
    экстремальные значения физически возможны (рекорды: -89.2°C / +56.7°C).

    Args:
        t: Температура в градусах Цельсия.

    Warns:
        UserWarning: Если t < -90°C или t > 60°C.

    Examples:
        >>> validate_temperature(22.5)   # OK, без предупреждений
        >>> validate_temperature(-95.0)  # UserWarning
    """
    if t < -90.0 or t > 60.0:
        warnings.warn(
            f"Температура {t}°C выходит за физически правдоподобный диапазон "
            f"[-90, 60]°C. Проверьте корректность данных.",
            UserWarning,
            stacklevel=2,
        )


def validate_humidity(rh: float) -> None:
    """Проверяет корректность относительной влажности.

    Args:
        rh: Относительная влажность в процентах.

    Raises:
        ValueError: Если rh вне [0, 100].

    Examples:
        >>> validate_humidity(65.0)   # OK
        >>> validate_humidity(105.0)
        Traceback (most recent call last):
            ...
        ValueError: Относительная влажность должна быть в диапазоне [0, 100]%, получено: 105.0
    """
    if not (0.0 <= rh <= 100.0):
        raise ValueError(
            f"Относительная влажность должна быть в диапазоне [0, 100]%, получено: {rh}"
        )


def validate_wind_speed(v: float) -> None:
    """Проверяет физическую правдоподобность скорости ветра.

    Максимальная зарегистрированная скорость ветра ~113 м/с (торнадо).
    Порог 120 м/с с запасом.

    Args:
        v: Скорость ветра в м/с.

    Raises:
        ValueError: Если v вне [0, 120].

    Examples:
        >>> validate_wind_speed(10.0)   # OK
        >>> validate_wind_speed(-1.0)
        Traceback (most recent call last):
            ...
        ValueError: Скорость ветра должна быть в диапазоне [0, 120] м/с, получено: -1.0
    """
    if not (0.0 <= v <= 120.0):
        raise ValueError(
            f"Скорость ветра должна быть в диапазоне [0, 120] м/с, получено: {v}"
        )
