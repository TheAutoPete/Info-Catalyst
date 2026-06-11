from dataclasses import dataclass


APPROX_CHARS_PER_TOKEN = 3.2
LONG_TRANSCRIPT_CHARS = 45_000
VERY_LONG_TRANSCRIPT_CHARS = 90_000
HIGH_TOKEN_THRESHOLD = 18_000
VERY_HIGH_TOKEN_THRESHOLD = 35_000
EXPENSIVE_MODE_NAMES = {"Investment Lens"}
EXPENSIVE_MODE_KEYWORDS = {"investment"}
EXPENSIVE_MODE_LONG_TRANSCRIPT_CHARS = 30_000
HIGH_REASONING_EFFORTS = {"high", "xhigh"}
EXPENSIVE_MODELS = {"gpt-5.5"}


@dataclass(frozen=True)
class CostEstimate:
    transcript_char_count: int
    approximate_transcript_tokens: int
    analysis_mode: str
    model: str
    reasoning_effort: str
    cost_level: str
    warnings: tuple[str, ...]
    requires_confirmation: bool


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / APPROX_CHARS_PER_TOKEN))


def estimate_report_cost(
    transcript: str,
    *,
    analysis_mode: str,
    model: str,
    reasoning_effort: str,
) -> CostEstimate:
    char_count = len(transcript or "")
    token_count = estimate_tokens(transcript or "")
    warnings = _build_warnings(
        char_count,
        token_count,
        analysis_mode=analysis_mode,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    cost_level = classify_cost_level(
        token_count,
        char_count=char_count,
        analysis_mode=analysis_mode,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    return CostEstimate(
        transcript_char_count=char_count,
        approximate_transcript_tokens=token_count,
        analysis_mode=analysis_mode,
        model=model,
        reasoning_effort=reasoning_effort,
        cost_level=cost_level,
        warnings=tuple(warnings),
        requires_confirmation=cost_level in {"High", "Very High"},
    )


def classify_cost_level(
    approximate_tokens: int,
    *,
    char_count: int = 0,
    analysis_mode: str,
    model: str,
    reasoning_effort: str,
) -> str:
    score = 0

    if approximate_tokens >= VERY_HIGH_TOKEN_THRESHOLD or char_count >= VERY_LONG_TRANSCRIPT_CHARS:
        score += 3
    elif approximate_tokens >= HIGH_TOKEN_THRESHOLD or char_count >= LONG_TRANSCRIPT_CHARS:
        score += 2
    elif approximate_tokens >= 8_000:
        score += 1

    if model in EXPENSIVE_MODELS:
        score += 2

    if reasoning_effort == "xhigh":
        score += 2
    elif reasoning_effort == "high":
        score += 1

    if _is_expensive_mode(analysis_mode):
        score += 1
        if char_count >= EXPENSIVE_MODE_LONG_TRANSCRIPT_CHARS:
            score += 1

    if score >= 5:
        return "Very High"
    if score >= 3:
        return "High"
    if score >= 1:
        return "Medium"
    return "Low"


def _build_warnings(
    char_count: int,
    approximate_tokens: int,
    *,
    analysis_mode: str,
    model: str,
    reasoning_effort: str,
) -> list[str]:
    warnings = []
    if char_count >= VERY_LONG_TRANSCRIPT_CHARS:
        warnings.append("Transcript is very long and may use a large number of tokens.")
    elif char_count >= LONG_TRANSCRIPT_CHARS:
        warnings.append("Transcript is long; generation may be slower and more expensive.")

    if approximate_tokens >= HIGH_TOKEN_THRESHOLD:
        warnings.append("Approximate transcript token count is high.")

    if model in EXPENSIVE_MODELS:
        warnings.append("gpt-5.5 is an expensive model profile.")

    if reasoning_effort in HIGH_REASONING_EFFORTS:
        warnings.append("High or xhigh reasoning effort may increase token usage.")

    if _is_expensive_mode(analysis_mode) and char_count >= EXPENSIVE_MODE_LONG_TRANSCRIPT_CHARS:
        warnings.append("Investment Lens on long transcripts is more likely to be high cost.")

    return warnings


def _is_expensive_mode(analysis_mode: str) -> bool:
    normalized = (analysis_mode or "").strip()
    return normalized in EXPENSIVE_MODE_NAMES or any(
        keyword in normalized.lower() for keyword in EXPENSIVE_MODE_KEYWORDS
    )
