#!/usr/bin/env python3
"""
Анализ экономической эффективности ночных смен в круглосуточных салонах.

Выгружает заказы за период и анализирует:
- Выручку днем (9:00-21:00) и ночью (21:00-9:00)
- Средний чек по времени суток
- Количество заказов
- Долю ночных продаж от общей
"""

import os
import sys
import io
import json
from datetime import datetime, time
from typing import List, Dict, Any, Optional
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Добавляем parent директорию в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export_retailcrm import RetailCRMExporter


class NightShiftAnalyzer:
    """Анализатор эффективности ночных смен."""

    # Круглосуточные салоны (ID из salons.json)
    NIGHT_SALONS = {
        'barkhat-ekb': 'ЕКБ Бажова 89',
        'barkhat-tomsk': 'Томск Дальне-Ключевская 16а',
        'cheliabinsk-tsvillinga-59': 'Челябинск Цвиллинга 59'
    }

    # Временные границы
    DAY_START = time(9, 0)   # 9:00
    NIGHT_START = time(21, 0)  # 21:00

    def __init__(self):
        """Инициализация анализатора."""
        self.exporter = RetailCRMExporter()
        self.salons_map = {}

        # Загружаем конфигурацию салонов
        config_path = Path(__file__).parent.parent / 'data' / 'config' / 'salons.json'
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                salons_config = json.load(f)
                self.salons_map = {
                    salon['retailcrm_id']: salon
                    for salon in salons_config['salons']
                }

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Парсить дату-время из строки RetailCRM."""
        if not dt_str:
            return None
        try:
            # RetailCRM возвращает в формате ISO 8601
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None

    def _is_night_order(self, created_at: str) -> bool:
        """
        Определить, является ли заказ ночным.

        Ночные часы: 21:00 - 09:00
        Дневные часы: 09:00 - 21:00

        Args:
            created_at: Строка с датой создания заказа

        Returns:
            True если заказ создан ночью
        """
        dt = self._parse_datetime(created_at)
        if not dt:
            return False

        order_time = dt.time()

        # Ночь: время >= 21:00 ИЛИ время < 9:00
        return order_time >= self.NIGHT_START or order_time < self.DAY_START

    def _get_period_of_day(self, created_at: str) -> str:
        """Получить период суток для заказа."""
        if self._is_night_order(created_at):
            return 'night'
        return 'day'

    def _extract_salon_info(self, order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Извлечь информацию о салоне из заказа.

        Args:
            order: Заказ из RetailCRM

        Returns:
            Информация о салоне или None
        """
        shipment_store = order.get('shipmentStore', '')

        if isinstance(shipment_store, dict):
            store_code = shipment_store.get('code', '')
        else:
            store_code = str(shipment_store) if shipment_store else ''

        if not store_code:
            return None

        salon_info = self.salons_map.get(store_code)
        if salon_info:
            return {
                'id': store_code,
                'name': salon_info['name'],
                'city': salon_info['city'],
                'is_night_salon': store_code in self.NIGHT_SALONS
            }

        return None

    def _extract_order_sum(self, order: Dict[str, Any]) -> float:
        """Извлечь сумму заказа."""
        summ = order.get('summ') or order.get('totalSumm') or 0
        return float(summ) if summ else 0.0

    def analyze_period(
        self,
        from_date: str,
        to_date: str,
        night_only: bool = False
    ) -> Dict[str, Any]:
        """
        Проанализировать эффективность ночных смен за период.

        Args:
            from_date: Начальная дата (YYYY-MM-DD HH:MM:SS)
            to_date: Конечная дата (YYYY-MM-DD HH:MM:SS)
            night_only: Только круглосуточные салоны

        Returns:
            Словарь с результатами анализа
        """
        print(f"[ANALYSIS] Загрузка данных за период: {from_date} - {to_date}")

        # Выгружаем заказы
        orders = self.exporter.fetch_orders(from_date, to_date)

        # Фильтруем по салонам если нужно
        if night_only:
            orders = [
                order for order in orders
                if self._extract_salon_info(order) and
                   self._extract_salon_info(order)['is_night_salon']
            ]
            print(f"[FILTER] Только круглосуточные салоны: {len(orders)} заказов")

        # Анализируем по времени суток
        result = {
            'period': {'from': from_date, 'to': to_date},
            'night_only': night_only,
            'summary': {
                'day': {'orders': 0, 'revenue': 0.0, 'avg_check': 0.0},
                'night': {'orders': 0, 'revenue': 0.0, 'avg_check': 0.0}
            },
            'by_salon': [],
            'hourly_distribution': {str(h): 0 for h in range(24)}
        }

        salon_stats = {}

        for order in orders:
            salon_info = self._extract_salon_info(order)
            if not salon_info:
                continue

            period = self._get_period_of_day(order.get('createdAt', ''))
            order_sum = self._extract_order_sum(order)

            # Парсим время для почасовой статистики
            dt = self._parse_datetime(order.get('createdAt', ''))
            if dt:
                hour = dt.hour
                result['hourly_distribution'][str(hour)] = (
                    result['hourly_distribution'].get(str(hour), 0) + order_sum
                )

            # Инициализируем статистику по салону
            salon_key = salon_info['name']
            if salon_key not in salon_stats:
                salon_stats[salon_key] = {
                    'name': salon_key,
                    'city': salon_info['city'],
                    'is_night_salon': salon_info['is_night_salon'],
                    'day': {'orders': 0, 'revenue': 0.0, 'avg_check': 0.0},
                    'night': {'orders': 0, 'revenue': 0.0, 'avg_check': 0.0}
                }

            # Добавляем в статистику
            result['summary'][period]['orders'] += 1
            result['summary'][period]['revenue'] += order_sum

            salon_stats[salon_key][period]['orders'] += 1
            salon_stats[salon_key][period]['revenue'] += order_sum

        # Вычисляем средние чеки
        for period in ['day', 'night']:
            if result['summary'][period]['orders'] > 0:
                result['summary'][period]['avg_check'] = (
                    result['summary'][period]['revenue'] /
                    result['summary'][period]['orders']
                )

        # Вычисляем средние чеки по салонам
        for salon_data in salon_stats.values():
            for period in ['day', 'night']:
                if salon_data[period]['orders'] > 0:
                    salon_data[period]['avg_check'] = (
                        salon_data[period]['revenue'] /
                        salon_data[period]['orders']
                    )
            result['by_salon'].append(salon_data)

        # Сортируем салоны по ночной выручке
        result['by_salon'].sort(
            key=lambda x: x['night']['revenue'],
            reverse=True
        )

        return result

    def print_report(self, analysis: Dict[str, Any]) -> None:
        """Вывести красивый отчет на консоль."""
        print("\n" + "=" * 70)
        print("АНАЛИЗ ЭФФЕКТИВНОСТИ НОЧНЫХ СМЕН")
        print("=" * 70)

        period = analysis['period']
        print(f"\nПериод: {period['from']} - {period['to']}")

        if analysis['night_only']:
            print("Фильтр: только круглосуточные салоны")

        print("\n" + "-" * 70)
        print("СВОДНАЯ СТАТИСТИКА")
        print("-" * 70)

        summary = analysis['summary']

        print(f"\n{'Показатель':<30} {'День (9-21)':>20} {'Ночь (21-9)':>20}")
        print("-" * 70)

        print(f"{'Заказы, шт.':<30} {summary['day']['orders']:>20} {summary['night']['orders']:>20}")
        print(f"{'Выручка, руб.':<30} {summary['day']['revenue']:>20,.2f} {summary['night']['revenue']:>20,.2f}")
        print(f"{'Средний чек, руб.':<30} {summary['day']['avg_check']:>20,.2f} {summary['night']['avg_check']:>20,.2f}")

        total_orders = summary['day']['orders'] + summary['night']['orders']
        total_revenue = summary['day']['revenue'] + summary['night']['revenue']

        if total_orders > 0:
            night_share = summary['night']['orders'] / total_orders * 100
            night_revenue_share = summary['night']['revenue'] / total_revenue * 100

            print("\n" + "-" * 70)
            print("ДОЛЯ НОЧНЫХ ПОКАЗАТЕЛЕЙ")
            print("-" * 70)
            print(f"Доля ночных заказов: {night_share:.1f}%")
            print(f"Доля ночной выручки: {night_revenue_share:.1f}%")

        # Проверка эффективности
        print("\n" + "-" * 70)
        print("ЭФФЕКТИВНОСТЬ")
        print("-" * 70)

        if summary['night']['orders'] > 0:
            check_ratio = summary['night']['avg_check'] / summary['day']['avg_check'] if summary['day']['avg_check'] > 0 else 0
            print(f"Ночной чек vs Дневной: {check_ratio:.2%} ", end="")

            if check_ratio >= 1:
                print("[+] (ночной чек выше)")
            elif check_ratio >= 0.9:
                print("[~] (ночной чек чуть ниже)")
            else:
                print("[-] (ночной чек значительно ниже)")

            # Оценка окупаемости (условная)
            # Если ночные продажи составляют >15% от дневных - считается эффективным
            if night_revenue_share >= 15:
                print(f"Ночные продажи: {night_revenue_share:.1f}% от дневных [+]")
            elif night_revenue_share >= 8:
                print(f"Ночные продажи: {night_revenue_share:.1f}% от дневных [~]")
            else:
                print(f"Ночные продажи: {night_revenue_share:.1f}% от дневных [-]")
        else:
            print("Нет ночных заказов за период")

        print("\n" + "-" * 70)
        print("СТАТИСТИКА ПО САЛОНАМ")
        print("-" * 70)

        for salon in analysis['by_salon']:
            if salon['night']['orders'] == 0:
                continue

            print(f"\n[*] {salon['name']} ({salon['city']})")
            print(f"  {'День:':<10} {salon['day']['orders']:>4} заказов, "
                  f"{salon['day']['revenue']:>12,.2f} руб., "
                  f"ср.чек {salon['day']['avg_check']:>8,.2f} руб.")
            print(f"  {'Ночь:':<10} {salon['night']['orders']:>4} заказов, "
                  f"{salon['night']['revenue']:>12,.2f} руб., "
                  f"ср.чек {salon['night']['avg_check']:>8,.2f} руб.")

            salon_total = salon['day']['orders'] + salon['night']['orders']
            if salon_total > 0:
                night_pct = salon['night']['orders'] / salon_total * 100
                print(f"  Доля ночи: {night_pct:.1f}%")

        # Почасовое распределение
        print("\n" + "-" * 70)
        print("РАСПРЕДЕЛЕНИЕ ВЫРУЧКИ ПО ЧАСАМ")
        print("-" * 70)

        hourly = analysis['hourly_distribution']
        total_hourly = sum(hourly.values())

        if total_hourly > 0:
            for hour in range(24):
                revenue = hourly.get(str(hour), 0)
                pct = revenue / total_hourly * 100
                bar = "#" * int(pct / 2)
                period = "[N]" if hour >= 21 or hour < 9 else "[D]"
                print(f"{hour:02d}:00 {period} {revenue:>12,.2f} руб. ({pct:5.1f}%) {bar}")

        print("\n" + "=" * 70)


def main():
    """Главная функция."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Анализ эффективности ночных смен'
    )
    parser.add_argument(
        '--from',
        dest='from_date',
        required=True,
        help='Начальная дата (YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--to',
        dest='to_date',
        required=True,
        help='Конечная дата (YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--night-only',
        action='store_true',
        help='Только круглосуточные салоны'
    )
    parser.add_argument(
        '--output',
        help='Сохранить результат в JSON файл'
    )

    args = parser.parse_args()

    try:
        analyzer = NightShiftAnalyzer()
        analysis = analyzer.analyze_period(
            args.from_date,
            args.to_date,
            night_only=args.night_only
        )

        analyzer.print_report(analysis)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            print(f"\n[SAVE] Результат сохранен в: {args.output}")

    except Exception as e:
        print(f"\n[-] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
