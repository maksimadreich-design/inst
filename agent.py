import os
import sys
import time
from dotenv import load_dotenv
from instagrapi import Client
from google import genai

# Фікс для виводу емодзі на Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Ти — персональний digital-асистент та менеджер української студії "ProstoDev".
Ти спілкуєшся з потенційними клієнтами в Instagram Direct від імені команди ProstoDev.
Твій стиль: діловий, впевнений, але водночас дуже дружній та живий. Спілкуйся українською мовою.

Наші ключові послуги:
1. 🌐 Створення сучасних сайтів: лендінги, інтернет-магазини, сайти для бізнесу "під ключ" (швидкі, адаптивні, готові до продажів). Терміни: 7-10 робочих днів.
2. 🚁 FPV відеозйомка: динамічні, трендові та кінематографічні FPV-ролики для бізнесу, закладів, нерухомості та соцмереж (Reels/TikTok).
3. 🚀 Прокачка та реклама сайтів (Google Ads, таргет, SEO, трафік) для залучення реальних клієнтів і лідів.

Правила відповідей:
- Відповідай коротко (1-3 речення), живо і природно для соцмереж, без зайвої "води".
- Якщо питають ціну — поясни, що бюджет залежить від задачі (сайт, FPV чи реклама), але ми підбираємо оптимальне рішення під ключ.
- Головна мета діалогу: призначити 10-хвилинний дзвінок/онлайн-зустріч для консультації або взяти номер телефону/нік у Telegram для зв'язку.
"""

def generate_ai_reply(client_username, message_text):
    try:
        prompt = f"Клієнт @{client_username} пише в Direct: \"{message_text}\". Дай коротку влучну відповідь за інструкцією."
        response = ai_client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=dict(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[AI Error]: {e}")
        return "Привіт! Дякую за звернення. Підкажіть, яка послуга вас цікавить: створення сайту, FPV зйомка чи налаштування реклами?"

def run():
    print(f"🚀 Запуск Instagram AI Агента для @{IG_USERNAME}...")
    cl = Client()
    
    # Файл збереження сесії, щоб не логінитись щоразу
    session_file = "ig_session.json"
    if os.path.exists(session_file):
        try:
            print("🔄 Завантажуємо збережену сесію...")
            cl.load_settings(session_file)
            cl.login(IG_USERNAME, IG_PASSWORD)
            print("✅ Сесію відновлено успішно!")
        except Exception as e:
            print(f"Помилка відновлення сесії, входимо заново: {e}")
            cl.login(IG_USERNAME, IG_PASSWORD)
            cl.dump_settings(session_file)
    else:
        print("🔐 Перший вхід в Instagram...")
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(session_file)
        print("✅ Успішний вхід! Сесію збережено.")

    user_id = cl.user_id
    print(f"🎧 Слухаємо Direct повідомлення для User ID: {user_id}")

    replied_ids = set()

    while True:
        try:
            threads = cl.direct_threads(amount=10)
            for thread in threads:
                if not thread.messages:
                    continue
                last_msg = thread.messages[0]
                
                # Якщо повідомлення від нас самих - ігноруємо
                if str(last_msg.user_id) == str(user_id):
                    continue
                
                if last_msg.id in replied_ids:
                    continue

                replied_ids.add(last_msg.id)
                msg_text = last_msg.text or ""
                sender = thread.users[0].username if thread.users else "клієнт"

                print(f"\n📩 Отримано повідомлення від @{sender}: \"{msg_text}\"")
                print("🤖 Генеруємо відповідь AI...")
                reply = generate_ai_reply(sender, msg_text)
                
                # Відправляємо відповідь у Direct
                cl.direct_send(reply, thread_ids=[thread.id])
                print(f"✅ Відповідь надіслано в Direct @{sender}: \"{reply}\"")

        except Exception as err:
            print(f"⚠️ Помилка перевірки Direct: {err}")

        time.sleep(15)

if __name__ == "__main__":
    run()
