import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import BASE_DIR
from services.output_languages import get_output_language


CONTEXT_DIR = BASE_DIR / "reports" / "context"

FOLLOW_UP_QUESTIONS_BY_LANGUAGE = {
    "zh-TW": (
        "這份報告中最重要的三個結論是什麼？",
        "哪些內容是逐字稿中的直接主張，哪些是報告的解讀？",
        "有哪些公司、產品、產業或 ticker 值得後續追蹤？",
        "有哪些關鍵主張需要用外部資料再驗證？",
        "如果我要更新 watchlist，這份報告提示了哪些可能影響？",
        "報告中有哪些不確定性、偏誤或缺漏脈絡？",
        "請把這份報告整理成一頁投資或研究備忘錄。",
        "請列出可以繼續追問原始逐字稿的五個問題。",
        "哪些內容適合轉成標籤、主題或資料庫欄位？",
        "請用保守、中性、進取三種情境重述可能影響。",
    ),
    "en": (
        "What are the three most important conclusions in this report?",
        "Which points are direct transcript claims, and which are interpretation?",
        "Which companies, products, sectors, or tickers should be tracked next?",
        "Which key claims need external verification?",
        "What possible watchlist implications does this report suggest?",
        "What uncertainties, biases, or missing context appear in the report?",
        "Turn this report into a one-page investment or research memo.",
        "List five useful follow-up questions for the original transcript.",
        "Which points could become tags, topics, or database fields?",
        "Restate the potential impact in conservative, neutral, and aggressive scenarios.",
    ),
    "ja": (
        "このレポートで最も重要な結論を3つ挙げてください。",
        "どの内容が逐語録の直接的な主張で、どの内容が解釈ですか？",
        "今後追跡すべき企業、製品、セクター、ticker は何ですか？",
        "外部情報で追加検証すべき重要な主張は何ですか？",
        "このレポートは watchlist にどのような示唆を与えますか？",
        "レポート内の不確実性、偏り、または不足している文脈は何ですか？",
        "このレポートを1ページの投資または調査メモにまとめてください。",
        "元の逐語録について追加で尋ねるべき質問を5つ挙げてください。",
        "タグ、トピック、データベース項目に変換できる内容は何ですか？",
        "潜在的な影響を保守的、中立的、積極的の3つのシナリオで説明してください。",
    ),
}

EXTERNAL_AI_INSTRUCTIONS = {
    "zh-TW": (
        "請使用台灣慣用繁體中文回答。只能根據下方報告與逐字稿摘錄作答；"
        "不要捏造來源沒有支持的主張，並清楚區分逐字稿中的直接主張與你的解讀。"
    ),
    "en": (
        "Answer in clear professional English. Use only the report and transcript excerpt below; "
        "do not invent unsupported source claims, and clearly distinguish direct transcript claims from your interpretation."
    ),
    "ja": (
        "自然で専門的な日本語で回答してください。下記のレポートと逐語録抜粋のみを根拠にし、"
        "根拠のない主張を作らず、逐語録の直接的な主張とあなたの解釈を明確に区別してください。"
    ),
}


def build_context_pack(
    *,
    report_text: str,
    metadata: dict[str, Any],
    report_path: Path | None = None,
    transcript_excerpt: str = "",
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    language = get_output_language(metadata.get("output_language") or metadata.get("output_language_label"))
    report_path_text = str(report_path or metadata.get("report_file_path") or "")
    report_excerpt = report_text.strip()
    source_title = str(metadata.get("video_title") or "Untitled source")
    source_url = str(metadata.get("source_url") or "")
    analysis_mode = str(metadata.get("analysis_mode") or metadata.get("report_type") or "")
    model = str(metadata.get("selected_model") or _first_model(metadata.get("models")) or "")

    questions = FOLLOW_UP_QUESTIONS_BY_LANGUAGE.get(
        language.code,
        FOLLOW_UP_QUESTIONS_BY_LANGUAGE[get_output_language().code],
    )

    return "\n".join(
        [
            "# Report Q&A Context Pack",
            "",
            "## Source Metadata",
            "",
            f"- Source title: {source_title}",
            f"- Source URL: {source_url}",
            f"- Video ID: {metadata.get('video_id') or ''}",
            f"- Analysis mode: {analysis_mode}",
            f"- Report output language: {language.label}",
            f"- Model used for original report: {model}",
            f"- Generated timestamp: {generated_at.isoformat(timespec='seconds')}",
            f"- Transcript language: {metadata.get('transcript_language') or ''}",
            f"- Report file path: {report_path_text}",
            "",
            "## Instructions For External AI",
            "",
            EXTERNAL_AI_INSTRUCTIONS[language.code],
            "",
            "Use only the provided report and transcript excerpt. Do not invent source claims.",
            "Distinguish direct claims from the transcript from interpretation.",
            "",
            "## Core Topic",
            "",
            f"- {_infer_core_topic(report_excerpt, source_title)}",
            "",
            "## Original Report",
            "",
            report_excerpt,
            "",
            "## Transcript Excerpt",
            "",
            _format_transcript_excerpt(transcript_excerpt, language.code),
            "",
            "## Suggested Follow-up Questions",
            "",
            "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1)),
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


def _format_transcript_excerpt(transcript_excerpt: str, language_code: str) -> str:
    transcript_excerpt = transcript_excerpt.strip()
    if not transcript_excerpt:
        empty_messages = {
            "zh-TW": "此 Context Pack 沒有附上逐字稿摘錄；請主要依據原始報告作答。",
            "en": "No transcript excerpt is included in this Context Pack; answer primarily from the original report.",
            "ja": "この Context Pack には逐語録抜粋が含まれていません。主に元のレポートに基づいて回答してください。",
        }
        return empty_messages.get(language_code, empty_messages["zh-TW"])
    excerpt = transcript_excerpt[:2_000].strip()
    truncated_messages = {
        "zh-TW": "\n\n（逐字稿摘錄已截斷。）",
        "en": "\n\n(Transcript excerpt truncated.)",
        "ja": "\n\n（逐語録抜粋は途中で省略されています。）",
    }
    return excerpt + (truncated_messages.get(language_code, truncated_messages["zh-TW"]) if len(transcript_excerpt) > len(excerpt) else "")


def _infer_core_topic(report_text: str, source_title: str) -> str:
    if source_title and source_title != "Untitled source":
        return source_title
    for line in report_text.splitlines():
        cleaned = re.sub(r"^[#*\-\s]+", "", line).strip()
        if cleaned and len(cleaned) > 4:
            return cleaned[:120]
    return "Untitled source"


def _first_model(models: Any) -> str:
    if isinstance(models, dict) and models:
        return str(next(iter(models.values())))
    return ""
