<!--
  ============================================================
  ОБОЗНАЧЕНИЕ : WD.DOC.HT-001
  НАИМЕНОВАНИЕ: Как добавить пороговое предупреждение
  ДОКУМЕНТ    : КС-СТО-1.10.ОД
  ПРОГРАММА   : Weather Dashboard
  ============================================================
-->

# Как добавить пороговое предупреждение

Diátaxis-тип: **How-to** — решение конкретной задачи.

**Цель:** добавить новый порог, например «туман» (видимость < 1000 м).

---

## Шаг 1 — Добавить поле в ThresholdConfig

Файл: `src/weather_dashboard/config.py`

```python
@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    # ... существующие поля ...
    visibility_min_m: float = 1000.0  # ← новый порог тумана

## Шаг 2 — Добавить переменную в HOURLY_VARIABLES (если нужна)

HOURLY_VARIABLES: tuple[str, ...] = (
    # ... существующие ...
    "visibility",   # ← добавить если переменная есть в Open-Meteo
)

## Шаг 3 — Добавить поле в NormalizedForecast

Файл: src/weather_dashboard/calc/normalizer.py
@dataclass
class NormalizedForecast:
    # ... существующие поля ...
    visibility: list[float] = field(default_factory=list)
И добавить извлечение в normalize_forecast():
norm.visibility = _to_floats(h.get("visibility", []))