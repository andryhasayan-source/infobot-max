"""
database.py — YDB через нативный Python SDK.

Таблицы:
  bot_config    — настройки (приветствие, кнопки, тексты)
  contacts_links — ссылки в разделе Контакты
  admins        — администраторы
  admin_states  — FSM-состояния при редактировании
  bot_users     — уникальные пользователи
  stats         — счётчики (запуски, кнопки)
"""
import time
import logging
from typing import Optional
import ydb
import ydb.iam
from config import YDB_ENDPOINT, YDB_DATABASE, INITIAL_ADMIN_ID

logger = logging.getLogger(__name__)

# Значения по умолчанию
DEFAULTS = {
    "welcome_text":    "👋 Привет! Я помощник разработчика в MAX.\n\nВыберите действие:",
    "button_myid":     "🆔 Мой ID",
    "button_chats":    "📋 Чаты бота",
    "button_contacts": "📞 Контакты",
    "contacts_text":   "📞 <b>Контакты</b>\n\nСвяжитесь с нами:",
}

STAT_KEYS = ["starts", "unique_users", "btn_myid", "btn_chats", "btn_contacts", "bot_added", "bot_removed"]

_driver: Optional[ydb.Driver] = None
_pool:   Optional[ydb.SessionPool] = None
_initialized: bool = False


def _get_pool() -> ydb.SessionPool:
    global _driver, _pool
    if _pool is not None:
        return _pool
    _driver = ydb.Driver(
        endpoint=YDB_ENDPOINT,
        database=YDB_DATABASE,
        credentials=ydb.iam.MetadataUrlCredentials(),
    )
    _driver.wait(timeout=5)
    _pool = ydb.SessionPool(_driver)
    return _pool


def _run(query: str, params: dict = None):
    pool = _get_pool()
    def callee(session):
        if params:
            prepared = session.prepare(query)
            return session.transaction().execute(
                prepared, params, commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(5),
            )
        return session.transaction().execute(
            query, commit_tx=True,
            settings=ydb.BaseRequestSettings().with_timeout(5),
        )
    return pool.retry_operation_sync(callee)


def _scheme(query: str):
    pool = _get_pool()
    def callee(session):
        session.execute_scheme(query)
    pool.retry_operation_sync(callee)


def init_db() -> None:
    global _initialized
    if _initialized:
        return

    _scheme("CREATE TABLE IF NOT EXISTS bot_config (`key` Utf8, `value` Utf8, PRIMARY KEY (`key`))")
    _scheme("CREATE TABLE IF NOT EXISTS contacts_links (`id` Utf8, `text` Utf8, `url` Utf8, `order` Int64, PRIMARY KEY (`id`))")
    _scheme("CREATE TABLE IF NOT EXISTS admins (`user_id` Int64, PRIMARY KEY (`user_id`))")
    _scheme("CREATE TABLE IF NOT EXISTS admin_states (`user_id` Int64, `state` Utf8, `data` Utf8, PRIMARY KEY (`user_id`))")
    _scheme("CREATE TABLE IF NOT EXISTS bot_users (`user_id` Int64, PRIMARY KEY (`user_id`))")
    _scheme("CREATE TABLE IF NOT EXISTS stats (`key` Utf8, `value` Int64, PRIMARY KEY (`key`))")

    # Дефолты конфига — только если таблица пустая
    try:
        r = _run("SELECT COUNT(*) AS cnt FROM bot_config")
        if r[0].rows[0].cnt == 0:
            for key, value in DEFAULTS.items():
                _run("DECLARE $k AS Utf8; DECLARE $v AS Utf8;\n"
                     "UPSERT INTO bot_config (`key`, `value`) VALUES ($k, $v)",
                     {"$k": key, "$v": value})
    except Exception as e:
        logger.error("init defaults: %s", e)

    # Счётчики статистики
    for k in STAT_KEYS:
        try:
            _run("DECLARE $k AS Utf8; DECLARE $v AS Int64;\n"
                 "INSERT INTO stats (`key`, `value`) VALUES ($k, $v)",
                 {"$k": k, "$v": 0})
        except Exception:
            pass  # уже существует

    # Первый администратор
    if INITIAL_ADMIN_ID:
        try:
            _run("DECLARE $uid AS Int64;\n"
                 "UPSERT INTO admins (`user_id`) VALUES ($uid)",
                 {"$uid": INITIAL_ADMIN_ID})
        except Exception as e:
            logger.error("init admin: %s", e)

    _initialized = True
    logger.info("init_db done")


# ── bot_config ─────────────────────────────────

def cfg_get(key: str) -> str:
    try:
        r = _run("DECLARE $k AS Utf8;\nSELECT `value` FROM bot_config WHERE `key` = $k", {"$k": key})
        rows = r[0].rows
        return rows[0].value if rows else DEFAULTS.get(key, "")
    except Exception as e:
        logger.error("cfg_get %s: %s", key, e)
        return DEFAULTS.get(key, "")


def cfg_set(key: str, value: str) -> None:
    try:
        _run("DECLARE $k AS Utf8; DECLARE $v AS Utf8;\n"
             "UPSERT INTO bot_config (`key`, `value`) VALUES ($k, $v)",
             {"$k": key, "$v": value})
    except Exception as e:
        logger.error("cfg_set %s: %s", key, e)


def cfg_all() -> dict:
    try:
        r    = _run("SELECT `key`, `value` FROM bot_config")
        data = dict(DEFAULTS)
        data.update({row.key: row.value for row in r[0].rows})
        return data
    except Exception as e:
        logger.error("cfg_all: %s", e)
        return dict(DEFAULTS)


# ── contacts_links ─────────────────────────────

def links_all() -> list[dict]:
    try:
        r = _run("SELECT `id`, `text`, `url` FROM contacts_links ORDER BY `order`")
        return [{"id": row.id, "text": row.text, "url": row.url} for row in r[0].rows]
    except Exception as e:
        logger.error("links_all: %s", e)
        return []


def link_get(link_id: str) -> Optional[dict]:
    try:
        r = _run("DECLARE $id AS Utf8;\nSELECT `id`,`text`,`url` FROM contacts_links WHERE `id`=$id", {"$id": link_id})
        rows = r[0].rows
        return {"id": rows[0].id, "text": rows[0].text, "url": rows[0].url} if rows else None
    except Exception as e:
        logger.error("link_get: %s", e)
        return None


def link_add(text: str, url: str) -> str:
    lid = str(int(time.time() * 1000))
    try:
        _run("DECLARE $id AS Utf8; DECLARE $t AS Utf8; DECLARE $u AS Utf8; DECLARE $o AS Int64;\n"
             "UPSERT INTO contacts_links (`id`,`text`,`url`,`order`) VALUES ($id,$t,$u,$o)",
             {"$id": lid, "$t": text, "$u": url, "$o": int(lid)})
    except Exception as e:
        logger.error("link_add: %s", e)
    return lid


def link_update(link_id: str, text: str, url: str) -> None:
    try:
        _run("DECLARE $id AS Utf8; DECLARE $t AS Utf8; DECLARE $u AS Utf8;\n"
             "UPDATE contacts_links SET `text`=$t, `url`=$u WHERE `id`=$id",
             {"$id": link_id, "$t": text, "$u": url})
    except Exception as e:
        logger.error("link_update: %s", e)


def link_delete(link_id: str) -> None:
    try:
        _run("DECLARE $id AS Utf8;\nDELETE FROM contacts_links WHERE `id`=$id", {"$id": link_id})
    except Exception as e:
        logger.error("link_delete: %s", e)


# ── admins ─────────────────────────────────────

def admin_is(user_id: int) -> bool:
    try:
        r = _run("DECLARE $uid AS Int64;\nSELECT `user_id` FROM admins WHERE `user_id`=$uid", {"$uid": user_id})
        return len(r[0].rows) > 0
    except Exception as e:
        logger.error("admin_is: %s", e)
        return False


def admin_all() -> list[int]:
    try:
        r = _run("SELECT `user_id` FROM admins")
        return [row.user_id for row in r[0].rows]
    except Exception as e:
        logger.error("admin_all: %s", e)
        return []


def admin_count() -> int:
    try:
        r = _run("SELECT COUNT(*) AS cnt FROM admins")
        return r[0].rows[0].cnt
    except Exception as e:
        logger.error("admin_count: %s", e)
        return 0


def admin_add(user_id: int) -> None:
    try:
        _run("DECLARE $uid AS Int64;\nUPSERT INTO admins (`user_id`) VALUES ($uid)", {"$uid": user_id})
    except Exception as e:
        logger.error("admin_add: %s", e)


def admin_delete(user_id: int) -> bool:
    if admin_count() <= 1:
        return False
    try:
        _run("DECLARE $uid AS Int64;\nDELETE FROM admins WHERE `user_id`=$uid", {"$uid": user_id})
        return True
    except Exception as e:
        logger.error("admin_delete: %s", e)
        return False


# ── admin_states ───────────────────────────────

def state_get(user_id: int) -> tuple[Optional[str], Optional[str]]:
    try:
        r = _run("DECLARE $uid AS Int64;\nSELECT `state`,`data` FROM admin_states WHERE `user_id`=$uid", {"$uid": user_id})
        rows = r[0].rows
        return (rows[0].state, rows[0].data) if rows else (None, None)
    except Exception as e:
        logger.error("state_get: %s", e)
        return None, None


def state_set(user_id: int, state: str, data: str = "") -> None:
    try:
        _run("DECLARE $uid AS Int64; DECLARE $s AS Utf8; DECLARE $d AS Utf8;\n"
             "UPSERT INTO admin_states (`user_id`,`state`,`data`) VALUES ($uid,$s,$d)",
             {"$uid": user_id, "$s": state, "$d": data})
    except Exception as e:
        logger.error("state_set: %s", e)


def state_clear(user_id: int) -> None:
    try:
        _run("DECLARE $uid AS Int64;\nDELETE FROM admin_states WHERE `user_id`=$uid", {"$uid": user_id})
    except Exception as e:
        logger.error("state_clear: %s", e)


# ── stats ──────────────────────────────────────

def stats_inc(key: str) -> None:
    try:
        _run("DECLARE $k AS Utf8;\n"
             "UPDATE stats SET `value` = `value` + 1 WHERE `key` = $k",
             {"$k": key})
    except Exception as e:
        logger.error("stats_inc %s: %s", key, e)


def stats_add_user(user_id: int) -> None:
    """Добавить пользователя если новый, увеличить счётчик unique_users."""
    try:
        r = _run("DECLARE $uid AS Int64;\nSELECT `user_id` FROM bot_users WHERE `user_id`=$uid", {"$uid": user_id})
        if len(r[0].rows) == 0:
            _run("DECLARE $uid AS Int64;\nUPSERT INTO bot_users (`user_id`) VALUES ($uid)", {"$uid": user_id})
            stats_inc("unique_users")
    except Exception as e:
        logger.error("stats_add_user: %s", e)


def stats_reset() -> None:
    """Сбросить все счётчики статистики в 0."""
    try:
        for k in STAT_KEYS:
            _run("DECLARE $k AS Utf8;\nUPDATE stats SET `value` = 0 WHERE `key` = $k", {"$k": k})
    except Exception as e:
        logger.error("stats_reset: %s", e)


def stats_get_all() -> dict:
    try:
        r = _run("SELECT `key`, `value` FROM stats")
        return {row.key: row.value for row in r[0].rows}
    except Exception as e:
        logger.error("stats_get_all: %s", e)
        return {}
