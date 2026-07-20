# Промт для продолжения: Аналитика по продажам — Фаза 10

Скопируй этот промт в новую сессию для продолжения задачи.

---

## Контекст

Я реализую аналитику по продажам для Бархата (сеть цветочных салонов).

**Что уже сделано:**
- ✅ Фаза 0-5: Создан весь функционал (export script, API endpoints, HTML dashboard)
- ✅ Фаза 6: Первый деплой на Amvera
- ✅ Фаза 7-8: Отладка SSL соединения с RetailCRM API
- ✅ Фаза 8: Mock режим готов, фронтенд протестирован
- ⏳ Фаза 9: Попытки исправить SSL/TLS проблемы

**Последние коммиты:**
```
04d2f29 - refactor: simplify to use only urllib3 with custom SSL context
866798f - fix: try third RetailCRM IP and add urllib3 fallback
4a0972b - fix: add poolmanager attribute to SNIAdapter for compatibility
```

---

## Текущий статус: Фаза 10 — Тест HTTP + Фоновый режим

### Последние действия (Фаза 9)

**SSL отладка:**
- ❌ Попробованы 3 разных IP адреса RetailCRM
- ❌ SNI (Server Name Indication) через requests.Session
- ❌ urllib3 с custom SSL context (TLSv1.2)
- ❌ Перmissive cipher suites
- ❌ Host header для SNI

**Проблема:**
```
SSLError: _sslobj.read(len, buffer)
```
TLS handshake проходит, но чтение ответа падает. Даже за 1 день данных не загружается.

### Текущее действие: Тест HTTP вместо HTTPS

**Что сделал пользователь:**
1. В Amvera Dashboard → Settings → Environment Variables
2. Изменил `RETAILCRM_API_URL` с `https://` на `http://`
3. Задеплоил

**Нужно проверить:**
- https://barhat-zai-cube564.amvera.io/sales-analytics.html

**Если HTTP работает:**
- Отлично! SSL проблема решена

**Если HTTP не работает:**
- Переходим к реализации фонового режима с кэшем

---

## Следующие шаги

### Шаг 1: Проверить результат HTTP теста

Открыть https://barhat-zai-cube564.amvera.io/sales-analytics.html и проверить:
- Загружаются ли данные за текущий месяц
- Есть ли данные по 13 салонам

**Если работает:** ✅ SSL проблема решена с HTTP

**Если ошибка:** → Реализуем фоновый режим

---

### Шаг 2: Реализация фонового режима (если HTTP не сработает)

**Архитектура:**
1. При старте контейнера — загружаем данные в фоне в кэш
2. Frontend читает из кэша (мгновенно)
3. API endpoint `/api/sales/refresh` для обновления кэша
4. Фоновая задача для периодического обновления (раз в час)

**Файлы для изменения:**
- `reports/app.py` — добавить фоновую загрузку
- `scripts/export_retailcrm_sales.py` — добавить кэширование при старте

**План реализации:**
1. Добавить threading/background task в `app.py`
2. При старте — загружать данные за текущий месяц в кэш
3. API endpoints возвращают данные из кэша
4. Добавить `/api/sales/refresh` для принудительного обновления

---

## Важные файлы

- `scripts/export_retailcrm.py` — запросы к RetailCRM API
- `scripts/export_retailcrm_sales.py` — группировка по салонам
- `reports/app.py` — API endpoints
- `sales-analytics.html` — фронтенд с графиками
- `data/config/salons.json` — маппинг салонов (13 шт.)
- `Dockerfile` — `/etc/hosts` с RetailCRM IP

---

## Начинай с проверки HTTP теста!

**Сначала:** Узнать результат HTTP теста от пользователя
**Потом:** Либо завершаем (если работает), либо реализуем фоновый режим

---

## Дополнительная информация

### Текущие переменные окружения в Amvera:
- `RETAILCRM_API_URL=http://barhatretailcrm.retailcrm.ru` (изменено)
- `RETAILCRM_API_KEY=***SET***`
- `SALES_MOCK_MODE` — удалено

### Текущий код для SSL:
```python
# TLSv1.2 для совместимости
self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
self.ssl_context.check_hostname = False
self.ssl_context.verify_mode = ssl.CERT_NONE
```

### /etc/hosts в контейнере:
```
93.77.160.100 barhatretailcrm.retailcrm.ru
```
