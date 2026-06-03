# =============================================================
# ПУТЬ        : tests/unit/test_open_meteo.py
# ОБОЗНАЧЕНИЕ : WD.TEST.05
# НАИМЕНОВАНИЕ: Тесты клиента Forecast API
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, unittest.mock, httpx, weather_dashboard.meteo.open_meteo
# =============================================================
# Назначение:
#   Покрывает ТЗ раздел 11.1 п.1:
#     - корректная сборка URL/params (timezone обязателен при daily)
#     - обработка HTTP 4xx/5xx ошибок
#     - обработка JSON-ошибки {"error": true, "reason": "..."}
#     - обработка сетевых ошибок (timeout, connection error)
#     - contradiction() при daily без timezone
#   Проверка: pytest tests/unit/test_open_meteo.py -v
# =============================================================

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tests.conftest import CapturingHandler, extract_extra
from weather_dashboard.meteo.open_meteo import (
    ForecastClient,
    ForecastError,
    ForecastResponse,
)

# -------------------------------------------------------------
# Раздел 0. Фикстуры и вспомогательные функции
# -------------------------------------------------------------


def _mock_response(
    status_code: int = 200,
    body: dict[str, Any] | None = None,
) -> MagicMock:
    """Создать мок httpx.Response."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = body or {}
    return mock


def _minimal_forecast_body() -> dict[str, Any]:
    """Минимальный валидный ответ Forecast API."""
    return {
        "latitude": 55.7558,
        "longitude": 37.6176,
        "timezone": "Europe/Moscow",
        "hourly_units": {"temperature_2m": "°C"},
        "hourly": {
            "time": ["2026-06-03T00:00", "2026-06-03T01:00"],
            "temperature_2m": [18.0, 17.5],
        },
        "daily_units": {"temperature_2m_max": "°C"},
        "daily": {
            "time": ["2026-06-03"],
            "temperature_2m_max": [24.0],
        },
    }


# -------------------------------------------------------------
# Раздел 1. Тесты сборки параметров запроса
# -------------------------------------------------------------


@pytest.mark.unit()
def test_build_params_basic() -> None:
    """_build_params возвращает latitude, longitude, timezone, forecast_days."""
    client = ForecastClient()
    params = client._build_params(55.7558, 37.6176, None, None, "auto", 7)

    assert params["latitude"] == 55.7558
    assert params["longitude"] == 37.6176
    assert params["timezone"] == "auto"
    assert params["forecast_days"] == 7


@pytest.mark.unit()
def test_build_params_hourly_joined() -> None:
    """Список hourly переменных объединяется через запятую."""
    client = ForecastClient()
    params = client._build_params(
        55.0, 37.0,
        ["temperature_2m", "wind_speed_10m"],
        None,
        "auto",
        7,
    )
    assert params["hourly"] == "temperature_2m,wind_speed_10m"


@pytest.mark.unit()
def test_build_params_daily_joined() -> None:
    """Список daily переменных объединяется через запятую."""
    client = ForecastClient()
    params = client._build_params(
        55.0, 37.0,
        None,
        ["temperature_2m_max", "sunrise"],
        "Europe/Moscow",
        7,
    )
    assert params["daily"] == "temperature_2m_max,sunrise"


@pytest.mark.unit()
def test_build_params_no_hourly_no_daily() -> None:
    """Без hourly/daily ключи не добавляются в params."""
    client = ForecastClient()
    params = client._build_params(55.0, 37.0, None, None, "auto", 7)
    assert "hourly" not in params
    assert "daily" not in params


@pytest.mark.unit()
def test_build_params_timezone_auto() -> None:
    """timezone='auto' передаётся как есть (ТЗ 4.1)."""
    client = ForecastClient()
    params = client._build_params(55.0, 37.0, None, None, "auto", 7)
    assert params["timezone"] == "auto"


# -------------------------------------------------------------
# Раздел 2. Тесты валидации входных данных
# -------------------------------------------------------------


@pytest.mark.unit()
def test_validate_daily_without_timezone_raises() -> None:
    """daily без timezone → ValueError (ТЗ 4.1: timezone обязателен)."""
    client = ForecastClient()
    with pytest.raises(ValueError, match="timezone обязателен"):
        client._validate_inputs(55.0, 37.0, ["temperature_2m_max"], "", 7)


@pytest.mark.unit()
def test_validate_daily_with_auto_timezone_ok() -> None:
    """daily с timezone='auto' — валидация проходит."""
    client = ForecastClient()
    # Не должно поднимать исключение
    client._validate_inputs(55.0, 37.0, ["temperature_2m_max"], "auto", 7)


@pytest.mark.unit()
def test_validate_daily_without_timezone_logs_contradiction(
    capturing_handler: CapturingHandler,
) -> None:
    """daily без timezone → contradiction() в ledger (ТЗ 8.3)."""
    from weather_dashboard.bootstrap.ledger import LedgerLogger

    ledger = LedgerLogger(corr_id="test-corr-id")
    client = ForecastClient(ledger=ledger)

    with pytest.raises(ValueError):
        client._validate_inputs(55.0, 37.0, ["temperature_2m_max"], "", 7)

    contradiction_records = [
        r for r in capturing_handler.records
        if getattr(r, "kind", None) == "contradiction"
    ]
    assert contradiction_records, "contradiction() не вызван при daily без timezone"
    extra = extract_extra(contradiction_records[0])
    assert extra["subject"] == "forecast_client.config"


@pytest.mark.unit()
def test_validate_invalid_latitude_raises() -> None:
    """latitude вне [-90, 90] → ValueError."""
    client = ForecastClient()
    with pytest.raises(ValueError, match="latitude"):
        client._validate_inputs(91.0, 37.0, None, "auto", 7)


@pytest.mark.unit()
def test_validate_invalid_longitude_raises() -> None:
    """longitude вне [-180, 180] → ValueError."""
    client = ForecastClient()
    with pytest.raises(ValueError, match="longitude"):
        client._validate_inputs(55.0, 181.0, None, "auto", 7)


@pytest.mark.unit()
def test_validate_forecast_days_too_large_raises() -> None:
    """forecast_days > 16 → ValueError (ТЗ 4.1: максимум 16)."""
    client = ForecastClient()
    with pytest.raises(ValueError, match="forecast_days"):
        client._validate_inputs(55.0, 37.0, None, "auto", 17)


@pytest.mark.unit()
def test_validate_forecast_days_zero_raises() -> None:
    """forecast_days = 0 → ValueError."""
    client = ForecastClient()
    with pytest.raises(ValueError, match="forecast_days"):
        client._validate_inputs(55.0, 37.0, None, "auto", 0)


# -------------------------------------------------------------
# Раздел 3. Тесты HTTP-ошибок
# -------------------------------------------------------------


@pytest.mark.unit()
def test_do_request_http_400_raises_forecast_error() -> None:
    """HTTP 400 с JSON-ошибкой → ForecastError с reason (ТЗ 4.1)."""
    error_body = {"error": True, "reason": "Invalid parameter: timezone"}
    mock_resp = _mock_response(status_code=400, body=error_body)

    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.return_value = mock_resp

        with pytest.raises(ForecastError) as exc_info:
            client._do_request({"latitude": 55.0})

    assert exc_info.value.status_code == 400
    assert "Invalid parameter" in exc_info.value.reason


@pytest.mark.unit()
def test_do_request_http_500_raises_forecast_error() -> None:
    """HTTP 500 → ForecastError со статус-кодом 500."""
    mock_resp = _mock_response(status_code=500, body={"error": True})

    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.return_value = mock_resp

        with pytest.raises(ForecastError) as exc_info:
            client._do_request({})

    assert exc_info.value.status_code == 500


@pytest.mark.unit()
def test_do_request_json_error_field_raises() -> None:
    """HTTP 200 + {"error": true} → ForecastError (некоторые ошибки API)."""
    error_body = {"error": True, "reason": "No data available"}
    mock_resp = _mock_response(status_code=200, body=error_body)

    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.return_value = mock_resp

        with pytest.raises(ForecastError) as exc_info:
            client._do_request({})

    assert "No data available" in exc_info.value.reason


@pytest.mark.unit()
def test_do_request_timeout_raises_forecast_error() -> None:
    """httpx.TimeoutException → ForecastError."""
    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(ForecastError) as exc_info:
            client._do_request({})

    assert exc_info.value.status_code == 0


@pytest.mark.unit()
def test_do_request_connection_error_raises_forecast_error() -> None:
    """httpx.ConnectError → ForecastError."""
    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.side_effect = httpx.ConnectError("connection refused")

        with pytest.raises(ForecastError) as exc_info:
            client._do_request({})

    assert exc_info.value.status_code == 0


# -------------------------------------------------------------
# Раздел 4. Тесты успешного ответа
# -------------------------------------------------------------


@pytest.mark.unit()
def test_do_request_success_returns_dict() -> None:
    """HTTP 200 с валидным JSON → словарь данных."""
    body = _minimal_forecast_body()
    mock_resp = _mock_response(status_code=200, body=body)

    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.return_value = mock_resp

        result = client._do_request({"latitude": 55.7558})

    assert result["latitude"] == 55.7558
    assert "hourly" in result


@pytest.mark.unit()
def test_parse_response_fills_forecast_response() -> None:
    """_parse_response корректно заполняет ForecastResponse."""
    body = _minimal_forecast_body()
    client = ForecastClient()
    resp = client._parse_response(body)

    assert isinstance(resp, ForecastResponse)
    assert resp.latitude == pytest.approx(55.7558)
    assert resp.longitude == pytest.approx(37.6176)
    assert resp.timezone == "Europe/Moscow"
    assert "temperature_2m" in resp.hourly
    assert resp.hourly_units["temperature_2m"] == "°C"
    assert "temperature_2m_max" in resp.daily


@pytest.mark.unit()
def test_parse_response_empty_body_safe() -> None:
    """_parse_response с пустым телом — не падает, возвращает дефолты."""
    client = ForecastClient()
    resp = client._parse_response({})

    assert resp.latitude == pytest.approx(0.0)
    assert resp.hourly == {}
    assert resp.daily == {}


@pytest.mark.unit()
def test_fetch_full_cycle_success() -> None:
    """fetch() полный цикл: валидация → запрос → ForecastResponse."""
    body = _minimal_forecast_body()
    mock_resp = _mock_response(status_code=200, body=body)

    client = ForecastClient()
    with patch("httpx.Client") as mock_client_cls:
        mock_ctx = mock_client_cls.return_value.__enter__.return_value
        mock_ctx.get.return_value = mock_resp

        resp = client.fetch(
            latitude=55.7558,
            longitude=37.6176,
            hourly=["temperature_2m"],
            daily=["temperature_2m_max"],
            timezone="auto",
            forecast_days=7,
        )

    assert isinstance(resp, ForecastResponse)
    assert resp.latitude == pytest.approx(55.7558)