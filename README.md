# Summary Agent

A Proof of Concept (POC) AI-powered Webex Bot that automatically summarizes ServiceNow customer service cases using Cisco's internal Circuit LLM.

---

## What It Does

- Engineer types a case number (e.g. `CS0001051`) in a Webex space
- Bot fetches the case details and full conversation history from ServiceNow
- Sends it to Cisco Circuit LLM (GPT-4o-mini) for AI summarization
- Returns a structured summary back to Webex — in seconds

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.13 | Core language |
| FastAPI | REST API server |
| ServiceNow REST API | Fetches case data and journal entries |
| Cisco Circuit LLM | AI summarization (OAuth2 + GPT-4o-mini) |
| Webex Bot API | Sends/receives messages and Adaptive Cards |
| python-dotenv | Environment variable management |
| uvicorn | ASGI server |
| ngrok | Local tunnel for webhook testing |

---

## Project Structure

```
summary-agent/
├── app.py                # FastAPI app — all routes and webhook logic
├── config.py             # Loads environment variables
├── formatter.py          # Builds structured timeline from journal entries
├── servicenow_client.py  # ServiceNow API calls
├── summarizer.py         # Circuit LLM prompt + API call
├── requirements.txt      # Dependencies
└── .env                  # Secrets (not committed)
```

---

## Getting Started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```
SERVICENOW_INSTANCE=your-instance.service-now.com
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
WEBEX_BOT_TOKEN=your-webex-bot-token
WEBEX_BOT_EMAIL=your-bot@webex.bot
CIRCUIT_CLIENT_ID=your-client-id
CIRCUIT_CLIENT_SECRET=your-client-secret
CIRCUIT_APP_KEY=your-app-key
CIRCUIT_MODEL=gpt-4o-mini
```

### 3. Run the server
```bash
uvicorn app:app --reload
```

### 4. Test
```bash
curl http://127.0.0.1:8000/health
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/` | GET | Bot status |
| `/debug-env` | GET | Verify env vars loaded |
| `/webhook/webex` | POST | Webex message webhook |
| `/webhook/webex/card-action` | POST | Webex card form submissions |

---

## Author

**Jansi Gorle** — jgorle@cisco.com
