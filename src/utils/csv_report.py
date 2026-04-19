import csv
from pathlib import Path


def save_csv_report(results: list[dict], output_path: str, findings_only: bool = True) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "путь",
            "категории_пДн",
            "количество_находок",
            "УЗ",
            "формат_файла",
        ])

        for res in results:
            path = res.get("path", "")
            file_format = Path(path).suffix.lstrip(".").upper() if Path(path).suffix else "UNKNOWN"
            assessment = res.get("document_assessment") or {}

            has_pd = assessment.get("has_personal_data")
            if has_pd is None:
                has_pd = bool(res.get("pd_categories")) or bool(res.get("has_pd"))

            if findings_only and not has_pd:
                continue
            
            pd_categories = res.get("pd_categories") or {}
            if not pd_categories:
                detected_categories = assessment.get("detected_categories") or []
                pd_categories = {category: 0 for category in detected_categories}

            detected_categories = sorted(pd_categories.keys())
            counts_by_category = "; ".join(
                f"{category}={pd_categories[category]}" for category in detected_categories
            ) if detected_categories else "0"

            writer.writerow([
                path,
                ", ".join(detected_categories),
                counts_by_category,
                res.get("protection_level", "УЗ-4"),
                file_format,
            ])

    return str(output_file)