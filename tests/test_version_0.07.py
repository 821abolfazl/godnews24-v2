# Tests for bot version 2026-11-13-0.07:
# (1) reply threading — a news item that replies to a source post we already
# posted in @GodNews24 goes out as a reply to OUR copy of that post
# (state["post_map"]: source item id -> our channel message id). If the parent
# was never posted by us, the news goes out without a reply, as before.
# (2) the dinner digest «برای دیدن خبر کامل کلیک کنید» link is now inside
# parentheses and bold.
import os
import sys
import time
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot007", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

# ---- fakes ----
TG_CALLS = []
NEXT_IDS = [1000]
FAIL_METHODS = set()

def fake_tg(method, files=None, **data):
    if method in FAIL_METHODS:
        return False
    TG_CALLS.append((method, dict(data)))
    NEXT_IDS[0] += 1
    bot.LAST_TG_IDS.append(NEXT_IDS[0])
    return True

bot.tg = fake_tg
bot.proxy_parts = lambda: ('<a href="https://t.me/proxy?server=1.1.1.1&port=443&secret=x">پروکسی</a>😉',
                           'پروکسی😉 https://t.me/proxy?server=1.1.1.1&port=443&secret=x')
bot.save_state = lambda state: None
bot.download = lambda url, limit=30 * 1024 * 1024, max_seconds=60: b"fake-bytes"

def fresh_state(**kw):
    st = {"tg_offset": 0, "last_post_ids": []}
    st.update(kw)
    bot.STATE_REF[0] = st
    return st

def reset():
    TG_CALLS.clear()
    FAIL_METHODS.clear()
    NEXT_IDS[0] = 1000
    bot.LAST_TG_IDS.clear()

def mk(id_, title, summary, ts=None, reply_to=None, media=None):
    d = {"id": id_, "title": title, "summary": summary,
         "paras": [summary] if summary else [], "ts": ts or time.time(),
         "category": "general", "src": "AloNews", "media": media or [],
         "image": None, "video": None}
    if reply_to:
        d["reply_to"] = reply_to
    return d

PHRASE = "برای دیدن خبر کامل کلیک کنید"

# ---- 1. parse_tg_page extracts the reply target ----
PAGE = """
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="AloNews/12340">
    <div class="tgme_widget_message_bubble">
      <div class="tgme_widget_message_text js-message_text" dir="auto">مقایسه وضعیت حضور و آرایش نظامی آمریکا در منطقه در جریان جنگ ۴۰روزه با وضعیت کنونی<br>🆔 @AloNews</div>
      <div class="tgme_widget_message_footer"><div class="tgme_widget_message_meta"><a class="tgme_widget_message_date" href="https://t.me/AloNews/12340"><time datetime="2026-11-16T18:30:00+00:00">22:00</time></a></div></div>
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="AloNews/12341">
    <div class="tgme_widget_message_bubble">
      <a class="tgme_widget_message_reply" href="https://t.me/AloNews/12340"><span class="tgme_widget_message_author">AloNews</span><div class="tgme_widget_message_metatext">مقایسه وضعیت حضور...</div></a>
      <div class="tgme_widget_message_text js-message_text" dir="auto">ونس: اجازه نمی‌دهیم جنگ حتی به تعهدی دوساله تبدیل شود<br>🆔 @AloNews</div>
      <div class="tgme_widget_message_footer"><div class="tgme_widget_message_meta"><a class="tgme_widget_message_date" href="https://t.me/AloNews/12341"><time datetime="2026-11-16T18:35:00+00:00">22:05</time></a></div></div>
    </div>
  </div>
</div>
<div class="tgme_widget_message_wrap js-widget_message_wrap">
  <div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="AloNews/12342">
    <div class="tgme_widget_message_bubble">
      <a class="tgme_widget_message_reply" href="https://t.me/OtherChan/9"><span class="tgme_widget_message_author">OtherChan</span><div class="tgme_widget_message_metatext">چیزی از کانال دیگر</div></a>
      <div class="tgme_widget_message_text js-message_text" dir="auto">خبر سوم که به کانال دیگری ریپلای زده<br>🆔 @AloNews</div>
      <div class="tgme_widget_message_footer"><div class="tgme_widget_message_meta"><a class="tgme_widget_message_date" href="https://t.me/AloNews/12342"><time datetime="2026-11-16T18:40:00+00:00">22:10</time></a></div></div>
    </div>
  </div>
</div>
"""

posts = bot.parse_tg_page(PAGE)
check("parse: three posts read", len(posts) == 3, len(posts))
check("parse: plain post has no reply_to", posts[0].get("reply_to") is None, posts[0])
check("parse: reply post extracts parent", posts[1].get("reply_to") == "AloNews/12340", posts[1])
check("parse: cross-channel reply still extracted raw", posts[2].get("reply_to") == "OtherChan/9", posts[2])
check("parse: post ids still read", [p["post_id"] for p in posts] == ["AloNews/12340", "AloNews/12341", "AloNews/12342"],
      [p["post_id"] for p in posts])

# regex fallback path (no bs4)
saved_bs4 = sys.modules.get("bs4")
sys.modules["bs4"] = None
try:
    posts_re = bot.parse_tg_page(PAGE)
finally:
    if saved_bs4 is None:
        sys.modules.pop("bs4", None)
    else:
        sys.modules["bs4"] = saved_bs4
check("parse regex: three posts read", len(posts_re) == 3, len(posts_re))
check("parse regex: reply post extracts parent", posts_re[1].get("reply_to") == "AloNews/12340", posts_re[1])
check("parse regex: plain post has no reply_to", posts_re[0].get("reply_to") is None, posts_re[0])
check("parse regex: cross-channel reply still extracted raw", posts_re[2].get("reply_to") == "OtherChan/9", posts_re[2])

# ---- 2. fetch_tg attaches reply_to only for the same channel ----
class FakeResp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

orig_get = bot.requests.get
bot.requests.get = lambda url, headers=None, timeout=None: FakeResp(PAGE)
try:
    items = bot.fetch_tg("general", "AloNews", False)
finally:
    bot.requests.get = orig_get
by_id = {i["id"]: i for i in items}
check("fetch_tg: three items", len(items) == 3, len(items))
check("fetch_tg: plain item has reply_to None", by_id["tg:AloNews/12340"].get("reply_to") is None, by_id.get("tg:AloNews/12340"))
check("fetch_tg: same-channel reply kept", by_id["tg:AloNews/12341"].get("reply_to") == "tg:AloNews/12340",
      by_id.get("tg:AloNews/12341"))
check("fetch_tg: cross-channel reply dropped", by_id["tg:AloNews/12342"].get("reply_to") is None,
      by_id.get("tg:AloNews/12342"))

# ---- 3. send() threads the reply onto the first message of the post ----
reset()
st = fresh_state(post_map={"tg:AloNews/12340": 777})
ok = bot.send(mk("tg:AloNews/12341", "ونس: اجازه نمی‌دهیم جنگ حتی به تعهدی دوساله تبدیل شود",
                 "متن خبر.", reply_to="tg:AloNews/12340"))
check("send text: sent", ok is True and len(TG_CALLS) == 1, TG_CALLS)
check("send text: replies to our copy of the parent",
      TG_CALLS[0][0] == "sendMessage" and TG_CALLS[0][1].get("reply_to_message_id") == 777, TG_CALLS)
check("send text: post_map records the new post",
      st.get("post_map", {}).get("tg:AloNews/12341") == 1001, st.get("post_map"))

reset()
st = fresh_state(post_map={"tg:AloNews/12340": 777})
ok = bot.send(mk("tg:AloNews/12341", "ونس: اجازه نمی‌دهیم جنگ حتی به تعهدی دوساله تبدیل شود",
                 "متن خبر.", reply_to="tg:AloNews/99999"))
check("send text: unknown parent goes out without reply",
      ok is True and "reply_to_message_id" not in TG_CALLS[0][1], TG_CALLS)

reset()
st = fresh_state(post_map={})
ok = bot.send(mk("tg:AloNews/12341", "خبر بدون ریپلای", "متن خبر."))
check("send text: no reply_to means no reply",
      ok is True and "reply_to_message_id" not in TG_CALLS[0][1], TG_CALLS)

# media group with caption: the group itself carries the reply
reset()
st = fresh_state(post_map={"tg:AloNews/12340": 777})
media = [("photo", "https://x/1.jpg"), ("photo", "https://x/2.jpg")]
ok = bot.send(mk("tg:AloNews/12341", "خبر عکس‌دار", "متن کوتاه خبر.",
                 reply_to="tg:AloNews/12340", media=media))
check("send group: sent as one media group", ok is True and len(TG_CALLS) == 1 and TG_CALLS[0][0] == "sendMediaGroup", TG_CALLS)
check("send group: group replies to our copy of the parent",
      TG_CALLS[0][1].get("reply_to_message_id") == 777, TG_CALLS)
check("send group: post_map records the group",
      st.get("post_map", {}).get("tg:AloNews/12341") == 1001, st.get("post_map"))

# long text + media: media first (with reply), text after (without reply)
reset()
st = fresh_state(post_map={"tg:AloNews/12340": 777})
long_sum = "متن طولانی خبر. " * 100
ok = bot.send(mk("tg:AloNews/12341", "خبر طولانی عکس‌دار", long_sum,
                 reply_to="tg:AloNews/12340", media=media))
check("send long+media: media then text", ok is True and len(TG_CALLS) == 2
      and TG_CALLS[0][0] == "sendMediaGroup" and TG_CALLS[1][0] == "sendMessage", TG_CALLS)
check("send long+media: only the media carries the reply",
      TG_CALLS[0][1].get("reply_to_message_id") == 777 and "reply_to_message_id" not in TG_CALLS[1][1], TG_CALLS)
check("send long+media: post_map records the first message",
      st.get("post_map", {}).get("tg:AloNews/12341") == 1001, st.get("post_map"))

# media fails: text-only fallback carries the reply
reset()
st = fresh_state(post_map={"tg:AloNews/12340": 777})
FAIL_METHODS.add("sendMediaGroup")
ok = bot.send(mk("tg:AloNews/12341", "خبر عکس‌دار", "متن کوتاه خبر.",
                 reply_to="tg:AloNews/12340", media=media))
check("send fallback: text only when media fails",
      ok is True and len(TG_CALLS) == 1 and TG_CALLS[0][0] == "sendMessage", TG_CALLS)
check("send fallback: the text carries the reply",
      TG_CALLS[0][1].get("reply_to_message_id") == 777, TG_CALLS)

# post_map cap: oldest entries evicted
reset()
big_map = {f"tg:AloNews/{i}": i for i in range(2000)}
st = fresh_state(post_map=big_map)
ok = bot.send(mk("tg:AloNews/99999", "خبر تازه", "متن خبر."))
check("post_map: capped at 2000", len(st.get("post_map", {})) == 2000, len(st.get("post_map", {})))
check("post_map: new post kept", st.get("post_map", {}).get("tg:AloNews/99999") == 1001, st.get("post_map"))
check("post_map: oldest evicted", "tg:AloNews/0" not in st.get("post_map", {}), list(st.get("post_map", {}))[:3])

# ---- 4. dinner digest link: parentheses + bold ----
entries = [
    {"t": "خبر عکس‌دار مهم", "e": "🔴", "red": True, "ts": time.time(), "src": "test",
     "link": "https://t.me/GodNews24/111"},
    {"t": "خبر کوتاه معمولی", "e": "🔵", "red": False, "ts": time.time() - 60, "src": "test"},
]
txt = bot.build_digest_text("🍽️ شام خبری گادنیوز ۲۴", entries)
check("digest: link is in parentheses and bold",
      ' — (<b><a href="https://t.me/GodNews24/111">' + PHRASE + "</a></b>)" in txt, txt)
check("digest: old link substring still there (y regression)",
      '<a href="https://t.me/GodNews24/111">' + PHRASE + "</a>" in txt, txt)
check("digest: phrase appears exactly once", txt.count(PHRASE) == 1, txt)
check("digest: plain line still has no phrase", "🔵 خبر کوتاه معمولی" in txt and "خبر کوتاه معمولی —" not in txt, txt)

print()
print(f"Passed: {len(PASS)}, Failed: {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
