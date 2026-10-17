import os
import sys
import time
import random
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from instagrapi import Client
from db import get_connection
from multi_agents import filter_spam_agent, sales_agent, followup_agent
from telegram_alerts import send_telegram_meeting_alert

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

cl = None
# Буфер для склеювання повідомлень клієнта:
# { thread_id: {"last_incoming_time": float, "messages": [str], "username": str, "full_name": str} }
thread_debounce_buffers = {}

def get_ig_client():
    global cl
    if cl is not None:
        return cl

    client = Client()
    session_file = "ig_session.json"
    if os.path.exists(session_file):
        try:
            client.load_settings(session_file)
            client.login(IG_USERNAME, IG_PASSWORD)
            cl = client
            return cl
        except Exception:
            pass

    client.login(IG_USERNAME, IG_PASSWORD)
    client.dump_settings(session_file)
    cl = client
    return cl

def send_ig_direct_message(thread_id: str, text: str):
    client = get_ig_client()
    client.direct_send(text, thread_ids=[thread_id])

def check_human_handoff(text: str) -> tuple[bool, str]:
    """
    Перевіряє, чи треба вимкнути AI і терміново передати діалог людині.
    Повертає: (треба_передати: bool, причина: str)
    """
    # 1. Клієнт надіслав телефон (UA номери або 10+ цифр)
    phone_pattern = r'(\+?380\s?\(?\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}|\b0\d{9}\b)'
    if re.search(phone_pattern, text):
        return True, "Клієнт надіслав номер телефону"

    # 2. Клієнт скинув нік в Telegram
    tg_pattern = r'(@[a-zA-Z0-9_]{4,}|t\.me/[a-zA-Z0-9_]+)'
    if re.search(tg_pattern, text.lower()):
        return True, "Клієнт надав контактний Telegram"

    return False, ""

def sync_and_buffer_messages():
    """
    Опитує Direct та збирає всі короткі повідомлення клієнта в єдиний буфер (Debounce).
    """
    client = get_ig_client()
    user_id = str(client.user_id)
    conn = get_connection()
    c = conn.cursor()

    threads = client.direct_threads(amount=10)
    current_time = time.time()

    for thread in threads:
        thread_id = str(thread.id)
        if not thread.messages:
            continue

        username = thread.users[0].username if thread.users else "клієнт"
        full_name = thread.users[0].full_name if thread.users else ""

        # Зберігаємо тред
        c.execute("""
        INSERT INTO threads (thread_id, username, full_name, last_message_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(thread_id) DO UPDATE SET 
            username=excluded.username,
            full_name=excluded.full_name
        """, (thread_id, username, full_name, datetime.now().isoformat()))
        conn.commit()

        # Зберігаємо нові повідомлення в базу
        for m in reversed(thread.messages[:10]):
            m_id = str(m.id)
            sender = "agent" if str(m.user_id) == user_id else "client"
            m_text = m.text or ""
            c.execute("""
            INSERT OR IGNORE INTO messages (thread_id, message_id, sender, text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (thread_id, m_id, sender, m_text, m.timestamp.isoformat()))
        conn.commit()

        # Останнє повідомлення
        last_msg = thread.messages[0]
        # Якщо останнє повідомлення від нас — пропускаємо
        if str(last_msg.user_id) == user_id:
            # Очищуємо буфер якщо ми вже відповіли
            if thread_id in thread_debounce_buffers:
                del thread_debounce_buffers[thread_id]
            continue

        # Перевірка: чи AI увімкнений для цього чату
        c.execute("SELECT ai_enabled, status FROM threads WHERE thread_id = ?", (thread_id,))
        t_row = c.fetchone()
        if not t_row or not t_row["ai_enabled"]:
            continue

        # Додаємо повідомлення в буфер склеювання (Message Debounce)
        if thread_id not in thread_debounce_buffers:
            # Збираємо всі неповторні останні повідомлення клієнта
            thread_debounce_buffers[thread_id] = {
                "last_incoming_time": current_time,
                "messages": [last_msg.text or ""],
                "last_msg_id": str(last_msg.id),
                "username": username,
                "full_name": full_name
            }
        else:
            # Якщо прийшло ще одне повідомлення в той самий діалог — оновлюємо час таймера і склеюємо
            buf = thread_debounce_buffers[thread_id]
            if buf.get("last_msg_id") != str(last_msg.id):
                buf["messages"].append(last_msg.text or "")
                buf["last_msg_id"] = str(last_msg.id)
                buf["last_incoming_time"] = current_time
                print(f"🧩 [Склеювання]: Додано повідомлення від @{username}: \"{last_msg.text}\". Скинуто таймер.")

    conn.close()

def process_ready_buffers():
    """
    Обробляє ті діалоги, де клієнт закінчив писати серію повідомлень і сплив Jitter-таймер.
    """
    if not thread_debounce_buffers:
        return

    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    settings = {r["key"]: r["value"] for r in c.fetchall()}
    base_delay = int(settings.get("first_reply_delay_sec", 45))
    custom_b2b = settings.get("b2b_sales_instructions", "")

    # Перевірка робочого часу: 11:00 - 21:00
    now_hour = datetime.now().hour
    if not (11 <= now_hour < 21):
        # Вночі не надсилаємо вихідні повідомлення клієнтам
        return

    current_time = time.time()
    ready_threads = []

    for thread_id, buf in list(thread_debounce_buffers.items()):
        # Анти-бан Jitter (наприклад 45 сек -> рандом від 35 до 70 сек)
        jitter_delay = base_delay + random.randint(-10, 25)
        if jitter_delay < 25:
            jitter_delay = 25

        elapsed = current_time - buf["last_incoming_time"]
        if elapsed >= jitter_delay:
            ready_threads.append((thread_id, buf))

    for thread_id, buf in ready_threads:
        del thread_debounce_buffers[thread_id]
        username = buf["username"]
        # Склеєний єдиний текст клієнта:
        merged_client_text = " \n ".join([m for m in buf["messages"] if m.strip()])
        if not merged_client_text:
            continue

        print(f"\n🚀 [Обробка запиту] @{username} (склеєно {len(buf['messages'])} повід.):\n\"{merged_client_text}\"")

        # 1. ТРИГЕР ПЕРЕДАЧІ ЛЮДИНІ (HUMAN HANDOFF)
        need_handoff, handoff_reason = check_human_handoff(merged_client_text)
        if need_handoff:
            print(f"🛑 [Human Handoff Trigger]: {handoff_reason} від @{username}! Вимикаємо AI в чаті.")
            c.execute("UPDATE threads SET ai_enabled = 0, status = 'waiting_human' WHERE thread_id = ?", (thread_id,))
            c.execute("""
            INSERT INTO leads (username, full_name, phone, status, created_at)
            VALUES (?, ?, ?, 'hot_lead', ?)
            ON CONFLICT(username) DO UPDATE SET phone=excluded.phone, status='hot_lead'
            """, (username, buf["full_name"], merged_client_text, datetime.now().isoformat()))
            conn.commit()

            # Сповіщення в Telegram
            from telegram_alerts import send_telegram_meeting_alert
            send_telegram_meeting_alert(username, "Терміново (передано людині)", "Контакт отримано", merged_client_text, 0)
            continue

        # 2. ФІЛЬТР СПАМУ
        filter_res = filter_spam_agent(username, merged_client_text)
        if filter_res.get("is_spam"):
            print(f"🚫 [Filter Agent]: Виявлено сторонній спам/пропозицію від @{username}.")
            reply_text = "Вітаю. Підкажіть, чи цікавить вас створення сайту, FPV відеозйомка або реклама для вашого бізнесу? Якщо ні — гарного дня!"
        else:
            # 3. B2B SALES AGENT (ПРОДАЖ ЗУСТРІЧІ НА 15-20 ХВ)
            c.execute("SELECT sender, text FROM messages WHERE thread_id = ? ORDER BY id ASC LIMIT 10", (thread_id,))
            chat_history = [dict(r) for r in c.fetchall()]

            sales_res = sales_agent(username, chat_history, custom_b2b)
            reply_text = sales_res.get("reply_text")

            # Зберігаємо ліда
            service = sales_res.get("detected_service")
            contact = sales_res.get("client_phone_or_contact")
            c.execute("""
            INSERT INTO leads (username, full_name, service, phone, status, created_at)
            VALUES (?, ?, ?, ?, 'in_progress', ?)
            ON CONFLICT(username) DO UPDATE SET service=excluded.service, phone=excluded.phone
            """, (username, buf["full_name"], service, contact, datetime.now().isoformat()))
            conn.commit()

            # Якщо узгоджується зустріч
            if sales_res.get("meeting_requested") or sales_res.get("proposed_time"):
                prop_time = sales_res.get("proposed_time") or "09:00 - 21:00 (15-20 хв аудит)"
                c.execute("""
                INSERT INTO appointments (username, appointment_date, duration_minutes, status, created_at)
                VALUES (?, ?, 20, 'pending', ?)
                """, (username, prop_time, datetime.now().isoformat()))
                conn.commit()
                app_id = c.lastrowid
                send_telegram_meeting_alert(username, prop_time, service, merged_client_text, app_id)

        # 4. СИМУЛЯЦІЯ ДРУКУ ЗАЛЕЖНО ВІД ДОВЖИНИ ТЕКСТУ (1 сек на 20 символів)
        typing_simulation_sec = max(2, min(len(reply_text) // 20, 8))
        print(f"⌨️ Симуляція друку тексту ({len(reply_text)} симв): {typing_simulation_sec} сек...")
        time.sleep(typing_simulation_sec)

        # Відправка відповіді в Direct
        try:
            client = get_ig_client()
            client.direct_send(reply_text, thread_ids=[thread_id])
            now_iso = datetime.now().isoformat()
            c.execute("""
            INSERT INTO messages (thread_id, message_id, sender, text, created_at)
            VALUES (?, ?, 'agent', ?, ?)
            """, (thread_id, f"auto_{int(datetime.now().timestamp())}", reply_text, now_iso))
            c.execute("UPDATE threads SET last_message_at = ? WHERE thread_id = ?", (now_iso, thread_id))
            conn.commit()
            print(f"✅ [Відправлено в Direct @{username}]:\n\"{reply_text}\"")
        except Exception as e:
            print(f"❌ Помилка відправки в Direct: {e}")

    conn.close()

def main_loop():
    print(f"🚀 Професійний фоновий воркер ProstoDev із Debounce та Human Handoff запущений!")
    while True:
        try:
            sync_and_buffer_messages()
            process_ready_buffers()
        except Exception as err:
            print(f"⚠️ Помилка циклу: {err}")
        time.sleep(12)

if __name__ == "__main__":
    main_loop()
