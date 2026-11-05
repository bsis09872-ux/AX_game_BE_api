from fastapi import FastAPI

from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging
from wallet.presentation.router import router as wallet_router

setup_logging()

app = FastAPI(title="AX Game BE API")
register_exception_handlers(app)
app.include_router(wallet_router)


@app.get("/health")
async def health():
    return {"status": "ok"}