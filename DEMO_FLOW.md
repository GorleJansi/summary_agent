# Demo Guide — Webex Case Summary Bot

> **Purpose:** Use this document during demos or onboarding to explain how the bot works, what the user experiences, and which tool does what at every step.

---

## What This Bot Does — One Line

> An engineer types a ServiceNow case number in Webex → the bot fetches the case, reads all notes and emails, sends it to an AI model, and replies with a structured summary — all in under 5 seconds, without the engineer leaving Webex.

---

## 1. User Flow — Step by Step

### Scenario A — Engineer types a case number directly

```
┌─────────────────────────────────────────────────────────────────────┐
│  WEBEX SPACE                                                        │
│                                                                     │
│  👤 Engineer:   CS0001051                                           │
│                                                                     │
│  🤖 Bot:        ┌──────────────────────────────────────┐           │
│                 │ ⏳ Generating summary for CS0001051… │           │
│                 │ This usually takes a few seconds.    │           │
│                 └──────────────────────────────────────┘           │
│                 [card updates automatically ↓]                      │
│                                                                     │
│  🤖 Bot:        ┌──────────────────────────────────────┐           │
│                 │ 📋 Summary — CS0001051               │           │
│                 │                                      │           │
│                 │ Issue:                               │           │
│                 │  WhatsApp messages not delivered     │           │
│                 │  since the previous day.             │           │
│                 │                                      │           │
│                 │ What happened:                       │           │
│                 │  - Customer reported delivery fail   │           │
│                 │  - Engineer reviewed Meta API logs   │           │
│                 │  - Error code 131047 identified      │           │
│                 │                                      │           │
│                 │ What was tried:                      │           │
│                 │  - Reviewed Meta API logs            │           │
│                 │  - Escalated to platform team        │           │
│                 │                                      │           │
│                 │ Current status:                      │           │
│                 │  Under active investigation.         │           │
│                 │                                      │           │
│                 │ Next steps:                          │           │
│                 │  Platform team to confirm fix with   │           │
│                 │  Meta.                               │           │
│                 │                                      │           │
│                 │ [Summarize another case] [Close]     │           │
│                 └──────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Scenario B — Engineer uses the input card (button flow)

```
┌─────────────────────────────────────────────────────────────────────┐
│  WEBEX SPACE                                                        │
│                                                                     │
│  👤 Engineer:   "help" / "hi" / any non-case message               │
│                                                                     │
│  🤖 Bot:        ┌──────────────────────────────────────┐           │
│                 │ 🔍 Support Assistant                 │           │
│                 │ Enter a ServiceNow case number to    │           │
│                 │ generate an AI-powered summary.      │           │
│                 │                                      │           │
│                 │ [_______ e.g. CS0001051 ___________] │  ← text input
│                 │                                      │           │
│                 │ [   Summarize   ]  [   Cancel   ]    │           │
│                 └──────────────────────────────────────┘           │
│                                                                     │
│  👤 Engineer:   types CS0001051 → clicks Summarize                  │
│                                                                     │
│  🤖 Bot:        card updates to ⏳ working… then 📋 summary         │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Scenario C — Engineer asks for another case after a summary

```
Engineer clicks "Summarize another case"
    │
    ▼
Summary card is replaced with 🔍 input card
(same card slot — no extra messages in the chat)
    │
Engineer types new case number → clicks Summarize
    │
    ▼
⏳ working card → 📋 new summary card
```

---

### Scenario D — Closing / Exiting

```
Engineer clicks "Close" on summary card
    → Input card appears in place

Engineer clicks "Cancel" on input card
    → Text message: "Closed ✅ Enter a case number anytime…"

Engineer types "exit", "quit", or "close"
    → Text message: "Closed ✅ Message me anytime…"
```

---

## 2. Full Architecture — What Happens Behind the Scenes

```
╔══════════════════════════════════════════════════════════════════════╗
║  WEBEX SPACE (Engineer's screen)                                     ║
║                                                                      ║
║  Engineer types "CS0001051"                                          ║
╚══════════════════════════════╦═══════════════════════════════════════╝
                               │ Webex sends HTTP POST (webhook event)
                               ▼
╔══════════════════════════════════════════════════════════════════════╗
║  NGROK (tunnel — dev only)                                           ║
║  https://abc123.ngrok-free.app  →  http://localhost:8000             ║
╚══════════════════════════════╦═══════════════════════════════════════╝
                               │
                               ▼
╔══════════════════════════════════════════════════════════════════════╗
║  FASTAPI APP  (app.py, running via uvicorn on port 8000)             ║
║                                                                      ║
║  POST /webhook/webex                                                 ║
║    1. Validate: not a bot message, not a thread reply                ║
║    2. Fetch full message from Webex API → extract case number        ║
║    3. Send ⏳ "working" Adaptive Card → return 200 OK immediately    ║
║    4. Spawn background thread → run pipeline                         ║
║                                                                      ║
║  POST /webhook/webex/card-action                                     ║
║    1. Validate: not a bot                                            ║
║    2. Fetch action details → read action name + case number input    ║
║    3. Replace card with ⏳ working card → return 200 OK              ║
║    4. Spawn background thread → run pipeline                         ║
╚══════╦═══════════════════════════════════════════════════════════════╝
       │ Background thread: _summarize_and_flip()
       │
       ├──────────────────────────────────────────────┐
       │                                              │
       ▼                                              ▼
╔══════════════════════╗              ╔═══════════════════════════════╗
║  SERVICENOW API      ║              ║  CISCO CIRCUIT LLM            ║
║  (servicenow_        ║              ║  (summarizer.py)              ║
║   client.py)         ║              ║                               ║
║                      ║              ║  Step 1 — Get token:          ║
║  GET case record     ║              ║  POST id.cisco.com/oauth2/... ║
║  → sys_id, title,    ║              ║  Body: client_credentials     ║
║    state, priority   ║              ║  → Bearer access token        ║
║                      ║              ║                               ║
║  GET journal entries ║              ║  Step 2 — Call LLM:           ║
║  → comments +        ║              ║  POST chat-ai.cisco.com/      ║
║    work_notes        ║              ║    gpt-4o-mini/completions    ║
║  (with documentkey   ║              ║  Headers: api-key: <token>    ║
║   fallback)          ║              ║  Body: prompt + appkey        ║
║                      ║              ║  Temp: 0.0 (deterministic)    ║
║  GET case emails     ║              ║  → Summary text               ║
║  → sys_email table   ║              ╚═══════════════════════════════╝
╚══════╦═══════════════╝
       │
       ▼
╔══════════════════════════════════════════════════════════════════════╗
║  FORMATTER  (formatter.py)                                           ║
║                                                                      ║
║  Merges journal entries + emails into one list                       ║
║  Sorts chronologically by timestamp                                  ║
║  Labels each entry: type / speaker / timestamp / text               ║
║  Splits into: Customer Emails / Customer Comments / Work Notes       ║
╚══════╦═══════════════════════════════════════════════════════════════╝
       │
       ▼
╔══════════════════════════════════════════════════════════════════════╗
║  SUMMARIZER  (summarizer.py)                                         ║
║                                                                      ║
║  build_prompt() → structured prompt with case data + timeline        ║
║  Strict rules: no PII, no invention, max 5 bullets, collapse noise   ║
║  call_circuit_llm() → sends prompt → gets back fixed-format summary  ║
╚══════╦═══════════════════════════════════════════════════════════════╝
       │
       ▼
╔══════════════════════════════════════════════════════════════════════╗
║  CARD FLIP  (app.py — _summarize_and_flip)                           ║
║                                                                      ║
║  PATCH /messages/{card_message_id}                                   ║
║  Replaces ⏳ working card with 📋 summary card (in-place)            ║
║  Engineer sees the summary appear without a new message              ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 3. Tool Used at Each Step

| Step | What Happens | File | Tool / Library |
|------|-------------|------|---------------|
| 1 | Engineer sends message in Webex | — | Webex (user action) |
| 2 | Webex POSTs webhook event to public URL | — | Webex Bot API |
| 3 | Request reaches local machine | — | **ngrok** (dev tunnel) |
| 4 | Server receives and routes the request | `app.py` | **uvicorn** + **FastAPI** |
| 5 | Bot-loop check (ignore own messages) | `app.py` | `is_bot_message()` — standard `str` ops |
| 6 | Fetch full message from Webex API | `app.py` | **requests** (`GET /messages/{id}`) |
| 7 | Send ⏳ working card to Webex room | `app.py` | **requests** (`POST /messages`) |
| 8 | Return `200 OK` immediately | `app.py` | **FastAPI** response |
| 9 | Start background pipeline | `app.py` | **threading** (daemon thread) |
| 10 | Fetch case record from ServiceNow | `servicenow_client.py` | **requests** + HTTP Basic Auth |
| 11 | Fetch journal entries from ServiceNow | `servicenow_client.py` | **requests** (with `documentkey` fallback) |
| 12 | Fetch case emails from ServiceNow | `servicenow_client.py` | **requests** |
| 13 | Merge + sort all entries into timeline | `formatter.py` | Pure Python (`datetime`, `re`, `sorted`) |
| 14 | Build structured AI prompt | `summarizer.py` | Pure Python (f-string template) |
| 15 | Get OAuth2 token from Cisco | `summarizer.py` | **requests** + **base64** |
| 16 | Call Circuit LLM with prompt | `summarizer.py` | **requests** + **json** |
| 17 | Parse LLM response | `summarizer.py` | **json** / dict access |
| 18 | Replace ⏳ card with 📋 summary | `app.py` | **requests** (`PATCH /messages/{id}`) |
| 19 | Engineer reads summary in Webex | — | Webex Adaptive Card UI |
| 20 | Engineer clicks "Summarize another" | — | Webex card action → back to step 2 |

---

## 4. Bot Loop Prevention — Why It Matters

When the bot sends a message, Webex fires a webhook for that message too. Without protection, the bot would:
1. Send a summary
2. Receive its own summary as a new message
3. Try to summarize it → send another message
4. Loop forever ♾️

**How we stop it — `is_bot_message(email)` in `app.py`:**

```
Incoming webhook event
        │
        ├─ Is person_email the bot? → ignore
        │    Checks: exact match, ends with .bot, @webex.bot, bot@cisco
        │
        ├─ Does the message have a parentId? → ignore (thread reply)
        │
        ├─ Does the text match "Summary for CS..."? → ignore (bot echo)
        │
        └─ Is the text a known bot card fallback phrase? → ignore
```

---

## 5. Card Lifecycle — Visual

```
State 0: Nothing                    Engineer types "CS0001051"
                                            │
                                            ▼
State 1: Working card               ┌─────────────────────────┐
         (sent immediately)         │ ⏳ Generating summary…  │
                                    │ for CS0001051            │
                                    └─────────────────────────┘
                                    LLM runs in background (3-5s)
                                            │
                                            ▼
State 2: Summary card               ┌─────────────────────────┐
         (card PATCHed in-place)    │ 📋 Summary — CS0001051  │
                                    │ Issue: ...              │
                                    │ What happened: ...      │
                                    │ What was tried: ...     │
                                    │ Current status: ...     │
                                    │ Next steps: ...         │
                                    │                         │
                                    │ [Summarize another][Close]│
                                    └─────────────────────────┘
                                            │
                          ┌─────────────────┴────────────────┐
                          ▼                                   ▼
              "Summarize another"                          "Close"
                          │                                   │
                          ▼                                   ▼
State 3: Input card       ┌──────────────────┐   ┌──────────────────┐
         (card PATCHed)   │ 🔍 Support Asst  │   │ 🔍 Support Asst  │
                          │ [___________]    │   │ [___________]    │
                          │ [Summarize][Cancel]│  │ [Summarize][Cancel]│
                          └──────────────────┘   └──────────────────┘
```

> ℹ️ Cards always **replace** the previous card in the same message slot — the Webex chat stays clean with no extra messages.

---

## 6. Key Design Decisions (Good for Demo Q&A)

| Decision | Why |
|----------|-----|
| **Background thread for LLM call** | Webex requires a `200 OK` response within a few seconds. The LLM can take 5–10s. Threading lets us respond immediately and update the card when ready. |
| **In-place card flip (PATCH)** | Avoids flooding the chat with multiple messages. The ⏳ card becomes the 📋 card — one clean interaction. |
| **Temperature = 0.0** | Makes the LLM output deterministic. Same case always gives the same summary — important for consistency in support workflows. |
| **documentkey fallback in ServiceNow** | Different ServiceNow instances store journal entries differently. The fallback ensures the bot works across environments. |
| **is_bot_message() with domain check** | Even if the `WEBEX_BOT_EMAIL` env var is wrong or missing, the `.bot` domain check catches the bot's own messages. Prevents infinite loops. |
| **No PII in summaries** | The LLM prompt explicitly instructs the model to never include email addresses or personal names — only issue details. |
| **Timeline split by source** | Splitting emails / comments / work notes into labelled sections helps the LLM understand who said what and in what context. |

---

## 7. Environment Variables Quick Reference

| Variable | Used In | Purpose |
|----------|---------|---------|
| `SERVICENOW_INSTANCE` | `servicenow_client.py` | ServiceNow hostname |
| `SERVICENOW_USERNAME` | `servicenow_client.py` | API credentials |
| `SERVICENOW_PASSWORD` | `servicenow_client.py` | API credentials |
| `WEBEX_BOT_TOKEN` | `app.py` | Authenticate all Webex API calls |
| `WEBEX_BOT_EMAIL` | `app.py` | Detect and ignore bot's own messages |
| `CIRCUIT_CLIENT_ID` | `summarizer.py` | OAuth2 client ID for Circuit LLM |
| `CIRCUIT_CLIENT_SECRET` | `summarizer.py` | OAuth2 client secret |
| `CIRCUIT_APP_KEY` | `summarizer.py` | App registration key passed to LLM |
| `CIRCUIT_MODEL` | `summarizer.py` | Model name (default: `gpt-4o-mini`) |
| `CIRCUIT_TOKEN_URL` | `summarizer.py` | OAuth2 token endpoint |
| `CIRCUIT_CHAT_BASE_URL` | `summarizer.py` | LLM chat completions base URL |

---

## 8. How to Run for a Demo

```bash
# Terminal 1 — Start the app
cd /path/to/summary-agent
source .venv/bin/activate
uvicorn app:app --reload

# Terminal 2 — Start the tunnel
ngrok http 8000
# Copy the https URL: e.g. https://abc123.ngrok-free.app

# In Webex Developer Portal — update webhook URLs to:
#   https://abc123.ngrok-free.app/webhook/webex
#   https://abc123.ngrok-free.app/webhook/webex/card-action

# Verify everything is up:
curl http://localhost:8000/
curl http://localhost:8000/debug-env
```

**Then in Webex:** Open the space where the bot is a member and type a case number like `CS0001051`.

---

## 9. Files at a Glance

| File | Role | Key contents |
|------|------|-------------|
| `app.py` | 🧠 Main brain | Routes, card logic, bot-loop prevention, background thread, all webhook handlers |
| `config.py` | 🔑 Secrets loader | Reads `.env` into Python variables at startup |
| `servicenow_client.py` | 📥 Data fetcher | 3 functions: get case / get journal entries / get emails |
| `formatter.py` | 🗂️ Timeline builder | Merges + sorts all entries, labels speaker and type |
| `summarizer.py` | 🤖 AI caller | OAuth2 token → prompt builder → Circuit LLM call → summary |
| `.env` | 🔒 Secrets file | All API keys and credentials — never committed to git |
| `requirements.txt` | 📦 Dependencies | `fastapi`, `uvicorn`, `requests`, `python-dotenv` |
