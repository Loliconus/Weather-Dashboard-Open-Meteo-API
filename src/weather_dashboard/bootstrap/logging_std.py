# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/logging_std.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.05
# НАИМЕНОВАНИЕ: Конфигурация stdlib-логирования (JSON и text)
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : logging, json, datetime
# =============================================================
# Назначение:
#   configure_logging() настраивает root logger.
#   JsonFormatter — для CI/production (машиночитаемый).
#   TextFormatter — для разработки (человекочитаемый).
#   Только stdlib, без сторонних библиотек (NFR-COMP-001).
#   Проверка: pytest tests/unit/test_boot.py
# =============================================================

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# -------------------------------------------------------------
# Раздел 0. Стандартные поля LogRecord (для фильтрации в extra)
# -------------------------------------------------------------

_STANDARD_LOG_RECORD_ATTRS: frozenset[str] = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
)


# -------------------------------------------------------------
# Раздел 1. Форматтеры
# -------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Форматтер JSON-строк для machine-readable логов.

    Сериализует стандартные поля LogRecord + все extra-поля
    в одну строку JSON. Используется в CI и production.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Сформировать JSON-строку из LogRecord."""
        # Базовые поля
        log_entry: dict[str, Any] = {
            "ts": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }

        # Extra-поля (поля ledger-схемы и ctx)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS and not key.startswith("_"):
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Форматтер человекочитаемых строк для разработки."""

    _FMT = "%(asctime)s [%(levelname)-8s] %(name)s | %(message)s"
    _DATE = "%H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self._FMT, datefmt=self._DATE)


# -------------------------------------------------------------
# Раздел 2. Точка конфигурации
# -------------------------------------------------------------


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
) -> None:
    """Настроить root logger.

    Идемпотентна: существующие handlers очищаются перед добавлением.
    После вызова все модули пишут в stdout через единый handler.

    Args:
        level: Уровень логирования ("DEBUG"|"INFO"|"WARNING"|"ERROR").
        fmt:   Формат записей ("json"|"text").
    """
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())

    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))