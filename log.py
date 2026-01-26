from datetime import datetime

def log(user_id, message):
    log_text = f"[{datetime.now().strftime("%H:%M %d.%m.%Y")}]\t{message}\n"
    log_path = f"logs\\{user_id}.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_text)

def log_sys(message):
    log("system", message)
