from fastapi import FastAPI

from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

setup_logging()

app = FastAPI(title="AX Game BE API")
register_exception_handlers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}