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
    from faster_whisper import WhisperModel

# Al inicio del archivo (carga el modelo una sola vez)
model_size = "tiny"  # o "base", "small" si tenés más RAM
whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")  # "cuda" si Railway te da GPU algún día

# Dentro de process_update, después de chequear text:
if "voice" in message:
    voice = message["voice"]
    file_id = voice["file_id"]

    # Descargar audio (como antes)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}")
        file_path = resp.json()["result"]["file_path"]
        audio_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"

    async with httpx.AsyncClient() as client:
        audio_resp = await client.get(audio_url)
        audio_bytes = audio_resp.content

    # Guardar temporalmente (Railway tiene /tmp)
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_path = tmp_file.name

    # Transcribir
    try:
        segments, info = whisper_model.transcribe(tmp_path, language="es", beam_size=5)
        transcript = " ".join([segment.text for segment in segments]).strip()

        if not transcript:
            await send_message(chat_id, "No entendí el audio 😅. Repetilo más claro?")
            return

        await send_message(chat_id, f"🎤 Transcribí: {transcript}")

        # Procesar el texto transcrito como mensaje normal
        text = transcript
        low = text.lower()
        # Pegá tu lógica de recordatorios acá (mañana, todos los días, etc.)

    except Exception as e:
        await send_message(chat_id, f"Error al transcribir: {str(e)}")
    finally:
        import os
        os.unlink(tmp_path)  # borra el temporal
    return
