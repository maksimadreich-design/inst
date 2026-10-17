import time
import random
import sqlite3
from datetime import datetime
from instagrapi import Client
from worker import get_ig_client
from multi_agents import ai

def generate_personalized_skhidnytsya_pitch(target_username: str) -> str:
    """
    Генерує максимально персоналізоване перше повідомлення під конкретний заклад Східниці.
    """
    prompt = f"""
Ти — Ярослав із студії ProstoDev Studio.
Ти пишеш перше повідомлення в Instagram Direct закладу/готелю зі Східниці (@{target_username}).
Зараз ти перебуваєш у Східниці.

Мета: запропонувати зустрітися на 10 хвилин прямо у них на локації/кафе, випити кави та показати свіжі зразки FPV-відеозйомки для готелів/басейнів/чанів або обговорити оновлення сайту.

Вимоги:
1. Жива, легка ділова українська мова, без офіціозу.
2. 2-3 речення максимум.
3. Закінчуй простим відкритим питанням (наприклад: "Коли вам зручніше перетнутися — сьогодні чи завтра в першій половині дня?").
4. Без слів "асистент", "бот", "пропоную послуги". Тільки чистий партнерський вайб.
"""
    try:
        res = ai.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt,
            config=dict(temperature=0.7)
        )
        return res.text.strip().replace('"', '')
    except Exception as e:
        return f"Вітаю! Ярослав, ProstoDev Studio. Зараз якраз у Східниці — знімаємо промо-прольоти на FPV для комплексів та оновлюємо сайти. Можемо зустрітися на 10 хв прямо у вас на локації, вип'ємо кави, покажу приклади. Коли вам зручніше — сьогодні після обіду чи завтра?"

def is_working_hours() -> bool:
    """
    Перевірка: дозволено писати тільки з 11:00 до 21:00.
    У нічний час та зранку бот спить, щоб не турбувати людей.
    """
    now = datetime.now()
    return 11 <= now.hour < 21

def run_safe_outreach():
    print("🎯 Старт модуля аутрічу по Східниці...")
    
    if not is_working_hours():
        now = datetime.now().strftime("%H:%M")
        print(f"🌙 Зараз нічний час ({now}). Бот спить! Розсилка активна тільки з 11:00 до 21:00.")
        return

    conn = sqlite3.connect("prostodev.db")
    c = conn.cursor()

    c.execute("SELECT id, username FROM outreach_targets WHERE status = 'pending' LIMIT 5")
    targets = c.fetchall()

    if not targets:
        print("Всі акаунти з каналу вже опрацьовані або нових немає.")
        conn.close()
        return

    client = get_ig_client()

    for target_id, username in targets:
        print(f"\n📍 Підготовка повідомлення для @{username}...")
        message = generate_personalized_skhidnytsya_pitch(username)
        print(f"📝 Згенерований текст:\n\"{message}\"")

        # Відправка через пошук користувача
        try:
            user_info = client.user_info_by_username(username)
            target_pk = user_info.pk

            print(f"📤 Відправляємо в Direct @{username}...")
            client.direct_send(message, user_ids=[target_pk])

            # Оновлюємо статус в базі
            c.execute("""
            UPDATE outreach_targets 
            SET status = 'sent', sent_at = ? 
            WHERE id = ?
            """, (datetime.now().isoformat(), target_id))
            conn.commit()

            print(f"✅ Успішно надіслано для @{username}!")

            # Захисна затримка між холодними першими повідомленнями (10-15 хвилин)
            # Щоб Meta не заблокувала вихідні запити
            wait_time = random.randint(600, 900)
            print(f"🛡️ Анти-бан захист: чекаємо {wait_time // 60} хв перед наступним акаунтом...")
            time.sleep(wait_time)

        except Exception as e:
            print(f"❌ Не вдалося надіслати для @{username}: {e}")
            c.execute("UPDATE outreach_targets SET status = 'failed' WHERE id = ?", (target_id,))
            conn.commit()

    conn.close()

if __name__ == "__main__":
    run_safe_outreach()
