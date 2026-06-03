# =============================================================
# ПУТЬ        : src/weather_dashboard/config.py
# ОБОЗНАЧЕНИЕ : WD.CFG.01
# НАИМЕНОВАНИЕ: Конфигурация проекта Weather Dashboard
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : dataclasses
# =============================================================
# Назначение:
#   Единственный источник истины для всех параметров проекта:
#   дефолтная локация (Москва), переменные Open-Meteo,
#   пороги предупреждений, параметры ComfortIndex,
#   параметры "окна прогулки".
#   Параметры читаются кодом через DEFAULT_CONFIG.
#   Проверка: python -c "from weather_dashboard.config import DEFAULT_CONFIG; print(DEFAULT_CONFIG)"
# =============================================================

from __future__ import annotations

from dataclasses import dataclass, field

# -------------------------------------------------------------
# Раздел 0. Переменные Open-Meteo (ТЗ раздел 4.1)
# -------------------------------------------------------------

HOURLY_VARIABLES: tuple[str, ...] = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "precipitation_probability",
    "weather_code",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)

DAILY_VARIABLES: tuple[str, ...] = (
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "sunrise",
    "sunset",
    "wind_gusts_10m_max",
    "shortwave_radiation_sum",
)

# -------------------------------------------------------------
# Раздел 1. Датакласс конфигурации
# -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LocationConfig:
    """Конфигурация локации по умолчанию."""

    name: str
    latitude: float
    longitude: float
    timezone: str = "auto"   # ТЗ 4.1: timezone=auto разрешён


@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    """Пороги для предупреждений (ТЗ раздел 7.3)."""

    wind_gust_ms: float = 15.0      # м/с — порог порывов ветра
    precip_prob_pct: float = 70.0   # % — порог вероятности осадков
    precip_sum_mm: float = 10.0     # мм — порог суммы осадков
    frost_temp_c: float = -10.0     # °C — порог мороза
    heat_temp_c: float = 35.0       # °C — порог жары


@dataclass(frozen=True, slots=True)
class WalkWindowConfig:
    """Параметры алгоритма поиска 'окна прогулки' (ТЗ раздел 7.2 B)."""

    precip_prob_max_pct: float = 30.0   # P0: макс. вероятность осадков
    wind_speed_max_ms: float = 10.0     # W0: макс. скорость ветра
    temp_min_c: float = -5.0            # Tmin: минимальная температура
    temp_max_c: float = 30.0            # Tmax: максимальная температура
    horizon_hours: int = 48             # горизонт поиска в часах


@dataclass(frozen=True, slots=True)
class ComfortIndexConfig:
    """Коэффициенты формулы ComfortIndex (ТЗ раздел 7.2 C).

    Формула:
        CI = 100
           − k_t  · |AT − t_opt|         (отклонение "ощущаемой")
           − k_h  · max(0, RH − rh_ok)   (дискомфорт влажности)
           − k_w  · max(0, WS − ws_ok)   (дискомфорт ветра)
           − k_p  · PP / 100             (штраф за осадки)
        CI = clamp(CI, 0, 100)

    Категории:
        CI ≥ 70 → "комфортно"
        40 ≤ CI < 70 → "терпимо"
        CI < 40 → "тяжело"
    """

    t_opt: float = 22.0     # Оптимальная "ощущаемая" температура, °C
    rh_ok: float = 60.0     # Порог влажности, выше которого дискомфорт, %
    ws_ok: float = 5.0      # Порог ветра, выше которого дискомфорт, м/с
    k_t: float = 2.0        # Коэффициент отклонения температуры
    k_h: float = 0.5        # Коэффициент влажности
    k_w: float = 1.5        # Коэффициент ветра
    k_p: float = 30.0       # Коэффициент осадков


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    """Корневой конфиг проекта.

    Единственный источник всех параметров (SSOT).
    Используется как DEFAULT_CONFIG в коде пайплайна.
    """

    location: LocationConfig
    thresholds: ThresholdConfig
    walk_window: WalkWindowConfig
    comfort: ComfortIndexConfig
    forecast_days: int = 7          # ТЗ 4.1: по умолчанию 7, макс 16
    hourly_vars: tuple[str, ...] = field(default_factory=lambda: HOURLY_VARIABLES)
    daily_vars: tuple[str, ...] = field(default_factory=lambda: DAILY_VARIABLES)


# -------------------------------------------------------------
# Раздел 2. Экземпляр по умолчанию (Москва)
# -------------------------------------------------------------

DEFAULT_CONFIG = DashboardConfig(
    location=LocationConfig(
        name="Москва",
        latitude=55.7558,
        longitude=37.6176,
        timezone="auto",
    ),
    thresholds=ThresholdConfig(),
    walk_window=WalkWindowConfig(),
    comfort=ComfortIndexConfig(),
)