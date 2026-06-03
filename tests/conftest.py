# =============================================================
# ПУТЬ        : tests/conftest.py
# ОБОЗНАЧЕНИЕ : WD.TEST.00
# НАИМЕНОВАНИЕ: Фикстуры pytest — общие для всех тестов
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, logging, os
# =============================================================
# Назначение:
#   reset_logging (autouse) — сбрасывает handlers И уровни логгеров
#   после каждого теста, включая именованный логгер "ledger".
#   capturing_handler — подключает handler И выставляет уровень DEBUG
#   на логгере "ledger", чтобы INFO-сообщения не фильтровались.
#   clean_env — удаляет RST_* переменные среды.
#   Проверка: pytest tests/ (фикстуры применяются автоматически)
# =============================================================

from __future__ import annotations

import logging
import os
from collections.abc import Generator
from typing import Any

import pytest

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_RST_ENV_VARS: tuple[str, ...] = ("RST_ENV", "RST_LOG_LEVEL", "RST_LOG_FORMAT")


# -------------------------------------------------------------
# Раздел 1. Управление логированием
# -------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_logging() -> Generator[None, None, None]:
    """Сбросить состояние логгеров после каждого теста.

    Autouse=True — применяется ко всем тестам автоматически.

    Сбрасывает:
    - root logger: handlers + уровень → WARNING
    - именованный логгер "ledger": handlers + уровень → NOTSET
      (NOTSET означает "наследовать от root", не фиксировать свой уровень)

    Без сброса уровня "ledger" тесты, которые вызывают capturing_handler
    после предыдущего теста, могут унаследовать повышенный уровень фильтрации
    и не получить INFO-сообщения в records.
    """
    yield

    # Сброс root logger
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)

    # Сброс именованного ledger-логгера
    # ВАЖНО: setLevel(NOTSET) снимает явный уровень — логгер наследует от root.
    # Без этого уровень DEBUG, выставленный capturing_handler-фикстурой,
    # "протекает" между тестами и создаёт ложные зависимости.
    ledger_logger = logging.getLogger("ledger")
    ledger_logger.handlers.clear()
    ledger_logger.setLevel(logging.NOTSET)


# -------------------------------------------------------------
# Раздел 2. Среда выполнения
# -------------------------------------------------------------


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Удалить RST_* переменные среды перед тестом.

    Использовать в тестах, проверяющих дефолтные значения:

        def test_defaults(clean_env: None) -> None:
            s = load_settings()
            assert s.env == "dev"
    """
    for var in _RST_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# -------------------------------------------------------------
# Раздел 3. Вспомогательные утилиты (доступны в тестах)
# -------------------------------------------------------------


class CapturingHandler(logging.Handler):
    """Захватывающий handler для проверки ledger-записей в тестах.

    Использование:
        handler = CapturingHandler()
        logging.getLogger("ledger").addHandler(handler)
        ledger.fact("service", "started")
        record = handler.records[-1]
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def extract_extra(record: logging.LogRecord) -> dict[str, Any]:
    """Извлечь extra-поля из LogRecord (поля схемы ledger).

    Фильтрует стандартные атрибуты LogRecord, возвращает только
    поля, добавленные через extra= в logging.log().

    Поля схемы (kind, subject, fact_id и т.д.) — в результате напрямую.
    Пользовательский контекст — в result["ctx"].
    """
    skip = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    )
    return {k: v for k, v in record.__dict__.items() if k not in skip}


@pytest.fixture()
def capturing_handler() -> Generator[CapturingHandler, None, None]:
    """Создать CapturingHandler, подключить к ledger-логгеру и выставить уровень.

    КРИТИЧНО: выставляем setLevel(DEBUG) именно на логгере "ledger",
    а не на root. Это нужно потому что:
    - reset_logging (autouse) выставляет root на WARNING
    - логгер "ledger" наследует уровень от root (NOTSET → WARNING)
    - fact() и transition() пишут с level="INFO"
    - INFO < WARNING → сообщения фильтруются ДО вызова emit()
    - capturing_handler.records остаётся пустым → IndexError

    setLevel(DEBUG) на именованном логгере снимает наследование
    и разрешает все уровни ≥ DEBUG независимо от root.
    """
    handler = CapturingHandler()
    ledger_logger = logging.getLogger("ledger")
    ledger_logger.addHandler(handler)
    ledger_logger.setLevel(logging.DEBUG)  # ← ключевой фикс
    yield handler
    # Очистка происходит в reset_logging (autouse)