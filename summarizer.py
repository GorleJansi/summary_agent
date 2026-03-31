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
    """Raised when Circuit token fetch or chat completion fails."""


def _get_display_value(
    data: Dict[str, Any],
    field: str,
    default: str = "Not explicitly mentioned",
) -> str:
    value = data.get(field)
    if value is None or value == "":
        return default
    if isinstance(value, dict):
        return str(value.get("display_value") or value.get("value") or default)
    return str(value)


def build_prompt(case_data: Dict[str, Any], timeline: List[Dict[str, Any]]) -> str:
    case_number      = _get_display_value(case_data, "number", "Unknown")
    short_desc       = (
        _get_display_value(case_data, "case", "")
        or _get_display_value(case_data, "short_description", "Not explicitly mentioned")
    )
    state            = _get_display_value(case_data, "state")
    description      = _get_display_value(case_data, "description")
    priority         = _get_display_value(case_data, "priority")
    assignment_group = _get_display_value(case_data, "assignment_group")
    last_updated     = _get_display_value(case_data, "sys_updated_on")

    # Split timeline by type so the LLM understands the source of each entry
    emails, comments, work_notes = [], [], []
    for i, item in enumerate(timeline, start=1):
        entry = f"{i}. [{item.get('timestamp', '')}] {item.get('speaker', 'unknown')}: {item.get('text', '').strip()}"
        t = item.get("type", "")
        if t == "email":
            emails.append(entry)
        elif t == "work_note":
            work_notes.append(entry)
        else:
            comments.append(entry)

    def fmt(label: str, items: List[str]) -> str:
        if not items:
            return f"[{label}]\nNone.\n"
        return f"[{label}]\n" + "\n".join(items) + "\n"

    timeline_text = (
        fmt("Customer Emails", emails)
        + "\n" + fmt("Customer Comments", comments)
        + "\n" + fmt("Internal Work Notes", work_notes)
    )

    return f"""You are a support engineer assistant. Read the ServiceNow case below and write a clear summary.

The engineer reading this must instantly know:
- What is the customer's problem?
- What has already been tried? (so they do not repeat it)
- Where does the ticket stand right now?
- What should happen next?

STRICT RULES:
- Use ONLY information explicitly present in the case data and timeline below.
- Do NOT invent, infer, or assume anything not stated. If missing, write: Not explicitly mentioned.
- Collapse repetition: if the same issue is reported across many emails, say it once and note it was reported repeatedly.
- Never include email addresses, personal names, or any PII.
- Short sentences. Bullets only. Be specific.

Case Details:
- Case Number   : {case_number}
- Title         : {short_desc}
- Description   : {description}
- State         : {state}
- Priority      : {priority}
- Group         : {assignment_group}
- Last Updated  : {last_updated}

Timeline:
{timeline_text}

Return EXACTLY this format — no extra sections, no markdown fences:

Summary for {case_number}

Issue:
<1-2 sentences — what is the actual problem the customer is facing?>

What happened:
- <key event, oldest to newest — max 5 bullets, skip repeated noise>

What was tried:
- <actions from Internal Work Notes only>
- (if none: Not explicitly mentioned)

Current status:
<1-2 sentences — where does this ticket stand right now?>

Next steps:
- <only if clearly stated in the case — otherwise: Not explicitly mentioned>
""".strip()


def get_access_token() -> str:
    if not CIRCUIT_CLIENT_ID or not CIRCUIT_CLIENT_SECRET:
        raise CircuitLLMError("Missing CIRCUIT_CLIENT_ID or CIRCUIT_CLIENT_SECRET")

    encoded = base64.b64encode(
        f"{CIRCUIT_CLIENT_ID}:{CIRCUIT_CLIENT_SECRET}".encode()
    ).decode()

    resp = requests.post(
        CIRCUIT_TOKEN_URL,
        headers={
            "Content-Type":  "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded}",
        },
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    resp.raise_for_status()

    token = resp.json().get("access_token")
    if not token:
        raise CircuitLLMError(f"Token response missing access_token: {resp.json()}")
    return token


def call_circuit_llm(prompt: str) -> str:
    if not CIRCUIT_APP_KEY:
        raise CircuitLLMError("Missing CIRCUIT_APP_KEY")

    token = get_access_token()
    url   = f"{CIRCUIT_CHAT_BASE_URL}/{CIRCUIT_MODEL}/chat/completions"

    resp = requests.post(
        url,
        headers={
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "api-key":       token,
        },
        json={
            "messages": [
                {
                    "role":    "system",
                    "content": (
                        "You summarize ServiceNow support cases for engineers. "
                        "Be brief, accurate, and never invent information not present in the case."
                    ),
                },
                {
                    "role":    "user",
                    "content": prompt,
                },
            ],
            "user":        json.dumps({"appkey": CIRCUIT_APP_KEY}),
            "temperature": 0.0,
        },
        timeout=60,
    )
    resp.raise_for_status()
    payload = resp.json()

    choices = payload.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        if content:
            return content.strip()

    # Fallback response shape
    if isinstance(payload.get("message"), dict):
        content = payload["message"].get("content")
        if content:
            return content.strip()

    raise CircuitLLMError(f"Unexpected LLM response format: {payload}")


def summarize_case_with_llm(
    case_data: Dict[str, Any],
    timeline:  List[Dict[str, Any]],
) -> str:
    try:
        return call_circuit_llm(build_prompt(case_data, timeline))
    except Exception as e:
        print(f"LLM summarization error: {repr(e)}")
        return "Summary generation failed. Please try again."