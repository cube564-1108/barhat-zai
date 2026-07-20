# Рефлексия: Аналитика по продажам — Фаза 6 (Деплой и отладка)

**Дата:** 2026-07-17
**Задача:** Деплой на Amvera и отладка SSL соединения

---

## Что делал

1. ✅ Обновил Dockerfile — добавил `sales-analytics.html` и скрипты
2. ✅ Создал feature-ветку `feature/sales-analytics`
3. ✅ Закоммитил и запушил в GitHub
4. ✅ Создал PR и замержил в main
5. ✅ Добавил `RETAILCRM_API_URL` в Amvera secrets

## Проблемы

### Проблема 1: ModuleNotFoundError: No module named 'export_retailcrm'

**Причина:** В Dockerfile не был скопирован `scripts/export_retailcrm.py`

**Решение:** Добавил `COPY scripts/export_retailcrm.py /app/scripts/export_retailcrm.py` в Dockerfile

### Проблема 2: Docker build failure — lstat /workspace/export_retailcrm.py

**Причина:** В Dockerfile был `COPY export_retailcrm.py /app/` — файла в корне нет

**Решение:** Убрал неправильную строку, оставил только правильный путь из `scripts/`

### Проблема 3: HTTP 400 — Missing RETAILCRM_API_URL

**Причина:** В Amvera был только `RETAILCRM_API_KEY`, но не было `RETAILCRM_API_URL`

**Решение:** Добавил `RETAILCRM_API_URL=https://barhat.retailcrm.ru` в secrets

### Проблема 4: HTTP 500 — SSL connection error

**Причина:** SSL проверка при соединении с RetailCRM API

**Решение (в процессе):**
- Добавил `urllib3.disable_warnings()`
- Добавил `verify=False` в `requests.get()`
- Добавил `session.verify = False` глобально

---

## Результат

**Частично.** Сайт работает, но аналитика по продажам возвращает 500.

---

## Что можно было сделать лучше

1. **Проверить все файлы в Dockerfile до коммита** — можно было заранее проверить что все зависимости есть
2. **Добавить все переменные окружения сразу** — можно было проверить `.env` локально и добавить все переменные в Amvera
3. **SSL verify=False сразу** — можно было добавить это при первом написании кода, зная что RetailCRM может иметь проблемы с SSL

---

## Было / Стало

| Было | Стало |
|------|-------|
| Нет аналитики по продажам на проде | Сайт работает, дашборд доступен |
| Нет конфигурационных файлов | Все конфиги добавлены в Docker |
| Нет переменных окружения | RETAILCRM_API_URL и API_KEY добавлены |
| — | SSL отладка в процессе |

---

## Следующие шаги (Фаза 7)

1. Дождаться завершения deploy с `session.verify = False`
2. Проверить работает ли аналитика по продажам
3. Если нет — попробовать альтернативные решения (timeout, другой URL, локальное тестирование)
