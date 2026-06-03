# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/__init__.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.00
# НАИМЕНОВАНИЕ: Инициализация bootstrap-слоя
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : boot, settings, schema, ledger
# =============================================================
# Назначение:
#   Экспортирует публичный API переносимого bootstrap-слоя.
#   Слой скопирован из RST Bootstrap и адаптирован (только
#   _DISTRIBUTION_NAME изменён в meta.py — правило из AI-REFERENCE).
#   Проверка: from weather_dashboard.bootstrap import boot, Runtime
# =============================================================

from __future__ import annotations

from weather_dashboard.bootstrap.boot import Runtime, boot
from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.bootstrap.settings import Settings

__all__ = ["boot", "Runtime", "LedgerLogger", "Settings"]