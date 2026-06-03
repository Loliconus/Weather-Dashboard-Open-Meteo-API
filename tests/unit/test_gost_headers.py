# =============================================================
# ПУТЬ        : tests/unit/test_gost_headers.py
# ОБОЗНАЧЕНИЕ : WD.TEST.04
# НАИМЕНОВАНИЕ: Автопроверка ГОСТ-шапок во всех .py файлах
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : pytest, pathlib
# =============================================================
# Назначение:
#   Проверяет наличие обязательных маркеров MIN-профиля
#   в первых 20 строках каждого .py файла в src/ и tests/.
#   Маркеры: ПУТЬ, ОБОЗНАЧЕНИЕ, НАИМЕНОВАНИЕ, ДОКУМЕНТ, Назначение.
#   Падает при добавлении нового файла без шапки (NFR-MAINT-002).
#   Проверка: pytest tests/unit/test_gost_headers.py -v
# =============================================================

from __future__ import annotations

from pathlib import Path

import pytest

# -------------------------------------------------------------
# Раздел 0. Константы
# -------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCAN_DIRS = (_REPO_ROOT / "src", _REPO_ROOT / "tests")
_REQUIRED_MARKERS: tuple[str, ...] = (
    "ПУТЬ",
    "ОБОЗНАЧЕНИЕ",
    "НАИМЕНОВАНИЕ",
    "ДОКУМЕНТ",
    "Назначение",
)
_HEADER_LINES = 20

# -------------------------------------------------------------
# Раздел 1. Вспомогательные функции
# -------------------------------------------------------------


def _collect_py_files() -> list[Path]:
    """Собрать все .py файлы из src/ и tests/."""
    files: list[Path] = []
    for scan_dir in _SCAN_DIRS:
        if scan_dir.exists():
            files.extend(scan_dir.rglob("*.py"))
    return sorted(files)


def _check_file_headers(py_file: Path) -> list[str]:
    """Проверить наличие обязательных маркеров в первых N строках.

    Returns:
        Список отсутствующих маркеров (пустой если всё ок).
    """
    try:
        lines = py_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [f"Не удалось прочитать файл: {py_file}"]

    header_text = "\n".join(lines[:_HEADER_LINES])
    return [m for m in _REQUIRED_MARKERS if m not in header_text]


# -------------------------------------------------------------
# Раздел 2. Параметризованный тест
# -------------------------------------------------------------


@pytest.mark.unit()
@pytest.mark.parametrize("py_file", _collect_py_files(), ids=lambda p: str(p.relative_to(_REPO_ROOT)))
def test_gost_header_present(py_file: Path) -> None:
    """Каждый .py файл содержит обязательные маркеры ГОСТ-шапки.

    Проверяются первые 20 строк. Маркеры: ПУТЬ, ОБОЗНАЧЕНИЕ,
    НАИМЕНОВАНИЕ, ДОКУМЕНТ, Назначение (NFR-MAINT-002).
    """
    missing = _check_file_headers(py_file)
    assert not missing, (
        f"Файл {py_file.relative_to(_REPO_ROOT)} "
        f"не содержит маркеры: {missing}. "
        f"Добавьте ГОСТ-шапку согласно КС-СТО-1.04.СК Раздел 3.1."
    )