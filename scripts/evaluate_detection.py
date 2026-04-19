#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate scanner JSON report")
    parser.add_argument("report", type=Path, help="Path to JSON report")
    args = parser.parse_args()

    payload = json.loads(args.report.read_text(encoding="utf-8"))
    total = len(payload)
    flagged = [x for x in payload if (x.get("document_assessment") or {}).get("has_personal_data")]

    by_format = Counter(Path(item.get("path", "")).suffix.lower() for item in flagged)
    by_category = Counter()
    by_reason = Counter()
    for item in flagged:
        assessment = item.get("document_assessment") or {}
        for cat in assessment.get("detected_categories", []):
            by_category[cat] += 1
        by_reason[assessment.get("short_reason", "") or "n/a"] += 1

    print(f"total_files={total}")
    print(f"flagged_files={len(flagged)}")
    print("flagged_by_format=", dict(by_format))
    print("flagged_by_category=", dict(by_category))
    print("top_reason_codes=", dict(by_reason.most_common(10)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())