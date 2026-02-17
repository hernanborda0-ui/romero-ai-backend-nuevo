import os
from fastapi import FastAPI, Request
from app.telegram_handler import process_update
from app.scheduler import init_scheduler

app = FastAPI(title="Romero AI")

@app.on_event("startup")
async def startup_event():
    init_scheduler()

@app.get("/")
def home():
    return {"status": "Romero AI is running"}

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    await process_update(data)
    return {"ok": True}
