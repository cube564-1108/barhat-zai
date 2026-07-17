#!/usr/bin/env python3
"""
Выгрузка заказов из RetailCRM для сверки с МойСклад.
"""

import os
import ssl
import urllib3
from datetime import datetime
from typing import List, Dict, Any
import json
from dotenv import load_dotenv

# Отключаем предупреждения SSL (для self-signed certificates)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RetailCRMExporter:
    """Экспортер заказов из RetailCRM."""

    def __init__(self):
        """Инициализация с загрузкой переменных окружения."""
        load_dotenv()

        self.api_url = os.getenv('RETAILCRM_API_URL')
        self.api_key = os.getenv('RETAILCRM_API_KEY')

        if not self.api_url or not self.api_key:
            raise ValueError("RETAILCRM_API_URL и RETAILCRM_API_KEY должны быть указаны в .env")

        # Создаём PoolManager с кастомным SSL контекстом
        # Используем urllib3 напрямую для лучшего контроля SSL
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Создаём HTTP connection pool без SSL проверки
        self.http = urllib3.PoolManager(
            cert_reqs='CERT_NONE',
            assert_hostname=False,
            timeout=urllib3.Timeout(connect=10, read=30),
            retries=urllib3.Retry(total=3, backoff_factor=0.5)
        )

        self.headers = {
            'X-API-Key': self.api_key
        }

    def fetch_orders(self, from_date: str, to_date: str = None) -> List[Dict[str, Any]]:
        """
        Выгрузить заказы за период.

        Args:
            from_date: Начальная дата в формате 'YYYY-MM-DD HH:MM:SS'
            to_date: Конечная дата в формате 'YYYY-MM-DD HH:MM:SS' (опционально)

        Returns:
            Список заказов с основными полями
        """
        all_orders = []
        limit = 50  # Максимально допустимый лимит для RetailCRM
        offset = 0

        print(f"Начинаем выгрузку заказов с {from_date}")
        if to_date:
            print(f"по {to_date}")

        while True:
            # Формируем URL с параметрами (из-за особенностей RetailCRM API)
            url = f"{self.api_url}/api/v5/orders?limit={limit}&offset={offset}"
            if from_date:
                url += f"&fromDate={from_date}"
            if to_date:
                url += f"&toDate={to_date}"
            url += "&fields=id,number,status,sum,totalSum,createdAt,updatedAt,customer,paymentType,deliveryType,cost"

            try:
                # Используем urllib3 вместо requests
                response = self.http.request(
                    'GET',
                    url,
                    headers=self.headers
                )

                if response.status != 200:
                    print(f"Ошибка HTTP: {response.status}")
                    if response.status >= 500:
                        # Server error - продолжаем пытаться
                        break
                    elif response.status == 401:
                        print("Ошибка авторизации - проверьте API ключ")
                        break
                    continue

                # Парсим JSON ответ
                import json
                data = json.loads(response.data.decode('utf-8'))

                if not data.get('success'):
                    error_msg = data.get('errorMsg', 'Unknown error')
                    print(f"Ошибка API: {error_msg}")
                    break

                orders = data.get('orders', [])
                if not orders:
                    break

                all_orders.extend(orders)

                # Показываем прогресс
                total_count = data.get('pagination', {}).get('totalCount', 0)
                print(f"Загружено: {len(all_orders)} из {total_count}")

                # Проверяем, есть ли еще страницы
                if len(orders) < limit:
                    break

                offset += limit

            except urllib3.exceptions.HTTPError as e:
                print(f"Ошибка при запросе: {e}")
                break
            except Exception as e:
                print(f"Неожиданная ошибка: {e}")
                break

        print(f"Всего загружено заказов: {len(all_orders)}")
        return all_orders

    def normalize_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализовать заказ к унифицированному формату.

        Args:
            order: Сырой заказ из RetailCRM

        Returns:
            Нормализованный заказ
        """
        customer = order.get('customer', {})
        customer_name = customer.get('firstName', '') + ' ' + customer.get('lastName', '')
        customer_name = customer_name.strip() or customer.get('nickname', 'Неизвестно')

        # Обработка статуса (может быть объектом или строкой)
        status = order.get('status', {})
        if isinstance(status, str):
            status_code = status
            status_name = status
        else:
            status_code = status.get('code', 'unknown')
            status_name = status.get('name', 'Неизвестно')

        # Обработка paymentType и deliveryType (аналогично)
        payment_type = order.get('paymentType', {})
        if isinstance(payment_type, str):
            payment_type_name = payment_type
        else:
            payment_type_name = payment_type.get('name', '')

        delivery_type = order.get('deliveryType', {})
        if isinstance(delivery_type, str):
            delivery_type_name = delivery_type
        else:
            delivery_type_name = delivery_type.get('name', '')

        return {
            'id': str(order.get('id', '')),
            'number': order.get('number', ''),
            'status': status_code,
            'status_name': status_name,
            'sum': float(order.get('summ', 0) or 0),
            'total_sum': float(order.get('totalSumm', 0) or 0),
            'created_at': order.get('createdAt', ''),
            'updated_at': order.get('updatedAt', ''),
            'customer_id': str(customer.get('id', '')),
            'customer_name': customer_name,
            'customer_phone': customer.get('phone', '') or customer.get('contacts', [{}])[0].get('value', '') if customer.get('contacts') else '',
            'payment_type': payment_type_name,
            'delivery_type': delivery_type_name,
            'source': 'retailcrm'
        }

    def export_to_file(self, orders: List[Dict[str, Any]], filename: str = 'retailcrm_orders.json'):
        """
        Сохранить заказы в JSON файл.

        Args:
            orders: Список заказов
            filename: Имя файла для сохранения
        """
        normalized_orders = [self.normalize_order(order) for order in orders]

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(normalized_orders, f, ensure_ascii=False, indent=2)

        print(f"Сохранено {len(normalized_orders)} заказов в {filename}")
        return normalized_orders


def main():
    """Главная функция для тестирования."""
    import argparse

    parser = argparse.ArgumentParser(description='Выгрузка заказов из RetailCRM')
    parser.add_argument('--from', dest='from_date', required=True, help='Начальная дата (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--to', dest='to_date', help='Конечная дата (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--output', default='retailcrm_orders.json', help='Имя выходного файла')

    args = parser.parse_args()

    try:
        exporter = RetailCRMExporter()
        orders = exporter.fetch_orders(args.from_date, args.to_date)
        exporter.export_to_file(orders, args.output)
        print(f"✅ Выгрузка завершена! Заказы сохранены в {args.output}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
