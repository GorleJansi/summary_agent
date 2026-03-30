# POC: Automated ServiceNow Case Summarization via Webex Bot

## 1. Executive Summary

This POC demonstrates an AI-powered support assistant that automatically summarizes ServiceNow customer service cases and delivers the summary directly inside a Webex conversation.

Support engineers currently spend significant time manually reading through case histories, customer comments, and internal work notes to understand the current situation. This bot eliminates that overhead — an engineer simply types a case number in Webex and receives a structured, AI-generated summary in seconds.

---

## 2. Problem Statement

| Pain Point | Impact |
|------------|--------|
| Support engineers manually read long ServiceNow case histories | Time-consuming, error-prone |
| No quick way to get a structured summary of a case | Slows down triage and handover |
| Case journals contain noise (test entries, repeated comments) | Hard to extract actionable information quickly |
| No integration between ServiceNow and Webex for case context | Context-switching across multiple tools |

---

## 3. Solution Overview

An intelligent Webex Bot that:

1. Listens for messages in a Webex space
2. Accepts a ServiceNow case number (e.g. `CS0001051`)
3. Fetches the full case record and journal history from ServiceNow
4. Builds a structured timeline of all customer comments and engineer work notes
5. Sends the timeline to Cisco's internal Circuit LLM (AI model)
6. Returns a clean, structured summary back to the Webex space

The engineer never leaves Webex. The entire interaction takes 3–5 seconds.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        WEBEX SPACE                          │
│  Engineer types: "CS0001051"                                │
│  Bot replies with AI summary                                │
└────────────────────┬────────────────────────────────────────┘
                     │  Webex Webhook (HTTPS POST)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   FASTAPI APPLICATION                        │
│                    (app.py — port 8000)                     │
│                                                             │
│  POST /webhook/webex       ← Receives Webex messages        │
│  POST /webhook/webex/card-action ← Handles card submissions │
│  GET  /health              ← Health check                   │
│  GET  /debug-env           ← Env var verification           │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────┐              ┌───────────────────────────┐
│  SERVICENOW API  │              │    CISCO CIRCUIT LLM      │
│                  │              │                           │
│ Fetch case by    │              │ Step 1: OAuth2 token      │
│ case number      │              │  → id.cisco.com           │
│                  │              │                           │
│ Fetch journal    │              │ Step 2: Chat completion   │
│ entries          │              │  → chat-ai.cisco.com      │
│ (comments +      │              │  Model: gpt-4o-mini       │
│  work notes)     │              └───────────────────────────┘
└──────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  FORMATTER (formatter.py)    │
│  Builds structured timeline  │
│  from raw journal entries    │
└──────────────────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  SUMMARIZER (summarizer.py)  │
│  Builds AI prompt            │
│  Calls Circuit LLM           │
│  Returns structured summary  │
└──────────────────────────────┘
```

---

## 5. Project Structure

```
summary-agent/
├── app.py                  # Main FastAPI application — all routes & webhook logic
├── config.py               # Loads all environment variables from .env
├── formatter.py            # Converts raw journal entries into structured timeline
├── servicenow_client.py    # ServiceNow REST API integration
├── summarizer.py           # Circuit LLM integration — prompt + AI call
├── requirements.txt        # Python package dependencies
└── .env                    # Configuration & secrets (not shared)
```

---

## 6. Layer-by-Layer Code Explanation

### Layer 1 — Configuration (`config.py`)

**What it does:**
Loads all secrets and configuration values from the `.env` file into Python variables at startup.

**Key variables:**

| Variable | Purpose |
|----------|---------|
| `SERVICENOW_INSTANCE` | ServiceNow hostname |
| `SERVICENOW_USERNAME` | ServiceNow API credentials |
| `SERVICENOW_PASSWORD` | ServiceNow API credentials |
| `WEBEX_BOT_TOKEN` | Webex Bot API token |
| `WEBEX_BOT_EMAIL` | Bot's own email (to ignore its own messages) |
| `CIRCUIT_CLIENT_ID` | Cisco Circuit LLM OAuth2 client ID |
| `CIRCUIT_CLIENT_SECRET` | Cisco Circuit LLM OAuth2 secret |
| `CIRCUIT_APP_KEY` | Cisco Circuit LLM app registration key |
| `CIRCUIT_MODEL` | LLM model name (`gpt-4o-mini`) |
| `CIRCUIT_TOKEN_URL` | OAuth2 token endpoint |
| `CIRCUIT_CHAT_BASE_URL` | Circuit LLM chat completions base URL |

**Why separate?** Keeps all secrets in one place, makes the app portable, and avoids hardcoding credentials.

---

### Layer 2 — ServiceNow Client (`servicenow_client.py`)

**What it does:**
Makes authenticated REST API calls to ServiceNow to retrieve case data.

**Functions:**

`get_case_by_number(case_number)`
- Calls ServiceNow Table API: `GET /api/now/table/sn_customerservice_case`
- Fetches: `sys_id`, `number`, `short_description`, `description`, `state`, timestamps
- Returns the case record as a Python dictionary

`get_case_journal_entries(sys_id)`
- Calls ServiceNow Table API: `GET /api/now/table/sys_journal_field`
- Fetches all `comments` (customer-visible) and `work_notes` (internal engineer notes)
- Ordered by creation date (chronological)
- Falls back to `documentkey` query if primary query returns empty

**Authentication:** HTTP Basic Auth (username + password)

---

### Layer 3 — Formatter (`formatter.py`)

**What it does:**
Transforms raw ServiceNow journal entry data into a clean, structured timeline suitable for the AI model.

**Functions:**

| Function | Purpose |
|----------|---------|
| `clean_text(text)` | Strips newlines, extra whitespace from entry text |
| `to_iso(ts)` | Converts ServiceNow timestamp format to ISO 8601 |
| `map_speaker(element)` | Maps `comments` → `customer`, `work_notes` → `support_engineer` |
| `map_type(element)` | Maps element to `comment` or `work_note` |
| `build_timeline(journal_entries)` | Produces a list of structured timeline dicts |

**Output format per timeline entry:**
```python
{
  "type": "comment",
  "speaker": "customer",
  "timestamp": "2026-03-29T02:05:25Z",
  "text": "WhatsApp messages not delivered since yesterday"
}
```

---

### Layer 4 — Summarizer (`summarizer.py`)

**What it does:**
Builds the AI prompt from case data and timeline, authenticates with Cisco Circuit LLM via OAuth2, calls the LLM API, and returns the structured summary.

**Functions:**

`_get_display_value(case_data, field_name)`
- Safely extracts a field value from the ServiceNow case record
- Handles nested dict format (ServiceNow returns `{"display_value": "...", "value": "..."}`)

`build_prompt(case_data, timeline)`
- Constructs a detailed, instruction-guided prompt for the LLM
- Includes: case number, title, state, description, priority, assignment group, full timeline
- Instructs the LLM to return output in a fixed structured format:
  - Problem Summary
  - Customer Impact
  - Case Context
  - Key Updates
  - Technical Findings
  - Current Status

`get_access_token()`
- Authenticates with Cisco's OAuth2 server: `https://id.cisco.com/oauth2/default/v1/token`
- Uses `client_credentials` grant type
- Encodes `client_id:client_secret` as Base64 for HTTP Basic Auth header
- Returns a Bearer access token

`call_circuit_llm(prompt)`
- Calls: `https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions`
- Sends the system role + user prompt
- Passes `CIRCUIT_APP_KEY` in the `user` field as a JSON-encoded string
- Parses and returns the LLM's response content

`summarize_case_with_llm(case_data, timeline)`
- Orchestrator: calls `build_prompt()` → calls `call_circuit_llm()` → returns summary string

---

### Layer 5 — Application (`app.py`)

**What it does:**
The main FastAPI application. Handles all incoming HTTP requests from Webex, orchestrates the full summarization flow, and sends responses back to Webex.

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Returns bot running status |
| `/health` | GET | Health check — confirms server is up |
| `/debug-env` | GET | Confirms environment variables are loaded |
| `/webhook/webex` | POST | Receives all Webex message events |
| `/webhook/webex/card-action` | POST | Receives Webex Adaptive Card form submissions |

**Key Functions:**

`request_with_retry(method, url, max_retries=3)`
- Wraps all outbound HTTP calls with automatic retry logic (3 attempts, exponential backoff)
- Ensures reliability against transient network errors

`extract_case_number(text)`
- Uses regex `\bCS\d+\b` to find a ServiceNow case number anywhere in a message

`is_case_number(text)`
- Checks if the entire message is just a case number (e.g. user typed only `CS0001051`)

`build_case_input_card()`
- Builds an **Adaptive Card** — an interactive form inside Webex with:
  - Text input for case number
  - "Summarize" button
  - "Exit" button

`send_case_input_card(room_id)`
- Sends the Adaptive Card to the Webex room so users can submit a case number via form

`get_summary(case_number)`
- Full orchestration pipeline:
  1. Fetch case from ServiceNow
  2. Fetch journal entries
  3. Build timeline
  4. Call LLM for summary
  5. Return structured result

**Webhook Message Flow (`/webhook/webex`):**

```
1. Receive Webex event → extract message_id + room_id
2. Ignore bot's own messages (prevent loop)
3. Ignore "exit/quit/close" → send goodbye message
4. If message is exactly a case number → generate summary + show next card
5. If message contains "summarize CS..." → generate summary + show next card
6. Otherwise → show input card (guide user)
```

**Card Action Flow (`/webhook/webex/card-action`):**

```
1. Receive card submission event → fetch action details
2. If action = "exit_menu" → send goodbye message
3. If action = "summarize_case" → extract case number → generate summary → show next card
4. If case number invalid → show error + retry card
```

---

## 7. Technologies Used

| Technology | Category | Why Used |
|-----------|----------|----------|
| **Python 3.13** | Language | Core development language |
| **FastAPI** | Web framework | High-performance API server with auto docs |
| **uvicorn** | ASGI server | Runs the FastAPI app, handles HTTP connections |
| **requests** | HTTP client | Makes REST calls to ServiceNow, Webex, Circuit LLM |
| **python-dotenv** | Config management | Loads secrets from `.env` — no hardcoded credentials |
| **pydantic** | Data validation | Validates incoming request bodies |
| **base64** | Encoding | Encodes credentials for Circuit LLM OAuth2 Basic Auth |
| **json** | Serialization | Encodes Circuit LLM `appkey` metadata |
| **Cisco Circuit LLM** | AI/LLM | Internal Cisco AI platform — generates case summaries |
| **Webex Bot API** | Messaging | Sends and receives messages in Webex spaces |
| **ServiceNow REST API** | Data source | Fetches case records and journal entries |
| **Adaptive Cards** | UI | Interactive form cards inside Webex for case input |
| **ngrok** | Dev tunneling | Exposes local server to internet for Webex webhook testing |

---

## 8. Data Flow — End to End

```
1. Engineer types "CS0001051" in Webex space
          │
2. Webex sends POST to /webhook/webex (our FastAPI server)
          │
3. app.py extracts case number "CS0001051"
          │
4. servicenow_client.py calls ServiceNow API
   → Returns: case title, state, description, sys_id
          │
5. servicenow_client.py fetches journal entries (comments + work notes)
          │
6. formatter.py builds structured timeline
   → [{ speaker: "customer", timestamp: "...", text: "..." }, ...]
          │
7. summarizer.py builds prompt with case data + timeline
          │
8. summarizer.py calls id.cisco.com → gets OAuth2 access token
          │
9. summarizer.py calls chat-ai.cisco.com with prompt
   → Returns: AI-generated structured summary
          │
10. app.py sends summary back to Webex room
    → Engineer sees: Problem Summary, Actions Taken, Status, Next Steps
          │
11. Bot shows interactive card: "Enter next case number"
```

---

## 9. Sample Output

**Input:** Engineer types `CS0001051` in Webex

**Bot Response:**
```
Summary for CS0001051

Problem Summary:
The customer reports that the Webex Connect desktop app fails to launch.
No error message is displayed; the application silently exits on startup.

Customer Impact:
- Customer is unable to use the desktop application

Case Context:
- Priority: High
- Assignment Group: CX Connect Support
- Last Updated: 2026-03-29T02:05:25Z

Key Updates:
- Customer confirmed the issue started after the latest system update
- Engineer checked logs and identified a missing dependency error

Technical Findings:
- Meta API returning error code 131047 on message delivery calls

Current Status:
- Case is open and under active investigation by the support engineer
```

---

## 10. Security Considerations

| Item | Approach |
|------|----------|
| Credentials storage | All secrets in `.env` file, never in source code |
| ServiceNow auth | HTTP Basic Auth over HTTPS |
| Circuit LLM auth | OAuth2 client credentials (short-lived Bearer token) |
| Webex bot identity | Bot email used to prevent self-triggered message loops |
| SSL/TLS | All API calls use HTTPS |
| `.env` file | Should be in `.gitignore` — not committed to any repository |

---

## 11. Current State & Limitations

### ✅ Working
- FastAPI server with all endpoints
- ServiceNow case + journal entry fetching
- Timeline formatter
- Circuit LLM OAuth2 token fetch
- Circuit LLM chat completions call
- Webex message receiving and reply
- Adaptive Card UI for case input
- Card action handler for form submissions
- Retry logic on all outbound HTTP calls

### ⚠️ Pending Validation
- Circuit LLM API endpoint URL — needs confirmation of correct internal URL
- Webex webhook registration with permanent URL (requires cloud deployment)

### 🔜 Next Steps for Production
- Deploy to cloud (AWS / GCP / Azure / Cisco internal hosting) for permanent webhook URL
- Add Webex webhook secret validation (HMAC signature check)
- Add structured logging to file
- Add token caching with expiry refresh for Circuit LLM
- Add unit tests

---

## 12. How to Run Locally

```bash
# 1. Clone / open the project
cd /path/to/summary-agent

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
uvicorn app:app --reload
# Server runs at http://127.0.0.1:8000

# 5. Expose via ngrok (for Webex webhook)
ngrok http 8000
# Register https://<ngrok-url>/webhook/webex in Webex Developer Portal

# 6. Test health
curl http://127.0.0.1:8000/health

# 7. Test case summary
curl -X POST http://127.0.0.1:8000/summary/by-case-number \
  -H "Content-Type: application/json" \
  -d '{"case_number": "CS0001051"}'
```

---

## 13. Dependencies (`requirements.txt`)

```
fastapi
uvicorn
requests
python-dotenv
```

All other modules used (`base64`, `json`, `re`, `os`, `time`, `typing`) are part of Python's standard library — no additional installation required.
