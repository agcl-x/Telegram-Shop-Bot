import sqlite3
import json
from log import *

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    log_sys('config.json was succsesfully loaded')


def fetch_as_dicts(query, params=()):
    log_sys(f"Initiating connection to database( {config["pathToDatabase"]} )")
    with sqlite3.connect(config['pathToDatabase']) as conn:
        log_sys("Successfully connected to database")
        cur = conn.cursor()
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        log_sys("Data was successfully fetched")
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def SQLmake(query, params=()):
    log_sys(f"Initiating connection to database( {config["pathToDatabase"]} )")
    with sqlite3.connect(config['pathToDatabase']) as conn:
        log_sys("Successfully connected to database")
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.lastrowid