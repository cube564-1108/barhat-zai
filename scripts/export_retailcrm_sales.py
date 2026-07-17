#!/usr/bin/env python3
"""
Аналитика продаж из RetailCRM.
Группировка продаж по салонам с кэшированием.

Наследуется от RetailCRMExporter и добавляет:
- Фильтрацию по статусам (исключает cancel-other)
- Группировку по салонам
- Кэширование результатов
- Сравнение периодов
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

# Добавляем parent директорию в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_retailcrm import RetailCRMExporter


class SalesAnalyticsExporter(RetailCRMExporter):
    """Экспортер аналитики продаж по салонам."""

    def __init__(self):
        """Инициализация с загрузкой конфигов."""
        super().__init__()
        self.salons_map = {}
        self.excluded_statuses = []
        self.field_names = {}
        self.cache_config = {}

        # Paths
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = self.base_dir / 'data' / 'config'
        self.cache_dir = self.base_dir / 'data' / 'cache'

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._load_config()

    def _load_config(self) -> None:
        """Загрузка всех конфигурационных файлов."""
        # Load salons mapping
        salons_path = self.config_dir / 'salons.json'
        if salons_path.exists():
            with open(salons_path, 'r', encoding='utf-8') as f:
                salons_config = json.load(f)
                self.salons_map = {
                    salon['retailcrm_id']: salon
                    for salon in salons_config['salons']
                }

        # Load excluded statuses
        statuses_path = self.config_dir / 'statuses.json'
        if statuses_path.exists():
            with open(statuses_path, 'r', encoding='utf-8') as f:
                statuses_config = json.load(f)
                self.excluded_statuses = statuses_config.get('excluded_statuses', [])

        # Load field names
        fields_path = self.config_dir / 'fields.json'
        if fields_path.exists():
            with open(fields_path, 'r', encoding='utf-8') as f:
                self.field_names = json.load(f)

        # Load cache config
        cache_path = self.config_dir / 'cache.json'
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                self.cache_config = json.load(f)

        print(f"[OK] Загружен маппинг для {len(self.salons_map)} салонов")
        print(f"[FILTER] Исключаемые статусы: {self.excluded_statuses}")

    def _filter_valid_orders(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Исключить заказы с исключаемыми статусами.

        Args:
            orders: Список заказов из RetailCRM

        Returns:
            Отфильтрованный список заказов
        """
        valid_orders = []

        for order in orders:
            status = self._extract_order_status(order)
            if status not in self.excluded_statuses:
                valid_orders.append(order)

        excluded_count = len(orders) - len(valid_orders)
        if excluded_count > 0:
            print(f"[FILTER] Исключено {excluded_count} заказов со статусами {self.excluded_statuses}")

        return valid_orders

    def _extract_order_status(self, order: Dict[str, Any]) -> str:
        """
        Извлечь код статуса заказа.

        Args:
            order: Заказ из RetailCRM

        Returns:
            Код статуса
        """
        status = order.get('status', {})
        if isinstance(status, str):
            return status
        return status.get('code', 'unknown') if isinstance(status, dict) else 'unknown'

    def _extract_salon_name(self, order: Dict[str, Any]) -> Optional[str]:
        """
        Извлечь название салона из заказа.

        Args:
            order: Заказ из RetailCRM

        Returns:
            Название салона или None
        """
        # shipmentStore may be an object or a string
        shipment_store = order.get('shipmentStore', '')

        if isinstance(shipment_store, dict):
            store_code = shipment_store.get('code', '')
        else:
            store_code = str(shipment_store) if shipment_store else ''

        if not store_code:
            return None

        salon_info = self.salons_map.get(store_code)
        if salon_info:
            return salon_info['name']

        return None

    def _extract_order_sum(self, order: Dict[str, Any]) -> float:
        """
        Извлечь сумму заказа.

        Args:
            order: Заказ из RetailCRM

        Returns:
            Сумма заказа (float)
        """
        # Try 'summ' first, then 'totalSumm' as fallback
        summ = order.get('summ') or order.get('totalSumm') or 0
        return float(summ) if summ else 0.0

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Проверить данные на корректность.

        Args:
            data: Данные для проверки

        Returns:
            True если данные корректны
        """
        if not data.get('salons'):
            raise ValueError("Нет данных по салонам")

        total = data.get('total', {})
        if total.get('orders_count', 0) == 0:
            raise ValueError("Нет заказов за выбранный период")

        return True

    def _fetch_orders_for_period(self, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """
        Получить заказы за период с фильтрацией.

        Args:
            from_date: Начальная дата
            to_date: Конечная дата

        Returns:
            Отфильтрованный список заказов
        """
        orders = self.fetch_orders(from_date, to_date)
        return self._filter_valid_orders(orders)

    def group_by_salon(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Сгруппировать заказы по салонам.

        Args:
            orders: Список заказов

        Returns:
            Словарь с данными по салонам
        """
        salon_stats = {}

        for order in orders:
            salon_name = self._extract_salon_name(order)
            if not salon_name:
                continue

            if salon_name not in salon_stats:
                salon_stats[salon_name] = {
                    'name': salon_name,
                    'orders_count': 0,
                    'shipment_sum': 0.0
                }

            salon_stats[salon_name]['orders_count'] += 1
            salon_stats[salon_name]['shipment_sum'] += self._extract_order_sum(order)

        # Calculate average check and convert to list
        result = []
        for stats in salon_stats.values():
            stats['avg_check'] = stats['shipment_sum'] / stats['orders_count'] if stats['orders_count'] > 0 else 0
            result.append(stats)

        # Sort by shipment sum descending
        result.sort(key=lambda x: x['shipment_sum'], reverse=True)

        return result

    def get_current_month_stats(self) -> Dict[str, Any]:
        """
        Получить статистику за текущий месяц.

        Returns:
            Данные по продажам за текущий месяц
        """
        now = datetime.now()
        from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        to_date = now.strftime('%Y-%m-%d %H:%M:%S')

        # Check cache
        cache_key = f'current_month_{now.year}_{now.month}'
        cached = self._load_cache(cache_key)
        if cached is not None:
            print(f"[CACHE] Используем кэш: {cache_key}")
            return cached

        print(f"[DATA] Загружаем данные за текущий месяц: {from_date} - {to_date}")

        orders = self._fetch_orders_for_period(from_date, to_date)
        salons = self.group_by_salon(orders)

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
                'type': 'current_month'
            },
            'salons': salons,
            'total': total,
            'cached': False
        }

        self._validate_data(result)
        self._save_cache(result, cache_key)

        return result

    def compare_periods(
        self,
        from_date: str,
        to_date: str,
        compare_from_date: Optional[str] = None,
        compare_to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Сравнить два периода.

        Args:
            from_date: Начало текущего периода
            to_date: Конец текущего периода
            compare_from_date: Начало периода для сравнения (опционально)
            compare_to_date: Конец периода для сравнения (опционально)

        Returns:
            Сравнение двух периодов
        """
        # Check cache
        cache_key = f'compare_{from_date}_{to_date}'
        if compare_from_date:
            cache_key += f'_vs_{compare_from_date}_{compare_to_date}'

        cached = self._load_cache(cache_key)
        if cached is not None:
            print(f"[CACHE] Используем кэш: {cache_key}")
            return cached

        print(f"[DATA] Сравниваем периоды: {from_date} - {to_date}")

        # Current period
        orders_current = self._fetch_orders_for_period(from_date, to_date)
        salons_current = self.group_by_salon(orders_current)

        total_current = {
            'orders_count': sum(s['orders_count'] for s in salons_current),
            'shipment_sum': sum(s['shipment_sum'] for s in salons_current),
            'avg_check': 0
        }
        if total_current['orders_count'] > 0:
            total_current['avg_check'] = total_current['shipment_sum'] / total_current['orders_count']

        # Compare period (if provided)
        salons_compare = []
        total_compare = {'orders_count': 0, 'shipment_sum': 0, 'avg_check': 0}

        if compare_from_date:
            print(f"  с периодом: {compare_from_date} - {compare_to_date}")
            orders_compare = self._fetch_orders_for_period(compare_from_date, compare_to_date)
            salons_compare = self.group_by_salon(orders_compare)

            total_compare = {
                'orders_count': sum(s['orders_count'] for s in salons_compare),
                'shipment_sum': sum(s['shipment_sum'] for s in salons_compare),
                'avg_check': 0
            }
            if total_compare['orders_count'] > 0:
                total_compare['avg_check'] = total_compare['shipment_sum'] / total_compare['orders_count']

        # Calculate changes
        def calc_change(current, compare):
            if not compare or compare == 0:
                return None
            return ((current - compare) / compare) * 100

        changes = {
            'orders_count': calc_change(total_current['orders_count'], total_compare['orders_count']),
            'shipment_sum': calc_change(total_current['shipment_sum'], total_compare['shipment_sum']),
            'avg_check': calc_change(total_current['avg_check'], total_compare['avg_check'])
        }

        result = {
            'period_current': {
                'from': from_date,
                'to': to_date,
                'salons': salons_current,
                'total': total_current
            },
            'period_compare': {
                'from': compare_from_date or '',
                'to': compare_to_date or '',
                'salons': salons_compare,
                'total': total_compare
            },
            'changes': changes,
            'cached': False
        }

        self._save_cache(result, cache_key)

        return result

    def get_monthly_comparison(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Получить данные по месяцам для сравнения.

        Args:
            year: Год (по умолчанию текущий)

        Returns:
            Данные по месяцам
        """
        if year is None:
            year = datetime.now().year

        # Check cache
        cache_key = f'monthly_{year}'
        cached = self._load_cache(cache_key)
        if cached is not None:
            print(f"[CACHE] Используем кэш: {cache_key}")
            return cached

        print(f"[DATA] Загружаем данные по месяцам за {year} год")

        months = []
        now = datetime.now()

        for month in range(1, 13):
            # Skip future months
            if year == now.year and month > now.month:
                continue

            # First and last day of month
            from_date = datetime(year, month, 1).strftime('%Y-%m-%d %H:%M:%S')

            if month == 12:
                to_date = datetime(year, 12, 31, 23, 59, 59).strftime('%Y-%m-%d %H:%M:%S')
            else:
                to_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
                to_date = to_date.strftime('%Y-%m-%d %H:%M:%S')

            # Get data for month
            orders = self._fetch_orders_for_period(from_date, to_date)
            salons = self.group_by_salon(orders)

            total = {
                'orders_count': sum(s['orders_count'] for s in salons),
                'shipment_sum': sum(s['shipment_sum'] for s in salons),
                'avg_check': 0
            }
            if total['orders_count'] > 0:
                total['avg_check'] = total['shipment_sum'] / total['orders_count']

            months.append({
                'month': month,
                'month_name': datetime(year, month, 1).strftime('%B'),
                'from_date': from_date,
                'to_date': to_date,
                'salons': salons,
                'total': total
            })

        result = {
            'year': year,
            'months': months,
            'cached': False
        }

        self._save_cache(result, cache_key)

        return result

    def _save_cache(self, data: Dict[str, Any], key: str) -> None:
        """
        Сохранить данные в кэш.

        Args:
            data: Данные для сохранения
            key: Ключ кэша
        """
        if not self.cache_config.get('enabled', True):
            return

        cache_file = self.cache_dir / f'{key}.json'

        cache_entry = {
            'data': data,
            'cached_at': datetime.now().isoformat(),
            'ttl': self.cache_config.get('ttl_seconds', 3600)
        }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_entry, f, ensure_ascii=False, indent=2)

        print(f"[CACHE] Сохранено в кэш: {key}")

    def _load_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Загрузить данные из кэша.

        Args:
            key: Ключ кэша

        Returns:
            Данные из кэша или None
        """
        if not self.cache_config.get('enabled', True):
            return None

        cache_file = self.cache_dir / f'{key}.json'

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_entry = json.load(f)

            # Check TTL
            cached_at = datetime.fromisoformat(cache_entry['cached_at'])
            ttl_seconds = cache_entry.get('ttl', self.cache_config.get('ttl_seconds', 3600))

            if datetime.now() - cached_at > timedelta(seconds=ttl_seconds):
                print(f"⏰ Кэш устарел: {key}")
                return None

            # Update cached flag
            if isinstance(cache_entry['data'], dict):
                cache_entry['data']['cached'] = True

            return cache_entry['data']

        except Exception as e:
            print(f"⚠️ Ошибка загрузки кэша {key}: {e}")
            return None


def main():
    """Главная функция для тестирования."""
    import argparse

    parser = argparse.ArgumentParser(description='Аналитика продаж из RetailCRM')
    parser.add_argument('--mode', choices=['current', 'compare', 'monthly'],
                       default='current', help='Режим работы')
    parser.add_argument('--from', dest='from_date', help='Начальная дата (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--to', dest='to_date', help='Конечная дата (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--compare-from', dest='compare_from',
                       help='Начальная дата для сравнения (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--compare-to', dest='compare_to',
                       help='Конечная дата для сравнения (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--year', type=int, help='Год для месячного отчета')
    parser.add_argument('--output', help='Сохранить результат в файл')

    args = parser.parse_args()

    try:
        exporter = SalesAnalyticsExporter()

        if args.mode == 'current':
            result = exporter.get_current_month_stats()
            print(f"\n[STAT] Статистика за текущий месяц:")
            print(f"Всего заказов: {result['total']['orders_count']}")
            print(f"Сумма продаж: {result['total']['shipment_sum']:,.2f} ₽")
            print(f"Средний чек: {result['total']['avg_check']:,.2f} ₽")
            print(f"\nПо салонам:")
            for salon in result['salons'][:5]:  # Top 5
                print(f"  {salon['name']}: {salon['orders_count']} заказов, "
                      f"{salon['shipment_sum']:,.2f} ₽, ср.чек {salon['avg_check']:,.2f} ₽")

        elif args.mode == 'compare':
            if not args.from_date or not args.to_date:
                print("[ERROR] Для режима compare нужны параметры --from и --to")
                return 1

            result = exporter.compare_periods(
                args.from_date, args.to_date,
                args.compare_from, args.compare_to
            )

            print(f"\n[STAT] Сравнение периодов:")
            curr = result['period_current']['total']
            comp = result['period_compare']['total']
            chg = result['changes']

            print(f"\nТекущий период:")
            print(f"  Заказов: {curr['orders_count']}, Сумма: {curr['shipment_sum']:,.2f} ₽")
            print(f"\nПериод сравнения:")
            print(f"  Заказов: {comp['orders_count']}, Сумма: {comp['shipment_sum']:,.2f} ₽")
            print(f"\nИзменения:")
            for key, value in chg.items():
                if value is not None:
                    print(f"  {key}: {value:+.1f}%")

        elif args.mode == 'monthly':
            result = exporter.get_monthly_comparison(args.year)
            print(f"\n[STAT] Данные по месяцам за {result['year']}:")
            for month in result['months']:
                print(f"\n{month['month_name']}:")
                print(f"  Заказов: {month['total']['orders_count']}, "
                      f"Сумма: {month['total']['shipment_sum']:,.2f} ₽, "
                      f"Ср.чек: {month['total']['avg_check']:,.2f} ₽")

        # Save to file if requested
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n[SAVE] Результат сохранен в {args.output}")

        print("\n[OK] Готово!")
        return 0

    except Exception as e:
        print(f"[ERROR] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
