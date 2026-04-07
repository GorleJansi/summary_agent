# Tools Explained — All Tools & Libraries Used in This Project

---

## uvicorn

### What is it?
**uvicorn** is a lightweight, high-performance **web server** for Python.
It runs your FastAPI application and makes it listen for HTTP requests on a port (default: 8000).

### Why do we need it?
FastAPI is just Python code — it can't receive HTTP requests on its own.
uvicorn is the engine that starts the server, binds to a port, and passes each incoming request to your FastAPI app.

### Analogy
> Think of FastAPI as the kitchen (does the cooking), and uvicorn as the restaurant door (lets people in).

### How we use it

```bash
# Start the server
uvicorn app:app --reload
```

| Part | Meaning |
|------|---------|
| `uvicorn` | The server program |
| `app` | The filename (`app.py`) |
| `:app` | The FastAPI object inside that file (`app = FastAPI()`) |
| `--reload` | Auto-restart when you save any file (development mode only) |

### What happens when you run it

```
uvicorn starts
    └── Binds to http://127.0.0.1:8000
    └── Loads app.py
    └── Waits for HTTP requests
    └── Forwards each request to FastAPI
    └── Returns the response
```

### In production
In a deployed environment (cloud server), uvicorn runs without `--reload` and is typically managed by a process manager like `gunicorn` or `systemd`.

```bash
# Production style
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## ngrok

### What is it?
**ngrok** is a **reverse tunnel** tool. It creates a secure public HTTPS URL that forwards traffic to your local machine.

### Why do we need it?
Our FastAPI server runs on `http://127.0.0.1:8000` — this address only works **on your own laptop**.

The Webex Bot webhook needs to send HTTP POST requests to our server whenever a user sends a message. But Webex is on the internet and **cannot reach your laptop's localhost**.

ngrok bridges this gap by giving your local server a public URL.

### Analogy
> Think of your laptop as a house with no street address. ngrok gives it a temporary address so delivery trucks (Webex) can find it.

### How we use it

```bash
# Expose local port 8000 to the internet
ngrok http 8000
```

**Output from ngrok:**
```
Forwarding  https://abc123.ngrok-free.app -> http://127.0.0.1:8000
```

Now `https://abc123.ngrok-free.app/webhook/webex` is publicly accessible and forwards to your local FastAPI app.

### How traffic flows with ngrok

```
User types "CS0001037" in Webex
        │
        ▼
Webex Bot sends POST to:
https://abc123.ngrok-free.app/webhook/webex
        │
        ▼
ngrok receives it (ngrok cloud servers)
        │
        ▼
ngrok tunnels it to your laptop:
http://127.0.0.1:8000/webhook/webex
        │
        ▼
uvicorn receives it → FastAPI handles it
        │
        ▼
App fetches ServiceNow case → sends reply to Webex
```

### Limitation
- The free ngrok URL **changes every time** you restart ngrok
- You must update the Webex webhook URL each time
- ngrok is **blocked on Cisco corporate network**

### In production
ngrok is **not used in production** and was only used in early development. This project now uses **AWS Lambda + API Gateway** for a permanent public HTTPS endpoint — no tunnel needed. See the [Mangum](#mangum) and [Docker / AWS Lambda](#docker--aws-lambda) sections below.

---

## Side-by-Side Comparison

| | uvicorn | ngrok | Mangum + Lambda |
|---|---------|-------|------------------|
| **What it does** | Runs your Python web server locally | Creates a public tunnel to your laptop | Runs your FastAPI app inside AWS Lambda |
| **Where it runs** | On your machine | On your machine + ngrok's cloud | AWS cloud |
| **Port** | 8000 (local only) | Creates public HTTPS URL | API Gateway provides permanent HTTPS URL |
| **Required in production?** | ❌ No (Lambda replaces it) | ❌ No | ✅ Yes |
| **Required in development?** | ✅ Yes | Optional (blocked on Cisco network) | ❌ No |
| **Start command** | `uvicorn app:app --reload` | `ngrok http 8000` | Deployed via Docker image to AWS |

---

## Full Local Dev Setup

```bash
# Just start the server — no ngrok needed if using Lambda in production
uvicorn app:app --reload

# Server runs at http://127.0.0.1:8000
# Test: curl http://127.0.0.1:8000/
```

For **production**, the app runs as an AWS Lambda function behind API Gateway. Register the API Gateway URL as the Webex Bot webhook:
- `https://<api-gateway-url>/webhook/webex` — for messages
- `https://<api-gateway-url>/webhook/webex/card-action` — for card submissions

---

## FastAPI

### What is it?
**FastAPI** is the Python **web framework** used to build this application. It lets you define API endpoints (routes) using simple Python functions.

### Why do we use it?
- Very fast and easy to write
- Automatically generates interactive API docs at `/docs`
- Built-in request validation using Pydantic
- Used by Webex, ServiceNow webhooks to receive and respond to HTTP requests

### How we use it

```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"message": "ServiceNow + Webex case-summary bot is running ✅"}
```

### Analogy
> FastAPI is the **brain** of the app — it decides what to do when a request comes in.

---

## requests

### What is it?
**requests** is a Python library for making **HTTP calls** to external APIs.

### Why do we use it?
We use it to talk to three external services:
1. **ServiceNow REST API** — fetch case details, journal entries, and case emails
2. **Webex API** — fetch message content, send replies, send/replace Adaptive Cards
3. **Cisco Circuit LLM** — fetch OAuth2 access token and call the chat completions endpoint

### How we use it

```python
import requests
response = requests.get("https://dev181123.service-now.com/api/now/table/sn_customerservice_case", auth=("admin", "password"))
data = response.json()
```

### Analogy
> `requests` is the **phone** your app uses to call ServiceNow and Webex.

---

## python-dotenv

### What is it?
**python-dotenv** loads environment variables from a `.env` file into your Python app.

### Why do we use it?
We store secrets (passwords, API keys, tokens) in a `.env` file so they are:
- Not hardcoded in the source code
- Not accidentally committed to git
- Easy to change without modifying code

### Our `.env` file
```
SERVICENOW_INSTANCE=https://dev181123.service-now.com
SERVICENOW_USERNAME=admin
SERVICENOW_PASSWORD=...
WEBEX_BOT_TOKEN=...
WEBEX_BOT_EMAIL=jansi-test@webex.bot
CIRCUIT_CLIENT_ID=...
CIRCUIT_CLIENT_SECRET=...
CIRCUIT_APP_KEY=...
CIRCUIT_MODEL=gpt-4o-mini
```

### How we use it

```python
from dotenv import load_dotenv
import os
load_dotenv()
password = os.getenv("SERVICENOW_PASSWORD")
```

### Analogy
> `.env` is a **locked safe** for your secrets. `python-dotenv` is the key that opens it when the app starts.

---

## Mangum

### What is it?
**Mangum** is a Python library that wraps ASGI applications (like FastAPI) so they can run inside **AWS Lambda**.

### Why do we need it?
AWS Lambda expects a specific handler function that receives an event and returns a response. FastAPI is an ASGI web framework that expects HTTP requests. Mangum bridges this gap — it converts API Gateway events into ASGI requests that FastAPI understands, and converts FastAPI's responses back into the format Lambda expects.

### How we use it

```python
# lambda_handler.py
from mangum import Mangum
from app import app

handler = Mangum(app, lifespan="off")
```

| Part | Meaning |
|------|--------|
| `app` | The FastAPI instance from `app.py` |
| `lifespan="off"` | Disables startup/shutdown events (not needed in Lambda) |
| `handler` | The function AWS Lambda calls for every request |

### How it works

```
User sends message in Webex
     │
     ▼
Webex webhook → API Gateway receives HTTPS POST
     │
     ▼
API Gateway translates to Lambda event JSON
     │
     ▼
Lambda invokes handler() (Mangum)
     │
     ▼
Mangum converts event → ASGI request → FastAPI handles it
     │
     ▼
FastAPI response → Mangum converts back → API Gateway → HTTPS response
```

### Analogy
> Mangum is the **interpreter** between AWS Lambda (speaks event JSON) and FastAPI (speaks HTTP). Neither can understand each other without it.

---

## Docker / AWS Lambda

### What is Docker?
**Docker** packages your application and all its dependencies into a single **container image** that runs identically everywhere.

### Why do we use Docker?
AWS Lambda supports deploying functions as Docker container images. We package our entire FastAPI app into a Docker image based on AWS's official Python 3.13 Lambda base image.

### Our Dockerfile

```dockerfile
FROM public.ecr.aws/lambda/python:3.13

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY app.py config.py formatter.py servicenow_client.py \
     summarizer.py lambda_handler.py ${LAMBDA_TASK_ROOT}/

CMD ["lambda_handler.handler"]
```

| Part | Meaning |
|------|--------|
| `FROM public.ecr.aws/lambda/python:3.13` | AWS-optimized Python 3.13 base image for Lambda |
| `LAMBDA_TASK_ROOT` | The directory Lambda looks in for your code (`/var/task`) |
| `CMD ["lambda_handler.handler"]` | Tells Lambda to call `handler()` in `lambda_handler.py` |

### Build & test locally

```bash
# Build the image
docker build -t summary-agent:latest .

# Test locally (simulates Lambda runtime)
docker run --rm -p 9000:8080 --env-file .env summary-agent:latest

# Send a test request
curl http://localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"httpMethod":"GET","path":"/"}'
```

### Deploy to AWS

```bash
# 1. Push to ECR (Elastic Container Registry)
aws ecr get-login-password --region <REGION> | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

docker tag summary-agent:latest <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/summary-agent:latest
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/summary-agent:latest

# 2. Create Lambda function from ECR image
# 3. Attach API Gateway (HTTP API) for public HTTPS URL
# 4. Register Webex webhooks pointing to the API Gateway URL
```

### Why Lambda instead of ngrok?

| | ngrok | AWS Lambda |
|---|-------|------------|
| **URL** | Changes every restart | Permanent API Gateway URL |
| **Cost** | Free tier limited | Pay per request (very cheap) |
| **Corporate network** | Blocked by Cisco | Works everywhere |
| **Uptime** | Only while laptop is open | Always available |
| **Scaling** | Single laptop | Auto-scales to thousands of requests |

### Analogy
> Docker is the **shipping container** — everything the app needs is packed inside. AWS Lambda is the **warehouse** — it stores and runs the container whenever a request arrives, and you only pay for the seconds it's running.

---

## pydantic

### What is it?
**pydantic** is a Python data validation library. FastAPI uses it internally to validate incoming request bodies and serialize responses.

### Why do we use it?
FastAPI depends on pydantic for all JSON parsing and response serialization. When our webhook endpoints (`/webhook/webex`, `/webhook/webex/card-action`) receive POST requests, pydantic ensures the JSON bodies are valid — and returns a clear `422 Unprocessable Entity` error if not.

### How we use it

FastAPI uses pydantic behind the scenes automatically. Every `return {"status": "ok"}` from a route is validated and serialized by pydantic.

```python
# FastAPI + pydantic validate the request and response automatically
@app.post("/webhook/webex")
async def webex_webhook(request: Request):
    body = await request.json()  # pydantic validates JSON structure
    ...
    return {"status": "ok"}     # pydantic serializes the response
```

### Analogy
> Pydantic is the **security guard** at the API door — checks every request and response has the right format.

---

## base64

### What is it?
Built-in Python module that encodes/decodes data in Base64 format.

### Why do we use it?
The Cisco Circuit LLM OAuth2 token endpoint requires **HTTP Basic Authentication**. This means we must encode `client_id:client_secret` as a Base64 string and send it in the `Authorization` header.

### How we use it

```python
import base64
creds = f"{CIRCUIT_CLIENT_ID}:{CIRCUIT_CLIENT_SECRET}"
encoded = base64.b64encode(creds.encode("utf-8")).decode("utf-8")
headers = {"Authorization": f"Basic {encoded}"}
```

### Analogy
> Base64 is like putting your username and password into a sealed envelope (encoded format) before sending it to the authentication server.

---

## json (Python standard library)

### What is it?
Built-in Python module to encode/decode JSON data.

### Why do we use it?
The Circuit LLM API requires an `appkey` sent as a JSON-encoded string inside the request body's `user` field.

### How we use it

```python
import json
body = {
    "user": json.dumps({"appkey": CIRCUIT_APP_KEY}),
    ...
}
```

### Analogy
> `json` is the translator between Python dictionaries and the JSON strings that APIs understand.

---

## Cisco Circuit LLM (via REST API)

### What is it?
**Cisco Circuit** is the internal enterprise AI/LLM platform used inside Cisco. It provides OpenAI-compatible chat completions API but authenticated with Cisco's own OAuth2 system.

### Why do we use it instead of OpenAI?
- Runs inside Cisco's corporate environment (no public internet data leakage)
- Uses Cisco SSO / OAuth2 — no OpenAI billing needed
- Passes through the Cisco Umbrella proxy without SSL issues
- Model used: `gpt-4o-mini` (configured via `CIRCUIT_MODEL` in `.env`)

### How it works — 2 step flow

**Step 1 — Get access token:**
```
POST https://id.cisco.com/oauth2/default/v1/token
Authorization: Basic base64(client_id:client_secret)
Body: grant_type=client_credentials
→ Returns: { "access_token": "eyJ..." }
```

**Step 2 — Call the LLM:**
```
POST https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions
Headers:
  api-key: <access_token>
  Content-Type: application/json
Body: {
  "messages": [...],
  "user": "{\"appkey\": \"egai-prd-cx-...\"}"
}
→ Returns: { "choices": [{ "message": { "content": "..." } }] }
```

### Key config values in `.env`

| Variable | Value |
|----------|-------|
| `CIRCUIT_CLIENT_ID` | `0oatuvf1hxeWbWSbT5d7` |
| `CIRCUIT_CLIENT_SECRET` | `Dni7MPub...` |
| `CIRCUIT_APP_KEY` | `egai-prd-cx-123212180-summarize-...` |
| `CIRCUIT_MODEL` | `gpt-4o-mini` |
| `CIRCUIT_TOKEN_URL` | `https://id.cisco.com/oauth2/default/v1/token` |
| `CIRCUIT_CHAT_BASE_URL` | `https://chat-ai.cisco.com/openai/deployments` |

### Analogy
> Circuit LLM is like having an internal AI analyst inside Cisco's office — you show them the case, they give you a summary, and everything stays inside the building.

---

## All Tools — Quick Reference

| Tool | Type | Purpose | Required in Prod? |
|------|------|---------|-------------------|
| **FastAPI** | Web framework | Defines API routes and handles requests | ✅ |
| **uvicorn** | ASGI server | Runs the FastAPI app locally on port 8000 | ❌ (Lambda replaces it) |
| **Mangum** | Lambda adapter | Converts API Gateway events ↔ ASGI requests | ✅ |
| **Docker** | Containerization | Packages app into AWS Lambda container image | ✅ (for deployment) |
| **AWS Lambda** | Serverless compute | Runs the app in the cloud, always available | ✅ |
| **API Gateway** | HTTPS endpoint | Permanent public URL for Webex webhooks | ✅ |
| **requests** | HTTP client | Calls ServiceNow, Webex, and Circuit LLM APIs | ✅ |
| **python-dotenv** | Config loader | Loads secrets from `.env` file | ✅ |
| **pydantic** | Validation | Validates incoming API request data | ✅ |
| **base64** | Encoding | Encodes credentials for Circuit LLM Basic Auth | ✅ |
| **json** | Serialization | Encodes `appkey` payload for Circuit LLM | ✅ |
| **Cisco Circuit LLM** | AI backend | Internal Cisco LLM — generates case summaries | ✅ |
| **ngrok** | Tunnel | Gives local server a public HTTPS URL | ❌ (replaced by Lambda) |
