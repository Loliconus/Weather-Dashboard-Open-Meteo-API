# Contributing Guide

Спасибо за интерес к Weather Dashboard! 🌤

## Быстрый старт

```bash
# 1. Fork репозитория на GitHub, затем:
git clone https://github.com/YOUR_USERNAME/Weather-Dashboard-Open-Meteo-API.git
cd Weather-Dashboard-Open-Meteo-API

# 2. Установить uv (если не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Установить зависимости (из lockfile)
uv sync --frozen --all-extras

# 4. Установить pre-commit хуки
uv run pre-commit install

# 5. Проверить что всё работает
uv run pytest -q

Workflow
Мы используем GitHub Flow:

text

main (protected)
  └── feat/my-feature     ← ваша ветка
  └── fix/bug-description
  └── docs/update-readme
Создайте ветку от main:

Bash

git checkout -b feat/my-feature
Делайте коммиты по Conventional Commits.

Убедитесь что все проверки проходят:

Bash

uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run ty check src/
uv run pytest --cov=src --cov-fail-under=80
Откройте Pull Request в main. Заполните PR template.

Дождитесь прохождения CI (quality.yml) и review от @Loliconus.

Conventional Commits
Формат сообщения коммита:

text

<type>(<scope>): <description>

[optional body]

[optional footer(s)]
Типы
Тип	Когда использовать
feat	Новая функциональность
fix	Исправление бага
docs	Только документация
style	Форматирование (не влияет на логику)
refactor	Рефакторинг без изменения функциональности
perf	Улучшение производительности
test	Добавление/исправление тестов
chore	Обновление зависимостей, CI, конфигов
ci	Изменения в CI/CD
revert	Откат коммита
Примеры
text

feat(indices): add apparent temperature feel description in RU

fix(client): handle Retry-After header as float

docs(readme): add screenshots section

test(aggregations): add edge case for empty hourly data

chore(deps): update httpx to 0.28.1
Breaking changes
Добавьте ! после типа и BREAKING CHANGE: в footer:

text

feat(api)!: rename get_weather to get_forecast

BREAKING CHANGE: get_weather() удалён, используйте get_forecast()
Стандарты кода
Python
Стиль: PEP 8, enforced через ruff
Форматирование: ruff format (double quotes, 88 символов)
Типы: полные аннотации везде, ty check --strict
Docstrings: PEP 257 Google style
Минимальный docstring для публичных функций:

Python

def my_function(x: float, y: float) -> float:
    """Краткое описание.

    Args:
        x: Описание параметра x.
        y: Описание параметра y.

    Returns:
        Описание возвращаемого значения.

    Raises:
        ValueError: Когда именно бросается.

    Examples:
        >>> my_function(1.0, 2.0)
        3.0
    """
Для индексных функций дополнительно:

Python

    """
    Formula:
        HI = ...формула...

    Source:
        Автор (год). "Название". Ссылка.

    Notes:
        Edge cases и ограничения применимости.
    """
JavaScript
ES2022+, Vanilla JS (без фреймворков)
"use strict" в начале файла
const/let, без var
Числа через Intl.NumberFormat("ru-RU")
Даты через Intl.DateTimeFormat("ru-RU", { timeZone })
Тесты
Каждая новая функция → минимум: KAT + граничные значения + @given (Hypothesis)
Coverage ≥ 80% для processing/, ≥ 60% для api/
Интеграционные тесты → respx.mock, без реальных HTTP-запросов
Именование: test_<что тестируется>_<ожидаемый результат>
Структура PR
Один PR — одно изменение
Максимум ~400 строк diff (исключение: автогенерированные файлы)
Описание в PR template обязательно
Скриншоты для UI-изменений
Вопросы
Откройте Discussion или Issue с шаблоном.