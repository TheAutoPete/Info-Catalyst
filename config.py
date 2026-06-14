import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

PROMPTS_DIR = BASE_DIR / "prompts"
REPORTS_DIR = BASE_DIR / "reports" / "markdown"
REPORT_METADATA_DIR = BASE_DIR / "reports" / "metadata"
REPORT_CONTEXT_DIR = BASE_DIR / "reports" / "context"
TRANSCRIPTS_DIR = BASE_DIR / "reports" / "transcripts"
LOGS_DIR = BASE_DIR / "logs"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


OPENAI_USE_SYSTEM_PROXY = _env_flag("OPENAI_USE_SYSTEM_PROXY", False)
