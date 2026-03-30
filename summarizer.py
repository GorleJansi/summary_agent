import base64
import json
from typing import Any, Dict, List

import requests

from config import (
    CIRCUIT_APP_KEY,
    CIRCUIT_CHAT_BASE_URL,
    CIRCUIT_CLIENT_ID,
    CIRCUIT_CLIENT_SECRET,
    CIRCUIT_MODEL,
    CIRCUIT_TOKEN_URL,
)


class CircuitLLMError(Exception):
    """Raised when CIRCUIT token or chat completion fails."""


def _get_display_value(
    case_data: Dict[str, Any],
    field_name: str,
    default: str = "Not explicitly mentioned",
) -> str:
    value = case_data.get(field_name)

    if value is None or value == "":
        return default

    if isinstance(value, dict):
        if value.get("display_value"):
            return str(value["display_value"])
        if value.get("value"):
            return str(value["value"])
        return default

    return str(value)


def build_prompt(case_data: Dict[str, Any], timeline: List[Dict[str, Any]]) -> str:
    case_number = _get_display_value(case_data, "number", "Unknown")
    case_title = (
        _get_display_value(case_data, "case", "")
        or _get_display_value(case_data, "short_description", "")
        or "Not explicitly mentioned"
    )
    state = _get_display_value(case_data, "state")
    description = _get_display_value(case_data, "description")

    priority = _get_display_value(case_data, "priority")
    assignment_group = _get_display_value(case_data, "assignment_group")
    last_updated = _get_display_value(case_data, "sys_updated_on")

    lines = []
    for i, item in enumerate(timeline, start=1):
        timestamp = item.get("timestamp", "")
        speaker = item.get("speaker", "unknown")
        text = item.get("text", "")
        lines.append(f"{i}. [{timestamp}] {speaker}: {text}")

    timeline_text = "\n".join(lines) if lines else "No journal activity found."

    return f"""
You are a support engineer summarizing ServiceNow cases.

Make the output:
- Short
- Clear
- Informative
- Useful for engineers
- Free of unnecessary text

Rules:
- Do NOT invent anything
- Only use explicitly available data from the case fields and timeline
- Ignore obvious noise like "test", "bad", or unrelated placeholder notes
- Keep bullets short and specific
- If a section has no information, write "Not explicitly mentioned"

Case Number: {case_number}
Title: {case_title}
State: {state}
Description: {description}

Case Context:
- Priority: {priority}
- Assignment Group: {assignment_group}
- Last Updated: {last_updated}

Timeline:
{timeline_text}

Return exactly in this format:

Problem Summary:
<1-2 line summary>

Customer Impact:
- <impact or Not explicitly mentioned>

Case Context:
- Priority: {priority}
- Assignment Group: {assignment_group}
- Last Updated: {last_updated}

Key Updates:
- <important update>
- If none: Not explicitly mentioned

Technical Findings:
- <explicit technical finding>
- If none: Not explicitly mentioned

Current Status:
- <explicit status only>
""".strip()


def get_access_token() -> str:
    if not CIRCUIT_CLIENT_ID or not CIRCUIT_CLIENT_SECRET:
        raise CircuitLLMError("Missing CIRCUIT_CLIENT_ID or CIRCUIT_CLIENT_SECRET")

    creds = f"{CIRCUIT_CLIENT_ID}:{CIRCUIT_CLIENT_SECRET}"
    encoded = base64.b64encode(creds.encode("utf-8")).decode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded}",
    }
    data = {"grant_type": "client_credentials"}

    response = requests.post(
        CIRCUIT_TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise CircuitLLMError(f"Token response missing access_token: {payload}")

    return access_token


def call_circuit_llm(prompt: str) -> str:
    if not CIRCUIT_APP_KEY:
        raise CircuitLLMError("Missing CIRCUIT_APP_KEY")

    access_token = get_access_token()
    url = f"{CIRCUIT_CHAT_BASE_URL}/{CIRCUIT_MODEL}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "api-key": access_token,
    }

    body = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You summarize support cases clearly, briefly, and accurately for engineers. "
                    "Do not invent or infer missing information."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "user": json.dumps({"appkey": CIRCUIT_APP_KEY}),
        "temperature": 0.1,
    }

    response = requests.post(url, headers=headers, json=body, timeout=60)
    response.raise_for_status()

    payload = response.json()

    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if content:
            return content.strip()

    if isinstance(payload.get("message"), dict):
        content = payload["message"].get("content")
        if content:
            return content.strip()

    raise CircuitLLMError(f"Unexpected LLM response format: {payload}")


def summarize_case_with_llm(case_data: Dict[str, Any], timeline: List[Dict[str, Any]]) -> str:
    prompt = build_prompt(case_data, timeline)
    return call_circuit_llm(prompt)