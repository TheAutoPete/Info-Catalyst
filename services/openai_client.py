import importlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI

import config


config = importlib.reload(config)
OPENAI_API_KEY = getattr(config, "OPENAI_API_KEY", None)
OPENAI_MODEL = getattr(config, "OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_USE_SYSTEM_PROXY = getattr(config, "OPENAI_USE_SYSTEM_PROXY", False)


class OpenAIRequestError(RuntimeError):
    """Raised when an OpenAI request fails with a user-actionable message."""


@dataclass(frozen=True)
class MarkdownGenerationResult:
    text: str
    usage: dict[str, Any]


def _configured_proxy_names() -> list[str]:
    return sorted(name for name in os.environ if "proxy" in name.lower())


def _connection_error_message(exc: Exception) -> str:
    proxy_names = _configured_proxy_names()
    proxy_hint = ""
    if proxy_names and OPENAI_USE_SYSTEM_PROXY:
        proxy_hint = (
            " Detected proxy environment variables: "
            f"{', '.join(proxy_names)}. If that proxy is stale or not running, set "
            "OPENAI_USE_SYSTEM_PROXY=false in .env or remove the proxy variables before starting Streamlit."
        )

    return (
        "Could not connect to the OpenAI API. Check your internet connection and any VPN/proxy settings."
        f"{proxy_hint} Original error: {exc}"
    )


def generate_markdown(prompt: str, *, model: str | None = None, reasoning_effort: str | None = None) -> str:
    return generate_markdown_with_usage(prompt, model=model, reasoning_effort=reasoning_effort).text


def generate_markdown_with_usage(
    prompt: str,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    analysis_mode: str = "",
) -> MarkdownGenerationResult:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")

    selected_model = model or OPENAI_MODEL
    request_args = {
        "model": selected_model,
        "input": prompt,
    }
    if reasoning_effort and reasoning_effort != "none":
        request_args["reasoning"] = {"effort": reasoning_effort}

    try:
        with httpx.Client(trust_env=OPENAI_USE_SYSTEM_PROXY, timeout=120.0) as http_client:
            client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)
            response = client.responses.create(**request_args)
    except (APIConnectionError, APITimeoutError) as exc:
        raise OpenAIRequestError(_connection_error_message(exc)) from exc
    except AuthenticationError as exc:
        raise OpenAIRequestError("OpenAI authentication failed. Check OPENAI_API_KEY in your .env file.") from exc
    except APIStatusError as exc:
        raise OpenAIRequestError(
            f"OpenAI API returned HTTP {exc.status_code}. The selected model profile may not be supported: "
            f"model={selected_model}, reasoning_effort={reasoning_effort or 'none'}. {exc.message}"
        ) from exc
    except APIError as exc:
        raise OpenAIRequestError(f"OpenAI API request failed: {exc}") from exc

    usage = _extract_usage(response)
    usage.update(
        {
            "model": selected_model,
            "reasoning_effort": reasoning_effort or "none",
            "analysis_mode": analysis_mode,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return MarkdownGenerationResult(text=response.output_text.strip(), usage=usage)


def _extract_usage(response: Any) -> dict[str, Any]:
    try:
        usage = _to_plain_mapping(getattr(response, "usage", None))
        if not usage:
            return {}

        input_details = _to_plain_mapping(usage.get("input_tokens_details"))
        output_details = _to_plain_mapping(usage.get("output_tokens_details"))
        return {
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_tokens": output_details.get("reasoning_tokens"),
            "cached_tokens": input_details.get("cached_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "raw_usage": usage,
        }
    except Exception:
        logging.exception("Failed to extract OpenAI usage metadata")
        return {}


def _to_plain_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}
