"""Dataclass-модели для всех ответов Open-Meteo API.

Все модели:
- frozen=True        — иммутабельность после создания
- __slots__=True     — меньше памяти, быстрый доступ к атрибутам
- from_dict()        — фабрика десериализации из dict (ответ API)
- to_dict()          — сериализация в dict (для Jinja2 / data.js)

float | None для всех метеопеременных:
    Open-Meteo возвращает null для недоступных измерений.
    None-значения должны обрабатываться явно в processing/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


# ---------------------------------------------------------------------------
# Геолокация
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Location:
    """Результат поиска города через Geocoding API.

    Args:
        id: Уникальный идентификатор города в базе Open-Meteo/GeoNames.
        name: Название города.
        lat: Широта (градусы, WGS84).
        lon: Долгота (градусы, WGS84).
        country_code: Двухбуквенный ISO 3166-1 alpha-2 код страны.
        timezone: IANA timezone string (например, "Europe/Moscow").
        elevation: Высота над уровнем моря, м.
        admin1: Регион/область (первый административный уровень).

    Examples:
        >>> loc = Location.from_dict({
        ...     "id": 524901, "name": "Москва", "latitude": 55.7558,
        ...     "longitude": 37.6173, "country_code": "RU",
        ...     "timezone": "Europe/Moscow", "elevation": 144.0,
        ...     "admin1": "Москва"
        ... })
        >>> loc.name
        'Москва'
    """

    id: int
    name: str
    lat: float
    lon: float
    country_code: str
    timezone: str
    elevation: float
    admin1: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт Location из словаря ответа Geocoding API.

        Args:
            data: Словарь одного элемента из results[].

        Returns:
            Экземпляр Location.

        Raises:
            KeyError: Если обязательное поле отсутствует.
            TypeError: Если тип поля несовместим.
        """
        return cls(
            id=int(data["id"]),
            name=str(data["name"]),
            lat=float(data["latitude"]),
            lon=float(data["longitude"]),
            country_code=str(data.get("country_code", "")),
            timezone=str(data.get("timezone", "UTC")),
            elevation=float(data.get("elevation", 0.0)),
            admin1=str(data.get("admin1", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует Location в JSON-совместимый словарь.

        Returns:
            Словарь с полями модели.
        """
        return {
            "id": self.id,
            "name": self.name,
            "latitude": self.lat,
            "longitude": self.lon,
            "country_code": self.country_code,
            "timezone": self.timezone,
            "elevation": self.elevation,
            "admin1": self.admin1,
        }


# ---------------------------------------------------------------------------
# Метаданные прогноза
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ForecastMetadata:
    """Метаданные ответа Forecast API.

    Args:
        latitude: Скорректированная широта (ближайшая grid-точка).
        longitude: Скорректированная долгота.
        timezone: IANA timezone string.
        utc_offset_seconds: Смещение UTC в секундах.
        generation_time_ms: Время генерации ответа на сервере, мс.
    """

    latitude: float
    longitude: float
    timezone: str
    utc_offset_seconds: int
    generation_time_ms: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт ForecastMetadata из корневого словаря ответа API.

        Args:
            data: Корневой словарь ответа /v1/forecast.

        Returns:
            Экземпляр ForecastMetadata.
        """
        return cls(
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            timezone=str(data.get("timezone", "UTC")),
            utc_offset_seconds=int(data.get("utc_offset_seconds", 0)),
            generation_time_ms=float(data.get("generationtime_ms", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "utc_offset_seconds": self.utc_offset_seconds,
            "generation_time_ms": self.generation_time_ms,
        }


# ---------------------------------------------------------------------------
# Текущая погода
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CurrentWeather:
    """Данные current-блока ответа Forecast API.

    Args:
        time: ISO 8601 timestamp текущего момента.
        temperature_2m: Температура на высоте 2м, °C.
        apparent_temperature: Ощущаемая температура, °C.
        wind_speed_10m: Скорость ветра на высоте 10м, м/с.
        relative_humidity_2m: Относительная влажность, %.
        precipitation: Осадки за текущий час, мм.
        weather_code: WMO Weather interpretation code.
    """

    time: str
    temperature_2m: float | None
    apparent_temperature: float | None
    wind_speed_10m: float | None
    relative_humidity_2m: float | None
    precipitation: float | None
    weather_code: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт CurrentWeather из блока current ответа API.

        Args:
            data: Словарь data["current"].

        Returns:
            Экземпляр CurrentWeather.
        """

        def _f(key: str) -> float | None:
            v = data.get(key)
            return float(v) if v is not None else None

        def _i(key: str) -> int | None:
            v = data.get(key)
            return int(v) if v is not None else None

        return cls(
            time=str(data.get("time", "")),
            temperature_2m=_f("temperature_2m"),
            apparent_temperature=_f("apparent_temperature"),
            wind_speed_10m=_f("wind_speed_10m"),
            relative_humidity_2m=_f("relative_humidity_2m"),
            precipitation=_f("precipitation"),
            weather_code=_i("weather_code"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {
            "time": self.time,
            "temperature_2m": self.temperature_2m,
            "apparent_temperature": self.apparent_temperature,
            "wind_speed_10m": self.wind_speed_10m,
            "relative_humidity_2m": self.relative_humidity_2m,
            "precipitation": self.precipitation,
            "weather_code": self.weather_code,
        }


# ---------------------------------------------------------------------------
# Почасовой прогноз
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class HourlyForecast:
    """Hourly-блок ответа Forecast API.

    Все метеопеременные — list[float | None].
    None означает отсутствие данных для конкретного часа.
    Длина всех списков совпадает с длиной time.

    Args:
        time: Список ISO 8601 timestamps (один на час).
        units: Словарь {переменная: единица измерения}.
        temperature_2m: Температура 2м, °C.
        apparent_temperature: Ощущаемая температура, °C.
        precipitation: Осадки, мм.
        rain: Дождь, мм.
        snowfall: Снег, см.
        precipitation_probability: Вероятность осадков, %.
        wind_speed_10m: Скорость ветра 10м, м/с.
        wind_direction_10m: Направление ветра 10м, °.
        wind_gusts_10m: Порывы ветра 10м, м/с.
        relative_humidity_2m: Относительная влажность, %.
        dew_point_2m: Точка росы, °C.
        surface_pressure: Давление у поверхности, гПа.
        shortwave_radiation: Солнечная радиация, Вт/м².
        uv_index: УФ-индекс.
        cloud_cover: Облачность, %.
        visibility: Видимость, м.
    """

    time: list[str]
    units: dict[str, str]
    temperature_2m: list[float | None]
    apparent_temperature: list[float | None]
    precipitation: list[float | None]
    rain: list[float | None]
    snowfall: list[float | None]
    precipitation_probability: list[float | None]
    wind_speed_10m: list[float | None]
    wind_direction_10m: list[float | None]
    wind_gusts_10m: list[float | None]
    relative_humidity_2m: list[float | None]
    dew_point_2m: list[float | None]
    surface_pressure: list[float | None]
    shortwave_radiation: list[float | None]
    uv_index: list[float | None]
    cloud_cover: list[float | None]
    visibility: list[float | None]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт HourlyForecast из блока hourly ответа API.

        Args:
            data: Словарь data["hourly"]; units из data["hourly_units"].

        Returns:
            Экземпляр HourlyForecast.
        """

        def _list(key: str) -> list[float | None]:
            raw = data.get(key, [])
            return [float(v) if v is not None else None for v in raw]

        return cls(
            time=list(data.get("time", [])),
            units=dict(data.get("_units", {})),
            temperature_2m=_list("temperature_2m"),
            apparent_temperature=_list("apparent_temperature"),
            precipitation=_list("precipitation"),
            rain=_list("rain"),
            snowfall=_list("snowfall"),
            precipitation_probability=_list("precipitation_probability"),
            wind_speed_10m=_list("wind_speed_10m"),
            wind_direction_10m=_list("wind_direction_10m"),
            wind_gusts_10m=_list("wind_gusts_10m"),
            relative_humidity_2m=_list("relative_humidity_2m"),
            dew_point_2m=_list("dew_point_2m"),
            surface_pressure=_list("surface_pressure"),
            shortwave_radiation=_list("shortwave_radiation"),
            uv_index=_list("uv_index"),
            cloud_cover=_list("cloud_cover"),
            visibility=_list("visibility"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {
            "time": self.time,
            "units": self.units,
            "temperature_2m": self.temperature_2m,
            "apparent_temperature": self.apparent_temperature,
            "precipitation": self.precipitation,
            "rain": self.rain,
            "snowfall": self.snowfall,
            "precipitation_probability": self.precipitation_probability,
            "wind_speed_10m": self.wind_speed_10m,
            "wind_direction_10m": self.wind_direction_10m,
            "wind_gusts_10m": self.wind_gusts_10m,
            "relative_humidity_2m": self.relative_humidity_2m,
            "dew_point_2m": self.dew_point_2m,
            "surface_pressure": self.surface_pressure,
            "shortwave_radiation": self.shortwave_radiation,
            "uv_index": self.uv_index,
            "cloud_cover": self.cloud_cover,
            "visibility": self.visibility,
        }


# ---------------------------------------------------------------------------
# Дневной прогноз
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class DailyForecast:
    """Daily-блок ответа Forecast API.

    Args:
        time: Список дат YYYY-MM-DD.
        units: Словарь {переменная: единица}.
        temperature_2m_max: Максимальная температура, °C.
        temperature_2m_min: Минимальная температура, °C.
        precipitation_sum: Сумма осадков за сутки, мм.
        wind_speed_10m_max: Максимальная скорость ветра, м/с.
        uv_index_max: Максимальный УФ-индекс.
        sunrise: ISO 8601 время восхода.
        sunset: ISO 8601 время заката.
    """

    time: list[str]
    units: dict[str, str]
    temperature_2m_max: list[float | None]
    temperature_2m_min: list[float | None]
    precipitation_sum: list[float | None]
    wind_speed_10m_max: list[float | None]
    uv_index_max: list[float | None]
    sunrise: list[str]
    sunset: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт DailyForecast из блока daily ответа API.

        Args:
            data: Словарь data["daily"]; units из data["daily_units"].

        Returns:
            Экземпляр DailyForecast.
        """

        def _list(key: str) -> list[float | None]:
            raw = data.get(key, [])
            return [float(v) if v is not None else None for v in raw]

        def _strlist(key: str) -> list[str]:
            return [str(v) for v in data.get(key, [])]

        return cls(
            time=_strlist("time"),
            units=dict(data.get("_units", {})),
            temperature_2m_max=_list("temperature_2m_max"),
            temperature_2m_min=_list("temperature_2m_min"),
            precipitation_sum=_list("precipitation_sum"),
            wind_speed_10m_max=_list("wind_speed_10m_max"),
            uv_index_max=_list("uv_index_max"),
            sunrise=_strlist("sunrise"),
            sunset=_strlist("sunset"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {
            "time": self.time,
            "units": self.units,
            "temperature_2m_max": self.temperature_2m_max,
            "temperature_2m_min": self.temperature_2m_min,
            "precipitation_sum": self.precipitation_sum,
            "wind_speed_10m_max": self.wind_speed_10m_max,
            "uv_index_max": self.uv_index_max,
            "sunrise": self.sunrise,
            "sunset": self.sunset,
        }


# ---------------------------------------------------------------------------
# Агрегированный ответ Forecast API
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ForecastResponse:
    """Полный ответ endpoint /v1/forecast.

    Args:
        metadata: Метаданные (координаты, timezone, время генерации).
        current: Текущие условия.
        hourly: Почасовой прогноз.
        daily: Дневной прогноз.
    """

    metadata: ForecastMetadata
    current: CurrentWeather
    hourly: HourlyForecast
    daily: DailyForecast

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт ForecastResponse из полного ответа /v1/forecast.

        Args:
            data: Полный JSON-ответ API в виде словаря.

        Returns:
            Экземпляр ForecastResponse.

        Raises:
            KeyError: Если обязательный блок отсутствует.
        """
        # Инжектируем units в подсловари для from_dict
        hourly_data = dict(data["hourly"])
        hourly_data["_units"] = data.get("hourly_units", {})

        daily_data = dict(data["daily"])
        daily_data["_units"] = data.get("daily_units", {})

        return cls(
            metadata=ForecastMetadata.from_dict(data),
            current=CurrentWeather.from_dict(data["current"]),
            hourly=HourlyForecast.from_dict(hourly_data),
            daily=DailyForecast.from_dict(daily_data),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {
            "metadata": self.metadata.to_dict(),
            "current": self.current.to_dict(),
            "hourly": self.hourly.to_dict(),
            "daily": self.daily.to_dict(),
        }


# ---------------------------------------------------------------------------
# Качество воздуха
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class AirQualityResponse:
    """Ответ endpoint /v1/air-quality.

    Args:
        metadata: Метаданные (координаты, timezone).
        hourly: Словарь {переменная: list[float | None]}.
        units: Словарь {переменная: единица}.
    """

    metadata: ForecastMetadata
    hourly: dict[str, list[float | None]]
    units: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт AirQualityResponse из ответа /v1/air-quality.

        Args:
            data: Полный JSON-ответ API в виде словаря.

        Returns:
            Экземпляр AirQualityResponse.
        """
        raw_hourly = data.get("hourly", {})
        parsed: dict[str, list[float | None]] = {}
        for key, values in raw_hourly.items():
            if key == "time":
                continue
            parsed[key] = [float(v) if v is not None else None for v in values]
        # Включаем time отдельно
        parsed["time"] = [str(t) for t in raw_hourly.get("time", [])]  # type: ignore[assignment]

        return cls(
            metadata=ForecastMetadata.from_dict(data),
            hourly=parsed,
            units=dict(data.get("hourly_units", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {
            "metadata": self.metadata.to_dict(),
            "hourly": self.hourly,
            "units": self.units,
        }


# ---------------------------------------------------------------------------
# Высота над уровнем моря
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ElevationResponse:
    """Ответ endpoint /v1/elevation.

    Args:
        elevation: Список высот для переданных координат (batch до 100).
    """

    elevation: list[float]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Создаёт ElevationResponse из ответа /v1/elevation.

        Args:
            data: Полный JSON-ответ API в виде словаря.

        Returns:
            Экземпляр ElevationResponse.
        """
        return cls(elevation=[float(v) for v in data.get("elevation", [])])

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в JSON-совместимый словарь."""
        return {"elevation": self.elevation}


# ---------------------------------------------------------------------------
# Ошибки API (RFC 9457 Problem Details)
# ---------------------------------------------------------------------------
@dataclass
class WeatherAPIError(Exception):
    """Ошибка HTTP 4xx от Open-Meteo API.

    Соответствует RFC 9457 Problem Details for HTTP APIs.

    Args:
        type: URI-ссылка, идентифицирующая тип проблемы.
        title: Краткое человекочитаемое описание.
        status: HTTP статус-код.
        detail: Подробное описание конкретного возникновения.
        instance: URI конкретного возникновения проблемы.

    Notes:
        Open-Meteo при HTTP 400 возвращает {"reason": "..."},
        что маппируется на поле detail.
    """

    type: str
    title: str
    status: int
    detail: str
    instance: str

    def __str__(self) -> str:
        return f"WeatherAPIError [{self.status}] {self.title}: {self.detail}"


@dataclass
class WeatherClientError(Exception):
    message: str
    original: Exception | None = None

    def __post_init__(self) -> None:
        # Явно инициализируем Exception, иначе str(self) будет пустым
        super().__init__(self.message)

    def __str__(self) -> str:
        orig = (
            f" (caused by: {type(self.original).__name__}: {self.original})"
            if self.original
            else ""
        )
        return f"WeatherClientError: {self.message}{orig}"
