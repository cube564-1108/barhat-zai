#!/usr/bin/env python3
"""
Выгрузка заказов из RetailCRM для сверки с МойСклад.
"""

import os
import sys
import ssl
import urllib3
import logging
from datetime import datetime
from typing import List, Dict, Any
import json
from urllib.parse import quote, urlparse
from dotenv import load_dotenv

# Пробуем импортировать requests для fallback
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Настраиваем логирование в stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Отключаем предупреждения SSL (для self-signed certificates)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RetailCRMExporter:
    """Экспортер заказов из RetailCRM."""

    def __init__(self):
        """Инициализация с загрузкой переменных окружения."""
        load_dotenv()

        self.api_url = os.getenv('RETAILCRM_API_URL')
        self.api_key = os.getenv('RETAILCRM_API_KEY')

        # Извлекаем hostname для SNI и Host header
        parsed_url = urlparse(self.api_url)
        self.api_hostname = parsed_url.netloc  # barhatretailcrm.retailcrm.ru

        # Логируем для отладки (без ключа!)
        logger.info(f"RetailCRM URL: {self.api_url}")
        logger.info(f"API Key: {'***SET***' if self.api_key else 'NOT SET'}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"urllib3 version: {urllib3.__version__}")

        if not self.api_url or not self.api_key:
            raise ValueError("RETAILCRM_API_URL и RETAILCRM_API_KEY должны быть указаны в .env")

        # Создаём максимально permissive SSL context
        # Это необходимо для соединения с RetailCRM при проблемах с сертификатом
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # Разрешаем соединение с legacy серверами
        try:
            self.ssl_context.options |= ssl.OP_LEGACY_SERVER_CONNECT
        except Exception:
            pass

        # Устанавливаем минимальный уровень безопасности для совместимости
        try:
            self.ssl_context.set_ciphers('DEFAULT:@SECLEVEL=0')
        except Exception:
            pass  # Игнорируем если не поддерживается
        try:
            self.ssl_context.set_ciphers('HIGH:!DH:!3DES')
        except Exception:
            pass

        # Разрешаем все поддерживаемые TLS версии
        try:
            self.ssl_context.minimum_version = ssl.TLSVersion.TLSv1
        except Exception:
            pass
        try:
            self.ssl_context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
        except Exception:
            pass

        # Дополнительные опции для совместимости
        try:
            self.ssl_context.options &= ~ssl.OP_NO_SSLv2
            self.ssl_context.options &= ~ssl.OP_NO_SSLv3
            self.ssl_context.options &= ~ssl.OP_NO_TLSv1
            self.ssl_context.options &= ~ssl.OP_NO_TLSv1_1
        except Exception:
            pass

        # Выбираем метод запроса: requests предпочтительнее
        self.use_requests = REQUESTS_AVAILABLE

        if self.use_requests:
            logger.info("Using requests library for API calls")
            # Создаём Session с правильным SSL context для SNI
            self.requests_session = requests.Session()
            self.requests_session.verify = False
            # Используем наш SSL context через urllib3 HTTPAdapter
            try:
                from requests.adapters import HTTPAdapter
                # Создаём urllib3 pool manager с нашим SSL context
                self.pool_manager = urllib3.PoolManager(
                    ssl_context=self.ssl_context,
                    timeout=urllib3.Timeout(connect=10, read=30),
                    retries=urllib3.Retry(total=3, backoff_factor=0.5)
                )
                # Создаём adapter с нашим pool manager
                class SNIAdapter(HTTPAdapter):
                    def __init__(self, pool_manager, *args, **kwargs):
                        self._pool_manager = pool_manager
                        super().__init__(*args, **kwargs)

                    def init_poolmanager(self, connections, maxsize, block=False):
                        return self._pool_manager

                self.requests_session.mount('https://', SNIAdapter(self.pool_manager))
                logger.info("Configured requests Session with custom SSL context")
            except Exception as e:
                logger.warning(f"Failed to configure custom SSL adapter: {e}")
                logger.info("Falling back to default requests with verify=False")
        else:
            logger.info("Using urllib3 for API calls")

        # Создаём HTTP connection pool для urllib3 fallback
        # Пробуем разные варианты инициализации для совместимости
        try:
            # Вариант 1: с ssl_context (новые версии urllib3)
            self.http = urllib3.PoolManager(
                ssl_context=self.ssl_context,
                timeout=urllib3.Timeout(connect=10, read=30),
                retries=urllib3.Retry(total=3, backoff_factor=0.5)
            )
        except TypeError:
            # Вариант 2: с cert_reqs и assert_hostname (старые версии)
            try:
                self.http = urllib3.PoolManager(
                    cert_reqs='CERT_NONE',
                    assert_hostname=False,
                    timeout=urllib3.Timeout(connect=10, read=30),
                    retries=urllib3.Retry(total=3, backoff_factor=0.5)
                )
            except Exception:
                # Вариант 3: самый простой fallback
                self.http = urllib3.PoolManager(
                    timeout=urllib3.Timeout(connect=10, read=30),
                    retries=urllib3.Retry(total=3, backoff_factor=0.5)
                )

        self.headers = {
            'X-API-Key': self.api_key
        }

        # Выбираем метод запроса: requests предпочтительнее
        self.use_requests = REQUESTS_AVAILABLE
        if self.use_requests:
            logger.info("Using requests library for API calls")
        else:
            logger.info("Using urllib3 for API calls")

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
                url += f"&fromDate={quote(from_date)}"
            if to_date:
                url += f"&toDate={quote(to_date)}"
            url += "&fields=id,number,status,sum,totalSum,createdAt,updatedAt,customer,paymentType,deliveryType,cost"

            logger.info(f"Fetching URL: {url}")

            try:
                if self.use_requests:
                    # Используем requests Session с custom SSL context для SNI
                    logger.info("Using requests library with custom SSL...")
                    headers_with_host = {**self.headers, 'Host': self.api_hostname}
                    response = self.requests_session.get(
                        url,
                        headers=headers_with_host,
                        timeout=30
                    )
                    logger.info(f"Got response: status={response.status_code}")

                    if response.status_code != 200:
                        print(f"Ошибка HTTP: {response.status_code}")
                        if response.status_code >= 500:
                            break
                        elif response.status_code == 401:
                            print("Ошибка авторизации - проверьте API ключ")
                            break
                        elif response.status_code == 403:
                            print("Ошибка доступа - нет прав на ресурс")
                            break
                        continue

                    data = response.json()

                else:
                    # Fallback на urllib3
                    logger.info("Using urllib3...")
                    response = self.http.request(
                        'GET',
                        url,
                        headers=self.headers,
                        retries=False
                    )
                    logger.info(f"Got response: status={response.status}")

                    if response.status != 200:
                        print(f"Ошибка HTTP: {response.status}")
                        if response.status >= 500:
                            break
                        elif response.status == 401:
                            print("Ошибка авторизации - проверьте API ключ")
                            break
                        elif response.status == 403:
                            print("Ошибка доступа - нет прав на ресурс")
                            break
                        continue

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
                logger.error(f"HTTPError: {type(e).__name__}: {e}")
                break
            except urllib3.exceptions.SSLError as e:
                logger.error(f"SSLError: {type(e).__name__}: {e}")
                logger.error("Это может быть связано с проблемами сертификата RetailCRM")
                import traceback
                traceback.print_exc()
                break
            except requests.exceptions.SSLError as e:
                logger.error(f"Requests SSLError: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                break
            except Exception as e:
                logger.error(f"Unexpected error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
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
