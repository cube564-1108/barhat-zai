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

load_dotenv()

# Конфигурация
SSO_SECRET = os.environ.get("BARKHAT_SSO_SECRET", "")
SSO_ENABLED = bool(SSO_SECRET)

if not SSO_ENABLED:
    print("⚠️  WARNING: BARKHAT_SSO_SECRET not set — SSO disabled, running in open mode")
    print("⚠️  Set BARKHAT_SSO_SECRET environment variable to enable authentication")

SESSION_SECRET = os.environ.get("SESSION_SECRET", os.urandom(32).hex())

app = Flask(__name__, static_folder='.')
CORS(app)

# Сериализатор для сессий (itsdangerous)
session_serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="barkhat-quality-session")


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


def main():
    """Запуск сервера."""
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'

    print(f"🌸 Запуск сервера отчетов Бархат на порту {port}")
    print(f"📊 Открой в браузере: http://localhost:{port}")

    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
