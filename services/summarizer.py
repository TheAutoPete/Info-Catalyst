from services.prompt_loader import format_prompt, load_prompt


def build_summary_prompt(transcript: str, source_url: str = "") -> str:
    return format_prompt(load_prompt("summary_prompt.md"), transcript=transcript, source_url=source_url)


def generate_summary_report(transcript: str, source_url: str = "") -> str:
    from services.openai_client import generate_markdown

    return generate_markdown(build_summary_prompt(transcript, source_url))
