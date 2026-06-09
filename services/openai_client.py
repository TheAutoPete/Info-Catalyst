from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL


def generate_markdown(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )
    return response.output_text.strip()

