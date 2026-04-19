from pathlib import Path

from src.utils.csv_report import save_csv_report


def test_csv_report_full_inventory_mode(tmp_path: Path):
    results = [
        {
            "path": "/tmp/a.txt",
            "status": "success",
            "has_pd": False,
            "pd_categories": {},
            "protection_level": "УЗ-0",
            "document_assessment": {
                "has_personal_data": False,
                "overall_confidence": "no_pd_or_weak",
                "overall_risk_score": 0,
                "legal_buckets_present": [],
                "detected_categories": [],
                "short_reason": "нет",
                "hit_count": 0,
                "strongest_category": None,
            },
        },
        {
            "path": "/tmp/b.txt",
            "status": "success",
            "has_pd": True,
            "pd_categories": {"full_name": 1},
            "protection_level": "УЗ-3",
            "document_assessment": {
                "has_personal_data": True,
                "overall_confidence": "high",
                "overall_risk_score": 70,
                "legal_buckets_present": ["ordinary"],
                "detected_categories": ["BASIC_PERSONAL_DATA"],
                "short_reason": "ФИО + дата рождения",
                "hit_count": 3,
                "strongest_category": "BASIC_PERSONAL_DATA",
            },
        },
    ]

    output = save_csv_report(results, str(tmp_path / "report.csv"), findings_only=False)
    body = Path(output).read_text(encoding="utf-8")

    assert "путь,категории_пДн,количество_находок,УЗ,формат_файла" in body
    assert "/tmp/a.txt" in body
    assert "/tmp/b.txt" in body
    assert "full_name=1" in body


def test_csv_report_findings_only(tmp_path: Path):
    results = [{"path": "/tmp/empty.txt", "status": "success", "has_pd": False, "pd_categories": {}}]
    output = save_csv_report(results, str(tmp_path / "report.csv"), findings_only=True)
    lines = Path(output).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1  # only header