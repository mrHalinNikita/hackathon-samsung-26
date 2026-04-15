import csv
from pathlib import Path

def save_csv_report(results: list[dict], output_path: str) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['path', 'categories_pd', 'count', 'uz_level', 'file_format'])

        for res in results:

            if not res.get('pd_categories'):
                continue

            path = res.get('path', '')
            file_format = Path(path).suffix.lstrip('.').upper() if Path(path).suffix else 'UNKNOWN'

            categories = res['pd_categories']
            cats_str = ', '.join(categories.keys())
            count = sum(categories.values())
            uz_level = res.get('protection_level', 'УЗ-4')

            writer.writerow([path, cats_str, count, uz_level, file_format])

    return str(output_file)