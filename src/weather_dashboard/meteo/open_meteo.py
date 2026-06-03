# =============================================================
# ПУТЬ        : src/weather_dashboard/meteo/open_meteo.py
# ОБОЗНАЧЕНИЕ : WD.METEO.01
# НАИМЕНОВАНИЕ: Клиент Open-Meteo Forecast API
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : httpx, dataclasses, weather_dashboard.bootstrap.ledger
# =============================================================
# Назначение:
#   ForecastClient.fetch() запрашивает прогноз с
#   https://api.open-meteo.com/v1/forecast.
#   Контракты из ТЗ раздел 4.1:
#     - latitude/longitude обязательны
#     - timezone обязателен при daily-переменных (иначе contradiction)
#     - обрабатывает HTTP-ошибки и JSON-ошибки (error/reason)
#   Все события фиксируются через LedgerLogger.
#   Проверка: pytest tests/unit/test_open_meteo.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from weather_dashboard.bootstrap.ledger import LedgerLogger

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
_DEFAULT_TIMEOUT: float = 30.0
_MAX_FORECAST_DAYS: int = 16


# -------------------------------------------------------------
# Раздел 1. Типы данных
# -------------------------------------------------------------


@dataclass
class ForecastResponse:
    """Ответ Forecast API — сырые данные плюс единицы измерения.

    Поля hourly_units / daily_units используются в разделе 7.1 ТЗ
    для нормализации временного ряда к внутренней структуре.
    """

    latitude: float
    longitude: float
    timezone: str
    hourly: dict[str, list[Any]] = field(default_factory=dict)
    hourly_units: dict[str, str] = field(default_factory=dict)
    daily: dict[str, list[Any]] = field(default_factory=dict)
    daily_units: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class ForecastError(Exception):
    """Ошибка запроса к Forecast API.

    Атрибут reason содержит сообщение из поля "reason" JSON-ошибки
    (ТЗ раздел 4.1: API возвращает HTTP 400 + {"error": true, "reason": "..."}).
    """

    def __init__(self, message: str, status_code: int = 0, reason: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


# -------------------------------------------------------------
# Раздел 2. Клиент
# -------------------------------------------------------------


class ForecastClient:
    """HTTP-клиент для Open-Meteo Forecast API.

    Использует httpx.Client (синхронный). Все значимые события
    фиксируются через LedgerLogger если он передан.

    Пример использования:
        client = ForecastClient(ledger=rt.ledger)
        response = client.fetch(
            latitude=55.7558,
            longitude=37.6176,
            hourly=["temperature_2m", "wind_speed_10m"],
            daily=["temperature_2m_max"],
            timezone="auto",
            forecast_days=7,
        )
    """

    def __init__(
        self,
        ledger: LedgerLogger | None = None,
        base_url: str = _BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._ledger = ledger
        self._base_url = base_url
        self._timeout = timeout

    # ----------------------------------------------------------
    # Раздел 3. Публичный API
    # ----------------------------------------------------------

    def fetch(
        self,
        latitude: float,
        longitude: float,
        hourly: list[str] | None = None,
        daily: list[str] | None = None,
        timezone: str = "auto",
        forecast_days: int = 7,
    ) -> ForecastResponse:
        """Запросить прогноз погоды.

        Args:
            latitude:     Широта локации.
            longitude:    Долгота локации.
            hourly:       Список почасовых переменных (ТЗ 4.1).
            daily:        Список суточных переменных (ТЗ 4.1).
            timezone:     Временная зона. ОБЯЗАТЕЛЬНА при daily.
                          "auto" — Open-Meteo определяет по координатам.
            forecast_days: 1–16, по умолчанию 7 (ТЗ 4.1).

        Returns:
            ForecastResponse с данными и единицами измерения.

        Raises:
            ForecastError:  HTTP-ошибка или JSON-ошибка от API.
            ValueError:     daily переданы без timezone (contradiction).
        """
        self._validate_inputs(latitude, longitude, daily, timezone, forecast_days)
        params = self._build_params(latitude, longitude, hourly, daily, timezone, forecast_days)

        fetch_id = self._log_fact("open_meteo_api", "fetch_start",
                                  lat=latitude, lon=longitude,
                                  forecast_days=forecast_days)

        try:
            raw = self._do_request(params)
        except ForecastError:
            self._log_fact("open_meteo_api", "fetch_error",
                           cause=fetch_id, level="ERROR")
            raise

        self._log_fact("open_meteo_api", "fetch_complete",
                       cause=fetch_id,
                       has_hourly=bool(raw.get("hourly")),
                       has_daily=bool(raw.get("daily")))

        return self._parse_response(raw)

    # ----------------------------------------------------------
    # Раздел 4. Вспомогательные методы
    # ----------------------------------------------------------

    def _validate_inputs(
        self,
        latitude: float,
        longitude: float,
        daily: list[str] | None,
        timezone: str,
        forecast_days: int,
    ) -> None:
        """Проверить входные параметры согласно правилам ТЗ раздел 4.1."""
        # ТЗ 4.1: timezone обязателен при daily-переменных
        if daily and not timezone:
            if self._ledger:
                self._ledger.contradiction(
                    subject="forecast_client.config",
                    thesis="daily-переменные запрошены",
                    antithesis="timezone не передан",
                    invariant=(
                        "Open-Meteo требует timezone при запросе"
                        " daily-переменных (ТЗ 4.1)"
                    ),
                    resolution="fetch() отклонён с ValueError",
                )
            msg = (
                "timezone обязателен при запросе daily-переменных."
                " Передайте timezone='auto' или явное значение."
            )
            raise ValueError(msg)

        if not (-90 <= latitude <= 90):
            raise ValueError(f"latitude={latitude} вне диапазона [-90, 90]")

        if not (-180 <= longitude <= 180):
            raise ValueError(f"longitude={longitude} вне диапазона [-180, 180]")

        if not (1 <= forecast_days <= _MAX_FORECAST_DAYS):
            raise ValueError(
                f"forecast_days={forecast_days} вне диапазона"
                f" [1, {_MAX_FORECAST_DAYS}]"
            )

    def _build_params(
        self,
        latitude: float,
        longitude: float,
        hourly: list[str] | None,
        daily: list[str] | None,
        timezone: str,
        forecast_days: int,
    ) -> dict[str, Any]:
        """Собрать словарь параметров для GET-запроса."""
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "forecast_days": forecast_days,
        }
        if hourly:
            params["hourly"] = ",".join(hourly)
        if daily:
            params["daily"] = ",".join(daily)
        return params

    def _do_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Выполнить HTTP GET запрос и вернуть JSON.

        Raises:
            ForecastError: HTTP-ошибка (4xx/5xx) или JSON {"error": true}.
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise ForecastError(
                f"Таймаут запроса к Open-Meteo: {exc}",
                status_code=0,
            ) from exc
        except httpx.RequestError as exc:
            raise ForecastError(
                f"Ошибка сети при запросе к Open-Meteo: {exc}",
                status_code=0,
            ) from exc

        # ТЗ 4.1: API возвращает HTTP 400 + JSON {"error": true, "reason": "..."}
        if response.status_code != 200:
            reason = ""
            try:
                body = response.json()
                reason = body.get("reason", "")
            except Exception:  # noqa: BLE001
                pass
            raise ForecastError(
                f"Open-Meteo вернул HTTP {response.status_code}: {reason}",
                status_code=response.status_code,
                reason=reason,
            )

        data: dict[str, Any] = response.json()

        # Некоторые ошибки API возвращаются с HTTP 200 но с полем error
        if data.get("error"):
            reason = data.get("reason", "неизвестная ошибка")
            raise ForecastError(
                f"Open-Meteo вернул ошибку: {reason}",
                status_code=200,
                reason=reason,
            )

        return data

    def _parse_response(self, raw: dict[str, Any]) -> ForecastResponse:
        """Разобрать JSON-ответ в ForecastResponse."""
        return ForecastResponse(
            latitude=float(raw.get("latitude", 0.0)),
            longitude=float(raw.get("longitude", 0.0)),
            timezone=str(raw.get("timezone", "")),
            hourly=raw.get("hourly", {}),
            hourly_units=raw.get("hourly_units", {}),
            daily=raw.get("daily", {}),
            daily_units=raw.get("daily_units", {}),
            raw=raw,
        )

    # ----------------------------------------------------------
    # Раздел 5. Утилиты логирования
    # ----------------------------------------------------------

    def _log_fact(
        self,
        subject: str,
        action: str,
        cause: str | None = None,
        level: str = "INFO",
        **ctx: Any,
    ) -> str:
        """Записать факт если ledger подключён. Вернуть fact_id или ''."""
        if self._ledger:
            return self._ledger.fact(
                subject=subject,
                action=action,
                cause=cause,
                level=level,
                **ctx,
            )
        return ""