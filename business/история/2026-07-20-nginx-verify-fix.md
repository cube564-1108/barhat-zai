---
name: 2026-07-20-nginx-verify-fix
description: Исправление 403 Forbidden из-за неверного proxy_pass
date: 2026-07-20
---

# Сессия: Исправление 403 Forbidden на сайте

## Задача
Проверить, почему сайт https://barhat-zai-cube564.amvera.io/ не работает.

## Как решал

### Диагностика
1. Проверил сайт через `curl` — получил `HTTP/1.1 403 Forbidden`
2. Проверил `/api/health` — работает, значит Flask и nginx запущены
3. Проверил `/verify` — вернул `404 Not Found`

### Проблема
В [nginx.conf:57](nginx.conf#L57) была ошибка в `proxy_pass`:
```nginx
proxy_pass http://flask_app/verify;
```

Когда `proxy_pass` указан с URI, nginx заменяет часть URI, совпадающую с location:
- Запрос: `GET /verify`
- Результат: `GET /verifyverify` на Flask
- Flask не знает `/verifyverify` → 404

### Решение
Изменил на:
```nginx
proxy_pass http://flask_app;
```

Теперь `/verify` correctly проксируется на Flask.

## Результат
✅ Сайт работает: https://barhat-zai-cube564.amvera.io/

## Что можно было лучше
**Правило nginx proxy_pass:** Если `proxy_pass` указан без URI (только `http://upstream`), nginx передаёт оригинальный URI. Если с URI (`http://upstream/path`), nginx заменяет часть URI, совпадающую с location.

## Было/Стало
- **Было:** 403 Forbidden на всех страницах
- **Стало:** Сайт работает, авторизация работает

## Файлы
- [nginx.conf](nginx.conf) — исправлен proxy_pass для /verify
