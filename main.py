import subprocess
import threading
import sys
import os

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_worker():
    # Запуск фонового процесу опитування Instagram
    import worker
    worker.main_loop()

if __name__ == "__main__":
    from db import init_db
    init_db()

    # Запускаємо воркер в окремому фоновому потоці
    t = threading.Thread(target=run_worker, daemon=True)
    t.start()

    # Запускаємо веб-панель на порті, який вимагає хмара (або 8000)
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=port)
