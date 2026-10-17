import sqlite3
import json
import sys
from datetime import datetime

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "prostodev.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Таблиця діалогів
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        ai_enabled INTEGER DEFAULT 1,
        status TEXT DEFAULT 'new',
        last_message_at TEXT,
        follow_up_count INTEGER DEFAULT 0,
        last_follow_up_at TEXT
    )
    """)

    # 2. Таблиця повідомлень
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT,
        message_id TEXT UNIQUE,
        sender TEXT,
        text TEXT,
        created_at TEXT,
        FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
    )
    """)

    # 3. Таблиця лідів
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        full_name TEXT,
        phone TEXT,
        telegram TEXT,
        service TEXT,
        notes TEXT,
        status TEXT DEFAULT 'lead',
        created_at TEXT
    )
    """)

    # 4. Таблиця зустрічей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        appointment_date TEXT,
        duration_minutes INTEGER DEFAULT 45,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        created_at TEXT
    )
    """)

    # 5. Таблиця налаштувань AI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Базові налаштування
    default_settings = {
        "first_reply_delay_sec": "45",
        "greeting_template": "Вітаю! Мене звати асистент студії ProstoDev. Підкажіть, яка послуга вас цікавить: створення сайту, FPV відеозйомка чи реклама?",
        "b2b_sales_instructions": "Суворий діловий B2B стиль. Не називати точних цін (індивідуально після аудиту на зустрічі). Кваліфікувати нішу та пропонувати зустріч на 45-60 хв з 09:00 до 21:00 (Пн-Нд). По FPV локація: Львівська область.",
        "ai_global_active": "1"
    }

    for key, val in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()
    print("✅ База даних SQLite (prostodev.db) успішно ініціалізована!")

if __name__ == "__main__":
    init_db()
