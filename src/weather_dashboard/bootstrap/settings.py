# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/settings.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.01
# НАИМЕНОВАНИЕ: Загрузка и валидация переменных среды
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : os, sys, dataclasses
# =============================================================
# Назначение:
#   Читает RST_ENV / RST_LOG_LEVEL / RST_LOG_FORMAT из os.environ.
#   При невалидном значении печатает все ошибки в stderr и вызывает
#   SystemExit(1) — согласно ТЗ раздел 8.4 и AI-REFERENCE часть 2.1.
#   Проверка: pytest tests/unit/test_settings.py
# =============================================================

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Literal

# -------------------------------------------------------------
# Раздел 0. Константы допустимых значений
# -------------------------------------------------------------

_ENV_VALUES: frozenset[str] = frozenset({"dev", "staging", "prod"})
_LOG_LEVEL_VALUES: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})
_LOG_FORMAT_VALUES: frozenset[str] = frozenset({"json", "text"})


# -------------------------------------------------------------
# Раздел 1. Датакласс настроек
# -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Settings:
    """Валидированные настройки окружения.

    Все поля иммутабельны после создания (frozen=True).
    Соответствует контракту RST Bootstrap (AI-REFERENCE часть 6.1).
    """

    env: Literal["dev", "staging", "prod"] = field(default="dev")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = field(default="INFO")
    log_format: Literal["json", "text"] = field(default="json")


# -------------------------------------------------------------
# Раздел 2. Загрузка и валидация
# -------------------------------------------------------------


def load_settings() -> Settings:
    """Загрузить настройки из переменных среды.

    Returns:
        Валидированный экземпляр Settings.

    Raises:
        SystemExit(1): При любом невалидном значении переменной среды.
    """
    errors: list[str] = []

    raw_env = os.environ.get("RST_ENV", "dev")
    if raw_env not in _ENV_VALUES:
        errors.append(
            f"RST_ENV={raw_env!r} is invalid."
            f" Allowed: {sorted(_ENV_VALUES)}"
        )

    raw_log_level = os.environ.get("RST_LOG_LEVEL", "INFO")
    if raw_log_level not in _LOG_LEVEL_VALUES:
        errors.append(
            f"RST_LOG_LEVEL={raw_log_level!r} is invalid."
            f" Allowed: {sorted(_LOG_LEVEL_VALUES)}"
        )

    raw_log_format = os.environ.get("RST_LOG_FORMAT", "json")
    if raw_log_format not in _LOG_FORMAT_VALUES:
        errors.append(
            f"RST_LOG_FORMAT={raw_log_format!r} is invalid."
            f" Allowed: {sorted(_LOG_FORMAT_VALUES)}"
        )

    if errors:
        for err in errors:
            print(f"[CONFIG ERROR] {err}", file=sys.stderr)  # noqa: T201
        sys.exit(1)

    return Settings(
        env=raw_env,  # type: ignore[arg-type]
        log_level=raw_log_level,  # type: ignore[arg-type]
        log_format=raw_log_format,  # type: ignore[arg-type]
    )