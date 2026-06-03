# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/ledger.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.06
# НАИМЕНОВАНИЕ: LedgerLogger — семантический API записи фактов
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : logging, uuid, datetime, dataclasses,
#               bootstrap.schema, bootstrap.context
# =============================================================
# Назначение:
#   4 метода поверх stdlib logging:
#     fact()           — наблюдение события
#     transition()     — переход состояния
#     contradiction()  — противоречие двух утверждений
#     threshold()      — пороговое событие метрики
#   Каждый метод возвращает fact_id для построения цепочек.
#   Проверка: pytest tests/unit/test_ledger_schema.py
# =============================================================

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from weather_dashboard.bootstrap.schema import (
    ContradictionRecord,
    FactRecord,
    ThresholdRecord,
    TransitionRecord,
)

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_LEDGER_LOGGER_NAME: str = "ledger"

# Поля BaseRecord, которые НЕ передаются в extra
# (они уже есть в стандартных полях LogRecord или не нужны)
_SKIP_IN_EXTRA: frozenset[str] = frozenset({"level", "message"})


# -------------------------------------------------------------
# Раздел 1. LedgerLogger
# -------------------------------------------------------------


class LedgerLogger:
    """Семантический регистратор фактов поверх stdlib logging.

    Все записи уходят через стандартный logging.Logger с именем
    'ledger'. Поля схемы передаются через LogRecord.extra и
    доступны форматтерам (JsonFormatter включает их в JSON).

    Создание через boot() — рекомендованный способ.
    Прямое создание используется в тестах.
    """

    def __init__(
        self,
        corr_id: str,
        name: str = _LEDGER_LOGGER_NAME,
    ) -> None:
        self._corr_id = corr_id
        self._logger = logging.getLogger(name)

    # ----------------------------------------------------------
    # Раздел 2. Вспомогательные методы
    # ----------------------------------------------------------

    @staticmethod
    def _new_fact_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _emit(
        self,
        record_obj: (
            FactRecord
            | TransitionRecord
            | ContradictionRecord
            | ThresholdRecord
        ),
        level: str,
    ) -> None:
        """Отправить запись через stdlib logger с extra-полями.

        Используем dataclasses.fields() вместо __dataclass_fields__
        для совместимости с Python 3.14 (slots-иерархии).
        """
        log_level = getattr(logging, level, logging.INFO)

        extra: dict[str, Any] = {}
        for f in dataclasses.fields(record_obj):  # type: ignore[arg-type]
            if f.name not in _SKIP_IN_EXTRA:
                extra[f.name] = getattr(record_obj, f.name)

        self._logger.log(log_level, record_obj.message, extra=extra)

    # ----------------------------------------------------------
    # Раздел 3. Публичный API
    # ----------------------------------------------------------

    def fact(
        self,
        subject: str,
        action: str,
        cause: str | None = None,
        level: str = "INFO",
        **ctx: Any,
    ) -> str:
        """Записать факт — наблюдение произошедшего события.

        Args:
            subject: Кто/что наблюдается.
            action:  Что произошло.
            cause:   fact_id причинного события (опционально).
            level:   Уровень важности.
            **ctx:   Произвольный контекст → extra["ctx"].

        Returns:
            fact_id этой записи (UUID4 строка).
        """
        fact_id = self._new_fact_id()
        record = FactRecord(
            kind="fact",
            subject=subject,
            corr_id=self._corr_id,
            fact_id=fact_id,
            cause_id=cause,
            ts=self._now_iso(),
            level=level,
            message=f"[fact] {subject}: {action}",
            ctx=dict(ctx),
            action=action,
        )
        self._emit(record, level)
        return fact_id

    def transition(
        self,
        subject: str,
        from_state: str,
        to_state: str,
        cause: str,
        level: str = "INFO",
        **ctx: Any,
    ) -> str:
        """Записать переход состояния субъекта.

        Args:
            subject:    Субъект, меняющий состояние.
            from_state: Исходное состояние.
            to_state:   Целевое состояние.
            cause:      fact_id или текст причины (ОБЯЗАТЕЛЕН).
            level:      Уровень важности.
            **ctx:      Произвольный контекст.

        Returns:
            fact_id этой записи.
        """
        fact_id = self._new_fact_id()
        record = TransitionRecord(
            kind="transition",
            subject=subject,
            corr_id=self._corr_id,
            fact_id=fact_id,
            cause_id=cause,
            ts=self._now_iso(),
            level=level,
            message=f"[transition] {subject}: {from_state} → {to_state}",
            ctx=dict(ctx),
            from_state=from_state,
            to_state=to_state,
            cause=cause,
        )
        self._emit(record, level)
        return fact_id

    def contradiction(
        self,
        subject: str,
        thesis: str,
        antithesis: str,
        invariant: str,
        resolution: str | None = None,
        level: str = "WARNING",
        **ctx: Any,
    ) -> str:
        """Записать противоречие между двумя утверждениями.

        Args:
            subject:    Область противоречия.
            thesis:     Утверждение A.
            antithesis: Утверждение B (противоречит A).
            invariant:  Инвариант, который нельзя нарушить.
            resolution: Принятое решение (None = не разрешено).
            level:      Уровень важности (по умолчанию WARNING).
            **ctx:      Произвольный контекст.

        Returns:
            fact_id этой записи.
        """
        fact_id = self._new_fact_id()
        record = ContradictionRecord(
            kind="contradiction",
            subject=subject,
            corr_id=self._corr_id,
            fact_id=fact_id,
            cause_id=None,
            ts=self._now_iso(),
            level=level,
            message=(
                f"[contradiction] {subject}: "
                f"{thesis[:60]!r} ↔ {antithesis[:60]!r}"
            ),
            ctx=dict(ctx),
            thesis=thesis,
            antithesis=antithesis,
            invariant=invariant,
            resolution=resolution,
        )
        self._emit(record, level)
        return fact_id

    def threshold(
        self,
        subject: str,
        metric: str,
        value: float,
        limit: float,
        new_regime: str,
        level: str = "WARNING",
        **ctx: Any,
    ) -> str:
        """Записать пороговое событие — метрика пересекла предел.

        Args:
            subject:    "metric:<name>" — объект наблюдения.
            metric:     Техническое имя метрики.
            value:      Текущее значение.
            limit:      Пороговое значение.
            new_regime: Новый режим после пересечения.
            level:      Уровень важности.
            **ctx:      Произвольный контекст.

        Returns:
            fact_id этой записи.
        """
        fact_id = self._new_fact_id()
        record = ThresholdRecord(
            kind="threshold",
            subject=subject,
            corr_id=self._corr_id,
            fact_id=fact_id,
            cause_id=None,
            ts=self._now_iso(),
            level=level,
            message=(
                f"[threshold] {metric}={value} "
                f"exceeds limit={limit} → regime={new_regime}"
            ),
            ctx=dict(ctx),
            metric=metric,
            value=value,
            limit=limit,
            new_regime=new_regime,
        )
        self._emit(record, level)
        return fact_id