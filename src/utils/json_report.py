import json
from pathlib import Path


def save_json_report(results: list[dict], output_path: str, findings_only: bool = True) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    payload = []
    for res in results:
        assessment = res.get("document_assessment") or {}
        has_pd = assessment.get("has_personal_data")
        if has_pd is None:
            has_pd = bool(res.get("pd_categories")) or bool(res.get("has_pd"))
        if findings_only and not has_pd:
            continue
        payload.append(res)

    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_file)