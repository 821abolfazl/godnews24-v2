# Tests for bot version 2026-11-13-0.12 (the next-round recheck design was
# abandoned before ever going live; this same-round design IS 0.12):
# News go out on time, as before; ~1 minute later AND again ~5 minutes later,
# in the SAME round, the bot re-reads the just-posted Telegram items and, if
# the source text grew (stale/partial preview page at the first fetch),
# completes our own channel post in place (editMessageText for a text post,
# editMessageCaption for a captioned photo) — no delay, no repost, no dup.
# While waiting for each recheck, the bot keeps answering admin commands
# (_sleep_polling polls every 10s with the round's live state).
# 1. _item_text_hash is stable for the same text, changes when paras change.
# 2. send() records watch_next for TG items only, with the right editable
#    message id: text post -> the text message; caption post -> the photo
#    message; long text + media -> the separate text message.
# 3. recheck_watch(watch): no change -> no edit; changed text -> editMessageText;
#    changed caption -> editMessageCaption; missing fresh item -> no edit;
#    caption grown past 1000 chars -> skipped; muted category -> no edit;
#    second recheck with unchanged text -> no re-edit (hash updated after
#    the first edit); text grown further -> edited again with the newest text.
# 4. _sleep_polling polls admin commands while waiting.
# 5. The old next-round machinery is gone: no recheck_watch_prev,
#    no watch_prev anywhere in the code.
# 6. Version pin 0.12; menu unchanged (20 buttons, same tail).
import os
import sys
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot012", "/home/hatch/workspace/godnews24/bot.py")
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

calls = []
next_mid = [100]

def fake_tg(method, files=None, **data):
    next_mid[0] += 1
    bot.LAST_TG_IDS.append(next_mid[0])
    calls.append((method, dict(data)))
    return True

bot.tg = fake_tg

def fresh_state():
    st = {"rejected": [], "stats": {}}
    bot.STATE_REF[0] = st
    return st

def tg_item(pid="alonews/158629", title="تیتر خبر", paras=("پاراگراف اول.", "پاراگراف دوم."),
            media=None, short=False, category=None):
    it = {"id": "tg:" + pid, "title": title, "summary": " ".join(paras), "paras": list(paras),
          "ts": 1700000000, "src": "AloNews", "kind": None, "category": category or "political"}
    if media:
        it["media"] = media
    if short:
        it["short"] = True
    return it

def reset_calls():
    calls.clear()
    next_mid[0] = 100

# ---- 1. hash: stable, changes with the text ----
a = tg_item()
b = tg_item()
c = tg_item(paras=("پاراگراف اول.", "پاراگراف عوض شده."))
check("hash stable for same text", bot._item_text_hash(a) == bot._item_text_hash(b))
check("hash changes when paras change", bot._item_text_hash(a) != bot._item_text_hash(c))
check("hash changes when title changes",
      bot._item_text_hash(a) != bot._item_text_hash(tg_item(title="تیتر دیگر")))

# ---- 2. send() records watch_next (TG only, right editable message) ----
st = fresh_state()
reset_calls()
check("send text post ok", bot.send(tg_item()))
w = st.get("watch_next", {}).get("tg:alonews/158629")
check("text post watched", w is not None)
check("text post: mid is the text message, cap False",
      w and w["mid"] == 101 and w["cap"] is False, w)
check("text post: hash matches item", w and w["h"] == bot._item_text_hash(tg_item()))

st = fresh_state()
reset_calls()
check("send caption post ok", bot.send(tg_item(media=[("photo", "https://example.com/x.jpg")])))
w = st.get("watch_next", {}).get("tg:alonews/158629")
check("caption post watched", w is not None)
check("caption post: mid is the photo message, cap True",
      w and w["mid"] == 101 and w["cap"] is True, w)

st = fresh_state()
reset_calls()
long_paras = ("پاراگراف بسیار طولانی. " * 60, "پاراگراف دوم.")
check("send long-text media post ok", bot.send(tg_item(media=[("photo", "https://example.com/x.jpg")],
                                                      paras=long_paras)))
w = st.get("watch_next", {}).get("tg:alonews/158629")
check("long media post watched", w is not None)
check("long media post: mid is the separate text message (102), cap False",
      w and w["mid"] == 102 and w["cap"] is False, w)

st = fresh_state()
reset_calls()
rss = tg_item()
rss["id"] = "rss:example/1"
check("send RSS post ok", bot.send(rss))
check("RSS item is NOT watched", not st.get("watch_next"))

# ---- 3. recheck_watch (same-round, takes the watch dict) ----
FEEDS = [("political", "tg:AloNews", True)]
real_fetch_tg = bot.fetch_tg

def with_fresh(fresh_items):
    bot.fetch_tg = lambda category, name, domestic: list(fresh_items)

def watch_for(entry, **extra):
    st = fresh_state()
    st.update(extra)
    return st, {"tg:alonews/158629": entry}

base = tg_item()
base_h = bot._item_text_hash(base)

# 3a. unchanged -> no edit
st, watch = watch_for({"h": base_h, "mid": 101, "cap": False})
with_fresh([base])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("unchanged: no edit call", not calls)

# 3b. changed text -> editMessageText with the new full text
changed = tg_item(paras=("پاراگراف اول.", "پاراگراف دوم.", "پاراگراف سومِ تازه."))
st, watch = watch_for({"h": base_h, "mid": 101, "cap": False})
with_fresh([changed])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("changed text: one edit call", len(calls) == 1, calls)
check("changed text: editMessageText to the right message",
      calls and calls[0][0] == "editMessageText" and calls[0][1].get("message_id") == 101, calls)
check("changed text: new text contains the added paragraph",
      calls and "پاراگراف سومِ تازه" in (calls[0][1].get("text") or ""), calls)

# 3c. changed caption -> editMessageCaption
st, watch = watch_for({"h": base_h, "mid": 101, "cap": True})
with_fresh([changed])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("changed caption: editMessageCaption to the photo message",
      len(calls) == 1 and calls[0][0] == "editMessageCaption"
      and calls[0][1].get("message_id") == 101, calls)
check("changed caption: new caption contains the added paragraph",
      calls and "پاراگراف سومِ تازه" in (calls[0][1].get("caption") or ""), calls)

# 3d. fresh item missing (source deleted / now filtered) -> no edit
st, watch = watch_for({"h": base_h, "mid": 101, "cap": False})
with_fresh([])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("missing fresh item: no edit", not calls)

# 3e. caption grown past 1000 chars -> skipped (can't fit a caption)
grown = tg_item(paras=("پاراگراف بسیار طولانی. " * 60, "پاراگراف دوم."))
st, watch = watch_for({"h": base_h, "mid": 101, "cap": True})
with_fresh([grown])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("caption over 1000 chars: no edit", not calls)

# 3f. muted category -> no edit
muted = tg_item(paras=("پاراگراف اول.", "پاراگراف دوم.", "پاراگراف سومِ تازه."), category="politics")
st, watch = watch_for({"h": base_h, "mid": 101, "cap": False},
                      muted_categories={"alonews": ["political"]})
with_fresh([muted])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("muted category: no edit", not calls)

bot.fetch_tg = real_fetch_tg

# 3g. second recheck, text unchanged since the first edit -> no re-edit
st, watch = watch_for({"h": base_h, "mid": 101, "cap": False})
with_fresh([changed])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("first recheck edits once", len(calls) == 1, calls)
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("second recheck with same text: no re-edit", not calls, calls)

# 3h. text grows further between the two rechecks -> edited again, newest text
v3 = tg_item(paras=("پاراگراف اول.", "پاراگراف دوم.", "پاراگراف سومِ تازه.", "پاراگراف چهارمِ تازه‌تر."))
st, watch = watch_for({"h": base_h, "mid": 101, "cap": False})
with_fresh([changed])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("grows further: first edit", len(calls) == 1, calls)
with_fresh([v3])
reset_calls()
bot.recheck_watch(st, FEEDS, watch)
check("grows further: second edit with newest text",
      len(calls) == 1 and "پاراگراف چهارمِ تازه‌تر" in (calls[0][1].get("text") or ""), calls)

bot.fetch_tg = real_fetch_tg

# ---- 4. _sleep_polling polls admin commands while waiting ----
polled = []
saved = []
real_process = bot.process_commands
real_save = bot.save_state
bot.process_commands = lambda st_: polled.append(True) or True
bot.save_state = lambda st_: saved.append(True)
try:
    st = fresh_state()
    bot._sleep_polling(st, 0.05)
    check("sleep_polling polls commands", len(polled) >= 1, polled)
    check("sleep_polling saves state when commands changed it", len(saved) >= 1, saved)
finally:
    bot.process_commands = real_process
    bot.save_state = real_save

# ---- 5. old next-round machinery is gone ----
check("no recheck_watch_prev (next-round design gone)", not hasattr(bot, "recheck_watch_prev"))
src = open("/home/hatch/workspace/godnews24/bot.py", encoding="utf-8").read()
check("no watch_prev in bot.py", "watch_prev" not in src)
check("first wait is 60s", bot.RECHECK_WAIT_SEC == 60, bot.RECHECK_WAIT_SEC)
check("second wait is 240s (5 min total)", bot.RECHECK_WAIT2_SEC == 240, bot.RECHECK_WAIT2_SEC)
check("run() polls while waiting, then rechecks twice",
      "_sleep_polling(state, RECHECK_WAIT_SEC)" in src
      and "_sleep_polling(state, RECHECK_WAIT2_SEC)" in src
      and sum(1 for line in src.splitlines()
              if line.strip().startswith("recheck_watch(state, tg_feeds, watch)")) == 2)

# ---- 6. version pin + menu unchanged ----
check("version is 0.12", bot.BOT_VERSION == "2026-11-13-0.12", bot.BOT_VERSION)
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu still 20 buttons", len(labels) == 20, len(labels))
check("menu tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
