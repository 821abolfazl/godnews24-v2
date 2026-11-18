# Tests for bot version 2026-11-13-0.05: third dedup check (exact title,
# fuller item wins) + three new emoji categories (🏍️ 📰 💊).
# Also covers the 0.04 regressions.
import hashlib
import os
import sys
import time
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot005", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

bot.tg = lambda method, files=None, **data: True
bot.proxy_parts = lambda: ('<a href="https://t.me/proxy?server=1.1.1.1&port=443&secret=<redacted>">پروکسی</a>😉',
                           'پروکسی😉 https://t.me/proxy?server=1.1.1.1&port=443&secret=<redacted>')
bot.save_state = lambda state: None
sent = []
bot.admin_send = lambda text, reply_markup=None: sent.append(text) or True
bot.save_rules_file = lambda: None
bot.commit_rules = lambda: None

NOW = time.time()
def mk(id_, title, summary, ts, kind=None):
    d = {"id": id_, "title": title, "summary": summary,
         "paras": [summary] if summary else [], "ts": ts,
         "category": "general", "src": "test"}
    if kind:
        d["kind"] = kind
    return d

TITLE = "مدارس تهران فردا دایر هست"
SHORT_SUM = ""
LONG_SUM = "طبق تصمیم کمیته‌ی اضطرار، مدارس فردا دایر هستند، اما دانش‌آموزان اجازه‌ی حضور در حیاط مدرسه را ندارند."

# ---- 1. version / basics ----
check("version is 0.05", bot.BOT_VERSION == "2026-11-13-0.05", bot.BOT_VERSION)
check("POLL_SECONDS is 10", bot.POLL_SECONDS == 10, bot.POLL_SECONDS)
check("menu still has 19 buttons", len(bot.MENU_BUTTONS) == 19, len(bot.MENU_BUTTONS))
cmds = [c for _, c in bot.MENU_BUTTONS]
want = ["/status", "/stats", "/rules", "/skipped", "/errors", "/send", "/muted",
        "/block", "/mute", "/unmute", "/remove", "/add", "/strip", "/unstrip",
        "/pause", "/resume", "/delete", "/test", "/help"]
check("menu order unchanged", cmds == want, cmds)
src = open("bot.py", encoding="utf-8").read()
check("no price board refs", "price_board" not in src and "تابلو قیمت" not in src)
check("no doubled backslash-n in HELP_TEXT", "\\n" not in bot.HELP_TEXT)
check("support note still present", "عضوگیری" in bot.SUPPORT_TEXT)
check("summary title still x", bot.SUMMARY_TITLE == "🍳 صبحانه خبری گادنیوز۲۴", bot.SUMMARY_TITLE)
check("21 emojis in EMOJI_LIST_STR", len(bot.EMOJI_LIST_STR.split("|")) == 21, bot.EMOJI_LIST_STR)
check("EMOJI_CATEGORY_KEYS has 21 entries", len(bot.EMOJI_CATEGORY_KEYS) == 21, len(bot.EMOJI_CATEGORY_KEYS))
check("rules.txt md5 unchanged", hashlib.md5(open("rules.txt", "rb").read()).hexdigest() == "405e5a6f9908871c301cba069bb0b14e")
check("news.yml md5 unchanged", hashlib.md5(open("news.yml", "rb").read()).hexdigest() == "d5e01294585b37c209ff027ca5ae8a3f")

# ---- 2. norm_title ----
check("norm_title strips punctuation and extra spaces",
      bot.norm_title("مدارس  تهران، فردا دایر هست!") == TITLE)
check("norm_title normalizes Arabic yeh/keh",
      bot.norm_title("خبر جديد") == "خبر جدید")
check("norm_title empty stays empty", bot.norm_title("") == "")

# ---- 3. resolve_title_dupes: the real incident pair ----
seen = {}
short = mk("rss:1", TITLE, SHORT_SUM, NOW - 60)
long = mk("tg:2", TITLE, LONG_SUM, NOW - 30)
res = bot.resolve_title_dupes([short, long], seen)
check("incident pair: only the fuller item survives",
      len(res) == 1 and res[0] is long, [i["id"] for i in res])
check("incident pair: shorter item marked seen", seen.get("rss:1") is None and "rss:1" in seen, seen)
seen = {}
res = bot.resolve_title_dupes([long, short], seen)
check("incident pair reversed: fuller still wins",
      len(res) == 1 and res[0] is long, [i["id"] for i in res])

# ---- 4. resolve_title_dupes: exemptions and edges ----
seen = {}
a = mk("x:1", "قیمت لحظه‌ای طلا و ارز", "طلا ۱۰۰", NOW - 60, kind="gold")
b = mk("x:2", "قیمت لحظه‌ای طلا و ارز", "طلا ۲۰۰", NOW - 30, kind="gold")
check("pricelists with same title are NOT deduped",
      len(bot.resolve_title_dupes([a, b], seen)) == 2)
seen = {}
c = mk("x:3", "خبر اول", "متن اول", NOW - 60)
d = mk("x:4", "خبر دوم", "متن دوم", NOW - 30)
check("different titles both kept", len(bot.resolve_title_dupes([c, d], seen)) == 2)
seen = {}
e = mk("x:5", TITLE, "متن یکسان", NOW - 60)
f = mk("x:6", TITLE, "متن یکسان", NOW - 30)
res = bot.resolve_title_dupes([e, f], seen)
check("equal summaries: first item kept", len(res) == 1 and res[0] is e, [i["id"] for i in res])
seen = {}
g = mk("x:7", "", "بدون تیتر", NOW - 60)
h = mk("x:8", "", "بدون تیتر هم", NOW - 30)
check("empty titles are NOT deduped", len(bot.resolve_title_dupes([g, h], seen)) == 2)
seen = {}
res = bot.resolve_title_dupes([], seen)
check("empty list in, empty out", res == [])

# ---- 5. choose(): cross-run title check ----
seen = {}
item = mk("rss:9", TITLE, LONG_SUM, NOW - 60)
chosen = bot.choose([item], 5, seen, [], [], {"مدارس تهران فردا دایر هست"})
check("choose skips item whose title was posted this run window",
      chosen == [] and "rss:9" in seen, chosen)
seen = {}
chosen = bot.choose([item], 5, seen, [], [])
check("choose keeps item when no recent title", len(chosen) == 1, chosen)
seen = {}
chosen = bot.choose([item], 5, seen, [], [], set())
check("choose with empty recent_titles keeps item", len(chosen) == 1, chosen)
# old titles entries without "ti" must not break the recent_titles build
old_entries = [{"t": NOW, "k": ["الف", "ب"]}, {"t": NOW, "k": ["ج"]}]
check("old titles entries without ti build an empty set",
      {t.get("ti") for t in old_entries if t.get("ti")} == set())

# ---- 6. choose(): Jaccard dedup still works (regression) ----
seen = {}
i1 = mk("a:1", "زلزله شدید در تهران رخ داد", "زلزله شدید در تهران رخ داد و مردم وحشت کردند", NOW - 60)
i2 = mk("a:2", "زلزله شدید در تهران رخ داد", "زلزله شدید در تهران رخ داد و مردم وحشت کردند", NOW - 30)
chosen = bot.choose([i1, i2], 5, seen, [], [])
check("identical content, different ids: one skipped by Jaccard, newer kept",
      len(chosen) == 1 and chosen[0]["id"] == "a:2" and "a:1" in seen, [i["id"] for i in chosen])

# ---- 7. run_once wiring (source checks) ----
check("to_post passes through resolve_title_dupes",
      "to_post = resolve_title_dupes(to_post, seen)" in src)
check("titles entries record the normalized title",
      '"ti": norm_title(item["title"])' in src)
check("choose calls pass recent_titles",
      "choose(cands, n, seen, recent_sets, kept_sets, recent_titles)" in src and
      "choose(pool, OTHER_MAX_POSTS, seen, recent_sets, kept_sets, recent_titles)" in src)
check("no '📊 تفکیک دسته‌ها:' block title left in code", "📊 تفکیک دسته‌ها:" not in src)

# ---- 8. /add works for all 21 emojis ----
bot.DYNAMIC_RULES = {"blocked": [], "red": [], "yellow": [], "blue": [], "football": [],
                     "tech": [], "plane": [], "car": [], "meat": [], "chicken": [],
                     "alert": [], "hot": [], "basketball": [], "volleyball": [],
                     "game": [], "jet": [], "fuel": [], "housing": [], "sheep": [],
                     "motorcycle": [], "newspaper": [], "drug": [], "strip_end": []}
ALL_WORDS = {"red": "سرخط", "yellow": "بورسی", "blue": "مدرسه‌ای", "football": "فوتبالی",
             "tech": "رباتی", "plane": "پروازی", "car": "ماشینی", "meat": "گوشتی",
             "chicken": "مرغی", "alert": "هشدار", "hot": "داغ", "basketball": "بسکتبال",
             "volleyball": "والیبال", "game": "بازی", "jet": "جت‌خصوصی",
             "fuel": "سوخت", "housing": "ویلایی", "sheep": "گوسفند",
             "motorcycle": "موتورسواری", "newspaper": "روزنامه‌ای", "drug": "آسپرین",
             "mobile": "موبایلی", "bank": "بانکی", "chart": "نموداری",
             "chart_up": "صعودی", "chart_down": "نزولی"}
ok_add = True
for emoji, key in bot.EMOJI_CATEGORY_KEYS.items():
    sent.clear()
    bot.handle_command({"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0},
                       "/add", f"/add {emoji} {ALL_WORDS[key]}")
    if ALL_WORDS[key] not in bot.DYNAMIC_RULES[key]:
        ok_add = False
        print("   add failed for", emoji, key)
check("/add works for all 26 emojis", ok_add)
check("VS16 motorcycle add (🏍️) registers under motorcycle",
      "موتورسواری" in bot.DYNAMIC_RULES["motorcycle"])

# ---- 9. /remove works for a new emoji ----
sent.clear()
bot.handle_command({"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0},
                   "/remove", "/remove 🏍️ موتورسواری")
check("/remove 🏍️ works", "موتورسواری" not in bot.DYNAMIC_RULES["motorcycle"], sent)
bot.DYNAMIC_RULES["motorcycle"] = ["موتورسواری"]

# ---- 10. parse + format of the new sections ----
parsed = bot.parse_rules_text("[🏍️]\nموتورسواری\n[📰]\nروزنامه‌ای\n[💊]\nآسپرین\n[motorcycle]\nموتور\n")
check("parse: VS16 [🏍️] header read as motorcycle", parsed["motorcycle"] == ["موتورسواری", "موتور"], parsed["motorcycle"])
check("parse: [📰] header read as newspaper", parsed["newspaper"] == ["روزنامه‌ای"], parsed["newspaper"])
check("parse: [💊] header read as drug", parsed["drug"] == ["آسپرین"], parsed["drug"])
fmt = bot.format_rules_text(bot.DYNAMIC_RULES)
check("format: all 3 new sections written",
      all(h in fmt for h in ("[🏍️]", "[📰]", "[💊]")), fmt[:600])

# ---- 11. /rules shows all 21 emojis ----
sent.clear()
bot.handle_command({"tg_offset": 0, "last_post_ids": [], "menu_pending": None, "menu_pending_ts": 0},
                   "/rules", "/rules")
rules_text = sent[-1] if sent else ""
check("/rules lists all 21 emojis",
      all(e in rules_text for e in ("🔴", "🟡", "🔵", "⚽", "🤖", "✈️", "🚙", "🥩", "🍗",
                                    "🚨", "🔥", "🏀", "🏐", "🎮", "🛩", "⛽️", "🏘️", "🐑",
                                    "🏍️", "📰", "💊")), rules_text[:400])

# ---- 12. decide() lead emoji for the new lists ----
def decide_title(title):
    return bot.decide({"title": title, "paras": [], "summary": "", "category": "general"})

check("decide motorcycle word → 🏍️", decide_title("موتورسواری خبر جدید") == ("🏍️", "🔹"), decide_title("موتورسواری خبر جدید"))
check("decide newspaper word → 📰", decide_title("روزنامه‌ای خبر جدید") == ("📰", "🔹"), decide_title("روزنامه‌ای خبر جدید"))
check("decide dynamic drug word (آسپرین) → 💊", decide_title("آسپرین خبر جدید")[0] == "💊", decide_title("آسپرین خبر جدید"))
check("decide hardcoded drug word (داروخانه) still → 💊", decide_title("داروخانه خبر جدید")[0] == "💊")
check("topic beats red: motorcycle word + red word → 🏍️",
      decide_title("موتورسواری سپاه خبر جدید")[0] == "🏍️")
check("topic beats red: newspaper word + red word → 📰",
      decide_title("روزنامه‌ای سپاه خبر جدید")[0] == "📰")
check("HELP_TEXT /add line lists all 21",
      "🏍️|📰|💊" in bot.HELP_TEXT)
check("menu prompts list the new emojis",
      "🏍️📰💊" in bot.MENU_PROMPTS["/add"] and "🏍️📰💊" in bot.MENU_PROMPTS["/remove"])

# ---- 13. 0.04 regressions: merged breakdown block ----
SRC = {"AloNews": 66, "parsi.euronews.com": 35, "arz_talaaa": 24, "kiosk": 4, "digest": 1}
SRC_CAT = {"AloNews": {"political": 26, "economic": 4, "sport": 1, "general": 26},
           "parsi.euronews.com": {"political": 8, "economic": 3, "general": 18},
           "arz_talaaa": {"economic": 18}}
check("0.04: helper total + categories for one source",
      bot.category_breakdown_lines({"AloNews": SRC_CAT["AloNews"]}, {"AloNews": 66}) ==
      ["AloNews: ۶۶ پست", "🔴 سیاسی ۲۶", "🟡 اقتصادی ۴", "⚽ ورزشی ۱", "🔵 عمومی ۲۶"])
br = bot.category_breakdown_lines(SRC_CAT, SRC)
check("0.04: kiosk/digest show total only, no category lines",
      "kiosk: ۴ پست" in br and "digest: ۱ پست" in br and
      br.index("kiosk: ۴ پست") + 1 == br.index("digest: ۱ پست"), br)
check("0.04: sources sorted by total desc",
      [br.index("AloNews: ۶۶ پست"), br.index("parsi.euronews.com: ۳۵ پست"),
       br.index("arz_talaaa: ۲۴ پست")] == sorted([br.index("AloNews: ۶۶ پست"),
       br.index("parsi.euronews.com: ۳۵ پست"), br.index("arz_talaaa: ۲۴ پست")]), br)
check("0.04: empty in, empty out", bot.category_breakdown_lines({}, {}) == [])

# ---- 13b. kiosk right before digest at the end (0.05, user's screenshot) ----
def _order(src, src_cat=None):
    lines = bot.category_breakdown_lines(src_cat or {}, src)
    return [ln.split(":")[0] for ln in lines if ln.endswith("پست")]
check("kiosk before digest even when digest has more posts",
      _order({"AloNews": 10, "kiosk": 1, "digest": 2}) == ["AloNews", "kiosk", "digest"],
      _order({"AloNews": 10, "kiosk": 1, "digest": 2}))
o = _order({"AloNews": 74, "parsi.euronews.com": 39, "arz_talaaa": 27,
            "www.independentpersian.com": 5, "rss.dw.com": 5, "kiosk": 4,
            "www.isna.ir": 3, "digest": 1})
check("screenshot order: kiosk+digest last, kiosk adjacent before digest, isna above kiosk",
      o[-2:] == ["kiosk", "digest"] and o.index("www.isna.ir") < o.index("kiosk") and
      o.index("AloNews") < o.index("parsi.euronews.com") < o.index("arz_talaaa"), o)
check("only kiosk present: kiosk last",
      _order({"AloNews": 10, "kiosk": 2}) == ["AloNews", "kiosk"])
check("only digest present: digest last",
      _order({"AloNews": 10, "digest": 2}) == ["AloNews", "digest"])
check("no kiosk/digest: order unchanged",
      _order({"AloNews": 10, "arz_talaaa": 5}) == ["AloNews", "arz_talaaa"])
check("kiosk/digest category lines (none) still follow their headers",
      bot.category_breakdown_lines({}, {"kiosk": 4, "digest": 1}) == ["kiosk: ۴ پست", "digest: ۱ پست"])

# ---- 14. 0.03 regressions ----
bot.DYNAMIC_RULES["alert"] = ["هشدار"]
check("0.03: decide alert word → 🚨",
      bot.decide({"title": "هشدار خبر جدید", "paras": [], "summary": "", "category": "general"})[0] == "🚨")
check("0.01: proxy cap still 300",
      __import__("inspect").signature(bot.prepare_proxies).parameters["max_checks"].default == 300)

print()
print(f"PASS {len(PASS)} FAIL {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
