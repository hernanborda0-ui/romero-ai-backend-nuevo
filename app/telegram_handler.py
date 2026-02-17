import os
import re
import pytz
import httpx
from datetime import datetime, timedelta
from app.scheduler import schedule_once, schedule_daily

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("Falta TELEGRAM_TOKEN en variables de entorno")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TZ = pytz.timezone(os.getenv("APP_TZ", "America/Argentina/Buenos_Aires"))

async def send_message(chat_id: int, text: str):
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TELEGRAM_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })

def parse_time(text: str):
    m = re.search(r"a las\s+(\d{1,2})(?::(\d{2}))?", text, re.IGNORECASE)
    if not m:
        return None
    h = int(m.group(1))
    mn = int(m.group(2)) if m.group(2) else 0
    if 0 <= h <= 23 and 0 <= mn <= 59:
        return h, mn
    return None

async def process_update(data: dict):
    message = data.get("message") or data.get("edited_message")
    if not message:
        return

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not text or not chat_id:
        return

    low = text.lower()

    if low == "/start":
        await send_message(chat_id,
            "¡Hola! Soy Romero AI.\n"
            "• Ej.: 'reunión mañana a las 15:30'\n"
            "• Ej.: 'tomar vitaminas todos los días a las 08:00'\n"
            "Te confirmo cuando quede programado ✅")
        return

    if "mañana" in low:
        hm = parse_time(low)
        if hm:
            hour, minute = hm
            now = datetime.now(TZ)
            run_dt = TZ.localize(datetime(now.year, now.month, now.day, hour, minute)) + timedelta(days=1)
            schedule_once(chat_id, f"📌 Recordatorio: {text}", run_dt)
            await send_message(chat_id, f"✅ Te aviso mañana a las {hour:02d}:{minute:02d}.")
            return

    if "todos los días" in low or "todos los dias" in low:
        hm = parse_time(low)
        if hm:
            hour, minute = hm
            schedule_daily(chat_id, f"🔄 Recordatorio diario: {text}", hour, minute, TZ)
            await send_message(chat_id, f"✅ Activo recordatorio diario a las {hour:02d}:{minute:02d}.")
            return

    await send_message(chat_id, "👌 Recibido. Probá: 'mañana a las 9' o 'todos los días a las 08:00'.")
