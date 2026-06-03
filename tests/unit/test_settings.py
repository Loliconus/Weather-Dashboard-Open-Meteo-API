# =============================================================
# ПУТЬ        : tests/unit/test_settings.py
# ОБОЗНАЧЕНИЕ : WD.TEST.01
# НАИМЕНОВАНИЕ: Тесты загрузки и валидации настроек
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, weather_dashboard.bootstrap.settings
# =============================================================
# Назначение:
#   Покрывает FR-BOOT-004: дефолты, чтение из среды,
#   SystemExit(1) при невалидных значениях (ТЗ раздел 8.4).
#   Проверка: pytest tests/unit/test_settings.py -v
# =============================================================

from __future__ import annotations

import dataclasses

import pytest

from weather_dashboard.bootstrap.settings import load_settings

# -------------------------------------------------------------
# Раздел 1. Дефолтные значения
# -------------------------------------------------------------


@pytest.mark.unit()
def test_defaults_env(clean_env: None) -> None:
    """Дефолт RST_ENV = 'dev'."""
    s = load_settings()
    assert s.env == "dev"


@pytest.mark.unit()
def test_defaults_log_level(clean_env: None) -> None:
    """Дефолт RST_LOG_LEVEL = 'INFO'."""
    s = load_settings()
    assert s.log_level == "INFO"


@pytest.mark.unit()
def test_defaults_log_format(clean_env: None) -> None:
    """Дефолт RST_LOG_FORMAT = 'json'."""
    s = load_settings()
    assert s.log_format == "json"


# -------------------------------------------------------------
# Раздел 2. Чтение из переменных среды
# -------------------------------------------------------------


@pytest.mark.unit()
def test_reads_rst_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """RST_ENV='prod' читается корректно."""
    monkeypatch.setenv("RST_ENV", "prod")
    s = load_settings()
    assert s.env == "prod"


@pytest.mark.unit()
def test_reads_rst_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """RST_LOG_LEVEL='DEBUG' читается корректно."""
    monkeypatch.setenv("RST_LOG_LEVEL", "DEBUG")
    s = load_settings()
    assert s.log_level == "DEBUG"


@pytest.mark.unit()
def test_reads_rst_log_format_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """RST_LOG_FORMAT='text' читается корректно."""
    monkeypatch.setenv("RST_LOG_FORMAT", "text")
    s = load_settings()
    assert s.log_format == "text"


# -------------------------------------------------------------
# Раздел 3. Иммутабельность Settings
# -------------------------------------------------------------


@pytest.mark.unit()
def test_settings_is_frozen(clean_env: None) -> None:
    """Settings иммутабельны (frozen=True) — присваивание бросает FrozenInstanceError.

    ВАЖНО: используем setattr(), а НЕ object.__setattr__().
    object.__setattr__() обходит __setattr__ датакласса и пишет
    напрямую в __dict__ объекта — FrozenInstanceError не поднимается.
    setattr() вызывает Settings.__setattr__, который и бросает исключение.
    """
    s = load_settings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(s, "env", "prod")  # type: ignore[misc]


# -------------------------------------------------------------
# Раздел 4. Валидация — SystemExit(1) при ошибках
# -------------------------------------------------------------


@pytest.mark.unit()
def test_invalid_rst_env_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Невалидный RST_ENV вызывает SystemExit(1)."""
    monkeypatch.setenv("RST_ENV", "UNKNOWN")
    with pytest.raises(SystemExit) as exc_info:
        load_settings()
    assert exc_info.value.code == 1


@pytest.mark.unit()
def test_invalid_rst_log_level_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Невалидный RST_LOG_LEVEL вызывает SystemExit(1)."""
    monkeypatch.setenv("RST_LOG_LEVEL", "VERBOSE")
    with pytest.raises(SystemExit) as exc_info:
        load_settings()
    assert exc_info.value.code == 1


@pytest.mark.unit()
def test_invalid_rst_log_format_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Невалидный RST_LOG_FORMAT вызывает SystemExit(1)."""
    monkeypatch.setenv("RST_LOG_FORMAT", "xml")
    with pytest.raises(SystemExit) as exc_info:
        load_settings()
    assert exc_info.value.code == 1


@pytest.mark.unit()
def test_multiple_invalid_all_reported(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Все ошибки выводятся в stderr (не только первая)."""
    monkeypatch.setenv("RST_ENV", "BAD")
    monkeypatch.setenv("RST_LOG_LEVEL", "VERBOSE")

    with pytest.raises(SystemExit):
        load_settings()

    captured = capsys.readouterr()
    assert "RST_ENV" in captured.err
    assert "RST_LOG_LEVEL" in captured.err