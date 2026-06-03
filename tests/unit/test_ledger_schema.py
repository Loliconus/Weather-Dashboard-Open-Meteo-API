# =============================================================
# ПУТЬ        : tests/unit/test_ledger_schema.py
# ОБОЗНАЧЕНИЕ : WD.TEST.02
# НАИМЕНОВАНИЕ: Тесты LedgerLogger — все 4 метода и схемы записей
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, logging, weather_dashboard.bootstrap.ledger
# =============================================================
# Назначение:
#   Покрывает FR-BOOT-005, NFR-OBS-001.
#   Проверяет: возврат fact_id, обязательные поля, специфичные
#   поля каждого типа, контекст ctx, цепочки причинности.
#   Проверка: pytest tests/unit/test_ledger_schema.py -v
# =============================================================

from __future__ import annotations

import logging
import uuid

import pytest

from tests.conftest import CapturingHandler, extract_extra
from weather_dashboard.bootstrap.ledger import LedgerLogger

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_REQUIRED_FIELDS = frozenset({
    "kind", "subject", "corr_id", "fact_id", "cause_id", "ts",
})

_TEST_CORR_ID = "test-corr-id-0000-0000-0000-000000000000"


def _make_ledger(handler: CapturingHandler) -> LedgerLogger:
    """Создать LedgerLogger с подключённым capturing handler."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    logging.getLogger("ledger").addHandler(handler)
    return ledger


# -------------------------------------------------------------
# Раздел 1. Тесты fact()
# -------------------------------------------------------------


@pytest.mark.unit()
def test_fact_returns_non_empty_fact_id(
    capturing_handler: CapturingHandler,
) -> None:
    """fact() возвращает непустую строку UUID4."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    fid = ledger.fact("svc", "started")
    assert fid
    uuid.UUID(fid)  # Проверяем валидность UUID


@pytest.mark.unit()
def test_fact_required_fields_present(
    capturing_handler: CapturingHandler,
) -> None:
    """fact() создаёт запись со всеми обязательными полями (NFR-OBS-001)."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.fact("svc", "started")

    record = capturing_handler.records[-1]
    extra = extract_extra(record)

    for field_name in _REQUIRED_FIELDS:
        assert field_name in extra, f"Обязательное поле отсутствует: {field_name}"


@pytest.mark.unit()
def test_fact_kind_is_fact(capturing_handler: CapturingHandler) -> None:
    """fact() создаёт запись с kind='fact'."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.fact("svc", "started")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["kind"] == "fact"


@pytest.mark.unit()
def test_fact_action_field(capturing_handler: CapturingHandler) -> None:
    """fact() сохраняет action в схеме записи."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.fact("pipeline", "fetch_complete")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["action"] == "fetch_complete"


@pytest.mark.unit()
def test_fact_cause_id_none_by_default(
    capturing_handler: CapturingHandler,
) -> None:
    """fact() без cause= устанавливает cause_id=None."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.fact("svc", "started")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["cause_id"] is None


@pytest.mark.unit()
def test_fact_cause_id_propagated(capturing_handler: CapturingHandler) -> None:
    """fact(cause=fid) сохраняет cause_id в записи."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    parent_id = ledger.fact("svc", "started")
    ledger.fact("svc", "child_event", cause=parent_id)

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["cause_id"] == parent_id


@pytest.mark.unit()
def test_fact_ctx_stored_correctly(capturing_handler: CapturingHandler) -> None:
    """Произвольный контекст (**kwargs) сохраняется в extra['ctx']."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.fact("api", "request", user_id="u-42", amount=100.0)

    extra = extract_extra(capturing_handler.records[-1])
    ctx = extra.get("ctx", {})
    assert ctx["user_id"] == "u-42"
    assert ctx["amount"] == 100.0


@pytest.mark.unit()
def test_fact_corr_id_matches(capturing_handler: CapturingHandler) -> None:
    """fact() сохраняет corr_id из конструктора LedgerLogger."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.fact("svc", "started")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["corr_id"] == _TEST_CORR_ID


# -------------------------------------------------------------
# Раздел 2. Тесты transition()
# -------------------------------------------------------------


@pytest.mark.unit()
def test_transition_returns_fact_id(
    capturing_handler: CapturingHandler,
) -> None:
    """transition() возвращает непустую строку UUID4."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    fid = ledger.transition("pipeline", "init", "fetching", cause="root")
    assert fid
    uuid.UUID(fid)


@pytest.mark.unit()
def test_transition_kind_is_transition(
    capturing_handler: CapturingHandler,
) -> None:
    """transition() создаёт запись с kind='transition'."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.transition("pipeline", "init", "fetching", cause="root")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["kind"] == "transition"


@pytest.mark.unit()
def test_transition_state_fields(capturing_handler: CapturingHandler) -> None:
    """transition() сохраняет from_state и to_state."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.transition("pipeline", "fetching", "validated", cause="root")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["from_state"] == "fetching"
    assert extra["to_state"] == "validated"


# -------------------------------------------------------------
# Раздел 3. Тесты contradiction()
# -------------------------------------------------------------


@pytest.mark.unit()
def test_contradiction_returns_fact_id(
    capturing_handler: CapturingHandler,
) -> None:
    """contradiction() возвращает непустую строку UUID4."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    fid = ledger.contradiction(
        subject="data",
        thesis="длина hourly=168",
        antithesis="длина hourly=100",
        invariant="массивы должны быть одинаковой длины",
    )
    assert fid
    uuid.UUID(fid)


@pytest.mark.unit()
def test_contradiction_kind(capturing_handler: CapturingHandler) -> None:
    """contradiction() создаёт запись с kind='contradiction'."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.contradiction("d", "A", "B", "I")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["kind"] == "contradiction"


@pytest.mark.unit()
def test_contradiction_fields_stored(
    capturing_handler: CapturingHandler,
) -> None:
    """contradiction() сохраняет thesis/antithesis/invariant/resolution."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.contradiction(
        subject="arrays",
        thesis="len=168",
        antithesis="len=100",
        invariant="всегда 168",
        resolution="взят предыдущий отчёт",
    )

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["thesis"] == "len=168"
    assert extra["antithesis"] == "len=100"
    assert extra["invariant"] == "всегда 168"
    assert extra["resolution"] == "взят предыдущий отчёт"


@pytest.mark.unit()
def test_contradiction_resolution_none(
    capturing_handler: CapturingHandler,
) -> None:
    """contradiction() с resolution=None сохраняет None."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.contradiction("d", "A", "B", "I", resolution=None)

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["resolution"] is None


# -------------------------------------------------------------
# Раздел 4. Тесты threshold()
# -------------------------------------------------------------


@pytest.mark.unit()
def test_threshold_returns_fact_id(
    capturing_handler: CapturingHandler,
) -> None:
    """threshold() возвращает непустую строку UUID4."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    fid = ledger.threshold(
        subject="metric:wind_gust",
        metric="wind_gust_ms",
        value=20.0,
        limit=15.0,
        new_regime="alert",
    )
    assert fid
    uuid.UUID(fid)


@pytest.mark.unit()
def test_threshold_kind(capturing_handler: CapturingHandler) -> None:
    """threshold() создаёт запись с kind='threshold'."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.threshold("metric:x", "x", 20.0, 15.0, "alert")

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["kind"] == "threshold"


@pytest.mark.unit()
def test_threshold_fields_stored(capturing_handler: CapturingHandler) -> None:
    """threshold() сохраняет metric/value/limit/new_regime."""
    ledger = LedgerLogger(corr_id=_TEST_CORR_ID)
    ledger.threshold(
        subject="metric:wind_gust",
        metric="wind_gust_ms",
        value=20.5,
        limit=15.0,
        new_regime="alert",
    )

    extra = extract_extra(capturing_handler.records[-1])
    assert extra["metric"] == "wind_gust_ms"
    assert extra["value"] == pytest.approx(20.5)
    assert extra["limit"] == pytest.approx(15.0)
    assert extra["new_regime"] == "alert"