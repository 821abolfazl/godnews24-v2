# Tests for bot version 2026-11-13-0.03: menu reorder (pause/resume to the
# tail) + nine new emoji categories. Also covers the 0.02 regressions.
import os
import sys
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot003", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

bot.tg = lambda method, files=None, **data: True
bot.proxy_parts = lambda: ('<a href="https://t.me/proxy?server=1.1.1.1&port=443&secret=eeaa">پروکسی</a>😉',
                           'پروکسی😉 https://t.me/proxy?server=1.1.1.1&port=443&secret=eeaa')
bot.save_state = lambda state: None
sent = []
bot.admin_send = lambda text, reply_markup=None: sent.append(text) or True

NEW_KEYS = {"🚨": "alert", "🔥": "hot", "🏀": "basketball", "🏐": "volleyball",
            "🎮": "game", "🛩": "jet", "⛽️": "fuel", "🏘️": "housing", "🐑": "sheep"}
NEW_WORDS = {"alert": "هشدار", "hot": "داغ", "basketball": "بسکتبال",
             "volleyball": "والیبال", "game": "بازی", "jet": "جت‌خصوصی",
             "fuel": "سوخت", "housing": "ویلایی", "sheep": "گوسفند",
             "motorcycle": "موتورسواری", "newspaper": "روزنامه‌ای", "drug": "آسپرین",
             "mobile": "موبایلی", "bank": "بانکی", "chart": "نموداری",
             "chart_up": "صعودی", "chart_down": "نزولی", "un": "مللی"}

# ---- 1. version / basics ----
check("version is 0.03", bot.BOT_VERSION == "2026-11-13-0.03", bot.BOT_VERSION)
check("POLL_SECONDS is 10", bot.POLL_SECONDS == 10, bot.POLL_SECONDS)
check("menu still has 19 buttons", len(bot.MENU_BUTTONS) == 19, len(bot.MENU_BUTTONS))
src = open("bot.py", encoding="utf-8").read()
check("no price board refs", "price_board" not in src and "تابلو قیمت" not in src)
check("no doubled backslash-n in HELP_TEXT", "\\n" not in bot.HELP_TEXT)
check("support note still present", "عضوگیری" in bot.SUPPORT_TEXT, bot.SUPPORT_TEXT)
check("summary title still x", bot.SUMMARY_TITLE == "🍳 صبحانه خبری گادنیوز۲۴", bot.SUMMARY_TITLE)
check("18 emojis in EMOJI_LIST_STR", len(bot.EMOJI_LIST_STR.split("|")) == 18, bot.EMOJI_LIST_STR)
check("EMOJI_CATEGORY_KEYS has 18 entries", len(bot.EMOJI_CATEGORY_KEYS) == 18, len(bot.EMOJI_CATEGORY_KEYS))

# ---- 2. exact menu order (pause/resume moved to the tail) ----
cmds = [c for _, c in bot.MENU_BUTTONS]
want = ["/status", "/stats", "/rules", "/skipped", "/errors", "/send", "/muted",
        "/block", "/mute", "/unmute", "/remove", "/add", "/strip", "/unstrip",
        "/pause", "/resume", "/delete", "/test", "/help"]
check("menu order is exactly the requested layout", cmds == want, cmds)
check("pause and resume sit right before delete",
      cmds.index("/pause") == cmds.index("/delete") - 2 and
      cmds.index("/resume") == cmds.index("/delete") - 1, cmds)
check("last three are still delete, test, help", cmds[-3:] == ["/delete", "/test", "/help"], cmds[-3:])
check("help is very last", cmds[-1] == "/help")
check("no command lost or duplicated", sorted(cmds) == sorted(want), cmds)
check("all menu commands still known", all(c in bot.KNOWN_COMMANDS for c in cmds))
check("keyboard rows still 2 per row, help alone on last row",
      [len(r) for r in bot.menu_keyboard()["keyboard"]] == [2] * 9 + [1])

# ---- 3. pause / resume still work ----
st = {"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0, "paused": False}
bot.handle_command(st, "/pause", "/pause")
check("pause sets paused", st.get("paused") is True, st)
bot.handle_command(st, "/resume", "/resume")
check("resume clears paused", st.get("paused") is False, st)

# ---- 4. /add works for all 18 emojis ----
bot.DYNAMIC_RULES = {"blocked": [], "red": [], "yellow": [], "blue": [], "football": [],
                     "tech": [], "plane": [], "car": [], "meat": [], "chicken": [],
                     "alert": [], "hot": [], "basketball": [], "volleyball": [],
                     "game": [], "jet": [], "fuel": [], "housing": [], "sheep": [],
                     "strip_end": []}
bot.save_rules_file = lambda: None
bot.commit_rules = lambda: None
ALL_WORDS = {"red": "سرخط", "yellow": "بورسی", "blue": "مدرسه‌ای", "football": "فوتبالی",
             "tech": "رباتی", "plane": "پروازی", "car": "ماشینی", "meat": "گوشتی",
             "chicken": "مرغی"}
ALL_WORDS.update(NEW_WORDS)
ok_add = True
for emoji, key in bot.EMOJI_CATEGORY_KEYS.items():
    sent.clear()
    bot.handle_command({"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0},
                       "/add", f"/add {emoji} {ALL_WORDS[key]}")
    if ALL_WORDS[key] not in bot.DYNAMIC_RULES[key]:
        ok_add = False
        print("   add failed for", emoji, key)
check("/add works for all 26 emojis", ok_add)
check("VS16 fuel add (⛽️) registers under fuel", "سوخت" in bot.DYNAMIC_RULES["fuel"])
check("VS16 housing add (🏘️) registers under housing", "ویلایی" in bot.DYNAMIC_RULES["housing"])

# ---- 5. /remove works for a new emoji ----
sent.clear()
bot.handle_command({"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0},
                   "/remove", "/remove 🐑 گوسفند")
check("/remove 🐑 works", "گوسفند" not in bot.DYNAMIC_RULES["sheep"], sent)
bot.DYNAMIC_RULES["sheep"] = ["گوسفند"]

# ---- 6. parse + format of the new sections ----
parsed = bot.parse_rules_text("[⛽️]\nسوخت\n[🏘️]\nویلایی\n[🚨]\nهشدار\n[🛩]\nجت‌خصوصی\n")
check("parse: VS16 [⛽️] header read as fuel", parsed["fuel"] == ["سوخت"], parsed["fuel"])
check("parse: VS16 [🏘️] header read as housing", parsed["housing"] == ["ویلایی"], parsed["housing"])
check("parse: [🚨] and [🛩] headers read", parsed["alert"] == ["هشدار"] and parsed["jet"] == ["جت‌خصوصی"], parsed)
fmt = bot.format_rules_text(bot.DYNAMIC_RULES)
check("format: all 9 new sections written",
      all(h in fmt for h in ("[🚨]", "[🔥]", "[🏀]", "[🏐]", "[🎮]", "[🛩]", "[⛽️]", "[🏘️]", "[🐑]")), fmt[:400])

# ---- 7. /rules shows all 18 emojis ----
sent.clear()
bot.handle_command({"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0},
                   "/rules", "/rules")
rules_text = sent[-1] if sent else ""
check("/rules lists all 18 emojis",
      all(e in rules_text for e in ("🔴", "🟡", "🔵", "⚽", "🤖", "✈️", "🚙", "🥩", "🍗",
                                    "🚨", "🔥", "🏀", "🏐", "🎮", "🛩", "⛽️", "🏘️", "🐑")), rules_text[:300])

# ---- 8. decide() lead emoji for each new list ----
def decide_title(title):
    return bot.decide({"title": title, "paras": [], "summary": "", "category": "general"})

EXPECT = {"alert": ("🚨", "🔻"), "hot": ("🔥", "🔻"), "basketball": ("🏀", "🔹"),
          "volleyball": ("🏐", "🔹"), "game": ("🎮", "🔹"), "jet": ("🛩", "🔹"),
          "fuel": ("⛽️", "🔹"), "housing": ("🏘️", "🔸"), "sheep": ("🐑", "🔹"),
          "un": ("🇺🇳", "🔹")}
for key, (emoji, marker) in EXPECT.items():
    got = decide_title(f"{NEW_WORDS[key]} خبر جدید")
    check(f"decide {key} word → {emoji}", got == (emoji, marker), got)
check("topic beats red: alert word + red word → 🚨",
      decide_title("هشدار سپاه خبر جدید")[0] == "🚨")
check("housing via HOUSING_RE still works (مسکن, no list word)",
      decide_title("قیمت مسکن بالا رفت")[0] == "🏘️")
check("petrol بنزین still → 🔵 (existing behaviour)",
      decide_title("قیمت بنزین اعلام شد")[0] == "🔵")
check("HELP_TEXT /add line lists all 18",
      "🚨|🔥|🏀|🏐|🎮|🛩|⛽️|🏘️|🐑" in bot.HELP_TEXT)
check("menu prompts list all 18 emojis",
      "🚨🔥🏀🏐🎮🛩⛽️🏘️🐑" in bot.MENU_PROMPTS["/add"] and
      "🚨🔥🏀🏐🎮🛩⛽️🏘️🐑" in bot.MENU_PROMPTS["/remove"])

# ---- 9. 0.02 regressions ----
check("0.02: /add 🥩 still works", "گوشتی" in bot.DYNAMIC_RULES["meat"])
check("0.02: decide meat word → 🥩",
      decide_title("قیمت گوشتی")[0] == "🥩")
check("0.01: proxy cap still 300",
      __import__("inspect").signature(bot.prepare_proxies).parameters["max_checks"].default == 300)
check("0.01: breakdown new format still works",
      bot.category_breakdown_lines({"AloNews": {"political": 3, "general": 1}}) ==
      ["AloNews:", "🔴 سیاسی ۳", "🔵 عمومی ۱"])

print()
print(f"PASS {len(PASS)} FAIL {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
