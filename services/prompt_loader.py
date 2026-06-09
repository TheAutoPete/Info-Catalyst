from pathlib import Path

from config import PROMPTS_DIR


def load_prompt(filename: str, prompts_dir: Path = PROMPTS_DIR) -> str:
    return (prompts_dir / filename).read_text(encoding="utf-8")


def format_prompt(template: str, *, transcript: str, source_url: str = "") -> str:
    return template.format(
        transcript=transcript.strip(),
        source_url=source_url.strip() or "Manual transcript input",
    )

