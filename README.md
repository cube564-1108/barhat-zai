# 🌸 Бархат - сеть цветочных салонов

[![Codespaces](https://github.com/cube564-1108/barhat-zai/actions/badge.svg)](https://github.com/cube564-1108/barhat-zai/codespaces)
[![Open in Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/cube564-1108/barhat-zai)

## 📋 О проекте

**Бархат** — сеть цветочных салонов. Занимаемся изготовлением и продажей букетов из цветов, клубники в шоколаде и других подарков.

## 🚀 Быстрый старт

### Вариант 1: Работа в браузере (GitHub Codespaces)

Нажми кнопку **[Open in Codespaces](https://codespaces.new/cube564-1108/barhat-zai)** — получишь полноценную среду разработки прямо в браузере!

**Что доступно в Codespace:**
- ✅ VS Code в браузере
- ✅ Python 3.11 с зависимостями
- ✅ Доступ ко всем файлам проекта
- ✅ Терминал для запуска скриптов

### Вариант 2: Локальная работа

```bash
# Клонируй репозиторий
git clone https://github.com/cube564-1108/barhat-zai.git
cd barhat-zai

# Установи зависимости
pip install -r scripts/requirements.txt
pip install -r reports/requirements.txt
```

## 📁 Структура проекта

| Директория | Описание |
|------------|----------|
| [business/](business/) | Бизнес-контекст: аудитория, продукты, цели, экономика |
| [scripts/](scripts/) | Python скрипты для работы с CRM и МойСклад |
| [reports/](reports/) | Отчёты и дашборды |
| [ai-clone/](ai-clone/) | Цифровая проекция владельца |
| [mastery/](mastery/) | Методологии работы |
| [plans/](plans/) | Технические планы |

## 🌐 Дашборды

### Florist Quality Dashboard

**Ссылка:** (будет доступна после деплоя на Amvera)

Дашборд для отслеживания качества сборки букетов по флористам.

## 📊 Скрипты

| Скрипт | Описание |
|--------|----------|
| `scripts/export_retailcrm.py` | Экспорт заказов из RetailCRM |
| `scripts/export_moysklad.py` | Экспорт из МойСклад |
| `scripts/reconcile_orders.py` | Сверка заказов между системами |
| `scripts/florist_orders.py` | Экспорт заказов флористов |
| `process_quality_data_full.py` | Обработка данных для дашборда |

## 🔗 Полезные ссылки

- **Бизнес-контекст:** [business/INDEX.md](business/INDEX.md)
- **Инструкции:** [instructions/](instructions/)
- **Планы:** [plans/](plans/)

---

*Создано с ❤️ для Бархат*
