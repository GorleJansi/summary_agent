# AWS Lambda Docker Deployment Guide

## Overview

This deploys the summary-agent FastAPI app as an AWS Lambda container image.
Instead of ngrok (blocked by Cisco), Lambda + API Gateway gives a permanent public HTTPS URL.

```
Webex Bot → API Gateway URL → Lambda (Docker) → FastAPI app
                                    ↓
                              ServiceNow API
                              Circuit LLM
                              Webex API (reply)
```

---

## Files Created for Lambda

| File | Purpose |
|------|---------|
| `lambda_handler.py` | Entry point — wraps FastAPI with Mangum |
| `Dockerfile` | Builds the Lambda container image |
| `.dockerignore` | Excludes .env, .venv, .git from image |

---

## Step 1 — Build the Docker Image Locally

```bash
cd /path/to/summary-agent
docker build -t summary-agent .
```

### Test locally (optional):
```bash
docker run -p 9000:8080 \
  -e SERVICENOW_INSTANCE=dev181123.service-now.com \
  -e SERVICENOW_USERNAME=admin \
  -e SERVICENOW_PASSWORD='your-password' \
  -e WEBEX_BOT_TOKEN=your-token \
  -e WEBEX_BOT_EMAIL=your-bot@webex.bot \
  -e CIRCUIT_CLIENT_ID=your-client-id \
  -e CIRCUIT_CLIENT_SECRET=your-secret \
  -e CIRCUIT_APP_KEY=your-app-key \
  -e CIRCUIT_MODEL=gpt-4o-mini \
  summary-agent

# In another terminal:
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"version":"2.0","routeKey":"GET /","rawPath":"/","rawQueryString":"","headers":{},"requestContext":{"http":{"method":"GET","path":"/","protocol":"HTTP/1.1","sourceIp":"127.0.0.1"},"routeKey":"GET /","stage":"$default"},"isBase64Encoded":false}'
```

Expected: `{"statusCode": 200, "body": "..."}`

---

## Step 2 — Push to AWS ECR

```bash
# 1. Login to ECR (replace ACCOUNT_ID and REGION)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# 2. Create repository (one time)
aws ecr create-repository --repository-name summary-agent

# 3. Tag the image
docker tag summary-agent:latest \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/summary-agent:latest

# 4. Push
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/summary-agent:latest
```

---

## Step 3 — Lambda Configuration

### Environment Variables (set in Lambda console):

| Variable | Value |
|----------|-------|
| `SERVICENOW_INSTANCE` | `dev181123.service-now.com` |
| `SERVICENOW_USERNAME` | `admin` |
| `SERVICENOW_PASSWORD` | (from .env) |
| `WEBEX_BOT_TOKEN` | (from .env) |
| `WEBEX_BOT_EMAIL` | `jansi-test@webex.bot` |
| `CIRCUIT_CLIENT_ID` | (from .env) |
| `CIRCUIT_CLIENT_SECRET` | (from .env) |
| `CIRCUIT_APP_KEY` | (from .env) |
| `CIRCUIT_MODEL` | `gpt-4o-mini` |

### Lambda Settings:

| Setting | Value |
|---------|-------|
| Runtime | Container image |
| Handler | Set in Dockerfile (`lambda_handler.handler`) |
| Memory | 512 MB (minimum recommended) |
| Timeout | 60 seconds |
| Architecture | x86_64 |

### API Gateway:

- Create HTTP API
- Route: `ANY /{proxy+}` → Lambda function
- This gives a public URL like: `https://abc123.execute-api.us-east-1.amazonaws.com`

---

## Step 4 — Register Webex Webhooks

Once you have the API Gateway URL:

```bash
# Messages webhook
curl -X POST https://webexapis.com/v1/webhooks \
  -H "Authorization: Bearer YOUR_WEBEX_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summary-agent-messages",
    "targetUrl": "https://YOUR-API-GATEWAY-URL/webhook/webex",
    "resource": "messages",
    "event": "created"
  }'

# Card actions webhook
curl -X POST https://webexapis.com/v1/webhooks \
  -H "Authorization: Bearer YOUR_WEBEX_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "summary-agent-card-actions",
    "targetUrl": "https://YOUR-API-GATEWAY-URL/webhook/webex/card-action",
    "resource": "attachmentActions",
    "event": "created"
  }'
```

---

## Before vs After

| Before (ngrok) | After (Lambda) |
|----------------|---------------|
| Runs on your laptop | Runs on AWS cloud |
| ngrok tunnel (blocked by Cisco) | API Gateway (permanent HTTPS URL) |
| Stops when laptop sleeps | Always available 24/7 |
| No cost | ~$0 for low usage (Lambda free tier) |
