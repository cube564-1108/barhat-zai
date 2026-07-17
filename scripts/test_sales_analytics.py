#!/usr/bin/env python3
"""
Unit tests для SalesAnalyticsExporter.
Тестирует логику без обращения к API.
"""

import sys
from datetime import datetime

# Mock orders для тестирования
MOCK_ORDERS = [
    {
        'id': 1,
        'status': 'complete',
        'summ': 5000,
        'totalSumm': 5000,
        'createdAt': '2026-07-01 10:00:00',
        'shipmentStore': {
            'code': 'barkhat-ekb',
            'name': 'ЕКБ Бажова 89'
        }
    },
    {
        'id': 2,
        'status': 'complete',
        'summ': 3000,
        'totalSumm': 3000,
        'createdAt': '2026-07-02 11:00:00',
        'shipmentStore': {
            'code': 'barkhat-nsk-levyi',
            'name': 'НСК Блюхера 61'
        }
    },
    {
        'id': 3,
        'status': 'cancel-other',  # Должен быть исключён
        'summ': 2000,
        'totalSumm': 2000,
        'createdAt': '2026-07-03 12:00:00',
        'shipmentStore': {
            'code': 'barkhat-tomsk',
            'name': 'Томск Дальне-Ключевская 16а'
        }
    },
    {
        'id': 4,
        'status': 'new',
        'summ': 7000,
        'totalSumm': 7000,
        'createdAt': '2026-07-04 13:00:00',
        'shipmentStore': 'barkhat-nsk-levyi'  # Строка вместо объекта (НСК)
    },
    {
        'id': 5,
        'status': 'complete',
        'summ': 0,  # Нулевая сумма
        'totalSumm': 0,
        'createdAt': '2026-07-05 14:00:00',
        'shipmentStore': {
            'code': 'barkhat-nsk-levyi',
            'name': 'НСК Блюхера 61'
        }
    },
    {
        'id': 6,
        'status': 'complete',
        'summ': 4000,
        'totalSumm': 4000,
        'createdAt': '2026-07-06 15:00:00',
        'shipmentStore': {
            'code': 'unknown-store',  # Неизвестный магазин
            'name': 'Неизвестный'
        }
    }
]


def test_config_loading():
    """Тест загрузки конфигов."""
    print("\n=== TEST: Config Loading ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()

    # Проверка маппинга салонов
    assert len(exporter.salons_map) > 0, "Салоны не загружены"
    print(f"[OK] Загружено {len(exporter.salons_map)} салонов")

    # Проверка исключаемых статусов
    assert 'cancel-other' in exporter.excluded_statuses, "cancel-other не в исключаемых"
    print(f"[OK] Исключаемые статусы: {exporter.excluded_statuses}")

    # Проверка названий полей
    assert 'shipmentStore' in exporter.field_names.values(), "shipmentStore не в полях"
    print(f"[OK] Поля: {exporter.field_names}")

    return True


def test_filter_valid_orders():
    """Тест фильтрации заказов."""
    print("\n=== TEST: Filter Valid Orders ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()
    valid_orders = exporter._filter_valid_orders(MOCK_ORDERS)

    # Должны исключить заказ с cancel-other
    assert len(valid_orders) == 5, f"Ожидается 5 валидных заказов, получено {len(valid_orders)}"
    print(f"[OK] Отфильтровано: {len(valid_orders)} из {len(MOCK_ORDERS)} заказов")

    # Проверяем что cancel-other исключён
    statuses = [exporter._extract_order_status(o) for o in valid_orders]
    assert 'cancel-other' not in statuses, "cancel-other не исключён"
    print(f"[OK] Статусы валидных заказов: {set(statuses)}")

    return True


def test_extract_salon_name():
    """Тест извлечения названия салона."""
    print("\n=== TEST: Extract Salon Name ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()

    # Объект shipmentStore
    salon1 = exporter._extract_salon_name(MOCK_ORDERS[0])
    assert salon1 == "ЕКБ Бажова 89", f"Ожидается 'ЕКБ Бажова 89', получено '{salon1}'"
    print(f"[OK] Из объекта: {salon1}")

    # Строка shipmentStore
    salon2 = exporter._extract_salon_name(MOCK_ORDERS[3])
    assert salon2 == "НСК Блюхера 61", f"Ожидается 'НСК Блюхера 61', получено '{salon2}'"
    print(f"[OK] Из строки: {salon2}")

    # Неизвестный магазин
    salon3 = exporter._extract_salon_name(MOCK_ORDERS[5])
    assert salon3 is None, f"Ожидается None для неизвестного магазина"
    print(f"[OK] Неизвестный магазин: {salon3}")

    return True


def test_extract_order_sum():
    """Тест извлечения суммы заказа."""
    print("\n=== TEST: Extract Order Sum ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()

    sum1 = exporter._extract_order_sum(MOCK_ORDERS[0])
    assert sum1 == 5000.0, f"Ожидается 5000.0, получено {sum1}"
    print(f"[OK] Сумма заказа 1: {sum1}")

    sum2 = exporter._extract_order_sum(MOCK_ORDERS[4])
    assert sum2 == 0.0, f"Ожидается 0.0, получено {sum2}"
    print(f"[OK] Нулевая сумма: {sum2}")

    return True


def test_group_by_salon():
    """Тест группировки по салонам."""
    print("\n=== TEST: Group By Salon ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()
    valid_orders = exporter._filter_valid_orders(MOCK_ORDERS)
    grouped = exporter.group_by_salon(valid_orders)

    print(f"[OK] Сгруппировано {len(grouped)} салонов")

    # Проверка ЕКБ
    ekb = next((s for s in grouped if s['name'] == 'ЕКБ Бажова 89'), None)
    assert ekb is not None, "ЕКБ не найден"
    assert ekb['orders_count'] == 1, f"Ожидается 1 заказ для ЕКБ, получено {ekb['orders_count']}"
    assert ekb['shipment_sum'] == 5000.0, f"Ожидается 5000.0 для ЕКБ, получено {ekb['shipment_sum']}"
    assert ekb['avg_check'] == 5000.0, f"Ожидается avg_check 5000.0, получено {ekb['avg_check']}"
    print(f"[OK] ЕКБ: {ekb['orders_count']} заказов, сумма {ekb['shipment_sum']}, ср.чек {ekb['avg_check']}")

    # Проверка НСК
    nsk = next((s for s in grouped if s['name'] == 'НСК Блюхера 61'), None)
    assert nsk is not None, "НСК не найден"
    assert nsk['orders_count'] == 3, f"Ожидается 3 заказа для НСК, получено {nsk['orders_count']}"
    assert nsk['shipment_sum'] == 10000.0, f"Ожидается 10000.0 для НСК, получено {nsk['shipment_sum']}"
    print(f"[OK] НСК: {nsk['orders_count']} заказов, сумма {nsk['shipment_sum']}, ср.чек {nsk['avg_check']}")

    # Проверка сортировки
    for i in range(len(grouped) - 1):
        assert grouped[i]['shipment_sum'] >= grouped[i+1]['shipment_sum'], "Не отсортировано по убыванию"
    print(f"[OK] Сортировка по убыванию суммы")

    return True


def test_validate_data():
    """Тест группировки по салонам."""
    print("\n=== TEST: Group By Salon ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()
    valid_orders = exporter._filter_valid_orders(MOCK_ORDERS)
    grouped = exporter.group_by_salon(valid_orders)

    print(f"[OK] Сгруппировано {len(grouped)} салонов")

    # Проверка ЕКБ
    ekb = next((s for s in grouped if s['name'] == 'ЕКБ Бажова 89'), None)
    assert ekb is not None, "ЕКБ не найден"
    assert ekb['orders_count'] == 2, f"Ожидается 2 заказа для ЕКБ, получено {ekb['orders_count']}"
    assert ekb['shipment_sum'] == 12000.0, f"Ожидается 12000.0 для ЕКБ, получено {ekb['shipment_sum']}"
    assert ekb['avg_check'] == 6000.0, f"Ожидается avg_check 6000.0, получено {ekb['avg_check']}"
    print(f"[OK] ЕКБ: {ekb['orders_count']} заказов, сумма {ekb['shipment_sum']}, ср.чек {ekb['avg_check']}")

    # Проверка НСК
    nsk = next((s for s in grouped if s['name'] == 'НСК Блюхера 61'), None)
    assert nsk is not None, "НСК не найден"
    assert nsk['orders_count'] == 2, f"Ожидается 2 заказа для НСК, получено {nsk['orders_count']}"
    assert nsk['shipment_sum'] == 3000.0, f"Ожидается 3000.0 для НСК (без нулевого заказа), получено {nsk['shipment_sum']}"
    print(f"[OK] НСК: {nsk['orders_count']} заказов, сумма {nsk['shipment_sum']}, ср.чек {nsk['avg_check']}")

    # Проверка сортировки
    for i in range(len(grouped) - 1):
        assert grouped[i]['shipment_sum'] >= grouped[i+1]['shipment_sum'], "Не отсортировано по убыванию"
    print(f"[OK] Сортировка по убыванию суммы")

    return True


def test_validate_data():
    """Тест валидации данных."""
    print("\n=== TEST: Validate Data ===")

    from export_retailcrm_sales import SalesAnalyticsExporter

    exporter = SalesAnalyticsExporter()

    # Валидные данные
    valid_data = {
        'salons': [{'name': 'Test', 'orders_count': 10, 'shipment_sum': 50000}],
        'total': {'orders_count': 10, 'shipment_sum': 50000}
    }
    assert exporter._validate_data(valid_data), "Валидные данные не прошли проверку"
    print("[OK] Валидные данные прошли проверку")

    # Пустые салоны
    empty_salons = {'salons': [], 'total': {'orders_count': 0, 'shipment_sum': 0}}
    try:
        exporter._validate_data(empty_salons)
        assert False, "Должна была быть ошибка для пустых салонов"
    except ValueError:
        print("[OK] Пустые салоны отклонены")

    # Нулевые заказы
    zero_orders = {
        'salons': [{'name': 'Test', 'orders_count': 0, 'shipment_sum': 0}],
        'total': {'orders_count': 0, 'shipment_sum': 0}
    }
    try:
        exporter._validate_data(zero_orders)
        assert False, "Должна была быть ошибка для нулевых заказов"
    except ValueError:
        print("[OK] Нулевые заказы отклонены")

    return True


def main():
    """Запуск всех тестов."""
    print("=" * 50)
    print("UNIT TESTS: SalesAnalyticsExporter")
    print("=" * 50)

    tests = [
        test_config_loading,
        test_filter_valid_orders,
        test_extract_salon_name,
        test_extract_order_sum,
        test_group_by_salon,
        test_validate_data
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 50)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 50)

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    exit(main())
