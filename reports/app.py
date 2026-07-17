#!/usr/bin/env python3
"""
Backend API для лендинга с отчетами по сверке заказов.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, request, jsonify, send_from_directory, redirect, make_response, abort
from flask_cors import CORS
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer

# Добавляем корневую директорию в path для импорта скриптов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорт аналитики продаж
from scripts.export_retailcrm_sales import SalesAnalyticsExporter

load_dotenv()

# Конфигурация
SSO_SECRET = os.environ.get("BARKHAT_SSO_SECRET", "")
SSO_ENABLED = bool(SSO_SECRET)

# Mock режим для аналитики продаж (для тестирования фронтенда без API)
SALES_MOCK_MODE = os.environ.get("SALES_MOCK_MODE", "false").lower() == "true"

if not SSO_ENABLED:
    print("⚠️  WARNING: BARKHAT_SSO_SECRET not set — SSO disabled, running in open mode")
    print("⚠️  Set BARKHAT_SSO_SECRET environment variable to enable authentication")

SESSION_SECRET = os.environ.get("SESSION_SECRET", os.urandom(32).hex())

app = Flask(__name__, static_folder='.')
CORS(app)

# Сериализатор для сессий (itsdangerous)
session_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="barkhat-quality-session")

# Lazy init для SalesAnalyticsExporter
_sales_exporter = None

def get_sales_exporter():
    """Получить экземпляр SalesAnalyticsExporter (lazy init)."""
    global _sales_exporter
    if _sales_exporter is None:
        _sales_exporter = SalesAnalyticsExporter()
    return _sales_exporter


def create_session_cookie(user_claims):
    """Создать подписанное значение куки сессии."""
    # Сохраняем только нужные данные
    session_data = {
        "sub": user_claims.get("sub"),
        "name": user_claims.get("name"),
        "email": user_claims.get("email"),
        "role": user_claims.get("role"),
        "salon": user_claims.get("salon"),
    }
    return session_serializer.dumps(session_data)


def verify_session(token):
    """Проверить сессию и вернуть данные пользователя или None."""
    try:
        # Max_age=8 часов (28800 секунд)
        return session_serializer.loads(token, max_age=28800)
    except Exception:
        return None


def require_session(f):
    """Декоратор: требовать валидную сессию для эндпоинта."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Если SSO отключён — пропускаем все запросы (open mode)
        if not SSO_ENABLED:
            request.user = {"name": "Anonymous", "sub": None}
            return f(*args, **kwargs)

        session_token = request.cookies.get("session")
        if not session_token:
            abort(401)
        user = verify_session(session_token)
        if not user:
            abort(401)
        # Добавляем пользователя в request context
        request.user = user
        return f(*args, **kwargs)
    return decorated


@app.route("/sso")
def sso():
    """
    SSO entry point — проверяет JWT от БАРХАТ Пульс и завёт сессию.

    GET /sso?token=<JWT>
    """
    token = request.args.get("token", "")
    if not token:
        abort(400, "Missing token parameter")

    try:
        # Проверяем подпись и claims JWT
        claims = jwt.decode(
            token,
            SSO_SECRET,
            algorithms=["HS256"],
            audience="quality",
            issuer="barkhat-pulse",
            options={"require": ["exp", "aud", "iss", "sub"]}
        )
    except jwt.ExpiredSignatureError:
        abort(403, "Token expired")
    except jwt.InvalidTokenError as e:
        abort(403, f"Invalid token: {str(e)}")
    except Exception as e:
        abort(403, f"Token verification failed: {str(e)}")

    # Создаём нашу сессию
    session_value = create_session_cookie(claims)

    # Редирект на корень с установкой куки
    resp = make_response(redirect("/"))
    # Кука внутри iframe — нужны SameSite=None; Secure; Partitioned (CHIPS)
    resp.headers.add(
        "Set-Cookie",
        f"session={session_value}; "
        f"Secure; HttpOnly; SameSite=None; Partitioned; Path=/; Max-Age=28800"
    )
    return resp


@app.route("/verify")
def verify():
    """
    Эндпоинт для nginx auth_request — проверяет сессию.

    Возвращает 200 если сессия валидна, 401 если нет.
    """
    session_token = request.cookies.get("session")
    if not session_token:
        abort(401)

    user = verify_session(session_token)
    if not user:
        abort(401)

    return jsonify({"status": "ok", "user": user["name"]}), 200





@app.route('/')
@require_session
def index():
    """Главная страница (требует сессию)."""
    return send_from_directory('.', 'index.html')


@app.route('/api/reconcile', methods=['POST'])
@require_session
def reconcile_orders():
    """
    Запустить сверку заказов за период.

    Body:
    {
        "from": "2026-07-01T00:00",
        "to": "2026-07-07T23:59"
    }
    """
    try:
        data = request.json
        from_date_str = data.get('from')
        to_date_str = data.get('to')

        if not from_date_str:
            return jsonify({'error': 'Не указана дата начала'}), 400

        # Конвертируем даты из формата datetime-local в формат для скриптов
        from_date = datetime.fromisoformat(from_date_str).strftime('%Y-%m-%d %H:%M:%S')
        to_date = datetime.fromisoformat(to_date_str).strftime('%Y-%m-%d %H:%M:%S') if to_date_str else None

        print(f"Запуск сверки: {from_date} - {to_date}")

        # Пути к скриптам
        scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        crm_script = os.path.join(scripts_dir, 'scripts', 'export_retailcrm.py')
        ms_script = os.path.join(scripts_dir, 'scripts', 'export_moysklad.py')
        reconcile_script = os.path.join(scripts_dir, 'scripts', 'reconcile_orders.py')

        # Временные файлы
        temp_dir = os.path.join(scripts_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        crm_file = os.path.join(temp_dir, 'crm_orders.json')
        ms_file = os.path.join(temp_dir, 'ms_orders.json')
        report_file = os.path.join(temp_dir, 'report.json')

        # Шаг 1: Выгрузка из CRM
        print('Выгрузка из RetailCRM...')
        cmd_crm = [
            sys.executable, crm_script,
            '--from', from_date,
            '--output', crm_file
        ]
        if to_date:
            cmd_crm.extend(['--to', to_date])

        result_crm = subprocess.run(cmd_crm, capture_output=True, text=True)
        if result_crm.returncode != 0:
            return jsonify({'error': f'Ошибка выгрузки CRM: {result_crm.stderr}'}), 500

        # Шаг 2: Выгрузка из МойСклад
        print('Выгрузка из МойСклад...')
        cmd_ms = [
            sys.executable, ms_script,
            '--from', from_date,
            '--output', ms_file
        ]
        if to_date:
            cmd_ms.extend(['--to', to_date])

        result_ms = subprocess.run(cmd_ms, capture_output=True, text=True)
        if result_ms.returncode != 0:
            return jsonify({'error': f'Ошибка выгрузки МойСклад: {result_ms.stderr}'}), 500

        # Шаг 3: Сверка
        print('Выполнение сверки...')
        cmd_reconcile = [
            sys.executable, reconcile_script,
            '--crm', crm_file,
            '--ms', ms_file,
            '--output', report_file
        ]

        result_reconcile = subprocess.run(cmd_reconcile, capture_output=True, text=True)
        if result_reconcile.returncode != 0:
            return jsonify({'error': f'Ошибка сверки: {result_reconcile.stderr}'}), 500

        # Читаем отчет
        with open(report_file, 'r', encoding='utf-8') as f:
            report = json.load(f)

        # Удаляем временные файлы
        try:
            os.remove(crm_file)
            os.remove(ms_file)
            os.remove(report_file)
        except:
            pass

        return jsonify(report)

    except Exception as e:
        print(f'Ошибка: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/update-quality', methods=['POST'])
@require_session
def update_quality_data():
    """
    Обновить данные качества букетов из Pyrus.

    Запускает процесс:
    1. Выгрузка из Pyrus (pyrus_export.py)
    2. Генерация HTML (process_quality_data_full.py)
    3. Обновление index.html в корне
    """
    try:
        print("🔄 Начинаем обновление данных качества...")

        # Пути к скриптам и файлам
        # В контейнере app.py лежит в /app/, локально в reports/
        if os.path.exists('/app/pyrus_export.py'):
            # Контейнер
            root_dir = '/app'
        else:
            # Локальная разработка
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        pyrus_script = os.path.join(root_dir, 'pyrus_export.py')
        process_script = os.path.join(root_dir, 'process_quality_data_full.py')
        data_dir = os.path.join(root_dir, 'data')
        target_html = os.path.join(root_dir, 'index.html')

        # Шаг 1: Выгрузка из Pyrus
        print("📥 Шаг 1: Выгрузка из Pyrus...")

        # Подготавливаем переменные окружения для скриптов
        script_env = {
            **os.environ,
            'PYTHONIOENCODING': 'utf-8',
            'DATA_DIR': data_dir,
            'OUTPUT_FILE': target_html
        }

        cmd_pyrus = [sys.executable, pyrus_script]
        result_pyrus = subprocess.run(
            cmd_pyrus,
            capture_output=True,
            text=True,
            cwd=root_dir,
            env=script_env
        )

        if result_pyrus.returncode != 0:
            return jsonify({
                'error': 'Ошибка выгрузки из Pyrus',
                'details': result_pyrus.stderr
            }), 500

        print("✅ Выгрузка из Pyrus завершена")

        # Шаг 2: Генерация HTML
        print("📊 Шаг 2: Генерация HTML...")
        cmd_process = [sys.executable, process_script]
        result_process = subprocess.run(
            cmd_process,
            capture_output=True,
            text=True,
            cwd=root_dir,
            env=script_env
        )

        if result_process.returncode != 0:
            return jsonify({
                'error': 'Ошибка генерации HTML',
                'details': result_process.stderr
            }), 500

        print("✅ HTML сгенерирован")

        # Шаг 3: Проверка, что файл создан
        if not os.path.exists(target_html):
            return jsonify({
                'error': 'HTML файл не был создан'
            }), 500

        # Получаем статистику из сгенерированного HTML
        # Извлекаем количество заказов из HTML
        with open(target_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
            # Ищем totalOrders в JavaScript
            import re
            match = re.search(r'totalOrders.*?(\d+[,\d]*)', html_content)
            total_orders = match.group(1) if match else 'N/A'

        return jsonify({
            'success': True,
            'message': 'Данные успешно обновлены',
            'timestamp': datetime.now().isoformat(),
            'stats': {
                'total_orders': total_orders
            }
        })

    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/health')
def health():
    """Проверка здоровья сервера."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'retailcrm': bool(os.getenv('RETAILCRM_API_KEY')),
            'moysklad': bool(os.getenv('MOYSKLAD_LOGIN') or os.getenv('MOYSKLAD_TOKEN')),
            'pyrus': bool(os.getenv('PYRUS_ACCESS_TOKEN'))
        }
    })


# ============================================================
# Mock данные для аналитики продаж
# ============================================================

def get_mock_current_month():
    """Mock данные для текущего месяца."""
    now = datetime.now()
    from_date = datetime(now.year, now.month, 1).strftime('%Y-%m-%d %H:%M:%S')
    return {
        'period': {
            'from': from_date,
            'to': now.strftime('%Y-%m-%d %H:%M:%S'),
            'label': f"1-{now.day} {now.strftime('%B %Y')}"
        },
        'salons': [
            {'salon': 'Фрунзе', 'orders_count': 156, 'shipment_sum': 487500, 'avg_check': 3125},
            {'salon': 'Советская', 'orders_count': 124, 'shipment_sum': 372000, 'avg_check': 3000},
            {'salon': 'Малая Земля', 'orders_count': 98, 'shipment_sum': 343000, 'avg_check': 3500},
            {'salon': 'Агрономическая', 'orders_count': 87, 'shipment_sum': 261000, 'avg_check': 3000},
            {'salon': 'Онлайн', 'orders_count': 143, 'shipment_sum': 429000, 'avg_check': 3000}
        ],
        'total': {
            'orders_count': 608,
            'shipment_sum': 1892500,
            'avg_check': 3112.5
        },
        'cached': False,
        'generated_at': now.isoformat()
    }

def get_mock_monthly_comparison():
    """Mock данные для месячного сравнения."""
    now = datetime.now()
    return {
        'year': now.year,
        'months': ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл'],
        'current_year': [1250000, 1180000, 1420000, 1650000, 1580000, 1720000, 1892500],
        'last_year': [980000, 920000, 1150000, 1280000, 1250000, 1380000, 1520000]
    }

def get_mock_compare_periods():
    """Mock данные для сравнения периодов."""
    return {
        'period1': {
            'from': '2026-07-01 00:00:00',
            'to': '2026-07-15 23:59:59',
            'orders_count': 312,
            'shipment_sum': 946250,
            'avg_check': 3033.0
        },
        'period2': {
            'from': '2026-06-01 00:00:00',
            'to': '2026-06-15 23:59:59',
            'orders_count': 287,
            'shipment_sum': 861000,
            'avg_check': 3000.0
        },
        'diff': {
            'orders_count': 25,
            'orders_count_percent': 8.7,
            'shipment_sum': 85250,
            'shipment_sum_percent': 9.9,
            'avg_check': 33.0,
            'avg_check_percent': 1.1
        }
    }


# ============================================================
# API эндпоинты аналитики продаж
# ============================================================

@app.route('/api/sales/current-month')
@require_session
def api_sales_current_month():
    """
    Получить статистику за текущий месяц.

    Query params:
        year (опционально): Год
        month (опционально): Месяц (1-12)

    Returns:
        JSON с данными по салонам за месяц
    """
    # Mock режим для тестирования фронтенда
    if SALES_MOCK_MODE:
        return jsonify(get_mock_current_month())

    try:
        exporter = get_sales_exporter()

        # Проверяем опциональные параметры
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)

        if year is not None and month is not None:
            # Запрашиваем конкретный месяц
            from_date = datetime(year, month, 1).strftime('%Y-%m-%d %H:%M:%S')

            if month == 12:
                to_date = datetime(year, 12, 31, 23, 59, 59).strftime('%Y-%m-%d %H:%M:%S')
            else:
                to_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
                to_date = to_date.strftime('%Y-%m-%d %H:%M:%S')

            # Выгружаем данные
            orders = exporter.fetch_orders(from_date, to_date)
            orders = exporter._filter_valid_orders(orders)
            salons = exporter.group_by_salon(orders)

            total = {
                'orders_count': sum(s['orders_count'] for s in salons),
                'shipment_sum': sum(s['shipment_sum'] for s in salons),
                'avg_check': 0
            }
            if total['orders_count'] > 0:
                total['avg_check'] = total['shipment_sum'] / total['orders_count']

            result = {
                'period': {
                    'from': from_date,
                    'to': to_date,
                    'label': f"{1}-{datetime(year, month, 1).day} {datetime(year, month, 1).strftime('%B %Y')}"
                },
                'salons': salons,
                'total': total,
                'cached': False,
                'generated_at': datetime.now().isoformat()
            }
        else:
            # Текущий месяц (использует кэш)
            result = exporter.get_current_month_stats()
            result['generated_at'] = datetime.now().isoformat()

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Неверные параметры: {str(e)}'}), 400
    except Exception as e:
        print(f'[ERROR] /api/sales/current-month: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/compare-periods')
@require_session
def api_sales_compare_periods():
    """
    Сравнить два периода.

    Query params:
        from: Начальная дата текущего периода (YYYY-MM-DD)
        to: Конечная дата текущего периода (YYYY-MM-DD)
        compare_from (опционально): Начальная дата для сравнения
        compare_to (опционально): Конечная дата для сравнения

    Returns:
        JSON с сравнением двух периодов
    """
    # Mock режим для тестирования фронтенда
    if SALES_MOCK_MODE:
        return jsonify(get_mock_compare_periods())

    try:
        from_date = request.args.get('from')
        to_date = request.args.get('to')

        if not from_date or not to_date:
            return jsonify({'error': 'Не указаны параметры from и to'}), 400

        # Конвертируем даты
        from_dt = datetime.strptime(from_date, '%Y-%m-%d')
        to_dt = datetime.strptime(to_date, '%Y-%m-%d')

        from_date_str = from_dt.strftime('%Y-%m-%d %H:%M:%S')
        to_date_str = (to_dt + timedelta(days=1) - timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')

        # Период для сравнения (по умолчанию прошлый год)
        compare_from = request.args.get('compare_from')
        compare_to = request.args.get('compare_to')

        if compare_from and compare_to:
            compare_from_dt = datetime.strptime(compare_from, '%Y-%m-%d')
            compare_to_dt = datetime.strptime(compare_to, '%Y-%m-%d')
            compare_from_str = compare_from_dt.strftime('%Y-%m-%d %H:%M:%S')
            compare_to_str = (compare_to_dt + timedelta(days=1) - timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
        else:
            # По умолчанию сравниваем с прошлым годом
            compare_from_dt = from_dt.replace(year=from_dt.year - 1)
            compare_to_dt = to_dt.replace(year=to_dt.year - 1)
            compare_from_str = compare_from_dt.strftime('%Y-%m-%d %H:%M:%S')
            compare_to_str = (compare_to_dt + timedelta(days=1) - timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')

        exporter = get_sales_exporter()
        result = exporter.compare_periods(
            from_date_str, to_date_str,
            compare_from_str, compare_to_str
        )

        result['generated_at'] = datetime.now().isoformat()

        return jsonify(result)

    except ValueError as e:
        return jsonify({'error': f'Неверный формат даты: {str(e)}'}), 400
    except Exception as e:
        print(f'[ERROR] /api/sales/compare-periods: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/monthly-comparison')
@require_session
def api_sales_monthly_comparison():
    """
    Получить данные по месяцам для сравнения с прошлым годом.

    Query params:
        year (опционально): Год (по умолчанию текущий)

    Returns:
        JSON с данными по месяцам
    """
    # Mock режим для тестирования фронтенда
    if SALES_MOCK_MODE:
        return jsonify(get_mock_monthly_comparison())

    try:
        year = request.args.get('year', type=int)

        exporter = get_sales_exporter()
        result = exporter.get_monthly_comparison(year)
        result['generated_at'] = datetime.now().isoformat()

        return jsonify(result)

    except Exception as e:
        print(f'[ERROR] /api/sales/monthly-comparison: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/cache/clear', methods=['POST'])
@require_session
def api_sales_cache_clear():
    """
    Очистить кэш аналитики продаж.

    Returns:
        JSON с подтверждением
    """
    try:
        exporter = get_sales_exporter()

        # Удаляем все файлы кэша
        import glob
        cache_files = glob.glob(str(exporter.cache_dir / '*.json'))
        deleted_count = 0

        for cache_file in cache_files:
            try:
                os.remove(cache_file)
                deleted_count += 1
            except:
                pass

        return jsonify({
            'success': True,
            'message': f'Удалено {deleted_count} файлов кэша',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f'[ERROR] /api/sales/cache/clear: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def main():
    """Запуск сервера."""
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    print(f"🌸 Запуск сервера отчетов Бархат на порту {port}")
    print(f"📊 Открой в браузере: http://localhost:{port}")

    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
