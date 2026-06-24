"""
main.py — Точка входа Яндекс Cloud Function.
"""
import json
import logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from database import init_db
init_db()

from handlers import dispatch


def handler(event: dict, context) -> dict:
    try:
        raw    = event.get("body", event)
        update = json.loads(raw) if isinstance(raw, str) else raw
        dispatch(update)
    except Exception as e:
        logging.exception("Ошибка: %s", e)
    return {"statusCode": 200, "body": "ok"}
