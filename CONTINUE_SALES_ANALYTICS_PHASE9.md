# Промт для продолжения: Аналитика по продажам — Фаза 9

Скопируй этот промт в новую сессию для продолжения задачи.

---

## Контекст

Я реализую аналитику по продажам для Бархата (сеть цветочных салонов).

**Что уже сделано:**
- ✅ Фаза 0-5: Создан весь функционал (export script, API endpoints, HTML dashboard)
- ✅ Фаза 6: Первый деплой на Amvera
- ⏳ Фаза 7-8: Отладка SSL соединения с RetailCRM API
- ✅ Фаза 8: Mock режим готов, фронтенд протестирован

**Последние коммиты:**
```
73dc7d6 - fix: update mock data with real salons and add year comparison
125c61e - fix: correct mock data structure and add filter handlers
2d45e83 - fix: add requests fallback for SSL and mock mode
```

---

## Текущий статус: Фаза 9 — Проверка SSL fix на Amvera

### Что было сделано в Фазе 8

**Mock режим (для тестирования фронтенда):**
- ✅ Добавлен `SALES_MOCK_MODE=true` в reports/app.py
- ✅ Mock данные с 13 реальными салонами из salons.json
- ✅ Фильтры периодов работают (current/last/custom)
- ✅ Месячный график с сравнением по годам

**SSL отладка:**
- ✅ Добавлен requests fallback вместо urllib3
- ✅ `requests.get(verify=False)` для проблемных SSL
- ✅ Логирование версий Python/urllib3

### Что сейчас на Amvera

- **Переменная окружения:** `SALES_MOCK_MODE=true` (нужно для теста фронтенда)
- **Сайт:** https://barhat-zai-cube564.amvera.io/sales-analytics.html
- **Последний деплой:** 73dc7d6

---

## Следующие шаги

### Шаг 1: Убрать mock режим и проверить SSL

1. В Amvera Dashboard → **Settings** → **Environment Variables**:
   - **УДАЛИ** переменную `SALES_MOCK_MODE` (или поставь `false`)
2. Нажми **Deploy**
3. Открой https://barhat-zai-cube564.amvera.io/sales-analytics.html

**Если работает** — отлично! SSL проблема решена с requests fallback.
**Если ошибка 500** — показывай логи.

---

### Шаг 2: Если SSL ошибка сохраняется

Варианты:

**A. Проверить RetailCRM с их стороны**
- Связаться с поддержкой RetailCRM
- Узнать требования к TLS версиям
- Проверить нет ли ограничений по IP

**B. Альтернативный подход**
- Использовать HTTP вместо HTTPS (если RetailCRM разрешает)
- Настроить proxy сервер для запросов
- Использовать alternative API client

---

### Шаг 3: Финальная проверка функционала

Когда API заработает:
1. ✅ Загрузка текущего месяца
2. ✅ Переключение периодов
3. ✅ Custom периоды
4. ✅ Сравнение по годам
5. ✅ Очистка кэша
6. ✅ Все 13 салонов с правильными данными

---

## Важные файлы

- `scripts/export_retailcrm.py` — запросы к RetailCRM API (requests fallback)
- `scripts/export_retailcrm_sales.py` — группировка по салонам
- `reports/app.py` — API endpoints + mock режим
- `sales-analytics.html` — фронтенд с графиками
- `data/config/salons.json` — маппинг салонов (13 шт.)

---

## Начинай с Шага 1!

**Сначала:** Убери `SALES_MOCK_MODE` на Amvera и задеплой.
**Потом:** Проверь загрузится ли реальный данных.

**Если ошибка — покажи логи!**

---
