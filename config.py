"""
config.py — Переменные окружения Cloud Function.

  BOT_TOKEN        — токен бота из MAX
  YDB_ENDPOINT     — grpcs://ydb.serverless.yandexcloud.net:2135
  YDB_DATABASE     — /ru-central1/b1g.../etn...
  INITIAL_ADMIN_ID — ваш user_id в MAX (нужен при первом запуске)
"""
import os

BOT_TOKEN:        str = os.environ.get("BOT_TOKEN", "")
YDB_ENDPOINT:     str = os.environ.get("YDB_ENDPOINT", "")
YDB_DATABASE:     str = os.environ.get("YDB_DATABASE", "")
INITIAL_ADMIN_ID: int = int(os.environ.get("INITIAL_ADMIN_ID", "0"))

MAX_API: str = "https://platform-api.max.ru"
