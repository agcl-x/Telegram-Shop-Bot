import os
from datetime import datetime


def log(user_id, message):
    folder_path = "logs"
    log_path = os.path.join(folder_path, f"{user_id}.log")

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    log_text = f"[{datetime.now().strftime('%H:%M %d.%m.%Y')}]\t{message}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_text)

def log_sys(message):
    log("system", message)
