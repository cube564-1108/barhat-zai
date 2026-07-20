# Промт для продолжения: Аналитика по продажам — Фаза 6

Скопируй этот промт в новую сессию для продолжения задачи.

---

## Контекст

Я реализую аналитику по продажам для Бархата (сеть цветочных салонов).

**Что уже сделано:**
- ✅ Фаза 0: Созданы все конфиг файлы (salons, statuses, fields, cache)
- ✅ Фаза 1: Исследован RetailCRM API, найдены все поля, создан маппинг магазинов
- ✅ Фаза 2: Создан `scripts/export_retailcrm_sales.py` с классом `SalesAnalyticsExporter`
- ✅ Фаза 3: Добавлены 4 API эндпоинта в `reports/app.py`
- ✅ Фаза 4: Создан `sales-analytics.html` с Chart.js и бренд-токенами Бархат
- ✅ Фаза 5: Интегрирован в главный дашборд (`index.html`)

**Финальный план:** `plans/2026-07-17-sales-analytics-final.md`

**Рефлексии по сессиям:**
- `business/история/2026-07-17-sales-analytics-phase1-complete.md`
- `business/история/2026-07-17-sales-analytics-phase2-complete.md`
- `business/история/2026-07-17-sales-analytics-phases-2-3-4-complete.md`
- `business/история/2026-07-17-sales-analytics-phase5-complete.md`

---

## Задача: Фаза 6 — Деплой на Amvera

### 1. Проверить Dockerfile

Прочитать `Dockerfile` (в корне или в `.amvera/`) и убедиться что:
- `sales-analytics.html` копируется в образ
- `data/config/*.json` файлы копируются
- `scripts/export_retailcrm_sales.py` копируется
- `scripts/test_sales_analytics.py` копируется
- `reports/app.py` копируется (с изменениями)

Если чего-то нет — добавить в Dockerfile.

### 2. Проверить структуру файлов

Убедиться что все файлы на месте:
```
barhat-zai/
├── sales-analytics.html          (НОВЫЙ)
├── index.html                     (ИЗМЕНЁН — новый конфиг)
├── dashboard-config.json          (ИЗМЕНЁН — новая категория)
├── data/
│   └── config/
│       ├── salons.json           (НОВЫЙ)
│       ├── statuses.json         (НОВЫЙ)
│       ├── fields.json           (НОВЫЙ)
│       └── cache.json            (НОВЫЙ)
├── scripts/
│   ├── export_retailcrm_sales.py (НОВЫЙ)
│   └── test_sales_analytics.py   (НОВЫЙ)
└── reports/
    └── app.py                     (ИЗМЕНЁН — новые эндпоинты)
```

### 3. Создать feature-ветку и закоммитить

```bash
git checkout -b feature/sales-analytics
git add sales-analytics.html
git add index.html
git add dashboard-config.json
git add data/config/
git add scripts/export_retailcrm_sales.py
git add scripts/test_sales_analytics.py
git add reports/app.py
git commit -m "feat: add sales analytics dashboard

- Add SalesAnalyticsExporter for sales data aggregation
- Add 4 API endpoints for sales analytics
- Add sales-analytics.html with Chart.js
- Integrate into main dashboard (Analytics category)
- Config files for salons, statuses, fields, cache

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### 4. Пуш в GitHub

```bash
git push -u origin feature/sales-analytics
```

### 5. Pull Request

Создать PR на GitHub с описанием изменений.

### 6. Deploy на Amvera

- Зайти в Amvera Dashboard
- Нажать "Deploy"
- Дождаться окончания билда
- Проверить логи если есть ошибки

### 7. Smoke-test

После деплоя:
1. Открыть дашборд
2. Проверить что раздел "Аналитика → Продажи" отображается
3. Проверить что API эндпоинты отвечают
4. Проверить что графики отображаются

### 8. Merge в main

Если всё работает — мержим в main.

---

## Начинай с проверки Dockerfile!

**Что нужно проверить в Dockerfile:**
- COPY `sales-analytics.html`
- COPY `data/config/`
- COPY `scripts/export_retailcrm_sales.py`
- COPY `reports/app.py`

**Важно:** Убедиться что `.env` файл (с RETAILCRM_API_KEY) есть в Amvera secrets!

---

**Начинай реализацию!**
