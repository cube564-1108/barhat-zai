"""
Выгрузка данных из формы Pyrus "Анкета для бархат зай"
"""

import requests
import os
import csv
import json
from datetime import datetime

# Переменные окружения (загружаются из Amvera, не из .env)
TOKEN = os.getenv('PYRUS_ACCESS_TOKEN')
LOGIN = os.getenv('PYRUS_LOGIN')
FORM_ID = 1327961

# Директория для выгрузки данных
DATA_DIR = os.getenv('DATA_DIR', '/app/data')

# Авторизация
def auth():
    session = requests.Session()
    session.trust_env = False

    response = session.post(
        'https://api.pyrus.com/v4/auth',
        headers={'Content-Type': 'application/json'},
        json={'login': LOGIN, 'security_key': TOKEN}
    )

    if response.status_code != 200:
        raise Exception(f"Auth failed: {response.text}")

    access_token = response.json()['access_token']
    return session, access_token

# Получение структуры формы
def get_form_structure(session, access_token, form_id):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    response = session.get(f'https://api.pyrus.com/v4/forms/{form_id}', headers=headers)
    response.raise_for_status()
    return response.json()

# Получение всех заявок с пагинацией
def get_all_submissions(session, access_token, form_id):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    all_tasks = []
    page = 0
    next_page_token = None

    while True:
        params = {}
        if next_page_token:
            params['next_page_token'] = next_page_token

        # Добавляем фильтр для получения всех задач, включая завершённые
        params['include_archived'] = 'true'

        response = session.get(
            f'https://api.pyrus.com/v4/forms/{form_id}/register',
            headers=headers,
            params=params
        )
        response.raise_for_status()

        data = response.json()
        tasks = data.get('tasks', [])
        all_tasks.extend(tasks)

        page += 1
        print(f"  Page {page}: {len(tasks)} tasks (total: {len(all_tasks)})")

        has_more = data.get('has_more', False)
        if not has_more:
            break

        next_page_token = data.get('next_page_token')

    return all_tasks

# Выгрузка в CSV
def export_to_csv(tasks, form_structure, output_file):
    # Создаём маппинг field_id -> название
    field_names = {f['id']: f['name'] for f in form_structure.get('fields', [])}

    # Собираем все уникальные field_id из задач
    all_field_ids = set()
    for task in tasks:
        for v in task.get('values', []):
            all_field_ids.add(v['field_id'])

    # Сортированные ID полей
    sorted_fields = sorted(all_field_ids)

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        # Заголовок
        header = ['Task_ID', 'Created_Date'] + [field_names.get(fid, f'Field_{fid}') for fid in sorted_fields]
        writer.writerow(header)

        # Данные
        for task in tasks:
            row = [
                task.get('id'),
                task.get('creation_date', '')
            ]

            # Создаём dict значений для быстрого доступа
            values_dict = {v['field_id']: v.get('value') for v in task.get('values', [])}

            # Добавляем значения полей в правильном порядке
            for field_id in sorted_fields:
                value = values_dict.get(field_id, '')

                # Обработка списков (multiple_choice)
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                # Обработка вложений (files)
                elif isinstance(value, dict) and 'id' in value:
                    value = f"[file: {value.get('name', value['id'])}]"

                row.append(str(value))

            writer.writerow(row)

    print(f"\n[OK] Exported {len(tasks)} submissions to {output_file}")

# Выгрузка в JSON
def export_to_json(tasks, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"[OK] Exported {len(tasks)} submissions to {output_file}")

# Главная функция
def main():
    print("=" * 60)
    print("Pyrus Form Export")
    print("=" * 60)

    # Auth
    print("\n[1/4] Authenticating...")
    session, access_token = auth()
    print("  [OK] Authenticated")

    # Get form structure
    print(f"\n[2/4] Getting form structure (ID: {FORM_ID})...")
    form_structure = get_form_structure(session, access_token, FORM_ID)
    print(f"  [OK] Form: {form_structure.get('name')}")
    print(f"  [OK] Fields: {len(form_structure.get('fields', []))}")

    # Get all submissions
    print(f"\n[3/4] Downloading submissions...")
    tasks = get_all_submissions(session, access_token, FORM_ID)
    print(f"  [OK] Total submissions: {len(tasks)}")

    # Export
    print(f"\n[4/4] Exporting...")

    # Создаём директорию для данных, если не существует
    os.makedirs(DATA_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    csv_file = os.path.join(DATA_DIR, f"pyrus_export_{FORM_ID}_{timestamp}.csv")
    json_file = os.path.join(DATA_DIR, f"pyrus_export_{FORM_ID}_{timestamp}.json")

    # Также сохраняем как "latest.csv" для удобства использования
    latest_csv = os.path.join(DATA_DIR, "latest.csv")

    export_to_csv(tasks, form_structure, csv_file)
    export_to_json(tasks, json_file)

    # Копируем в latest.csv
    import shutil
    shutil.copy(csv_file, latest_csv)
    print(f"[OK] Latest export saved to {latest_csv}")

    print("\n" + "=" * 60)
    print("[OK] Export complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()
