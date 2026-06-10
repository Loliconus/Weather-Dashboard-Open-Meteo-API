"""Async HTTP-клиент для Open-Meteo API.

Единственная точка выхода в сеть. Только транспорт — без бизнес-логики.

Принципы:
- httpx.AsyncClient (не requests)
- tenacity retry: 3 попытки, exponential backoff, на 429 и 5xx
- Дифференцированный TTL JSON-кеш в CACHE_DIR
- Логирование: DEBUG для запросов, INFO для кеш-хитов, WARNING для retry
- User-Agent из config.py
- Все методы полностью аннотированы, возвращают dataclasses из models.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from weather_dashboard.api.endpoints import (
    DEFAULT_AIR_QUALITY,
    DEFAULT_CURRENT,
    DEFAULT_DAILY,
    DEFAULT_HOURLY,
    AirQualityVariable,
    CurrentVariable,
    DailyVariable,
    HourlyVariable,
    PrecipUnit,
    TempUnit,
    WindUnit,
)
from weather_dashboard.api.models import (
    AirQualityResponse,
    ElevationResponse,
    ForecastResponse,
    Location,
    WeatherAPIError,
    WeatherClientError,
)
from weather_dashboard.config import AppConfig
from weather_dashboard.config import config as default_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL-константы (секунды) — единственный SSOT для TTL
# ---------------------------------------------------------------------------
_TTL: dict[str, int] = {
    "current": 5 * 60,  # 5 мин
    "hourly_24h": 30 * 60,  # 30 мин
    "daily_7d": 3 * 60 * 60,  # 3 ч
    "daily_16d": 6 * 60 * 60,  # 6 ч
    "geocoding": 7 * 24 * 60 * 60,  # 7 дней
    "elevation": 0,  # ∞ — 0 означает "никогда не истекает"
    "air_quality": 60 * 60,  # 1 ч
}
_ELEVATION_NEVER_EXPIRES = True


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def _params_hash(params: dict[str, Any]) -> str:
    """SHA-256 хеш отсортированных параметров запроса.

    Args:
        params: Словарь параметров HTTP-запроса.

    Returns:
        Первые 16 символов hex-дайджеста SHA-256.
    """
    serialized = json.dumps(sorted(params.items()), ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _cache_path(cache_dir: Path, endpoint: str, params: dict[str, Any]) -> Path:
    """Путь к файлу кеша.

    Args:
        cache_dir: Директория кеша из config.
        endpoint: Короткое имя endpoint (forecast, geocoding, ...).
        params: Параметры запроса для хеширования.

    Returns:
        Path к JSON-файлу кеша.
    """
    return cache_dir / f"{endpoint}_{_params_hash(params)}.json"


def _read_cache(
    path: Path,
    ttl_seconds: int,
    *,
    never_expires: bool = False,
) -> dict[str, Any] | None:
    """Читает кеш если он существует и не устарел.

    Args:
        path: Путь к файлу кеша.
        ttl_seconds: TTL в секундах (0 = использовать never_expires).
        never_expires: Если True — TTL игнорируется.

    Returns:
        Словарь данных или None если кеш устарел / не существует.
    """
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            envelope = json.load(f)
        cached_at: float = envelope.get("_cached_at", 0.0)
        payload: dict[str, Any] = envelope.get("data", {})
        if never_expires:
            logger.info("Кеш-хит (∞ TTL): %s", path.name)
            return payload
        age = time.time() - cached_at
        if age < ttl_seconds:
            logger.info(
                "Кеш-хит (возраст %.0fs / TTL %ss): %s", age, ttl_seconds, path.name
            )
            return payload
        logger.debug(
            "Кеш устарел (возраст %.0fs / TTL %ss): %s", age, ttl_seconds, path.name
        )
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        logger.debug("Ошибка чтения кеша %s: %s", path.name, exc)
    return None


def _write_cache(path: Path, data: dict[str, Any]) -> None:
    """Записывает данные в кеш с меткой времени.

    Args:
        path: Путь к файлу кеша.
        data: JSON-сериализуемый словарь данных.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"_cached_at": time.time(), "data": data}
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("Не удалось записать кеш %s: %s", path.name, exc)


def _should_retry(exc: BaseException) -> bool:
    """Предикат retry для tenacity: повторять на 429 и 5xx.

    Args:
        exc: Исключение из предыдущей попытки.

    Returns:
        True если нужно повторить запрос.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    if isinstance(exc, httpx.TransportError):
        return True
    return False


def _log_retry(retry_state: RetryCallState) -> None:
    """Callback для логирования retry-попыток.

    Args:
        retry_state: Состояние tenacity retry.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retry попытка %d/3: %s",
        retry_state.attempt_number,
        exc,
    )


# ---------------------------------------------------------------------------
# Основной клиент
# ---------------------------------------------------------------------------
class WeatherClient:
    """Async HTTP-клиент для Open-Meteo API.

    Использовать как async context manager:

    Examples:
        >>> async with WeatherClient() as client:
        ...     forecast = await client.get_forecast(55.7558, 37.6173)

    Args:
        cfg: Конфигурация приложения. По умолчанию — синглтон config.
    """

    def __init__(self, cfg: AppConfig = default_config) -> None:
        self._cfg = cfg
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> WeatherClient:
        """Создаёт httpx.AsyncClient при входе в контекст."""
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self._cfg.USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        """Закрывает httpx.AsyncClient при выходе из контекста."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Внутренние методы ───────────────────────────────────────────────

    def _http(self) -> httpx.AsyncClient:
        """Возвращает активный httpx.AsyncClient.

        Raises:
            RuntimeError: Если клиент не инициализирован.
        """
        if self._client is None:
            raise RuntimeError(
                "WeatherClient должен использоваться как async context manager"
            )
        return self._client

    async def _get(
        self,
        url: str,
        params: dict[str, Any],
        cache_key: str,
        ttl: int,
        *,
        never_expires: bool = False,
    ) -> dict[str, Any]:
        """Выполняет GET-запрос с кешем и retry.

        Args:
            url: Полный URL endpoint.
            params: Query-параметры.
            cache_key: Короткое имя для файла кеша.
            ttl: TTL кеша в секундах.
            never_expires: Если True — кеш не устаревает.

        Returns:
            JSON-ответ в виде словаря.

        Raises:
            WeatherAPIError: При HTTP 4xx от API.
            WeatherClientError: При сетевых ошибках или исчерпании retry.
        """
        path = _cache_path(self._cfg.CACHE_DIR, cache_key, params)

        # Попытка чтения кеша
        cached = _read_cache(path, ttl, never_expires=never_expires)
        if cached is not None:
            return cached

        logger.debug("HTTP GET %s params=%s", url, params)

        @retry(
            retry=retry_if_exception(_should_retry),
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=1, max=10),
            before_sleep=_log_retry,
            reraise=True,  # ← изменить на True
        )
        async def _fetch() -> dict[str, Any]:
            # НЕ перехватываем TransportError здесь — пусть tenacity видит его
            resp = await self._http().get(url, params=params)

            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                logger.warning(
                    "HTTP 429 Too Many Requests. Retry-After: %s", retry_after
                )
                raise httpx.HTTPStatusError("429", request=resp.request, response=resp)

            if resp.status_code >= 500:
                logger.warning("HTTP %d от %s", resp.status_code, url)
                raise httpx.HTTPStatusError(
                    str(resp.status_code), request=resp.request, response=resp
                )

            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    reason = body.get("reason", "Неизвестная ошибка API")
                except Exception:
                    reason = resp.text
                raise WeatherAPIError(
                    type="https://open-meteo.com/en/docs/error",
                    title="Ошибка запроса к Open-Meteo API",
                    status=resp.status_code,
                    detail=reason,
                    instance=str(resp.url),
                )

            return dict(resp.json())

        try:
            result = await _fetch()
        except WeatherAPIError:
            raise
        except httpx.TransportError as exc:  # ← теперь ловим здесь, после retry
            stale = _read_cache(path, 0, never_expires=True)
            if stale is not None:
                logger.warning(
                    "API недоступен, используется устаревший кеш: %s", path.name
                )
                return stale
            raise WeatherClientError(
                f"Сетевая ошибка при запросе {url}: {exc}", original=exc
            ) from exc
        except Exception as exc:
            raise WeatherClientError(
                f"Неожиданная ошибка при запросе {url}: {exc}", original=exc
            ) from exc

        _write_cache(path, result)
        return result

    # ── Публичные методы ─────────────────────────────────────────────────

    async def get_forecast(
        self,
        lat: float,
        lon: float,
        *,
        timezone: str = "auto",
        forecast_days: int = 7,
        past_days: int = 1,
        temperature_unit: TempUnit = TempUnit.CELSIUS,
        wind_speed_unit: WindUnit = WindUnit.MS,
        precipitation_unit: PrecipUnit = PrecipUnit.MM,
        hourly: tuple[HourlyVariable, ...] = DEFAULT_HOURLY,
        daily: tuple[DailyVariable, ...] = DEFAULT_DAILY,
        current: tuple[CurrentVariable, ...] = DEFAULT_CURRENT,
    ) -> ForecastResponse:
        """Получает прогноз погоды для координат.

        Args:
            lat: Широта (-90..90).
            lon: Долгота (-180..180).
            timezone: IANA timezone или "auto".
                      Обязателен для daily-данных.
            forecast_days: Дней прогноза (1–16).
            past_days: Дней истории (0–92).
            temperature_unit: Единица температуры.
            wind_speed_unit: Единица скорости ветра.
            precipitation_unit: Единица осадков.
            hourly: Набор hourly-переменных.
            daily: Набор daily-переменных.
            current: Набор current-переменных.

        Returns:
            ForecastResponse с metadata, current, hourly, daily.

        Raises:
            ValueError: Если timezone не задан при запросе daily-данных.
            WeatherAPIError: При HTTP 4xx от API.
            WeatherClientError: При сетевых ошибках.
        """
        if daily and not timezone:
            raise ValueError(
                "Параметр timezone обязателен при запросе daily-данных "
                "(требование Open-Meteo API)"
            )

        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
            "forecast_days": forecast_days,
            "past_days": past_days,
            "temperature_unit": str(temperature_unit),
            "wind_speed_unit": str(wind_speed_unit),
            "precipitation_unit": str(precipitation_unit),
            "hourly": ",".join(str(v) for v in hourly),
            "daily": ",".join(str(v) for v in daily),
            "current": ",".join(str(v) for v in current),
        }

        # Выбираем TTL в зависимости от forecast_days
        ttl = _TTL["daily_7d"] if forecast_days <= 7 else _TTL["daily_16d"]

        data = await self._get(
            url=f"{self._cfg.FORECAST_BASE_URL}/forecast",
            params=params,
            cache_key="forecast",
            ttl=ttl,
        )
        return ForecastResponse.from_dict(data)

    async def search_locations(
        self,
        name: str,
        *,
        count: int = 5,
        language: str = "ru",
    ) -> list[Location]:
        """Ищет города по названию через Geocoding API.

        Args:
            name: Название города (минимум 2 символа).
            count: Максимальное количество результатов (1–100).
            language: Язык результатов (ISO 639-1).

        Returns:
            Список Location, отсортированный по релевантности API.

        Raises:
            ValueError: Если name короче 2 символов.
            WeatherAPIError: При HTTP 4xx от API.
            WeatherClientError: При сетевых ошибках.
        """
        if len(name.strip()) < 2:
            raise ValueError("Название города должно содержать минимум 2 символа")

        params: dict[str, Any] = {
            "name": name.strip(),
            "count": count,
            "language": language,
            "format": "json",
        }

        data = await self._get(
            url=f"{self._cfg.GEOCODING_BASE_URL}/search",
            params=params,
            cache_key="geocoding",
            ttl=_TTL["geocoding"],
        )

        results = data.get("results", [])
        return [Location.from_dict(r) for r in results]

    async def get_air_quality(
        self,
        lat: float,
        lon: float,
        *,
        variables: tuple[AirQualityVariable, ...] = DEFAULT_AIR_QUALITY,
    ) -> AirQualityResponse:
        """Получает данные качества воздуха для координат.

        Args:
            lat: Широта (-90..90).
            lon: Долгота (-180..180).
            variables: Набор AQ-переменных.

        Returns:
            AirQualityResponse с hourly-данными.

        Raises:
            WeatherAPIError: При HTTP 4xx от API.
            WeatherClientError: При сетевых ошибках.
        """
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(str(v) for v in variables),
        }

        data = await self._get(
            url=f"{self._cfg.AIR_QUALITY_BASE_URL}/air-quality",
            params=params,
            cache_key="air_quality",
            ttl=_TTL["air_quality"],
        )
        return AirQualityResponse.from_dict(data)

    async def get_elevation(
        self,
        lat: float,
        lon: float,
    ) -> float:
        """Получает высоту над уровнем моря для координат.

        Использует Copernicus DEM GLO-90.
        Кеш бессрочный (детерминированные данные рельефа).

        Args:
            lat: Широта (-90..90).
            lon: Долгота (-180..180).

        Returns:
            Высота над уровнем моря в метрах.

        Raises:
            WeatherAPIError: При HTTP 4xx от API.
            WeatherClientError: При сетевых ошибках.
        """
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
        }

        data = await self._get(
            url=f"{self._cfg.FORECAST_BASE_URL}/elevation",
            params=params,
            cache_key="elevation",
            ttl=0,
            never_expires=_ELEVATION_NEVER_EXPIRES,
        )
        resp = ElevationResponse.from_dict(data)
        return resp.elevation[0] if resp.elevation else 0.0
