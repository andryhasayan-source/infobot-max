"""
keyboards.py — Все клавиатуры бота.
"""
from database import cfg_all, links_all, admin_all


# ── Пользователь ───────────────────────────────

def kb_main(is_admin: bool = False) -> list:
    c = cfg_all()
    kb = [
        [{"type": "message", "text": c["button_myid"],     "payload": c["button_myid"]}],
        [{"type": "message", "text": c["button_chats"],    "payload": c["button_chats"]}],
        [{"type": "message", "text": c["button_contacts"], "payload": c["button_contacts"]}],
    ]
    if is_admin:
        kb.append([{"type": "message", "text": "⚙️ Админпанель", "payload": "⚙️ Админпанель"}])
    kb.append([{"type": "message", "text": "🏠 Главная", "payload": "🏠 Главная"}])
    return kb


def kb_contacts() -> list:
    return [
        [{"type": "link", "text": lnk["text"], "url": lnk["url"]}]
        for lnk in links_all()
    ]


# ── Администратор ──────────────────────────────

def kb_admin_main() -> list:
    return [
        [{"type": "callback", "text": "📝 Приветствие",   "payload": "adm:welcome"}],
        [{"type": "callback", "text": "📞 Контакты",       "payload": "adm:contacts"}],
        [{"type": "callback", "text": "🔘 Кнопки",         "payload": "adm:buttons"}],
        [{"type": "callback", "text": "👥 Администраторы", "payload": "adm:admins"}],
        [{"type": "callback", "text": "📊 Статистика",     "payload": "adm:stats"}],
        [{"type": "callback", "text": "🏠 На главную",     "payload": "adm:exit"}],
    ]


def kb_back(to: str = "adm:main") -> list:
    return [[{"type": "callback", "text": "◀️ Назад", "payload": to}]]


def kb_cancel(to: str = "adm:main") -> list:
    return [[{"type": "callback", "text": "❌ Отмена", "payload": to}]]


def kb_stats() -> list:
    return [
        [{"type": "callback", "text": "🗑️ Сбросить статистику", "payload": "adm:stats_reset"}],
        [{"type": "callback", "text": "◀️ Назад", "payload": "adm:main"}],
    ]


def kb_confirm_stats_reset() -> list:
    return [[
        {"type": "callback", "text": "✅ Сбросить",  "payload": "adm:stats_confirm_reset"},
        {"type": "callback", "text": "❌ Отмена",    "payload": "adm:stats"},
    ]]


def kb_admin_buttons() -> list:
    c = cfg_all()
    fields = [
        ("button_myid",     f"Кнопка 1: {c['button_myid']}"),
        ("button_chats",    f"Кнопка 2: {c['button_chats']}"),
        ("button_contacts", f"Кнопка 3: {c['button_contacts']}"),
    ]
    kb = [[{"type": "callback", "text": label, "payload": f"adm:edit:{key}"}]
          for key, label in fields]
    kb += kb_back()
    return kb


def kb_admin_contacts() -> list:
    lnks = links_all()
    kb   = []
    for lnk in lnks:
        short = lnk["text"][:20] + ("…" if len(lnk["text"]) > 20 else "")
        kb.append([
            {"type": "callback", "text": f"✏️ {short}", "payload": f"adm:editlink:{lnk['id']}"},
            {"type": "callback", "text": "🗑️",           "payload": f"adm:dellink:{lnk['id']}"},
        ])
    kb.append([{"type": "callback", "text": "➕ Добавить ссылку", "payload": "adm:addlink"}])
    kb += kb_back()
    return kb


def kb_confirm_del_link(link_id: str) -> list:
    return [[
        {"type": "callback", "text": "✅ Удалить", "payload": f"adm:confirmdellink:{link_id}"},
        {"type": "callback", "text": "❌ Отмена",  "payload": "adm:contacts"},
    ]]


def kb_admin_admins() -> list:
    kb = []
    for uid in admin_all():
        kb.append([
            {"type": "callback", "text": f"🆔 {uid}",   "payload": "adm:noop"},
            {"type": "callback", "text": "🗑️ Удалить", "payload": f"adm:deladmin:{uid}"},
        ])
    kb.append([{"type": "callback", "text": "➕ Добавить", "payload": "adm:addadmin"}])
    kb += kb_back()
    return kb


def kb_confirm_del_admin(uid: int) -> list:
    return [[
        {"type": "callback", "text": "✅ Удалить", "payload": f"adm:confirmdeladmin:{uid}"},
        {"type": "callback", "text": "❌ Отмена",  "payload": "adm:admins"},
    ]]
