import re
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR


def save_report(report_type: str, content: str, source_label: str, reports_dir: Path = REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{_slugify(source_label)}-{_slugify(report_type)}.md"
    path = reports_dir / filename
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return slug[:80] or "report"

