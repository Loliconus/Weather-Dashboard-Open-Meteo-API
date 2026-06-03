# =============================================================
# ПУТЬ        : src/weather_dashboard/__init__.py
# ОБОЗНАЧЕНИЕ : WD.PKG.00
# НАИМЕНОВАНИЕ: Публичный API пакета
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : importlib.metadata, bootstrap.boot
# =============================================================
# Назначение:
#   Точка входа пакета. Экспортирует boot() и __version__.
#   Версия читается из манифеста — SSOT в pyproject.toml.
#   Проверка: python -c "import weather_dashboard; print(weather_dashboard.__version__)"
# =============================================================

from __future__ import annotations

import importlib.metadata

from weather_dashboard.bootstrap.boot import Runtime, boot

try:
    __version__: str = importlib.metadata.version("weather-dashboard")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

__all__ = ["boot", "Runtime", "__version__"]