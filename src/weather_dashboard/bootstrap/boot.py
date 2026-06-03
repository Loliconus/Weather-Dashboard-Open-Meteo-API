# =============================================================
# ПУТЬ        : src/weather_dashboard/bootstrap/boot.py
# ОБОЗНАЧЕНИЕ : WD.BOOT.07
# НАИМЕНОВАНИЕ: boot() — единая точка инициализации
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : bootstrap.settings, bootstrap.meta, bootstrap.context,
#               bootstrap.ledger, bootstrap.logging_std
# =============================================================
# Назначение:
#   boot() выполняет 5 фиксированных шагов и возвращает
#   замороженный Runtime с settings/meta/ledger/corr_id.
#   Первая JSON-запись в stdout — "паспорт изделия" (action=boot).
#   Проверка: pytest tests/unit/test_boot.py
# =============================================================

from __future__ import annotations

from dataclasses import dataclass

from weather_dashboard.bootstrap.context import new_corr_id
from weather_dashboard.bootstrap.ledger import LedgerLogger
from weather_dashboard.bootstrap.logging_std import configure_logging
from weather_dashboard.bootstrap.meta import ProductMeta, load_meta
from weather_dashboard.bootstrap.settings import Settings, load_settings

# -------------------------------------------------------------
# Раздел 1. Датакласс результата
# -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Runtime:
    """Результат boot() — контейнер сервисов текущего запуска.

    Иммутабелен (frozen=True). Передаётся через весь пайплайн.
    Все важные события фиксируются через rt.ledger.
    """

    settings: Settings    # Валидированные настройки из среды
    meta: ProductMeta     # Метаданные изделия из манифеста
    ledger: LedgerLogger  # Готовый логгер с привязанным corr_id
    corr_id: str          # UUID4 текущего запуска


# -------------------------------------------------------------
# Раздел 2. Функция инициализации
# -------------------------------------------------------------


def boot() -> Runtime:
    """Инициализировать Runtime за 5 фиксированных шагов.

    Шаги (порядок неизменен — см. AI-REFERENCE часть 3.2):
        1. load_settings()     → Settings (валидация env)
        2. configure_logging() → настройка root logger
        3. new_corr_id()       → UUID4, LedgerLogger(corr_id=...)
        4. load_meta()         → ProductMeta, ledger.fact("boot")
        5. return Runtime(...)

    Returns:
        Замороженный Runtime.

    Raises:
        SystemExit(1):                  Невалидная переменная среды.
        PackageNotFoundError:           Пакет не установлен.
    """
    # Шаг 1 — настройки
    settings = load_settings()

    # Шаг 2 — логирование
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    # Шаг 3 — correlation ID + ledger
    corr_id = new_corr_id()
    ledger = LedgerLogger(corr_id=corr_id)

    # Шаг 4 — паспорт изделия (первая запись в журнале)
    meta = load_meta()
    ledger.fact(
        subject="application",
        action="boot",
        product_name=meta.name,
        product_version=meta.version,
        description=meta.description,
        env=settings.env,
        log_level=settings.log_level,
        log_format=settings.log_format,
    )

    # Шаг 5 — возврат Runtime
    return Runtime(
        settings=settings,
        meta=meta,
        ledger=ledger,
        corr_id=corr_id,
    )