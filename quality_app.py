#!/usr/bin/env python3
"""
Flask backend для обновления данных качества из Pyrus API
Запускается на Amvera, проксирует запросы к Pyrus (токен хранится только на сервере)
"""

import os
import sys
import requests
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

PYRUS_TOKEN = os.getenv('PYRUS_ACCESS_TOKEN')
PYRUS_LOGIN = os.getenv('PYRUS_LOGIN')
FORM_ID = 1327961


def auth_pyrus():
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

    return session, response.json().get('access_token')


def get_all_submissions(session, access_token, form_id):
    """Получение всех заявок с пагинацией"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    all_tasks = []
    next_page_token = None

    while True:
        params = {}
        if next_page_token:
            params['next_page_token'] = next_page_token
        params['include_archived'] = 'true'

        response = session.get(
            f'https://api.pyrus.com/v4/forms/{form_id}/register',
            headers=headers,
            params=params
        )
        response.raise_for_status()

        data = response.json()
        tasks = data.get('tasks', [])
        all_tasks.extend(tasks)

        has_more = data.get('has_more', False)
        if not has_more:
            break

        next_page_token = data.get('next_page_token')

    return all_tasks


def parse_period(period_str):
    """Парсит период ММ.ГГГГ в число для сортировки"""
    if not period_str:
        return 0
    try:
        parts = period_str.split('.')
        if len(parts) == 2:
            return int(parts[1]) * 100 + int(parts[0])
    except:
        pass
    return 0


def safe_int(value):
    """Безопасное преобразование в int"""
    if value is None or value == '':
        return None
    try:
        return int(float(str(value).strip()))
    except:
        return None


def pyrus_to_records(tasks):
    """Преобразует задачи Pyrus в формат для дашборда 14-18"""

    city_mapping = {
        'ЕКБ': 'Екатеринбург',
        'БРН': 'Брянск',
        'ЧЛБ': 'Челябинск',
        'Челябинск': 'Челябинск',
        'НСК': 'Новосибирск',
        'Томск': 'Томск'
    }

    category_max = {
        'Клубничный букет': 14,
        'Цветочный букет': 14,
        'Коробочка с клубникой или бананами': 14,
        'Клубничный бокс': 14,
        'Клубнично-цветочный букет': 18,
        'Цветочный бокс': 14,
        'Коробочка+цветочный букет': 18,
        'Цветочно-клубничный бокс': 18
    }

    records = []

    for task in tasks:
        # Создаём dict значений
        values = {}
        for v in task.get('fields', []):
            field_id = v.get('id')
            value = v.get('value')

            if isinstance(value, dict) and 'choice_names' in value:
                choice_names = value.get('choice_names', [])
                value = choice_names[0] if choice_names else ''
            elif isinstance(value, list):
                value = ', '.join(str(v) for v in value)

            values[field_id] = value

        # Дата
        created_date = values.get(1, '') or task.get('create_date', '')
        period = ''
        date_display = ''

        if created_date:
            try:
                if 'T' in created_date:
                    dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                    date_display = created_date.split('T')[0]
                else:
                    dt = datetime.strptime(created_date, '%Y-%m-%d')
                    date_display = created_date
                period = f"{dt.month}.{dt.year}"
            except:
                pass

        # Салон и город
        salon = values.get(10, '')
        city = ''
        if salon:
            salon_parts = salon.split()
            if salon_parts:
                city_code = salon_parts[0]
                city = city_mapping.get(city_code, city_code)

        product_type = values.get(6, '')
        max_score = category_max.get(product_type, 14)
        total_score = safe_int(values.get(18, ''))

        record = {
            'task_id': str(task.get('id', '')),
            'order_id': values.get(4, ''),
            'period': period,
            'period_sort': parse_period(period),
            'date': date_display,
            'salon': salon,
            'city': city,
            'florist': values.get(3, ''),
            'product_type': product_type,
            'total_score': total_score,
            'max_score': max_score,
            'catalog_match': safe_int(values.get(7, '')),
            'packaging_neatness': safe_int(values.get(8, '')),
            'strawberry_design': safe_int(values.get(11, '')),
            'flower_processing': safe_int(values.get(20, '')),
            'assembly_technique': safe_int(values.get(13, '')),
            'film_separation': safe_int(values.get(14, '')),
            'materials_rules': safe_int(values.get(15, '')),
            'photo': safe_int(values.get(16, '')),
            'freshness': safe_int(values.get(23, '')),
            'comment': values.get(17, '')
        }

        records.append(record)

    return records


def calculate_period_data(records):
    """Вычисляет агрегированные данные по периодам"""

    period_data = {}
    all_records = records

    for record in records:
        period = record.get('period', 'all')
        if not period:
            period = 'all'

        if period not in period_data:
            period_data[period] = {
                'kpi': {'14': {'count': 0, 'sum': 0, 'perfect': 0},
                       '18': {'count': 0, 'sum': 0, 'perfect': 0}},
                'salons': {}
            }

        pd = period_data[period]

        # KPI
        max_score = record.get('max_score', 14)
        total_score = record.get('total_score', 0)
        group = '14' if max_score == 14 else '18'

        if total_score:
            pd['kpi'][group]['count'] += 1
            pd['kpi'][group]['sum'] += total_score
            perfect_threshold = 13 if max_score == 14 else 17
            if total_score >= perfect_threshold:
                pd['kpi'][group]['perfect'] += 1

        # По салонам
        salon = record.get('salon', '')
        if not salon:
            continue

        if salon not in pd['salons']:
            pd['salons'][salon] = {
                '14': {'count': 0, 'sum': 0, 'max_sum': 0},
                '18': {'count': 0, 'sum': 0, 'max_sum': 0}
            }

        if total_score:
            pd['salons'][salon][group]['count'] += 1
            pd['salons'][salon][group]['sum'] += total_score
            pd['salons'][salon][group]['max_sum'] += max_score

    # Вычисляем проценты
    for period, pd in period_data.items():
        for group in ['14', '18']:
            count = pd['kpi'][group]['count']
            if count > 0:
                avg = pd['kpi'][group]['sum'] / count
                max_avg = 14 if group == '14' else 18
                pd['kpi'][group]['percent'] = round((avg / max_avg) * 100, 1)
            else:
                pd['kpi'][group]['percent'] = 0

        for salon, sd in pd['salons'].items():
            for group in ['14', '18']:
                count = sd[group]['count']
                if count > 0:
                    avg = sd[group]['sum'] / count
                    max_avg = 14 if group == '14' else 18
                    sd[group]['avg'] = round(avg, 1)
                    sd[group]['max'] = max_avg
                    sd[group]['percent'] = round((avg / max_avg) * 100, 1)
                else:
                    sd[group]['avg'] = 0
                    sd[group]['max'] = 14 if group == '14' else 18
                    sd[group]['percent'] = 0

    return period_data


@app.route('/')
def index():
    """Главная страница - отдаёт HTML"""
    return send_from_directory('.', 'quality-report-14-18.html')


@app.route('/api/quality/update', methods=['POST'])
def update_quality():
    """Обновляет данные из Pyrus API"""

    try:
        # 1. Авторизация
        session, access_token = auth_pyrus()

        # 2. Получение данных
        tasks = get_all_submissions(session, access_token, FORM_ID)

        # 3. Преобразование
        records = pyrus_to_records(tasks)

        # 4. Вычисление агрегатов
        period_data = calculate_period_data(records)

        return jsonify({
            'success': True,
            'total_records': len(records),
            'periods': list(period_data.keys()),
            'period_data': period_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/health')
def health():
    """Health check для Amvera"""
    return jsonify({'status': 'ok', 'service': 'quality-backend'})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
