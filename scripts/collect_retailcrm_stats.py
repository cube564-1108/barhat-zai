#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для сбора всех уникальных статусов и магазинов из RetailCRM.
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from collections import Counter

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
    print("Сбор статусов и магазинов из RetailCRM")
    print("=" * 60)

    session = requests.Session()
    session.trust_env = False
    headers = {'X-API-Key': api_key}

    # Выгружаем за последние 60 дней
    from_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
    to_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    all_orders = []
    limit = 50
    offset = 0

    print(f"Период: {from_date} → {to_date}")
    print()

    while True:
        params = {
            'limit': limit,
            'offset': offset,
            'fromDate': from_date,
            'toDate': to_date,
            'fields': 'id,number,status,summ,totalSumm,createdAt,shipmentStore,customFields'
        }

        try:
            response = session.get(f"{api_url}/api/v5/orders", headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                print(f"Ошибка API: {data.get('errorMsg')}")
                break

            orders = data.get('orders', [])
            if not orders:
                break

            all_orders.extend(orders)
            print(f"Загружено: {len(all_orders)} заказов")

            if len(orders) < limit:
                break

            offset += limit

            # Ограничим для скорости
            if len(all_orders) >= 500:
                print("Достигнут лимит 500 заказов")
                break

        except Exception as e:
            print(f"Ошибка: {e}")
            break

    if not all_orders:
        print("Заказы не найдены")
        return 1

    # Анализируем статусы
    print()
    print("=" * 60)
    print("Статусы заказов:")
    print("=" * 60)

    status_counter = Counter()
    for order in all_orders:
        status = order.get('status', 'unknown')
        status_counter[status] += 1

    for status, count in status_counter.most_common():
        print(f"  {status}: {count} заказов")

    # Анализируем магазины
    print()
    print("=" * 60)
    print("Магазины (shipmentStore):")
    print("=" * 60)

    store_counter = Counter()
    for order in all_orders:
        store = order.get('shipmentStore', 'no-store')
        if store:
            store_counter[store] += 1

    for store, count in store_counter.most_common():
        print(f"  {store}: {count} заказов")

    # Сохраняем результаты
    result = {
        'statuses': dict(status_counter),
        'stores': dict(store_counter),
        'total_orders': len(all_orders),
        'from_date': from_date,
        'to_date': to_date
    }

    output_file = 'data/mock/retailcrm_stats.json'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        import json
        json.dump(result, f, ensure_ascii=False, indent=2)

    print()
    print(f"💾 Результаты сохранены в: {output_file}")
    print()
    print("=" * 60)
    print("✅ Анализ завершен!")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    exit(main())
