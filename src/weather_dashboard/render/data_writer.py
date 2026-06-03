# =============================================================
# ПУТЬ        : src/weather_dashboard/render/data_writer.py
# ОБОЗНАЧЕНИЕ : WD.REND.01
# НАИМЕНОВАНИЕ: Запись артефактов данных (JSON, CSV, build.json)
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : json, csv, pathlib, datetime,
#               weather_dashboard.calc, weather_dashboard.bootstrap.ledger
# =============================================================
# Назначение:
#   DataWriter.write_all() сохраняет в docs/data/:
#     latest.json   — полный нормализованный прогноз
#     metrics.json  — суточные метрики + ComfortIndex + WalkWindow + alerts
#     hourly.csv    — почасовой ряд
#     daily.csv     — суточный ряд
#   DataWriter.write_build() сохраняет docs/meta/build.json.
#   Проверка: pytest tests/unit/test_data_writer.py
# =============================================================

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.calc.metrics import ComfortIndex, DailyMetrics
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.calc.thresholds import ThresholdAlert
from weather_dashboard.calc.windows import WalkWindow

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"
_DATA_DIR = _DOCS_DIR / "data"
_META_DIR = _DOCS_DIR / "meta"


# -------------------------------------------------------------
# Раздел 1. DataWriter
# -------------------------------------------------------------


class DataWriter:
    """Записывает артефакты данных в docs/data/ и docs/meta/.

    Все пути вычисляются относительно корня репозитория.
    Директории создаются автоматически.
    """

    def __init__(
        self,
        docs_dir: Path | None = None,
        ledger: LedgerLogger | None = None,
    ) -> None:
        self._docs = docs_dir or _DOCS_DIR
        self._data = self._docs / "data"
        self._meta = self._docs / "meta"
        self._ledger = ledger
        self._data.mkdir(parents=True, exist_ok=True)
        self._meta.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------
    # Раздел 2. Публичный API
    # ----------------------------------------------------------

    def write_all(
        self,
        norm: NormalizedForecast,
        daily_metrics: list[DailyMetrics],
        comfort: ComfortIndex,
        walk_window: WalkWindow | None,
        alerts: list[ThresholdAlert],
        location_name: str = "",
        location_lat: float = 0.0,
        location_lon: float = 0.0,
    ) -> None:
        """Записать все артефакты данных.

        Args:
            norm:           Нормализованный прогноз.
            daily_metrics:  Суточные метрики.
            comfort:        ComfortIndex за ближайшие сутки.
            walk_window:    Окно прогулки (или None).
            alerts:         Пороговые предупреждения.
            location_name:  Название локации.
            location_lat:   Широта.
            location_lon:   Долгота.
        """
        write_id = self._log("data_writer", "write_start")

        self._write_latest_json(norm, location_name, location_lat, location_lon)
        self._write_metrics_json(daily_metrics, comfort, walk_window, alerts)
        self._write_hourly_csv(norm)
        self._write_daily_csv(norm)

        self._log("data_writer", "write_complete", cause=write_id,
                  files=["latest.json", "metrics.json", "hourly.csv", "daily.csv"])

    def write_build(
        self,
        mode: str = "nominal",
        error: str = "",
        location_name: str = "",
    ) -> None:
        """Записать docs/meta/build.json со статусом сборки.

        Args:
            mode:          "nominal" | "degraded".
            error:         Сообщение ошибки если mode="degraded".
            location_name: Название локации.
        """
        build_data: dict[str, Any] = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "mode": mode,
            "location": location_name,
            "error": error,
            "next_update": "по расписанию (4x/сутки)",
        }
        path = self._meta / "build.json"
        path.write_text(
            json.dumps(build_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._log("data_writer", "build_json_written", mode=mode)

    # ----------------------------------------------------------
    # Раздел 3. Запись отдельных файлов
    # ----------------------------------------------------------

    def _write_latest_json(
        self,
        norm: NormalizedForecast,
        location_name: str,
        lat: float,
        lon: float,
    ) -> None:
        """Записать latest.json — полный почасовой + суточный ряд."""
        data: dict[str, Any] = {
            "location": {
                "name": location_name,
                "latitude": lat,
                "longitude": lon,
                "timezone": norm.timezone,
            },
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "n_hourly": norm.n_hourly,
            "n_daily": norm.n_daily,
            "hourly_units": norm.hourly_units,
            "daily_units": norm.daily_units,
            "hourly": {
                "time": [dt.isoformat() for dt in norm.hourly_times],
                "temperature_2m": norm.temperature_2m,
                "apparent_temperature": norm.apparent_temperature,
                "relative_humidity_2m": norm.relative_humidity_2m,
                "dew_point_2m": norm.dew_point_2m,
                "precipitation": norm.precipitation,
                "precipitation_probability": norm.precipitation_probability,
                "weather_code": norm.weather_code,
                "wind_speed_10m": norm.wind_speed_10m,
                "wind_direction_10m": norm.wind_direction_10m,
                "wind_gusts_10m": norm.wind_gusts_10m,
            },
            "daily": {
                "time": [dt.isoformat() for dt in norm.daily_times],
                "temperature_2m_max": norm.temperature_2m_max,
                "temperature_2m_min": norm.temperature_2m_min,
                "apparent_temperature_max": norm.apparent_temperature_max,
                "apparent_temperature_min": norm.apparent_temperature_min,
                "precipitation_sum": norm.precipitation_sum,
                "precipitation_probability_max": norm.precipitation_probability_max,
                "sunrise": norm.sunrise,
                "sunset": norm.sunset,
                "wind_gusts_10m_max": norm.wind_gusts_10m_max,
                "shortwave_radiation_sum": norm.shortwave_radiation_sum,
            },
        }
        path = self._data / "latest.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_metrics_json(
        self,
        daily_metrics: list[DailyMetrics],
        comfort: ComfortIndex,
        walk_window: WalkWindow | None,
        alerts: list[ThresholdAlert],
    ) -> None:
        """Записать metrics.json — расчётные метрики."""
        walk_data: dict[str, Any] | None = None
        if walk_window:
            walk_data = {
                "start": walk_window.start.isoformat(),
                "end": walk_window.end.isoformat(),
                "duration_hours": walk_window.duration_hours,
                "reason": walk_window.reason,
            }

        data: dict[str, Any] = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "comfort_index": {
                "value": comfort.value,
                "category": comfort.category.value,
                "t_penalty": comfort.t_penalty,
                "h_penalty": comfort.h_penalty,
                "w_penalty": comfort.w_penalty,
                "p_penalty": comfort.p_penalty,
                "hours_used": comfort.hours_used,
            },
            "walk_window": walk_data,
            "alerts": [
                {
                    "metric": a.metric,
                    "value": a.value,
                    "limit": a.limit,
                    "new_regime": a.new_regime,
                    "description": a.description,
                    "date": a.date,
                }
                for a in alerts
            ],
            "daily_metrics": [
                {
                    "date": m.date,
                    "t_mean_day": round(m.t_mean_day, 2),
                    "t_amp_day": round(m.t_amp_day, 2),
                    "rain_hours_50": m.rain_hours_50,
                    "wind_gust_max": round(m.wind_gust_max, 2),
                    "solar_sum": round(m.solar_sum, 2),
                }
                for m in daily_metrics
            ],
        }
        path = self._data / "metrics.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_hourly_csv(self, norm: NormalizedForecast) -> None:
        """Записать hourly.csv — почасовой ряд."""
        path = self._data / "hourly.csv"
        fields = [
            "time", "temperature_2m", "apparent_temperature",
            "relative_humidity_2m", "dew_point_2m",
            "precipitation", "precipitation_probability",
            "weather_code", "wind_speed_10m",
            "wind_direction_10m", "wind_gusts_10m",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for i in range(norm.n_hourly):
                writer.writerow({
                    "time": norm.hourly_times[i].isoformat() if i < len(norm.hourly_times) else "",
                    "temperature_2m": norm.temperature_2m[i] if i < len(norm.temperature_2m) else "",
                    "apparent_temperature": norm.apparent_temperature[i] if i < len(norm.apparent_temperature) else "",
                    "relative_humidity_2m": norm.relative_humidity_2m[i] if i < len(norm.relative_humidity_2m) else "",
                    "dew_point_2m": norm.dew_point_2m[i] if i < len(norm.dew_point_2m) else "",
                    "precipitation": norm.precipitation[i] if i < len(norm.precipitation) else "",
                    "precipitation_probability": norm.precipitation_probability[i] if i < len(norm.precipitation_probability) else "",
                    "weather_code": norm.weather_code[i] if i < len(norm.weather_code) else "",
                    "wind_speed_10m": norm.wind_speed_10m[i] if i < len(norm.wind_speed_10m) else "",
                    "wind_direction_10m": norm.wind_direction_10m[i] if i < len(norm.wind_direction_10m) else "",
                    "wind_gusts_10m": norm.wind_gusts_10m[i] if i < len(norm.wind_gusts_10m) else "",
                })

    def _write_daily_csv(self, norm: NormalizedForecast) -> None:
        """Записать daily.csv — суточный ряд."""
        path = self._data / "daily.csv"
        fields = [
            "time", "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max", "apparent_temperature_min",
            "precipitation_sum", "precipitation_probability_max",
            "sunrise", "sunset",
            "wind_gusts_10m_max", "shortwave_radiation_sum",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for i in range(norm.n_daily):
                writer.writerow({
                    "time": norm.daily_times[i].isoformat() if i < len(norm.daily_times) else "",
                    "temperature_2m_max": norm.temperature_2m_max[i] if i < len(norm.temperature_2m_max) else "",
                    "temperature_2m_min": norm.temperature_2m_min[i] if i < len(norm.temperature_2m_min) else "",
                    "apparent_temperature_max": norm.apparent_temperature_max[i] if i < len(norm.apparent_temperature_max) else "",
                    "apparent_temperature_min": norm.apparent_temperature_min[i] if i < len(norm.apparent_temperature_min) else "",
                    "precipitation_sum": norm.precipitation_sum[i] if i < len(norm.precipitation_sum) else "",
                    "precipitation_probability_max": norm.precipitation_probability_max[i] if i < len(norm.precipitation_probability_max) else "",
                    "sunrise": norm.sunrise[i] if i < len(norm.sunrise) else "",
                    "sunset": norm.sunset[i] if i < len(norm.sunset) else "",
                    "wind_gusts_10m_max": norm.wind_gusts_10m_max[i] if i < len(norm.wind_gusts_10m_max) else "",
                    "shortwave_radiation_sum": norm.shortwave_radiation_sum[i] if i < len(norm.shortwave_radiation_sum) else "",
                })

    # ----------------------------------------------------------
    # Раздел 4. Утилиты
    # ----------------------------------------------------------

    def _log(self, subject: str, action: str,
             cause: str | None = None, **ctx: Any) -> str:
        if self._ledger:
            return self._ledger.fact(subject=subject, action=action,
                                     cause=cause, **ctx)
        return ""