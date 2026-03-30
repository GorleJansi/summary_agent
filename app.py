from fastapi import FastAPI, Request
import re
import time
from typing import Dict, Any, Optional

import requests

from config import WEBEX_BOT_TOKEN, WEBEX_BOT_EMAIL
from servicenow_client import get_case_by_number, get_case_journal_entries
from formatter import build_timeline
from summarizer import summarize_case_with_llm

app = FastAPI()

WEBEX_API_BASE = "https://webexapis.com/v1"


def get_webex_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {WEBEX_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


def request_with_retry(method: str, url: str, max_retries: int = 3, **kwargs):
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            last_error = exc
            print(f"Request failed ({attempt}/{max_retries}) for {url}: {repr(exc)}")
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

    raise last_error


def extract_case_number(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\bCS\d+\b", text.upper())
    return match.group() if match else None


def is_case_number(text: str) -> bool:
    if not text:
        return False
    return bool(re.fullmatch(r"CS\d+", text.strip(), re.IGNORECASE))


def get_webex_message(message_id: str) -> Dict[str, Any]:
    url = f"{WEBEX_API_BASE}/messages/{message_id}"
    response = request_with_retry("GET", url, headers=get_webex_headers())
    return response.json()


def get_attachment_action(action_id: str) -> Dict[str, Any]:
    url = f"{WEBEX_API_BASE}/attachment/actions/{action_id}"
    response = request_with_retry("GET", url, headers=get_webex_headers())
    return response.json()


def send_webex_message(room_id: str, text: str) -> None:
    url = f"{WEBEX_API_BASE}/messages"
    payload = {
        "roomId": room_id,
        "text": text,
    }
    request_with_retry("POST", url, headers=get_webex_headers(), json=payload)


def build_case_input_card(title: str, subtitle: str) -> Dict[str, Any]:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
            },
            {
                "type": "TextBlock",
                "text": subtitle,
                "wrap": True,
                "spacing": "Small",
            },
            {
                "type": "Input.Text",
                "id": "case_number",
                "placeholder": "Enter case number, e.g. CS0001051",
                "isRequired": True,
                "errorMessage": "Please enter a valid case number",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Summarize",
                "data": {
                    "action": "summarize_case"
                },
            },
            {
                "type": "Action.Submit",
                "title": "Exit",
                "data": {
                    "action": "exit_menu"
                },
            },
        ],
    }


def send_case_input_card(
    room_id: str,
    title: str = "Support Assistant",
    subtitle: str = "Enter a case number to generate a summary."
) -> None:
    url = f"{WEBEX_API_BASE}/messages"
    payload = {
        "roomId": room_id,
        "text": "Support Assistant",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": build_case_input_card(title, subtitle),
            }
        ],
    }
    request_with_retry("POST", url, headers=get_webex_headers(), json=payload)


def get_summary(case_number: str) -> Dict[str, Any]:
    case_record = get_case_by_number(case_number)

    if not case_record:
        return {
            "case_number": case_number,
            "summary": "Case not found.",
        }

    case_sys_id = case_record.get("sys_id")
    if not case_sys_id:
        return {
            "case_number": case_number,
            "summary": "Case record is missing sys_id.",
        }

    journal_entries = get_case_journal_entries(case_sys_id)
    timeline = build_timeline(journal_entries)
    llm_summary = summarize_case_with_llm(case_record, timeline)

    return {
        "case_number": case_number,
        "summary": llm_summary,
    }


def format_webex_reply(summary_result: Dict[str, Any]) -> str:
    return (
        f"Summary for {summary_result.get('case_number', '')}\n\n"
        f"{summary_result.get('summary', '')}"
    )


def parse_action_name(action_details: Dict[str, Any]) -> Optional[str]:
    inputs = action_details.get("inputs") or {}
    if isinstance(inputs, dict) and inputs.get("action"):
        return inputs.get("action")

    data = action_details.get("data") or {}
    if isinstance(data, dict) and data.get("action"):
        return data.get("action")

    return None


def parse_case_number_from_action(action_details: Dict[str, Any]) -> Optional[str]:
    inputs = action_details.get("inputs") or {}
    if not isinstance(inputs, dict):
        return None

    case_number = inputs.get("case_number")
    if not case_number:
        return None

    return extract_case_number(case_number)


@app.get("/")
def root():
    return {"message": "ServiceNow + Webex + CIRCUIT LLM summary bot is running"}


@app.get("/debug-env")
def debug_env():
    return {
        "has_webex_token": bool(WEBEX_BOT_TOKEN),
        "webex_bot_email": WEBEX_BOT_EMAIL,
    }


@app.post("/webhook/webex")
async def webex_webhook(request: Request):
    try:
        body = await request.json()
        print("Incoming Webex webhook:", body)

        data = body.get("data", {})
        message_id = data.get("id")
        room_id = data.get("roomId")
        person_email = (data.get("personEmail") or "").lower()

        if not message_id or not room_id:
            return {"status": "ignored", "reason": "Missing message id or room id"}

        if WEBEX_BOT_EMAIL and person_email == WEBEX_BOT_EMAIL.lower():
            return {"status": "ignored", "reason": "Bot webhook event"}

        message = get_webex_message(message_id)
        fetched_email = (message.get("personEmail") or "").lower()
        text = (message.get("text") or "").strip()

        print("Fetched Webex text:", text)

        if WEBEX_BOT_EMAIL and fetched_email == WEBEX_BOT_EMAIL.lower():
            return {"status": "ignored", "reason": "Fetched bot message"}

        if text.startswith("Summary for CS"):
            return {"status": "ignored", "reason": "Bot summary message"}

        if text.lower() in {"exit", "quit", "close"}:
            send_webex_message(
                room_id,
                "Okay — closed the flow. Message me anytime or enter a case number when you need another summary."
            )
            return {"status": "ok", "reason": "Exited"}

        if is_case_number(text):
            case_number = text.strip().upper()
            summary_result = get_summary(case_number)
            send_webex_message(room_id, format_webex_reply(summary_result))
            send_case_input_card(
                room_id,
                title="Summarize another case",
                subtitle="Enter the next case number below."
            )
            return {"status": "ok", "case_number": case_number}

        direct_case_number = extract_case_number(text)
        if direct_case_number and text.lower().startswith("summarize"):
            summary_result = get_summary(direct_case_number)
            send_webex_message(room_id, format_webex_reply(summary_result))
            send_case_input_card(
                room_id,
                title="Summarize another case",
                subtitle="Enter the next case number below."
            )
            return {"status": "ok", "case_number": direct_case_number}

        # default: show input card on first/fallback interaction
        send_case_input_card(
            room_id,
            title="Support Assistant",
            subtitle="Enter a case number to generate a summary."
        )
        return {"status": "ok", "reason": "Input card shown"}

    except Exception as e:
        print("Webhook processing error:", repr(e))
        return {"status": "error", "detail": str(e)}


@app.post("/webhook/webex/card-action")
async def webex_card_action_webhook(request: Request):
    try:
        body = await request.json()
        print("Incoming Webex card action webhook:", body)

        data = body.get("data", {})
        action_id = data.get("id")
        room_id = data.get("roomId")
        person_email = (data.get("personEmail") or "").lower()

        if not action_id or not room_id:
            return {"status": "ignored", "reason": "Missing action id or room id"}

        if WEBEX_BOT_EMAIL and person_email == WEBEX_BOT_EMAIL.lower():
            return {"status": "ignored", "reason": "Bot action event"}

        action_details = get_attachment_action(action_id)
        print("Card action details:", action_details)

        action_name = parse_action_name(action_details)

        if action_name == "exit_menu":
            send_webex_message(
                room_id,
                "Okay — closed the flow. Enter a case number anytime if you want a summary."
            )
            return {"status": "ok", "reason": "Exited"}

        if action_name == "summarize_case":
            case_number = parse_case_number_from_action(action_details)

            if not case_number:
                send_webex_message(
                    room_id,
                    "I couldn't find a valid case number in the card input. Please enter something like CS0001051."
                )
                send_case_input_card(
                    room_id,
                    title="Try again",
                    subtitle="Enter a valid case number to generate a summary."
                )
                return {"status": "ok", "reason": "Invalid card input"}

            summary_result = get_summary(case_number)
            send_webex_message(room_id, format_webex_reply(summary_result))
            send_case_input_card(
                room_id,
                title="Summarize another case",
                subtitle="Enter the next case number below."
            )
            return {"status": "ok", "case_number": case_number}

        return {"status": "ignored", "reason": f"Unknown card action: {action_name}"}

    except Exception as e:
        print("Card action processing error:", repr(e))
        return {"status": "error", "detail": str(e)}