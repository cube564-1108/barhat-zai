# Промт для продолжения: Аналитика по продажам — Фаза 2

Скопируй этот промт в новую сессию для продолжения задачи.

---

## Контекст

Я реализую аналитику по продажам для Бархата (сеть цветочных салонов). Данные берутся из RetailCRM API.

**Что уже сделано:**
- ✅ Фаза 0: Созданы все конфиг файлы (salons, statuses, fields, cache)
- ✅ Фаза 1: Исследован RetailCRM API, найдены все поля, создан маппинг магазинов

**Финальный план:** `plans/2026-07-17-sales-analytics-final.md`

**Рефлексия предыдущей сессии:** `business/история/2026-07-17-sales-analytics-phase1-complete.md`

---

## Задача: Фаза 2 — Backend модуль выгрузки данных

Создать файл `scripts/export_retailcrm_sales.py` с классом `SalesAnalyticsExporter`.

### Ключевые требования:

1. **Наследование** от `RetailCRMExporter` (существующий класс в `scripts/export_retailcrm.py`)

2. **Использовать конфиги** из `data/config/`:
   - `salons.json` — маппинг RetailCRM ID → названия салонов
   - `statuses.json` — исключаемый статус `cancel-other`
   - `fields.json` — названия полей (`shipmentStore`, `summ`, `createdAt`)
   - `cache.json` — TTL кэша (3600 сек)

3. **Важно!** Маппинг магазинов учитывает изменения ID в апреле 2026:
   - ЕКБ: `barkhat-ekb2` → `barkhat-ekb`
   - НСК: `barkhat-nsk` → `barkhat-nsk-levyi`
   - Томск: `tomsk-frunze-102` → `barkhat-tomsk`
   Все ID должны работать для исторических данных!

4. **Методы класса:**
   - `_load_config()` — загрузка всех конфигов
   - `_filter_valid_orders(orders)` — исключить `cancel-other`
   - `_extract_salon_name(order)` — получить `shipmentStore` и замапить на название
   - `_extract_order_sum(order)` — получить `summ`
   - `_validate_data(data)` — проверить на пустые значения
   - `group_by_salon(orders)` — группировка по салонам
   - `get_current_month_stats()` — текущий месяц по салонам
   - `compare_periods(from, to)` — сравнение двух периодов
   - `get_monthly_comparison(year)` — данные по месяцам
   - `_save_cache(data, key)` / `_load_cache(key)` — кэширование в JSON

5. **Кэширование:**
   - Сохранять в `data/cache/` с TTL из конфига
   - Ключи кэша: `current_month`, `compare_YYYYMMDD_YYYYMMDD`, `monthly_YYYY`

6. **Формат данных API** (как должен возвращать):
   ```json
   {
     "period": {...},
     "salons": [{"name": "...", "shipment_sum": 456000, "orders_count": 234, "avg_check": 1948}],
     "total": {...},
     "cached": false
   }
   ```

### Поле limit в RetailCRM API
Важно: API требует `limit` = 20, 50 или 100 (не 1!)

### Начать с:

1. Создать базовую структуру класса с загрузкой конфигов
2. Реализовать фильтрацию и извлечение полей
3. Реализовать группировку по салонам с учётом маппинга
4. Добавить кэширование
5. Реализовать 3 метода для отчётов
6. Добавить тестирование в `if __name__ == '__main__'`

### Файлы для чтения перед стартом:
- `scripts/export_retailcrm.py` — базовый класс для наследования
- `data/config/salons.json` — маппинг магазинов
- `data/config/fields.json` — названия полей
- `data/config/statuses.json` — исключаемые статусы
- `data/mock/retailcrm_stats.json` — пример данных

---

**Начинай реализацию!**
