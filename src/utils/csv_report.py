import csv
from pathlib import Path


def save_csv_report(results: list[dict], output_path: str, findings_only: bool = True) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "file_path",
            "status",
            "has_personal_data",
            "overall_confidence",
            "overall_risk_score",
            "legal_buckets_present",
            "detected_categories",
            "short_reason",
            "hit_count",
            "strongest_category",
            "uz_level",
            "file_format",
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
            
            detected_categories = assessment.get("detected_categories")
            if detected_categories is None:
                detected_categories = list((res.get("pd_categories") or {}).keys())

            legal_buckets = assessment.get("legal_buckets_present", [])

            writer.writerow([
                path,
                res.get("status", "unknown"),
                has_pd,
                assessment.get("overall_confidence", "no_pd_or_weak"),
                assessment.get("overall_risk_score", 0),
                ", ".join(legal_buckets),
                ", ".join(detected_categories),
                assessment.get("short_reason", ""),
                assessment.get("hit_count", res.get("pd_entity_count", 0)),
                assessment.get("strongest_category", ""),
                res.get("protection_level", "УЗ-4"),
                file_format,
            ])

    return str(output_file)