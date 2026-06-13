from dataclasses import dataclass


@dataclass(frozen=True)
class OutputLanguage:
    label: str
    code: str
    slug: str
    prompt_instruction: str


TRADITIONAL_CHINESE = OutputLanguage(
    label="Traditional Chinese",
    code="zh-TW",
    slug="traditional-chinese",
    prompt_instruction=(
        "Final output must be in Taiwan-style Traditional Chinese.\n"
        "Convert Simplified Chinese terms to Traditional Chinese.\n"
        "Preserve company names, tickers, product names, technical terms, and proper nouns where appropriate.\n"
        "Do not output Simplified Chinese unless directly quoting source text.\n"
        "Render all report section headings and body text in Taiwan-style Traditional Chinese."
    ),
)

ENGLISH = OutputLanguage(
    label="English",
    code="en",
    slug="english",
    prompt_instruction=(
        "Final output must be in clear professional English.\n"
        "Preserve company names, tickers, product names, technical terms, and proper nouns.\n"
        "Do not use Chinese section headings unless directly quoting source text.\n"
        "Render all report section headings and body text in clear professional English."
    ),
)

JAPANESE = OutputLanguage(
    label="Japanese",
    code="ja",
    slug="japanese",
    prompt_instruction=(
        "Final output must be in natural professional Japanese.\n"
        "Preserve company names, tickers, product names, technical terms, and proper nouns where appropriate.\n"
        "Do not use Chinese section headings unless directly quoting source text.\n"
        "Render all report section headings and body text in natural professional Japanese."
    ),
)

OUTPUT_LANGUAGES = (TRADITIONAL_CHINESE, ENGLISH, JAPANESE)
DEFAULT_OUTPUT_LANGUAGE = TRADITIONAL_CHINESE.code
SHARED_EVIDENCE_RULES = (
    "Use only the transcript content.",
    "Do not invent source claims.",
    "Distinguish direct claims from the transcript from interpretation.",
)

_BY_CODE = {language.code: language for language in OUTPUT_LANGUAGES}
_BY_LABEL = {language.label: language for language in OUTPUT_LANGUAGES}
_BY_SLUG = {language.slug: language for language in OUTPUT_LANGUAGES}


def get_output_language(value: str | None = None) -> OutputLanguage:
    if not value:
        return _BY_CODE[DEFAULT_OUTPUT_LANGUAGE]
    return (
        _BY_CODE.get(value)
        or _BY_LABEL.get(value)
        or _BY_SLUG.get(value)
        or _BY_CODE[DEFAULT_OUTPUT_LANGUAGE]
    )


def get_output_language_labels() -> list[str]:
    return [language.label for language in OUTPUT_LANGUAGES]


def get_default_output_language() -> OutputLanguage:
    return get_output_language(DEFAULT_OUTPUT_LANGUAGE)
