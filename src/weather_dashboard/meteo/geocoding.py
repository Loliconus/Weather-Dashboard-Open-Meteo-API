# =============================================================
# ПУТЬ        : src/weather_dashboard/meteo/geocoding.py
# ОБОЗНАЧЕНИЕ : WD.METEO.02
# НАИМЕНОВАНИЕ: Клиент Open-Meteo Geocoding API
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : httpx, dataclasses, weather_dashboard.bootstrap.ledger
# =============================================================
# Назначение:
#   GeocodingClient.search() ищет локации по имени через
#   https://geocoding-api.open-meteo.com/v1/search.
#   Контракты из ТЗ раздел 4.2:
#     - name обязателен
#     - count по умолчанию 10, максимум 100
#     - language (lowercase), countryCode (ISO 3166-1 alpha-2)
#     - ошибки: HTTP 400 + JSON {"error": true, "reason": "..."}
#     - пустые результаты возвращают пустой список (не ошибка)
#   Проверка: pytest tests/unit/test_geocoding.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from weather_dashboard.bootstrap.ledger import LedgerLogger

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_BASE_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
_DEFAULT_TIMEOUT: float = 15.0
_DEFAULT_COUNT: int = 10
_MAX_COUNT: int = 100


# -------------------------------------------------------------
# Раздел 1. Типы данных
# -------------------------------------------------------------


@dataclass
class GeocodingResult:
    """Одна локация из ответа Geocoding API.

    Используется для отображения в UI (панель выбора локации, ТЗ 6.1).
    Атрибуты соответствуют полям ответа Open-Meteo Geocoding API.
    """

    id: int
    name: str
    latitude: float
    longitude: float
    country: str = ""
    country_code: str = ""
    admin1: str = ""        # Регион/область первого уровня
    timezone: str = "auto"
    population: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        """Человекочитаемое название для UI."""
        parts = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


class GeocodingError(Exception):
    """Ошибка запроса к Geocoding API.

    Атрибут reason содержит поле "reason" из JSON-ошибки
    (ТЗ раздел 4.2: HTTP 400 + {"error": true, "reason": "..."}).
    """

    def __init__(self, message: str, status_code: int = 0, reason: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


# -------------------------------------------------------------
# Раздел 2. Клиент
# -------------------------------------------------------------


class GeocodingClient:
    """HTTP-клиент для Open-Meteo Geocoding API.

    Использует httpx.Client (синхронный). Все значимые события
    фиксируются через LedgerLogger если он передан.

    Пример использования:
        client = GeocodingClient(ledger=rt.ledger)
        results = client.search("Москва", language="ru", count=5)
        for r in results:
            print(r.display_name, r.latitude, r.longitude)
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

    def search(
        self,
        name: str,
        count: int = _DEFAULT_COUNT,
        language: str = "ru",
        country_code: str = "",
    ) -> list[GeocodingResult]:
        """Найти локации по названию.

        Args:
            name:         Название города/посёлка. Обязателен.
                          2 символа → точные совпадения,
                          3+ символа → fuzzy (ТЗ 4.2).
            count:        Максимальное число результатов [1, 100].
                          По умолчанию 10 (ТЗ 4.2).
            language:     Язык результатов (lowercase ISO 639-1).
                          По умолчанию "ru".
            country_code: Фильтр по стране (ISO 3166-1 alpha-2).
                          Пустая строка = без фильтра.

        Returns:
            Список GeocodingResult. Пустой список если ничего не найдено.

        Raises:
            ValueError:      name пустой или count вне диапазона.
            GeocodingError:  HTTP-ошибка или JSON-ошибка от API.
        """
        self._validate_inputs(name, count)
        params = self._build_params(name, count, language, country_code)

        search_id = self._log_fact(
            "geocoding_api", "search_start",
            query=name, count=count, language=language,
        )

        try:
            raw = self._do_request(params)
        except GeocodingError:
            self._log_fact("geocoding_api", "search_error",
                           cause=search_id, level="ERROR", query=name)
            raise

        results = self._parse_results(raw)

        self._log_fact(
            "geocoding_api", "search_complete",
            cause=search_id,
            results_count=len(results),
            query=name,
        )

        return results

    # ----------------------------------------------------------
    # Раздел 4. Вспомогательные методы
    # ----------------------------------------------------------

    def _validate_inputs(self, name: str, count: int) -> None:
        """Проверить входные параметры."""
        if not name or not name.strip():
            raise ValueError("name не может быть пустым")

        if not (1 <= count <= _MAX_COUNT):
            raise ValueError(
                f"count={count} вне допустимого диапазона"
                f" [1, {_MAX_COUNT}]"
            )

    def _build_params(
        self,
        name: str,
        count: int,
        language: str,
        country_code: str,
    ) -> dict[str, Any]:
        """Собрать словарь параметров для GET-запроса."""
        params: dict[str, Any] = {
            "name": name,
            "count": count,
            "language": language.lower(),
            "format": "json",
        }
        if country_code:
            params["countryCode"] = country_code.upper()
        return params

    def _do_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Выполнить HTTP GET запрос и вернуть JSON.

        Raises:
            GeocodingError: HTTP-ошибка или JSON {"error": true}.
        """
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise GeocodingError(
                f"Таймаут запроса к Geocoding API: {exc}",
                status_code=0,
            ) from exc
        except httpx.RequestError as exc:
            raise GeocodingError(
                f"Ошибка сети при запросе к Geocoding API: {exc}",
                status_code=0,
            ) from exc

        # ТЗ 4.2: ошибки возвращаются с HTTP 400 + {"error": true, "reason": "..."}
        if response.status_code != 200:
            reason = ""
            try:
                body = response.json()
                reason = body.get("reason", "")
            except Exception:  # noqa: BLE001
                pass
            raise GeocodingError(
                f"Geocoding API вернул HTTP {response.status_code}: {reason}",
                status_code=response.status_code,
                reason=reason,
            )

        data: dict[str, Any] = response.json()

        if data.get("error"):
            reason = data.get("reason", "неизвестная ошибка")
            raise GeocodingError(
                f"Geocoding API вернул ошибку: {reason}",
                status_code=200,
                reason=reason,
            )

        return data

    def _parse_results(self, raw: dict[str, Any]) -> list[GeocodingResult]:
        """Разобрать JSON-ответ в список GeocodingResult.

        Пустой ответ ({"results": null} или {}) — возвращает [].
        Это штатное поведение при отсутствии совпадений (ТЗ 4.2).
        """
        items = raw.get("results") or []
        results: list[GeocodingResult] = []

        for item in items:
            try:
                results.append(
                    GeocodingResult(
                        id=int(item.get("id", 0)),
                        name=str(item.get("name", "")),
                        latitude=float(item.get("latitude", 0.0)),
                        longitude=float(item.get("longitude", 0.0)),
                        country=str(item.get("country", "")),
                        country_code=str(item.get("country_code", "")),
                        admin1=str(item.get("admin1", "")),
                        timezone=str(item.get("timezone", "auto")),
                        population=int(item.get("population", 0)),
                        raw=item,
                    )
                )
            except (TypeError, ValueError):
                # Пропускаем некорректные записи — не ломаем весь список
                continue

        return results

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