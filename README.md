<!--
  ============================================================
  ОБОЗНАЧЕНИЕ : WD.DOC.RD-001
  НАИМЕНОВАНИЕ: Главный документ проекта
  ДОКУМЕНТ    : КС-СТО-1.10.ОД
  ПРОГРАММА   : Weather Dashboard
  ============================================================
-->

# Weather Dashboard (Open-Meteo API)

> Статический дашборд прогноза погоды с пайплайном «данные → расчёт → визуализация → публикация».  
> Разработан по стандарту КС-СТО на основе шаблона RST Bootstrap.

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

---

## 📋 Назначение

Дашборд генерирует статический HTML-отчёт о прогнозе погоды по данным
[Open-Meteo](https://open-meteo.com/) и публикует его на GitHub Pages.

**Особенности:**
- Автоматическое обновление по расписанию (GitHub Actions)
- Расчёт 7+ метрик: ComfortIndex, «окно прогулки», пороговые предупреждения
- Degraded-режим: при недоступности API показывается последний валидный отчёт
- Экспорт данных в JSON и CSV
- «Советская» визуальная эстетика: формуляр, штампы, ведомость

---

## ⚡ Быстрый старт

### Требования

- Python ≥ 3.11
- `pip install -e ".[dev]"`

### Запуск локально

```bash
git clone <repo-url> "Weather Dashboard (Open-Meteo API)"
cd "Weather Dashboard (Open-Meteo API)"
pip install -e ".[dev]"

RST_ENV=dev RST_LOG_LEVEL=INFO RST_LOG_FORMAT=text \
  python -m weather_dashboard
```

### Запуск тестов

```bash
pytest tests/unit/ -v
```

### Полный цикл CI локально

```bash
ruff format .
ruff check .
pytest tests/unit/ -v
python -m weather_dashboard
```

---

## 🏗️ Архитектура

```
Генератор (Python)          Витрина (docs/)
─────────────────           ───────────────
boot()                      index.html
  → ForecastClient          assets/style.css
  → GeocodingClient         assets/app.js
  → Validator               data/latest.json
  → MetricsCalculator       data/metrics.json
  → HtmlRenderer            data/hourly.csv
  → FileWriter              data/daily.csv
                            meta/build.json
```

Пайплайн состояний:
`init → fetched → validated → computed → rendered → published`

---

## 📂 Структура репозитория

```
Weather Dashboard (Open-Meteo API)/
├── docs/                    # GitHub Pages (статика)
│   ├── index.html
│   ├── assets/
│   ├── data/                # Генерируемые JSON/CSV
│   └── meta/build.json
├── src/weather_dashboard/
│   ├── bootstrap/           # Переносимый RST-слой
│   ├── meteo/               # Клиенты Open-Meteo API
│   ├── calc/                # Расчёты метрик
│   └── render/              # Генератор HTML
├── tests/unit/
├── .github/workflows/
└── pyproject.toml
```

---

## 📊 Данные и атрибуция

**Прогноз погоды:** [Open-Meteo](https://open-meteo.com/)  
Лицензия: **CC BY 4.0** — при использовании данных обязательна атрибуция.

**Геокодирование:** Open-Meteo Geocoding API  
Данные о местоположении основаны на [GeoNames](https://www.geonames.org/).

---

## 📚 Документация

| Раздел | Описание |
|:-------|:---------|
| [docs/reference/](docs/reference/) | Переменные API, конфиг, формулы |
| [docs/how-to/](docs/how-to/) | Как добавить порог, сменить город |
| [docs/concepts/](docs/concepts/) | Пайплайн, degraded-режим |

---

## 📝 Лицензия

MIT © 2026 — см. [LICENSE](LICENSE)