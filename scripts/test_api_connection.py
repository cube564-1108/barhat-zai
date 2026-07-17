#!/usr/bin/env python3
"""
Тестовый скрипт для проверки соединения с RetailCRM API.
Запускается локально с теми же переменными окружения, что и в Amvera.
"""

import os
import sys
import requests
import urllib3
from datetime import datetime, timedelta

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_retailcrm_connection():
    """Тестируем соединение с RetailCRM API."""

    # Получаем переменные окружения (должны быть в .env или установлены вручную)
    api_url = os.getenv('RETAILCRM_API_URL', 'https://barhat.retailcrm.ru')
    api_key = os.getenv('RETAILCRM_API_KEY')

    print(f"🔍 Тестирование соединения с RetailCRM")
    print(f"   URL: {api_url}")
    print(f"   Ключ: {'{' + api_key[:10] + '...' if api_key else 'НЕ УСТАНОВЛЕН'}'}")
    print()

    if not api_key:
        print("❌ ОШИБКА: RETAILCRM_API_KEY не установлен!")
        print("   Установите его в .env файл или:")
        print("   export RETAILCRM_API_KEY='your-key-here'")
        return False

    # Создаём сессию с отключённой проверкой SSL
    session = requests.Session()
    session.verify = False
    session.trust_env = False

    headers = {'X-API-Key': api_key}

    # Тест 1: Базовый ping-запрос
    print("📡 Тест 1: Пробный запрос на получение 1 заказа...")
    try:
        # Запрашиваем 1 заказ за сегодня
        today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        url = f"{api_url}/api/v5/orders?limit=1&fromDate={today}&fields=id"

        print(f"   URL: {url}")

        response = session.get(url, headers=headers, verify=False, timeout=30)

        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"   Response keys: {list(data.keys())}")
            if 'success' in data:
                print(f"   Success: {data['success']}")
            print("   ✅ Успешно!")
            return True
        elif response.status_code == 401:
            print("   ❌ Ошибка авторизации — неверный API ключ")
            return False
        elif response.status_code == 403:
            print("   ❌ Ошибка доступа — нет прав на этот ресурс")
            return False
        elif response.status_code == 404:
            print("   ❌ Не найдено — возможно неверный URL")
            return False
        else:
            print(f"   ❌ Неожиданный статус: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False

    except requests.exceptions.SSLError as e:
        print(f"   ❌ SSL Ошибка: {e}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"   ❌ Timeout: {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Ошибка соединения: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Неизвестная ошибка: {type(e).__name__}: {e}")
        return False


def test_with_different_urls():
    """Пробуем разные варианты URL."""
    api_key = os.getenv('RETAILCRM_API_KEY')
    if not api_key:
        print("❌ API ключ не установлен")
        return

    base_urls = [
        'https://barhat.retailcrm.ru',
        'https://barhat.retailcrm.ru/api',
        'http://barhat.retailcrm.ru',
    ]

    session = requests.Session()
    session.verify = False
    session.trust_env = False
    headers = {'X-API-Key': api_key}

    print("\n📡 Тест 2: Проба разных URL...")
    for base in base_urls:
        try:
            url = f"{base}/v5/orders?limit=1&fields=id"
            print(f"   Пробуем: {url}")
            response = session.get(url, headers=headers, verify=False, timeout=10)
            print(f"      → Status: {response.status_code}")
            if response.status_code == 200:
                print(f"      ✅ РАБОТАЕТ!")
                return base
        except Exception as e:
            print(f"      → Ошибка: {type(e).__name__}")

    return None


if __name__ == '__main__':
    print("=" * 60)
    print("Тестирование RetailCRM API соединения")
    print("=" * 60)
    print()

    success = test_retailcrm_connection()

    if not success:
        print("\n" + "=" * 60)
        working_url = test_with_different_urls()

        if working_url:
            print(f"\n💡 Найден рабочий URL: {working_url}")
            print("   Обновите RETAILCRM_API_URL в Amvera!")
        else:
            print("\n💡 Возможные проблемы:")
            print("   1. Неверный API ключ")
            print("   2. Неверный URL (barhat.retailcrm.ru)")
            print("   3. Блокировка по IP")
            print("   4. Проблемы с DNS/сетью")

    sys.exit(0 if success else 1)
