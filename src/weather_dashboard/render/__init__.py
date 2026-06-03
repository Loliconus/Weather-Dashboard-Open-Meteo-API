# =============================================================
# ПУТЬ        : src/weather_dashboard/render/__init__.py
# ОБОЗНАЧЕНИЕ : WD.REND.00
# НАИМЕНОВАНИЕ: Инициализация слоя рендеринга
# ДОКУМЕНТ    : КС-СТО-1.04.СК
# ПРОГРАММА   : Weather Dashboard
# ЗАВИСИМОСТИ : render_html, data_writer
# =============================================================
# Назначение:
#   Экспортирует HtmlRenderer и DataWriter.
#   Проверка: from weather_dashboard.render import HtmlRenderer
# =============================================================

from __future__ import annotations

from weather_dashboard.render.data_writer import DataWriter
from weather_dashboard.render.render_html import HtmlRenderer

__all__ = ["HtmlRenderer", "DataWriter"]