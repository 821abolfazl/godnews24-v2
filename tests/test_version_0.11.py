# Tests for bot version 2026-11-13-0.11:
# 1. Banned words ([ممنوع] / /block) now apply to RSS/website sources too
#    (fetch_feed), not only to Telegram channels (fetch_tg):
#    - a blocked word in the title skips the item, logged as "کلمه‌ی ممنوع"
#    - a blocked word only in the summary skips the item too
#    - hardcoded BLOCKED_WORDS also apply to feeds
#    - with an empty blocked list the same word passes through
# 2. Version pin 0.11; menu unchanged (20 buttons, same tail).
import os
import sys
import importlib.util
from types import SimpleNamespace

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot011", "/home/hatch/workspace/godnews24/bot.py")
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

FEED_URL = "https://example.com/rss"

class Entry(dict):
    """Like feedparser's FeedParserDict: attribute access maps to keys."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

def fake_entries(entries):
    def fake_parse(url, request_headers=None):
        return SimpleNamespace(entries=[Entry(e) for e in entries])
    return fake_parse

real_parse = bot.feedparser.parse

# ---- 1. blocked word in title / summary / hardcoded list ----
st = fresh_state()
bot.DYNAMIC_RULES["blocked"] = ["کلمه‌ممنوعه"]
bot.feedparser.parse = fake_entries([
    {"id": "1", "link": "https://example.com/1", "title": "خبر معمولی اول", "summary": "متن خبر"},
    {"id": "2", "link": "https://example.com/2", "title": "خبر با کلمه‌ممنوعه در تیتر", "summary": "متن"},
    {"id": "3", "link": "https://example.com/3", "title": "خبر معمولی دوم", "summary": "در متن خلاصه کلمه‌ممنوعه آمده"},
    {"id": "4", "link": "https://example.com/4", "title": "خوشچشم در تیتر", "summary": ""},
])
try:
    items = bot.fetch_feed("sports", FEED_URL, False)
finally:
    bot.feedparser.parse = real_parse

check("feed: only the clean item survives", [i["id"] for i in items] == ["1"], [i["id"] for i in items])
check("feed: three blocked rejections logged",
      len([e for e in st["rejected"] if e.get("why") == "کلمه‌ی ممنوع"]) == 3, st["rejected"])
check("feed: blocked rejection src is the feed domain",
      all(e.get("src") == "example.com" for e in st["rejected"] if e.get("why") == "کلمه‌ی ممنوع"), st["rejected"])
check("feed: RSS_READ counts only kept items", bot.RSS_READ.get(FEED_URL) == 1, bot.RSS_READ.get(FEED_URL))

# ---- 1b. same word passes when the blocked list is empty ----
st = fresh_state()
bot.DYNAMIC_RULES["blocked"] = []
bot.feedparser.parse = fake_entries([
    {"id": "1", "link": "https://example.com/1", "title": "خبر با کلمه‌ممنوعه در تیتر", "summary": "متن"},
])
try:
    items = bot.fetch_feed("sports", FEED_URL, False)
finally:
    bot.feedparser.parse = real_parse
check("feed: word passes with empty blocked list", [i["id"] for i in items] == ["1"], [i["id"] for i in items])
check("feed: no blocked rejection with empty list",
      not [e for e in st["rejected"] if e.get("why") == "کلمه‌ی ممنوع"], st["rejected"])

# ---- 2. version + menu unchanged ----
check("version: is 0.11", bot.BOT_VERSION == "2026-11-13-0.11", bot.BOT_VERSION)
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu: still 20 buttons", len(labels) == 20, len(labels))
check("menu: tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

print()
print(f"Passed: {len(PASS)}, Failed: {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
