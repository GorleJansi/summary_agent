"""
AWS Lambda entry point.
Wraps the FastAPI app with Mangum so API Gateway events are
translated into ASGI requests that FastAPI can handle.
"""

from mangum import Mangum
from app import app  # import the FastAPI instance

# Mangum adapter: converts API Gateway/ALB events → FastAPI
handler = Mangum(app, lifespan="off")
