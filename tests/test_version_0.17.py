# Tests for bot version 2026-11-19-0.17.
# /send album: an admin media group (several photos/videos with one caption)
# is now sent to the channel as ONE sendMediaGroup post instead of only the
# first photo (reported 17:58 — a 7-photo nebula album, only photo 1 arrived).
# 1. send_album_to_channel: one sendMediaGroup, caption (proxy + @GodNews24)
#    on the first item only, all ids recorded for /delete.
# 2. Long caption: media without caption + full text separately.
# 3. Mixed photo+video album; empty album rejected.
# 4. process_commands collects a media_group_id into one album post;
#    a following message flushes the album first.
# 5. Regressions: single photo still sendPhoto; photo without pending ignored;
#    inline "/send ..." caption on an album strips the command.
# 6. Version pin 0.17; menu unchanged (20 buttons, same tail).
# News media (same version): when a media group fails but exactly one item is
# downloadable, that one is sent alone with the caption instead of the whole
# post going text-only; and a text-only fallback is now recorded as a send
# error ("خطا در ارسال رسانه") so it shows in /errors and in the /status
# error count, instead of only being printed to the run log (last 2 runs had
# zero such failures — the problem is intermittent, so the record is what
# lets us catch the next one).
# 7. send_group salvage: 1 downloadable of 3 -> single photo with caption;
#    0 downloadable -> False.
# 8. send() records a media failure in /errors (source + title, errors
#    counter up); nothing recorded when media succeeds or the item has no media.
# 9. /status error count includes media failures.
import os
import sys
import time
import json
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot017", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

ADMIN_MSGS = []
TG_CALLS = []
PARSE_MODES = []
NEXT_IDS = [1000]

def fake_admin_send(text, reply_markup=None):
    ADMIN_MSGS.append(text)
    return True

def fake_tg(method, files=None, **data):
    TG_CALLS.append((method, dict(data)))
    PARSE_MODES.append(bot.PARSE_MODE[0])
    if method == "sendMediaGroup":
        try:
            items = json.loads(data.get("media", "[]"))
        except Exception:
            items = []
        for _ in items or [None]:
            NEXT_IDS[0] += 1
            bot.LAST_TG_IDS.append(NEXT_IDS[0])
    else:
        NEXT_IDS[0] += 1
        bot.LAST_TG_IDS.append(NEXT_IDS[0])
    return True

bot.tg = fake_tg
bot.admin_send = fake_admin_send
bot.proxy_parts = lambda: ('<a href="https://t.me/proxy?server=1.1.1.1&port=443&secret=eeaa">پروکسی</a>😉',
                           'پروکسی😉 https://t.me/proxy?server=1.1.1.1&port=443&secret=eeaa')
bot.save_state = lambda state: None

def fresh_state(**kw):
    st = {"tg_offset": 0, "last_post_ids": []}
    st.update(kw)
    return st

def reset():
    ADMIN_MSGS.clear()
    TG_CALLS.clear()
    PARSE_MODES.clear()
    bot.LAST_TG_IDS.clear()

class Resp:
    def __init__(self, payload):
        self.payload = payload
    def json(self):
        return self.payload

def run_updates(updates, pending="/send"):
    real_get = bot.requests.get
    bot.requests.get = lambda url, params=None, timeout=None: Resp({"ok": True, "result": updates})
    try:
        kw = {} if pending is None else {"menu_pending": pending, "menu_pending_ts": time.time()}
        st = fresh_state(**kw)
        changed = bot.process_commands(st)
        return st, changed
    finally:
        bot.requests.get = real_get

def upd(uid, msg):
    return {"update_id": uid, "message": msg}

def photo_msg(mid, fid, gid=None, caption=None):
    m = {"message_id": mid, "chat": {"id": 123}, "photo": [{"file_id": fid}]}
    if gid:
        m["media_group_id"] = gid
    if caption is not None:
        m["caption"] = caption
    return m

def album_media(call):
    try:
        return json.loads(call[1].get("media", "[]"))
    except Exception:
        return []

# ---- 1. version ----
check("version is 0.17", bot.BOT_VERSION == "2026-11-19-0.17", bot.BOT_VERSION)

# ---- 2. send_album_to_channel: three photos, one group ----
reset()
st = fresh_state()
bot.send_album_to_channel(st, [("photo", "P1"), ("photo", "P2"), ("photo", "P3")], "سحابی‌ها 🌌")
check("album: one sendMediaGroup", len(TG_CALLS) == 1 and TG_CALLS[0][0] == "sendMediaGroup", TG_CALLS)
media = album_media(TG_CALLS[0]) if TG_CALLS else []
check("album: all three file_ids", [m.get("media") for m in media] == ["P1", "P2", "P3"], media)
check("album: caption only on first item",
      media and "caption" in media[0] and all("caption" not in m for m in media[1:]), media)
cap = media[0].get("caption", "") if media else ""
check("album: caption has text", "سحابی‌ها 🌌" in cap, cap)
check("album: proxy link on the word", "<a href=" in cap and "پروکسی</a>" in cap, cap)
check("album: channel appended", cap.rstrip().endswith("@GodNews24"), cap)
check("album: sent as HTML", PARSE_MODES and PARSE_MODES[0] == "HTML", PARSE_MODES)
check("album: confirmation mentions count", any("۳ رسانه" in m or "3 رسانه" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("album: all three ids recorded", st.get("last_post_ids") == [1001, 1002, 1003], st.get("last_post_ids"))

# ---- 3. long caption: media without caption + separate text ----
reset()
st = fresh_state()
long_cap = "متن خیلی طولانی " * 100  # ~1500 chars
bot.send_album_to_channel(st, [("photo", "P1"), ("photo", "P2")], long_cap)
check("long caption: two calls", len(TG_CALLS) == 2, TG_CALLS)
media = album_media(TG_CALLS[0]) if TG_CALLS else []
check("long caption: group without caption", TG_CALLS[0][0] == "sendMediaGroup" and all("caption" not in m for m in media), TG_CALLS)
check("long caption: second is sendMessage with full text",
      len(TG_CALLS) == 2 and TG_CALLS[1][0] == "sendMessage" and "متن خیلی طولانی" in TG_CALLS[1][1].get("text", "") and "@GodNews24" in TG_CALLS[1][1].get("text", ""), TG_CALLS)

# ---- 4. mixed photo+video; empty album ----
reset()
st = fresh_state()
bot.send_album_to_channel(st, [("photo", "P1"), ("video", "V1")], "ترکیبی")
media = album_media(TG_CALLS[0]) if TG_CALLS else []
check("mixed album: photo+video types", [m.get("type") for m in media] == ["photo", "video"], media)

reset()
st = fresh_state()
bot.send_album_to_channel(st, [], "خالی")
check("empty album: error, no tg call", len(TG_CALLS) == 0 and any("پیدا نشد" in m for m in ADMIN_MSGS), ADMIN_MSGS)

# ---- 5. process_commands: pending /send + 3-photo album (reported case) ----
reset()
updates = [
    upd(10, photo_msg(1, "A1", gid="G1", caption="ناسا چنتا از واضح‌ترین عکس‌های سحابی‌ها رو منتشر کرده.")),
    upd(11, photo_msg(2, "A2", gid="G1")),
    upd(12, photo_msg(3, "A3", gid="G1")),
]
st, changed = run_updates(updates)
check("album via commands: one sendMediaGroup", len(TG_CALLS) == 1 and TG_CALLS[0][0] == "sendMediaGroup", TG_CALLS)
media = album_media(TG_CALLS[0]) if TG_CALLS else []
check("album via commands: all three file_ids", [m.get("media") for m in media] == ["A1", "A2", "A3"], media)
cap = media[0].get("caption", "") if media else ""
check("album via commands: caption kept", "سحابی‌ها" in cap, cap)
check("album via commands: pending cleared", st.get("menu_pending") is None, st.get("menu_pending"))
check("album via commands: confirmation", any("فرستاده شد" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("album via commands: offset advanced past all", st.get("tg_offset") == 13, st.get("tg_offset"))

# ---- 6. a following message flushes the album first ----
reset()
updates = [
    upd(20, photo_msg(1, "B1", gid="G2", caption="آلبوم")),
    upd(21, photo_msg(2, "B2", gid="G2")),
    upd(22, {"message_id": 3, "chat": {"id": 123}, "text": "✉️ ارسال خبر"}),
]
st, changed = run_updates(updates)
check("flush on next message: group sent once", len([c for c in TG_CALLS if c[0] == "sendMediaGroup"]) == 1, TG_CALLS)
check("flush on next message: menu prompt still sent", any("عکس/ویدیوی" in m for m in ADMIN_MSGS), ADMIN_MSGS)
check("flush on next message: pending is /send again", st.get("menu_pending") == "/send", st.get("menu_pending"))

# ---- 7. two albums in one batch ----
reset()
updates = [
    upd(30, photo_msg(1, "C1", gid="G3", caption="اول")),
    upd(31, photo_msg(2, "C2", gid="G3")),
    upd(32, photo_msg(3, "D1", gid="G4", caption="دوم")),
    upd(33, photo_msg(4, "D2", gid="G4")),
]
st, changed = run_updates(updates)
groups = [c for c in TG_CALLS if c[0] == "sendMediaGroup"]
check("two albums: two groups", len(groups) == 2, TG_CALLS)
check("two albums: first has C1 C2", [m.get("media") for m in album_media(groups[0])] == ["C1", "C2"] if groups else False, groups)
check("two albums: second has D1 D2", [m.get("media") for m in album_media(groups[1])] == ["D1", "D2"] if len(groups) > 1 else False, groups)

# ---- 8. inline "/send ..." caption on an album strips the command ----
reset()
updates = [
    upd(40, photo_msg(1, "E1", gid="G5", caption="/send سلام به کانال")),
    upd(41, photo_msg(2, "E2", gid="G5")),
]
st, changed = run_updates(updates, pending=None)
media = album_media(TG_CALLS[0]) if TG_CALLS else []
cap = media[0].get("caption", "") if media else ""
check("inline /send album: one group", len(TG_CALLS) == 1 and TG_CALLS[0][0] == "sendMediaGroup", TG_CALLS)
check("inline /send album: command stripped", cap.startswith("سلام به کانال"), cap)

# ---- 9. regressions: single photo still sendPhoto; stray photo ignored ----
reset()
msg = {"message_id": 5, "chat": {"id": 123}, "photo": [{"file_id": "only"}]}
st, changed = run_updates([upd(50, msg)])
check("single photo: still sendPhoto", len(TG_CALLS) == 1 and TG_CALLS[0][0] == "sendPhoto", TG_CALLS)

reset()
msg = {"message_id": 6, "chat": {"id": 123}, "photo": [{"file_id": "Y"}]}
st, changed = run_updates([upd(60, msg)], pending=None)
check("photo no pending: ignored", len(TG_CALLS) == 0 and len(ADMIN_MSGS) == 0, (TG_CALLS, ADMIN_MSGS))

reset()
msg = {"message_id": 7, "chat": {"id": 123}, "photo": [{"file_id": "Z1"}], "media_group_id": "G9"}
st, changed = run_updates([upd(70, msg)], pending=None)
check("album no pending: ignored", len(TG_CALLS) == 0 and len(ADMIN_MSGS) == 0, (TG_CALLS, ADMIN_MSGS))

# ---- 10. menu unchanged ----
check("menu still 20 buttons", len(bot.MENU_BUTTONS) == 20, len(bot.MENU_BUTTONS))
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu tail unchanged", labels[-3:] == ["🗑 حذف آخرین پست", "🧪 تست", "❓ راهنما"], labels[-3:])

# ---- 11. send_group salvage: only one media downloadable -> that one alone ----
# (before: the whole group fell back to text-only even though one photo was fine)
ORIG_TG = bot.tg
ORIG_DL = bot.download
bot.PARSE_MODE[0] = "HTML"
bot.UPLOAD_FAILS[0] = 0

def tg_group_fail(method, files=None, **data):
    TG_CALLS.append((method, dict(data), files))
    if method == "sendMediaGroup":
        return False
    NEXT_IDS[0] += 1
    bot.LAST_TG_IDS.append(NEXT_IDS[0])
    return True

reset()
bot.tg = tg_group_fail
bot.download = lambda url, limit=30 * 1024 * 1024, max_seconds=60: b"bytes" if "good" in url else None
media3 = [("photo", "https://example.com/bad1.jpg"), ("photo", "https://example.com/good.jpg"),
          ("video", "https://example.com/bad2.mp4")]
check("salvage: group of 3 with 1 good -> True",
      bot.send_group(media3, "خبر مهم") is True)
check("salvage: by_url group failed, single photo sent",
      len(TG_CALLS) == 2 and TG_CALLS[0][0] == "sendMediaGroup" and TG_CALLS[1][0] == "sendPhoto", TG_CALLS)
check("salvage: single photo carries the caption",
      TG_CALLS[1][1].get("caption") == "خبر مهم", TG_CALLS)
check("salvage: single photo uploaded (files, not url)",
      TG_CALLS[1][1].get("photo") is None and TG_CALLS[1][2] is not None and "photo" in TG_CALLS[1][2], TG_CALLS)

reset()
bot.download = lambda url, limit=30 * 1024 * 1024, max_seconds=60: None
check("salvage: nothing downloadable -> False",
      bot.send_group(media3, "خبر مهم") is False)
check("salvage: no photo sent when nothing downloads",
      all(c[0] == "sendMediaGroup" for c in TG_CALLS), TG_CALLS)
bot.tg = ORIG_TG
bot.download = ORIG_DL

# ---- 12. send() records a media failure in /errors when only the text goes out ----
def tg_media_fail(method, files=None, **data):
    TG_CALLS.append((method, dict(data)))
    if method in ("sendMediaGroup", "sendPhoto", "sendVideo"):
        return False
    NEXT_IDS[0] += 1
    bot.LAST_TG_IDS.append(NEXT_IDS[0])
    return True

def tg_item2(media=None):
    it = {"id": "tg:alonews/158629", "title": "تیتر خبر", "summary": "پاراگراف اول. پاراگراف دوم.",
          "paras": ["پاراگراف اول.", "پاراگراف دوم."], "ts": 1700000000, "src": "AloNews",
          "kind": None, "category": "political"}
    if media:
        it["media"] = media
    return it

reset()
bot.tg = tg_media_fail
bot.download = lambda url, limit=30 * 1024 * 1024, max_seconds=60: None
bot.UPLOAD_FAILS[0] = 0
st = fresh_state()
st["stats"] = {}
bot.STATE_REF[0] = st
check("media fail: text-only post still ok", bot.send(tg_item2(media=[("photo", "https://example.com/x.jpg")])))
rej = [e for e in (st.get("rejected") or []) if e.get("why") == "خطا در ارسال رسانه"]
check("media fail: recorded as an error", len(rej) == 1, rej)
check("media fail: source recorded", rej and rej[0].get("src") == "AloNews", rej)
check("media fail: errors counter up", st["stats"].get("errors") == 1, st["stats"])
err_text = "\n".join(bot.rejected_text(st, "errors"))
check("media fail: shows in /errors", "خطا در ارسال رسانه" in err_text and "AloNews" in err_text, err_text)

reset()
bot.tg = fake_tg
bot.download = ORIG_DL
st = fresh_state()
st["stats"] = {}
bot.STATE_REF[0] = st
check("media ok: post ok", bot.send(tg_item2(media=[("photo", "https://example.com/x.jpg")])))
check("media ok: nothing recorded", not [e for e in (st.get("rejected") or []) if e.get("why") == "خطا در ارسال رسانه"], st.get("rejected"))

reset()
st = fresh_state()
st["stats"] = {}
bot.STATE_REF[0] = st
check("no media: post ok", bot.send(tg_item2()))
check("no media: nothing recorded", not [e for e in (st.get("rejected") or []) if e.get("why") == "خطا در ارسال رسانه"], st.get("rejected"))
bot.STATE_REF[0] = None
bot.tg = ORIG_TG

# ---- 13. /status error count includes media failures ----
st = {"stats": {"posted": 5, "rejected": 1, "errors": 1},
      "rejected": [{"src": "AloNews", "why": "خطا در ارسال رسانه", "text": "تیتر خبر",
                    "t": 1700000000, "day": bot.rejected_day()}]}
out = bot.status_text(st)
check("status: errors count includes media failure", "1 خطا" in out, out)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
