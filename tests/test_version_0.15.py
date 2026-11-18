# Tests for bot version 2026-11-18-0.15.
# Two user reports, 2026-11-18 (screenshot of @GodNews24, 23:35):
# 1. A Digiato post ended with an extra paragraph: the title repeated plus
#    «The post appeared first on دیجیاتو.» — Digiato's English WordPress
#    footer credit. The bot's source-stripping only knew Persian patterns,
#    so the whole credit paragraph went out (with a 🔹 marker, looking like
#    real content). Fix: clean_paras() drops any paragraph containing
#    «appeared first on» (case-insensitive); it is never news content.
# 2. Use 🇺🇳 for the word «سازمان ملل»: new emoji category «un» (same shape
#    as the 0.14 categories), with «سازمان ملل» pre-filled under it in
#    rules.txt, so /add 🇺🇳 <word> also works from now on.
# 1. clean_paras drops the Digiato footer paragraph (exact case from the
#    screenshot), keeps real paragraphs; case-insensitive; a paragraph that
#    merely mentions دیجیاتو is kept.
# 2. 🇺🇳 in EMOJI_CATEGORY_KEYS / EMOJI_LIST_STR / HELP_TEXT / prompts.
# 3. rules parsing / formatting round-trip with the [🇺🇳] section.
# 4. /add 🇺🇳 سازمان ملل + /remove work end to end via handle_command.
# 5. /rules lists 🇺🇳 (empty and filled).
# 6. decide(): «سازمان ملل» in the title → 🇺🇳; topic beats 🔴; without the
#    word in the list, no 🇺🇳 (the category is word-driven, like the others).
# 7. The shipped rules.txt parses with «سازمان ملل» under [🇺🇳].
# 8. Version pin 0.15; menu unchanged (20 buttons, same tail).
import os
import sys
import importlib.util
from datetime import timedelta

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot015", "/home/hatch/workspace/godnews24/bot.py")
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
            "un": [], "markers": [], "strip_end": []}

def run_cmd(cmd, text):
    sent.clear()
    bot.handle_command(fresh_state(), cmd, text)
    return sent[-1] if sent else ""

# ---- 1. version / registry ----
check("version is 0.15", bot.BOT_VERSION == "2026-11-18-0.15", bot.BOT_VERSION)
check("EMOJI_CATEGORY_KEYS has 🇺🇳", bot.EMOJI_CATEGORY_KEYS.get("🇺🇳") == "un",
      bot.EMOJI_CATEGORY_KEYS.get("🇺🇳"))
check("EMOJI_LIST_STR has 🇺🇳", "🇺🇳" in bot.EMOJI_LIST_STR)
check("RULES_SECTION_TITLES has un", bot.RULES_SECTION_TITLES.get("un") == "[🇺🇳]")
check("RULES_SECTIONS parses [🇺🇳]", bot.RULES_SECTIONS.get("[🇺🇳]") == "un")
check("HELP_TEXT /add lists 🇺🇳", "🇺🇳" in bot.HELP_TEXT)
check("MENU_PROMPTS /add lists 🇺🇳", "🇺🇳" in bot.MENU_PROMPTS["/add"])
check("MENU_PROMPTS /remove lists 🇺🇳", "🇺🇳" in bot.MENU_PROMPTS["/remove"])
check("🇺🇳 is a single emoji for /add", bot._is_single_emoji("🇺🇳"))

# ---- 2. the Digiato footer paragraph ----
TITLE = "ابداع دانشمندان: توسعه ریزربات‌هایی که می‌توانند لخته‌های خون را از بین ببرند"
BODY = ("پژوهشگران مؤسسه فناوری فدرال زوریخ ریزربات‌های مغناطیسی ساخته‌اند که داروهای "
        "حل‌کننده لخته خون را به محل انسداد هدایت می‌کنند.")
FOOTER = f"{TITLE} . The post appeared first on دیجیاتو ."
paras = bot.clean_paras(f"{BODY}\n{FOOTER}", 12000)
check("footer paragraph dropped", paras == [BODY], paras)
check("footer dropped case-insensitively",
      bot.clean_paras("متن خبر.\nTHE POST APPEARED FIRST ON X.", 12000) == ["متن خبر."])
check("paragraph merely mentioning دیجیاتو is kept",
      bot.clean_paras("دیجیاتو گزارش داد که خبر مهمی رخ داده است.", 12000) ==
      ["دیجیاتو گزارش داد که خبر مهمی رخ داده است."])
check("footer mid-text dropped, rest kept",
      bot.clean_paras(f"{BODY}\n{FOOTER}\nپاراگراف بعدی خبر.", 12000) == [BODY, "پاراگراف بعدی خبر."])
# the RSS path: summary minus title, through strip_end_source, like fetch_feed does
rss_paras = bot.strip_end_source([p for p in bot.clean_paras(f"{BODY}\n{FOOTER}", 12000)
                                  if p != TITLE])
check("RSS path: no footer para survives", rss_paras == [BODY], rss_paras)

# ---- 3. rules parsing / formatting ----
p = bot.parse_rules_text("[🇺🇳]\nسازمان ملل\n[💊]\nدارو\n")
check("parse: un list", p["un"] == ["سازمان ملل"], p)
check("parse: old lists kept", p["drug"] == ["دارو"], p)
fmt = bot.format_rules_text(p)
check("format: [🇺🇳] header written", "[🇺🇳]" in fmt, fmt)
check("format: سازمان ملل written", "سازمان ملل" in fmt, fmt)
check("format+parse round-trip keeps un",
      bot.parse_rules_text(fmt)["un"] == ["سازمان ملل"])

# ---- 4. /add + /remove for 🇺🇳 ----
bot.DYNAMIC_RULES = fresh_rules()
msg = run_cmd("/add", "/add 🇺🇳 سازمان ملل")
check("/add 🇺🇳 سازمان ملل accepted",
      "سازمان ملل" in bot.DYNAMIC_RULES["un"] and "اضافه شد" in msg, msg)
check("/add duplicate under 🇺🇳 rejected",
      "همین حالا هم در" in run_cmd("/add", "/add 🇺🇳 سازمان ملل"))
msg = run_cmd("/remove", "/remove 🇺🇳 سازمان ملل")
check("/remove 🇺🇳 removes", "سازمان ملل" not in bot.DYNAMIC_RULES["un"] and "حذف شد" in msg, msg)

# ---- 5. /rules lists 🇺🇳 ----
bot.DYNAMIC_RULES = fresh_rules()
bot.DYNAMIC_RULES["un"] = ["سازمان ملل"]
out = run_cmd("/rules", "/rules")
check("/rules lists 🇺🇳 with word", "🇺🇳 (1): سازمان ملل" in out, out)
bot.DYNAMIC_RULES = fresh_rules()
out = run_cmd("/rules", "/rules")
check("/rules lists empty 🇺🇳", "🇺🇳 (0): —" in out, out)

# ---- 6. decide(): سازمان ملل → 🇺🇳 ----
def decide_with(rules, title, category="general"):
    bot.DYNAMIC_RULES = rules
    return bot.decide({"title": title, "paras": [], "summary": "", "category": category})[0]

r = fresh_rules(); r["un"] = ["سازمان ملل"]
check("decide: سازمان ملل → 🇺🇳",
      decide_with(r, "سازمان ملل قطعنامه جدیدی صادر کرد") == "🇺🇳")
r = fresh_rules(); r["un"] = ["سازمان ملل"]; r["red"] = ["ترامپ"]
check("decide: topic beats 🔴", decide_with(r, "ترامپ و سازمان ملل") == "🇺🇳")
r = fresh_rules()
check("decide: no word in list → no 🇺🇳",
      decide_with(r, "سازمان ملل قطعنامه جدیدی صادر کرد") != "🇺🇳")
r = fresh_rules(); r["un"] = ["سازمان ملل"]
bot.DYNAMIC_RULES = r
check("decide: marker for 🇺🇳 is 🔹",
      bot.decide({"title": "سازمان ملل قطعنامه جدیدی صادر کرد", "paras": [],
                  "summary": "", "category": "general"}) == ("🇺🇳", "🔹"))

# ---- 7. the shipped rules.txt ----
shipped = open("rules.txt", encoding="utf-8").read()
sp = bot.parse_rules_text(shipped)
check("shipped rules.txt: سازمان ملل under [🇺🇳]", sp["un"] == ["سازمان ملل"], sp["un"])
check("shipped rules.txt: old words intact",
      "بورس" in sp["yellow"] and "ترامپ" in sp["red"] and "دارو" in sp["drug"], sp)

# ---- 8. version pin + menu unchanged ----
check("menu still 20 buttons", len(bot.MENU_BUTTONS) == 20, len(bot.MENU_BUTTONS))
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
