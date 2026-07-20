# Промт для продолжения: Аналитика по продажам — Фаза 7

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
- ✅ Фаза 6: Деплой на Amvera

**Финальный план:** `plans/2026-07-17-sales-analytics-final.md`

**Рефлексии по сессиям:**
- `business/история/2026-07-17-sales-analytics-phase1-complete.md`
- `business/история/2026-07-17-sales-analytics-phase2-complete.md`
- `business/история/2026-07-17-sales-analytics-phases-2-3-4-complete.md`
- `business/история/2026-07-17-sales-analytics-phase5-complete.md`

---

## Текущий статус: Фаза 7 — Отладка SSL соединения

### Проблема

Сайт работает (https://barhat-zai-cube564.amvera.io/), но при загрузке аналитики по продажам возвращается **HTTP 500**.

**Логи показывают SSL ошибку при соединении с RetailCRM API:**
```
SystemExit: 1
ssl.py", line 1166, in read
http.client.py", line 291, in _read_status
File "/app/scripts/export_retailcrm.py", line 68, in fetch_orders
```

### Что уже尝试лено

1. ✅ Добавлена переменная `RETAILCRM_API_URL=https://barhat.retailcrm.ru` в Amvera
2. ✅ Добавлен `verify=False` в `requests.get()`
3. ✅ Добавлено `urllib3.disable_warnings()`
4. ⏳ **Сейчас:** Добавлено `session.verify = False` глобально

### Последний коммит

```
commit 38af991
fix: set session.verify=False globally for SSL issues
```

---

## Задачи

### 1. Проверить что deploy прошёл успешно

После deploy от пользователя:
- Открыть https://barhat-zai-cube564.amvera.io/
- Перейти в "Аналитика → Продажи"
- Проверить что графики загружаются

**Если работает:** → Завершить фазу 7, записать рефлексию
**Если 500:** → Показать логи, продолжить отладку

### 2. Если всё ещё 500 — альтернативные решения

Если `session.verify = False` не помогло:

**Вариант A:** Проверить API URL
- Может нужен URL без `https://` или с `/api`
- Пробовать: `https://barhat.retailcrm.ru/api`

**Вариант B:** Добавить timeout
```python
response = self.session.get(url, headers=self.headers, verify=False, timeout=30)
```

**Вариант C:** Проверить API ключ
- Может ключ неверный или истёк

**Вариант D:** Локальное тестирование
- Запустить `scripts/test_sales_analytics.py` локально с теми же переменными окружения

---

## Начинай с проверки deploy!

**Сначала спроси у пользователя:** "Завершился ли deploy? Работает ли аналитика по продажам?"

**Если работает:** → Запиши рефлексию и заверши проект
**Если не работает:** → Продолжай отладку по логам

---

**Начинай реализацию!**
