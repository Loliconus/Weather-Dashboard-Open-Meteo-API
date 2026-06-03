# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/context.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.03
# НАИМЕНОВАНИЕ: Контекстные переменные corr_id и cause_id
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : contextvars, uuid
# =============================================================
# Назначение:
#   Управление correlation ID и cause ID через contextvars.
#   Потокобезопасно и безопасно для asyncio (у каждого task
#   свой контекст). corr_id создаётся один раз в boot().
#   Проверка: pytest tests/unit/test_boot.py
# =============================================================

from __future__ import annotations

import uuid
from contextvars import ContextVar

# -------------------------------------------------------------
# Раздел 0. Контекстные переменные
# -------------------------------------------------------------

_corr_id_var: ContextVar[str] = ContextVar("corr_id", default="")
_cause_id_var: ContextVar[str | None] = ContextVar("cause_id", default=None)


# -------------------------------------------------------------
# Раздел 1. Публичный API
# -------------------------------------------------------------


def new_corr_id() -> str:
    """Создать новый UUID4 correlation ID и сохранить в контексте.

    Returns:
        Строковое представление UUID4.
    """
    cid = str(uuid.uuid4())
    _corr_id_var.set(cid)
    return cid


def get_corr_id() -> str:
    """Получить текущий correlation ID.

    Returns:
        UUID4 строка. Пустая строка если corr_id не установлен.
    """
    return _corr_id_var.get()


def set_corr_id(corr_id: str) -> None:
    """Установить существующий correlation ID (из входящего запроса).

    Args:
        corr_id: UUID4 строка от вызывающей стороны.
    """
    _corr_id_var.set(corr_id)


def get_cause_id() -> str | None:
    """Получить текущий cause ID.

    Returns:
        UUID4 строка или None если цепочка причинности не установлена.
    """
    return _cause_id_var.get()


def set_cause_id(cause_id: str | None) -> None:
    """Установить cause ID для текущего контекста.

    Args:
        cause_id: UUID4 факта-причины или None.
    """
    _cause_id_var.set(cause_id)