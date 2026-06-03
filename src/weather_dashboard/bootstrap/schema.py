# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/schema.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.04
# НАИМЕНОВАНИЕ: Dataclass-схемы четырёх типов ledger-записей
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : dataclasses, typing
# =============================================================
# Назначение:
#   Структуры данных для fact / transition / contradiction /
#   threshold записей. Используются только внутри ledger.py —
#   снаружи создавать экземпляры не нужно.
#   Поля схемы — верхний уровень LogRecord.extra (не в ctx).
#   Примечание: slots=True намеренно НЕ используется в иерархии
#   наследования — Python 3.10+ запрещает переопределять слоты
#   родителя в дочернем классе, что вызывает TypeError при импорте.
#   Проверка: pytest tests/unit/test_ledger_schema.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# -------------------------------------------------------------
# Раздел 0. Базовая схема (общие поля всех типов)
# -------------------------------------------------------------


@dataclass
class BaseRecord:
    """Общие поля для всех типов ledger-записей.

    Все 8 обязательных полей NFR-OBS-001.
    Поле ctx содержит произвольный контекст из **kwargs вызова.

    slots=True не используется: дочерние dataclass-классы
    с наследованием и дефолтными полями несовместимы со слотами
    родителя начиная с Python 3.10 (TypeError при импорте).
    """

    kind: str
    subject: str
    corr_id: str
    fact_id: str
    cause_id: str | None
    ts: str
    level: str
    message: str
    ctx: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать запись в словарь для JSON-лога."""
        result: dict[str, Any] = {
            "kind": self.kind,
            "subject": self.subject,
            "corr_id": self.corr_id,
            "fact_id": self.fact_id,
            "cause_id": self.cause_id,
            "ts": self.ts,
            "level": self.level,
            "message": self.message,
        }
        if self.ctx:
            result["ctx"] = self.ctx
        return result


# -------------------------------------------------------------
# Раздел 1. Конкретные схемы
# -------------------------------------------------------------


@dataclass
class FactRecord(BaseRecord):
    """Запись факта: наблюдение произошедшего события."""

    action: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["action"] = self.action
        return d


@dataclass
class TransitionRecord(BaseRecord):
    """Запись перехода состояния субъекта."""

    from_state: str = ""
    to_state: str = ""
    cause: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["from_state"] = self.from_state
        d["to_state"] = self.to_state
        d["cause"] = self.cause
        return d


@dataclass
class ContradictionRecord(BaseRecord):
    """Запись противоречия между двумя утверждениями."""

    thesis: str = ""
    antithesis: str = ""
    invariant: str = ""
    resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["thesis"] = self.thesis
        d["antithesis"] = self.antithesis
        d["invariant"] = self.invariant
        d["resolution"] = self.resolution
        return d


@dataclass
class ThresholdRecord(BaseRecord):
    """Запись порогового события: метрика пересекла лимит."""

    metric: str = ""
    value: float = 0.0
    limit: float = 0.0
    new_regime: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["metric"] = self.metric
        d["value"] = self.value
        d["limit"] = self.limit
        d["new_regime"] = self.new_regime
        return d