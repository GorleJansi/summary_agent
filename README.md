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
| uvicorn | ASGI server (local dev) |
| Mangum | ASGI → AWS Lambda adapter |
| Docker | Container packaging for Lambda deployment |
| AWS Lambda + API Gateway | Serverless cloud hosting (production) |

---

## Project Structure

```
summary-agent/
├── app.py                # FastAPI app — all routes and webhook logic
├── config.py             # Loads environment variables
├── formatter.py          # Builds structured timeline from journal entries
├── servicenow_client.py  # ServiceNow API calls
├── summarizer.py         # Circuit LLM prompt + API call
├── lambda_handler.py     # AWS Lambda entry point (Mangum wrapper)
├── Dockerfile            # Docker image for AWS Lambda deployment
├── .dockerignore         # Files excluded from Docker build
├── requirements.txt      # Dependencies
├── .env                  # Secrets (not committed)
├── LAMBDA_DEPLOY.md      # AWS Lambda deployment guide
├── POC_OVERVIEW.md       # Full architecture & code walkthrough
├── TOOLS_EXPLAINED.md    # Every tool/library explained
└── TEAM_MEETING.md       # Team presentation notes
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
curl http://127.0.0.1:8000/
```

---

## Deployment (AWS Lambda via Docker)

This app is production-ready for **AWS Lambda + API Gateway** — no ngrok needed.

### Build & test the Docker image locally
```bash
docker build -t summary-agent:latest .
docker run --rm -p 9000:8080 --env-file .env summary-agent:latest
curl http://localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"httpMethod":"GET","path":"/"}'
```

### Deploy to AWS
```bash
# Authenticate with ECR
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

# Tag and push
docker tag summary-agent:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/summary-agent:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/summary-agent:latest

# Then: Create Lambda from ECR image → attach API Gateway → register Webex webhooks
```

See **[LAMBDA_DEPLOY.md](LAMBDA_DEPLOY.md)** for the full step-by-step deployment guide.

---

## Webex Webhook Registration

After deploying to AWS, register two webhooks with the Webex API:

```bash
# 1. Messages webhook (fires when a user sends a message to the bot)
curl -X POST https://webexapis.com/v1/webhooks \
  -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summary-agent-messages",
    "targetUrl": "https://<API_GATEWAY_URL>/webhook/webex",
    "resource": "messages",
    "event": "created"
  }'

# 2. Card actions webhook (fires when a user clicks a button on an Adaptive Card)
curl -X POST https://webexapis.com/v1/webhooks \
  -H "Authorization: Bearer $WEBEX_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summary-agent-card-actions",
    "targetUrl": "https://<API_GATEWAY_URL>/webhook/webex/card-action",
    "resource": "attachmentActions",
    "event": "created"
  }'
```

| Webhook | Resource | Event | Target Endpoint |
|---------|----------|-------|-----------------|
| Messages | `messages` | `created` | `/webhook/webex` |
| Card Actions | `attachmentActions` | `created` | `/webhook/webex/card-action` |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Bot running status |
| `/debug-env` | GET | Verify env vars loaded + welcomed room count |
| `/webhook/webex` | POST | Webex message webhook (receives new messages) |
| `/webhook/webex/card-action` | POST | Webex Adaptive Card button/form submissions |

---

## Author

**Jansi Gorle** — jgorle@cisco.com

## Repository

[https://github.com/GorleJansi/summary_agent](https://github.com/GorleJansi/summary_agent)
