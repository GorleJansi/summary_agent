# POC: Automated ServiceNow Case Summarization via Webex Bot

## 1. Executive Summary

This POC demonstrates an AI-powered support assistant that automatically summarizes ServiceNow customer service cases and delivers the summary directly inside a Webex conversation.

Support engineers currently spend significant time manually reading through case histories, customer comments, internal work notes, and case emails to understand the current situation. This bot eliminates that overhead — an engineer simply types a case number in Webex and receives a structured, AI-generated summary in seconds.

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
3. Fetches the full case record, journal history, and case emails from ServiceNow
4. Builds a unified, chronologically sorted timeline of customer comments, engineer work notes, and emails
5. Sends the timeline to Cisco's internal Circuit LLM (AI model)
6. Returns a clean, structured summary back to the Webex space as an interactive Adaptive Card

The engineer never leaves Webex. The entire interaction takes 3–5 seconds. The card updates in-place — a "working" spinner card flips to the summary automatically using a background thread.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        WEBEX SPACE                          │
│  Engineer types: "CS0001051"  (or uses input card)          │
│  Bot shows ⏳ working card → flips to 📋 summary card       │
└────────────────────┬────────────────────────────────────────┘
                     │  Webex Webhook (HTTPS POST)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               AWS API GATEWAY (HTTPS)                       │
│         Permanent public URL for Webex webhooks             │
└────────────────────┬────────────────────────────────────────┘
                     │  Lambda event (JSON)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS LAMBDA + MANGUM                             │
│         (lambda_handler.py → Mangum → FastAPI)              │
│                                                             │
│  POST /webhook/webex            ← Receives Webex messages   │
│  POST /webhook/webex/card-action← Handles card submissions  │
│  GET  /                         ← Bot running status        │
│  GET  /debug-env                ← Env var verification      │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────────────┐    ┌─────────────────────────────┐
│     SERVICENOW API       │    │      CISCO CIRCUIT LLM      │
│                          │    │                             │
│  sn_customerservice_case │    │  Step 1: OAuth2 token       │
│  → case record + sys_id  │    │   → id.cisco.com            │
│                          │    │                             │
│  sys_journal_field       │    │  Step 2: Chat completion    │
│  → comments + work_notes │    │   → chat-ai.cisco.com       │
│                          │    │   Model: gpt-4o-mini        │
│  sys_email               │    │   Temp: 0.0 (deterministic) │
│  → case emails           │    └─────────────────────────────┘
└──────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  FORMATTER (formatter.py)        │
│  Merges + sorts all entries into │
│  a unified chronological timeline│
│  (emails, comments, work notes)  │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  SUMMARIZER (summarizer.py)      │
│  Builds structured AI prompt     │
│  Calls Circuit LLM               │
│  Returns fixed-format summary    │
└──────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────┐
│  CARD FLIP (background thread)   │
│  PATCH /messages/{id}            │
│  Replaces ⏳ card with 📋 summary│
└──────────────────────────────────┘
```

---

## 5. Project Structure

```
summary-agent/
├── app.py                  # Main FastAPI app — routes, webhook logic, card management
├── config.py               # Loads all environment variables from .env
├── formatter.py            # Merges journal entries + emails into sorted timeline
├── servicenow_client.py    # ServiceNow REST API — case, journal, email fetching
├── summarizer.py           # Circuit LLM OAuth2 + prompt builder + AI call
├── lambda_handler.py       # AWS Lambda entry point (Mangum — wraps FastAPI)
├── Dockerfile              # Docker image for AWS Lambda deployment
├── .dockerignore           # Files excluded from Docker build context
├── requirements.txt        # Python package dependencies
├── .env                    # Configuration & secrets (gitignored, not committed)
├── LAMBDA_DEPLOY.md        # Step-by-step AWS Lambda deployment guide
├── POC_OVERVIEW.md         # This file — full architecture & code walkthrough
├── TOOLS_EXPLAINED.md      # Every tool and library explained
└── TEAM_MEETING.md         # Team presentation notes
```

---

## 6. Layer-by-Layer Code Explanation

### Layer 1 — Configuration (`config.py`)

**What it does:**
Loads all secrets and configuration values from the `.env` file into Python variables at startup using `python-dotenv`.

**Key variables:**

| Variable | Purpose |
|----------|---------|
| `SERVICENOW_INSTANCE` | ServiceNow hostname (e.g. `dev12345.service-now.com`) |
| `SERVICENOW_USERNAME` | ServiceNow API credentials |
| `SERVICENOW_PASSWORD` | ServiceNow API credentials |
| `WEBEX_BOT_TOKEN` | Webex Bot API bearer token |
| `WEBEX_BOT_EMAIL` | Bot's own email — used to prevent self-message loops |
| `CIRCUIT_CLIENT_ID` | Cisco Circuit LLM OAuth2 client ID |
| `CIRCUIT_CLIENT_SECRET` | Cisco Circuit LLM OAuth2 secret |
| `CIRCUIT_APP_KEY` | Cisco Circuit LLM app registration key |
| `CIRCUIT_MODEL` | LLM model name (default: `gpt-4o-mini`) |
| `CIRCUIT_TOKEN_URL` | OAuth2 token endpoint (default: `https://id.cisco.com/oauth2/default/v1/token`) |
| `CIRCUIT_CHAT_BASE_URL` | Circuit LLM base URL (default: `https://chat-ai.cisco.com/openai/deployments`) |

---

### Layer 2 — ServiceNow Client (`servicenow_client.py`)

**What it does:**
Makes authenticated REST API calls to ServiceNow to retrieve case data, journal entries, and case emails.

**Functions:**

`get_case_by_number(case_number)`
- Calls: `GET /api/now/table/sn_customerservice_case`
- Fetches: `sys_id`, `number`, `case`, `short_description`, `description`, `state`, `priority`, `severity`, `assignment_group`, `assigned_to`, timestamps
- Uses `sysparm_display_value=all` to get human-readable values alongside raw values
- Returns the first matching case record as a Python dict, or `None`

`get_case_journal_entries(sys_id)`
- Calls: `GET /api/now/table/sys_journal_field`
- Fetches all `comments` (customer-visible) and `work_notes` (internal engineer notes) ordered chronologically
- **Fallback:** if the primary `element_id` query returns empty, retries using `documentkey` (handles different ServiceNow instance configurations)

`get_case_emails(sys_id)`
- Calls: `GET /api/now/table/sys_email`
- Fetches emails linked to the case, filtered by `instance={sys_id}` and `target_table=sn_customerservice_case` to avoid pulling unrelated emails
- Returns: `sys_id`, `sys_created_on`, `type`, `subject`, `body`, `body_text`, `recipients`

**Authentication:** HTTP Basic Auth over HTTPS

---

### Layer 3 — Formatter (`formatter.py`)

**What it does:**
Transforms raw ServiceNow data (journal entries + emails) into a clean, unified, chronologically sorted timeline ready for the AI prompt.

**Functions:**

| Function | Purpose |
|----------|---------|
| `clean_text(text)` | Strips newlines, collapses extra whitespace |
| `to_iso(ts)` | Converts ServiceNow `YYYY-MM-DD HH:MM:SS` to ISO 8601 (`Z` suffix) |
| `map_speaker(element)` | Maps `comments` → `customer`, `work_notes` → `support_engineer`, `email` → `customer` |
| `map_type(element)` | Maps element to `comment`, `work_note`, or `email` |
| `build_timeline(journal_entries, email_entries)` | Merges both sources, sorts by timestamp ascending |

**Output format per timeline entry:**
```python
{
  "type":      "work_note",
  "source":    "work_notes",
  "speaker":   "support_engineer",
  "timestamp": "2026-03-29T02:05:25Z",
  "text":      "Checked logs — missing dependency confirmed"
}
```

The merged, sorted timeline means the LLM sees all events in true chronological order regardless of source.

---

### Layer 4 — Summarizer (`summarizer.py`)

**What it does:**
Builds the AI prompt from case data + timeline, authenticates with Cisco Circuit LLM via OAuth2, calls the LLM, and returns the structured summary string.

**Custom exception:** `CircuitLLMError` — raised when token fetch or chat completion fails, so the caller can handle it gracefully.

**Functions:**

`_get_display_value(data, field, default)`
- Safely extracts a field from the ServiceNow case record
- Handles nested dict format (`{"display_value": "...", "value": "..."}`)
- Returns `default` (`"Not explicitly mentioned"`) if field is missing or empty

`build_prompt(case_data, timeline)`
- Constructs a detailed, instruction-guided prompt
- Splits timeline into three labelled sections: **Customer Emails**, **Customer Comments**, **Internal Work Notes**
- Each timeline entry is numbered and formatted as: `N. [timestamp] speaker: text`
- Strict rules injected: no PII, no invention, collapse repetition, max 5 key-event bullets
- Returns output in a **fixed format** (no markdown fences):
  ```
  Summary for CS...
  Issue:
  What happened:
  What was tried:
  Current status:
  Next steps:
  ```

`get_access_token()`
- POSTs to `CIRCUIT_TOKEN_URL` with `grant_type=client_credentials`
- Encodes `client_id:client_secret` as Base64 for HTTP Basic Auth
- Returns a short-lived Bearer access token
- Raises `CircuitLLMError` if credentials are missing or token is absent from response

`call_circuit_llm(prompt)`
- Calls: `{CIRCUIT_CHAT_BASE_URL}/{CIRCUIT_MODEL}/chat/completions`
- Uses `api-key` header (not `Authorization: Bearer`) — Circuit LLM specific
- Passes `CIRCUIT_APP_KEY` as `json.dumps({"appkey": ...})` in the `user` field
- Sets `temperature: 0.0` for deterministic, repeatable summaries
- Handles both standard `choices[0].message.content` and fallback response shapes

`summarize_case_with_llm(case_data, timeline)`
- Orchestrator: `build_prompt()` → `call_circuit_llm()` → returns summary string
- On any exception: logs the error and returns `"Summary generation failed. Please try again."`

---

### Layer 5 — Application (`app.py`)

**What it does:**
The main FastAPI application. Handles all Webex webhook events, manages Adaptive Card lifecycle (send → working → summary → flip), orchestrates the full summarization pipeline, and prevents bot message loops.

**Bot Loop Prevention — `is_bot_message(email)`**

Defined at module level using `BOT_EMAIL_LOWER = (WEBEX_BOT_EMAIL or "").lower()`. Catches bot messages via four checks:
1. Exact match against `BOT_EMAIL_LOWER` (env var match)
2. Email ends with `.bot` (e.g. `jansi-test@webex.bot`)
3. Contains `@webex.bot`
4. Contains `bot@webex` or `bot@cisco`

This is robust even if the env var is wrong or missing.

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Returns bot running status message |
| `/debug-env` | GET | Shows whether `WEBEX_BOT_TOKEN` is set and the value of `WEBEX_BOT_EMAIL` |
| `/webhook/webex` | POST | Receives all Webex message events |
| `/webhook/webex/card-action` | POST | Receives Webex Adaptive Card button submissions |

**HTTP Helper — `_request(method, url, max_retries=3)`**
- Wraps all outbound HTTP calls
- 3 attempts with exponential backoff (1.5s × attempt)
- Returns `None` on 404 (rather than raising) — prevents crashes on deleted messages
- Raises on all other errors after retries exhausted

**Card Helpers:**

| Function | Purpose |
|----------|---------|
| `send_card(room_id, card, fallback_text)` | Sends a new card message, returns `message_id` |
| `replace_card(message_id, card, fallback_text)` | PATCHes an existing card in-place |
| `send_text(room_id, text)` | Sends a plain text message |
| `_welcome_card(user_email)` | Builds the 👋 welcome card (shown once per room on first contact) with "Get Started" button |
| `_input_card(title, subtitle)` | Builds the 🔍 input form card (text field + Summarize + Cancel) |
| `_working_card(case_number)` | Builds the ⏳ spinner card shown while LLM processes |
| `_summary_card(case_number, summary_text)` | Builds the 📋 result card (truncated to 2000 chars) with "Summarize another" + "Close" buttons |

**Welcome Flow — `_maybe_send_welcome(room_id, user_email)`**
- Tracks rooms in an in-memory `welcomed_rooms` set
- Sends the welcome card **once** per room per server session
- On server restart the set resets — users get a re-welcome (harmless)
- Greets user by name (extracted from email local part, e.g. "jgorle")

**Background Thread — `_summarize_and_flip(room_id, case_number, card_message_id)`**
- Runs the full `get_summary()` pipeline in a daemon thread so the webhook returns `200 OK` immediately
- When summary is ready, calls `replace_card()` to PATCH the ⏳ working card with the 📋 summary card
- If no `card_message_id` (edge case), sends a new card instead

**Webex Webhook Registration:**

Two webhooks must be registered with the Webex API pointing to your deployment URL:

| Webhook Name | Resource | Event | Target Endpoint |
|-------------|----------|-------|-----------------|
| `summary-agent-messages` | `messages` | `created` | `/webhook/webex` |
| `summary-agent-card-actions` | `attachmentActions` | `created` | `/webhook/webex/card-action` |

The bot uses an **org-wide webhook** — it receives events for all DMs in the org, but can only read/reply in rooms where it is already a member. Users must open a direct message with the bot to start using it.

**Webhook Message Flow (`/webhook/webex`):**

```
1. Receive Webex event → extract message_id, room_id, parentId, person_email
2. Ignore if missing message_id or room_id
3. Ignore if is_bot_message(person_email) — outer payload check
4. Ignore if parentId present — thread replies are skipped
5. Fetch full message from Webex API (returns None/404 if bot not in room)
6. Ignore if is_bot_message(fetched_email) — fetched message check
7. Ignore if text matches "Summary for CS..." — bot summary echo guard
8. Ignore if text is a known bot card fallback phrase (BOT_FALLBACK_PHRASES set)
9. Route message:
   a. Send 👋 welcome card if first contact in this room (one-time per session)
   b. If "exit/quit/close" → send goodbye text
   c. If text is exactly a case number (e.g. CS0001051) → send ⏳ card → background thread
   d. If text starts with "summarize" + has case number → send ⏳ card → background thread
   e. Otherwise → show 🔍 input card
```

**Card Action Flow (`/webhook/webex/card-action`):**

```
1. Receive card submission → extract action_id, room_id, person_email, card_message_id
2. Ignore if missing action_id or room_id
3. Ignore if is_bot_message(person_email)
4. Fetch action details from Webex API (returns inputs + action name)
5. action = "open_input_card" → replace/send input card (from welcome or summary card)
6. action = "exit_menu"       → send goodbye text ("Closed ✅")
7. action = "close_summary"   → replace/send input card
8. action = "summarize_case"  → validate case number
   → valid:   replace card with ⏳ working card → start background thread
   → invalid: replace/send input card with ⚠️ error subtitle
9. Unknown action → log and ignore
```

---

### Layer 6 — AWS Lambda Deployment (`lambda_handler.py` + `Dockerfile`)

**What it does:**
Packages the entire FastAPI application into a Docker container image that runs as an AWS Lambda function behind API Gateway, providing a permanent public HTTPS endpoint for Webex webhooks.

**Why Lambda instead of ngrok?**
- ngrok is **blocked on the Cisco corporate network**
- ngrok URLs change every restart — Lambda provides a **permanent URL**
- Lambda is **always available** (no need to keep a laptop open)
- Lambda **auto-scales** and costs near-zero for this use case

**Lambda Handler (`lambda_handler.py`):**
```python
from mangum import Mangum
from app import app
handler = Mangum(app, lifespan="off")
```

Mangum converts API Gateway events into ASGI requests that FastAPI understands. The `handler` function is what Lambda invokes for every incoming HTTP request.

**Docker Image:**
- Base: `public.ecr.aws/lambda/python:3.13` (AWS official Lambda runtime)
- Installs all dependencies from `requirements.txt`
- Copies all `.py` source files
- Entry point: `lambda_handler.handler`
- Image size: ~191 MB

**Deployment Flow:**
```
Docker build → Push to ECR → Create Lambda from image
  → Attach API Gateway → Register Webex webhooks
```

---

## 7. Technologies Used

| Technology | Category | Why Used |
|-----------|----------|----------|
| **Python 3.13** | Language | Core development language |
| **FastAPI** | Web framework | High-performance async API server with auto docs |
| **uvicorn** | ASGI server | Runs the FastAPI app locally during development |
| **Mangum** | Lambda adapter | Converts API Gateway events ↔ ASGI requests for Lambda |
| **Docker** | Containerization | Packages app into AWS Lambda container image |
| **AWS Lambda** | Serverless compute | Runs the app in the cloud — always available, auto-scaling |
| **AWS API Gateway** | HTTPS endpoint | Permanent public URL for Webex webhooks |
| **requests** | HTTP client | REST calls to ServiceNow, Webex, Circuit LLM |
| **python-dotenv** | Config management | Loads secrets from `.env` — no hardcoded credentials |
| **pydantic** | Validation | Validates incoming request data |
| **threading** | Concurrency | Background thread for LLM call — keeps webhook response fast |
| **base64** | Encoding | Encodes credentials for Circuit LLM OAuth2 Basic Auth header |
| **json** | Serialization | Encodes Circuit LLM `appkey` metadata in `user` field |
| **re** | Regex | Case number extraction and bot echo detection |
| **Cisco Circuit LLM** | AI/LLM | Internal Cisco AI platform — generates case summaries |
| **Webex Bot API** | Messaging | Sends/receives messages and manages cards in Webex spaces |
| **ServiceNow REST API** | Data source | Fetches case records, journal entries, and case emails |
| **Adaptive Cards** | UI | Interactive cards in Webex — input form, working spinner, summary display |
| **ngrok** | Dev tunneling | ❌ Replaced by AWS Lambda — was blocked on Cisco corporate network |

---

## 8. Data Flow — End to End

```
1. Engineer types "CS0001051" in Webex space
          │
2. Webex sends POST → API Gateway → Lambda → /webhook/webex
          │
3. app.py validates event (not bot, not thread reply)
          │
4. app.py sends ⏳ "Generating summary…" card → returns 200 OK immediately
          │
5. Background thread starts:
          │
6. servicenow_client.py → GET sn_customerservice_case
   → case title, state, description, priority, group, sys_id
          │
7. servicenow_client.py → GET sys_journal_field (with fallback)
   → comments + work_notes (chronological)
          │
8. servicenow_client.py → GET sys_email
   → emails linked to the case
          │
9. formatter.py merges + sorts all entries into unified timeline
   → [{ type, speaker, timestamp, text }, ...]
          │
10. summarizer.py builds structured prompt
    (case details + emails + comments + work notes sections)
          │
11. summarizer.py → POST id.cisco.com → OAuth2 access token
          │
12. summarizer.py → POST chat-ai.cisco.com/gpt-4o-mini
    → AI-generated structured summary (temperature=0.0)
          │
13. app.py PATCHes the ⏳ working card → replaced with 📋 summary card
    Engineer sees: Issue / What happened / What was tried / Status / Next steps
          │
14. Engineer clicks "Summarize another case" → input card replaces summary card
```

---

## 9. Sample Output

**Input:** Engineer types `CS0001051` in Webex

**Bot Response (as Adaptive Card):**
```
📋 Summary — CS0001051

Summary for CS0001051

Issue:
The customer reports that WhatsApp messages are not being delivered
since the previous day.

What happened:
- Customer reported delivery failures for all WhatsApp messages
- Engineer reviewed Meta API logs
- Meta API returning error code 131047 on message delivery calls
- Engineer escalated to platform team for investigation

What was tried:
- Reviewed Meta API logs and identified error code 131047
- Escalated to platform team

Current status:
Case is open and under active investigation by the platform team.
Error code 131047 has been identified as the root cause.

Next steps:
- Platform team to confirm fix timeline with Meta
```

---

## 10. Security Considerations

| Item | Approach |
|------|----------|
| Credentials storage | All secrets in `.env` file, never in source code |
| `.env` committed to git | No — `.gitignore` excludes `.env` |
| ServiceNow auth | HTTP Basic Auth over HTTPS |
| Circuit LLM auth | OAuth2 client credentials — short-lived Bearer token fetched per call |
| Webex bot loop prevention | `is_bot_message()` checks email domain, exact match, and known bot patterns |
| Bot echo prevention | Additional checks for summary text patterns and card fallback phrases |
| Thread replies | `parentId` check ensures bot ignores replies to its own messages |
| SSL/TLS | All API calls use HTTPS |
| PII in summaries | LLM prompt explicitly instructs: never include email addresses or personal names |

---

## 11. Current State & Limitations

### ✅ Working
- FastAPI server with all endpoints
- ServiceNow case record fetching
- ServiceNow journal entries (comments + work notes) with `documentkey` fallback
- ServiceNow case email fetching (`sys_email`)
- Unified timeline formatter (journal + email, chronologically sorted)
- Circuit LLM OAuth2 token fetch
- Circuit LLM chat completions with deterministic temperature
- Webex message receiving and bot loop prevention (`is_bot_message`)
- Adaptive Card UI: input card → working card → summary card (in-place PATCH)
- Background thread — webhook returns `200 OK` immediately while LLM processes
- Card actions: `summarize_case`, `open_input_card`, `exit_menu`, `close_summary`
- Retry logic (3 attempts, exponential backoff) on all outbound HTTP calls
- 404-safe message/action fetching (returns `None` instead of crashing)
- Docker image built and tested locally (GET / → 200 OK)
- Lambda handler with Mangum wrapping FastAPI
- Code pushed to GitHub: [GorleJansi/summary_agent](https://github.com/GorleJansi/summary_agent)

### ⏳ Pending (Awaiting AWS Access)
- Push Docker image to AWS ECR
- Create Lambda function from ECR image
- Attach API Gateway for permanent HTTPS URL
- Set Lambda environment variables (all `.env` values)
- Register Webex webhooks with API Gateway URL

### 🔜 Future Enhancements
- Add Webex webhook secret validation (HMAC signature check on incoming payloads)
- Cache Circuit LLM OAuth2 token with expiry refresh (avoid token fetch on every call)
- Add structured logging to file (rotate daily)
- Add unit tests for formatter, summarizer, and bot-ignore logic
- Add rate limiting per user/room to prevent abuse

---

## 12. How to Run

### Option A — Local Development

```bash
# 1. Clone the repo
git clone https://github.com/GorleJansi/summary_agent.git
cd summary_agent

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file and fill in credentials
# (See config.py for all required variables)

# 5. Start the FastAPI server
uvicorn app:app --reload
# Server runs at http://127.0.0.1:8000

# 6. Verify the bot is running
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/debug-env
```

### Option B — Docker (Local Lambda Simulation)

```bash
# 1. Build the Docker image
docker build -t summary-agent:latest .

# 2. Run locally (simulates Lambda)
docker run --rm -p 9000:8080 --env-file .env summary-agent:latest

# 3. Test
curl http://localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"httpMethod":"GET","path":"/"}'
```

### Option C — AWS Lambda (Production)

```bash
# 1. Push image to ECR
aws ecr get-login-password --region <REGION> | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
docker tag summary-agent:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/summary-agent:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/summary-agent:latest

# 2. Create Lambda from ECR image (via Console or CLI)
# 3. Attach API Gateway (HTTP API)
# 4. Set environment variables on Lambda
# 5. Register Webex webhooks:
#    POST https://webexapis.com/v1/webhooks
#    - targetUrl: https://<api-gateway-url>/webhook/webex
#    - targetUrl: https://<api-gateway-url>/webhook/webex/card-action
```

See **[LAMBDA_DEPLOY.md](LAMBDA_DEPLOY.md)** for the full step-by-step deployment guide.

---

## 13. Dependencies (`requirements.txt`)

```
fastapi
uvicorn
requests
python-dotenv
pydantic
mangum
```

All other modules used (`base64`, `json`, `re`, `os`, `time`, `threading`, `typing`) are part of Python's standard library — no additional installation required.

---

## 14. Repository

**GitHub:** [https://github.com/GorleJansi/summary_agent](https://github.com/GorleJansi/summary_agent)

**Author:** Jansi Gorle — jgorle@cisco.com
