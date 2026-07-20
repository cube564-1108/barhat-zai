---
name: florist-dashboard-task-id-fix
description: Проблема с отсутствием task_id в блоке "Задачи с низким баллом" в дашборде флористов
metadata:
  type: project
---

# Проблема: Блок "Задачи с низким баллом" пустой

**Дата обнаружения:** 2026-07-16

## Симптом

В дашборде florist-quality-dashboard.html в блоке "Задачи с низким баллом" не отображаются задачи.

## Причина

В цепочке передачи данных теряется поле `task_id`:

1. **Pyrus API** → `task.id` есть ✓
2. **pyrus_to_csv_format()** → сохраняет в `record['task_id']` ✓
3. **generate_dashboard()** → **НЕ передаёт** `task_id` в `data.append()` ✗
4. **prepare_data_for_js()** → не получает `task_id` ✗
5. **JavaScript** → фильтрует все задачи из-за `!order.task_id` ✗

## Решение

Добавить `'task_id': record.get('task_id', '')` в `scripts/generate_dashboard_from_pyrus.py`:

```python
data.append({
    'task_id': record.get('task_id', ''),  # ← ДОБАВИТЬ ЭТО
    'city': '',
    'period': record['период'],
    ...
})
```

**Файл исправлен:** 2026-07-16

## Логика блока "Задачи с низким баллом"

**Критерий попадания:**
- Категории с maxScore = 14: оценка **≤ 13**
- Категории с maxScore = 18: оценка **≤ 16**

**Формат ссылки:**
```javascript
const pyrusUrl = 'https://pyrus.com/' + task.taskId;
// → https://pyrus.com/t#id123456789
```

**Структура отображения:**
```
🔍 [Салон]
  🔗 Заказ #123456  12/14  (Флорист: Иван)
  🔗 Заказ #789012  10/14  (Флорист: Петр)
  ... (до 5 худших задач на салон)
```

**Связанные файлы:**
- `scripts/generate_dashboard_from_pyrus.py` — основной скрипт генерации из Pyrus API
- `process_quality_data_full.py` — модуль генерации HTML
- `florist-quality-dashboard.html` — результирующий дашборд
