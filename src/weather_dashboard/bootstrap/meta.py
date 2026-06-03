# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/meta.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.02
# НАИМЕНОВАНИЕ: Метаданные изделия из манифеста дистрибутива
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : importlib.metadata, dataclasses
# =============================================================
# Назначение:
#   Читает name/version/description из pyproject.toml через
#   importlib.metadata — единственный источник истины (SSOT).
#   _DISTRIBUTION_NAME — единственное место адаптации при переносе.
#   Проверка: pytest tests/unit/test_boot.py::test_meta
# =============================================================

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field

# -------------------------------------------------------------
# Раздел 0. Константа дистрибутива (ЕДИНСТВЕННОЕ МЕСТО ИЗМЕНЕНИЯ
#           при переносе bootstrap в другой проект)
# -------------------------------------------------------------

_DISTRIBUTION_NAME: str = "weather-dashboard"


# -------------------------------------------------------------
# Раздел 1. Датакласс метаданных
# -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductMeta:
    """Метаданные изделия из манифеста.

    Все поля читаются из pyproject.toml через importlib.metadata.
    Хардкод версий и имён в коде запрещён (NFR-MAINT).
    """

    name: str = field()
    version: str = field()
    description: str = field()
    python_requires: str = field(default="")


# -------------------------------------------------------------
# Раздел 2. Загрузка метаданных
# -------------------------------------------------------------


def load_meta() -> ProductMeta:
    """Загрузить метаданные из установленного дистрибутива.

    Returns:
        ProductMeta с данными из pyproject.toml.

    Raises:
        importlib.metadata.PackageNotFoundError:
            Пакет не установлен (нужен pip install -e .).
    """
    meta = importlib.metadata.metadata(_DISTRIBUTION_NAME)

    return ProductMeta(
        name=meta["Name"] or _DISTRIBUTION_NAME,
        version=meta["Version"] or "0.0.0",
        description=meta["Summary"] or "",
        python_requires=meta["Requires-Python"] or "",
    )