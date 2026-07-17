#!/usr/bin/env python3
"""
Генерация комбинированного отчёта по качеству сборки букетов
Раздельная статистика для групп 14 и 18 баллов

Группа 14:
- Клубничный букет
- Цветочный букет
- Коробочка с клубникой или бананами
- Клубничный бокс

Группа 18:
- Клубнично-цветочный букет
- Цветочный бокс
- Цветочно-клубничный бокс
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

PYRUS_TOKEN = os.getenv('PYRUS_ACCESS_TOKEN')
PYRUS_LOGIN = os.getenv('PYRUS_LOGIN')
FORM_ID = 1327961

OUTPUT_HTML = "quality-report-14-18.html"

# Максимальные баллы по категориям
CATEGORY_MAX = {
    'Клубничный букет': 14,
    'Цветочный букет': 14,
    'Коробочка с клубникой или бананами': 14,
    'Клубничный бокс': 14,
    'Клубнично-цветочный букет': 18,
    'Цветочный бокс': 14,
    'Коробочка+цветочный букет': 18,
    'Цветочно-клубничный бокс': 18
}

# Группы категорий
GROUP_14 = {
    'Клубничный букет',
    'Цветочный букет',
    'Коробочка с клубникой или бананами',
    'Клубничный бокс'
}

GROUP_18 = {
    'Клубнично-цветочный букет',
    'Коробочка+цветочный букет',
    'Цветочно-клубничный бокс'
}


def get_group(product_type):
    """Определяет группу (14 или 18) по типу товара"""
    if product_type in GROUP_14:
        return 14
    elif product_type in GROUP_18:
        return 18
    else:
        return None


def normalize_score(score, max_score):
    """Возвращает нормализованный процент"""
    if max_score == 0:
        return 0
    return (score / max_score) * 100


def auth():
    """Авторизация в Pyrus API"""
    session = requests.Session()
    session.trust_env = False

    response = session.post(
        'https://api.pyrus.com/v4/auth',
        headers={'Content-Type': 'application/json'},
        json={'login': PYRUS_LOGIN, 'security_key': PYRUS_TOKEN}
    )

    if response.status_code != 200:
        raise Exception(f"Auth failed: {response.text}")

    access_token = response.json()['access_token']
    return session, access_token


def get_all_submissions(session, access_token, form_id):
    """Получение всех заявок с пагинацией"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    all_tasks = []
    next_page_token = None

    while True:
        params = {'include_archived': 'true'}
        if next_page_token:
            params['next_page_token'] = next_page_token

        response = session.get(
            f'https://api.pyrus.com/v4/forms/{form_id}/register',
            headers=headers,
            params=params
        )
        response.raise_for_status()

        data = response.json()
        tasks = data.get('tasks', [])
        all_tasks.extend(tasks)

        print(f"  Загружено: {len(all_tasks)} заявок")

        has_more = data.get('has_more', False)
        if not has_more:
            break

        next_page_token = data.get('next_page_token')

    return all_tasks


def parse_submissions(tasks):
    """Парсит заявки в структурированный формат"""
    orders = []

    for task in tasks:
        values = {}
        for v in task.get('fields', []):
            field_id = v.get('id')
            value = v.get('value')

            if isinstance(value, dict) and 'choice_names' in value:
                value = value.get('choice_names', [''])[0]
            elif isinstance(value, list):
                value = ', '.join(str(v) for v in value)

            values[field_id] = value

        # Извлекаем дату
        created_date = values.get(1, '') or task.get('create_date', '')
        period = ''
        if created_date:
            try:
                if 'T' in created_date:
                    dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(created_date, '%Y-%m-%d')
                period = f"{dt.month}.{dt.year}"
            except:
                pass

        # Маппинг полей
        order = {
            'task_id': task.get('id', ''),
            'salon': values.get(10, ''),
            'florist': values.get(3, ''),
            'order_id': values.get(4, ''),
            'product_type': values.get(6, ''),
            'total_score': safe_float(values.get(18, '')),
            'period': period,
            'date': created_date.split('T')[0] if 'T' in created_date else created_date,
            'comment': values.get(17, '')
        }

        # Определяем группу
        order['group'] = get_group(order['product_type'])
        if order['group']:
            order['max_score'] = order['group']
            order['percent'] = normalize_score(order['total_score'], order['max_score'])

        orders.append(order)

    return orders


def calculate_stats(orders):
    """Рассчитывает статистику по группам и салонам"""
    # Группируем по салонам и группам
    salon_stats = {}  # {salon: {'14': {...}, '18': {...}}}

    for order in orders:
        if not order['group'] or not order['salon']:
            continue

        salon = order['salon']
        group = str(order['group'])

        if salon not in salon_stats:
            salon_stats[salon] = {'14': None, '18': None}

        # Инициализируем если нет
        if salon_stats[salon][group] is None:
            salon_stats[salon][group] = {
                'orders': [],
                'total_score': 0,
                'count': 0
            }

        salon_stats[salon][group]['orders'].append(order)
        salon_stats[salon][group]['total_score'] += order['total_score']
        salon_stats[salon][group]['count'] += 1

    # Рассчитываем средние
    results = {}
    for salon, groups in salon_stats.items():
        results[salon] = {
            '14': None,
            '18': None,
            'overall_count': 0,
            'overall_percent': 0
        }

        total_percent = 0
        total_groups = 0

        for group in ['14', '18']:
            if groups[group] and groups[group]['count'] > 0:
                avg_score = groups[group]['total_score'] / groups[group]['count']
                max_score = int(group)
                avg_percent = normalize_score(avg_score, max_score)

                results[salon][group] = {
                    'avg_score': round(avg_score, 1),
                    'max_score': max_score,
                    'avg_percent': round(avg_percent, 1),
                    'count': groups[group]['count'],
                    'orders': groups[group]['orders']  # сохраняем заказы для динамики
                }

                total_percent += avg_percent
                total_groups += 1
                results[salon]['overall_count'] += groups[group]['count']

        if total_groups > 0:
            results[salon]['overall_percent'] = round(total_percent / total_groups, 1)

    return results


def calculate_period_stats(orders):
    """Рассчитывает статистику по периодам для динамики"""
    # salon_period_data[salon][period]['14' or '18'] = {avg, count, percent}
    salon_period_data = {}

    for order in orders:
        if not order['group'] or not order['salon'] or not order['period']:
            continue

        salon = order['salon']
        period = order['period']
        group = str(order['group'])

        if salon not in salon_period_data:
            salon_period_data[salon] = {}

        if period not in salon_period_data[salon]:
            salon_period_data[salon][period] = {'14': [], '18': []}

        salon_period_data[salon][period][group].append(order['total_score'])

    # Рассчитываем средние по периодам
    results = {}
    for salon, periods in salon_period_data.items():
        results[salon] = {}

        for period, groups in periods.items():
            results[salon][period] = {}

            for group in ['14', '18']:
                scores = groups[group]
                if scores:
                    avg = sum(scores) / len(scores)
                    max_score = int(group)
                    results[salon][period][group] = {
                        'avg': round(avg, 1),
                        'max': max_score,
                        'count': len(scores),
                        'percent': round((avg / max_score) * 100, 1)
                    }

    return results

    # Рассчитываем средние
    results = {}
    for salon, groups in salon_stats.items():
        results[salon] = {
            '14': None,
            '18': None,
            'overall_count': 0,
            'overall_percent': 0
        }

        total_percent = 0
        total_groups = 0

        for group in ['14', '18']:
            if groups[group] and groups[group]['count'] > 0:
                avg_score = groups[group]['total_score'] / groups[group]['count']
                max_score = int(group)
                avg_percent = normalize_score(avg_score, max_score)

                results[salon][group] = {
                    'avg_score': round(avg_score, 1),
                    'max_score': max_score,
                    'avg_percent': round(avg_percent, 1),
                    'count': groups[group]['count']
                }

                total_percent += avg_percent
                total_groups += 1
                results[salon]['overall_count'] += groups[group]['count']

        if total_groups > 0:
            results[salon]['overall_percent'] = round(total_percent / total_groups, 1)

    return results


def calculate_category_stats(orders):
    """Рассчитывает статистику по салонам и категориям"""
    # salon_category_stats[salon][category] = {total, count, avg, max}
    salon_category_stats = {}

    for order in orders:
        if not order['salon'] or not order['product_type'] or order['total_score'] == 0:
            continue

        salon = order['salon']
        category = order['product_type']
        max_score = CATEGORY_MAX.get(category, 14)

        if salon not in salon_category_stats:
            salon_category_stats[salon] = {}

        if category not in salon_category_stats[salon]:
            salon_category_stats[salon][category] = {
                'total': 0,
                'count': 0,
                'max': max_score
            }

        salon_category_stats[salon][category]['total'] += order['total_score']
        salon_category_stats[salon][category]['count'] += 1

    # Рассчитываем средние
    results = {}
    for salon, categories in salon_category_stats.items():
        results[salon] = {}
        for category, data in categories.items():
            if data['count'] > 0:
                avg = data['total'] / data['count']
                results[salon][category] = {
                    'avg': round(avg, 1),
                    'max': data['max'],
                    'count': data['count'],
                    'percent': round((avg / data['max']) * 100, 1)
                }

    return results


def calculate_period_category_stats(orders):
    """Рассчитывает статистику по салонам и категориям по периодам"""
    # period_category_stats[period][salon][category] = {total, count, avg, max}
    period_category_stats = {}

    for order in orders:
        if not order['salon'] or not order['product_type'] or order['total_score'] == 0 or not order['period']:
            continue

        period = order['period']
        salon = order['salon']
        category = order['product_type']
        max_score = CATEGORY_MAX.get(category, 14)

        if period not in period_category_stats:
            period_category_stats[period] = {}

        if salon not in period_category_stats[period]:
            period_category_stats[period][salon] = {}

        if category not in period_category_stats[period][salon]:
            period_category_stats[period][salon][category] = {
                'total': 0,
                'count': 0,
                'max': max_score
            }

        period_category_stats[period][salon][category]['total'] += order['total_score']
        period_category_stats[period][salon][category]['count'] += 1

    # Рассчитываем средние
    results = {}
    for period, salons in period_category_stats.items():
        results[period] = {}
        for salon, categories in salons.items():
            results[period][salon] = {}
            for category, data in categories.items():
                if data['count'] > 0:
                    avg = data['total'] / data['count']
                    results[period][salon][category] = {
                        'avg': round(avg, 1),
                        'max': data['max'],
                        'count': data['count'],
                        'percent': round((avg / data['max']) * 100, 1)
                    }

    return results


def calculate_period_salon_stats(orders):
    """Рассчитывает статистику по салонам по периодам (аналог calculate_stats)"""
    # period_salon_stats[period][salon] = {'14': {...}, '18': {...}}
    period_salon_stats = {}

    for order in orders:
        if not order['group'] or not order['salon'] or not order['period']:
            continue

        period = order['period']
        salon = order['salon']
        group = str(order['group'])

        if period not in period_salon_stats:
            period_salon_stats[period] = {}

        if salon not in period_salon_stats[period]:
            period_salon_stats[period][salon] = {'14': None, '18': None}

        # Инициализируем если нет
        if period_salon_stats[period][salon][group] is None:
            period_salon_stats[period][salon][group] = {
                'total_score': 0,
                'count': 0
            }

        period_salon_stats[period][salon][group]['total_score'] += order['total_score']
        period_salon_stats[period][salon][group]['count'] += 1

    # Рассчитываем средние
    results = {}
    for period, salons in period_salon_stats.items():
        results[period] = {}
        for salon, groups in salons.items():
            results[period][salon] = {
                '14': None,
                '18': None,
                'overall_count': 0,
                'overall_percent': 0
            }

            total_percent = 0
            total_groups = 0

            for group in ['14', '18']:
                if groups[group] and groups[group]['count'] > 0:
                    avg_score = groups[group]['total_score'] / groups[group]['count']
                    max_score = int(group)
                    avg_percent = normalize_score(avg_score, max_score)

                    results[period][salon][group] = {
                        'avg_score': round(avg_score, 1),
                        'max_score': max_score,
                        'avg_percent': round(avg_percent, 1),
                        'count': groups[group]['count']
                    }

                    total_percent += avg_percent
                    total_groups += 1
                    results[period][salon]['overall_count'] += groups[group]['count']

            if total_groups > 0:
                results[period][salon]['overall_percent'] = round(total_percent / total_groups, 1)

    return results


def generate_html(salon_stats, category_stats, period_stats, period_salon_stats, period_category_stats, period_data_json):
    """Генерирует HTML отчёт"""

    # Собираем все периоды для селектора
    all_periods = sorted(period_salon_stats.keys(), key=lambda p: (int(p.split('.')[1]), int(p.split('.')[0])), reverse=True)

    # Генерация опций для селектора периода
    period_options = '<option value="all">За всё время</option>'
    month_names = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                    'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
    for period in all_periods:
        month, year = period.split('.')
        period_options += f'<option value="{period}">{month_names[int(month) - 1]} {year}</option>'

    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчёт по качеству — Группы 14 и 18 баллов</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Vollkorn:wght@500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --barkhat-wine:        #411330;
            --barkhat-pink:        #D19CC2;
            --barkhat-pink-bright: #E1A4C9;
            --barkhat-pink-light:  #E4C2DD;
            --barkhat-pink-deep:   #B26FA1;
            --barkhat-gray-dark:   #3C3C3C;
            --barkhat-gray:        #6F6F6F;
            --barkhat-white:       #FFFFFF;
            --barkhat-gradient:    linear-gradient(135deg, #E1A4C9 0%, #B26FA1 100%);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Inter', sans-serif;
            background: var(--barkhat-white);
            padding: 12px;
            color: var(--barkhat-gray-dark);
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 12px;
        }}

        .header {{
            background: var(--barkhat-wine);
            color: var(--barkhat-white);
            padding: 16px 24px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}

        .header h1 {{
            font-family: 'Vollkorn', serif;
            font-size: 22px;
            font-weight: 600;
            margin-bottom: 4px;
        }}

        .header p {{
            font-size: 12px;
            opacity: 0.8;
        }}

        .kpi-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .kpi-card {{
            background: var(--barkhat-gradient);
            padding: 20px;
            border-radius: 10px;
            color: var(--barkhat-white);
        }}

        .kpi-card h3 {{
            font-family: 'Vollkorn', serif;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
            opacity: 0.9;
        }}

        .kpi-card .main-value {{
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 4px;
        }}

        .kpi-card .sub-value {{
            font-size: 13px;
            opacity: 0.8;
        }}

        .section-title {{
            font-family: 'Vollkorn', serif;
            font-size: 20px;
            color: var(--barkhat-wine);
            margin-bottom: 16px;
            font-weight: 600;
        }}

        .rating-table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--barkhat-white);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(65, 19, 48, 0.08);
        }}

        .rating-table th {{
            background: var(--barkhat-pink-light);
            color: var(--barkhat-wine);
            font-family: 'Vollkorn', serif;
            font-weight: 600;
            text-align: left;
            padding: 12px 16px;
            font-size: 13px;
        }}

        .rating-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid #eee;
            font-size: 13px;
        }}

        .rating-table tr:hover td {{
            background: rgba(228, 194, 221, 0.18);
        }}

        .score-14 {{ font-weight: 600; color: var(--barkhat-wine); }}
        .score-18 {{ font-weight: 600; color: var(--barkhat-pink-deep); }}
        .percent-good {{ color: #2D5A2D; font-weight: 600; }}
        .percent-avg {{ color: #6A5A2A; font-weight: 600; }}
        .percent-bad {{ color: #6A2A2A; font-weight: 600; }}
        .no-data {{ color: var(--barkhat-gray); font-style: italic; }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-14 {{ background: var(--barkhat-pink-light); color: var(--barkhat-wine); }}
        .badge-18 {{ background: var(--barkhat-pink-bright); color: var(--barkhat-white); }}

        /* Блок категорий по салонам */
        .salons-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .salon-categories-card {{
            background: var(--barkhat-white);
            border: 1px solid var(--barkhat-pink-light);
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(65, 19, 48, 0.06);
        }}

        .salon-categories-card h3 {{
            font-family: 'Vollkorn', serif;
            font-size: 16px;
            color: var(--barkhat-wine);
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--barkhat-pink-light);
        }}

        .category-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}

        .category-row:last-child {{
            border-bottom: none;
        }}

        .category-name {{
            flex: 1;
            font-size: 12px;
            color: var(--barkhat-gray);
            min-width: 140px;
        }}

        .category-score {{
            font-size: 13px;
            font-weight: 600;
            color: var(--barkhat-wine);
            white-space: nowrap;
        }}

        .progress-bar {{
            width: 100px;
            height: 8px;
            background: #f0f0f0;
            border-radius: 4px;
            overflow: hidden;
        }}

        .progress-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .progress-fill.high {{ background: #2D5A2D; }}
        .progress-fill.medium {{ background: #6A5A2A; }}
        .progress-fill.low {{ background: #6A2A2A; }}

        .category-count {{
            font-size: 11px;
            color: var(--barkhat-gray);
            min-width: 30px;
            text-align: right;
        }}

        /* Кнопка динамики */
        .trend-btn {{
            background: var(--barkhat-gradient);
            color: var(--barkhat-white);
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 11px;
            font-weight: 500;
            cursor: pointer;
            transition: opacity 0.2s ease;
        }}
        .trend-btn:hover {{
            opacity: 0.9;
        }}

        /* Модальное окно динамики */
        .trend-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(65, 19, 48, 0.85);
            backdrop-filter: blur(4px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .trend-modal.active {{
            display: flex;
        }}
        .trend-modal-content {{
            background: var(--barkhat-white);
            border-radius: 12px;
            padding: 24px;
            max-width: 800px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            position: relative;
            box-shadow: 0 8px 32px rgba(65, 19, 48, 0.3);
        }}
        .trend-modal-close {{
            position: absolute;
            top: 16px;
            right: 16px;
            background: var(--barkhat-pink-light);
            border: none;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--barkhat-wine);
        }}
        .trend-modal-close:hover {{
            background: var(--barkhat-pink);
        }}
        .trend-modal-title {{
            font-family: 'Vollkorn', serif;
            font-size: 18px;
            color: var(--barkhat-wine);
            margin-bottom: 16px;
            padding-right: 40px;
            font-weight: 600;
        }}
        .trend-modal-subtitle {{
            color: var(--barkhat-gray);
            font-size: 13px;
            margin-bottom: 20px;
        }}
        .trend-chart-container {{
            position: relative;
            height: 350px;
        }}

        /* Селектор периода */
        .period-selector {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 12px;
        }}

        .period-selector select {{
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            background: rgba(255, 255, 255, 0.15);
            color: var(--barkhat-white);
            cursor: pointer;
            min-width: 150px;
        }}

        .period-selector select option {{
            background: var(--barkhat-wine);
            color: var(--barkhat-white);
        }}

        .period-selector select:hover {{
            background: rgba(255, 255, 255, 0.25);
        }}

        .period-selector label {{
            font-size: 13px;
            opacity: 0.9;
        }}

        @media (max-width: 768px) {{
            .rating-table {{ display: block; overflow-x: auto; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Отчёт по качеству — Группы 14 и 18 баллов</h1>
            <p>Раздельная статистика для простых и комбо-букетов</p>
            <div class="period-selector">
                <label for="periodSelect">Период оценки:</label>
                <select id="periodSelect" onchange="updatePeriod()">
                    {period_options}
                </select>
            </div>
        </div>

        <!-- KPI карточки -->
        <div class="kpi-section">
'''

    # Общая статистика по группам
    total_14 = {'sum': 0, 'count': 0}
    total_18 = {'sum': 0, 'count': 0}

    for salon, stats in salon_stats.items():
        if stats['14']:
            total_14['sum'] += stats['14']['avg_percent']
            total_14['count'] += 1
        if stats['18']:
            total_18['sum'] += stats['18']['avg_percent']
            total_18['count'] += 1

    avg_14 = round(total_14['sum'] / total_14['count'], 1) if total_14['count'] > 0 else 0
    avg_18 = round(total_18['sum'] / total_18['count'], 1) if total_18['count'] > 0 else 0

    count_14 = sum(s['14']['count'] for s in salon_stats.values() if s['14'])
    count_18 = sum(s['18']['count'] for s in salon_stats.values() if s['18'])

    html += f'''
            <div class="kpi-card">
                <h3>🔹 Группа 14 баллов</h3>
                <div class="main-value">{avg_14}%</div>
                <div class="sub-value">Среднее качество • {count_14} заказов</div>
            </div>
            <div class="kpi-card">
                <h3>🔸 Группа 18 баллов</h3>
                <div class="main-value">{avg_18}%</div>
                <div class="sub-value">Среднее качество • {count_18} заказов</div>
            </div>
        </div>

        <h2 class="section-title">Комбинированный рейтинг салонов</h2>

        <table class="rating-table">
            <thead>
                <tr>
                    <th>Салон</th>
                    <th><span class="badge badge-14">14</span> Балл / %</th>
                    <th>Заказов</th>
                    <th><span class="badge badge-18">18</span> Балл / %</th>
                    <th>Заказов</th>
                    <th>Общий %</th>
                    <th>Динамика</th>
                </tr>
            </thead>
            <tbody>
'''

    # Сортировка по общему проценту
    sorted_salons = sorted(
        salon_stats.items(),
        key=lambda x: x[1]['overall_percent'],
        reverse=True
    )

    for salon, stats in sorted_salons:
        s14 = stats['14']
        s18 = stats['18']

        percent_class = 'percent-good' if stats['overall_percent'] >= 90 else 'percent-avg' if stats['overall_percent'] >= 80 else 'percent-bad'

        # Собираем данные периодов для этого салона
        periods_data = {}
        if salon in period_stats:
            periods_data = period_stats[salon]

        # Преобразуем данные периодов в JSON для JavaScript
        import json
        periods_json = json.dumps(periods_data) if periods_data else '{}'

        # Экранируем апострофы в названии салона для HTML
        salon_escaped = salon.replace("'", "&apos;")
        # Сохраняем JSON в data-атрибут (автоматически экранируется при вставке в HTML)
        periods_json_attr = json.dumps(periods_data) if periods_data else '{}'

        html += f'''
                <tr>
                    <td><strong>{salon}</strong></td>
                    <td>{f'<span class="score-14">{s14["avg_score"]}/14</span> ({s14["avg_percent"]}%)' if s14 else '<span class="no-data">—</span>'}</td>
                    <td>{s14['count'] if s14 else '-'}</td>
                    <td>{f'<span class="score-18">{s18["avg_score"]}/18</span> ({s18["avg_percent"]}%)' if s18 else '<span class="no-data">—</span>'}</td>
                    <td>{s18['count'] if s18 else '-'}</td>
                    <td><span class="{percent_class}">{stats['overall_percent']}%</span></td>
                    <td><button class="trend-btn" data-salon="{salon_escaped}" data-periods='{periods_json_attr}' onclick="showTrendFromBtn(this)">📈 Динамика</button></td>
                </tr>
'''

    html += '''
            </tbody>
        </table>

        <h2 class="section-title" style="margin-top: 32px;">Качество салонов по категориям</h2>

        <div class="salons-grid">
'''

    # Сортировка салонов по общему проценту
    sorted_salons = sorted(
        salon_stats.items(),
        key=lambda x: x[1]['overall_percent'],
        reverse=True
    )

    # Генерация карточек салонов с категориями
    for salon, stats in sorted_salons:
        if salon not in category_stats or not category_stats[salon]:
            continue

        html += f'''
            <div class="salon-categories-card">
                <h3>{salon}</h3>
'''

        # Сортировка категорий по проценту
        cats = sorted(
            category_stats[salon].items(),
            key=lambda x: x[1]['percent'],
            reverse=True
        )

        for category, data in cats:
            percent = data['percent']
            progress_class = 'high' if percent >= 90 else 'medium' if percent >= 80 else 'low'

            html += f'''
                <div class="category-row">
                    <div class="category-name">{category}</div>
                    <div class="category-score">{data['avg']}/{data['max']}</div>
                    <div class="progress-bar">
                        <div class="progress-fill {progress_class}" style="width: {percent}%"></div>
                    </div>
                    <div class="category-count">{data['count']} шт</div>
                </div>
'''

        html += '''
            </div>
'''

    html += '''
        </div>

        <div style="margin-top: 24px; padding: 16px; background: #F8F9FA; border-radius: 10px; font-size: 12px; color: var(--barkhat-gray);">
            <strong>Легенда:</strong><br>
            🔹 <strong>14 баллов</strong> — Клубничный букет, Цветочный букет, Коробочка с клубникой/бананами, Клубничный бокс<br>
            🔸 <strong>18 баллов</strong> — Клубнично-цветочный букет, Коробочка+цветочный букет, Цветочно-клубничный бокс<br>
            <strong>Общий %</strong> — среднее от нормализованных процентов по обеим группам
        </div>
    </div>

    <!-- Модальное окно динамики -->
    <div class="trend-modal" id="trendModal">
        <div class="trend-modal-content">
            <button class="trend-modal-close" onclick="closeTrendModal()">&times;</button>
            <h2 class="trend-modal-title" id="trendModalTitle">Динамика качества</h2>
            <p class="trend-modal-subtitle">Качество по категориям за последние 6 месяцев</p>
            <div class="trend-chart-container">
                <canvas id="trendChart"></canvas>
            </div>
        </div>
    </div>

    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
        let trendChart = null;

        function showTrendFromBtn(btn) {
            const salonName = btn.getAttribute('data-salon');
            const periodsData = JSON.parse(btn.getAttribute('data-periods'));
            showTrend(salonName, periodsData);
        }

        function showTrend(salonName, periodsData) {
            document.getElementById('trendModalTitle').textContent = 'Динамика: ' + salonName;
            document.getElementById('trendModal').classList.add('active');

            // Функция для конвертации периода в формат даты
            const formatPeriod = function(periodStr) {
                const parts = periodStr.split('.');
                const month = parts[0];
                const year = parts[1];
                const monthNames = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
                return monthNames[parseInt(month) - 1] + '.' + year.slice(2);
            };

            // Функция для получения числового значения периода для сортировки
            const periodValue = function(periodStr) {
                const parts = periodStr.split('.');
                return parseInt(parts[1]) * 100 + parseInt(parts[0]); // ГГГГММ
            };

            // Подготовка данных - сортируем хронологически от старого к новому
            const sortedPeriods = Object.keys(periodsData).sort((a, b) => periodValue(a) - periodValue(b));
            const periods = sortedPeriods.slice(-6);
            const labels = periods.map(formatPeriod);
            const data14 = [];
            const data18 = [];

            periods.forEach(period => {
                const pData = periodsData[period];
                if (pData['14']) {
                    data14.push(pData['14'].avg);
                } else {
                    data14.push(null);
                }
                if (pData['18']) {
                    data18.push(pData['18'].avg);
                } else {
                    data18.push(null);
                }
            });

            // Уничтожаем предыдущий график
            if (trendChart) {
                trendChart.destroy();
            }

            // Создаём график
            const ctx = document.getElementById('trendChart').getContext('2d');
            trendChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '14 баллов',
                            data: data14,
                            borderColor: '#D19CC2',
                            backgroundColor: 'rgba(209, 156, 194, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 4,
                            pointBackgroundColor: '#D19CC2'
                        },
                        {
                            label: '18 баллов',
                            data: data18,
                            borderColor: '#B26FA1',
                            backgroundColor: 'rgba(178, 111, 161, 0.1)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 4,
                            pointBackgroundColor: '#B26FA1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                font: { family: 'Inter', size: 12 },
                                color: '#3C3C3C'
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const maxScore = context.dataset.label.includes('14') ? 14 : 18;
                                    return context.dataset.label + ': ' + context.parsed.y + '/' + maxScore;
                                }
                            }
                        }
                    },
                    scales: {
                        y: {
                            min: 8,
                            max: 20,
                            ticks: {
                                callback: function(value) {
                                    return value.toFixed(1);
                                },
                                font: { family: 'Inter', size: 11 },
                                color: '#6F6F6F'
                            },
                            grid: {
                                color: 'rgba(0, 0, 0, 0.05)'
                            }
                        },
                        x: {
                            ticks: {
                                font: { family: 'Inter', size: 11 },
                                color: '#6F6F6F'
                            },
                            grid: {
                                display: false
                            }
                        }
                    },
                    plugins: {
                        datalabels: {
                            anchor: 'end',
                            align: 'top',
                            color: '#411330',
                            font: {
                                weight: 'bold',
                                size: 11
                            },
                            formatter: function(value) {
                                return value ? value.toFixed(1) : '';
                            }
                        }
                    }
                },
                plugins: [{
                    id: 'datalabels',
                    afterDatasetsDraw: function(chart) {
                        const ctx = chart.ctx;
                        ctx.font = 'bold 11px Inter';
                        ctx.fillStyle = '#411330';
                        ctx.textAlign = 'center';

                        chart.data.datasets.forEach(function(dataset, datasetIndex) {
                            const meta = chart.getDatasetMeta(datasetIndex);
                            meta.data.forEach(function(point, index) {
                                const value = dataset.data[index];
                                if (value) {
                                    ctx.fillText(value.toFixed(1), point.x, point.y - 10);
                                }
                            });
                        });
                    }
                }]
            });
        }

        function closeTrendModal() {
            document.getElementById('trendModal').classList.remove('active');
            if (trendChart) {
                trendChart.destroy();
                trendChart = null;
            }
        }

        // Закрытие по клику вне окна
        document.getElementById('trendModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeTrendModal();
            }
        });

        '''
    html += f'''
        // ===== ДАННЫЕ ПО ПЕРИОДАМ =====
        const periodData = {period_data_json};
    '''
    html += '''

        // ===== ФУНКЦИЯ ОБНОВЛЕНИЯ ПО ПЕРИОДУ =====
        function updatePeriod() {
            const selectedPeriod = document.getElementById('periodSelect').value;
            const data = selectedPeriod === 'all' ? periodData.all : periodData.byPeriod[selectedPeriod];

            if (!data) return;

            // Обновляем KPI карточки
            updateKPI(data.kpi);

            // Обновляем таблицу рейтинга салонов
            updateSalonTable(data.salons);

            // Обновляем карточки категорий
            updateCategories(data.categories);
        }

        function updateKPI(kpi) {
            const card14 = document.querySelector('.kpi-card:nth-child(1) .main-value');
            const sub14 = document.querySelector('.kpi-card:nth-child(1) .sub-value');
            const card18 = document.querySelector('.kpi-card:nth-child(2) .main-value');
            const sub18 = document.querySelector('.kpi-card:nth-child(2) .sub-value');

            if (card14) card14.textContent = kpi['14'].percent + '%';
            if (sub14) sub14.textContent = 'Среднее качество • ' + kpi['14'].count + ' заказов';
            if (card18) card18.textContent = kpi['18'].percent + '%';
            if (sub18) sub18.textContent = 'Среднее качество • ' + kpi['18'].count + ' заказов';
        }

        function updateSalonTable(salons) {
            const tbody = document.querySelector('.rating-table tbody');
            if (!tbody) return;

            tbody.innerHTML = '';

            // Сортировка салонов
            const sortedSalons = Object.entries(salons).sort((a, b) => b[1].overall_percent - a[1].overall_percent);

            sortedSalons.forEach(([salon, stats]) => {
                const s14 = stats['14'];
                const s18 = stats['18'];
                const percentClass = stats.overall_percent >= 90 ? 'percent-good' : stats.overall_percent >= 80 ? 'percent-avg' : 'percent-bad';

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><strong>${salon}</strong></td>
                    <td>${s14 ? `<span class="score-14">${s14.avg_score}/14</span> (${s14.avg_percent}%)` : '<span class="no-data">—</span>'}</td>
                    <td>${s14 ? s14.count : '-'}</td>
                    <td>${s18 ? `<span class="score-18">${s18.avg_score}/18</span> (${s18.avg_percent}%)` : '<span class="no-data">—</span>'}</td>
                    <td>${s18 ? s18.count : '-'}</td>
                    <td><span class="${percentClass}">${stats.overall_percent}%</span></td>
                    <td><button class="trend-btn" data-salon="${salon.replace(/'/g, "&apos;")}" data-periods='${JSON.stringify(periodData.trends[salon] || {})}' onclick="showTrendFromBtn(this)">📈 Динамика</button></td>
                `;
                tbody.appendChild(row);
            });
        }

        function updateCategories(categories) {
            const grid = document.querySelector('.salons-grid');
            if (!grid) return;

            grid.innerHTML = '';

            // Сортировка салонов
            const sortedSalons = Object.keys(categories).sort((a, b) => {
                const aAvg = categories[a] ? Object.values(categories[a]).reduce((sum, c) => sum + c.percent, 0) / Object.values(categories[a]).length : 0;
                const bAvg = categories[b] ? Object.values(categories[b]).reduce((sum, c) => sum + c.percent, 0) / Object.values(categories[b]).length : 0;
                return bAvg - aAvg;
            });

            sortedSalons.forEach(salon => {
                const salonCats = categories[salon];
                if (!salonCats) return;

                const card = document.createElement('div');
                card.className = 'salon-categories-card';
                card.innerHTML = `<h3>${salon}</h3>`;

                // Сортировка категорий по проценту
                const sortedCats = Object.entries(salonCats).sort((a, b) => b[1].percent - a[1].percent);

                sortedCats.forEach(([category, data]) => {
                    const progressClass = data.percent >= 90 ? 'high' : data.percent >= 80 ? 'medium' : 'low';
                    const row = document.createElement('div');
                    row.className = 'category-row';
                    row.innerHTML = `
                        <div class="category-name">${category}</div>
                        <div class="category-score">${data.avg}/${data.max}</div>
                        <div class="progress-bar">
                            <div class="progress-fill ${progressClass}" style="width: ${data.percent}%"></div>
                        </div>
                        <div class="category-count">${data.count} шт</div>
                    `;
                    card.appendChild(row);
                });

                grid.appendChild(card);
            });
        }
    </script>
</body>
</html>'''

    return html


def safe_float(value):
    """Безопасное преобразование во float"""
    if value is None or value == '':
        return 0.0
    try:
        return float(str(value).strip())
    except:
        return 0.0


def main():
    print("=" * 60)
    print("Генерация комбинированного отчёта по качеству")
    print("=" * 60)

    # 1. Авторизация
    print("\n[1/4] Авторизация в Pyrus...")
    session, access_token = auth()
    print("  [OK] Авторизован")

    # 2. Получение данных
    print(f"\n[2/4] Загрузка данных из формы {FORM_ID}...")
    tasks = get_all_submissions(session, access_token, FORM_ID)
    print(f"  [OK] Загружено: {len(tasks)} заявок")

    # 3. Парсинг и расчёт
    print(f"\n[3/4] Обработка данных...")
    orders = parse_submissions(tasks)
    salon_stats = calculate_stats(orders)
    category_stats = calculate_category_stats(orders)
    period_stats = calculate_period_stats(orders)
    period_salon_stats = calculate_period_salon_stats(orders)
    period_category_stats = calculate_period_category_stats(orders)
    print(f"  [OK] Обработано: {len(orders)} заказов, {len(salon_stats)} салонов")

    # 4. Подготовка данных по периодам для JavaScript
    print(f"\n[4/5] Подготовка данных по периодам...")

    import json

    # Данные "за всё время"
    # KPI за всё время
    total_14 = {'sum': 0, 'count': 0}
    total_18 = {'sum': 0, 'count': 0}
    for salon, stats in salon_stats.items():
        if stats['14']:
            total_14['sum'] += stats['14']['avg_percent']
            total_14['count'] += 1
        if stats['18']:
            total_18['sum'] += stats['18']['avg_percent']
            total_18['count'] += 1
    avg_14 = round(total_14['sum'] / total_14['count'], 1) if total_14['count'] > 0 else 0
    avg_18 = round(total_18['sum'] / total_18['count'], 1) if total_18['count'] > 0 else 0
    count_14 = sum(s['14']['count'] for s in salon_stats.values() if s['14'])
    count_18 = sum(s['18']['count'] for s in salon_stats.values() if s['18'])

    all_data = {
        'kpi': {
            '14': {'percent': avg_14, 'count': count_14},
            '18': {'percent': avg_18, 'count': count_18}
        },
        'salons': salon_stats,
        'categories': category_stats
    }

    # Данные по периодам
    by_period_data = {}
    for period, salons in period_salon_stats.items():
        # KPI за период
        total_14_p = {'sum': 0, 'count': 0}
        total_18_p = {'sum': 0, 'count': 0}
        for salon, stats in salons.items():
            if stats['14']:
                total_14_p['sum'] += stats['14']['avg_percent']
                total_14_p['count'] += 1
            if stats['18']:
                total_18_p['sum'] += stats['18']['avg_percent']
                total_18_p['count'] += 1
        avg_14_p = round(total_14_p['sum'] / total_14_p['count'], 1) if total_14_p['count'] > 0 else 0
        avg_18_p = round(total_18_p['sum'] / total_18_p['count'], 1) if total_18_p['count'] > 0 else 0
        count_14_p = sum(s['14']['count'] for s in salons.values() if s['14'])
        count_18_p = sum(s['18']['count'] for s in salons.values() if s['18'])

        by_period_data[period] = {
            'kpi': {
                '14': {'percent': avg_14_p, 'count': count_14_p},
                '18': {'percent': avg_18_p, 'count': count_18_p}
            },
            'salons': salons,
            'categories': period_category_stats.get(period, {})
        }

    period_data_json = json.dumps({
        'all': all_data,
        'byPeriod': by_period_data,
        'trends': period_stats
    }, ensure_ascii=False)

    print(f"  [OK] Данные подготовлены для {len(by_period_data)} периодов")

    # 5. Генерация HTML
    print(f"\n[5/5] Генерация HTML...")
    html = generate_html(salon_stats, category_stats, period_stats, period_salon_stats, period_category_stats, period_data_json)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [OK] Сохранено: {OUTPUT_HTML}")

    print("\n" + "=" * 60)
    print("[OK] ГОТОВО! Отчёт создан")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    exit(main())
