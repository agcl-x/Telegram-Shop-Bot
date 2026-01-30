import sqlite3
import json
import os
from log import *
import dataStructures

# Завантажуємо конфіг
config_path = 'config.json'
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
else:
    config = {'pathToDatabase': 'database.db'}
    log_sys('Warning: config.json not found, using default db path')


def fetch_as_dicts(query, params=()):
    try:
        with sqlite3.connect(config['pathToDatabase']) as conn:
            conn.row_factory = sqlite3.Row  # Дозволяє звертатися до колонок за назвою
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        log_sys(f"[SQL ERROR] Query: {query} | Error: {e}")
        return []


def getCustomer(user_id=""):
    if not user_id:
        return None
    customer_data_list = fetch_as_dicts("SELECT * FROM users WHERE id = ?", (user_id,))

    if not customer_data_list:
        return None

    customer_data = customer_data_list[0]
    # Зверніть увагу: ключі мають співпадати з назвами колонок у БД (зазвичай lowercase)
    newCustomer = dataStructures.Customer(
        user_id,
        customer_data.get("PIB", ""),
        customer_data.get("phone", ""),
        customer_data.get("address", "")
    )
    return newCustomer


def SQLmake(query, params=()):
    try:
        with sqlite3.connect(config['pathToDatabase']) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        log_sys(f"[SQL ERROR] Query: {query} | Error: {e}")
        return None