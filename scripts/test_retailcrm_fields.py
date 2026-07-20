#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Быстрый тестовый скрипт для исследования полей RetailCRM API.
Выгружает только 1 заказ для быстрого анализа структуры.
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def main():
    load_dotenv()

    api_url = os.getenv('RETAILCRM_API_URL')
    api_key = os.getenv('RETAILCRM_API_KEY')

    print("=" * 60)
    print("Исследование полей RetailCRM API (быстрый режим)")
    print("=" * 60)
    print(f"API URL: {api_url}")

    # Создаем session с отключением прокси
    session = requests.Session()
    session.trust_env = False

    headers = {'X-API-Key': api_key}

    # Выгружаем заказы за последние 30 дней (чтобы были данные)
    from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    to_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    params = {
        'limit': 20,  # RetailCRM требует 20, 50 или 100
        'fromDate': from_date,
        'toDate': to_date,
        'fields': 'id,number,status,sum,totalSum,createdAt,customer,paymentType,deliveryType,cost,orderMethod,customFields,store'
    }

    print(f"Запрос: {api_url}/api/v5/orders")
    print(f"  fromDate: {from_date}")
    print(f"  toDate: {to_date}")
    print()

    try:
        response = session.get(f"{api_url}/api/v5/orders", headers=headers, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if not data.get('success'):
            print(f"Ошибка API: {data.get('errorMsg', 'Unknown error')}")
            return 1

        orders = data.get('orders', [])
        if not orders:
            print("Заказы не найдены")
            return 0

        order = orders[0]
        print(f"✅ Получен заказ #{order.get('number')}")

        # Сохраняем полную структуру
        output_file = 'data/mock/retailcrm_order_sample.json'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(order, f, ensure_ascii=False, indent=2)
        print(f"💾 Структура сохранена в: {output_file}")

        # Ключевые поля
        print()
        print("=" * 60)
        print("Ключевые поля:")
        print("=" * 60)

        # Магазин
        print("\n[Магазин]")
        store = order.get('store')
        if store:
            if isinstance(store, dict):
                print(f"  order.store.code = {store.get('code')}")
                print(f"  order.store.name = {store.get('name')}")
            else:
                print(f"  order.store = {store}")
        else:
            print("  Поле 'store' отсутствует")
            # Проверяем customFields
            custom = order.get('customFields', {})
            if custom:
                print(f"  customFields доступен: {list(custom.keys())[:5]}")

        # Сумма
        print("\n[Сумма]")
        print(f"  order.sum = {order.get('sum')}")
        print(f"  order.totalSum = {order.get('totalSum')}")

        # Дата
        print("\n[Дата]")
        print(f"  order.createdAt = {order.get('createdAt')}")

        # Статус
        print("\n[Статус]")
        status = order.get('status')
        if isinstance(status, dict):
            print(f"  order.status.code = {status.get('code')}")
            print(f"  order.status.name = {status.get('name')}")
        else:
            print(f"  order.status = {status}")

        # Типы оплаты и доставки
        print("\n[Тип оплаты]")
        payment = order.get('paymentType')
        if isinstance(payment, dict):
            print(f"  order.paymentType.code = {payment.get('code')}")
            print(f"  order.paymentType.name = {payment.get('name')}")

        print("\n[Тип доставки]")
        delivery = order.get('deliveryType')
        if isinstance(delivery, dict):
            print(f"  order.deliveryType.code = {delivery.get('code')}")
            print(f"  order.deliveryType.name = {delivery.get('name')}")

        print()
        print("=" * 60)
        print("✅ Анализ завершен!")
        print("=" * 60)

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"Response text: {e.response.text}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
