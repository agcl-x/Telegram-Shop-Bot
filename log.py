from datetime import datetime
import os


def log(user_id, message):
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Використовуємо одинарні лапки всередині f-string для сумісності
    log_text = f"[{datetime.now().strftime('%H:%M %d.%m.%Y')}]\t{message}\n"
    log_path = f"logs/{user_id}.log"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_text)
    except Exception as e:
        print(f"Logging error: {e}")


def log_sys(message):
    log("system", message)