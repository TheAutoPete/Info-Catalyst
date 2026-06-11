import importlib

from services import prompt_loader as _prompt_loader
from services.model_profiles import ModelProfile, get_analysis_mode


prompt_loader = importlib.reload(_prompt_loader)


BASE_LANGUAGE_REQUIREMENT = "Final output must be in Taiwan-style Traditional Chinese."

MODE_INSTRUCTIONS = {
    "Quick Summary": """# Quick Summary Report

## 核心摘要

## 5-8 個重點

## 重要名詞 / 公司 / 人物

## 一分鐘結論""",
    "Deep Analysis": """# Deep Analysis Report

## 核心論點

## 內容架構

## 關鍵主張

## 論證品質

## 可能盲點

## 反方觀點

## 值得追蹤的問題""",
    "Investment Lens": """# Investment Lens Report

## 投資摘要

## 核心 thesis

## 產業鏈位置

## 受益者 / 受害者

## 可投資標的 / 公司 / ticker if mentioned

## 估值與市場預期可能落差

## 催化劑

## 風險

## 反方論點

## 對 portfolio / watchlist 的啟示

## 接下來需要驗證的資料""",
    "Bias Check": """# Bias Check Report

## 主要偏誤

## 過度推論

## 缺乏證據的主張

## 敘事陷阱

## 利益衝突或立場偏誤

## 反方觀點

## 可信度評分

## 需要外部驗證的地方""",
    "Titan Input / Structured Research": """# Titan Input Report

## 情報摘要

## 可結構化 facts

## companies / tickers / sectors mentioned

## macro variables mentioned

## AI supply chain relevance

## key claims to verify

## possible watchlist impact

## suggested tags""",
}


def build_mode_report_prompt(
    transcript: str,
    source_url: str,
    *,
    analysis_mode: str,
    profile: ModelProfile,
) -> str:
    mode = get_analysis_mode(analysis_mode)
    return prompt_loader.format_prompt(
        prompt_loader.load_prompt("mode_report_prompt.md"),
        transcript=transcript,
        source_url=source_url,
        analysis_mode=mode.name,
        mode_purpose=mode.purpose,
        model=profile.model,
        reasoning_effort=profile.reasoning_effort,
        mode_instructions=MODE_INSTRUCTIONS[mode.name],
    )


def add_report_header(
    report: str,
    *,
    analysis_mode: str,
    model: str,
    reasoning_effort: str,
    override: bool,
) -> str:
    selection = "manual override" if override else "auto-selected"
    header = "\n".join(
        [
            "## Report Settings",
            "",
            f"- Analysis Mode: {analysis_mode}",
            f"- Model: {model}",
            f"- Reasoning Effort: {reasoning_effort}",
            f"- Model Selection: {selection}",
        ]
    )
    return f"{header}\n\n{report.strip()}"
