"""
handlers.py — Вся логика бота MAX.

Пользователь:   🆔 Мой ID | 📋 Чаты бота | 📞 Контакты | [⚙️ Админпанель] | 🏠 Главная
Администратор:  те же + Админпанель
Админпанель:    Приветствие | Контакты | Кнопки | Администраторы | Статистика | На главную

Статистика считает:
  starts        — запуски /start и bot_started
  unique_users  — уникальные пользователи
  btn_myid      — нажатий кнопки Мой ID
  btn_chats     — нажатий кнопки Чаты бота
  btn_contacts  — нажатий кнопки Контакты
  bot_added     — сколько раз бота добавляли в каналы/чаты
  bot_removed   — сколько раз бота удаляли из каналов/чатов
"""
import logging
from typing import Optional
import requests
from config import BOT_TOKEN, MAX_API
from database import (
    cfg_get, cfg_set, cfg_all,
    links_all, link_get, link_add, link_update, link_delete,
    admin_is, admin_all, admin_add, admin_delete, admin_count,
    state_get, state_set, state_clear,
    stats_inc, stats_add_user, stats_get_all, stats_reset,
)
from keyboards import (
    kb_main, kb_contacts, kb_admin_main,
    kb_back, kb_cancel, kb_stats,
    kb_confirm_stats_reset,
    kb_admin_buttons, kb_admin_contacts,
    kb_confirm_del_link, kb_admin_admins, kb_confirm_del_admin,
)

logger = logging.getLogger(__name__)
_H = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}
_T = 8


# ══════════════════════════════════════════════
# MAX API
# ══════════════════════════════════════════════

def _send(chat_id: int, text: str, buttons: Optional[list] = None) -> Optional[dict]:
    body: dict = {"text": text, "format": "html"}
    if buttons:
        body["attachments"] = [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
    try:
        r = requests.post(f"{MAX_API}/messages", params={"chat_id": chat_id},
                          headers=_H, json=body, timeout=_T)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("send: %s", e)
        return None


def _edit(mid: str, text: str, buttons: Optional[list] = None) -> None:
    body: dict = {
        "text": text, "format": "html",
        "attachments": [{"type": "inline_keyboard", "payload": {"buttons": buttons}}]
                        if buttons else [],
    }
    try:
        r = requests.put(f"{MAX_API}/messages", params={"message_id": mid},
                         headers=_H, json=body, timeout=_T)
        r.raise_for_status()
    except Exception as e:
        logger.error("edit mid=%s: %s", mid, e)


def _ack(callback_id: str, popup: str = "") -> None:
    body: dict = {"callback_id": callback_id}
    if popup:
        body["message"] = {"type": "popup", "text": popup}
    try:
        requests.post(f"{MAX_API}/answers", headers=_H, json=body, timeout=_T)
    except Exception as e:
        logger.error("ack: %s", e)


# ══════════════════════════════════════════════
# Парсинг апдейтов
# ══════════════════════════════════════════════

def _parse_msg(update: dict) -> tuple:
    m = update.get("message", {})
    uid = m.get("sender", {}).get("user_id")
    cid = m.get("recipient", {}).get("chat_id")
    return (
        int(uid) if uid is not None else None,
        int(cid) if cid is not None else None,
        (m.get("body", {}).get("text") or "").strip(),
        m.get("body", {}).get("mid"),
    )


def _parse_cb(update: dict) -> tuple:
    c   = update.get("callback", {})
    msg = update.get("message", {})
    uid = c.get("user", {}).get("user_id")
    cid = msg.get("recipient", {}).get("chat_id")
    mid = msg.get("body", {}).get("mid")
    return (
        int(uid) if uid is not None else None,
        int(cid) if cid is not None else None,
        c.get("callback_id"),
        mid,
        (c.get("payload") or "").strip(),
    )


# ══════════════════════════════════════════════
# Чаты бота
# ══════════════════════════════════════════════

def _get_bot_chats() -> str:
    try:
        r = requests.get(f"{MAX_API}/chats", headers=_H, timeout=_T)
        r.raise_for_status()
        chats = r.json().get("chats", [])
    except Exception as e:
        logger.error("get_bot_chats: %s", e)
        return "❌ Ошибка при запросе к API MAX."

    if not chats:
        return (
            "📋 <b>Чаты бота</b>\n\n"
            "<i>Бот не состоит ни в одном канале или чате.</i>\n\n"
            "Добавьте бота в канал как администратора и нажмите снова."
        )

    lines = [f"📋 <b>Чаты и каналы бота</b> — {len(chats)}\n"]
    for chat in chats:
        chat_id   = chat.get("chat_id", "—")
        title     = chat.get("title", "—")
        ctype     = chat.get("type", "—")
        is_public = chat.get("is_public", False)
        link      = chat.get("link", "")
        members   = chat.get("participants_count", "—")

        if ctype == "channel":
            label = "📢 Публичный канал" if is_public else "🔒 Приватный канал"
        elif ctype == "chat":
            label = "💬 Групповой чат"
        else:
            label = f"📁 {ctype}"

        line = (f"{label}\n"
                f"   📛 <b>{title}</b>\n"
                f"   🆔 Chat ID: <code>{chat_id}</code>\n"
                f"   👥 Участников: {members}")
        if link and is_public:
            line += f"\n   📎 {link}"
        lines.append(line)

    lines.append("\n<i>Только каналы и чаты где состоит бот.</i>")
    return "\n\n".join(lines)


# ══════════════════════════════════════════════
# Экраны администратора
# ══════════════════════════════════════════════

def _screen_main(chat_id: int, mid: str) -> None:
    _edit(mid,
          f"🔧 <b>Панель администратора</b>\n\n"
          f"👥 Администраторов: <b>{admin_count()}</b>\n"
          f"🔗 Ссылок в контактах: <b>{len(links_all())}</b>",
          kb_admin_main())


def _screen_stats(chat_id: int, mid: str) -> None:
    s = stats_get_all()
    _edit(mid,
          f"📊 <b>Статистика бота</b>\n\n"
          f"🚀 Запусков: <b>{s.get('starts', 0)}</b>\n"
          f"👤 Уникальных пользователей: <b>{s.get('unique_users', 0)}</b>\n\n"
          f"<b>Кнопки:</b>\n"
          f"   🆔 Мой ID: <b>{s.get('btn_myid', 0)}</b>\n"
          f"   📋 Чаты бота: <b>{s.get('btn_chats', 0)}</b>\n"
          f"   📞 Контакты: <b>{s.get('btn_contacts', 0)}</b>\n\n"
          f"<b>Привязки к каналам:</b>\n"
          f"   ➕ Добавлений: <b>{s.get('bot_added', 0)}</b>\n"
          f"   ➖ Удалений: <b>{s.get('bot_removed', 0)}</b>",
          kb_stats())


def _screen_welcome(chat_id: int, mid: str) -> None:
    _edit(mid,
          f"📝 <b>Приветствие</b>\n\n"
          f"Текущий текст:\n<i>{cfg_get('welcome_text')}</i>",
          [[{"type": "callback", "text": "✏️ Изменить", "payload": "adm:edit:welcome_text"}]]
          + kb_back())


def _screen_contacts(chat_id: int, mid: str) -> None:
    lnks = links_all()
    body = "\n".join(f"• <a href='{l['url']}'>{l['text']}</a>" for l in lnks) \
           or "<i>Ссылок пока нет</i>"
    _edit(mid,
          f"📞 <b>Контакты</b>\n\n"
          f"<b>Текст:</b>\n<i>{cfg_get('contacts_text')}</i>\n\n"
          f"<b>Ссылки:</b>\n{body}",
          [[{"type": "callback", "text": "✏️ Изменить текст", "payload": "adm:edit:contacts_text"}]]
          + kb_admin_contacts())


def _screen_buttons(chat_id: int, mid: str) -> None:
    _edit(mid, "🔘 <b>Кнопки пользователя</b>\n\nВыберите кнопку для переименования:",
          kb_admin_buttons())


def _screen_admins(chat_id: int, mid: str) -> None:
    body = "\n".join(f"• <code>{a}</code>" for a in admin_all()) \
           or "<i>Нет администраторов</i>"
    _edit(mid, f"👥 <b>Администраторы</b>\n\n{body}", kb_admin_admins())


# ══════════════════════════════════════════════
# Главный роутер
# ══════════════════════════════════════════════

def dispatch(update: dict) -> None:
    utype = update.get("update_type", "")

    # bot_started — пользователь нажал Старт
    if utype == "bot_started":
        uid = update.get("user", {}).get("user_id")
        cid = update.get("chat_id")
        if uid and cid:
            uid, cid = int(uid), int(cid)
            stats_inc("starts")
            stats_add_user(uid)
            _send(cid, cfg_get("welcome_text"), kb_main(admin_is(uid)))
        return

    # bot_added — бота добавили в канал/чат
    if utype == "bot_added":
        stats_inc("bot_added")
        return

    # bot_removed — бота удалили из канала/чата
    if utype == "bot_removed":
        stats_inc("bot_removed")
        return

    # message_created
    if utype == "message_created":
        user_id, chat_id, text, mid = _parse_msg(update)
        if not (user_id and chat_id):
            return

        is_adm = admin_is(user_id)

        # FSM администратора — проверяем первым
        state, state_data = state_get(user_id)
        if is_adm and state:
            if _admin_input(user_id, chat_id, text, state, state_data):
                return

        # Кнопка Главная / команда /start
        if text == "🏠 Главная" or text == "/start":
            if text == "/start":
                stats_inc("starts")
                stats_add_user(user_id)
            _send(chat_id, cfg_get("welcome_text"), kb_main(is_adm))
            return

        # Кнопка Админпанель / команда /admin
        if text == "⚙️ Админпанель" or text.startswith("/admin"):
            if not is_adm:
                _send(chat_id, "⛔ У вас нет прав доступа.")
                return
            state_clear(user_id)
            _send(chat_id,
                  f"🔧 <b>Панель администратора</b>\n\n"
                  f"👥 Администраторов: <b>{admin_count()}</b>\n"
                  f"🔗 Ссылок в контактах: <b>{len(links_all())}</b>",
                  kb_admin_main())
            return

        # Кнопки пользователя
        c = cfg_all()

        if text == c["button_myid"]:
            stats_inc("btn_myid")
            stats_add_user(user_id)
            _send(chat_id,
                  f"🆔 <b>Ваши идентификаторы</b>\n\n"
                  f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
                  f"💬 <b>Chat ID:</b> <code>{chat_id}</code>",
                  kb_main(is_adm))
            return

        if text == c["button_chats"]:
            stats_inc("btn_chats")
            # Контакты показываем с клавиатурой внизу
            result = _get_bot_chats()
            _send(chat_id, result, kb_main(is_adm))
            return

        if text == c["button_contacts"]:
            stats_inc("btn_contacts")
            lnks = kb_contacts()
            # Отправляем контакты, и следом главное меню чтобы оно было внизу
            _send(chat_id, c["contacts_text"], lnks if lnks else None)
            _send(chat_id, "Выберите действие:", kb_main(is_adm))
            return

        return

    # message_callback
    if utype == "message_callback":
        user_id, chat_id, cb_id, mid, payload = _parse_cb(update)
        if not (user_id and chat_id and cb_id):
            return
        if not payload.startswith("adm:"):
            _ack(cb_id)
            return
        if not admin_is(user_id):
            _ack(cb_id, "⛔ Нет доступа")
            return
        _admin_cb(user_id, chat_id, cb_id, mid, payload)


# ══════════════════════════════════════════════
# Администратор — callback роутер
# ══════════════════════════════════════════════

def _admin_cb(user_id: int, chat_id: int, cb_id: str, mid: str, payload: str) -> None:
    def ack(popup=""):
        _ack(cb_id, popup)

    # Навигация — словарь для чистоты
    nav = {
        "adm:main":     lambda: _screen_main(chat_id, mid),
        "adm:welcome":  lambda: _screen_welcome(chat_id, mid),
        "adm:contacts": lambda: _screen_contacts(chat_id, mid),
        "adm:buttons":  lambda: _screen_buttons(chat_id, mid),
        "adm:admins":   lambda: _screen_admins(chat_id, mid),
        "adm:stats":    lambda: _screen_stats(chat_id, mid),
    }
    if payload in nav:
        state_clear(user_id)
        nav[payload]()
        ack()
        return

    if payload == "adm:noop":
        ack(); return

    # На главную — выходим в меню пользователя
    if payload == "adm:exit":
        state_clear(user_id)
        _send(chat_id, cfg_get("welcome_text"), kb_main(admin_is(user_id)))
        ack(); return

    # Сброс статистики — запрос подтверждения
    if payload == "adm:stats_reset":
        _edit(mid, "🗑️ <b>Сбросить всю статистику?</b>\n\nЭто действие нельзя отменить.",
              kb_confirm_stats_reset())
        ack(); return

    # Подтверждение сброса
    if payload == "adm:stats_confirm_reset":
        stats_reset()
        _screen_stats(chat_id, mid)
        ack("✅ Статистика сброшена")
        return

    # Редактировать поле конфига
    if payload.startswith("adm:edit:"):
        field = payload[len("adm:edit:"):]
        labels = {
            "welcome_text":    "приветственный текст",
            "contacts_text":   "текст раздела Контакты",
            "button_myid":     "название кнопки 1",
            "button_chats":    "название кнопки 2",
            "button_contacts": "название кнопки 3",
        }
        back = ("adm:contacts" if field == "contacts_text" else
                "adm:welcome"  if field == "welcome_text"  else "adm:buttons")
        state_set(user_id, f"edit:{field}", mid)
        _edit(mid,
              f"✏️ Введите новый <b>{labels.get(field, field)}</b>:\n\n"
              f"<b>Текущее:</b>\n<i>{cfg_get(field)}</i>\n\n"
              f"<i>Отправьте новый текст следующим сообщением.</i>",
              kb_cancel(back))
        ack(); return

    # Добавить ссылку
    if payload == "adm:addlink":
        state_set(user_id, "addlink:text", mid)
        _edit(mid, "➕ <b>Новая ссылка — шаг 1/2</b>\n\nВведите <b>текст кнопки</b>:",
              kb_cancel("adm:contacts"))
        ack(); return

    # Редактировать ссылку
    if payload.startswith("adm:editlink:"):
        link_id = payload[len("adm:editlink:"):]
        lnk = link_get(link_id)
        if not lnk: ack("Ссылка не найдена"); return
        state_set(user_id, f"editlink:text:{link_id}", mid)
        _edit(mid,
              f"✏️ <b>Редактирование — шаг 1/2</b>\n\n"
              f"Текст: <i>{lnk['text']}</i>\n"
              f"URL: <i>{lnk['url']}</i>\n\n"
              "Введите новый <b>текст кнопки</b>:",
              kb_cancel("adm:contacts"))
        ack(); return

    # Удалить ссылку
    if payload.startswith("adm:dellink:"):
        link_id = payload[len("adm:dellink:"):]
        lnk = link_get(link_id)
        if not lnk: ack("Ссылка не найдена"); return
        _edit(mid, f"🗑️ Удалить ссылку?\n\n<b>{lnk['text']}</b>\n{lnk['url']}",
              kb_confirm_del_link(link_id))
        ack(); return

    if payload.startswith("adm:confirmdellink:"):
        link_delete(payload[len("adm:confirmdellink:"):])
        _screen_contacts(chat_id, mid)
        ack("✅ Удалено"); return

    # Добавить администратора
    if payload == "adm:addadmin":
        state_set(user_id, "addadmin", mid)
        _edit(mid, "➕ <b>Новый администратор</b>\n\nВведите <b>user_id</b>:",
              kb_cancel("adm:admins"))
        ack(); return

    # Удалить администратора
    if payload.startswith("adm:deladmin:"):
        target = int(payload[len("adm:deladmin:"):])
        if target == user_id:
            _edit(mid, "⚠️ Нельзя удалить самого себя.", kb_back("adm:admins"))
            ack(); return
        _edit(mid, f"🗑️ Удалить администратора <code>{target}</code>?",
              kb_confirm_del_admin(target))
        ack(); return

    if payload.startswith("adm:confirmdeladmin:"):
        target = int(payload[len("adm:confirmdeladmin:"):])
        if target == user_id: ack("Нельзя удалить самого себя!"); return
        if not admin_delete(target):
            _edit(mid, "⚠️ Нельзя удалить последнего администратора!", kb_back("adm:admins"))
        else:
            _screen_admins(chat_id, mid)
            ack("✅ Удалён")
        return

    ack()


# ══════════════════════════════════════════════
# Администратор — текстовый ввод FSM
# ══════════════════════════════════════════════

def _admin_input(user_id: int, chat_id: int, text: str, state: str, mid: str) -> bool:

    def warn(msg: str) -> None:
        _send(chat_id, msg)

    # Редактирование поля конфига — обновляем тот же экран
    if state.startswith("edit:"):
        field = state[len("edit:"):]
        cfg_set(field, text)
        state_clear(user_id)
        if mid:
            if field == "welcome_text":    _screen_welcome(chat_id, mid)
            elif field == "contacts_text": _screen_contacts(chat_id, mid)
            else:                          _screen_buttons(chat_id, mid)
        return True

    # Добавление ссылки — шаг 1: текст
    if state == "addlink:text":
        state_set(user_id, "addlink:url", f"{mid}||{text}")
        if mid:
            _edit(mid,
                  f"➕ <b>Новая ссылка — шаг 2/2</b>\n\n"
                  f"Текст: <b>{text}</b>\n\n"
                  f"Введите <b>URL</b> (https://...):",
                  [[{"type": "callback", "text": "❌ Отмена", "payload": "adm:contacts"}]])
        return True

    # Добавление ссылки — шаг 2: URL
    if state == "addlink:url":
        parts    = (mid or "").split("||", 1)
        orig_mid = parts[0]
        lnk_text = parts[1] if len(parts) > 1 else ""
        if not text.startswith("http"):
            warn("⚠️ URL должен начинаться с https://. Попробуйте ещё раз:")
            return True
        link_add(lnk_text, text)
        state_clear(user_id)
        if orig_mid: _screen_contacts(chat_id, orig_mid)
        return True

    # Редактирование ссылки — шаг 1: новый текст
    if state.startswith("editlink:text:"):
        link_id = state[len("editlink:text:"):]
        state_set(user_id, f"editlink:url:{link_id}", f"{mid}||{text}")
        if mid:
            _edit(mid,
                  f"✏️ <b>Редактирование — шаг 2/2</b>\n\n"
                  f"Текст: <b>{text}</b>\n\n"
                  f"Введите новый <b>URL</b>:",
                  [[{"type": "callback", "text": "❌ Отмена", "payload": "adm:contacts"}]])
        return True

    # Редактирование ссылки — шаг 2: новый URL
    if state.startswith("editlink:url:"):
        link_id  = state[len("editlink:url:"):]
        parts    = (mid or "").split("||", 1)
        orig_mid = parts[0]
        new_text = parts[1] if len(parts) > 1 else ""
        if not text.startswith("http"):
            warn("⚠️ URL должен начинаться с https://. Попробуйте ещё раз:")
            return True
        link_update(link_id, new_text, text)
        state_clear(user_id)
        if orig_mid: _screen_contacts(chat_id, orig_mid)
        return True

    # Добавление администратора
    if state == "addadmin":
        if not text.lstrip("-").isdigit():
            warn("⚠️ user_id должен быть числом. Попробуйте ещё раз:")
            return True
        new_id = int(text)
        admin_add(new_id)
        state_clear(user_id)
        if mid: _screen_admins(chat_id, mid)
        return True

    return False
