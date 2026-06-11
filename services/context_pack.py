import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import BASE_DIR


CONTEXT_DIR = BASE_DIR / "reports" / "context"
FOLLOW_UP_QUESTIONS = (
    "這份內容最值得驗證的三個關鍵假設是什麼？",
    "這個論點如果錯了，最可能錯在哪裡？",
    "有哪些公司或產業鏈環節可能受益？",
    "這份內容對我的 watchlist 有什麼啟示？",
    "請用更嚴格的投資委員會視角挑戰這份報告。",
    "哪些敘事可能過度樂觀或忽略反方證據？",
    "如果要做下一步研究，應該優先查哪些資料來源？",
    "請整理出可追蹤的催化因素、風險因素與驗證指標。",
    "這份報告中有哪些適合拆成獨立研究題目的段落？",
    "請把關鍵主張改寫成可驗證的研究假設。",
)


def build_context_pack(
    *,
    report_text: str,
    metadata: dict[str, Any],
    report_path: Path | None = None,
    transcript_excerpt: str = "",
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    report_path_text = str(report_path or metadata.get("report_file_path") or "")
    report_excerpt = report_text.strip()
    source_title = str(metadata.get("video_title") or "Untitled source")
    source_url = str(metadata.get("source_url") or "")
    analysis_mode = str(metadata.get("analysis_mode") or metadata.get("report_type") or "")
    model = str(metadata.get("selected_model") or _first_model(metadata.get("models")) or "")

    return "\n".join(
        [
            "# Report Q&A Context Pack",
            "",
            "## 來源資訊",
            "",
            f"- Source title: {source_title}",
            f"- Source URL: {source_url}",
            f"- Video ID: {metadata.get('video_id') or ''}",
            f"- Analysis mode: {analysis_mode}",
            f"- Model used for original report: {model}",
            f"- Generated timestamp: {generated_at.isoformat(timespec='seconds')}",
            f"- Transcript language: {metadata.get('transcript_language') or ''}",
            f"- Report file path: {report_path_text}",
            "",
            "## 給外部 AI 助理的使用指令",
            "",
            "你正在協助使用者根據以下 Info Catalyst 報告脈絡延伸分析。請使用台灣慣用繁體中文回答。"
            "請以提供的報告脈絡作為主要來源，不要捏造脈絡中不存在的來源主張。"
            "如果使用者詢問最新事實、價格、財報、法規或事件，請明確說明需要外部查證。",
            "",
            "輸出規則：使用台灣慣用繁體中文；保留公司名稱、ticker、產品名稱、技術術語與專有名詞；"
            "將簡體中文用語轉為繁體中文；除非引用原始來源文字，否則不要輸出簡體中文。",
            "",
            "## 精簡來源摘要",
            "",
            f"- 核心主題：{_infer_core_topic(report_excerpt, source_title)}",
            "- 主要論點：請根據下方完整報告整理，不要超出報告內容。",
            "- 關鍵主張：優先引用報告中的標題、條列與結論。",
            "- 重要證據或推理：只使用報告已提供的內容。",
            "- 重要公司 / ticker / 技術 / 人物：請從完整報告中擷取。",
            "- 主要風險、偏誤或反方觀點：請檢查報告中的風險、偏誤、待驗證與反論段落。",
            "- 投資或研究啟示：若報告有投資或研究含義，請以審慎語氣整理。",
            "- 驗證問題：優先找出報告明確標示需要查證或缺少上下文的地方。",
            "",
            "## 完整產出報告",
            "",
            report_excerpt,
            "",
            "## 逐字稿摘錄",
            "",
            _format_transcript_excerpt(transcript_excerpt),
            "",
            "## 建議延伸問題",
            "",
            "\n".join(f"{index}. {question}" for index, question in enumerate(FOLLOW_UP_QUESTIONS, start=1)),
            "",
        ]
    ).strip() + "\n"


def save_context_pack(
    *,
    report_text: str,
    metadata: dict[str, Any],
    report_path: Path,
    context_dir: Path = CONTEXT_DIR,
    transcript_excerpt: str = "",
) -> Path:
    context_dir.mkdir(parents=True, exist_ok=True)
    context_path = _context_path_for_report(report_path, context_dir)
    content = build_context_pack(
        report_text=report_text,
        metadata=metadata,
        report_path=report_path,
        transcript_excerpt=transcript_excerpt,
    )
    context_path.write_text(content, encoding="utf-8")
    return context_path


def read_metadata(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def context_pack_exists(metadata: dict[str, Any]) -> Path | None:
    path_text = metadata.get("context_pack_path")
    if not path_text:
        return None
    path = Path(path_text)
    return path if path.exists() else None


def _context_path_for_report(report_path: Path, context_dir: Path) -> Path:
    return context_dir / f"{report_path.stem}_context-pack.md"


def _format_transcript_excerpt(transcript_excerpt: str) -> str:
    transcript_excerpt = transcript_excerpt.strip()
    if not transcript_excerpt:
        return "本 Context Pack 預設不包含完整逐字稿。若需要逐字稿全文，請在未來版本另行匯出。"
    excerpt = transcript_excerpt[:2_000].strip()
    return excerpt + ("\n\n（以上為短摘錄，非完整逐字稿。）" if len(transcript_excerpt) > len(excerpt) else "")


def _infer_core_topic(report_text: str, source_title: str) -> str:
    if source_title and source_title != "Untitled source":
        return source_title
    for line in report_text.splitlines():
        cleaned = re.sub(r"^[#*\-\s]+", "", line).strip()
        if cleaned and len(cleaned) > 4:
            return cleaned[:120]
    return "請由完整報告判斷。"


def _first_model(models: Any) -> str:
    if isinstance(models, dict) and models:
        return str(next(iter(models.values())))
    return ""
