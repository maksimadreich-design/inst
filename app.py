import os
import sys
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
from db import get_connection

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI(title="ProstoDev Executive Control Center")
templates = Jinja2Templates(directory="templates")

# Models
class ManualMessageRequest(BaseModel):
    thread_id: str
    text: str

class SettingsUpdateRequest(BaseModel):
    first_reply_delay_sec: str
    greeting_template: str
    b2b_sales_instructions: str

class StatusUpdateRequest(BaseModel):
    status: str

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/healthz")
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# 2. Отримати список діалогів Direct
@app.get("/api/threads")
async def get_threads():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM threads ORDER BY last_message_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 3. Отримати історію повідомлень конкретного діалогу
@app.get("/api/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE thread_id = ? ORDER BY id ASC", (thread_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 4. Надіслати ручне повідомлення в Direct
@app.post("/api/send_message")
async def send_manual_message(req: ManualMessageRequest):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    msg_id = f"manual_{int(datetime.now().timestamp())}"
    cursor.execute("""
    INSERT INTO messages (thread_id, message_id, sender, text, created_at)
    VALUES (?, ?, 'agent', ?, ?)
    """, (req.thread_id, msg_id, req.text, now))
    cursor.execute("UPDATE threads SET last_message_at = ? WHERE thread_id = ?", (now, req.thread_id))
    conn.commit()
    conn.close()

    # Спроба відправити в Instagram, якщо підключено
    try:
        from worker import send_ig_direct_message
        send_ig_direct_message(req.thread_id, req.text)
    except Exception as e:
        print(f"[Manual Send IG Notice]: {e}")

    return {"status": "success", "text": req.text}

# 5. Отримати список лідів CRM
@app.get("/api/leads")
async def get_leads():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 6. Отримати зустрічі
@app.get("/api/appointments")
async def get_appointments():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 7. Оновити статус зустрічі
@app.post("/api/appointments/{app_id}/status")
async def update_appointment_status(app_id: int, req: StatusUpdateRequest):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", (req.status, app_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}

# 8. Отримати та оновити налаштування
@app.get("/api/settings")
async def get_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('first_reply_delay_sec', ?)", (req.first_reply_delay_sec,))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('greeting_template', ?)", (req.greeting_template,))
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('b2b_sales_instructions', ?)", (req.b2b_sales_instructions,))
    conn.commit()
    conn.close()
    return {"status": "saved"}

if __name__ == "__main__":
    print("🌐 Запуск веб-панелі ProstoDev Control Center на http://127.0.0.1:8000")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
