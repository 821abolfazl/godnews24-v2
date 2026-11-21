# Tests for bot version 2026-11-21-0.20.
# /muted (the list of muted sources/categories) is removed — /status already
# shows the same two lines whenever anything is muted, so /muted was
# redundant. In its menu slot, a new /unblock command removes a word from the
# blocked list ([ممنوع]), mirroring the /strip + /unstrip pair: /block adds,
# /unblock removes, both save rules.txt.
import os
import sys
import time
import copy
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot020", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

check("version is 0.20", bot.BOT_VERSION == "2026-11-21-0.20", bot.BOT_VERSION)

# ---- fakes ----
ADMIN_MSGS = []
SAVES = []

def fake_admin_send(text, reply_markup=None):
    ADMIN_MSGS.append(text)
    return True

bot.admin_send = fake_admin_send
bot.save_rules_file = lambda: SAVES.append("save")
bot.commit_rules = lambda: SAVES.append("commit")
bot.save_state = lambda state: None

REAL_RULES = copy.deepcopy(bot.DYNAMIC_RULES)

def fresh_state(**kw):
    st = {"tg_offset": 0, "last_post_ids": []}
    st.update(kw)
    return st

def reset_rules(blocked=("کلمه‌تستی", "دیگر", "🎮رایگان بازی کن و 4میلیون ببر")):
    bot.DYNAMIC_RULES = copy.deepcopy(REAL_RULES)
    bot.DYNAMIC_RULES["blocked"] = list(blocked)

def reset():
    ADMIN_MSGS.clear()
    SAVES.clear()

# ---- 1. /unblock removes a blocked word ----
reset(); reset_rules()
st = fresh_state()
bot.handle_command(st, "/unblock", "/unblock کلمه‌تستی")
check("unblock: word removed from blocked",
      "کلمه‌تستی" not in bot.DYNAMIC_RULES["blocked"], bot.DYNAMIC_RULES["blocked"])
check("unblock: other words stay",
      bot.DYNAMIC_RULES["blocked"] == ["دیگر", "🎮رایگان بازی کن و 4میلیون ببر"], bot.DYNAMIC_RULES["blocked"])
check("unblock: confirmation sent",
      any("حذف شد" in m and "کلمه‌تستی" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("unblock: rules saved", SAVES == ["save", "commit"], SAVES)

# ---- 2. /unblock on a word that is not blocked ----
reset(); reset_rules()
st = fresh_state()
bot.handle_command(st, "/unblock", "/unblock نبوده")
check("unblock missing: list unchanged",
      bot.DYNAMIC_RULES["blocked"] == ["کلمه‌تستی", "دیگر", "🎮رایگان بازی کن و 4میلیون ببر"], bot.DYNAMIC_RULES["blocked"])
check("unblock missing: says it is not blocked",
      any("در ممنوع نیست" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("unblock missing: rules NOT saved", SAVES == [], SAVES)

# ---- 3. /unblock with empty arg ----
reset(); reset_rules()
st = fresh_state()
bot.handle_command(st, "/unblock", "/unblock")
check("unblock empty: asks for the word",
      any("کلمه را هم بفرست" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("unblock empty: list unchanged", len(bot.DYNAMIC_RULES["blocked"]) == 3, bot.DYNAMIC_RULES["blocked"])

# ---- 4. the real case from tonight: emoji phrase ----
reset(); reset_rules()
st = fresh_state()
bot.handle_command(st, "/unblock", "/unblock 🎮رایگان بازی کن و 4میلیون ببر")
check("unblock emoji phrase: removed",
      "🎮رایگان بازی کن و 4میلیون ببر" not in bot.DYNAMIC_RULES["blocked"], bot.DYNAMIC_RULES["blocked"])

# ---- 5. /block still works (regression) ----
reset(); reset_rules()
st = fresh_state()
bot.handle_command(st, "/block", "/block تازه‌وارد")
check("block: word added", "تازه‌وارد" in bot.DYNAMIC_RULES["blocked"], bot.DYNAMIC_RULES["blocked"])
check("block: confirmation sent", any("به ممنوع اضافه شد" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("block: rules saved", SAVES == ["save", "commit"], SAVES)

# ---- 6. /muted is gone ----
check("muted gone: not in KNOWN_COMMANDS", "/muted" not in bot.KNOWN_COMMANDS, bot.KNOWN_COMMANDS)
check("unblock in KNOWN_COMMANDS", "/unblock" in bot.KNOWN_COMMANDS)
cmds = [c for _, c in bot.MENU_BUTTONS]
check("menu: still 20 buttons", len(bot.MENU_BUTTONS) == 20, len(bot.MENU_BUTTONS))
check("menu: /muted not in menu", "/muted" not in cmds, cmds)
check("menu: /unblock in /muted's old slot (right before /block)",
      cmds.index("/unblock") + 1 == cmds.index("/block"), cmds)
check("menu: /unblock label", bot.MENU_TEXT_TO_CMD.get("🔓 حذف از مسدودها") == "/unblock")
check("help: /muted gone", "/muted" not in bot.HELP_TEXT, bot.HELP_TEXT)
check("help: /unblock documented", "/unblock کلمه ← حذف کلمه از ممنوع" in bot.HELP_TEXT)
check("prompt: /unblock asks for the word", "ممنوع" in bot.MENU_PROMPTS.get("/unblock", ""), bot.MENU_PROMPTS.get("/unblock"))
check("menu tail order kept: delete, test, help last",
      cmds[-3:] == ["/delete", "/test", "/help"], cmds[-3:])

reset()
st = fresh_state()
bot.handle_command(st, "/muted", "/muted")
check("muted gone: /muted is now unknown command",
      any("دستور ناشناخته" in m for m in ADMIN_MSGS), ADMIN_MSGS)

# ---- 7. /status still shows muted sources (the reason /muted was redundant) ----
st = fresh_state(muted_sources=["AloNews"], muted_categories={"euronews": ["political"]})
txt = bot.status_text(st)
check("status: muted sources shown", "🔇 منبع‌های بی‌صدا: AloNews" in txt, txt)
check("status: muted categories shown", "🔇 دسته‌های بی‌صدا:" in txt and "euronews" in txt, txt)

# ---- 8. menu button flow: tap «حذف از مسدودها» -> prompt, then word -> removed ----
class Resp:
    def __init__(self, j): self._j = j
    def json(self): return self._j

def upd(uid, msg):
    return {"update_id": uid, "message": msg}

def run_updates(updates, pending=None):
    real_get = bot.requests.get
    bot.requests.get = lambda url, params=None, timeout=None: Resp({"ok": True, "result": updates})
    try:
        kw = {} if pending is None else {"menu_pending": pending, "menu_pending_ts": time.time()}
        st = fresh_state(**kw)
        changed = bot.process_commands(st)
        return st, changed
    finally:
        bot.requests.get = real_get

reset(); reset_rules()
msg = {"message_id": 6, "chat": {"id": 123}, "text": "🔓 حذف از مسدودها"}
st, changed = run_updates([upd(60, msg)])
check("menu button /unblock: prompt sent", any("ممنوع" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("menu button /unblock: pending set", st.get("menu_pending") == "/unblock", st.get("menu_pending"))

reset(); reset_rules()
msg = {"message_id": 7, "chat": {"id": 123}, "text": "کلمه‌تستی"}
st, changed = run_updates([upd(70, msg)], pending="/unblock")
check("menu flow /unblock: word removed", "کلمه‌تستی" not in bot.DYNAMIC_RULES["blocked"], bot.DYNAMIC_RULES["blocked"])
check("menu flow /unblock: confirmation sent", any("حذف شد" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("menu flow /unblock: pending cleared", st.get("menu_pending") is None, st.get("menu_pending"))

bot.DYNAMIC_RULES = REAL_RULES

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
