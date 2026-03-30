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
- Fix: Use a paid ngrok plan with a static domain, OR deploy to cloud

### In production
ngrok is **not used in production**. Once deployed to a cloud server (AWS, GCP, Azure, Railway, etc.), the server has a permanent public IP/domain and ngrok is no longer needed.

---

## Side-by-Side Comparison

| | uvicorn | ngrok |
|---|---------|-------|
| **What it does** | Runs your Python web server | Creates a public tunnel to your laptop |
| **Where it runs** | On your machine | On your machine + ngrok's cloud |
| **Port** | 8000 (local only) | Creates public HTTPS URL |
| **Required in production?** | ✅ Yes | ❌ No |
| **Required in development?** | ✅ Yes | ✅ Yes (for Webex webhooks) |
| **Start command** | `uvicorn app:app --reload` | `ngrok http 8000` |

---

## Full Local Dev Setup (both tools together)

```
Terminal 1                          Terminal 2
──────────────────────────────      ──────────────────────────────
$ uvicorn app:app --reload          $ ngrok http 8000

INFO: Uvicorn running on            Forwarding:
      http://127.0.0.1:8000         https://abc123.ngrok-free.app
                                          -> http://127.0.0.1:8000
```

Register `https://abc123.ngrok-free.app/webhook/webex` as the Webex Bot webhook URL, and the full flow works end-to-end from your laptop.

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

@app.get("/health")
def health():
    return {"status": "ok"}
```

### Analogy
> FastAPI is the **brain** of the app — it decides what to do when a request comes in.

---

## requests

### What is it?
**requests** is a Python library for making **HTTP calls** to external APIs.

### Why do we use it?
We use it to talk to two external services:
1. **ServiceNow REST API** — fetch case details and journal entries
2. **Webex API** — fetch message content and send replies back to Webex rooms

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
SN_INSTANCE=https://dev181123.service-now.com
SN_USERNAME=admin
SN_PASSWORD=bmXMd!/WF06y
OPENAI_API_KEY=sk-proj-...
WEBEX_BOT_TOKEN=...
```

### How we use it

```python
from dotenv import load_dotenv
import os
load_dotenv()
password = os.getenv("SN_PASSWORD")
```

### Analogy
> `.env` is a **locked safe** for your secrets. `python-dotenv` is the key that opens it when the app starts.

---

## OpenAI (openai SDK)

### What is it?
The **OpenAI Python SDK** lets you call OpenAI's GPT models (like `gpt-4o-mini`) from Python code.

### Why do we use it?
Instead of writing a manual rule-based summary, we send the case timeline to GPT and get back a human-readable, intelligent summary with:
- Problem Summary
- Actions Taken
- Current Status
- Next Steps

### How we use it

```python
from openai import OpenAI
client = OpenAI(api_key="sk-proj-...")
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)
print(response.choices[0].message.content)
```

### Current status
⚠️ Blocked by `429 insufficient_quota` — OpenAI account needs billing credits at https://platform.openai.com/settings/billing

### Analogy
> OpenAI is the **intelligent analyst** who reads the case and writes a proper summary for you.

---

## httpx

### What is it?
**httpx** is a modern Python HTTP client — similar to `requests` but supports both sync and async, and allows custom SSL configuration.

### Why do we use it?
The OpenAI SDK uses `httpx` internally for all API calls. We also use it directly to pass a **custom SSL certificate bundle** so that OpenAI API calls work through the **Cisco Umbrella corporate proxy**.

### How we use it

```python
import httpx
http_client = httpx.Client(verify="/tmp/macos-combined-certs.pem")
client = OpenAI(api_key="...", http_client=http_client)
```

### Analogy
> `httpx` is the **secure courier** that carries data to OpenAI, with the correct corporate ID badge (SSL cert) to pass through the firewall.

---

## certifi

### What is it?
**certifi** is a Python package that provides an up-to-date bundle of **SSL root certificates**.

### Why do we use it?
Python on macOS doesn't automatically trust all SSL certificates, especially those from corporate proxies like Cisco Umbrella. `certifi` provides a base certificate bundle.

### Note
In our case, even `certifi` alone wasn't enough because the Cisco Umbrella proxy uses its own certificate. We had to export the full **macOS system keychain** certs and use those instead (handled automatically in `summarizer.py`).

---

## pydantic

### What is it?
**pydantic** is a Python data validation library. FastAPI uses it to validate incoming request bodies.

### Why do we use it?
When the `/summary/by-case-number` endpoint receives a POST request, pydantic ensures the body has the correct fields and types — and returns a clear error if not.

### How we use it

```python
from pydantic import BaseModel

class CaseSummaryRequest(BaseModel):
    case_number: str
```

If someone sends `{"case_number": 123}` (int instead of string) — pydantic automatically rejects it with a `422 Unprocessable Entity` error.

### Analogy
> Pydantic is the **security guard** at the API door — checks your request has the right format before letting it in.

---

## ssl + socket (Python standard library)

### What are they?
Built-in Python modules for working with **SSL/TLS encryption** and **network connections**.

### Why do we use them?
We used them to **diagnose** the SSL issue — specifically to inspect which certificate was being presented by the server when connecting to `api.openai.com`. This revealed the Cisco Umbrella proxy was intercepting the connection.

```python
import ssl, socket
ctx = ssl.create_default_context()
with socket.create_connection(('api.openai.com', 443)) as sock:
    with ctx.wrap_socket(sock, server_hostname='api.openai.com') as ssock:
        print(ssock.getpeercert()['issuer'])
# Output: Cisco Secure Access SubCA — confirmed proxy interception
```

---

## subprocess (Python standard library)

### What is it?
Built-in Python module to **run shell commands** from within Python code.

### Why do we use it?
In `summarizer.py`, we run `security export` shell commands at startup to export the macOS system keychain SSL certificates into a `.pem` file — so the OpenAI client can trust the Cisco Umbrella proxy certificate.

```python
import subprocess
subprocess.run("security export -t certs -f pemseq -k /Library/Keychains/System.keychain -o /tmp/_sys.pem", shell=True)
```

---

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

| Tool | Type | Purpose |
|------|------|---------|
| **uvicorn** | Server | Runs the FastAPI app on port 8000 |
| **ngrok** | Tunnel | Gives local server a public HTTPS URL |
| **FastAPI** | Web framework | Defines API routes and handles requests |
| **requests** | HTTP client | Calls ServiceNow, Webex, and Circuit LLM APIs |
| **python-dotenv** | Config loader | Loads secrets from `.env` file |
| **pydantic** | Validation | Validates incoming API request data |
| **ssl + socket** | Diagnostics | Used to inspect SSL certificates |
| **base64** | Encoding | Encodes credentials for Circuit LLM Basic Auth |
| **json** | Serialization | Encodes `appkey` payload for Circuit LLM |
| **Cisco Circuit LLM** | AI backend | Internal Cisco LLM — generates case summaries |
