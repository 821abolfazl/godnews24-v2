# Tests for bot version 2026-11-13-0.10:
# 1. /rules no longer has a separate "ایموجی پاراگراف" line; each emoji row
#    shows its paragraph marker right in front of it ("🔻 🔴 (1): ...").
# 2. /marker accepts several leading emojis at once: /marker ⚽ 🥩 🔻 sets
#    the marker for both (last token is the marker, the rest are leads).
# 3. Menu: the /add and /marker buttons swap places.
import os
import sys
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot010", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

sent = []
bot.admin_send = lambda text, reply_markup=None: sent.append(text) or True
bot.save_rules_file = lambda: None
bot.commit_rules = lambda: None
bot.tg = lambda method, files=None, **data: True

def fresh_state():
    st = {"rejected": [], "stats": {}}
    bot.STATE_REF[0] = st
    return st

def reset_rules():
    # همه‌ی دسته‌ها رو خالی می‌کنیم تا خروجی /rules قطعی باشه
    # (rules.txt واقعی کلمه داره و تعدادها رو عوض می‌کنه)
    for k in list(bot.DYNAMIC_RULES.keys()):
        bot.DYNAMIC_RULES[k] = []
    bot.DYNAMIC_RULES["red"] = ["سپاه"]
    bot.DYNAMIC_RULES["football"] = ["فوتبال"]
    bot.DYNAMIC_RULES["meat"] = ["قیمت گوشت"]
    sent.clear()

# ---- 1. /rules display: marker in front of each emoji, no separate line ----
reset_rules()
st = fresh_state()
bot.handle_command(st, "/rules")
out = sent[-1]
check("rules: no separate markers line", "ایموجی پاراگراف" not in out, out)
check("rules: red row shows default marker in front", "🔻 🔴 (1): سپاه" in out, out)
check("rules: football row shows default marker in front", "🔹 ⚽ (1): فوتبال" in out, out)
check("rules: meat row shows default marker in front", "🔹 🥩 (1): قیمت گوشت" in out, out)
check("rules: yellow default is 🔸", "🔸 🟡 (0): —" in out, out)
check("rules: car default is 🔸", "🔸 🚙 (0): —" in out, out)
check("rules: alert default is 🔻", "🔻 🚨 (0): —" in out, out)
check("rules: blocked/strip rows have no marker prefix",
      "ممنوع (0): —" in out and "پاک شود از آخر متن (0): —" in out, out)
# override shows instead of the default
bot.DYNAMIC_RULES["markers"] = ["⚽ 🔻", "🔴 🔸"]
sent.clear()
bot.handle_command(st, "/rules")
out = sent[-1]
check("rules: football override shown", "🔻 ⚽ (1): فوتبال" in out, out)
check("rules: red override shown", "🔸 🔴 (1): سپاه" in out, out)
check("rules: meat still default", "🔹 🥩 (1): قیمت گوشت" in out, out)

# ---- 1b. the helper ----
reset_rules()
check("helper: red default 🔻", bot._effective_marker("🔴") == "🔻")
check("helper: yellow default 🔸", bot._effective_marker("🟡") == "🔸")
check("helper: football default 🔹", bot._effective_marker("⚽") == "🔹")
check("helper: VS16 label normalized", bot._effective_marker("⛽️") == "🔹")
bot.DYNAMIC_RULES["markers"] = ["⛽️ 🔸"]
check("helper: override wins", bot._effective_marker("⛽️") == "🔸")

# ---- 2. /marker with several leads at once ----
reset_rules()
st = fresh_state()
bot.handle_command(st, "/marker", "/marker ⚽ 🥩 🔻")
check("marker: multi sets both", bot.DYNAMIC_RULES.get("markers") == ["⚽ 🔻", "🥩 🔻"], bot.DYNAMIC_RULES.get("markers"))
check("marker: multi confirms both leads", "✅" in sent[-1] and "⚽" in sent[-1] and "🥩" in sent[-1] and "🔻" in sent[-1], sent[-1])
check("marker: overrides reflect both", bot.marker_overrides() == {"⚽": "🔻", "🥩": "🔻"}, bot.marker_overrides())
# a later single set replaces only its own lead
bot.handle_command(st, "/marker", "/marker 🥩 🔹")
check("marker: single set replaces only its lead",
      bot.DYNAMIC_RULES.get("markers") == ["⚽ 🔻", "🥩 🔹"], bot.DYNAMIC_RULES.get("markers"))
# three leads at once
bot.handle_command(st, "/marker", "/marker 🔴 🚨 🔥 🔻")
check("marker: three leads at once",
      bot.DYNAMIC_RULES.get("markers") == ["⚽ 🔻", "🥩 🔹", "🔴 🔻", "🚨 🔻", "🔥 🔻"], bot.DYNAMIC_RULES.get("markers"))
# single lead still sets (old behaviour)
bot.handle_command(st, "/marker", "/marker 🔵 🔸")
check("marker: single lead still works", "🔵 🔸" in bot.DYNAMIC_RULES.get("markers"), bot.DYNAMIC_RULES.get("markers"))
# single lead alone still removes (old behaviour)
bot.handle_command(st, "/marker", "/marker 🥩")
check("marker: single lead alone removes it", "🥩 🔹" not in bot.DYNAMIC_RULES.get("markers") and "⚽ 🔻" in bot.DYNAMIC_RULES.get("markers"), bot.DYNAMIC_RULES.get("markers"))
# garbage is rejected
before = list(bot.DYNAMIC_RULES.get("markers"))
bot.handle_command(st, "/marker", "/marker ⚽ کلمه")
check("marker: non-emoji marker rejected", bot.DYNAMIC_RULES.get("markers") == before and "مثال" in sent[-1], sent[-1])
# decide() uses the multi-set override
bot.DYNAMIC_RULES["markers"] = ["⚽ 🔻"]
check("marker: decide uses multi-set override",
      bot.decide({"title": "فوتبال ایران", "category": "sports", "summary": ""}) == ("⚽", "🔻"))

# ---- 2b. rules.txt storage unchanged ----
reset_rules()
bot.DYNAMIC_RULES["markers"] = ["⚽ 🔻", "🥩 🔻"]
formatted = bot.format_rules_text()
check("storage: markers section still in rules.txt",
      "[ایموجی پاراگراف]\n⚽ 🔻\n🥩 🔻" in formatted, formatted)

# ---- 3. menu: /add and /marker swapped ----
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu: /add before /remove", labels.index("➕ اضافه به ایموجی") < labels.index("➖ حذف از ایموجی"))
check("menu: /marker after /remove", labels.index("🔻 نشانه‌ی پاراگراف") > labels.index("➖ حذف از ایموجی"))
check("menu: /marker still before /strip", labels.index("🔻 نشانه‌ی پاراگراف") < labels.index("✂️ پاک‌شونده اضافه"))
check("menu: still 20 buttons", len(labels) == 20, len(labels))
check("menu: tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])
check("menu: marker prompt mentions several leads", "⚽ 🥩 🔻" in bot.MENU_PROMPTS["/marker"], bot.MENU_PROMPTS["/marker"])
check("help: marker line mentions several leads", "⚽ 🥩 🔻" in bot.HELP_TEXT, bot.HELP_TEXT)

check("version: is 0.10", bot.BOT_VERSION == "2026-11-13-0.10", bot.BOT_VERSION)

print()
print(f"Passed: {len(PASS)}, Failed: {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
