# =============================================================
# ПУТЬ        : tests/unit/test_boot.py
# ОБОЗНАЧЕНИЕ : WD.TEST.03
# НАИМЕНОВАНИЕ: Тесты функции boot() и датакласса Runtime
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, logging, weather_dashboard.bootstrap.boot
# =============================================================
# Назначение:
#   Покрывает FR-BOOT-003: 5 шагов boot(), паспорт изделия,
#   иммутабельность Runtime, наличие corr_id в ledger.
#   Требует pip install -e . (пакет должен быть установлен).
#   Проверка: pytest tests/unit/test_boot.py -v
# =============================================================

from __future__ import annotations

import logging
import uuid

import pytest

from tests.conftest import CapturingHandler, extract_extra
from weather_dashboard.bootstrap.boot import Runtime, boot

# -------------------------------------------------------------
# Раздел 1. Тесты структуры Runtime
# -------------------------------------------------------------


@pytest.mark.unit()
def test_boot_returns_runtime(clean_env: None) -> None:
    """boot() возвращает экземпляр Runtime."""
    rt = boot()
    assert isinstance(rt, Runtime)


@pytest.mark.unit()
def test_runtime_has_settings(clean_env: None) -> None:
    """Runtime содержит settings."""
    rt = boot()
    assert rt.settings is not None
    assert rt.settings.env == "dev"


@pytest.mark.unit()
def test_runtime_has_ledger(clean_env: None) -> None:
    """Runtime содержит ledger."""
    from weather_dashboard.bootstrap.ledger import LedgerLogger

    rt = boot()
    assert isinstance(rt.ledger, LedgerLogger)


@pytest.mark.unit()
def test_runtime_has_corr_id(clean_env: None) -> None:
    """Runtime содержит валидный UUID4 corr_id."""
    rt = boot()
    assert rt.corr_id
    uuid.UUID(rt.corr_id)  # Проверяем формат UUID


@pytest.mark.unit()
def test_runtime_is_frozen(clean_env: None) -> None:
    """Runtime иммутабелен (frozen=True)."""
    from dataclasses import FrozenInstanceError

    rt = boot()
    with pytest.raises(FrozenInstanceError):
        rt.corr_id = "new-id"  # type: ignore[misc]


# -------------------------------------------------------------
# Раздел 2. Тест паспорта изделия
# -------------------------------------------------------------


@pytest.mark.unit()
def test_boot_writes_passport_fact(clean_env: None) -> None:
    """boot() записывает паспорт изделия: kind='fact', action='boot'."""
    handler = CapturingHandler()
    logging.getLogger("ledger").addHandler(handler)

    boot()

    passport_records = [
        r for r in handler.records
        if getattr(r, "kind", None) == "fact"
        and getattr(r, "action", None) == "boot"
    ]
    assert passport_records, "Паспорт изделия не записан"

    extra = extract_extra(passport_records[0])
    assert extra["kind"] == "fact"
    assert extra["subject"] == "application"
    assert extra["action"] == "boot"


@pytest.mark.unit()
def test_boot_passport_contains_metadata(clean_env: None) -> None:
    """Паспорт содержит product_name и product_version в ctx."""
    handler = CapturingHandler()
    logging.getLogger("ledger").addHandler(handler)

    boot()

    passport = next(
        r for r in handler.records
        if getattr(r, "action", None) == "boot"
    )
    extra = extract_extra(passport)
    ctx = extra.get("ctx", {})
    assert ctx.get("product_name"), "product_name отсутствует в ctx паспорта"
    assert ctx.get("product_version"), "product_version отсутствует в ctx паспорта"


@pytest.mark.unit()
def test_boot_passport_contains_env(clean_env: None) -> None:
    """Паспорт содержит env в ctx."""
    handler = CapturingHandler()
    logging.getLogger("ledger").addHandler(handler)

    boot()

    passport = next(r for r in handler.records if getattr(r, "action", None) == "boot")
    ctx = extract_extra(passport).get("ctx", {})
    assert ctx.get("env") == "dev"


# -------------------------------------------------------------
# Раздел 3. Тесты уникальности corr_id
# -------------------------------------------------------------


@pytest.mark.unit()
def test_each_boot_generates_unique_corr_id(clean_env: None) -> None:
    """Каждый вызов boot() создаёт уникальный corr_id."""
    rt1 = boot()
    rt2 = boot()
    assert rt1.corr_id != rt2.corr_id