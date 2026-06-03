# =============================================================
# ПУТЬ        : src/weather_dashboard/__main__.py
# ОБОЗНАЧЕНИЕ : WD.PKG.01
# НАИМЕНОВАНИЕ: Точка входа — полный пайплайн генератора
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : weather_dashboard.bootstrap, weather_dashboard.meteo,
#               weather_dashboard.calc, weather_dashboard.render,
#               weather_dashboard.config
# =============================================================
# Назначение:
#   Запускается командой: python -m weather_dashboard
#   Пайплайн: boot → fetch → normalize → calc → render → write
#   Состояния: init → fetched → validated → computed → rendered → published
#   Degraded-режим: при ошибке API сохраняет предыдущий latest.json.
#   Проверка: python -m weather_dashboard (exit code 0)
# =============================================================

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from weather_dashboard.bootstrap.boot import boot
from weather_dashboard.calc.metrics import calculate_comfort_index, calculate_daily_metrics
from weather_dashboard.calc.normalizer import normalize_forecast
from weather_dashboard.calc.thresholds import check_thresholds
from weather_dashboard.calc.windows import find_walk_window
from weather_dashboard.config import DEFAULT_CONFIG
from weather_dashboard.meteo.geocoding import GeocodingClient, GeocodingError
from weather_dashboard.meteo.open_meteo import ForecastClient, ForecastError
from weather_dashboard.render.data_writer import DataWriter
from weather_dashboard.render.render_html import HtmlRenderer

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
_BUILD_JSON = _DOCS_DIR / "meta" / "build.json"


def main() -> None:
    """Основная точка входа генератора отчёта."""
    rt = boot()
    loc = DEFAULT_CONFIG.location

    start_id = rt.ledger.fact(
        subject="pipeline",
        action="start",
        location_name=loc.name,
        location_lat=loc.latitude,
        location_lon=loc.longitude,
    )

    rt.ledger.transition(
        subject="pipeline",
        from_state="init",
        to_state="fetching",
        cause=start_id,
    )

    writer = DataWriter(ledger=rt.ledger)
    renderer = HtmlRenderer(ledger=rt.ledger)

    # ----------------------------------------------------------
    # Шаг 1: Fetch
    # ----------------------------------------------------------
    last_updated = _read_last_updated()
    degraded = False

    try:
        forecast_client = ForecastClient(ledger=rt.ledger)
        response = forecast_client.fetch(
            latitude=loc.latitude,
            longitude=loc.longitude,
            hourly=list(DEFAULT_CONFIG.hourly_vars),
            daily=list(DEFAULT_CONFIG.daily_vars),
            timezone=loc.timezone,
            forecast_days=DEFAULT_CONFIG.forecast_days,
        )
        last_updated = datetime.now(tz=timezone.utc).isoformat()

    except ForecastError as exc:
        rt.ledger.contradiction(
            subject="pipeline.fetch",
            thesis="требуется актуальный прогноз от Open-Meteo",
            antithesis=f"API недоступен: {exc}",
            invariant="страница не должна ломаться при ошибке API (ТЗ 5.2)",
            resolution="переход в degraded-режим, используем предыдущие данные",
            status_code=exc.status_code,
        )
        writer.write_build(
            mode="degraded",
            error=str(exc),
            location_name=loc.name,
        )
        degraded = True
        _write_degraded_html(renderer, loc.name, last_updated)
        rt.ledger.fact("pipeline", "done_degraded", cause=start_id, error=str(exc))
        sys.exit(0)

    rt.ledger.transition(
        subject="pipeline",
        from_state="fetching",
        to_state="fetched",
        cause=start_id,
    )

    # ----------------------------------------------------------
    # Шаг 2: Normalize
    # ----------------------------------------------------------
    norm = normalize_forecast(response, ledger=rt.ledger)

    rt.ledger.transition(
        subject="pipeline",
        from_state="fetched",
        to_state="validated",
        cause=start_id,
        n_hourly=norm.n_hourly,
        n_daily=norm.n_daily,
    )

    # ----------------------------------------------------------
    # Шаг 3: Calculate
    # ----------------------------------------------------------
    daily_metrics = calculate_daily_metrics(norm)
    comfort = calculate_comfort_index(norm)
    walk_window = find_walk_window(norm)
    alerts = check_thresholds(norm, ledger=rt.ledger)

    rt.ledger.fact(
        subject="calc",
        action="complete",
        cause=start_id,
        daily_metrics=len(daily_metrics),
        comfort_ci=comfort.value,
        comfort_cat=comfort.category.value,
        alerts_count=len(alerts),
        walk_window_found=walk_window is not None,
    )

    rt.ledger.transition(
        subject="pipeline",
        from_state="validated",
        to_state="computed",
        cause=start_id,
    )

    # ----------------------------------------------------------
    # Шаг 4: Write data artifacts
    # ----------------------------------------------------------
    writer.write_all(
        norm=norm,
        daily_metrics=daily_metrics,
        comfort=comfort,
        walk_window=walk_window,
        alerts=alerts,
        location_name=loc.name,
        location_lat=loc.latitude,
        location_lon=loc.longitude,
    )
    writer.write_build(
        mode="nominal",
        location_name=loc.name,
    )

    # ----------------------------------------------------------
    # Шаг 5: Render HTML
    # ----------------------------------------------------------
    renderer.render(
        norm=norm,
        daily_metrics=daily_metrics,
        comfort=comfort,
        walk_window=walk_window,
        alerts=alerts,
        location_name=loc.name,
        location_lat=loc.latitude,
        location_lon=loc.longitude,
        build_mode="nominal",
        last_updated=last_updated,
    )

    rt.ledger.transition(
        subject="pipeline",
        from_state="computed",
        to_state="rendered",
        cause=start_id,
    )

    rt.ledger.fact(
        subject="pipeline",
        action="done",
        cause=start_id,
        phase="3",
        status="nominal",
        location=loc.name,
    )

    rt.ledger.transition(
        subject="pipeline",
        from_state="rendered",
        to_state="published",
        cause=start_id,
    )

    sys.exit(0)


# -------------------------------------------------------------
# Раздел 1. Вспомогательные функции
# -------------------------------------------------------------


def _read_last_updated() -> str:
    """Прочитать время последнего успешного обновления из build.json."""
    try:
        if _BUILD_JSON.exists():
            data = json.loads(_BUILD_JSON.read_text(encoding="utf-8"))
            if data.get("mode") == "nominal":
                return data.get("generated_at", "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def _write_degraded_html(
    renderer: HtmlRenderer,
    location_name: str,
    last_updated: str,
) -> None:
    """Рендерить minimal degraded-страницу без данных."""
    from weather_dashboard.calc.metrics import ComfortIndex, ComfortCategory
    from weather_dashboard.calc.normalizer import NormalizedForecast

    renderer.render(
        norm=NormalizedForecast(),
        daily_metrics=[],
        comfort=ComfortIndex(value=0.0, category=ComfortCategory.HARD),
        walk_window=None,
        alerts=[],
        location_name=location_name,
        build_mode="degraded",
        last_updated=last_updated,
    )


if __name__ == "__main__":
    main()