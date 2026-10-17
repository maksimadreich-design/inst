import urllib.request
import re
import sqlite3
from datetime import datetime

CHANNEL_URL = "https://t.me/s/geobizznes"

def scrape_channel_instagrams():
    try:
        req = urllib.request.Request(
            CHANNEL_URL, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        html = urllib.request.urlopen(req).read().decode('utf-8')
        
        # Знаходимо всі instagram профілі
        raw_igs = re.findall(r'instagram\.com/([a-zA-Z0-9_\.]+)', html)
        # Очищуємо від службових сторінок instagram
        ignored = {'p', 'reel', 'stories', 'explore', 'tv'}
        cleaned_igs = set([u.strip('/').lower() for u in raw_igs if u.strip('/').lower() not in ignored])
        
        return list(cleaned_igs)
    except Exception as e:
        print(f"[Помилка читання каналу]: {e}")
        return []

def sync_targets_to_db():
    conn = sqlite3.connect("prostodev.db")
    c = conn.cursor()

    # Створюємо таблицю таргетів, якщо немає
    c.execute("""
    CREATE TABLE IF NOT EXISTS outreach_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        source TEXT DEFAULT 'tg_geobizznes',
        status TEXT DEFAULT 'pending', -- pending, sent, replied, failed
        sent_at TEXT,
        created_at TEXT
    )
    """)

    found = scrape_channel_instagrams()
    new_count = 0
    for ig in found:
        try:
            c.execute("""
            INSERT INTO outreach_targets (username, created_at)
            VALUES (?, ?)
            """, (ig, datetime.now().isoformat()))
            new_count += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    return found, new_count

if __name__ == "__main__":
    targets, added = sync_targets_to_db()
    print(f"Знайдено в каналі: {len(targets)} акаунтів")
    print(f"Нових додано в базу: {added}")
    print("Список акаунтів Східниці:", targets)
