"""Оркестратор пайплайна генерации статики.

Пайплайн для каждой локации:
  elevation → forecast → air_quality → aggregations → indices → Jinja2 → docs/

При ошибке шага: WARNING + fallback на last_known_{location}.json.
Не падает полностью — страница деплоится даже при частичной недоступности API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from weather_dashboard.api.client import WeatherClient
from weather_dashboard.api.models import (
    AirQualityResponse,
    ForecastResponse,
    WeatherClientError,
)
from weather_dashboard.config import AppConfig
from weather_dashboard.config import config as default_config
from weather_dashboard.processing import aggregations, indices

logger = logging.getLogger(__name__)

# Путь к директории шаблонов (относительно этого файла)
_TEMPLATES_DIR = Path(__file__).parent / "templates"

# WMO weather code → описание на русском
_WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Ясно",
    1: "Преимущественно ясно",
    2: "Переменная облачность",
    3: "Пасмурно",
    45: "Туман",
    48: "Изморозь",
    51: "Лёгкая морось",
    53: "Умеренная морось",
    55: "Сильная морось",
    61: "Слабый дождь",
    63: "Умеренный дождь",
    65: "Сильный дождь",
    71: "Слабый снег",
    73: "Умеренный снег",
    75: "Сильный снег",
    77: "Снежная крупа",
    80: "Слабые ливни",
    81: "Умеренные ливни",
    82: "Сильные ливни",
    85: "Слабый снегопад",
    86: "Сильный снегопад",
    95: "Гроза",
    96: "Гроза с градом",
    99: "Сильная гроза с градом",
}

# WMO weather code → inline SVG (упрощённые иконки)
_WMO_SVG: dict[str, str] = {
    "clear": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<circle cx="12" cy="12" r="5"/>'
        '<line x1="12" y1="1" x2="12" y2="3"/>'
        '<line x1="12" y1="21" x2="12" y2="23"/>'
        '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>'
        '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>'
        '<line x1="1" y1="12" x2="3" y2="12"/>'
        '<line x1="21" y1="12" x2="23" y2="12"/>'
        '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>'
        '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>'
        "</svg>"
    ),
    "cloudy": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>'
        "</svg>"
    ),
    "rain": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<line x1="16" y1="13" x2="16" y2="21"/>'
        '<line x1="8" y1="13" x2="8" y2="21"/>'
        '<line x1="12" y1="15" x2="12" y2="23"/>'
        '<path d="M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25"/>'
        "</svg>"
    ),
    "snow": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<path d="M20 17.58A5 5 0 0 0 18 8h-1.26A8 8 0 1 0 4 16.25"/>'
        '<line x1="8" y1="16" x2="8" y2="21"/>'
        '<line x1="8" y1="21" x2="6" y2="19"/>'
        '<line x1="8" y1="21" x2="10" y2="19"/>'
        '<line x1="12" y1="18" x2="12" y2="23"/>'
        '<line x1="12" y1="23" x2="10" y2="21"/>'
        '<line x1="12" y1="23" x2="14" y2="21"/>'
        '<line x1="16" y1="16" x2="16" y2="21"/>'
        '<line x1="16" y1="21" x2="14" y2="19"/>'
        '<line x1="16" y1="21" x2="18" y2="19"/>'
        "</svg>"
    ),
    "storm": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<path d="M19 16.9A5 5 0 0 0 18 7h-1.26a8 8 0 1 0-11.62 9"/>'
        '<polyline points="13 11 9 17 15 17 11 23"/>'
        "</svg>"
    ),
    "fog": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
        '<line x1="3" y1="15" x2="21" y2="15"/>'
        '<line x1="3" y1="19" x2="21" y2="19"/>'
        '<path d="M10 3 Q12 1 14 3 Q16 5 18 3"/>'
        '<path d="M5 7 Q8 5 11 7 Q14 9 17 7 Q19 5 21 7"/>'
        "</svg>"
    ),
}


def _wmo_svg_key(code: int) -> str:
    """Определяет ключ SVG-иконки по WMO-коду."""
    if code == 0:
        return "clear"
    if code in (1, 2, 3, 45, 48):
        return "cloudy" if code in (2, 3) else ("fog" if code in (45, 48) else "clear")
    if code in range(51, 68) or code in range(80, 83):
        return "rain"
    if code in range(71, 78) or code in (85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "cloudy"


# ---------------------------------------------------------------------------
# Вспомогательные функции сборки контекста
# ---------------------------------------------------------------------------
def _build_location_context(
    location_cfg: dict[str, Any],
    elevation: float,
    forecast: ForecastResponse,
    air_q: AirQualityResponse,
) -> dict[str, Any]:
    """Собирает словарь контекста для одной локации.

    Args:
        location_cfg: Словарь локации из config.SNAPSHOT_LOCATIONS.
        elevation: Высота над уровнем моря, м.
        forecast: Ответ Forecast API.
        air_q: Ответ Air Quality API.

    Returns:
        JSON-сериализуемый словарь для Jinja2.
    """
    cur = forecast.current
    hourly = forecast.hourly
    daily = forecast.daily
    meta = forecast.metadata

    # ── Агрегаты ────────────────────────────────────────────────────────
    daily_aggs = aggregations.compute_all(hourly)

    # ── Индексы для текущего момента ────────────────────────────────────
    t = cur.temperature_2m or 0.0
    rh = cur.relative_humidity_2m or 0.0
    v = cur.wind_speed_10m or 0.0
    precip = cur.precipitation or 0.0

    # Точка росы из hourly[0] если есть
    td = (hourly.dew_point_2m[0] if hourly.dew_point_2m else None) or (t - 2.0)
    uv_now = (hourly.uv_index[0] if hourly.uv_index else None) or 0.0
    gusts = (hourly.wind_gusts_10m[0] if hourly.wind_gusts_10m else None) or 0.0

    # Индексы
    hi = indices.heat_index(t, rh)
    wc = indices.wind_chill(t, v)
    hx = indices.humidex(t, td) if td <= t else t
    dp = indices.dew_point(t, rh) if rh > 0 else t
    uv_risk = indices.uv_risk_level(uv_now)
    comfort = indices.comfort_score(t, rh, v, uv_now, precip)
    frost = indices.frost_risk(
        min((x for x in hourly.temperature_2m if x is not None), default=0.0)
    )
    wind_alert = indices.high_wind_alert(v, gusts)

    # Тренд температур
    t_means = [agg.temp_mean for agg in daily_aggs if agg.temp_mean is not None]
    trend: dict[str, Any] = {}
    if len(t_means) >= 2:
        trend = dict(indices.weather_trend(t_means))

    # AQI
    aqi_hourly = air_q.hourly.get("european_aqi", [])
    current_aqi = next((x for x in aqi_hourly if x is not None), None)
    aqi_cat = indices.aqi_category_eu(current_aqi) if current_aqi is not None else "—"

    # Тип осадков текущего часа
    precip_intensity = indices.precipitation_intensity(precip)

    # WMO код
    wmo_code = cur.weather_code or 0
    wmo_desc = _WMO_DESCRIPTIONS.get(wmo_code, "Неизвестно")
    wmo_svg = _WMO_SVG.get(_wmo_svg_key(wmo_code), _WMO_SVG["cloudy"])

    # Суточные карточки для 7-дневного прогноза
    daily_cards = []
    for i, date in enumerate(daily.time):
        card: dict[str, Any] = {
            "date": date,
            "t_max": daily.temperature_2m_max[i],
            "t_min": daily.temperature_2m_min[i],
            "precip_sum": daily.precipitation_sum[i],
            "wind_max": daily.wind_speed_10m_max[i],
            "uv_max": daily.uv_index_max[i],
            "sunrise": daily.sunrise[i] if i < len(daily.sunrise) else "",
            "sunset": daily.sunset[i] if i < len(daily.sunset) else "",
        }
        # UV риск для карточки
        uv_val = card["uv_max"] or 0.0
        card["uv_risk"] = indices.uv_risk_level(float(uv_val))
        # Доп. агрегаты если совпадает дата
        matching = [a for a in daily_aggs if a.date == date]
        if matching:
            agg = matching[0]
            card["precip_type"] = agg.precipitation_type
            card["sunshine_hours"] = agg.sunshine_hours
            card["wind_dir"] = agg.dominant_wind_direction
        daily_cards.append(card)

    return {
        # Мета
        "name": location_cfg["name"],
        "timezone": location_cfg["timezone"],
        "latitude": meta.latitude,
        "longitude": meta.longitude,
        "elevation": elevation,
        # Текущие условия
        "current": {
            "time": cur.time,
            "temperature": cur.temperature_2m,
            "apparent_temperature": cur.apparent_temperature,
            "wind_speed": cur.wind_speed_10m,
            "humidity": cur.relative_humidity_2m,
            "precipitation": precip,
            "weather_code": wmo_code,
            "weather_description": wmo_desc,
            "weather_svg": wmo_svg,
        },
        # Индексы
        "indices": {
            "heat_index": round(hi, 1),
            "wind_chill": round(wc, 1),
            "humidex": round(hx, 1),
            "dew_point": round(dp, 1),
            "uv_risk": uv_risk,
            "aqi": current_aqi,
            "aqi_category": aqi_cat,
            "precip_intensity": precip_intensity,
        },
        # Комфорт
        "comfort": {
            "score": round(comfort["score"], 1),
            "temp_sub": round(comfort["temp_sub"], 1),
            "humidity_sub": round(comfort["humidity_sub"], 1),
            "wind_sub": round(comfort["wind_sub"], 1),
            "uv_sub": round(comfort["uv_sub"], 1),
            "precip_sub": round(comfort["precip_sub"], 1),
        },
        # Алерты
        "alerts": {
            "frost_risk": frost,
            "high_wind": wind_alert,
        },
        # Тренд
        "trend": trend,
        # Прогноз
        "daily_cards": daily_cards,
        "hourly": forecast.hourly.to_dict(),
        "daily": forecast.daily.to_dict(),
        # Качество воздуха
        "air_quality": {
            "current_aqi": current_aqi,
            "aqi_category": aqi_cat,
            "hourly": {
                k: v
                for k, v in air_q.hourly.items()
                if k
                in (
                    "time",
                    "pm10",
                    "pm2_5",
                    "carbon_monoxide",
                    "nitrogen_dioxide",
                    "ozone",
                    "european_aqi",
                )
            },
            "units": air_q.units,
        },
        # Агрегаты
        "daily_aggregates": [
            {
                "date": a.date,
                "temp_min": a.temp_min,
                "temp_max": a.temp_max,
                "temp_mean": a.temp_mean,
                "total_precipitation": a.total_precipitation,
                "dominant_wind_direction": a.dominant_wind_direction,
                "max_uv_index": a.max_uv_index,
                "sunshine_hours": a.sunshine_hours,
                "precipitation_type": a.precipitation_type,
            }
            for a in daily_aggs
        ],
    }


async def _fetch_location(
    client: WeatherClient,
    location_cfg: dict[str, Any],
    cfg: AppConfig,
) -> dict[str, Any] | None:
    """Выполняет все API-запросы для одной локации.

    При ошибке любого шага: логирует WARNING, пробует fallback-кеш.
    Возвращает None только если и API, и fallback недоступны.

    Args:
        client: Инициализированный WeatherClient.
        location_cfg: Конфигурация локации.
        cfg: Конфигурация приложения.

    Returns:
        Словарь контекста или None.
    """
    name: str = str(location_cfg["name"])
    lat = float(str(location_cfg["latitude"]))
    lon = float(str(location_cfg["longitude"]))
    tz: str = str(location_cfg["timezone"])

    fallback_path = cfg.CACHE_DIR / f"last_known_{_slug(name)}.json"

    try:
        logger.info("Запрос данных для локации: %s", name)

        elevation = await client.get_elevation(lat, lon)
        logger.debug("Elevation %s: %.1f м", name, elevation)

        forecast = await client.get_forecast(
            lat,
            lon,
            timezone=tz,
            forecast_days=cfg.FORECAST_DAYS,
        )
        logger.debug("Forecast %s: OK", name)

        air_q = await client.get_air_quality(lat, lon)
        logger.debug("Air quality %s: OK", name)

        context = _build_location_context(location_cfg, elevation, forecast, air_q)

        # Сохраняем успешный результат как fallback
        _save_fallback(fallback_path, context)
        return context

    except WeatherClientError as exc:
        logger.warning(
            "Сетевая ошибка для локации %s: %s. Пробуем fallback-кеш.", name, exc
        )
    except Exception as exc:
        logger.warning(
            "Неожиданная ошибка для локации %s: %s. Пробуем fallback-кеш.", name, exc
        )

    # Fallback: последний успешный кеш
    return _load_fallback(fallback_path, name)


def _slug(name: str) -> str:
    """Превращает название города в безопасное имя файла."""
    return re.sub(r"[^\w]", "_", name.lower())


def _save_fallback(path: Path, context: dict[str, Any]) -> None:
    """Сохраняет контекст как fallback-кеш."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning("Не удалось сохранить fallback-кеш %s: %s", path, exc)


def _load_fallback(path: Path, name: str) -> dict[str, Any] | None:
    """Загружает fallback-кеш если он существует."""
    if not path.exists():
        logger.error("Fallback-кеш для %s не найден: %s", name, path)
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Использован fallback-кеш для %s", name)
        return dict(data)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Ошибка чтения fallback-кеша %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Jinja2 Environment
# ---------------------------------------------------------------------------
def _make_jinja_env() -> Environment:
    """Создаёт и настраивает Jinja2 Environment.

    Returns:
        Environment с FileSystemLoader из templates/.
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    # Фильтры
    def ru_number(value: float | None, decimals: int = 1) -> str:
        """Форматирует число в ru-RU стиле (JS делает то же через Intl)."""
        if value is None:
            return "—"
        formatted = f"{value:.{decimals}f}"
        # Заменяем десятичную точку на запятую для ru-RU
        return formatted.replace(".", ",")

    def wind_direction_ru(degrees: float | None) -> str:
        """Конвертирует градусы в русское обозначение стороны света."""
        if degrees is None:
            return "—"
        dirs = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
        idx = round(degrees / 45.0) % 8
        return dirs[idx]

    def comfort_color(score: float) -> str:
        """Возвращает CSS-класс цвета по значению Comfort Score."""
        if score <= 40:
            return "comfort--red"
        if score <= 70:
            return "comfort--yellow"
        return "comfort--green"

    def wmo_description(code: int | None) -> str:
        """Возвращает русское описание WMO-кода."""
        if code is None:
            return "Неизвестно"
        return _WMO_DESCRIPTIONS.get(int(code), "Неизвестно")

    env.filters["ru_number"] = ru_number
    env.filters["wind_direction_ru"] = wind_direction_ru
    env.filters["comfort_color"] = comfort_color
    env.filters["wmo_description"] = wmo_description

    return env


# ---------------------------------------------------------------------------
# Главная функция генератора
# ---------------------------------------------------------------------------
async def generate(cfg: AppConfig = default_config) -> bool:
    """Оркестрирует полный пайплайн генерации статики.

    Для каждой локации из cfg.SNAPSHOT_LOCATIONS:
      1. Запрашивает elevation, forecast, air_quality
      2. Вычисляет агрегаты и индексы
      3. Рендерит index.html и about.html через Jinja2
      4. Записывает data.js с JSON-снимком

    Не бросает исключений наружу — все ошибки логируются.
    Деплой выполняется даже при частичной недоступности API.

    Args:
        cfg: Конфигурация приложения.
    """
    logging.basicConfig(
        level=getattr(logging, cfg.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info(
        "Начало генерации snapshot. Локации: %s",
        [loc["name"] for loc in cfg.SNAPSHOT_LOCATIONS],
    )

    generated_at = datetime.now(UTC).isoformat()

    # ── Сбор данных ──────────────────────────────────────────────────────
    location_contexts: list[dict[str, Any]] = []

    async with WeatherClient(cfg) as client:
        tasks = [_fetch_location(client, loc, cfg) for loc in cfg.SNAPSHOT_LOCATIONS]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    for loc_cfg, result in zip(cfg.SNAPSHOT_LOCATIONS, results, strict=False):
        if result is not None:
            location_contexts.append(result)
            logger.info("Локация %s: данные готовы", loc_cfg["name"])
        else:
            logger.error(
                "Локация %s: нет данных (API и fallback недоступны)", loc_cfg["name"]
            )

    if not location_contexts:
        logger.error("Нет данных ни для одной локации. Генерация прервана.")
        return False

    # ── Рендеринг ────────────────────────────────────────────────────────
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assets_dir = cfg.OUTPUT_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    env = _make_jinja_env()

    # Общий контекст для всех шаблонов
    from weather_dashboard import __version__

    base_ctx: dict[str, Any] = {
        "locations": location_contexts,
        "default_location": location_contexts[0],
        "generated_at": generated_at,
        "version": __version__,
        "repo_url": ("https://github.com/Loliconus/Weather-Dashboard-Open-Meteo-API"),
        "author": "Loliconus",
    }

    # index.html
    _render_template(env, "index.html.j2", cfg.OUTPUT_DIR / "index.html", base_ctx)

    # about.html
    _render_template(env, "about.html.j2", cfg.OUTPUT_DIR / "about.html", base_ctx)

    # data.js — snapshot для Snapshot mode
    _write_data_js(assets_dir / "data.js", location_contexts, generated_at)

    logger.info(
        "Генерация завершена. Файлы: %s",
        [str(p) for p in cfg.OUTPUT_DIR.rglob("*.html")],
    )
    return True


def _render_template(
    env: Environment,
    template_name: str,
    output_path: Path,
    context: dict[str, Any],
) -> None:
    """Рендерит один Jinja2-шаблон в файл.

    Args:
        env: Jinja2 Environment.
        template_name: Имя шаблона относительно templates/.
        output_path: Путь для записи результата.
        context: Словарь контекста.
    """
    try:
        tmpl = env.get_template(template_name)
        html = tmpl.render(**context)
        output_path.write_text(html, encoding="utf-8")
        logger.info("Рендеринг OK: %s", output_path)
    except Exception as exc:
        logger.error("Ошибка рендеринга %s: %s", template_name, exc)


def _write_data_js(
    path: Path,
    contexts: list[dict[str, Any]],
    generated_at: str,
) -> None:
    """Записывает data.js с JSON-снимком данных для Snapshot mode.

    Формат: const WEATHER_SNAPSHOT = {...};

    Args:
        path: Путь к файлу data.js.
        contexts: Список контекстов локаций.
        generated_at: ISO 8601 timestamp генерации.
    """
    snapshot = {
        "generated_at": generated_at,
        "locations": contexts,
    }
    try:
        js_content = (
            "// Сгенерировано автоматически — не редактировать вручную.\n"
            f"// Обновлено: {generated_at}\n"
            "const WEATHER_SNAPSHOT = "
            + json.dumps(snapshot, ensure_ascii=False, indent=2)
            + ";\n"
        )
        path.write_text(js_content, encoding="utf-8")
        logger.info("data.js записан: %s", path)
    except OSError as exc:
        logger.error("Ошибка записи data.js: %s", exc)


# ---------------------------------------------------------------------------
# Точка входа CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Синхронная точка входа для python -m weather_dashboard.rendering.generator."""
    success = asyncio.run(generate())
    if not success:
        main.exit(1)


if __name__ == "__main__":
    main()
