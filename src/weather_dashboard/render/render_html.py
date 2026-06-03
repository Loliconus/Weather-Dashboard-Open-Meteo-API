# =============================================================
# ПУТЬ        : src/weather_dashboard/render/render_html.py
# ОБОЗНАЧЕНИЕ : WD.REND.02
# НАИМЕНОВАНИЕ: Генератор HTML-отчёта через Jinja2
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : jinja2, pathlib, datetime,
#               weather_dashboard.calc, weather_dashboard.bootstrap.ledger
# =============================================================
# Назначение:
#   HtmlRenderer.render() принимает все расчётные данные,
#   рендерит index.html.j2 и записывает docs/index.html.
#   Шаблон читается из render/templates/.
#   Проверка: pytest tests/unit/test_render_html.py
# =============================================================

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.calc.metrics import ComfortIndex, DailyMetrics
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.calc.thresholds import ThresholdAlert
from weather_dashboard.calc.windows import WalkWindow

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"
_OUTPUT_FILE = _DOCS_DIR / "index.html"


# -------------------------------------------------------------
# Раздел 1. HtmlRenderer
# -------------------------------------------------------------


class HtmlRenderer:
    """Генерирует docs/index.html из Jinja2-шаблона.

    Инициализируется один раз, render() можно вызывать многократно.
    """

    def __init__(
        self,
        templates_dir: Path | None = None,
        output_path: Path | None = None,
        ledger: LedgerLogger | None = None,
    ) -> None:
        self._tpl_dir = templates_dir or _TEMPLATES_DIR
        self._output = output_path or _OUTPUT_FILE
        self._ledger = ledger
        self._env = Environment(
            loader=FileSystemLoader(str(self._tpl_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def render(
        self,
        norm: NormalizedForecast,
        daily_metrics: list[DailyMetrics],
        comfort: ComfortIndex,
        walk_window: WalkWindow | None,
        alerts: list[ThresholdAlert],
        location_name: str = "",
        location_lat: float = 0.0,
        location_lon: float = 0.0,
        build_mode: str = "nominal",
        last_updated: str = "",
    ) -> None:
        """Отрендерить index.html и записать в docs/.

        Args:
            norm:           Нормализованный прогноз.
            daily_metrics:  Суточные метрики (7 дней).
            comfort:        ComfortIndex за ближайшие сутки.
            walk_window:    Лучшее окно прогулки (или None).
            alerts:         Пороговые предупреждения.
            location_name:  Название города.
            location_lat:   Широта.
            location_lon:   Долгота.
            build_mode:     "nominal" | "degraded".
            last_updated:   ISO-строка последнего успешного обновления.
        """
        render_id = self._log("html_renderer", "render_start")

        context = self._build_context(
            norm, daily_metrics, comfort, walk_window, alerts,
            location_name, location_lat, location_lon,
            build_mode, last_updated,
        )

        template = self._env.get_template("index.html.j2")
        html = template.render(**context)

        self._output.parent.mkdir(parents=True, exist_ok=True)
        self._output.write_text(html, encoding="utf-8")

        self._log("html_renderer", "render_complete",
                  cause=render_id, output=str(self._output))

    # ----------------------------------------------------------
    # Раздел 2. Построение контекста
    # ----------------------------------------------------------

    def _build_context(
        self,
        norm: NormalizedForecast,
        daily_metrics: list[DailyMetrics],
        comfort: ComfortIndex,
        walk_window: WalkWindow | None,
        alerts: list[ThresholdAlert],
        location_name: str,
        location_lat: float,
        location_lon: float,
        build_mode: str,
        last_updated: str,
    ) -> dict[str, Any]:
        """Собрать контекст для шаблона."""
        now = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

        # Текущие условия — первый час прогноза
        current = self._current_conditions(norm)

        # Почасовой ряд для графиков (первые 48 часов)
        hourly_48 = self._hourly_slice(norm, 48)

        # Суточная таблица
        daily_table = self._daily_table(norm, daily_metrics)

        return {
            # Мета
            "generated_at": now,
            "last_updated": last_updated or now,
            "build_mode": build_mode,
            "is_degraded": build_mode == "degraded",
            # Локация
            "location_name": location_name,
            "location_lat": location_lat,
            "location_lon": location_lon,
            "timezone": norm.timezone,
            # Текущие условия
            "current": current,
            # Данные для графиков (JSON-строки для JS)
            "hourly_48": hourly_48,
            # Таблицы
            "daily_table": daily_table,
            "hourly_table": self._hourly_table(norm, 24),
            # Расчёты
            "comfort": comfort,
            "walk_window": walk_window,
            "alerts": alerts,
            "daily_metrics": daily_metrics,
            # Единицы
            "hourly_units": norm.hourly_units,
            "daily_units": norm.daily_units,
        }

    def _current_conditions(self, norm: NormalizedForecast) -> dict[str, Any]:
        """Извлечь текущие условия (первый час прогноза)."""
        def _get(arr: list[Any], default: Any = 0) -> Any:
            return arr[0] if arr else default

        return {
            "temperature": _get(norm.temperature_2m, 0.0),
            "apparent_temperature": _get(norm.apparent_temperature, 0.0),
            "humidity": _get(norm.relative_humidity_2m, 0.0),
            "dew_point": _get(norm.dew_point_2m, 0.0),
            "precipitation": _get(norm.precipitation, 0.0),
            "precip_prob": _get(norm.precipitation_probability, 0.0),
            "wind_speed": _get(norm.wind_speed_10m, 0.0),
            "wind_direction": _get(norm.wind_direction_10m, 0.0),
            "wind_gusts": _get(norm.wind_gusts_10m, 0.0),
            "weather_code": _get(norm.weather_code, 0),
            "time": norm.hourly_times[0].isoformat() if norm.hourly_times else "",
        }

    def _hourly_slice(self, norm: NormalizedForecast, n: int) -> dict[str, Any]:
        """Срез почасового ряда для графиков (первые n часов)."""
        limit = min(n, norm.n_hourly)
        return {
            "labels": [dt.strftime("%d.%m %H:%M") for dt in norm.hourly_times[:limit]],
            "temperature_2m": norm.temperature_2m[:limit],
            "apparent_temperature": norm.apparent_temperature[:limit],
            "precipitation_probability": norm.precipitation_probability[:limit],
            "precipitation": norm.precipitation[:limit],
            "wind_speed_10m": norm.wind_speed_10m[:limit],
            "wind_gusts_10m": norm.wind_gusts_10m[:limit],
        }

    def _hourly_table(self, norm: NormalizedForecast, n: int) -> list[dict[str, Any]]:
        """Сформировать строки почасовой таблицы."""
        limit = min(n, norm.n_hourly)
        rows = []
        for i in range(limit):
            rows.append({
                "time": norm.hourly_times[i].strftime("%H:%M") if i < len(norm.hourly_times) else "",
                "temp": f"{norm.temperature_2m[i]:.1f}" if i < len(norm.temperature_2m) else "—",
                "feels": f"{norm.apparent_temperature[i]:.1f}" if i < len(norm.apparent_temperature) else "—",
                "humidity": f"{norm.relative_humidity_2m[i]:.0f}" if i < len(norm.relative_humidity_2m) else "—",
                "precip_prob": f"{norm.precipitation_probability[i]:.0f}" if i < len(norm.precipitation_probability) else "—",
                "wind": f"{norm.wind_speed_10m[i]:.1f}" if i < len(norm.wind_speed_10m) else "—",
                "gusts": f"{norm.wind_gusts_10m[i]:.1f}" if i < len(norm.wind_gusts_10m) else "—",
            })
        return rows

    def _daily_table(
        self,
        norm: NormalizedForecast,
        daily_metrics: list[DailyMetrics],
    ) -> list[dict[str, Any]]:
        """Сформировать строки суточной таблицы."""
        rows = []
        for i in range(norm.n_daily):
            dm = daily_metrics[i] if i < len(daily_metrics) else None
            rows.append({
                "date": norm.daily_times[i].strftime("%d.%m") if i < len(norm.daily_times) else "—",
                "t_max": f"{norm.temperature_2m_max[i]:.1f}" if i < len(norm.temperature_2m_max) else "—",
                "t_min": f"{norm.temperature_2m_min[i]:.1f}" if i < len(norm.temperature_2m_min) else "—",
                "precip_sum": f"{norm.precipitation_sum[i]:.1f}" if i < len(norm.precipitation_sum) else "—",
                "precip_prob": f"{norm.precipitation_probability_max[i]:.0f}" if i < len(norm.precipitation_probability_max) else "—",
                "wind_gust": f"{norm.wind_gusts_10m_max[i]:.1f}" if i < len(norm.wind_gusts_10m_max) else "—",
                "sunrise": norm.sunrise[i] if i < len(norm.sunrise) else "—",
                "sunset": norm.sunset[i] if i < len(norm.sunset) else "—",
                "solar": f"{norm.shortwave_radiation_sum[i]:.1f}" if i < len(norm.shortwave_radiation_sum) else "—",
                "t_mean": f"{dm.t_mean_day:.1f}" if dm else "—",
                "t_amp": f"{dm.t_amp_day:.1f}" if dm else "—",
                "rain_h50": str(dm.rain_hours_50) if dm else "—",
            })
        return rows

    # ----------------------------------------------------------
    # Раздел 3. Утилиты
    # ----------------------------------------------------------

    def _log(self, subject: str, action: str,
             cause: str | None = None, **ctx: Any) -> str:
        if self._ledger:
            return self._ledger.fact(subject=subject, action=action,
                                     cause=cause, **ctx)
        return ""