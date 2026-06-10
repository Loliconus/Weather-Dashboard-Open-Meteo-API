"""Интеграционные тесты WeatherClient — respx mock, без реальных HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from tests.conftest import (
    make_aq_dict,
    make_elevation_dict,
    make_forecast_dict,
    make_geocoding_dict,
)
from weather_dashboard.api.client import WeatherClient
from weather_dashboard.api.models import (
    AirQualityResponse,
    ForecastResponse,
    Location,
    WeatherAPIError,
    WeatherClientError,
)
from weather_dashboard.config import AppConfig

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_cfg(tmp_path: Path) -> AppConfig:
    """AppConfig с временным CACHE_DIR (изолирован от реального кеша)."""
    import dataclasses

    return dataclasses.replace(
        AppConfig(),
        CACHE_DIR=tmp_path / ".cache",
        OUTPUT_DIR=tmp_path / "docs",
    )


@pytest.fixture
def forecast_url() -> str:
    return "https://api.open-meteo.com/v1/forecast"


@pytest.fixture
def geocoding_url() -> str:
    return "https://geocoding-api.open-meteo.com/v1/search"


@pytest.fixture
def aq_url() -> str:
    return "https://air-quality-api.open-meteo.com/v1/air-quality"


@pytest.fixture
def elevation_url() -> str:
    return "https://api.open-meteo.com/v1/elevation"


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


class TestGetForecast:
    @respx.mock
    async def test_200_deserializes_correctly(self, tmp_cfg, forecast_url):
        """HTTP 200 → корректная десериализация в ForecastResponse."""
        respx.get(forecast_url).mock(
            return_value=httpx.Response(200, json=make_forecast_dict())
        )
        async with WeatherClient(tmp_cfg) as client:
            result = await client.get_forecast(
                55.7558, 37.6173, timezone="Europe/Moscow"
            )

        assert isinstance(result, ForecastResponse)
        assert result.current.temperature_2m == 22.5
        assert result.metadata.timezone == "Europe/Moscow"
        assert len(result.daily.time) == 7
        assert len(result.hourly.time) == 48

    @respx.mock
    async def test_timezone_missing_raises_before_request(self, tmp_cfg):
        """timezone='' при запросе daily → ValueError до HTTP-запроса."""
        async with WeatherClient(tmp_cfg) as client:
            with pytest.raises(ValueError, match="timezone"):
                await client.get_forecast(55.7558, 37.6173, timezone="")

        # HTTP-запрос не должен был отправляться
        assert respx.calls.call_count == 0

    @respx.mock
    async def test_400_raises_weather_api_error(self, tmp_cfg, forecast_url):
        """HTTP 400 + {"reason": "..."} → WeatherAPIError с RFC 9457."""
        respx.get(forecast_url).mock(
            return_value=httpx.Response(400, json={"reason": "Invalid latitude value"})
        )
        async with WeatherClient(tmp_cfg) as client:
            with pytest.raises(WeatherAPIError) as exc_info:
                await client.get_forecast(999.0, 0.0, timezone="auto")

        err = exc_info.value
        assert err.status == 400
        assert "Invalid latitude value" in err.detail
        assert err.title != ""
        assert err.type != ""

    @respx.mock
    async def test_429_retries_then_raises(self, tmp_cfg, forecast_url):
        """HTTP 429 → 3 retry → WeatherClientError (нет fallback-кеша)."""
        respx.get(forecast_url).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "1"})
        )
        async with WeatherClient(tmp_cfg) as client:
            with pytest.raises(WeatherClientError):
                await client.get_forecast(55.7558, 37.6173, timezone="auto")

        # Должно было быть 3 попытки
        assert respx.calls.call_count == 3

    @respx.mock
    async def test_500_retries_then_raises(self, tmp_cfg, forecast_url):
        """HTTP 500 → 3 retry → WeatherClientError."""
        respx.get(forecast_url).mock(return_value=httpx.Response(500))
        async with WeatherClient(tmp_cfg) as client:
            with pytest.raises(WeatherClientError):
                await client.get_forecast(55.7558, 37.6173, timezone="auto")

        assert respx.calls.call_count == 3

    @respx.mock
    async def test_cache_hit_no_second_request(self, tmp_cfg, forecast_url):
        """Второй вызов с теми же параметрами → кеш-хит, respx.calls == 1."""
        respx.get(forecast_url).mock(
            return_value=httpx.Response(200, json=make_forecast_dict())
        )
        async with WeatherClient(tmp_cfg) as client:
            r1 = await client.get_forecast(55.7558, 37.6173, timezone="Europe/Moscow")
            r2 = await client.get_forecast(55.7558, 37.6173, timezone="Europe/Moscow")

        assert respx.calls.call_count == 1
        assert r1.current.temperature_2m == r2.current.temperature_2m

    @respx.mock
    async def test_stale_cache_fallback_on_network_error(self, tmp_cfg, forecast_url):
        """Сетевая ошибка → fallback на устаревший кеш."""
        # Первый запрос успешен
        respx.get(forecast_url).mock(
            return_value=httpx.Response(200, json=make_forecast_dict())
        )
        async with WeatherClient(tmp_cfg) as client:
            await client.get_forecast(55.7558, 37.6173, timezone="Europe/Moscow")

        # Обнуляем TTL кеша вручную (имитируем устаревание)
        cache_files = list(tmp_cfg.CACHE_DIR.glob("forecast_*.json"))
        for f in cache_files:
            data = json.loads(f.read_text())
            data["_cached_at"] = 0.0  # устарел с эпохи Unix
            f.write_text(json.dumps(data))

        # Второй запрос — сетевая ошибка
        respx.get(forecast_url).mock(side_effect=httpx.ConnectError("conn refused"))

        async with WeatherClient(tmp_cfg) as client:
            # Должен вернуть из stale-кеша, не бросать
            result = await client.get_forecast(
                55.7558, 37.6173, timezone="Europe/Moscow"
            )

        assert isinstance(result, ForecastResponse)


# ---------------------------------------------------------------------------
# search_locations
# ---------------------------------------------------------------------------


class TestSearchLocations:
    @respx.mock
    async def test_200_returns_list_of_location(self, tmp_cfg, geocoding_url):
        respx.get(geocoding_url).mock(
            return_value=httpx.Response(200, json=make_geocoding_dict("Москва"))
        )
        async with WeatherClient(tmp_cfg) as client:
            result = await client.search_locations("Москва")

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Location)
        assert result[0].name == "Москва"
        assert result[0].lat == 55.7558

    @respx.mock
    async def test_empty_results(self, tmp_cfg, geocoding_url):
        respx.get(geocoding_url).mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        async with WeatherClient(tmp_cfg) as client:
            result = await client.search_locations("xyzXYZнеизвестнаяXYZxyz")
        assert result == []

    async def test_short_name_raises_before_request(self, tmp_cfg):
        """Строка < 2 символов → ValueError до HTTP-запроса."""
        async with WeatherClient(tmp_cfg) as client:
            with pytest.raises(ValueError, match="2 символа"):
                await client.search_locations("М")

    @respx.mock
    async def test_geocoding_cache_ttl(self, tmp_cfg, geocoding_url):
        """Geocoding кешируется на 7 дней (TTL_geocoding)."""
        respx.get(geocoding_url).mock(
            return_value=httpx.Response(200, json=make_geocoding_dict())
        )
        async with WeatherClient(tmp_cfg) as client:
            await client.search_locations("Москва")
            await client.search_locations("Москва")

        assert respx.calls.call_count == 1


# ---------------------------------------------------------------------------
# get_air_quality
# ---------------------------------------------------------------------------


class TestGetAirQuality:
    @respx.mock
    async def test_200_deserializes_correctly(self, tmp_cfg, aq_url):
        respx.get(aq_url).mock(return_value=httpx.Response(200, json=make_aq_dict()))
        async with WeatherClient(tmp_cfg) as client:
            result = await client.get_air_quality(55.7558, 37.6173)

        assert isinstance(result, AirQualityResponse)
        assert "european_aqi" in result.hourly
        assert all(v == 22.0 for v in result.hourly["european_aqi"])

    @respx.mock
    async def test_network_error_raises_client_error(self, tmp_cfg, aq_url):
        respx.get(aq_url).mock(side_effect=httpx.TimeoutException("timeout"))
        async with WeatherClient(tmp_cfg) as client:
            with pytest.raises(WeatherClientError, match="ошибка"):
                await client.get_air_quality(55.7558, 37.6173)


# ---------------------------------------------------------------------------
# get_elevation
# ---------------------------------------------------------------------------


class TestGetElevation:
    @respx.mock
    async def test_200_returns_float(self, tmp_cfg, elevation_url):
        respx.get(elevation_url).mock(
            return_value=httpx.Response(200, json=make_elevation_dict(144.0))
        )
        async with WeatherClient(tmp_cfg) as client:
            result = await client.get_elevation(55.7558, 37.6173)

        assert isinstance(result, float)
        assert result == 144.0

    @respx.mock
    async def test_elevation_cached_forever(self, tmp_cfg, elevation_url):
        """Elevation кешируется бессрочно (never_expires=True)."""
        respx.get(elevation_url).mock(
            return_value=httpx.Response(200, json=make_elevation_dict(200.0))
        )
        async with WeatherClient(tmp_cfg) as client:
            r1 = await client.get_elevation(55.7558, 37.6173)

        # Имитируем истечение обычного TTL
        for f in tmp_cfg.CACHE_DIR.glob("elevation_*.json"):
            data = json.loads(f.read_text())
            data["_cached_at"] = 0.0
            f.write_text(json.dumps(data))

        # Второй запрос — должен вернуть из кеша несмотря на 0.0 timestamp
        async with WeatherClient(tmp_cfg) as client:
            r2 = await client.get_elevation(55.7558, 37.6173)

        assert respx.calls.call_count == 1
        assert r1 == r2 == 200.0

    @respx.mock
    async def test_empty_response_returns_zero(self, tmp_cfg, elevation_url):
        respx.get(elevation_url).mock(
            return_value=httpx.Response(200, json={"elevation": []})
        )
        async with WeatherClient(tmp_cfg) as client:
            result = await client.get_elevation(55.7558, 37.6173)
        assert result == 0.0


# ---------------------------------------------------------------------------
# User-Agent header
# ---------------------------------------------------------------------------


class TestUserAgent:
    @respx.mock
    async def test_user_agent_sent(self, tmp_cfg, forecast_url):
        """Клиент отправляет корректный User-Agent."""
        route = respx.get(forecast_url).mock(
            return_value=httpx.Response(200, json=make_forecast_dict())
        )
        async with WeatherClient(tmp_cfg) as client:
            await client.get_forecast(55.7558, 37.6173, timezone="auto")

        sent_ua = route.calls[0].request.headers.get("user-agent", "")
        assert "Weather-Dashboard-Open-Meteo-API" in sent_ua
        assert "Loliconus" in sent_ua
