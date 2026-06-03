# =============================================================
# ПУТЬ        : tests/unit/test_data_writer.py
# ОБОЗНАЧЕНИЕ : WD.TEST.11
# НАИМЕНОВАНИЕ: Тесты записи артефактов данных (JSON, CSV)
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, pathlib, json, csv,
#               weather_dashboard.render.data_writer,
#               weather_dashboard.calc
# =============================================================
# Назначение:
#   Проверяет DataWriter.write_all() и write_build()
#   на синтетических данных в tmp-директории.
#   Проверка: pytest tests/unit/test_data_writer.py -v
# =============================================================

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from weather_dashboard.calc.metrics import ComfortCategory, ComfortIndex, DailyMetrics
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.calc.thresholds import ThresholdAlert
from weather_dashboard.calc.windows import WalkWindow
from weather_dashboard.render.data_writer import DataWriter


# -------------------------------------------------------------
# Раздел 0. Фикстуры
# -------------------------------------------------------------


@pytest.fixture()
def tmp_writer(tmp_path: Path) -> DataWriter:
    """DataWriter, пишущий в tmp_path."""
    return DataWriter(docs_dir=tmp_path)


def _make_norm(n_hourly: int = 4, n_daily: int = 2) -> NormalizedForecast:
    base = datetime(2026, 6, 3, tzinfo=timezone.utc)
    return NormalizedForecast(
        hourly_times=[base + timedelta(hours=i) for i in range(n_hourly)],
        daily_times=[base + timedelta(days=i) for i in range(n_daily)],
        temperature_2m=[20.0] * n_hourly,
        apparent_temperature=[19.0] * n_hourly,
        relative_humidity_2m=[60.0] * n_hourly,
        dew_point_2m=[12.0] * n_hourly,
        precipitation=[0.0] * n_hourly,
        precipitation_probability=[20.0] * n_hourly,
        weather_code=[0] * n_hourly,
        wind_speed_10m=[5.0] * n_hourly,
        wind_direction_10m=[180.0] * n_hourly,
        wind_gusts_10m=[8.0] * n_hourly,
        temperature_2m_max=[25.0] * n_daily,
        temperature_2m_min=[15.0] * n_daily,
        apparent_temperature_max=[24.0] * n_daily,
        apparent_temperature_min=[14.0] * n_daily,
        precipitation_sum=[1.0] * n_daily,
        precipitation_probability_max=[30.0] * n_daily,
        sunrise=["2026-06-03T04:00"] * n_daily,
        sunset=["2026-06-03T21:00"] * n_daily,
        wind_gusts_10m_max=[10.0] * n_daily,
        shortwave_radiation_sum=[18.0] * n_daily,
        timezone="Europe/Moscow",
        hourly_units={"temperature_2m": "°C"},
        daily_units={"temperature_2m_max": "°C"},
        n_hourly=n_hourly,
        n_daily=n_daily,
    )


def _make_daily_metrics(n: int = 2) -> list[DailyMetrics]:
    return [
        DailyMetrics(
            date=f"2026-06-0{i + 3}",
            t_mean_day=20.0,
            t_amp_day=5.0,
            rain_hours_50=3,
            wind_gust_max=10.0,
            solar_sum=18.0,
        )
        for i in range(n)
    ]


def _make_comfort() -> ComfortIndex:
    return ComfortIndex(
        value=75.0,
        category=ComfortCategory.COMFORTABLE,
        t_penalty=2.0,
        h_penalty=1.5,
        w_penalty=0.5,
        p_penalty=1.0,
        hours_used=24,
    )


def _make_walk_window() -> WalkWindow:
    base = datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc)
    return WalkWindow(
        start=base,
        end=base + timedelta(hours=4),
        duration_hours=4,
        reason="Тест: осадки<30%, ветер<10м/с",
    )


# -------------------------------------------------------------
# Раздел 1. Тесты write_all()
# -------------------------------------------------------------


@pytest.mark.unit()
def test_write_all_creates_latest_json(tmp_writer: DataWriter) -> None:
    """write_all() создаёт docs/data/latest.json."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=_make_walk_window(),
        alerts=[],
        location_name="Москва",
        location_lat=55.7558,
        location_lon=37.6176,
    )
    path = tmp_writer._data / "latest.json"
    assert path.exists(), "latest.json не создан"


@pytest.mark.unit()
def test_write_all_latest_json_structure(tmp_writer: DataWriter) -> None:
    """latest.json содержит location, hourly, daily, n_hourly."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
        location_lat=55.7558,
        location_lon=37.6176,
    )
    data = json.loads((tmp_writer._data / "latest.json").read_text(encoding="utf-8"))

    assert data["location"]["name"] == "Москва"
    assert data["location"]["latitude"] == pytest.approx(55.7558)
    assert data["n_hourly"] == 4
    assert data["n_daily"] == 2
    assert "hourly" in data
    assert "daily" in data


@pytest.mark.unit()
def test_write_all_creates_metrics_json(tmp_writer: DataWriter) -> None:
    """write_all() создаёт docs/data/metrics.json."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=_make_walk_window(),
        alerts=[],
        location_name="Москва",
    )
    assert (tmp_writer._data / "metrics.json").exists()


@pytest.mark.unit()
def test_write_all_metrics_json_comfort(tmp_writer: DataWriter) -> None:
    """metrics.json содержит comfort_index с корректными полями."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
    )
    data = json.loads((tmp_writer._data / "metrics.json").read_text(encoding="utf-8"))
    ci = data["comfort_index"]
    assert ci["value"] == pytest.approx(75.0)
    assert ci["category"] == "комфортно"
    assert ci["hours_used"] == 24


@pytest.mark.unit()
def test_write_all_metrics_json_walk_window(tmp_writer: DataWriter) -> None:
    """metrics.json содержит walk_window с start/end/duration."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=_make_walk_window(),
        alerts=[],
        location_name="Москва",
    )
    data = json.loads((tmp_writer._data / "metrics.json").read_text(encoding="utf-8"))
    ww = data["walk_window"]
    assert ww is not None
    assert ww["duration_hours"] == 4
    assert "start" in ww
    assert "reason" in ww


@pytest.mark.unit()
def test_write_all_metrics_json_walk_window_none(tmp_writer: DataWriter) -> None:
    """metrics.json walk_window=null когда окно не найдено."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
    )
    data = json.loads((tmp_writer._data / "metrics.json").read_text(encoding="utf-8"))
    assert data["walk_window"] is None


@pytest.mark.unit()
def test_write_all_metrics_json_alerts(tmp_writer: DataWriter) -> None:
    """metrics.json содержит список alerts."""
    alert = ThresholdAlert(
        metric="wind_gust_ms",
        value=20.0,
        limit=15.0,
        new_regime="alert",
        description="Порывы 20.0 м/с",
    )
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[alert],
        location_name="Москва",
    )
    data = json.loads((tmp_writer._data / "metrics.json").read_text(encoding="utf-8"))
    assert len(data["alerts"]) == 1
    assert data["alerts"][0]["metric"] == "wind_gust_ms"


@pytest.mark.unit()
def test_write_all_metrics_json_daily_metrics(tmp_writer: DataWriter) -> None:
    """metrics.json содержит daily_metrics с датами."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm,
        daily_metrics=_make_daily_metrics(n=2),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
    )
    data = json.loads((tmp_writer._data / "metrics.json").read_text(encoding="utf-8"))
    assert len(data["daily_metrics"]) == 2
    assert data["daily_metrics"][0]["t_mean_day"] == pytest.approx(20.0)


# -------------------------------------------------------------
# Раздел 2. Тесты CSV
# -------------------------------------------------------------


@pytest.mark.unit()
def test_write_all_creates_hourly_csv(tmp_writer: DataWriter) -> None:
    """write_all() создаёт docs/data/hourly.csv."""
    norm = _make_norm(n_hourly=4)
    tmp_writer.write_all(
        norm=norm, daily_metrics=[], comfort=_make_comfort(),
        walk_window=None, alerts=[],
    )
    assert (tmp_writer._data / "hourly.csv").exists()


@pytest.mark.unit()
def test_hourly_csv_row_count(tmp_writer: DataWriter) -> None:
    """hourly.csv содержит заголовок + n_hourly строк."""
    norm = _make_norm(n_hourly=4)
    tmp_writer.write_all(
        norm=norm, daily_metrics=[], comfort=_make_comfort(),
        walk_window=None, alerts=[],
    )
    with (tmp_writer._data / "hourly.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4


@pytest.mark.unit()
def test_hourly_csv_has_required_columns(tmp_writer: DataWriter) -> None:
    """hourly.csv содержит обязательные столбцы (ТЗ 4.1)."""
    norm = _make_norm(n_hourly=2)
    tmp_writer.write_all(
        norm=norm, daily_metrics=[], comfort=_make_comfort(),
        walk_window=None, alerts=[],
    )
    with (tmp_writer._data / "hourly.csv").open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
    assert "time" in cols
    assert "temperature_2m" in cols
    assert "wind_speed_10m" in cols
    assert "precipitation_probability" in cols


@pytest.mark.unit()
def test_write_all_creates_daily_csv(tmp_writer: DataWriter) -> None:
    """write_all() создаёт docs/data/daily.csv."""
    norm = _make_norm()
    tmp_writer.write_all(
        norm=norm, daily_metrics=[], comfort=_make_comfort(),
        walk_window=None, alerts=[],
    )
    assert (tmp_writer._data / "daily.csv").exists()


@pytest.mark.unit()
def test_daily_csv_row_count(tmp_writer: DataWriter) -> None:
    """daily.csv содержит заголовок + n_daily строк."""
    norm = _make_norm(n_daily=2)
    tmp_writer.write_all(
        norm=norm, daily_metrics=[], comfort=_make_comfort(),
        walk_window=None, alerts=[],
    )
    with (tmp_writer._data / "daily.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2


# -------------------------------------------------------------
# Раздел 3. Тесты write_build()
# -------------------------------------------------------------


@pytest.mark.unit()
def test_write_build_nominal(tmp_writer: DataWriter) -> None:
    """write_build(mode='nominal') создаёт build.json с mode=nominal."""
    tmp_writer.write_build(mode="nominal", location_name="Москва")
    data = json.loads((tmp_writer._meta / "build.json").read_text(encoding="utf-8"))
    assert data["mode"] == "nominal"
    assert data["location"] == "Москва"
    assert "generated_at" in data


@pytest.mark.unit()
def test_write_build_degraded(tmp_writer: DataWriter) -> None:
    """write_build(mode='degraded') сохраняет сообщение ошибки."""
    tmp_writer.write_build(mode="degraded", error="API timeout")
    data = json.loads((tmp_writer._meta / "build.json").read_text(encoding="utf-8"))
    assert data["mode"] == "degraded"
    assert "timeout" in data["error"].lower()


@pytest.mark.unit()
def test_write_build_creates_meta_dir(tmp_path: Path) -> None:
    """write_build() создаёт docs/meta/ если не существует."""
    docs = tmp_path / "newdocs"
    writer = DataWriter(docs_dir=docs)
    writer.write_build(mode="nominal")
    assert (docs / "meta" / "build.json").exists()