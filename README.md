# 🌤 Weather Dashboard — Open-Meteo API

[![Deploy Status](https://github.com/Loliconus/Weather-Dashboard-Open-Meteo-API/actions/workflows/deploy.yml/badge.svg)](https://github.com/Loliconus/Weather-Dashboard-Open-Meteo-API/actions/workflows/deploy.yml)
[![Quality Gates](https://github.com/Loliconus/Weather-Dashboard-Open-Meteo-API/actions/workflows/quality.yml/badge.svg)](https://github.com/Loliconus/Weather-Dashboard-Open-Meteo-API/actions/workflows/quality.yml)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Data CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Coverage ≥80%](https://img.shields.io/badge/coverage-≥80%25-brightgreen.svg)](#тестирование)

## 🔗 [Live Demo → Loliconus.github.io/Weather-Dashboard-Open-Meteo-API](https://Loliconus.github.io/Weather-Dashboard-Open-Meteo-API)

---

Портфолио-проект **Loliconus** — интерактивный дашборд погоды
на базе [Open-Meteo API](https://open-meteo.com/).
Демонстрирует полный стек: REST API интеграция, ETL-пайплайн,
визуализация данных, CI/CD production-grade.

> **Рынок:** РФ (ru-RU локаль, кириллица, московское время по умолчанию)

---

## ✨ Возможности

- 🔴 **Live mode** — живые данные прямо из Open-Meteo API (JS fetch)
- 📸 **Snapshot mode** — ежедневный CI-снимок (06:00 МСК), работает без сети
- 🔍 **Поиск города** с дебаунсом 300 мс, геолокация браузера
- 📅 **7-дневный прогноз** с графиком температур и анализом тренда
- ⏱ **Почасовой прогноз** с переключением дней без перезагрузки
- 🌫 **Качество воздуха** — PM2.5, PM10, CO, NO₂, O₃, European AQI
- 🧮 **11 метеоиндексов** — Heat Index, Wind Chill, Humidex и другие
- 🌡 **Comfort Score** — взвешенный индекс комфорта 0–100
- ❄️ **Алерты** — Frost Risk, High Wind Alert
- 🌙 **Dark mode** из коробки (`prefers-color-scheme`)
- ♿ **A11y** — ARIA-атрибуты, skip-to-content, `prefers-reduced-motion`
- 📱 **Адаптивный дизайн** — mobile, tablet, desktop

---

## 🖼 Скриншоты

> *Добавьте скриншоты после первого деплоя:*
> `docs/screenshots/hero.png`, `docs/screenshots/charts.png`,
> `docs/screenshots/indices.png`

---

## 🌐 Описание (English)

Weather Dashboard is a portfolio project showcasing REST API integration
with Open-Meteo, ETL data processing, interactive Chart.js visualizations,
and production-grade CI/CD. Built with Python 3.14 (snapshot generation)
and Vanilla JS ES2022 (browser runtime). Deployed to GitHub Pages via
GitHub Actions with OIDC, SHA-pinned actions, and supply chain security.

---

## 🛠 Технологический стек

| Инструмент | Версия | Назначение |
|-----------|--------|-----------|
| Python | 3.14 | Генерация снимков, расчёты |
| httpx | ≥ 0.28 | Async HTTP-клиент |
| Jinja2 | ≥ 3.1 | Шаблонизация HTML |
| tenacity | ≥ 9.0 | Retry + exponential backoff |
| Chart.js | 4.x | Интерактивные графики |
| Vanilla JS | ES2022 | Рантайм браузера |
| uv | latest | Менеджер пакетов Python |
| ruff | ≥ 0.9 | Линтер и форматтер |
| ty | ≥ 0.0.1a1 | Type checker |
| pytest + hypothesis | latest | Тесты |
| respx | ≥ 0.21 | Mock httpx |
| GitHub Actions | — | CI/CD |
| GitHub Pages | — | Хостинг |

---

## 🧮 Методы расчёта

| Индекс | Формула / Источник | Условие применения |
|--------|-------------------|--------------------|
| Heat Index | Rothfusz/NWS многочлен | T ≥ 27°C, RH ≥ 40% |
| Wind Chill | Environment Canada (2001) | T ≤ 10°C, V ≥ 1.3 м/с |
| Humidex | MSC (Masterson & Richardson, 1979) | — |
| Dew Point | Magnus (α=17.625, β=243.04°C) | RH > 0% |
| UV Risk | WHO UV Index Scale | — |
| EAQI Category | European Environment Agency | — |
| Precip Intensity | WMO No. 8 (CIMO Guide) | — |
| Weather Trend | МНК без NumPy, R² | ≥ 2 значений |
| Comfort Score | Взвешенные субиндексы | 5 параметров |
| Frost Risk | T_min < 0°C | — |
| High Wind Alert | Шкала Бофорта ≥ 14 м/с | — |

---

## 📁 Структура проекта

```
Weather-Dashboard-Open-Meteo-API/
├── src/weather_dashboard/
│   ├── api/
│   │   ├── client.py        # Async httpx-клиент, retry, кеш
│   │   ├── endpoints.py     # StrEnum URL/переменных (SSOT)
│   │   └── models.py        # frozen dataclasses, RFC 9457
│   ├── processing/
│   │   ├── aggregations.py  # hourly → daily агрегаты
│   │   ├── indices.py       # 11 метеоиндексов (pure, без NumPy)
│   │   └── validators.py    # ValueError/warnings на некорректный вход
│   ├── rendering/
│   │   ├── generator.py     # Оркестратор пайплайна
│   │   └── templates/       # Jinja2 шаблоны
│   └── config.py            # frozen dataclass + os.environ
├── tests/
│   ├── unit/                # test_validators, test_aggregations, test_indices
│   ├── integration/         # test_client (respx mock)
│   └── conftest.py
├── docs/                    # GitHub Pages output (CI-генерация)
│   ├── index.html
│   ├── about.html
│   └── assets/
│       ├── data.js          # Snapshot JSON
│       ├── dashboard.js     # Live mode + Chart.js
│       └── style.css
├── .github/
│   ├── workflows/
│   │   ├── deploy.yml       # Cron 06:00 MSK + push→deploy
│   │   └── quality.yml      # PR gates
│   └── ISSUE_TEMPLATE/
├── pyproject.toml           # SSOT (PEP 518/621)
└── ...
```

---

## 🚀 Локальная разработка

### Требования

- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Установка

```bash
git clone https://github.com/Loliconus/Weather-Dashboard-Open-Meteo-API.git
cd Weather-Dashboard-Open-Meteo-API

# Установить зависимости из lockfile
uv sync --frozen --all-extras

# Установить pre-commit хуки
uv run pre-commit install
```

### Генерация snapshot

```bash
uv run python -m weather_dashboard.rendering.generator
# → Генерирует docs/index.html, docs/about.html, docs/assets/data.js
```

### Просмотр локально

```bash
# Любой статический сервер, например:
cd docs && python -m http.server 8080
# Открыть http://localhost:8080
```

---

## 🧪 Тестирование

```bash
# Все тесты + coverage
uv run pytest --cov=src --cov-report=term-missing -v

# Только юнит-тесты (быстро, < 10 сек)
uv run pytest tests/unit/ -q

# Только интеграционные
uv run pytest tests/integration/ -v

# С HTML-отчётом coverage
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

**Требования:** coverage ≥ 80% (`processing/`), ≥ 60% (`api/`)

---

## 🔄 CI/CD

```
push → main ──┐
              ├──▶ quality gates (ruff + ty + pytest ≥80%)
cron 06:00 MSK┘         │
                         ▼
              generate snapshot (Python)
                         │
                         ▼
              upload docs/ artifact
                         │
                         ▼
              deploy → GitHub Pages (OIDC)
```

- **SHA-пиннинг** всех `uses:` (SLSA / OWASP A03:2025)
- **OIDC** — без секретов в репозитории
- **`uv sync --frozen`** — детерминированная сборка из `uv.lock`

---

## 📊 Данные и Attribution

| Источник | Использование | Лицензия |
|---------|--------------|---------|
| [Open-Meteo](https://open-meteo.com/) | Прогноз, геокодирование, высоты | CC BY 4.0 |
| [GeoNames](https://www.geonames.org/) | Данные геокодирования | CC BY 4.0 |
| [Copernicus DEM GLO-90](https://spacedata.copernicus.eu/) | Высоты рельефа | [DOI: 10.5270/ESA-c5d3d65](https://doi.org/10.5270/ESA-c5d3d65) |
| [CAMS (Copernicus)](https://atmosphere.copernicus.eu/) | Качество воздуха | CC BY 4.0 |

**Данные погоды предоставляются Open-Meteo.com по лицензии CC BY 4.0.**

---

## 👤 Автор

**Loliconus**
— [GitHub](https://github.com/Loliconus)

---

## 📄 Лицензия

- **Код:** [MIT License](LICENSE)
- **Данные погоды:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) (Open-Meteo)