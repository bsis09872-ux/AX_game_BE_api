from fastapi import FastAPI

app = FastAPI(title="AX Game BE API")


@app.get("/health")
async def health():
    return {"status": "ok"}