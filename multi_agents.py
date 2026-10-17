import os
import json
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# 1. СУПЕРВІЗОР-ФІЛЬТР (відсікає спам та холодні пропозиції від інших ботів)
def filter_spam_agent(client_username: str, message_text: str) -> dict:
    """
    Визначає, чи є повідомлення спамом/холодною розсилкою від іншого сервісу.
    Повертає: {"is_spam": bool, "action": "reply_or_close" | "continue"}
    """
    prompt = f"""
Ти — Supervisor-агент студії розробки ProstoDev.
Твоє завдання — проаналізувати вхідне повідомлення від акаунта @{client_username}:
"{message_text}"

Визнач, чи це:
A) Спам, авто-розсилка, холодний продаж іншого бізнесу (наприклад: пропозиції підбору авто, дропшипінгу, крипти, накрутки, холодні оффери).
B) Реальний запит людини або питання, пов'язане з послугами студії ProstoDev (сайти, відео, реклама, маркетинг, ціна, співпраця).

Відповідь надай СУВОРО у форматі JSON:
{{
  "is_spam": true або false,
  "reason": "коротке пояснення"
}}
"""
    try:
        res = ai.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=dict(temperature=0.1)
        )
        text = res.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text)
    except Exception as e:
        print(f"[Filter Agent Error]: {e}")
        # Якщо в тексті типові маркери авто-спаму
        spam_keywords = ["авто з-за кордону", "доставка авто", "накрутка", "арбітраж", "крипт"]
        is_sp = any(w in message_text.lower() for w in spam_keywords)
        return {"is_spam": is_sp, "reason": "fallback"}


# 2. МЕНЕДЖЕР ПРОДАЖІВ B2B (Кваліфікатор зустрічей)
def sales_agent(client_username: str, chat_history: list, custom_instructions: str = "") -> dict:
    """
    Веде суворий B2B діалог. Не називає точних цін у Direct. Кличе на зустріч 45-60 хв.
    """
    history_str = "\n".join([f"{m['sender']}: {m['text']}" for m in chat_history])
    
    prompt = f"""
Ти — B2B менеджер української студії ProstoDev (prostodev.ua).
Твій стиль: суворий діловий B2B, впевнений, без «води» та зайвих компліментів, грамотною українською мовою.

Послуги ProstoDev:
1. 🌐 Розробка сучасних сайтів та веб-додатків «під ключ» (лендінги, e-commerce, корпоративні).
2. 🚁 FPV відеозйомка для бізнесу, нерухомості та брендів. Локація зйомок: виключно Львівська область.
3. 🚀 Прокачка та масштабування реклами сайтів (Google Ads, таргет, трафік).

Залізні правила комунікації:
- НЕ називати точних цін у чаті. Якщо клієнт питає ціну — відповідай: «Вартість формується індивідуально під проект після короткого аудиту на зустрічі».
- Тримай повідомлення лаконічними (максимум 2-3 чітких речення).
- Головна мета — узгодити точний день і час онлайн-зустрічі (Google Meet / дзвінок на 45-60 хвилин) у проміжку з 09:00 до 21:00 (Пн-Нд).
- Якщо це був авто-спам/інший бізнес, перепитай: «Чи цікавить вас наш сайт/відео/реклама?», і якщо ні — ввічливо завершити.

Додаткові настанови від керівника:
{custom_instructions}

Історія листування:
{history_str}

Сформуй відповідь та витягни дані у форматі JSON:
{{
  "reply_text": "Текст відповіді клієнту в Direct",
  "detected_service": "сайт" | "fpv" | "реклама" | "інше" | null,
  "meeting_requested": true | false,
  "proposed_time": "текст запропонованого часу якщо є" | null,
  "client_phone_or_contact": "контакт клієнта якщо вказав" | null
}}
"""
    try:
        res = ai.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=dict(temperature=0.3)
        )
        text = res.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text)
    except Exception as e:
        print(f"[Sales Agent Error]: {e}")
        return {
            "reply_text": "Вітаю. Вартість та стратегія формуються індивідуально після аудиту задач вашого бізнесу. Пропоную провести коротку зустріч на 45 хвилин для обговорення деталей. Який день та час після 10:00 вам зручні?",
            "detected_service": None,
            "meeting_requested": False,
            "proposed_time": None,
            "client_phone_or_contact": None
        }


# 3. FOLLOW-UP AGENT (М'яке нагадування)
def followup_agent(client_username: str, last_message_text: str, step: int) -> str:
    """
    Генерує 1-ше або 2-ге нагадування, якщо клієнт не відповів.
    step = 1 (через 3 години)
    step = 2 (через 24 години)
    """
    if step == 1:
        return f"Вітаю, @{client_username}. Чи вдалося ознайомитися з повідомленням? Будемо раді узгодити час для короткого аудиту вашого проекту."
    elif step == 2:
        return f"Доброго дня, @{client_username}. Нагадую щодо обговорення сайту чи реклами. Якщо питання наразі актуальне — підкажіть, коли буде зручно зв'язатися."
    return ""
