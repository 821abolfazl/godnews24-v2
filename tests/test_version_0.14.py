# Tests for bot version 2026-11-18-0.14.
# Two user reports, 2026-11-18:
# 1. Add five new emoji categories to /add: 📱🏦📊📈📉 (mobile, bank, chart,
#    chart_up, chart_down). A word under one makes posts containing it carry
#    that emoji as the leading emoji (topic emojis checked before 🔴/🟡, like
#    the other topic emojis). 📱 already had built-in detection (MOBILE_RE);
#    the new part is that /add 📱 <word> now works and the word drives 📱
#    even for words the built-in regex doesn't know (e.g. «تلفن همراه»).
# 2. /status always showed 0 errors. Root cause: log_rejected() incremented
#    stats["rejected"] but never stats["errors"]; the only place that raised
#    the error counter was the rare kiosk-block crash handler (line 3438),
#    while every real send failure goes through log_rejected() with a why
#    starting with «خطا». Fix: log_rejected() counts why.startswith("خطا")
#    into stats["errors"], and the now-double-counting line in the kiosk
#    except is removed (that path also calls log_rejected with «خطا: برنامه»).
# 1. New emojis in EMOJI_CATEGORY_KEYS / EMOJI_LIST_STR / HELP_TEXT / prompts.
# 2. rules parsing / formatting round-trip with the new sections.
# 3. /add + /remove for all five new emojis (end to end via handle_command).
# 4. /rules lists the new emojis (empty and filled).
# 5. decide(): a word under each new emoji drives that leading emoji;
#    a topic emoji beats 🔴.
# 6. Error count: log_rejected with «خطا...» raises stats["errors"];
#    non-error rejections don't; same post twice counts once; /status and
#    the daily report show the count; /errors lists the failed posts.
# 7. Version pin 0.14; menu unchanged (20 buttons, same tail).
import os
import sys
import importlib.util
from datetime import timedelta

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot014", "/home/hatch/workspace/godnews24/bot.py")
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
    st = {"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0,
          "stats": {"day": DAY_ID, "posted": 0, "src": {}, "src_cat": {}, "ads": 0,
                    "rejected": 0, "runs": 0, "errors": 0, "first": None}}
    st.update(kw)
    return st

def fresh_rules():
    return {"blocked": [], "red": [], "yellow": [], "blue": [], "football": [], "tech": [],
            "plane": [], "car": [], "meat": [], "chicken": [], "alert": [], "hot": [],
            "basketball": [], "volleyball": [], "game": [], "jet": [], "fuel": [],
            "housing": [], "sheep": [], "motorcycle": [], "newspaper": [], "drug": [],
            "mobile": [], "bank": [], "chart": [], "chart_up": [], "chart_down": [],
            "markers": [], "strip_end": []}

def run_cmd(cmd, text):
    sent.clear()
    bot.handle_command(fresh_state(), cmd, text)
    return sent[-1] if sent else ""

# ---- 1. version / registry ----
check("version is 0.14", bot.BOT_VERSION == "2026-11-18-0.14", bot.BOT_VERSION)
NEW = {"📱": "mobile", "🏦": "bank", "📊": "chart", "📈": "chart_up", "📉": "chart_down"}
for emoji, key in NEW.items():
    check(f"EMOJI_CATEGORY_KEYS has {emoji}", bot.EMOJI_CATEGORY_KEYS.get(emoji) == key,
          bot.EMOJI_CATEGORY_KEYS.get(emoji))
    check(f"EMOJI_LIST_STR has {emoji}", emoji in bot.EMOJI_LIST_STR)
    check(f"RULES_SECTION_TITLES has {key}", bot.RULES_SECTION_TITLES.get(key) == f"[{emoji}]",
          bot.RULES_SECTION_TITLES.get(key))
    check(f"RULES_SECTIONS parses [{emoji}]", bot.RULES_SECTIONS.get(f"[{emoji}]") == key)
check("HELP_TEXT /add lists new emojis", all(e in bot.HELP_TEXT for e in NEW), bot.HELP_TEXT)
check("MENU_PROMPTS /add lists new emojis", all(e in bot.MENU_PROMPTS["/add"] for e in NEW))
check("MENU_PROMPTS /remove lists new emojis", all(e in bot.MENU_PROMPTS["/remove"] for e in NEW))

# ---- 2. rules parsing / formatting ----
txt = ("[📱]\nتلفن همراه\n[🏦]\nبانک ملی\n[📊]\nنمودار\n[📈]\nشاخص کل\n"
       "[📉]\nافت شاخص\n[💊]\nدارو\n")
p = bot.parse_rules_text(txt)
check("parse: mobile list", p["mobile"] == ["تلفن همراه"], p)
check("parse: bank list", p["bank"] == ["بانک ملی"], p)
check("parse: chart list", p["chart"] == ["نمودار"], p)
check("parse: chart_up list", p["chart_up"] == ["شاخص کل"], p)
check("parse: chart_down list", p["chart_down"] == ["افت شاخص"], p)
check("parse: old lists kept", p["drug"] == ["دارو"], p)
fmt = bot.format_rules_text(p)
check("format: all new section headers written",
      all(h in fmt for h in ("[📱]", "[🏦]", "[📊]", "[📈]", "[📉]")), fmt)
check("format: new words written",
      all(w in fmt for w in ("تلفن همراه", "بانک ملی", "نمودار", "شاخص کل", "افت شاخص")), fmt)
check("format+parse round-trip keeps new sections",
      bot.parse_rules_text(fmt)["chart_up"] == ["شاخص کل"])

# ---- 3. /add + /remove for the five new emojis ----
bot.DYNAMIC_RULES = fresh_rules()
WORDS = {"📱": "تلفن همراه", "🏦": "بانک ملی", "📊": "نمودار", "📈": "شاخص کل", "📉": "افت شاخص"}
for emoji, w in WORDS.items():
    msg = run_cmd("/add", f"/add {emoji} {w}")
    check(f"/add {emoji} {w} accepted", w in bot.DYNAMIC_RULES[NEW[emoji]] and "اضافه شد" in msg, msg)
check("/add duplicate under new emoji rejected",
      "همین حالا هم در" in run_cmd("/add", "/add 🏦 بانک ملی"))
msg = run_cmd("/remove", "/remove 📈 شاخص کل")
check("/remove 📈 removes", "شاخص کل" not in bot.DYNAMIC_RULES["chart_up"] and "حذف شد" in msg, msg)
check("/remove missing word under new emoji says so",
      "نیست" in run_cmd("/remove", "/remove 📈 شاخص کل"))
check("/add unknown emoji still rejected",
      "مثال" in run_cmd("/add", "/add 🟢 تست") and "تست" not in str(bot.DYNAMIC_RULES.values()))

# ---- 4. /rules lists the new emojis ----
bot.DYNAMIC_RULES = fresh_rules()
bot.DYNAMIC_RULES["bank"] = ["بانک ملی"]
out = run_cmd("/rules", "/rules")
check("/rules lists 🏦 with word", "🏦 (1): بانک ملی" in out, out)
check("/rules lists empty 📱", "📱 (0): —" in out, out)
check("/rules lists empty 📊📈📉",
      all(e in out for e in ("📊 (0): —", "📈 (0): —", "📉 (0): —")), out)

# ---- 5. decide(): the new lists drive the leading emoji ----
def decide_with(rules, title, category="general"):
    bot.DYNAMIC_RULES = rules
    return bot.decide({"title": title, "paras": [], "summary": "", "category": category})[0]

r = fresh_rules(); r["mobile"] = ["تلفن همراه"]
check("decide: mobile word → 📱 (not in built-in MOBILE_RE)",
      decide_with(r, "تلفن همراه جدید معرفی شد") == "📱")
r = fresh_rules(); r["bank"] = ["بانک ملی"]
check("decide: bank word → 🏦", decide_with(r, "بانک ملی نرخ سود را اعلام کرد") == "🏦")
r = fresh_rules(); r["chart"] = ["نمودار"]
check("decide: chart word → 📊", decide_with(r, "نمودار هفتگی بازار") == "📊")
r = fresh_rules(); r["chart_up"] = ["شاخص کل"]
check("decide: chart_up word → 📈", decide_with(r, "شاخص کل بورس بالا رفت") == "📈")
r = fresh_rules(); r["chart_down"] = ["افت شاخص"]
check("decide: chart_down word → 📉", decide_with(r, "افت شاخص بورس ادامه دارد") == "📉")
r = fresh_rules(); r["bank"] = ["بانک ملی"]; r["red"] = ["ترامپ"]
check("decide: topic emoji beats 🔴", decide_with(r, "ترامپ و بانک ملی") == "🏦")
r = fresh_rules(); r["red"] = ["ترامپ"]
check("decide: old red still 🔴", decide_with(r, "ترامپ سخنرانی کرد") == "🔴")
r = fresh_rules()
check("decide: no word → no new emoji", decide_with(r, "خبر معمولی روز") not in ("📱", "🏦", "📊", "📈", "📉"))

# ---- 6. the /status error-count bug ----
st = fresh_state()
bot.STATE_REF[0] = st
bot.log_rejected("AloNews", "خطا در ارسال", "خبر خراب یک", post_id=111)
check("error 1: errors=1 rejected=1",
      st["stats"]["errors"] == 1 and st["stats"]["rejected"] == 1, st["stats"])
bot.log_rejected("AloNews", "خطا در ارسال", "خبر خراب دو", post_id=222)
check("error 2: errors=2", st["stats"]["errors"] == 2, st["stats"])
bot.log_rejected("AloNews", "خطا در ارسال", "خبر خراب یک", post_id=111)
check("same failed post twice counts once", st["stats"]["errors"] == 2, st["stats"])
bot.log_rejected("AloNews", "تکراری", "خبر تکراری")
check("non-error rejection: errors unchanged, rejected+1",
      st["stats"]["errors"] == 2 and st["stats"]["rejected"] == 3, st["stats"])
bot.log_rejected("bot", "خطا: برنامه", "crash")
check("program error counts too", st["stats"]["errors"] == 3, st["stats"])
check("/status shows 3 خطا", "3 خطا" in bot.status_text(st), bot.status_text(st))
check("daily report shows 3 خطا",
      "⚠️ خطاها: 3" in bot.build_report(st, {}, DAY_ID), bot.build_report(st, {}, DAY_ID))
err_chunks = bot.rejected_text(st, "errors")
check("/errors lists the failed posts",
      any("خبر خراب یک" in c for c in err_chunks) and any("خبر خراب دو" in c for c in err_chunks),
      err_chunks)
bot.STATE_REF[0] = None

# ---- 7. version pin + menu unchanged ----
check("menu still 20 buttons", len(bot.MENU_BUTTONS) == 20, len(bot.MENU_BUTTONS))
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
