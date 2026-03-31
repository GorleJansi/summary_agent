import re
import time
import threading
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, Request

from config import WEBEX_BOT_TOKEN, WEBEX_BOT_EMAIL
from servicenow_client import get_case_by_number, get_case_journal_entries, get_case_emails
from formatter import build_timeline
from summarizer import summarize_case_with_llm

app = FastAPI()

WEBEX_API_BASE = "https://webexapis.com/v1"
BOT_EMAIL_LOWER = (WEBEX_BOT_EMAIL or "").lower()


def is_bot_message(email: str) -> bool:
    if not email:
        return False
    if BOT_EMAIL_LOWER and email == BOT_EMAIL_LOWER:
        return True
    if email.endswith(".bot"):
        return True
    if "@webex.bot" in email:
        return True
    if "bot@webex" in email or "bot@cisco" in email:
        return True
    return False


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {WEBEX_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


def _request(method: str, url: str, max_retries: int = 3, **kwargs) -> Optional[requests.Response]:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method, url, timeout=30, **kwargs)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            print(f"[HTTP] attempt {attempt}/{max_retries} failed for {url}: {repr(exc)}")
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
    raise last_exc


def get_webex_message(message_id: str) -> Optional[Dict[str, Any]]:
    resp = _request("GET", f"{WEBEX_API_BASE}/messages/{message_id}", headers=_headers())
    return resp.json() if resp else None


def get_attachment_action(action_id: str) -> Optional[Dict[str, Any]]:
    resp = _request("GET", f"{WEBEX_API_BASE}/attachment/actions/{action_id}", headers=_headers())
    return resp.json() if resp else None


def send_text(room_id: str, text: str) -> None:
    _request(
        "POST",
        f"{WEBEX_API_BASE}/messages",
        headers=_headers(),
        json={"roomId": room_id, "text": text},
    )


def send_card(room_id: str, card_content: Dict[str, Any], fallback_text: str = "Card") -> Optional[str]:
    resp = _request(
        "POST",
        f"{WEBEX_API_BASE}/messages",
        headers=_headers(),
        json={
            "roomId": room_id,
            "text": fallback_text,
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content,
            }],
        },
    )
    if resp:
        return resp.json().get("id")
    return None


def replace_card(message_id: str, card_content: Dict[str, Any], fallback_text: str = "Card") -> None:
    _request(
        "PATCH",
        f"{WEBEX_API_BASE}/messages/{message_id}",
        headers=_headers(),
        json={
            "text": fallback_text,
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card_content,
            }],
        },
    )


def _input_card(
    title: str = "🔍 Support Assistant",
    subtitle: str = "Enter a ServiceNow case number to generate an AI-powered summary.",
) -> Dict[str, Any]:
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
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": subtitle,
                "wrap": True,
                "spacing": "Small",
                "color": "Default",
            },
            {
                "type": "Input.Text",
                "id": "case_number",
                "placeholder": "e.g. CS0001051",
                "isRequired": True,
                "errorMessage": "Please enter a valid case number (e.g. CS0001051)",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Summarize",
                "style": "positive",
                "data": {"action": "summarize_case"},
            },
            {
                "type": "Action.Submit",
                "title": "Cancel",
                "data": {"action": "exit_menu"},
            },
        ],
    }


def _working_card(case_number: str) -> Dict[str, Any]:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "TextBlock",
                "text": f"⏳ Generating summary for {case_number}…",
                "wrap": True,
                "weight": "Bolder",
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": "This usually takes a few seconds. The card will update automatically.",
                "wrap": True,
            },
        ],
    }


def _summary_card(case_number: str, summary_text: str) -> Dict[str, Any]:
    max_chars = 2000
    body_text = summary_text if len(summary_text) <= max_chars else summary_text[:max_chars] + "…"

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "TextBlock",
                "text": f"📋 Summary — {case_number}",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Accent",
            },
            {
                "type": "TextBlock",
                "text": body_text,
                "wrap": True,
                "spacing": "Medium",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Summarize another case",
                "style": "positive",
                "data": {"action": "open_input_card"},
            },
            {
                "type": "Action.Submit",
                "title": "Close",
                "data": {"action": "close_summary"},
            },
        ],
    }


def extract_case_number(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\bCS\d+\b", text.upper())
    return match.group() if match else None


def is_bare_case_number(text: str) -> bool:
    return bool(text and re.fullmatch(r"CS\d+", text.strip(), re.IGNORECASE))


def get_summary(case_number: str) -> Dict[str, Any]:
    case_record = get_case_by_number(case_number)
    if not case_record:
        return {"case_number": case_number, "summary": "❌ Case not found in ServiceNow."}

    raw_sys_id = case_record.get("sys_id")
    if isinstance(raw_sys_id, dict):
        raw_sys_id = raw_sys_id.get("value") or raw_sys_id.get("display_value")

    if not raw_sys_id:
        return {"case_number": case_number, "summary": "❌ Case record is missing a sys_id."}

    journal_entries = get_case_journal_entries(raw_sys_id)
    email_entries = get_case_emails(raw_sys_id)
    timeline = build_timeline(journal_entries, email_entries)
    llm_summary = summarize_case_with_llm(case_record, timeline)

    return {"case_number": case_number, "summary": llm_summary}


def format_reply(result: Dict[str, Any]) -> str:
    case_number = result.get("case_number", "")
    summary = (result.get("summary") or "").strip()

    if not summary or summary.startswith("❌"):
        return f"Could not generate summary for {case_number}.\n\n{summary}"

    return summary


def _parse_action(action_details: Dict[str, Any]) -> Optional[str]:
    for key in ("inputs", "data"):
        container = action_details.get(key) or {}
        if isinstance(container, dict) and container.get("action"):
            return container["action"]
    return None


def _parse_case_from_action(action_details: Dict[str, Any]) -> Optional[str]:
    inputs = action_details.get("inputs") or {}
    if not isinstance(inputs, dict):
        return None
    return extract_case_number(inputs.get("case_number", ""))


def _summarize_and_flip(room_id: str, case_number: str, card_message_id: Optional[str]) -> None:
    result = get_summary(case_number)
    summary = format_reply(result)
    sum_card = _summary_card(case_number, summary)

    if card_message_id:
        replace_card(card_message_id, sum_card, fallback_text=f"Summary — {case_number}")
    else:
        send_card(room_id, sum_card, fallback_text=f"Summary — {case_number}")


@app.get("/")
def root():
    return {"message": "ServiceNow + Webex case-summary bot is running ✅"}


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
        data = body.get("data", {})
        message_id = data.get("id")
        room_id = data.get("roomId")
        parent_id = data.get("parentId")
        person_email = (data.get("personEmail") or "").lower()

        if not message_id or not room_id:
            return {"status": "ignored", "reason": "Missing message_id or room_id"}

        if is_bot_message(person_email):
            return {"status": "ignored", "reason": "Bot event (outer payload)"}

        if parent_id:
            return {"status": "ignored", "reason": "Thread reply (parentId present)"}

        message = get_webex_message(message_id)
        if not message:
            return {"status": "ignored", "reason": "Message not found (404 or fetch error)"}

        fetched_email = (message.get("personEmail") or "").lower()
        text = (message.get("text") or "").strip()

        if is_bot_message(fetched_email):
            return {"status": "ignored", "reason": "Bot event (fetched message)"}

        if re.search(r"Summary for CS\d+", text, re.IGNORECASE):
            return {"status": "ignored", "reason": "Bot summary echo"}

        bot_fallback_phrases = {
            "support assistant",
            "support assistant – enter a case number to summarize",
            "generating summary…",
            "generating summary...",
            "summary closed",
            "summarize another case?",
            "summary —",
        }
        if text.lower() in bot_fallback_phrases:
            return {"status": "ignored", "reason": "Bot card fallback text echo"}

        text_lower = text.lower()

        if text_lower in {"exit", "quit", "close"}:
            send_text(room_id, "Closed ✅ Message me anytime or enter a case number to start a new summary.")
            return {"status": "ok", "reason": "Exited via text command"}

        if is_bare_case_number(text):
            case_number = text.strip().upper()
            card_id = send_card(room_id, _working_card(case_number), fallback_text="Generating summary…")
            threading.Thread(
                target=_summarize_and_flip,
                args=(room_id, case_number, card_id),
                daemon=True,
            ).start()
            return {"status": "ok", "case_number": case_number}

        if text_lower.startswith("summarize"):
            direct_case = extract_case_number(text)
            if direct_case:
                card_id = send_card(room_id, _working_card(direct_case), fallback_text="Generating summary…")
                threading.Thread(
                    target=_summarize_and_flip,
                    args=(room_id, direct_case, card_id),
                    daemon=True,
                ).start()
                return {"status": "ok", "case_number": direct_case}

        send_card(
            room_id,
            _input_card(),
            fallback_text="Support Assistant – enter a case number to summarize",
        )
        return {"status": "ok", "reason": "Input card shown"}

    except Exception as exc:
        print(f"[webhook/webex] Error: {repr(exc)}")
        return {"status": "error", "detail": str(exc)}


@app.post("/webhook/webex/card-action")
async def webex_card_action_webhook(request: Request):
    try:
        body = await request.json()
        data = body.get("data", {})
        action_id = data.get("id")
        room_id = data.get("roomId")
        person_email = (data.get("personEmail") or "").lower()
        card_message_id = data.get("messageId")

        if not action_id or not room_id:
            return {"status": "ignored", "reason": "Missing action_id or room_id"}

        if is_bot_message(person_email):
            return {"status": "ignored", "reason": "Bot action event"}

        action_details = get_attachment_action(action_id)
        if not action_details:
            return {"status": "ignored", "reason": "Could not fetch action details (404?)"}

        action_name = _parse_action(action_details)

        if action_name == "open_input_card":
            if card_message_id:
                replace_card(
                    card_message_id,
                    _input_card(),
                    fallback_text="Support Assistant",
                )
            else:
                send_card(
                    room_id,
                    _input_card(),
                    fallback_text="Support Assistant",
                )
            return {"status": "ok", "reason": "Input card shown (open_input_card)"}

        if action_name == "exit_menu":
            send_text(room_id, "Closed ✅ Enter a case number anytime to generate a new summary.")
            return {"status": "ok", "reason": "Exited (exit_menu)"}

        if action_name == "close_summary":
            if card_message_id:
                replace_card(
                    card_message_id,
                    _input_card(),
                    fallback_text="Support Assistant",
                )
            else:
                send_card(
                    room_id,
                    _input_card(),
                    fallback_text="Support Assistant",
                )
            return {"status": "ok", "reason": "Returned to input card"}

        if action_name == "summarize_case":
            case_number = _parse_case_from_action(action_details)

            if not case_number:
                if card_message_id:
                    replace_card(
                        card_message_id,
                        _input_card(
                            title="⚠️ Invalid case number",
                            subtitle="Please enter a valid case number like CS0001051.",
                        ),
                        fallback_text="Invalid case number – try again",
                    )
                else:
                    send_card(
                        room_id,
                        _input_card(
                            title="⚠️ Invalid case number",
                            subtitle="Please enter a valid case number like CS0001051.",
                        ),
                        fallback_text="Invalid case number – try again",
                    )
                return {"status": "ok", "reason": "Invalid case number"}

            if card_message_id:
                replace_card(card_message_id, _working_card(case_number), fallback_text="Generating summary…")

            threading.Thread(
                target=_summarize_and_flip,
                args=(room_id, case_number, card_message_id),
                daemon=True,
            ).start()
            return {"status": "ok", "case_number": case_number}

        return {"status": "ignored", "reason": f"Unknown action: {action_name}"}

    except Exception as exc:
        print(f"[webhook/webex/card-action] Error: {repr(exc)}")
        return {"status": "error", "detail": str(exc)}