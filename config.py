import os
from dotenv import load_dotenv

load_dotenv()

SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")

WEBEX_BOT_TOKEN = os.getenv("WEBEX_BOT_TOKEN")
WEBEX_BOT_EMAIL = os.getenv("WEBEX_BOT_EMAIL")

CIRCUIT_CLIENT_ID     = os.getenv("CIRCUIT_CLIENT_ID")
CIRCUIT_CLIENT_SECRET = os.getenv("CIRCUIT_CLIENT_SECRET")
CIRCUIT_APP_KEY       = os.getenv("CIRCUIT_APP_KEY")
CIRCUIT_MODEL         = os.getenv("CIRCUIT_MODEL", "gpt-4o-mini")

CIRCUIT_TOKEN_URL     = os.getenv(
    "CIRCUIT_TOKEN_URL",
    "https://id.cisco.com/oauth2/default/v1/token"
)
CIRCUIT_CHAT_BASE_URL = os.getenv(
    "CIRCUIT_CHAT_BASE_URL",
    "https://chat-ai.cisco.com/openai/deployments"
)