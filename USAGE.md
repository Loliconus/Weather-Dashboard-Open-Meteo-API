<!--
  ============================================================
  ПУТЬ        : USAGE.md
  ОБОЗНАЧЕНИЕ : RST.DOC.US-001
  НАИМЕНОВАНИЕ: Руководство применения
  ДОКУМЕНТ    : КС-СТО-1.02.СР
  ПРОГРАММА   : RST Bootstrap
  ВВЕДЁН      : 2026-06-03
  ============================================================
-->

# USAGE — Руководство по применению

---

## Установка

Из PyPI:

    pip install rst-bootstrap

В режиме разработки (editable):

    pip install -e ".[dev,test]"

---

## Конфигурация (переменные среды)

| Переменная      | Допустимые значения             | Дефолт |
|:----------------|:--------------------------------|:-------|
| `RST_ENV`       | `dev` `staging` `prod`          | `dev`  |
| `RST_LOG_LEVEL` | `DEBUG` `INFO` `WARNING` `ERROR`| `INFO` |
| `RST_LOG_FORMAT`| `json` `text`                   | `json` |

При невалидном значении — `SystemExit(1)` с описанием ошибки.

---

## API

### `boot() → Runtime`

    from rst_bootstrap import boot

    rt = boot()
    # rt.settings  — Settings(env, log_level, log_format)
    # rt.meta      — ProductMeta(name, version, description, ...)
    # rt.ledger    — LedgerLogger
    # rt.corr_id   — str (UUID4)

### `LedgerLogger`

**fact** — наблюдение события:

    fact_id = rt.ledger.fact("service", "started", env="prod")

**transition** — изменение состояния:

    rt.ledger.transition("order", "pending", "shipped", cause=fact_id)

**contradiction** — зафиксировать противоречие:

    rt.ledger.contradiction(
        subject="config",
        thesis="json requested",
        antithesis="tty detected",
        invariant="json wins in CI",
        resolution="force json",
    )

**threshold** — метрика пересекла порог:

    rt.ledger.threshold(
        subject="metric:latency_ms",
        metric="latency_ms",
        value=6000.0,
        limit=5000.0,
        new_regime="degraded",
    )

---

## Переносимость bootstrap-слоя

Слой `src/<package_name>/bootstrap/` не содержит project-специфичных строк
в логике. Для переноса в другой проект:

1. Скопировать директорию `bootstrap/` в `src/<new_package_name>/`.
2. Обновить `pyproject.toml` (name, version, description).
3. Обновить `_DISTRIBUTION_NAME` в `bootstrap/meta.py`.

Проверить работоспособность:

    python -m <new_package_name>
    pytest tests/unit/