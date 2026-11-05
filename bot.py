import os
import re
import json
import html
import time
from datetime import datetime, timedelta, timezone
import random
import socket
import requests
from urllib.parse import urlparse, parse_qs
import feedparser

# ====== تنظیمات ======
TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.environ.get("CHANNEL", "@GodNews24")

# لینک پروکسی (مثلاً https://t.me/proxy?server=...&port=...&secret=...)
PROXY_LINK = ""          # لینک پیش‌فرض (اگه فایل پروکسی خالی بود)
PROXY_FILE = "proxies.txt"  # هر خط یک لینک پروکسی
ALIVE = []               # پروکسی‌های سالمِ همین اجرا

STATE_FILE = "posted.json"
TG_EVERY_MIN = 20        # کانال‌های تلگرامی: هر ۲۰ دقیقه
TG_MIN_POSTS = 5         # هر بار بین ۵ تا ۱۰ خبر
TG_MAX_POSTS = 10
OTHER_EVERY_MIN = 60     # بقیه‌ی منابع (خارجی و داخلی): تقریباً هر ساعت (اجراها هر ۲۰ دقیقه‌ان)
OTHER_MAX_POSTS = 5      # حداکثر ۵ خبر
SLACK_MIN = 5            # تحمل تأخیر/تعجیلِ زمان‌بندی گیت‌هاب
QUIET_START = 1 * 60     # ساعت سکوت: از ۰۱:۰۰ به وقت تهران
QUIET_END = 8 * 60 + 30  # تا ۰۸:۳۰ به وقت تهران
RUN_BUDGET_SEC = 300       # بیشتر از این توی یک اجرا خبر نمی‌فرسته (کل اجرا حداکثر ۸ دقیقه‌ست)
STALE_MIN = 60           # خبرِ جامونده‌ی قدیمی‌تر از این (دقیقه) دور ریخته می‌شه

# (دسته, آدرس RSS, داخلی؟)
# دسته‌ها: general, politics, economy, sports, tech
# منابع خارجی/بین‌المللی اولویت دارن؛ منابع داخلی (True) در هر اجرا حداکثر MAX_DOMESTIC_PER_RUN خبر می‌ذارن
FEEDS = [
    # --- منابع اصلی (کانال‌های تلگرام) ---
    ("general", "tg:AloNews", False),
    ("economy", "tg:arz_talaaa", False),
    ("general", "tg:VahidOnline", False),
    # --- خبرگزاری‌های خارجی ---
    ("general", "https://parsi.euronews.com/rss?format=mrss", False),
    ("general", "https://rss.dw.com/xml/rss-per-all", False),
    ("general", "https://www.france24.com/fa/rss", False),
    ("general", "https://farsi.alarabiya.net/feed/rss2/fa.xml", False),
    ("general", "https://www.independentpersian.com/rss.xml", False),
    # --- منابع داخلی (خیلی کم استفاده می‌شن) ---
    ("general", "https://www.isna.ir/rss", True),
    ("sports", "https://www.varzesh3.com/rss/all", True),
    ("tech", "https://digiato.com/feed", True),
    # کانال تلگرامی عمومی دیگه: آیدی رو بدون @ بعد از tg: بنویس، مثلاً:
    # ("general", "tg:CHANNELNAME", False),
]
MAX_DOMESTIC_PER_RUN = 1
DOMESTIC_CHANCE = 0.5   # فقط در حدود نصف اجراهای «بقیه‌ی منابع» یک خبر داخلی منتشر می‌شه
DEDUP_HOURS = 8         # خبرهای شبیه به هم در این بازه تکراری حساب می‌شن

# ====== دسته‌بندی و ایموجی ======
FLASH_KW = ["فوری", "عاجل", "انفجار", "حمله", "موشک", "زلزله", "کشته", "ترور"]
POLITICS_KW = ["رئیس‌جمهور", "رییس‌جمهور", "رهبر انقلاب", "مجلس", "دولت", "وزیر",
               "تحریم", "مذاکره", "شورای امنیت", "ترامپ", "نتانیاهو", "بایدن",
               "سیاست", "انتخابات", "سپاه", "پزشکیان", "اسرائیل", "آمریکا",
               "سران", "نشست", "سفیر", "دیپلمات", "پارلمان", "قطعنامه", "ناتو",
               "سازمان ملل", "کاخ سفید", "کرملین", "ارتش", "نظامی", "آتش‌بس", "پوتین", "اوکراین"]
ECON_KW = ["دلار", "یورو", "طلا", "سکه", "بورس", "تورم", "بانک", "ارز", "نفت",
           "اقتصاد", "بازار", "قیمت", "رمزارز", "بیت‌کوین", "بیت کوین", "مسکن",
           "یارانه", "بنزین", "صادرات", "واردات"]


SPORT_KW = ["فوتبال", "لیگ", "جام جهانی", "بازیکن", "مربی", "تیم ملی", "المپیک",
            "والیبال", "کشتی", "بسکتبال", "پرسپولیس", "استقلال", "گل زد"]


def pick_emoji(category, title, body=""):
    # ورزشی و فناوری و معمولی: 🔵
    if category in ("sports", "tech") or any(k in title for k in SPORT_KW):
        return "🔵"
    full = title + " " + body
    # کلمه‌های اجباری: اگه توی تیتر باشه 🔴 اول، بعد 🟡؛ اگه فقط توی متن باشه 🟡 اول، بعد 🔴
    if RED_RE.search(title):
        return "🔴"
    if YELLOW_RE.search(title) or YELLOW_RE.search(full):
        return "🟡"
    if RED_RE.search(full):
        return "🔴"
    # سیاسی و مهم و فوری: 🔴
    if any(k in title for k in FLASH_KW):
        return "🔴"
    # اقتصادی: 🟡
    econ_title = re.sub(r"ارز(?=ان|ش|ی|ن)", "", title)  # ارزان/ارزش اقتصادی حساب نمی‌شن
    if category == "economy" or any(k in econ_title for k in ECON_KW):
        return "🟡"
    if category == "politics" or any(k in title for k in POLITICS_KW):
        return "🔴"
    return "🔵"


# ====== حذف منبع از متن ======
SRC = (r"(?:ایسنا|مهر|ایرنا|تسنیم|فارس|مشرق|تابناک|خبرآنلاین|خبر\s?آنلاین|همشهری|ایلنا|ایکنا|"
       r"جماران|انتخاب|عصر\s?ایران|یورونیوز|دویچه[\s‌]?وله|DW|ورزش\s?(?:۳|3|سه)|دیجیاتو|زومیت|"
       r"دنیای\s?اقتصاد|اقتصادنیوز|اکوایران|تجارت\s?نیوز|باشگاه\s?خبرنگاران(?:\s?جوان)?|"
       r"خبرگزاری\s?صدا\s?و\s?سیما|BBC|رویترز|AFP|آسوشیتدپرس|AP)")
AG = r"(?:خبرگزاری\s+|پایگاه\s+خبری\s+|سایت\s+|روزنامه\s+|خبرنگار\s+|سرویس\s+\S+\s+)?"

SOURCE_RULES = [
    re.compile(r"(?:به\s+گزارش|به\s+نقل\s+از|بنا\s?بر\s+گزارش|طبق\s+گزارش|بر\s?اساس\s+گزارش)\s+"
               + AG + SRC + r"[\s،,:؛\-–—]*"),
    re.compile(r"(?:خبرنگار|خبرگزاری)\s+" + SRC + r"[\s،,:؛\-–—]*"),
    re.compile(r"^\s*" + AG + SRC + r"\s*[:\-–—ـ]\s*"),
    re.compile(r"[\(\[]\s*" + AG + SRC + r"\s*[\)\]]"),
    re.compile(r"\s*[|\-–—]\s*" + AG + SRC + r"\s*$"),
    re.compile(r"(?:منبع\s*:|انتهای\s+پیام|ادامه\s+مطلب|بیشتر\s+بخوانید).*$", re.S),
    re.compile(r"https?://\S+"),
]


def strip_sources(text):
    for rule in SOURCE_RULES:
        text = rule.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" \n\t،,:؛-–—")


def clean(text, limit):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = strip_sources(text.strip())
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def clean_paras(raw, limit=700):
    """متن رو به پاراگراف‌های تمیز (بدون منبع) تبدیل می‌کنه."""
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw or "")
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    paras, total = [], 0
    for line in text.split("\n"):
        line = strip_sources(line.strip())
        if len(line) < 6:
            continue
        if total + len(line) > limit:
            room = limit - total
            if room > 60:
                paras.append(line[:room].rsplit(" ", 1)[0] + "…")
            break
        paras.append(line)
        total += len(line)
    return paras


# ====== نفت و پرچم کشورها ======
def is_oil_price(title):
    has_oil = any(k in title for k in ["نفت", "برنت", "WTI"])
    has_price = any(k in title for k in ["قیمت", "نرخ", "بشکه", "برنت", "WTI", "دلاری"])
    return has_oil and has_price


COUNTRIES = {
    "IR": ["ایران"], "US": ["آمریکا", "امریکا", "ایالات متحده"], "RU": ["روسیه"],
    "CN": ["چین"], "IL": ["اسرائیل"], "IQ": ["عراق"], "TR": ["ترکیه"],
    "SA": ["عربستان"], "AE": ["امارات"], "QA": ["قطر"], "KW": ["کویت"],
    "BH": ["بحرین"], "OM": ["عمان"], "LB": ["لبنان"], "SY": ["سوریه"],
    "YE": ["یمن"], "PS": ["فلسطین"], "JO": ["اردن"], "EG": ["مصر"],
    "LY": ["لیبی"], "DZ": ["الجزایر"], "MA": ["مراکش"], "TN": ["تونس"],
    "SD": ["سودان"], "AF": ["افغانستان"], "PK": ["پاکستان"], "IN": ["هند"],
    "BD": ["بنگلادش"], "JP": ["ژاپن"], "KR": ["کره جنوبی"], "KP": ["کره شمالی"],
    "TW": ["تایوان"], "VN": ["ویتنام"], "ID": ["اندونزی"], "MY": ["مالزی"],
    "TH": ["تایلند"], "PH": ["فیلیپین"], "SG": ["سنگاپور"], "AU": ["استرالیا"],
    "NZ": ["نیوزیلند"], "CA": ["کانادا"], "MX": ["مکزیک"], "BR": ["برزیل"],
    "AR": ["آرژانتین"], "VE": ["ونزوئلا"], "CU": ["کوبا"], "CO": ["کلمبیا"],
    "CL": ["شیلی"], "DE": ["آلمان"], "FR": ["فرانسه"],
    "GB": ["انگلیس", "انگلستان", "بریتانیا"], "IT": ["ایتالیا"], "ES": ["اسپانیا"],
    "PT": ["پرتغال"], "NL": ["هلند"], "BE": ["بلژیک"], "CH": ["سوئیس"],
    "AT": ["اتریش"], "SE": ["سوئد"], "NO": ["نروژ"], "DK": ["دانمارک"],
    "FI": ["فنلاند"], "PL": ["لهستان"], "UA": ["اوکراین"], "BY": ["بلاروس"],
    "RO": ["رومانی"], "HU": ["مجارستان"], "GR": ["یونان"], "RS": ["صربستان"],
    "AM": ["ارمنستان"], "AZ": ["جمهوری آذربایجان", "آذربایجان"], "GE": ["گرجستان"],
    "KZ": ["قزاقستان"], "UZ": ["ازبکستان"], "TM": ["ترکمنستان"],
    "TJ": ["تاجیکستان"], "KG": ["قرقیزستان"], "ZA": ["آفریقای جنوبی"],
    "NG": ["نیجریه"], "ET": ["اتیوپی"], "KE": ["کنیا"], "IE": ["ایرلند"],
    "NP": ["نپال"], "LK": ["سریلانکا"], "MM": ["میانمار"], "KH": ["کامبوج"],
    "CY": ["قبرس"], "BG": ["بلغارستان"], "HR": ["کرواسی"], "PA": ["پاناما"], "EU": ["اتحادیه اروپا", "اروپا"],
}
_L = "\u0600-\u06FF\u200c"
COUNTRY_RE = []
for _code, _names in COUNTRIES.items():
    _alt = "|".join(re.escape(n) for n in sorted(_names, key=len, reverse=True))
    COUNTRY_RE.append((_code, re.compile(
        rf"(?<![{_L}])(?:{_alt})(?:\u200c?(?:های|ها|یی|ایی|ای|ی)){{0,2}}(?![{_L}])")))
NOT_COUNTRY = ["ایران خودرو", "ایران‌خودرو", "ایرانخودرو", "دریای عمان", "اقیانوس هند", "آذربایجان شرقی", "آذربایجان غربی",
               "خلیج فارس", "تنگه هرمز"]


# کلمه‌هایی که ایموجی اول رو اجباری می‌کنن
RED_TERMS = ["جنگ", "سپاه", "ترامپ", "کمیسیون[\\s\u200c]+امنیت[\\s\u200c]+ملی"]
YELLOW_TERMS = ["بورس", "فارکس", "ارز(?:ها|های)?[\\s\u200c]*دیجی?تال", "کریپتو", "رمز[\\s\u200c]*ارز"]
_SUF = "(?:\u200c?(?:ها|های|ی|یی|ای))?"
_red = "|".join(RED_TERMS)
_yel = "|".join(YELLOW_TERMS)
RED_RE = re.compile(rf"(?<![{_L}])(?:{_red}){_SUF}(?![{_L}])")      # جنگل قرمز حساب نمی‌شه
YELLOW_RE = re.compile(rf"(?<![{_L}])(?:{_yel})")

FLAG_WORDS = 6   # پرچم فقط وقتی که اسم کشور توی ۶ کلمه‌ی اولِ تیتر باشه


def flags_for(title, limit=2):
    if re.search("[\U0001F1E6-\U0001F1FF]", title):
        return ""  # خودش پرچم داره
    t = title.replace("ي", "ی").replace("ك", "ک")
    for bad in NOT_COUNTRY:
        t = t.replace(bad, " ")
    t = " ".join(" ".join(t.split()).split(" ")[:FLAG_WORDS])
    found = []
    for code, rx in COUNTRY_RE:
        m = rx.search(t)
        if m:
            found.append((m.start(), code))
    found.sort()
    return "".join(chr(0x1F1E6 + ord(c) - 65) for _, code in found[:limit] for c in code)


# ====== استخراج عکس و فیلم ======
def find_media(e):
    image, video = None, None

    def ok(u):
        return isinstance(u, str) and u.startswith("http")

    for m in e.get("media_content", []) or []:
        u, t = m.get("url"), (m.get("type") or m.get("medium") or "")
        if not ok(u):
            continue
        if "video" in t:
            video = video or u
        else:
            image = image or u
    for m in e.get("media_thumbnail", []) or []:
        if ok(m.get("url")):
            image = image or m["url"]
    for l in e.get("links", []) or []:
        if l.get("rel") == "enclosure" and ok(l.get("href")):
            t = l.get("type", "")
            if t.startswith("video"):
                video = video or l["href"]
            elif t.startswith("image"):
                image = image or l["href"]
    if not image:
        blob = e.get("summary", "") or ""
        for c in e.get("content", []) or []:
            blob += c.get("value", "")
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', blob)
        if m and ok(m.group(1)):
            image = m.group(1)
    return image, video


# ====== حافظه ======
def load_state():
    state = {"seen": [], "seeded": [], "titles": []}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):  # فرمت قدیمی
            state["seen"] = data
        else:
            state.update(data)
    return state


def save_state(state):
    state["seen"] = state["seen"][-5000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


# ====== تشخیص خبر تکراری ======
def tokens_of(item):
    n = 600 if item.get("kind") else 80   # لیست قیمت: اعداد هم حساب می‌شن
    text = item["title"] + " " + item["summary"][:n]
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[^\w\s]", " ", text)
    return {w for w in text.split() if len(w) >= 3}


def is_dup(tok, others, th=0.5):
    if not tok:
        return False
    for o in others:
        union = len(tok | o)
        if union and len(tok & o) / union >= th:
            return True
    return False


# ====== دریافت خبر ======

# ====== خبر از کانال تلگرام عمومی ======
def clean_tg(text):
    text = re.sub(r"(?:https?://)?(?:t|telegram)\.me/\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    lines = []
    for line in text.split("\n"):
        if re.search(r"(عضو|join|دنبال|فالو|ورود).{0,20}(کانال|channel|بشید|شوید)", line, re.I):
            continue
        lines.append(line.strip())
    return "\n".join(lines)


# ====== ایموجی کانال‌ها، فیلتر کلمه، شوخی، لیست قیمت ======
EMOJI_CHARS = ("\U0001F000-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\u2B00-\u2BFF"
               "\u2190-\u21FF\u25A0-\u25FF\u200d\ufe0f\u20e3\u2139\u203c\u2049\u2122"
               "\u3030\u303d\u3297\u3299\u00a9\u00ae")
EMOJI_RE = re.compile("[" + EMOJI_CHARS + "]+")
LEAD_RE = re.compile("^(?:[" + EMOJI_CHARS + "]|[\\s\\-\u2013\u2014\u2022\u00b7|])+")

# خبرهایی که این کلمه‌ها توشون باشه منتشر نمی‌شن (بدون فاصله و نیم‌فاصله بنویس)
BLOCKED_WORDS = ["خوشچشم"]

# کانال‌هایی که خبرِ شوخی‌شون منتشر نمی‌شه
JOKE_CHANNELS = {"AloNews"}
JOKE_EMOJIS = "😂🤣😆😅😹😜🤪😝🙃😁"
JOKE_RE = re.compile(r"شوخی|طنز|جوک|فکاهی|خنده\s?دار|خنده‌دار|بامزه|ترول|اول\s?آوریل|ه{3,}|خ{3,}")

MONEY_KW = ["دلار", "یورو", "سکه", "طلا", "درهم", "پوند", "تتر", "بیت‌کوین", "بیت کوین", "ارز", "مثقال"]
CAR_BRANDS = ["پراید", "پژو", "سمند", "دنا", "تیبا", "ساینا", "کوییک", "شاهین", "سورن", "رانا",
              "تارا", "هایما", "چری", "جک", "کیا", "هیوندای", "تویوتا", "مزدا", "رنو", "نیسان",
              "ام وی ام", "MVM", "فونیکس", "تیگو", "آریزو", "اطلس", "زامیاد", "سراتو",
              "اسپورتیج", "النترا", "سانتافه", "تندر", "سایپا", "کرمان موتور", "مگان", "بنز", "بی ام و"]


def strip_emoji(text):
    """همه‌ی ایموجی‌ها رو از متن برمی‌داره."""
    lines = []
    for line in text.split("\n"):
        line = EMOJI_RE.sub(" ", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        line = re.sub(r"^[\-\u2013\u2014\u2022\u00b7|:؛،.\s]+", "", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def strip_leading_emoji(line):
    return LEAD_RE.sub("", line).strip()


# کلمه‌های ممنوع فقط برای یک کانال
CHANNEL_BLOCKED = {"AloNews": ["عوستاد"]}


def is_blocked(text, extra=()):
    key = re.sub(r"[\s\u200c]", "", text)
    words = [re.sub(r"[\s\u200c]", "", w) for w in list(BLOCKED_WORDS) + list(extra)]
    return any(w in key for w in words)


def looks_like_joke(raw):
    return any(ch in raw for ch in JOKE_EMOJIS) or bool(JOKE_RE.search(raw))


def has_word(text, w):
    return re.search(r"(?<![\u0600-\u06FF])" + re.escape(w) + r"(?![\u0600-\u06FF])", text) is not None


def digit_lines(lines):
    return sum(1 for l in lines if len(re.findall(r"[0-9۰-۹]", l)) >= 2)


def detect_pricelist(lines):
    """'car' برای لیست قیمت خودرو، 'money' برای لیست قیمت طلا و ارز، وگرنه None."""
    if len(lines) < 4 or digit_lines(lines) < 3:
        return None
    text = " ".join(lines)
    head = lines[0]
    brands = sum(1 for b in CAR_BRANDS if has_word(text, b))
    if brands >= 3 or (("خودرو" in head or "ماشین" in head) and ("قیمت" in head or "لیست" in head)):
        return "car"
    money = sum(1 for k in MONEY_KW if k in text)
    if money >= 2 or (money >= 1 and ("قیمت" in head or "نرخ" in head)):
        return "money"
    return None


def parse_tg_page(page, allow_media_only=False):
    """پست‌های صفحه‌ی عمومی کانال رو برمی‌گردونه (با bs4، یا بدون اون با regex)."""
    posts = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        BeautifulSoup = None

    def uniq(seq):
        out = []
        for x in seq:
            if x not in out:
                out.append(x)
        return out

    if BeautifulSoup:
        soup = BeautifulSoup(page, "html.parser")
        for box in soup.select("div.tgme_widget_message"):
            post_id = box.get("data-post")
            body = box.select_one(".js-message_text") or box.select_one(".tgme_widget_message_text")
            if not post_id or (not body and not allow_media_only):
                continue
            if body:
                for br in body.find_all("br"):
                    br.replace_with("\n")
            photos = []
            for a in box.select("a.tgme_widget_message_photo_wrap"):
                m = re.search(r"url\('([^']+)'\)", a.get("style", ""))
                if m:
                    photos.append(m.group(1))
            videos = [v["src"] for v in box.select("video") if str(v.get("src", "")).startswith("http")]
            media = [("photo", u) for u in uniq(photos)] + [("video", u) for u in uniq(videos)]
            if not body and not media:
                continue
            t = box.select_one("time")
            posts.append({"post_id": post_id, "text": body.get_text() if body else "",
                          "html": body.decode_contents() if body else "", "media": media,
                          "dt": t.get("datetime") if t else None})
    else:
        for blk in re.split(r'(?=<div class="tgme_widget_message_wrap)', page)[1:]:
            pid = re.search(r'data-post="([^"]+)"', blk)
            body = (re.search(r'<div class="tgme_widget_message_text[^"]*js-message_text[^"]*"[^>]*>(.*?)</div>', blk, re.S)
                    or re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', blk, re.S))
            if not pid or (not body and not allow_media_only):
                continue
            inner = body.group(1) if body else ""
            raw = re.sub(r"(?i)<br\s*/?>", "\n", inner)
            text = html.unescape(re.sub(r"<[^>]+>", "", raw))
            photos = re.findall(r"tgme_widget_message_photo_wrap[^>]*style=\"[^\"]*url\('([^']+)'\)", blk)
            videos = [u for u in re.findall(r'<video[^>]+src="([^"]+)"', blk) if u.startswith("http")]
            media = [("photo", u) for u in uniq(photos)] + [("video", u) for u in uniq(videos)]
            if not body and not media:
                continue
            dt = re.search(r'<time[^>]+datetime="([^"]+)"', blk)
            posts.append({"post_id": pid.group(1), "text": text, "html": inner, "media": media,
                          "dt": dt.group(1) if dt else None})
    return posts


# ====== کیوسک خبر (@kioskkhabar): فقط چند پیام مشخص ======
KIOSK = "kioskkhabar"
MORNING_FROM, MORNING_TO = 8 * 60 + 30, 13 * 60   # صبح بخیر و نگاه گذرا: ۰۸:۳۰ تا ۱۳:۰۰ تهران
SUMMARY_WAIT_UNTIL = 10 * 60                        # نگاه گذرا تا ۱۰:۰۰ منتظر صبح بخیر می‌مونه
NIGHT_FROM, NIGHT_END = 45, 100                     # شب بخیر: ۰۰:۴۵ تا ۰۱:۴۰ تهران
PAPERS_MAX_AGE_H = 3                                # روزنامه‌ها: فقط تازه‌های ۳ ساعت اخیر


def tehran_now():
    return datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)


CHANNEL_SKIP_FROM, CHANNEL_SKIP_TO = 1 * 60, 7 * 60   # پست‌های کانال‌ها بین ۰۱:۰۰ تا ۰۷:۰۰ تهران استفاده نمی‌شن


def in_skip_hours(ts):
    t = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=3, minutes=30)
    return CHANNEL_SKIP_FROM <= t.hour * 60 + t.minute < CHANNEL_SKIP_TO


def tg_safe_html(inner):
    """HTML متن پست رو به فرمتی که تلگرام قبول می‌کنه تبدیل می‌کنه (بدون تغییر در محتوا)."""
    h = re.sub(r'<i class="emoji"[^>]*><b>(.*?)</b></i>', r"\1", inner or "", flags=re.S)
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)

    def fix_a(m):
        href, txt = m.group(1), m.group(2)
        if href.startswith(("http://", "https://", "tg://")):
            return f'<a href="{href}">{txt}</a>'
        return txt  # لینک هشتگ و لینک‌های نسبی: فقط متن

    h = re.sub(r'<a\s[^>]*?href="([^"]*)"[^>]*>(.*?)</a>', fix_a, h, flags=re.S)
    names = {"strong": "b", "em": "i", "ins": "u", "del": "s", "strike": "s"}

    def tag(m):
        closing, name = bool(m.group(1)), m.group(2).lower()
        name = names.get(name, name)
        if name in ("b", "i", "u", "s", "code", "pre"):
            return f"</{name}>" if closing else f"<{name}>"
        if name == "a":
            return m.group(0)
        return ""

    h = re.sub(r"<(/?)([a-zA-Z][a-zA-Z0-9\-]*)([^>]*)>", tag, h)
    return h.replace("&nbsp;", " ").strip()


def remove_hashtags(h):
    h = re.sub(r"#[\w\u0600-\u06FF\u200c]+", "", h)
    out = []
    for line in h.split("\n"):
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        if not line and (not out or not out[-1]):
            continue
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def kiosk_kind(p):
    key = re.sub(r"[\s\u200c_]+", "", p["text"])
    photos = [m for m in p["media"] if m[0] == "photo"]
    if "نگاهیگذرا" in key:
        return "summary"
    if "شببخیر" in key:
        return "night"
    if "صبحبخیر" in key:
        return "morning"
    if len(photos) >= 3 and any(w in key for w in ("روزنامه", "صفحهاول", "پیشخوان")):
        return "papers"
    return None


def fetch_kiosk(pages):
    out = []
    url = f"https://t.me/s/{KIOSK}"
    for _ in range(pages):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        except Exception as ex:
            print("kiosk error:", ex)
            break
        ps = parse_tg_page(r.text, allow_media_only=True)
        print(f"kiosk http={r.status_code} posts={len(ps)}")
        if not ps:
            break
        ids = []
        for p in ps:
            p["ts"] = 0
            if p["dt"]:
                try:
                    p["ts"] = datetime.fromisoformat(p["dt"]).timestamp()
                except ValueError:
                    pass
            p["id"] = "tg:" + p["post_id"]
            p["sp"] = kiosk_kind(p)
            p["html"] = tg_safe_html(p["html"])
            try:
                ids.append(int(p["post_id"].rsplit("/", 1)[1]))
            except (ValueError, IndexError):
                pass
        out += ps
        stamps = [p["ts"] for p in ps if p["ts"]]
        if (stamps and time.time() - min(stamps) > 15 * 3600) or not ids:
            break
        url = f"https://t.me/s/{KIOSK}?before={min(ids)}"
    return out


def fetch_tg(category, name, domestic):
    items = []
    skipped_night = 0
    try:
        r = requests.get(f"https://t.me/s/{name}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        posts = parse_tg_page(r.text)
        print(f"tg:{name} http={r.status_code} bytes={len(r.text)} posts_with_text={len(posts)}")
        if not posts:
            print(f"  ! هیچ پستی خونده نشد: پیش‌نمایش عمومی کانال بسته‌ست یا دسترسی بلاکه (آیدی: {name})")
        for p in posts:
            raw = p["text"]
            if is_blocked(raw, CHANNEL_BLOCKED.get(name, ())):
                print("  blocked word, skipped:", raw[:40].replace("\n", " "))
                continue
            if name in JOKE_CHANNELS and looks_like_joke(raw):
                print("  joke, skipped:", raw[:40].replace("\n", " "))
                continue
            text = clean_tg(raw)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            kind = detect_pricelist(lines)
            if kind:
                # لیست قیمت: ایموجی‌های داخل متن دست‌نخورده می‌مونه، فقط ایموجی اول عوض می‌شه
                title = clean(strip_leading_emoji(lines[0]), 200)
                paras = [x for x in (strip_sources(l) for l in lines[1:]) if x]
            else:
                text = strip_emoji(text)  # ایموجی‌های خود کانال حذف می‌شه
                lines = [l for l in text.split("\n") if l.strip()]
                if not lines or len(text) < 15:
                    continue
                title = clean(lines[0], 200)
                paras = [x for x in clean_paras("\n".join(lines[1:]), 700) if x != title]
            if not title:
                continue
            ts = 0
            if p["dt"]:
                try:
                    ts = datetime.fromisoformat(p["dt"]).timestamp()
                except ValueError:
                    pass
            if ts and in_skip_hours(ts):
                skipped_night += 1
                continue
            items.append({"id": "tg:" + p["post_id"], "title": title, "summary": " ".join(paras),
                          "paras": paras, "kind": kind, "category": category, "domestic": domestic,
                          "media": p["media"], "image": None, "video": None, "ts": ts})
    except Exception as ex:
        print("telegram channel error:", name, ex)
    items.sort(key=lambda x: x["ts"])
    print(f"{len(items):3d} items  tg:{name}" + (f"  ({skipped_night} پست ساعت ۰۱ تا ۰۷ رد شد)" if skipped_night else ""))
    return items


def fetch_feed(category, url, domestic):
    if url.startswith("tg:"):
        return fetch_tg(category, url[3:], domestic)
    items = []
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        for e in feed.entries:
            uid = e.get("id") or e.get("link")
            if not uid or not e.get("title"):
                continue
            title = clean(e.title, 200)
            if not title:
                continue
            paras = [p for p in clean_paras(e.get("summary", ""), 700) if p != title]
            summary = " ".join(paras)
            if len(summary) < 20:
                paras, summary = [], ""
            ts = time.mktime(e.published_parsed) if e.get("published_parsed") else 0
            image, video = find_media(e)
            items.append({"id": uid, "title": title, "summary": summary, "paras": paras,
                          "category": category, "domestic": domestic, "image": image, "video": video, "ts": ts})
    except Exception as ex:
        print("feed error:", url, ex)
    items.sort(key=lambda x: x["ts"])
    print(f"{len(items):3d} items  {url}")
    return items


# ====== پروکسی‌ها ======
def load_proxies():
    links = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    links.append(line.replace("tg://proxy?", "https://t.me/proxy?", 1))
    return links


def proxy_alive(link):
    try:
        q = parse_qs(urlparse(link).query)
        host, port = q["server"][0], int(q["port"][0])
        with socket.create_connection((host, port), timeout=3):
            return True
    except Exception:
        return False


def prepare_proxies(want=15, max_checks=80):
    """پروکسی‌ها رو هم‌زمان چک می‌کنه (سریع، تا ساعت‌های رایگان گیت‌هاب هدر نره)."""
    from concurrent.futures import ThreadPoolExecutor
    links = load_proxies()
    random.shuffle(links)
    sample = links[:max_checks]
    if sample:
        with ThreadPoolExecutor(max_workers=20) as ex:
            ok = list(ex.map(proxy_alive, sample))
        ALIVE.extend([l for l, good in zip(sample, ok) if good][:want])
    print(f"proxies: {len(links)} in file, {len(sample)} checked, {len(ALIVE)} alive")


# ====== ارسال ======
PARSE_MODE = ["HTML"]
UPLOAD_FAILS = [0]   # اگه آپلود دو بار تایم‌اوت شد، بقیه‌ی اجرا بدون آپلود ادامه پیدا می‌کنه
MARKER = {"🔴": "🔻", "🟡": "🔶", "🔵": "🔷"}


def proxy_parts():
    """(نسخه‌ی HTML, نسخه‌ی ساده) خط پروکسی."""
    link = random.choice(ALIVE) if ALIVE else PROXY_LINK
    if link:
        return f'<a href="{html.escape(link, quote=True)}">پروکسی</a>😉', f"پروکسی😉 {link}"
    return "پروکسی😉", "پروکسی😉"


def build_text(item, max_len=4000):
    esc = html.escape
    kind = item.get("kind")
    if kind:
        # لیست قیمت: ایموجی اول ثابته و ایموجی‌های داخل لیست دست‌نخورده می‌مونه
        lead = "🚙" if kind == "car" else "🟡"
        marker = ""
    else:
        full = item["title"] + " " + item.get("summary", "")
        base = pick_emoji(item["category"], item["title"], item.get("summary", ""))
        marker = MARKER[base]
        flags = flags_for(item["title"])
        forced = (base == "🔴" and RED_RE.search(full)) or (base == "🟡" and YELLOW_RE.search(full))
        if is_oil_price(item["title"]):
            lead = "🛢️"          # قیمت نفت: فقط همین ایموجی
            if base == "🔵":
                marker = "🔶"
        elif forced:
            lead = base + (" " + flags if flags else "")   # کلمه‌ی اجباری: ایموجی اول، بعدش پرچم
        elif flags:
            lead = flags          # اگه پرچم هست، ایموجی دسته‌بندی گذاشته نمی‌شه
        else:
            lead = base
    first = f"{lead} <b>{esc(item['title'])}</b>"

    tail = [proxy_parts()[0], CHANNEL]

    paras = list(item.get("paras") or [])
    mark = (not kind) and len(paras) >= 2   # فقط خبرِ چندپاراگرافی علامت می‌گیره

    def assemble(ps):
        if kind:
            body = ["\n".join(esc(p) for p in ps)] if ps else []
        else:
            body = [f"{marker} {esc(p)}" if mark else esc(p) for p in ps]
        return "\n\n".join([first] + body + tail)

    text = assemble(paras)
    while len(text) > max_len and paras:
        paras.pop()
        text = assemble(paras)
    return text


def tg(method, files=None, **data):
    data["chat_id"] = CHANNEL
    if PARSE_MODE[0] and method != "sendMediaGroup":
        data["parse_mode"] = PARSE_MODE[0]
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    timeout = (10, 60 if files else 30)
    try:
        r = requests.post(url, data=data, files=files, timeout=timeout)
        if r.status_code == 429:  # محدودیت سرعت تلگرام: صبر و یک بار تلاش دوباره
            try:
                wait = int(r.json().get("parameters", {}).get("retry_after", 5))
            except Exception:
                wait = 5
            time.sleep(min(wait, 30))
            r = requests.post(url, data=data, files=files, timeout=timeout)
    except requests.RequestException as ex:   # قطعی/کندیِ شبکه نباید کل اجرا رو خراب کنه
        print("  telegram network error:", method, type(ex).__name__)
        if files:
            UPLOAD_FAILS[0] += 1
        return False
    if not r.ok:
        print("  telegram error:", method, r.status_code, r.text[:150])
    return r.ok


def download(url, limit=30 * 1024 * 1024, max_seconds=60):
    try:
        started = time.time()
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=(10, 30), stream=True)
        if not r.ok:
            return None
        chunks, size = [], 0
        for chunk in r.iter_content(1 << 18):
            chunks.append(chunk)
            size += len(chunk)
            if size > limit or time.time() - started > max_seconds:
                print("  download skipped (too big or slow):", url[:70])
                return None
        return b"".join(chunks)
    except Exception as ex:
        print("  download error:", type(ex).__name__)
        return None


def media_list(item):
    if item.get("media"):
        return item["media"][:10]
    if item.get("video"):
        return [("video", item["video"])]
    if item.get("image"):
        return [("photo", item["image"])]
    return []


def send_single(kind, url, caption, upload_first=False):
    method, field = ("sendVideo", "video") if kind == "video" else ("sendPhoto", "photo")
    cap = {"caption": caption} if caption else {}

    def by_url():
        return tg(method, **{field: url}, **cap)

    def by_upload():   # خودمون دانلود و آپلود می‌کنیم
        if UPLOAD_FAILS[0] >= 2:
            return False
        data = download(url)
        if not data:
            return False
        return tg(method, files={field: ("file.mp4" if kind == "video" else "file.jpg", data)}, **cap)

    for attempt in ((by_upload, by_url) if upload_first else (by_url, by_upload)):
        if attempt():
            return True
    return False


def send_group(media, caption, upload_first=False):
    def first_caption(m, is_first):
        if is_first and caption:
            m["caption"] = caption
            if PARSE_MODE[0]:
                m["parse_mode"] = PARSE_MODE[0]
        return m

    def by_url():
        arr = [first_caption({"type": k, "media": u}, i == 0) for i, (k, u) in enumerate(media)]
        return tg("sendMediaGroup", media=json.dumps(arr))

    def by_upload():
        if UPLOAD_FAILS[0] >= 2:
            return False
        files, arr = {}, []
        for i, (k, u) in enumerate(media):
            d = download(u)
            if not d:
                continue
            fname = f"f{i}"
            files[fname] = (fname + (".mp4" if k == "video" else ".jpg"), d)
            arr.append(first_caption({"type": k, "media": f"attach://{fname}"}, not arr))
        if len(arr) >= 2:
            return tg("sendMediaGroup", files=files, media=json.dumps(arr))
        return False

    for attempt in ((by_upload, by_url) if upload_first else (by_url, by_upload)):
        if attempt():
            return True
    return False


def send(item):
    media = media_list(item)
    caption = build_text(item, max_len=1000)
    up = str(item.get("id", "")).startswith("tg:")   # تلگرام لینک عکس کانال‌ها رو نمی‌تونه بگیره؛ مستقیم آپلود
    if len(media) >= 2 and send_group(media, caption, up):
        return True
    if media and send_single(media[0][0], media[0][1], caption, up):
        return True
    return tg("sendMessage", text=build_text(item), disable_web_page_preview="true")


def plain_of(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def deliver(text, media):
    if media and len(text) > 1000:   # کپشن تلگرام حداکثر ۱۰۲۴ کاراکتره: اول عکس، بعد متن
        ok = send_group(media, "", True) if len(media) >= 2 else send_single(media[0][0], media[0][1], "", True)
        return ok and tg("sendMessage", text=text, disable_web_page_preview="true")
    if len(media) >= 2 and send_group(media, text, True):
        return True
    if media and send_single(media[0][0], media[0][1], text, True):
        return True
    if text:
        return tg("sendMessage", text=text, disable_web_page_preview="true")
    return False


def send_special(text, media, proxy):
    """متن (HTML) رو می‌فرسته. ته پیام: [پروکسی] و بعد آیدی کانال خودمون."""
    text = text.strip()
    p_html, p_plain = proxy_parts()
    if deliver("\n\n".join(x for x in (text, p_html if proxy else "", CHANNEL) if x), media):
        return True
    PARSE_MODE[0] = None   # اگه تلگرام فرمت HTML رو نپذیرفت، به‌صورت متن ساده
    try:
        parts = (plain_of(text), p_plain if proxy else "", CHANNEL)
        return deliver("\n\n".join(x for x in parts if x), media)
    finally:
        PARSE_MODE[0] = "HTML"


def strip_leading_emoji_html(h):
    """ایموجی‌های اول متن رو برمی‌داره (حتی اگه توی تگ <b> و مانند اون باشه)."""
    return re.sub(r"^((?:\s*<[^>]+>)*)(?:[" + EMOJI_CHARS + r"]|[\s\-\u2013\u2014\u2022\u00b7|])+", r"\1", h.strip())


def drop_id_lines(h):
    """خط‌هایی که فقط آیدی/لینک کیوسک هستن (امضای آخر پیام) حذف می‌شن."""
    keep = []
    for line in h.split("\n"):
        plain = re.sub(r"<[^>]+>", "", line).strip()
        if re.fullmatch(r"[\W_]*(?:@|(?:https?://)?(?:t|telegram)\.me/)" + KIOSK + r"[\W_]*", plain, re.I):
            continue
        keep.append(line)
    return "\n".join(keep).strip()


KIOSK_LINK_RE = re.compile(r"(?:https?://)?(?:t|telegram)\.me/" + KIOSK + r"[^\s<\"']*", re.I)
ANY_LINK_RE = re.compile(r"https?://[^\s<\"']+|(?:t|telegram)\.me/[^\s<\"']+", re.I)


def swap_channel(h, all_links=False):
    """آیدی و لینک کانال کیوسک رو با آیدی و لینک کانال خودمون عوض می‌کنه.
    all_links=True (برای «نگاه گذرا»): همه‌ی لینک‌ها به لینک کانال خودمون تبدیل می‌شن."""
    own_link = "https://t.me/" + CHANNEL.lstrip("@")
    link_re = ANY_LINK_RE if all_links else KIOSK_LINK_RE
    out = []
    for part in re.split(r"(<[^>]+>)", h):
        if part.startswith("<a "):
            m = re.search(r'href="([^"]*)"', part)
            if m and (all_links or KIOSK_LINK_RE.search(m.group(1))):
                part = f'<a href="{own_link}">'
            out.append(part)
        elif part.startswith("<"):
            out.append(part)
        else:
            part = link_re.sub(own_link, part)
            part = re.sub("@" + re.escape(KIOSK) + r"(?![A-Za-z0-9_])", CHANNEL, part, flags=re.I)
            out.append(part)
    return "".join(out)


def run_special(kind, p, seen, ks):
    text = p["html"]
    if kind in ("morning", "night"):
        text, proxy = remove_hashtags(text), False   # هشتگ پاک می‌شه، بدون پروکسی
    else:
        proxy = True                                  # نگاه گذرا و روزنامه‌ها: + پروکسی
    text = drop_id_lines(text)                              # امضای آخرِ کیوسک حذف می‌شه
    text = swap_channel(text, all_links=(kind == "summary"))
    text = strip_leading_emoji_html(text)                   # اول متن ایموجی نباشه
    ok = send_special(text, p["media"], proxy)
    if ok:
        seen[p["id"]] = None
        if kind in ks:
            ks[kind] = True
        print("kiosk posted:", kind, p["post_id"])
    return ok


def collect(feeds, seen, seeded, seed_n):
    """خبرهای تازه‌ی منابع رو جمع می‌کنه. منبع جدید: فقط seed_n خبر آخر، بقیه قدیمی حساب می‌شن."""
    cands = {}
    for category, url, domestic in feeds:
        items = fetch_feed(category, url, domestic)
        if not items:
            continue
        if url not in seeded:
            keep = seed_n if url.startswith("tg:") else 1
            for i in items[:-keep]:
                seen[i["id"]] = None
            fresh = items[-keep:]
            seeded.add(url)
        else:
            fresh = items
        for i in fresh:
            if i["id"] not in seen:
                cands[i["id"]] = i
    return list(cands.values())


def choose(cands, limit, seen, recent_sets, kept_sets):
    """جدیدترین خبرهای غیرتکراری رو تا سقف limit انتخاب می‌کنه."""
    final = []
    for item in sorted(cands, key=lambda x: -x["ts"]):
        tok = tokens_of(item)
        th = 0.9 if item.get("kind") else 0.5   # لیست قیمتِ تغییرکرده تکراری حساب نمی‌شه
        if is_dup(tok, recent_sets, th) or is_dup(tok, kept_sets, th):
            seen[item["id"]] = None
            print("duplicate skipped:", item["title"][:50])
            continue
        if len(final) >= limit:
            # صف کهنه نشه: خبر قدیمیِ جا‌مونده دور ریخته می‌شه
            if item["ts"] and time.time() - item["ts"] > STALE_MIN * 60:
                seen[item["id"]] = None
            continue
        item["tok"] = tok
        kept_sets.append(tok)
        final.append(item)
    return final


def is_quiet_hours():
    t = tehran_now()
    m = t.hour * 60 + t.minute
    return QUIET_START <= m < QUIET_END


def main():
    state = load_state()
    now = time.time()
    # اجرای دستی از دکمه‌ی Run workflow: همه‌چیز؛ اجرای خودکار (mode=auto) طبق زمان‌بندی
    force = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("RUN_MODE", "manual") != "auto"
    th = tehran_now()
    m = th.hour * 60 + th.minute
    day_id = (th - timedelta(hours=8)).strftime("%Y-%m-%d")   # «روز» کانال: ۰۸:۳۰ تا ۰۱:۰۰ بعد
    ks = state.get("kiosk") or {}
    if ks.get("day") != day_id:
        ks = {"day": day_id, "morning": False, "summary": False, "night": False}

    only_night = False
    if not force and is_quiet_hours():
        if m < NIGHT_END and not ks["night"]:
            only_night = True   # اجرا دیر شروع شده؛ فقط پیام «شب بخیر» فرستاده می‌شه
        else:
            print("ساعت سکوته (۰۱:۰۰ تا ۰۸:۳۰ تهران)؛ خبری منتشر نمی‌شه.")
            return

    run_tg = not only_night and (force or now - state.get("last_tg", 0) >= (TG_EVERY_MIN - SLACK_MIN) * 60)
    run_other = not only_night and (force or now - state.get("last_other", 0) >= (OTHER_EVERY_MIN - SLACK_MIN) * 60)

    print(f"run: event={os.environ.get('GITHUB_EVENT_NAME')} mode={os.environ.get('RUN_MODE')} "
          f"tehran={th:%H:%M} force={force} run_tg={run_tg} run_other={run_other} only_night={only_night}")
    if not (run_tg or run_other or only_night):
        since = (now - state.get("last_tg", 0)) / 60
        print(f"هنوز موقع اجرا نیست ({since:.0f} دقیقه از آخرین نوبت کانال‌ها گذشته).")
        return

    prepare_proxies()
    seen = dict.fromkeys(state["seen"])   # ترتیب حفظ می‌شه
    seeded = set(state["seeded"])
    recent = [t for t in state["titles"] if now - t["t"] < DEDUP_HOURS * 3600]
    recent_sets = [set(t["k"]) for t in recent]
    kept_sets, to_post = [], []

    # ---- کیوسک خبر: فقط پیام‌های مشخص
    pre, post = [], []
    morning_time = MORNING_FROM <= m < MORNING_TO
    night_time = NIGHT_FROM <= m < NIGHT_END
    pending_morning = morning_time and not (ks["morning"] and ks["summary"])
    kposts = []
    try:
        kposts = fetch_kiosk(8 if pending_morning else 3 if night_time else 2)
    except Exception as ex:
        print("kiosk error:", ex)

    def pick(kind, max_hours):
        c = [p for p in kposts if p["sp"] == kind and p["id"] not in seen and now - p["ts"] <= max_hours * 3600]
        return max(c, key=lambda x: x["ts"]) if c else None

    if not only_night:
        if morning_time and not ks["morning"]:
            p = pick("morning", 14)
            if p:
                pre.append(("morning", p))
        if morning_time and not ks["summary"]:
            p = pick("summary", 14)
            if p and (ks["morning"] or pre or m >= SUMMARY_WAIT_UNTIL):
                pre.append(("summary", p))
        for p in sorted([p for p in kposts if p["sp"] == "papers" and p["id"] not in seen
                         and now - p["ts"] <= PAPERS_MAX_AGE_H * 3600], key=lambda x: x["ts"]):
            pre.append(("papers", p))
    if night_time and not ks["night"]:
        p = pick("night", 6)
        if p:
            post.append(("night", p))

    # ---- بقیه‌ی منابع
    tg_feeds = [f for f in FEEDS if f[1].startswith("tg:")]
    other_feeds = [f for f in FEEDS if not f[1].startswith("tg:")]

    if run_tg:
        cands = collect(tg_feeds, seen, seeded, seed_n=TG_MAX_POSTS)
        n = random.randint(TG_MIN_POSTS, TG_MAX_POSTS)
        chosen = choose(cands, n, seen, recent_sets, kept_sets)
        print(f"کانال‌های تلگرامی: {len(cands)} خبر تازه، {len(chosen)} تا انتخاب شد (سقف {n})")
        to_post += chosen
        state["last_tg"] = now

    if run_other:
        cands = collect(other_feeds, seen, seeded, seed_n=1)
        dom = sorted([i for i in cands if i["domestic"]], key=lambda x: -x["ts"])
        keep_dom = dom[:MAX_DOMESTIC_PER_RUN] if random.random() < DOMESTIC_CHANCE else []
        for i in dom:
            if i not in keep_dom:
                seen[i["id"]] = None
        pool = [i for i in cands if not i["domestic"]] + keep_dom
        chosen = choose(pool, OTHER_MAX_POSTS, seen, recent_sets, kept_sets)
        print(f"بقیه‌ی منابع: {len(pool)} خبر تازه، {len(chosen)} تا انتخاب شد")
        to_post += chosen
        state["last_other"] = now

    started = time.time()
    try:
        for kind, p in pre:
            run_special(kind, p, seen, ks)
            time.sleep(3)

        for item in sorted(to_post, key=lambda x: x["ts"]):
            if time.time() - started > RUN_BUDGET_SEC:
                print("زمان این اجرا تموم شد؛ بقیه‌ی خبرها نوبت بعد.")
                break
            if send(item):
                seen[item["id"]] = None
                recent.append({"t": time.time(), "k": sorted(item["tok"])})
                print("posted:", item["title"][:60])
            time.sleep(3)

        for kind, p in post:
            run_special(kind, p, seen, ks)
    except Exception as ex:   # هر خطایی بیاد، حافظه ذخیره می‌شه تا خبر تکراری نره
        print("خطا در ارسال:", repr(ex))
    finally:
        state["seen"] = list(seen)
        state["seeded"] = list(seeded)
        state["titles"] = recent[-400:]
        state["kiosk"] = ks
        save_state(state)

if __name__ == "__main__":
    main()
