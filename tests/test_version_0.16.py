# Tests for bot version 2026-11-19-0.16.
# New emoji category 🦦 («otter», same shape as the 0.14/0.15 categories),
# with an empty [🦦] section in rules.txt — words are added later with
# /add 🦦 <word>, like the empty 📊/📈/📉 categories in 0.14.
# 1. 🦦 in EMOJI_CATEGORY_KEYS / EMOJI_LIST_STR / HELP_TEXT / prompts.
# 2. rules parsing / formatting round-trip with the [🦦] section.
# 3. /add 🦦 سمور + /remove work end to end via handle_command.
# 4. /rules lists 🦦 (empty and filled).
# 5. decide(): «سمور» in the title → 🦦; topic beats 🔴; without the
#    word in the list, no 🦦 (the category is word-driven, like the others).
# 6. The shipped rules.txt parses with an empty [🦦] section.
# 7. Version pin 0.16; menu unchanged (20 buttons, same tail).
import os
import sys
import importlib.util
from datetime import timedelta

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot016", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

sent = []
bot.tg = lambda method, files=None, **data: True
bot.admin_send = lambda text, reply_markup=None: sent.append(text) or True
bot.proxy_parts = lambda: ('<a href="https://t.me/proxy?server=1.1.1.1&port=443&secret=eeaa">پروکسی</a>😉',
                           'پروکسی😉 https://t.me/proxy?server=1.1.1.1&port=443&secret=eeaa')
bot.save_state = lambda state: None
bot.save_rules_file = lambda: None
bot.commit_rules = lambda: None

DAY_ID = (bot.tehran_now() - timedelta(hours=8)).strftime("%Y-%m-%d")

def fresh_state(**kw):
    st = {"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0}
    st.update(kw)
    return st

def fresh_rules():
    return {"blocked": [], "red": [], "yellow": [], "blue": [], "football": [], "tech": [],
            "plane": [], "car": [], "meat": [], "chicken": [], "alert": [], "hot": [],
            "basketball": [], "volleyball": [], "game": [], "jet": [], "fuel": [],
            "housing": [], "sheep": [], "motorcycle": [], "newspaper": [], "drug": [],
            "mobile": [], "bank": [], "chart": [], "chart_up": [], "chart_down": [],
            "un": [], "otter": [], "markers": [], "strip_end": []}

def run_cmd(cmd, text):
    sent.clear()
    bot.handle_command(fresh_state(), cmd, text)
    return sent[-1] if sent else ""

# ---- 1. version / registry ----
check("version is 0.16", bot.BOT_VERSION == "2026-11-19-0.16", bot.BOT_VERSION)
check("EMOJI_CATEGORY_KEYS has 🦦", bot.EMOJI_CATEGORY_KEYS.get("🦦") == "otter",
      bot.EMOJI_CATEGORY_KEYS.get("🦦"))
check("EMOJI_LIST_STR has 🦦", "🦦" in bot.EMOJI_LIST_STR)
check("RULES_SECTION_TITLES has otter", bot.RULES_SECTION_TITLES.get("otter") == "[🦦]")
check("RULES_SECTIONS parses [🦦]", bot.RULES_SECTIONS.get("[🦦]") == "otter")
check("HELP_TEXT /add lists 🦦", "🦦" in bot.HELP_TEXT)
check("MENU_PROMPTS /add lists 🦦", "🦦" in bot.MENU_PROMPTS["/add"])
check("MENU_PROMPTS /remove lists 🦦", "🦦" in bot.MENU_PROMPTS["/remove"])
check("🦦 is a single emoji for /add", bot._is_single_emoji("🦦"))

# ---- 2. rules parsing / formatting ----
p = bot.parse_rules_text("[🦦]\nسمور\n[💊]\nدارو\n")
check("parse: otter list", p["otter"] == ["سمور"], p)
check("parse: old lists kept", p["drug"] == ["دارو"], p)
fmt = bot.format_rules_text(p)
check("format: [🦦] header written", "[🦦]" in fmt, fmt)
check("format: سمور written", "سمور" in fmt, fmt)
check("format+parse round-trip keeps otter",
      bot.parse_rules_text(fmt)["otter"] == ["سمور"])
check("parse: empty [🦦] section", bot.parse_rules_text("[🦦]\n[💊]\nدارو\n")["otter"] == [])

# ---- 3. /add + /remove for 🦦 ----
bot.DYNAMIC_RULES = fresh_rules()
msg = run_cmd("/add", "/add 🦦 سمور")
check("/add 🦦 سمور accepted",
      "سمور" in bot.DYNAMIC_RULES["otter"] and "اضافه شد" in msg, msg)
check("/add duplicate under 🦦 rejected",
      "همین حالا هم در" in run_cmd("/add", "/add 🦦 سمور"))
msg = run_cmd("/remove", "/remove 🦦 سمور")
check("/remove 🦦 removes", "سمور" not in bot.DYNAMIC_RULES["otter"] and "حذف شد" in msg, msg)

# ---- 4. /rules lists 🦦 ----
bot.DYNAMIC_RULES = fresh_rules()
bot.DYNAMIC_RULES["otter"] = ["سمور"]
out = run_cmd("/rules", "/rules")
check("/rules lists 🦦 with word", "🦦 (1): سمور" in out, out)
bot.DYNAMIC_RULES = fresh_rules()
out = run_cmd("/rules", "/rules")
check("/rules lists empty 🦦", "🦦 (0): —" in out, out)

# ---- 5. decide(): سمور → 🦦 ----
def decide_with(rules, title, category="general"):
    bot.DYNAMIC_RULES = rules
    return bot.decide({"title": title, "paras": [], "summary": "", "category": category})[0]

r = fresh_rules(); r["otter"] = ["سمور"]
check("decide: سمور → 🦦",
      decide_with(r, "سمور آبی در خطر انقراض است") == "🦦")
r = fresh_rules(); r["otter"] = ["سمور"]; r["red"] = ["ترامپ"]
check("decide: topic beats 🔴", decide_with(r, "ترامپ و سمور آبی") == "🦦")
r = fresh_rules()
check("decide: no word in list → no 🦦",
      decide_with(r, "سمور آبی در خطر انقراض است") != "🦦")
r = fresh_rules(); r["otter"] = ["سمور"]
bot.DYNAMIC_RULES = r
check("decide: marker for 🦦 is 🔹",
      bot.decide({"title": "سمور آبی در خطر انقراض است", "paras": [],
                  "summary": "", "category": "general"}) == ("🦦", "🔹"))

# ---- 6. the shipped rules.txt ----
shipped = open("rules.txt", encoding="utf-8").read()
sp = bot.parse_rules_text(shipped)
check("shipped rules.txt: [🦦] section exists (empty)", sp["otter"] == [], sp["otter"])
check("shipped rules.txt: old words intact",
      "بورس" in sp["yellow"] and "ترامپ" in sp["red"] and "دارو" in sp["drug"]
      and "سازمان ملل" in sp["un"], sp)

# ---- 7. version pin + menu unchanged ----
check("menu still 20 buttons", len(bot.MENU_BUTTONS) == 20, len(bot.MENU_BUTTONS))
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
