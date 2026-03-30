# Import the built-in os module
# We use this to read environment variables from the system
import os

# Import load_dotenv from python-dotenv
# This helps load values from a .env file into environment variables
from dotenv import load_dotenv

# Load all variables from the .env file into the program environment
# Example: SERVICENOW_INSTANCE=dev181123.service-now.com
load_dotenv()

# Read the ServiceNow instance URL from environment variables
# Example value: dev181123.service-now.com
SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE")

# Read the ServiceNow username from environment variables
# Example value: admin
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME")

# Read the ServiceNow password from environment variables
# Example value: your password stored in .env
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD")

# Read the Webex bot token from environment variables
# This token is used to authenticate API calls to Webex
WEBEX_BOT_TOKEN = os.getenv("WEBEX_BOT_TOKEN")

# Read the Webex bot email from environment variables
# This is useful for identifying the bot's own messages
WEBEX_BOT_EMAIL = os.getenv("WEBEX_BOT_EMAIL")

# CIRCUIT LLM
CIRCUIT_CLIENT_ID = os.getenv("CIRCUIT_CLIENT_ID")
CIRCUIT_CLIENT_SECRET = os.getenv("CIRCUIT_CLIENT_SECRET")
CIRCUIT_APP_KEY = os.getenv("CIRCUIT_APP_KEY")
CIRCUIT_MODEL = os.getenv("CIRCUIT_MODEL", "gpt-4o-mini")

# CIRCUIT endpoints
CIRCUIT_TOKEN_URL = os.getenv(
    "CIRCUIT_TOKEN_URL",
    "https://id.cisco.com/oauth2/default/v1/token"
)
CIRCUIT_CHAT_BASE_URL = os.getenv(
    "CIRCUIT_CHAT_BASE_URL",
    "https://chat-ai.cisco.com/openai/deployments"
)