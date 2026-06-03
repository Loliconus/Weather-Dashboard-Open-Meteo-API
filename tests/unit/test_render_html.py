# =============================================================
# ПУТЬ        : tests/unit/test_render_html.py
# ОБОЗНАЧЕНИЕ : WD.TEST.12
# НАИМЕНОВАНИЕ: Тесты генератора HTML-отчёта
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, pathlib,
#               weather_dashboard.render.render_html,
#               weather_dashboard.calc
# =============================================================
# Назначение:
#   Проверяет HtmlRenderer.render():
#     - создание docs/index.html
#     - наличие ключевых блоков в HTML
#     - degraded-режим (баннер + режим ДЕГРАДИР.)
#     - данные локации в шапке
#     - атрибуция Open-Meteo и GeoNames (ТЗ 4.3, критерий 13.6)
#   Проверка: pytest tests/unit/test_render_html.py -v
# =============================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from weather_dashboard.calc.metrics import ComfortCategory, ComfortIndex, DailyMetrics
from weather_dashboard.calc.normalizer import NormalizedForecast
from weather_dashboard.calc.thresholds import ThresholdAlert
from weather_dashboard.calc.windows import WalkWindow
from weather_dashboard.render.render_html import HtmlRenderer


# -------------------------------------------------------------
# Раздел 0. Фикстуры
# -------------------------------------------------------------


@pytest.fixture()
def tmp_renderer(tmp_path: Path) -> HtmlRenderer:
    """HtmlRenderer, пишущий index.html в tmp_path."""
    from pathlib import Path as P
    templates_dir = P(__file__).parent.parent.parent / "src" / "weather_dashboard" / "render" / "templates"
    return HtmlRenderer(
        templates_dir=templates_dir,
        output_path=tmp_path / "index.html",
    )


def _make_norm(n: int = 24) -> NormalizedForecast:
    base = datetime(2026, 6, 3, tzinfo=timezone.utc)
    return NormalizedForecast(
        hourly_times=[base + timedelta(hours=i) for i in range(n)],
        daily_times=[base + timedelta(days=i) for i in range(7)],
        temperature_2m=[20.0] * n,
        apparent_temperature=[19.0] * n,
        relative_humidity_2m=[60.0] * n,
        dew_point_2m=[12.0] * n,
        precipitation=[0.0] * n,
        precipitation_probability=[20.0] * n,
        weather_code=[0] * n,
        wind_speed_10m=[5.0] * n,
        wind_direction_10m=[180.0] * n,
        wind_gusts_10m=[8.0] * n,
        temperature_2m_max=[25.0] * 7,
        temperature_2m_min=[15.0] * 7,
        apparent_temperature_max=[24.0] * 7,
        apparent_temperature_min=[14.0] * 7,
        precipitation_sum=[1.0] * 7,
        precipitation_probability_max=[30.0] * 7,
        sunrise=["2026-06-03T04:00"] * 7,
        sunset=["2026-06-03T21:00"] * 7,
        wind_gusts_10m_max=[10.0] * 7,
        shortwave_radiation_sum=[18.0] * 7,
        timezone="Europe/Moscow",
        hourly_units={"temperature_2m": "°C"},
        daily_units={"temperature_2m_max": "°C"},
        n_hourly=n,
        n_daily=7,
    )


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


def _make_daily_metrics() -> list[DailyMetrics]:
    return [
        DailyMetrics(
            date=f"2026-06-0{i + 3}",
            t_mean_day=20.0, t_amp_day=5.0,
            rain_hours_50=2, wind_gust_max=10.0, solar_sum=18.0,
        )
        for i in range(7)
    ]


def _render_default(renderer: HtmlRenderer, **kwargs: object) -> str:
    """Отрендерить с дефолтными параметрами, вернуть HTML."""
    renderer.render(
        norm=kwargs.get("norm", _make_norm()),
        daily_metrics=kwargs.get("daily_metrics", _make_daily_metrics()),
        comfort=kwargs.get("comfort", _make_comfort()),
        walk_window=kwargs.get("walk_window", None),
        alerts=kwargs.get("alerts", []),
        location_name=kwargs.get("location_name", "Москва"),
        location_lat=kwargs.get("location_lat", 55.7558),
        location_lon=kwargs.get("location_lon", 37.6176),
        build_mode=kwargs.get("build_mode", "nominal"),
        last_updated=kwargs.get("last_updated", "2026-06-03T12:00:00+00:00"),
    )
    return renderer._output.read_text(encoding="utf-8")


# -------------------------------------------------------------
# Раздел 1. Базовые тесты создания файла
# -------------------------------------------------------------


@pytest.mark.unit()
def test_render_creates_index_html(tmp_renderer: HtmlRenderer) -> None:
    """render() создаёт index.html."""
    _render_default(tmp_renderer)
    assert tmp_renderer._output.exists()


@pytest.mark.unit()
def test_render_output_is_html(tmp_renderer: HtmlRenderer) -> None:
    """index.html начинается с DOCTYPE."""
    html = _render_default(tmp_renderer)
    assert html.strip().startswith("<!DOCTYPE html")


@pytest.mark.unit()
def test_render_not_empty(tmp_renderer: HtmlRenderer) -> None:
    """index.html не пустой (> 1000 символов)."""
    html = _render_default(tmp_renderer)
    assert len(html) > 1000


# -------------------------------------------------------------
# Раздел 2. Тесты содержимого — ключевые блоки
# -------------------------------------------------------------


@pytest.mark.unit()
def test_render_contains_location_name(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит название локации в шапке."""
    html = _render_default(tmp_renderer, location_name="Москва")
    assert "Москва" in html


@pytest.mark.unit()
def test_render_contains_coordinates(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит координаты локации."""
    html = _render_default(tmp_renderer, location_lat=55.7558, location_lon=37.6176)
    assert "55.7558" in html


@pytest.mark.unit()
def test_render_contains_section_charts(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит раздел ГРАФИКИ."""
    html = _render_default(tmp_renderer)
    assert "ГРАФИКИ" in html


@pytest.mark.unit()
def test_render_contains_section_hourly(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит раздел ПОЧАСОВОЙ ПРОГНОЗ."""
    html = _render_default(tmp_renderer)
    assert "ПОЧАСОВОЙ" in html


@pytest.mark.unit()
def test_render_contains_section_daily(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит раздел СУТОЧНЫЙ ПРОГНОЗ."""
    html = _render_default(tmp_renderer)
    assert "СУТОЧНЫЙ" in html


@pytest.mark.unit()
def test_render_contains_calc_section(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит РАСЧЁТНЫЙ ОТДЕЛ."""
    html = _render_default(tmp_renderer)
    assert "РАСЧЁТНЫЙ ОТДЕЛ" in html


@pytest.mark.unit()
def test_render_contains_comfort_index(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит значение ComfortIndex."""
    html = _render_default(tmp_renderer, comfort=_make_comfort())
    assert "75.0" in html
    assert "ИНДЕКС КОМФОРТНОСТИ" in html


@pytest.mark.unit()
def test_render_contains_export_links(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит ссылки на экспорт (ТЗ 5.1 п.4)."""
    html = _render_default(tmp_renderer)
    assert "latest.json" in html
    assert "hourly.csv" in html
    assert "daily.csv" in html


@pytest.mark.unit()
def test_render_contains_chart_canvases(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит canvas-элементы для Chart.js (ТЗ 6.1 п.4)."""
    html = _render_default(tmp_renderer)
    assert 'id="chart-temp"' in html
    assert 'id="chart-precip"' in html
    assert 'id="chart-wind"' in html


# -------------------------------------------------------------
# Раздел 3. Тест атрибуции (ТЗ 4.3, критерий 13.6)
# -------------------------------------------------------------


@pytest.mark.unit()
def test_render_contains_openmeteo_attribution(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит атрибуцию Open-Meteo (CC BY 4.0, ТЗ 4.3)."""
    html = _render_default(tmp_renderer)
    assert "open-meteo.com" in html.lower() or "Open-Meteo" in html
    assert "CC BY 4.0" in html


@pytest.mark.unit()
def test_render_contains_geonames_attribution(tmp_renderer: HtmlRenderer) -> None:
    """index.html содержит упоминание GeoNames (ТЗ 4.3)."""
    html = _render_default(tmp_renderer)
    assert "GeoNames" in html or "geonames.org" in html


# -------------------------------------------------------------
# Раздел 4. Тест degraded-режима (ТЗ 5.2)
# -------------------------------------------------------------


@pytest.mark.unit()
def test_render_degraded_shows_banner(tmp_renderer: HtmlRenderer) -> None:
    """При build_mode='degraded' отображается баннер ДАННЫЕ УСТАРЕЛИ."""
    html = _render_default(tmp_renderer, build_mode="degraded",
                           last_updated="2026-06-03T10:00:00+00:00")
    assert "ДАННЫЕ УСТАРЕЛИ" in html


@pytest.mark.unit()
def test_render_degraded_shows_last_updated(tmp_renderer: HtmlRenderer) -> None:
    """При degraded в баннере показывается дата последнего обновления."""
    html = _render_default(tmp_renderer, build_mode="degraded",
                           last_updated="2026-06-03T10:00:00+00:00")
    assert "2026-06-03" in html


@pytest.mark.unit()
def test_render_nominal_no_degraded_banner(tmp_renderer: HtmlRenderer) -> None:
    """При build_mode='nominal' баннер деградации отсутствует."""
    html = _render_default(tmp_renderer, build_mode="nominal")
    assert "ДАННЫЕ УСТАРЕЛИ" not in html


# -------------------------------------------------------------
# Раздел 5. Тест walk_window
# -------------------------------------------------------------


@pytest.mark.unit()
def test_render_walk_window_shown(tmp_renderer: HtmlRenderer) -> None:
    """При наличии WalkWindow отображается длительность."""
    base = datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc)
    ww = WalkWindow(
        start=base,
        end=base + timedelta(hours=5),
        duration_hours=5,
        reason="тест",
    )
    html = _render_default(tmp_renderer, walk_window=ww)
    assert "5" in html
    assert "ОКНО ПРОГУЛКИ" in html


@pytest.mark.unit()
def test_render_no_walk_window_shows_dash(tmp_renderer: HtmlRenderer) -> None:
    """При отсутствии WalkWindow показывается заглушка."""
    html = _render_default(tmp_renderer, walk_window=None)
    assert "ОКНО ПРОГУЛКИ" in html


# -------------------------------------------------------------
# Раздел 6. Тест alerts
# -------------------------------------------------------------


@pytest.mark.unit()
def test_render_alerts_shown(tmp_renderer: HtmlRenderer) -> None:
    """При наличии alerts отображается текст предупреждения."""
    alert = ThresholdAlert(
        metric="wind_gust_ms",
        value=20.0,
        limit=15.0,
        new_regime="alert",
        description="Порывы ветра 20.0 м/с",
    )
    html = _render_default(tmp_renderer, alerts=[alert])
    assert "Порывы ветра" in html


@pytest.mark.unit()
def test_render_no_alerts_shows_ok(tmp_renderer: HtmlRenderer) -> None:
    """При отсутствии alerts показывается сообщение о норме."""
    html = _render_default(tmp_renderer, alerts=[])
    assert "Нарушений порогов не обнаружено" in html


# -------------------------------------------------------------
# Раздел 7. Тест _build_context
# -------------------------------------------------------------


@pytest.mark.unit()
def test_build_context_current_temperature(tmp_renderer: HtmlRenderer) -> None:
    """_build_context корректно извлекает текущую температуру (первый час)."""
    norm = _make_norm()
    norm.temperature_2m[0] = 22.5
    ctx = tmp_renderer._build_context(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
        location_lat=55.76,
        location_lon=37.62,
        build_mode="nominal",
        last_updated="",
    )
    assert ctx["current"]["temperature"] == pytest.approx(22.5)


@pytest.mark.unit()
def test_build_context_hourly_48_labels(tmp_renderer: HtmlRenderer) -> None:
    """_build_context hourly_48.labels содержит ≤48 меток."""
    norm = _make_norm(n=24)
    ctx = tmp_renderer._build_context(
        norm=norm,
        daily_metrics=[],
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
        location_lat=0.0, location_lon=0.0,
        build_mode="nominal", last_updated="",
    )
    assert len(ctx["hourly_48"]["labels"]) == 24


@pytest.mark.unit()
def test_build_context_daily_table_length(tmp_renderer: HtmlRenderer) -> None:
    """_build_context daily_table содержит n_daily строк."""
    norm = _make_norm()
    ctx = tmp_renderer._build_context(
        norm=norm,
        daily_metrics=_make_daily_metrics(),
        comfort=_make_comfort(),
        walk_window=None,
        alerts=[],
        location_name="Москва",
        location_lat=0.0, location_lon=0.0,
        build_mode="nominal", last_updated="",
    )
    assert len(ctx["daily_table"]) == 7