import os
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_MY_CHAT_ID = os.getenv("TELEGRAM_MY_CHAT_ID")

def send_telegram_meeting_alert(username: str, proposed_time: str, service: str, client_msg: str, appointment_id: int):
    """
    Надсилає багате повідомлення в Telegram з інтерактивними кнопками:
    [✅ Підтвердити] [🔄 Перенести]
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_MY_CHAT_ID:
        print("[Telegram Notice]: Токен або chat_id не налаштовано в .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    text = f"""
🎯 *НОВИЙ ЗАПИТ НА ЗУСТРІЧ (ProstoDev)*

👤 *Клієнт:* [@{username}](https://instagram.com/{username})
💼 *Послуга:* {service or 'Уточнюється'}
⏰ *Бажаний час:* {proposed_time or 'Не вказано (очікує узгодження)'}

💬 *Повідомлення клієнта:*
_{client_msg}_
"""

    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Підтвердити зустріч", "callback_data": f"confirm_meet_{appointment_id}"},
                {"text": "🔄 Перенести час", "callback_data": f"reschedule_meet_{appointment_id}"}
            ]
        ]
    }

    payload = {
        "chat_id": TELEGRAM_MY_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": inline_keyboard
    }

    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram Alert Error]: {e}")
        return False
