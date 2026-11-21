# Tests for bot version 2026-11-21-0.19.
# Three bugs reported 2026-11-21 (screenshots 09:30 / 09:50):
# 1. «کابل‌های برق» got the Afghanistan flag: COUNTRIES has AF: ["افغانستان",
#    "کابل"] and rx() accepts suffixes, so «کابل‌های برق» matched Kabul.
#    Fix: in flags_for, skip AF when the matched word is a کابل form and a
#    cable word (برق، مسی، فیبر، اینترنت، مخابرات، فشار) sits right next to it.
#    Real Kabul news («انفجار در کابل») keeps its flag.
# 2. MEHR video sent apart from the insurance text: the item's full HTML text
#    was ~1090 chars (>1000) so send() deliberately sent the video first
#    without caption, then the text. But the VISIBLE text was only ~763 chars
#    — the HTML length was inflated by the 245-char proxy URL + blockquote
#    tags, and Telegram's 1024 caption limit counts text after entities
#    parsing. Fix: measure caption length on plain (parsed) text everywhere
#    the 1000 threshold is used (build_text trimming, send(), deliver(),
#    recheck_watch skip).
# 3. FT post truncated («فایننشال تایمز به نقل از یک») — the source WAS complete;
#    the bot cut it itself: SOURCE_RULES had «منبع:.*$» which deleted everything
#    from «منبع:» to the end of the text, and «به نقل از یک منبع: ...» starts
#    with exactly that word. Fix: «منبع:» is stripped only when it ends the
#    text and is followed by a known source name; plus _title_and_paras keeps
#    the tail of an over-long single-line caption as a paragraph instead of
#    dropping it. The persistent watch is kept as well: it hardens the real
#    stale-preview case (preview short at fetch, source edited later).
# 4. Version pin 0.19.
import os
import sys
import time
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot019", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

check("version is 0.19", bot.BOT_VERSION == "2026-11-21-0.19", bot.BOT_VERSION)

# ---- 1. کابل: flag guard ----
AF = bot.flag_of("AF")
US = bot.flag_of("US")
check("kabel: کابل‌های برق -> no AF flag",
      AF not in bot.flags_for("سرقت کابل‌های برق در تهران افزایش یافت"))
check("kabel: کابل برق فشار قوی -> no AF flag",
      AF not in bot.flags_for("قطع کابل برق فشار قوی در جنوب تهران"))
check("kabel: کابل‌های اینترنت -> no AF flag",
      AF not in bot.flags_for("شریعتمداری: کابل‌های اینترنت را قطع کنید"))
check("kabel: کابل مسی -> no AF flag",
      AF not in bot.flags_for("قیمت کابل مسی افزایش یافت"))
check("kabel: کابل فیبر نوری -> no AF flag",
      AF not in bot.flags_for("قطع کابل فیبر نوری در مرکز شهر"))
check("kabul: انفجار در کابل -> AF flag",
      AF in bot.flags_for("انفجار در کابل"))
check("kabul: طالبان در کابل -> AF flag",
      AF in bot.flags_for("طالبان در کابل رژه رفتند"))
check("kabul: افغانستان -> AF flag",
      AF in bot.flags_for("افغانستان: طالبان کابینه را تغییر داد"))
check("kabul: اینترنت در کابل قطع شد -> AF flag kept (internet is not next to کابل)",
      AF in bot.flags_for("اینترنت در کابل قطع شد"))
check("flags: آمریکا still -> US flag",
      US in bot.flags_for("وزارت خزانه‌داری آمریکا چهار تبعه ایرانی را تحریم کرد"))

# ---- 1b. قانون «منبع:» — علت واقعی بریدگی پست FT ----
FT_LINE = ("فایننشال تایمز به نقل از یک منبع: فرماندهی مرکزی آمریکا (سنتکام) به دولت آمریکا "
           "اطلاع داده که برای حمله به ایران فرصت در حال از دست رفتن است و منابع مالی و آمادگی "
           "رزمی نیروهای آمریکایی در حال فرسایش است")
check("manba: «منبع:» وسط جمله متن را نمی‌خورد (سنتکام می‌ماند)",
      "سنتکام" in bot.clean(FT_LINE, 200) and "فرماندهی" in bot.clean(FT_LINE, 200)
      and bot.clean(FT_LINE, 200) != "فایننشال تایمز به نقل از یک",
      bot.clean(FT_LINE, 200))
check("manba: «منبع: ایسنا» آخر متن پاک می‌شود",
      bot.clean("متن خبر مهم است. منبع: ایسنا", 200) == "متن خبر مهم است.",
      bot.clean("متن خبر مهم است. منبع: ایسنا", 200))
check("manba: «منبع: خبرگزاری فارس» آخر متن پاک می‌شود",
      bot.clean("متن خبر مهم است. منبع: خبرگزاری فارس", 200) == "متن خبر مهم است.",
      bot.clean("متن خبر مهم است. منبع: خبرگزاری فارس", 200))
check("manba: «منبع: BBC» آخر متن پاک می‌شود",
      bot.clean("متن خبر مهم است. منبع: BBC", 200) == "متن خبر مهم است.",
      bot.clean("متن خبر مهم است. منبع: BBC", 200))

# ---- _title_and_paras: خط اول بلند ----
_ft_title, _ft_paras = bot._title_and_paras([FT_LINE])
check("title: خط تک‌خطی FT کامل می‌ماند",
      _ft_title.endswith("فرسایش است") and "سنتکام" in _ft_title, _ft_title)
check("title: تیتر FT بریده‌ی قبلی نیست",
      _ft_title != "فایننشال تایمز به نقل از یک", _ft_title)
_long1 = "تیتر خبر خیلی طولانی " + "کلمه " * 40 + "پایان خبر اینجاست و دنباله‌اش مهم است"
_t2, _ps2 = bot._title_and_paras([_long1, "پاراگراف دوم"])
check("title: دنباله‌ی خط بلند پاراگراف می‌شود",
      "پایان خبر اینجاست" in " ".join(_ps2) and "پاراگراف دوم" in _ps2, _ps2)
_t3, _ps3 = bot._title_and_paras(["تیتر خبر مهم امروز", "بدنه خبر اینجاست"])
check("title: حالت عادی عوض نشده",
      _t3 == "تیتر خبر مهم امروز" and _ps3 == ["بدنه خبر اینجاست"], (_t3, _ps3))
_t4, _ps4 = bot._title_and_paras(["فوری", "زلزله‌ای در تهران رخ داد", "جزئیات بیشتر"])
check("title: ادغام «فوری» هنوز کار می‌کند",
      _t4.startswith("فوری زلزله‌ای") and _ps4 == ["جزئیات بیشتر"], (_t4, _ps4))

# ---- 2. caption length on plain text ----
REAL_ALIVE = list(bot.ALIVE)
REAL_DECIDE = bot.decide
LONG_PROXY = "https://t.me/proxy?server=www.servertala.ir.&port=8443&secret=" + "x" * 180   # هم‌طول لینک واقعی کانال (۲۴۵ کاراکتر)
bot.ALIVE = [LONG_PROXY]
bot.decide = lambda item: ("🔵", "🔹")

INS_TITLE = "پرداخت خسارت بیمه‌ها از اول آذر برخط می‌شود؛ پایان مراجعه حضوری زیان‌دیدگان"
INS_PARAS = [
    "موسی رضایی، رئیس‌کل بیمه مرکزی، از آغاز اجرای طرح پرداخت برخط خسارت بیمه از اول آذرماه خبر داد.",
    "بر اساس این طرح، فرایند پرداخت خسارت در رشته‌های بیمه درمان تکمیلی، شخص ثالث و بدنه خودرو بدون نیاز به مراجعه حضوری زیان‌دیدگان انجام خواهد شد.",
    "این طرح طی سه تا چهار ماه گذشته با همکاری چند شرکت بیمه به‌صورت آزمایشی اجرا شده و اکنون شرکت‌های بیمه آمادگی لازم برای اجرای آن را دارند.",
    "با اجرای این برنامه، تمام مراحل از زمان وقوع حادثه تا پرداخت خسارت از طریق داشبورد مدیریتی تحت نظارت برخط بیمه مرکزی قرار می‌گیرد.",
    "همچنین تیم‌های نظارتی بیمه مرکزی با حضور سرزده در شعب شرکت‌های بیمه در تهران و استان‌ها، بر روند اجرای این فرایند نظارت خواهند کرد.",
]
ins_item = {"id": "tg:AloNews/999", "title": INS_TITLE, "paras": list(INS_PARAS),
            "src": "AloNews", "red_src": False, "kind": None,
            "media": [("video", "https://cdn.example.com/v.mp4")]}

cap = bot.build_text(ins_item, max_len=1000)
check("caption: insurance caption keeps all 5 paras",
      all(p[:25] in cap for p in INS_PARAS), [p[:25] for p in INS_PARAS if p[:25] not in cap])
check("caption: insurance plain text fits 1000", len(bot.plain_of(cap)) <= 1000, len(bot.plain_of(cap)))
check("caption: insurance HTML is over 1000 (old check would have split it)",
      len(cap) > 1000, len(cap))

# ---- send(): video + short-plain text go in ONE post ----
REAL_TG = bot.tg
REAL_DOWNLOAD = bot.download
REAL_REC_SENT = bot._record_sent_ids
REAL_REC_MAP = bot._record_post_map
REAL_REC_WATCH = bot._record_watch
REAL_REC_MEDIA = bot._record_media_failed
REAL_RESOLVE = bot._resolve_reply_to
TG_CALLS = []

def fake_tg(method, **kw):
    TG_CALLS.append((method, kw))
    return True

bot.tg = fake_tg
bot.download = lambda url, limit=30 * 1024 * 1024, max_seconds=60: b"fake-video-bytes"
bot._record_sent_ids = lambda: None
bot._record_post_map = lambda item: None
bot._record_watch = lambda *a, **k: None
bot._record_media_failed = lambda item: None
bot._resolve_reply_to = lambda item: None

TG_CALLS.clear()
check("send: insurance video+text -> True", bot.send(ins_item) is True)
check("send: insurance video+text -> exactly 1 telegram call", len(TG_CALLS) == 1, TG_CALLS)
check("send: insurance video+text -> the call is sendVideo",
      TG_CALLS and TG_CALLS[0][0] == "sendVideo", TG_CALLS)
check("send: insurance video+text -> caption present with all paras",
      TG_CALLS and "caption" in TG_CALLS[0][1]
      and all(p[:25] in TG_CALLS[0][1]["caption"] for p in INS_PARAS), TG_CALLS)

# ---- control: genuinely long text still splits ----
LONG_PARAS = ["این یک پاراگراف طولانی خبری است که برای آزمایش سقف کپشن نوشته شده و بیش از صد کاراکتر دارد و جزئیات زیادی را پوشش می‌دهد. " * 2] * 8
long_item = {"id": "tg:AloNews/1000", "title": "خبر خیلی طولانی با ویدیو",
             "paras": list(LONG_PARAS), "src": "AloNews", "red_src": False, "kind": None,
             "media": [("video", "https://cdn.example.com/v2.mp4")]}
TG_CALLS.clear()
check("send: genuinely long text -> True", bot.send(long_item) is True)
check("send: genuinely long text -> 2 telegram calls", len(TG_CALLS) == 2, TG_CALLS)
check("send: genuinely long text -> video first without caption, then text",
      len(TG_CALLS) == 2 and TG_CALLS[0][0] == "sendVideo" and "caption" not in TG_CALLS[0][1]
      and TG_CALLS[1][0] == "sendMessage", TG_CALLS)

bot.tg = REAL_TG
bot.download = REAL_DOWNLOAD
bot._record_sent_ids = REAL_REC_SENT
bot._record_post_map = REAL_REC_MAP
bot._record_watch = REAL_REC_WATCH
bot._record_media_failed = REAL_REC_MEDIA
bot._resolve_reply_to = REAL_RESOLVE
bot.ALIVE = REAL_ALIVE
bot.decide = REAL_DECIDE

# ---- 3. persistent watch ----
REAL_STATE_REF = bot.STATE_REF[0]
bot.STATE_REF[0] = {}
bot.LAST_TG_IDS.clear()
bot.LAST_TG_IDS.append(777)
watch_item = {"id": "tg:AloNews/1", "title": "t", "paras": []}
bot._record_watch(watch_item, [("photo", "https://x")], "full text", True)
entry = bot.STATE_REF[0].get("watch_next", {}).get("tg:AloNews/1")
check("watch: _record_watch stores t0", entry is not None and "t0" in entry, entry)
check("watch: _record_watch stores mid/cap", entry is not None and entry.get("mid") == 777
      and entry.get("cap") is True, entry)
bot.STATE_REF[0] = REAL_STATE_REF
bot.LAST_TG_IDS.clear()

now = time.time()
state = {}
bot._stash_long_watch(state, {"a": {"h": "x", "mid": 1, "cap": False, "t0": now},
                              "b": {"h": "y", "mid": 2, "cap": False, "t0": now - 4000}})
check("watch: _stash keeps fresh, prunes expired",
      "a" in state.get("watch_long", {}) and "b" not in state.get("watch_long", {}),
      state.get("watch_long", {}).keys())
bot._stash_long_watch(state, {"c": {"h": "z", "mid": 3, "cap": False, "t0": now}})
check("watch: _stash merges with existing long watch",
      "a" in state.get("watch_long", {}) and "c" in state.get("watch_long", {}),
      state.get("watch_long", {}).keys())
state2 = {"x": 1}
bot._stash_long_watch(state2, {})
check("watch: _stash empty watch is a no-op", state2 == {"x": 1}, state2)

# ---- recheck_watch edits a grown long-watched item ----
REAL_FETCH_TG = bot.fetch_tg
short_item = {"id": "tg:AloNews/159112", "title": "فایننشال تایمز به نقل از یک",
              "paras": [], "src": "AloNews", "red_src": False, "kind": None, "category": "general"}
grown_item = {"id": "tg:AloNews/159112",
              "title": "فایننشال تایمز به نقل از یک منبع: فرماندهی مرکزی آمریکا (سنتکام) به دولت آمریکا اطلاع داده که برای حمله به ایران فرصت در حال از دست رفتن است",
              "paras": [], "src": "AloNews", "red_src": False, "kind": None, "category": "general"}
bot.ALIVE = []
TG_CALLS.clear()
bot.tg = fake_tg
bot.fetch_tg = lambda cat, name, dom: [dict(grown_item)]
watch = {"tg:AloNews/159112": {"h": bot._item_text_hash(short_item), "mid": 777,
                               "cap": False, "t0": time.time()}}
bot.recheck_watch({}, [("x", "tg:AloNews", False)], watch)
check("recheck: grown text -> one editMessageText",
      len(TG_CALLS) == 1 and TG_CALLS[0][0] == "editMessageText", TG_CALLS)
check("recheck: grown text -> edits the right message with the new text",
      TG_CALLS and TG_CALLS[0][1].get("message_id") == 777
      and "سنتکام" in TG_CALLS[0][1].get("text", ""), TG_CALLS)
check("recheck: grown text -> hash updated in watch",
      watch["tg:AloNews/159112"]["h"] == bot._item_text_hash(grown_item),
      watch["tg:AloNews/159112"]["h"])

TG_CALLS.clear()
bot.fetch_tg = lambda cat, name, dom: [dict(short_item)]
watch2 = {"tg:AloNews/159112": {"h": bot._item_text_hash(short_item), "mid": 777,
                                "cap": False, "t0": time.time()}}
bot.recheck_watch({}, [("x", "tg:AloNews", False)], watch2)
check("recheck: unchanged text -> no edit", TG_CALLS == [], TG_CALLS)

bot.fetch_tg = REAL_FETCH_TG
bot.tg = REAL_TG
bot.ALIVE = REAL_ALIVE

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
