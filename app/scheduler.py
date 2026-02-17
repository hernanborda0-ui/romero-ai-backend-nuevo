from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
import os
import httpx

_scheduler: Optional[AsyncIOScheduler] = None

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

async def _send_message(chat_id: int, text: str):
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TELEGRAM_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })

def init_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    return _scheduler

def schedule_once(chat_id: int, text: str, run_dt: datetime):
    s = init_scheduler()
    s.add_job(_send_message, trigger=DateTrigger(run_date=run_dt),
              args=[chat_id, text],
              id=f"once-{chat_id}-{run_dt.timestamp()}",
              replace_existing=False)

def schedule_daily(chat_id: int, text: str, hour: int, minute: int, tz):
    s = init_scheduler()
    trig = CronTrigger(hour=hour, minute=minute, timezone=tz)
    job_id = f"daily-{chat_id}-{hour:02d}{minute:02d}"
    s.add_job(_send_message, trigger=trig, args=[chat_id, text],
              id=job_id, replace_existing=True)
