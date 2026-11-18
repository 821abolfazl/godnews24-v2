# Tests for bot version 2026-11-18-0.13 (mute-by-URL fix).
# Reported 2026-11-18: /mute http://www.isna.ir did NOT stop ISNA posts.
# Root cause: source_muted_key did a raw substring match of the muted entry
# against the feed URL, and "http://www.isna.ir" is not a substring of
# "https://www.isna.ir/rss" (http vs https). The fix normalizes both sides
# (strip scheme, www, trailing slash) before matching, in source_muted_key
# and in muted_category_of (RSS items carry src = netloc, e.g. www.isna.ir).
# 1. _mute_key normalization.
# 2. The reported case: http-muted ISNA matches the https feed.
# 3. https-muted, alias-muted and domain-muted still match; no false positives.
# 4. TG-channel matching unchanged.
# 5. muted_category_of with a URL key matches RSS items.
# 6. The real ISNA feed entry in FEEDS is filtered out when muted.
# 7. Version pin 0.13; menu unchanged (20 buttons, same tail).
import os
import sys
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot013", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

def fresh_state(**kw):
    st = {"tg_offset": 0, "last_post_ids": []}
    st.update(kw)
    return st

ISNA_FEED = "https://www.isna.ir/rss"
EURONEWS_FEED = "https://parsi.euronews.com/rss?format=mrss"

# ---- 1. _mute_key normalization ----
check("mute_key: strips http + www", bot._mute_key("http://www.isna.ir") == "isna.ir", bot._mute_key("http://www.isna.ir"))
check("mute_key: strips https + www + path", bot._mute_key("https://www.isna.ir/rss") == "isna.ir/rss", bot._mute_key("https://www.isna.ir/rss"))
check("mute_key: plain alias untouched", bot._mute_key("isna") == "isna")
check("mute_key: lowercases", bot._mute_key("AloNews") == "alonews")
check("mute_key: trailing slash stripped", bot._mute_key("https://www.isna.ir/") == "isna.ir", bot._mute_key("https://www.isna.ir/"))
check("mute_key: empty stays empty", bot._mute_key("") == "")

# ---- 2. the reported case ----
st_http = fresh_state(muted_sources=["http://www.isna.ir"])
check("reported: http-muted isna matches https feed", bot.source_muted_key(st_http, ISNA_FEED) is True)

# ---- 3. other spellings match; no false positives ----
check("https-muted isna matches", bot.source_muted_key(fresh_state(muted_sources=["https://www.isna.ir"]), ISNA_FEED) is True)
check("alias-muted isna matches", bot.source_muted_key(fresh_state(muted_sources=["isna"]), ISNA_FEED) is True)
check("domain-muted isna matches", bot.source_muted_key(fresh_state(muted_sources=["isna.ir"]), ISNA_FEED) is True)
check("isna mute does not match euronews", bot.source_muted_key(st_http, EURONEWS_FEED) is False)
check("dw mute does not match isna", bot.source_muted_key(fresh_state(muted_sources=["dw"]), ISNA_FEED) is False)
check("empty muted list passes", bot.source_muted_key(fresh_state(), ISNA_FEED) is False)

# ---- 4. TG-channel matching unchanged ----
st_tg = fresh_state(muted_sources=["AloNews"])
check("tg: muted channel matches", bot.source_muted_key(st_tg, "tg:AloNews") is True)
check("tg: other channel passes", bot.source_muted_key(st_tg, "tg:arz_talaaa") is False)
check("rss: alias still matches", bot.source_muted_key(fresh_state(muted_sources=["euronews"]), EURONEWS_FEED) is True)

# ---- 5. muted_category_of with a URL key ----
pol_isna = {"title": "خبر سیاسی", "paras": ["متن خبر."], "category": "politics", "kind": None, "src": "www.isna.ir"}
eco_isna = {"title": "قیمت طلا", "paras": ["متن خبر."], "category": "economy", "kind": None, "src": "www.isna.ir"}
st_cat = fresh_state(muted_categories={"http://www.isna.ir": ["political"]})
check("cat-mute: url key matches rss item", bot.muted_category_of(st_cat, pol_isna) == "political")
check("cat-mute: other category passes", bot.muted_category_of(st_cat, eco_isna) is None)
check("cat-mute: alias key still works",
      bot.muted_category_of(fresh_state(muted_categories={"euronews": ["political"]}),
                            {"title": "خبر سیاسی", "paras": ["متن."], "category": "politics", "kind": None, "src": "parsi.euronews.com"}) == "political")

# ---- 6. the real FEEDS entry is filtered when muted ----
other_feeds = [f for f in bot.FEEDS if not f[1].startswith("tg:") and not bot.source_muted_key(st_http, f[1])]
check("feeds: no isna entry left when muted", not any("isna" in f[1] for f in other_feeds), [f[1] for f in other_feeds if "isna" in f[1]])
other_feeds_open = [f for f in bot.FEEDS if not f[1].startswith("tg:") and not bot.source_muted_key(fresh_state(), f[1])]
check("feeds: isna present when not muted", any("isna" in f[1] for f in other_feeds_open))

# ---- 7. version pin + menu unchanged ----
check("version is 0.13", bot.BOT_VERSION == "2026-11-18-0.13", bot.BOT_VERSION)
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu still 20 buttons", len(labels) == 20, len(labels))
check("menu tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
