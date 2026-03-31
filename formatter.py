from datetime import datetime
from typing import List


def clean_text(text: str) -> str:
    """Remove newlines and collapse extra whitespace."""
    if not text:
        return ""
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def to_iso(ts: str) -> str:
    """Convert ServiceNow timestamp string to ISO 8601 format."""
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").isoformat() + "Z"
    except ValueError:
        return ts  # return as-is if format is unexpected


def map_speaker(element: str) -> str:
    mapping = {
        "comments":   "customer",
        "work_notes": "support_engineer",
        "email":      "customer",
    }
    return mapping.get(element, "unknown")


def map_type(element: str) -> str:
    mapping = {
        "comments":   "comment",
        "work_notes": "work_note",
        "email":      "email",
    }
    return mapping.get(element, "event")


def build_timeline(
    journal_entries: List[dict],
    email_entries: List[dict] = None
) -> List[dict]:
    """
    Build a unified, chronologically sorted timeline from:
    - journal_entries : comments and work_notes from sys_journal_field
    - email_entries   : emails from sys_email (optional)
    """
    timeline = []

    # Journal entries — comments and work notes
    for item in journal_entries:
        element = item.get("element", "")
        text    = clean_text(item.get("value", ""))
        if not text:
            continue
        timeline.append({
            "type":      map_type(element),
            "source":    element,
            "speaker":   map_speaker(element),
            "timestamp": to_iso(item.get("sys_created_on", "1970-01-01 00:00:00")),
            "text":      text,
        })

    # Email entries
    for email in (email_entries or []):
        text = clean_text(
            email.get("body_text") or email.get("body") or email.get("subject") or ""
        )
        if not text:
            continue
        timeline.append({
            "type":      "email",
            "source":    "email",
            "speaker":   "customer",
            "timestamp": to_iso(email.get("sys_created_on", "1970-01-01 00:00:00")),
            "text":      text,
        })

    # Sort chronologically so LLM sees events in order
    timeline.sort(key=lambda x: x["timestamp"])
    return timeline