from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    model: str
    reasoning_effort: str
    use_case: str


@dataclass(frozen=True)
class AnalysisMode:
    name: str
    slug: str
    purpose: str
    profile: ModelProfile


MODEL_OPTIONS = ("gpt-5.4-mini", "gpt-5.4", "gpt-5.5")
REASONING_EFFORT_OPTIONS = ("none", "low", "medium", "high", "xhigh")

ANALYSIS_MODES = (
    AnalysisMode(
        name="Quick Summary",
        slug="quick-summary",
        purpose="Fast, cheap, concise understanding of the video.",
        profile=ModelProfile("gpt-5.4-mini", "low", "daily quick scan"),
    ),
    AnalysisMode(
        name="Deep Analysis",
        slug="deep-analysis",
        purpose="Default high-quality analysis for important videos.",
        profile=ModelProfile("gpt-5.4", "medium", "general serious analysis"),
    ),
    AnalysisMode(
        name="Investment Lens",
        slug="investment-lens",
        purpose="Investing, industry research, business model analysis, macro, company analysis, and portfolio implications.",
        profile=ModelProfile("gpt-5.5", "high", "high-value investment analysis"),
    ),
    AnalysisMode(
        name="Bias Check",
        slug="bias-check",
        purpose="Examine bias, overclaiming, missing evidence, narrative traps, conflicts of interest, and weak assumptions.",
        profile=ModelProfile("gpt-5.4", "medium", "critical review"),
    ),
    AnalysisMode(
        name="Titan Input / Structured Research",
        slug="titan-input",
        purpose="Turn the video into structured research input for Axiom Brief / Project Titan.",
        profile=ModelProfile("gpt-5.4", "medium", "structured research archive"),
    ),
)

MODE_NAMES = tuple(mode.name for mode in ANALYSIS_MODES)
DEFAULT_ANALYSIS_MODE = "Deep Analysis"


def get_analysis_mode(name: str) -> AnalysisMode:
    if name == "Titan Input":
        name = "Titan Input / Structured Research"
    for mode in ANALYSIS_MODES:
        if mode.name == name:
            return mode
    raise ValueError(f"Unknown analysis mode: {name}")


def get_default_profile(mode_name: str) -> ModelProfile:
    return get_analysis_mode(mode_name).profile


def resolve_model_profile(
    mode_name: str,
    *,
    override: bool = False,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> ModelProfile:
    default_profile = get_default_profile(mode_name)
    if not override:
        return default_profile

    selected_model = model or default_profile.model
    selected_effort = reasoning_effort or default_profile.reasoning_effort

    if selected_model not in MODEL_OPTIONS:
        raise ValueError(f"Unsupported model: {selected_model}")
    if selected_effort not in REASONING_EFFORT_OPTIONS:
        raise ValueError(f"Unsupported reasoning effort: {selected_effort}")

    return ModelProfile(selected_model, selected_effort, "manual override")


def is_high_cost_profile(profile: ModelProfile) -> bool:
    return profile.model == "gpt-5.5" or profile.reasoning_effort in {"high", "xhigh"}
