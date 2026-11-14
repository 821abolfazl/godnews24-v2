import os
import sys
import re
import calendar
import json
import html
import time
from datetime import datetime, timedelta, timezone
import random
import socket
import requests
from urllib.parse import urlparse, parse_qs, unquote
import feedparser

# ====== تنظیمات ======
BOT_VERSION = "2026-11-13-r"   # توی لاگ و /status نوشته می‌شه تا معلوم باشه کدوم نسخه در حال اجراست
try:
    sys.stdout.reconfigure(line_buffering=True)   # لاگ همون لحظه توی گیت‌هاب دیده بشه
except Exception:
    pass
TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.environ.get("CHANNEL", "@GodNews24")

# لینک پروکسی (مثلاً https://t.me/proxy?server=...&port=...&secret=...)
PROXY_LINK = ""          # لینک پیش‌فرض (اگه فایل پروکسی خالی بود)
PROXY_FILE = "proxies.txt"  # هر خط یک لینک پروکسی
ALIVE = []               # پروکسی‌های سالمِ همین اجرا
RULES_FILE = "rules.txt"  # قوانین قابل ویرایش (ممنوع، ایموجی‌ها، پاک‌شدن از آخر متن)
LAST_TG_IDS = []  # message_idهای آخرین ارسال موفق تلگرام در همین فراخوان tg()
DYNAMIC_RULES = {"blocked": ["خوشچشم", "عوستاد", "رائفیپور", "رایفیپور", "عرزشی"], "red": ["سپاه", "ترامپ", "رویترز"], "yellow": ["بورس", "کریپتو"], "blue": ["کنکور", "مدرسه", "بنزین"], "strip_end": ["/ ایسنا", "| صداوسیما"]}
DYNAMIC_RULES_PREV = None  # نسخه‌ی قبلی قوانین، برای ایمنی
RULES_BLOCKED_SUSPENDED = [False]

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


def _word_pat(w):
    parts = (w or "").strip().split()
    return r"[\s\u200c]*".join(re.escape(x) for x in parts) if parts else ""

def _dyn_re(kind):
    words = [w for w in DYNAMIC_RULES.get(kind, []) if len((w or "").strip()) >= 3]
    if not words:
        return None
    try:
        return rx(*[_word_pat(w) for w in words])
    except Exception:
        return None

def _dyn_match(kind, text):
    r = _dyn_re(kind)
    return bool(r and r.search(text or ""))

def pick_emoji(category, title, body=""):
    # ورزشی و فناوری و معمولی: 🔵
    if category in ("sports", "tech") or any(k in title for k in SPORT_KW):
        return "🔵"
    full = title + " " + body
    # کلمه‌های اجباری: اگه توی تیتر باشه 🔴 اول، بعد 🟡؛ اگه فقط توی متن باشه 🟡 اول، بعد 🔴
    if RED_RE.search(title) or _dyn_match("red", title):
        return "🔴"
    if YELLOW_RE.search(title) or YELLOW_RE.search(full) or _dyn_match("yellow", title) or _dyn_match("yellow", full):
        return "🟡"
    if RED_RE.search(full) or _dyn_match("red", full):
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
SRC = (r"(?:CNN|سی\s?ان\s?ان|شبکه\s?(?:خبری\s?)?کان|صابرین\s?نیوز|المیادین|نیویورک\s?تایمز|آکسیوس|فاکس\s?نیوز|سی\s?بی\s?اس|وال\s?استریت(?:\s?ژورنال)?|فایننشال\s?تایمز|اینترفکس|العربیه|الجزیره|الجزایر|کانال\s?(?:۱۴|14)(?:\s?اسرائیل)?|ایسنا|مهر|ایرنا|تسنیم|فارس|مشرق|تابناک|خبرآنلاین|خبر\s?آنلاین|همشهری|ایلنا|ایکنا|"
       r"جماران|انتخاب|عصر\s?ایران|یورونیوز|دویچه[\s‌]?وله|DW|ورزش\s?(?:۳|3|سه)|دیجیاتو|زومیت|"
       r"دنیای\s?اقتصاد|اقتصادنیوز|اکوایران|تجارت\s?نیوز|باشگاه\s?خبرنگاران(?:\s?جوان)?|"
       r"خبرگزاری\s?صدا\s?و\s?سیما|BBC|رویترز|AFP|آسوشیتدپرس|AP)")
AG = r"(?:خبرگزاری\s+|پایگاه\s+خبری\s+|سایت\s+|روزنامه\s+|خبرنگار\s+|سرویس\s+\S+\s+)?"

SOURCE_RULES = [
    re.compile(r"\s*/\s*ایسنا(?=[\s.،]*$)"),   # «... / ایسنا» آخر متن: فقط همین کلمه پاک می‌شه (نقطه‌ی بعدش می‌مونه)
    re.compile(r"(?:به\s+گزارش|به\s+نقل\s+از|بنا\s?بر\s+گزارش|طبق\s+گزارش|بر\s?اساس\s+گزارش)\s+"
               + AG + SRC + r"[\s،,:؛\-–—]*"),
    re.compile(r"(?:خبرنگار|خبرگزاری)\s+" + SRC + r"[\s،,:؛\-–—]*"),
    re.compile(r"^\s*" + AG + SRC + r"\s*[:\-–—ـ]\s*"),
    re.compile(r"[\(\[]\s*" + AG + SRC + r"\s*[\)\]]"),
    re.compile(r"\s*[|\-–—]\s*" + AG + SRC + r"\s*$"),
    re.compile(r"(?:منبع\s*:|انتهای\s+پیام|ادامه\s+مطلب|بیشتر\s+بخوانید).*$", re.S),
    re.compile(r"https?://\S+"),
]


SEDAVASIMA_END_RE = re.compile(r"\s*\|\s*صداوسیما\s*[.،]?\s*$")

def strip_trailing_sedavasima(text):
    """فقط «| صداوسیما» آخر متن رو پاک می‌کنه؛ وسط متن دست نمی‌خوره."""
    return SEDAVASIMA_END_RE.sub("", text or "")

def apply_dynamic_strip_end(text):
    """عبارت‌های [پاک شود از آخر متن] فقط اگه آخر متن باشن پاک می‌شن."""
    for phrase in list(DYNAMIC_RULES.get("strip_end", [])):
        ph = (phrase or "").strip()
        if len(ph) < 3:
            continue
        t = (text or "").rstrip(" \t\n.,،؛")
        if t.endswith(ph):
            text = t[:-len(ph)].rstrip(" \t\n.,،؛-–—|")
    return text

def strip_sources(text):
    text = strip_trailing_sedavasima(text or "")
    for rule in SOURCE_RULES:
        text = rule.sub("", text)
    text = strip_trailing_sedavasima(text)
    text = apply_dynamic_strip_end(text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" \n\t،,:؛-–—")


def clean(text, limit):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = strip_sources(text.strip())
    if len(text) > limit:
        # برش تیتر بدون «…»؛ از مرز کلمه کوتاه می‌شه
        text = text[:limit].rsplit(" ", 1)[0]
    return text


def clean_paras(raw, limit=12000):
    """متن رو به پاراگراف‌های تمیز (بدون منبع) تبدیل می‌کنه.
    نسخه‌ی h: سقف از ۳۲۰۰ به ۱۲۰۰۰ رفت و دیگه هیچ پاراگرافی نصفه با «…»
    بریده نمی‌شه؛ اگه متن از سقف رد شد، فقط از مرز پاراگراف متوقف می‌شه.
    خبرهای معمولیِ این منابع عملاً زیر ۱۲۰۰۰ کاراکترن و کامل می‌رسن."""
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw or "")
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    paras, total = [], 0
    for line in text.split("\n"):
        line = strip_sources(line.strip())
        if len(line) < 6:
            continue
        if total + len(line) > limit:
            break   # پاراگراف نصفه اضافه نمی‌شه، «…» هم گذاشته نمی‌شه
        paras.append(line)
        total += len(line)
    return paras


# ====== نفت و پرچم کشورها ======
def is_oil_price(title):
    has_oil = any(k in title for k in ["نفت", "برنت", "WTI"])
    has_price = any(k in title for k in ["قیمت", "نرخ", "بشکه", "برنت", "WTI", "دلاری"])
    return has_oil and has_price


_L = "\u0621-\u063A\u0641-\u064A\u064B-\u0652\u0671-\u06D3\u06D5\u06F0-\u06F9\u200c"   # فقط حرف؛ ویرگول و نقطه‌ویرگول فارسی حرف حساب نمی‌شن


def rx(*alts, suffix=True):
    """عبارت‌های فارسی رو با مرز کلمه (و پسوندهای ی، ها، ان) تطبیق می‌ده؛ مثلاً «جنگل» جنگ حساب نمی‌شه."""
    pat = "|".join(alts)
    sfx = r"(?:\u200c?(?:های|ها|یی|ایی|ای|ی|یان|ان))?" if suffix else ""
    return re.compile(rf"(?<![{_L}])(?:{pat}){sfx}(?![{_L}])", re.I)


COUNTRIES = {
    "IR": ["ایران"], "US": ["آمریکا", "امریکا", "ایالات متحده", "واشنگتن", "پنتاگون", "کاخ سفید"],
    "RU": ["روسیه", "روس", "مسکو", "کرملین"], "CN": ["چین", "پکن"],
    "IL": ["اسرائیل", "اسراییل", "تل آویو", "تل‌آویو"], "IQ": ["عراق", "بغداد"],
    "TR": ["ترکیه", "آنکارا"], "SA": ["عربستان", "ریاض"], "AE": ["امارات", "ابوظبی", "دبی"],
    "QA": ["قطر", "دوحه"], "KW": ["کویت"], "BH": ["بحرین", "منامه"], "OM": ["عمان", "مسقط"],
    "LB": ["لبنان", "بیروت"], "SY": ["سوریه", "دمشق"], "YE": ["یمن", "صنعا"],
    "PS": ["فلسطین", "غزه", "کرانه باختری"], "JO": ["اردن"], "EG": ["مصر", "قاهره"],
    "LY": ["لیبی"], "DZ": ["الجزایر"], "MA": ["مراکش"], "TN": ["تونس"], "SD": ["سودان"],
    "AF": ["افغانستان", "کابل"], "PK": ["پاکستان", "اسلام آباد", "اسلام‌آباد"],
    "IN": ["هند", "دهلی نو", "دهلی"], "BD": ["بنگلادش"], "JP": ["ژاپن", "توکیو"],
    "KR": ["کره جنوبی", "سئول"], "KP": ["کره شمالی", "پیونگ یانگ", "پیونگ‌یانگ"],
    "TW": ["تایوان", "تایپه"], "VN": ["ویتنام"], "ID": ["اندونزی"], "MY": ["مالزی"],
    "TH": ["تایلند"], "PH": ["فیلیپین"], "SG": ["سنگاپور"], "AU": ["استرالیا"],
    "NZ": ["نیوزیلند"], "CA": ["کانادا"], "MX": ["مکزیک"], "BR": ["برزیل"],
    "AR": ["آرژانتین"], "VE": ["ونزوئلا", "کاراکاس"], "CU": ["کوبا", "هاوانا"],
    "CO": ["کلمبیا"], "CL": ["شیلی"], "DE": ["آلمان", "برلین"],
    "FR": ["فرانسه", "فرانسوی", "پاریس"], "GB": ["انگلیس", "انگلستان", "بریتانیا", "لندن"],
    "IT": ["ایتالیا"], "ES": ["اسپانیا", "مادرید"], "PT": ["پرتغال"], "NL": ["هلند"],
    "BE": ["بلژیک"], "CH": ["سوئیس"], "AT": ["اتریش"], "SE": ["سوئد"], "NO": ["نروژ"],
    "DK": ["دانمارک"], "FI": ["فنلاند"], "PL": ["لهستان", "ورشو"],
    "UA": ["اوکراین", "کی یف", "کی‌یف", "کییف"], "BY": ["بلاروس"], "RO": ["رومانی"],
    "HU": ["مجارستان"], "GR": ["یونان"], "RS": ["صربستان"], "AM": ["ارمنستان"],
    "AZ": ["جمهوری آذربایجان", "آذربایجان"], "GE": ["گرجستان"], "KZ": ["قزاقستان"],
    "UZ": ["ازبکستان"], "TM": ["ترکمنستان"], "TJ": ["تاجیکستان"], "KG": ["قرقیزستان"],
    "ZA": ["آفریقای جنوبی"], "NG": ["نیجریه"], "ET": ["اتیوپی"], "KE": ["کنیا"],
    "SO": ["سومالی"], "IE": ["ایرلند"], "IS": ["ایسلند"], "NP": ["نپال"],
    "LK": ["سریلانکا"], "MM": ["میانمار"], "KH": ["کامبوج"], "CY": ["قبرس"],
    "BG": ["بلغارستان"], "HR": ["کرواسی"], "PA": ["پاناما"], "SK": ["اسلواکی"],
    "SI": ["اسلوونی"], "LT": ["لیتوانی"], "LV": ["لتونی"], "EE": ["استونی"],
    "MN": ["مغولستان"], "LA": ["لائوس"],
}
COUNTRY_RE = []
for _code, _names in COUNTRIES.items():
    _alt = [r"[\s\u200c]*".join(re.escape(w) for w in n.split()) for n in sorted(_names, key=len, reverse=True)]
    COUNTRY_RE.append((_code, rx(*_alt)))
EU_RE = rx("اتحادیه[\\s\u200c]*اروپا", "اروپا")
NOT_COUNTRY = ["ایران خودرو", "ایران‌خودرو", "ایرانخودرو", "دریای عمان", "اقیانوس هند",
               "آذربایجان شرقی", "آذربایجان غربی", "خلیج فارس", "تنگه هرمز", "روس‌تا"]
FLAG_FILLERS = {"فوری", "عاجل", "خبر", "آخرین", "مهم", "جدید", "اختصاصی", "ویدیو", "ویدئو", "عکس", "تصاویر", "گزارش"}
FLAG_WORDS = 8   # کشور باید توی ۸ کلمه‌ی اولِ تیتر باشه (بعد از حذف کلمه‌های «فوری»، «خبر» و مانند اون)


def flag_of(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def flags_for(title, limit=3):
    if re.search("[\U0001F1E6-\U0001F1FF]", title):
        return ""  # خودش پرچم داره
    t = title.replace("ي", "ی").replace("ك", "ک").replace("#", " ").replace("_", " ")
    for bad in NOT_COUNTRY:
        t = t.replace(bad, " ")
    words = [w.strip(":،؛-–—|!؟?.«»\"'()") for w in t.split()]
    words = [w for w in words if w]
    while words and words[0] in FLAG_FILLERS:
        words.pop(0)
    s8, s6 = " ".join(words[:FLAG_WORDS]), " ".join(words[:6])
    found = []
    for code, rxc in COUNTRY_RE:
        m = rxc.search(s8)
        if m:
            found.append((m.start(), code))
    m = EU_RE.search(s6)   # اروپا فقط توی ۶ کلمه‌ی اول
    if m:
        found.append((m.start(), "EU"))
    found.sort()
    out = []
    for _, code in found:
        if code not in out:
            out.append(code)
    return "".join(flag_of(c) for c in out[:limit])


# ====== کلمه‌های اجباری، منبع‌های 🔴 و شخص‌ها ======
RED_RE = rx("جنگ", "سپاه", "ترامپ", r"کمیسیون[\s\u200c]+امنیت[\s\u200c]+ملی", r"رضا[\s\u200c]*پهلوی", r"تریتا[\s\u200c]*(?:پارسی|فارسی)", r"Trita[\s\u200c]*Parsi", "عراقچی", "Araghchi",
            r"سخنگوی[\s\u200c]+وزارت[\s\u200c]+(?:امور[\s\u200c]+)?خارجه", "بقایی",
            r"لحظات[\s\u200c]+اولیه[\s\u200c]+هدف[\s\u200c]+قرار[\s\u200c]+گرفت(?:ن)?",
            "هگست", "هگسث", "هیگست", "روبیو")
YELLOW_RE = re.compile(rf"(?<![{_L}])(?:بورس|فارکس|ارز(?:ها|های)?[\s\u200c]*دیجی?تال|کریپتو|رمز[\s\u200c]*ارز)")
RED_SRC_RE = rx(r"پست[\s\u200c]*واشنگتن", r"واشنگتن[\s\u200c]*پست", r"Washington[\s\u200c]*Post", "الجزایر", "الجزیره", r"فاکس[\s\u200c]*نیوز", r"Fox[\s\u200c]*News", r"کانال[\s\u200c]*(?:۱۴|14)",
                r"سی[\s\u200c]*بی[\s\u200c]*اس", "CBS", r"وال[\s\u200c]*استریت(?:[\s\u200c]*ژورنال)?",
                r"Wall[\s\u200c]*Street[\s\u200c]*Journal", "WSJ", r"فایننشال[\s\u200c]*تایمز",
                r"Financial[\s\u200c]*Times", "اینترفکس", "Interfax", "العربیه", r"Al[\s\u200c-]*Arabiya",
                r"صابرین[\s\u200c]*نیوز", "المیادین", r"نیویورک[\s\u200c]*تایمز", r"New[\s\u200c]*York[\s\u200c]*Times",
                "آکسیوس", "Axios", r"محسن[\s\u200c]*رضایی",
                r"سی[\s\u200c]*ان[\s\u200c]*ان", "CNN", r"شبکه[\s\u200c]*(?:خبری[\s\u200c]*)?کان",
                r"کان[\s\u200c]*(?:اسرائیل|اسراییل)", "رویترز", "Reuters", suffix=False)
PERSON_FLAGS = [
    (rx("نتانیاهو", "نتنیاهو", r"نتن[\s\u200c]*یاهو"), "IL"),
    (rx(r"کاخ[\s\u200c]*سفید"), "US"),
    (rx("زلنسکی", "زلینسکی", "زیلنسکی"), "UA"),
    (rx("پوتین"), "RU"),
]

# ====== موضوع‌ها ======
HOUSING_RE = rx("مسکن", "آپارتمان", "رهن", r"اجاره(?:[\s\u200c]*بها)?", "املاک")
PLANE_RE = rx("هواپیما")
DRUG_RE = rx("دارو", "داروخانه", "داروسازی", "داروساز")
FOOT_STRONG_RE = rx("فوتبال", "فوتبالیست", r"لیگ[\s\u200c]*برتر", r"لیگ[\s\u200c]*قهرمانان", r"جام[\s\u200c]*جهانی",
                    "پرسپولیس", r"رئال[\s\u200c]*مادرید", "بارسلونا", "لیورپول", r"منچستر[\s\u200c]*(?:یونایتد|سیتی)",
                    "بایرن", "آرسنال", "چلسی", "یوونتوس", r"پاری[\s\u200c]*سن[\s\u200c]*ژرمن")
FOOT_CLUB_RE = rx("استقلال", "سپاهان", "تراکتور", r"ذوب[\s\u200c]*آهن", "پیکان", "نساجی", r"گل[\s\u200c]*گهر")
FOOT_CTX_RE = rx("تیم", "بازی", "لیگ", "گل", "باشگاه", "سرمربی", "مهاجم", "هافبک", r"دروازه[\s\u200c]*بان", "داور", "فصل")
MOBILE_RE = rx("موبایل", "گوشی", "آیفون", "iPhone", "سامسونگ", "شیائومی", "گلکسی", "پیکسل", "هواوی", "ردمی",
               r"تلفن[\s\u200c]*همراه")
PETROL_RE = rx("بنزین")
FOOD_RE = rx("شیر", "گوشت", "دام", "مرغ", r"تخم[\s\u200c]*مرغ", "لبنیات", r"مواد[\s\u200c]*غذایی",
             r"مواد[\s\u200c]*اولیه", "پنیر", "ماست")
PRICE_CTX_RE = rx("قیمت", "نرخ", "گران", "ارزان", "تومان", "ریال", "گرانی")
DOLLAR_PRICE_RE = re.compile(r"(?:قیمت|نرخ)[\s\u200c]*(?:امروز[\s\u200c]*)?دلار|دلار[^\n]{0,40}تومان|دلار[\s\u200c]*(?:آزاد|امروز|بازار)")
OTHER_CUR_RE = rx("یورو", "سکه", "طلا", "درهم", "پوند", "تتر", r"بیت[\s\u200c]*کوین", "لیر", "دینار", "یوان", "روبل",
                  "نفت", "برنت", "بورس")
WEATHER_RE = rx("هواشناسی", r"پیش[\s\u200c]*بینی[\s\u200c]*هوا", r"وضعیت[\s\u200c]*جوی", r"آب[\s\u200c]*و[\s\u200c]*هوا",
                r"دمای[\s\u200c]*هوا", "بارش", "بارندگی", "باران", "رگبار", "برف", r"رعد[\s\u200c]*و[\s\u200c]*برق",
                "آفتابی", "ابری", "یخبندان", r"گرد[\s\u200c]*و[\s\u200c]*خاک")


EDU_RE = rx(r"وزیر[\s\u200c]*علوم", "کنکور", "مدرسه", "مدارس")
CIVIL_RE = rx("گواهینامه", r"گواهی[\s\u200c]*نامه", r"کارت[\s\u200c]*سوخت", r"تعویض[\s\u200c]*پلاک", "کالابرگ", r"کالا[\s\u200c]*برگ")
AIR_RE = rx("پهپاد", "موشک", "هواپیما", "جنگنده", "بالگرد", r"هلی[\s\u200c]*کوپتر")
MISSILE_DRONE_RE = rx("پهپاد", "موشک")
DOWN_RE = rx("سرنگون", "سرنگونی", "ساقط")
BLAST_RE = rx("انفجار", "منفجر", "اصابت")


def has_strike_event(head):
    """سرنگونی پهپاد/هواپیما، یا انفجار و اصابت موشک/پهپاد."""
    d, a = DOWN_RE.search(head), AIR_RE.search(head)
    if d and a:
        return True
    b, m = BLAST_RE.search(head), MISSILE_DRONE_RE.search(head)
    return bool(b and m)


FRUIT_RE = rx("میوه", "سیب", "پرتقال", "نارنگی", "موز", "هندوانه", "خربزه", "طالبی", "انار", "انگور", "گلابی",
              "هلو", "زردآلو", "شلیل", "گیلاس", "کیوی", "لیمو", "انجیر", "خرما", "توت", "آناناس", "انبه", "آلو")
BET_RE = rx(r"شرط[\s\u200c]*بندی", r"شرط[\s\u200c]*بند", "کازینو", "بتینگ", "betting", "1xbet", r"وان[\s\u200c]*ایکس[\s\u200c]*بت",
            "ملبت", "melbet", r"پین[\s\u200c]*آپ", r"pin[\s\u200c-]*up", r"بت[\s\u200c]*فا", "بتفا", r"بت[\s\u200c]*(?:۹۰|90)",
            "bet90", "رولت", "پوکر", r"سایت[\s\u200c]*(?:های[\s\u200c]*)?شرط", r"سایت[\s\u200c]*بت", r"ضریب[\s\u200c]*شرط",
            "بونوس", suffix=False)
BET_LATIN_RE = re.compile(r"(?<![A-Za-z0-9])bet(?![A-Za-z])", re.I)
# تبلیغ فیلترشکن/کانفیگ/اینترنت ملی (ته پست پاک می‌شه)
VPN_PROMO_RE = re.compile(r"فیلتر[\s\u200c]*شکن|اینترنت[\s\u200c]*ملی|نت[\s\u200c]*ملی|کانفیگ|کانفینگ|v2ray|vpn|وی[\s\u200c]*پی[\s\u200c]*ان|پروکسی", re.I)
STRONG_PROMO_RE = re.compile(r"فیلتر[\s\u200c]*شکن|کانفیگ|کانفینگ|v2ray|vpn|وی[\s\u200c]*پی[\s\u200c]*ان|پروکسی", re.I)


def is_betting(text):
    return bool(BET_RE.search(text) or BET_LATIN_RE.search(text))


CAR_WORD_RE = rx(r"ایران[\s\u200c]*خودرو", "خودرو", "خودروساز", "خودروسازی", "ماشین", "پراید", "پژو", "تیبا", "سمند", "ساینا", "کوییک", "سورن",
                 "هایما", "چانگان", "چری", "MVM", r"ام[\s\u200c]*وی[\s\u200c]*ام", "کیا", "هیوندای", "تویوتا", "مزدا",
                 "نیسان", "رنو", r"بی[\s\u200c]*ام[\s\u200c]*و", "مرسدس", "تسلا", "فورد", "شورولت", "هوندا", "پورشه",
                 "فراری", "سایپا")
CAR_EXCL_RE = rx(r"ماشین[\s\u200c]*آلات", r"ماشین[\s\u200c]*لباسشویی", r"ماشین[\s\u200c]*ظرفشویی", r"ماشین[\s\u200c]*حساب")
CAR_CTX_RE = rx("تولید", "فروش", "قیمت", "خرید", "بازار", "عرضه", "واردات", "صادرات", r"پیش[\s\u200c]*فروش",
                r"قرعه[\s\u200c]*کشی", r"ثبت[\s\u200c]*نام", "گران", "ارزان", "تومان", "نرخ", "تیراژ")
POLITICAL_RE = rx(r"رئیس[\s\u200c]*جمهور", "مذاکره", "مذاکرات", "تحریم", "انتخابات", r"شورای[\s\u200c]*امنیت", "نظامی",
                  "ارتش", "ناتو", "مجلس", "کنگره", "پارلمان", "سفیر", "دیپلمات", r"آتش[\s\u200c]*بس", "وزیر",
                  r"نخست[\s\u200c]*وزیر", "پدافند", "اعدام", "بازداشت")
POLITICAL_SKIP_CHANNELS = {"arz_talaaa"}   # این کانال‌ها خبر سیاسی نمی‌دن


def is_car_post(head, full):
    return bool(CAR_WORD_RE.search(head) and not CAR_EXCL_RE.search(head) and CAR_CTX_RE.search(full))


def is_political(head):
    return bool(POLITICAL_RE.search(head) or RED_RE.search(head)
                or any(prx.search(head) for prx, _ in PERSON_FLAGS) or has_strike_event(head))


def weather_emoji(t):
    def has(p):
        return re.search(p, t) is not None
    if has(r"رعد|صاعقه|تندر"):
        return "⛈️"
    if has(r"برف|بوران|کولاک|یخبندان"):
        return "🌨️"
    if has(r"نیمه[\s\u200c]*ابری|ابر[\s\u200c]*و[\s\u200c]*آفتاب|گاهی[\s\u200c]*ابری"):
        return "⛅️"
    if has(r"رگبار|پراکنده|بارانی[\s\u200c]*و[\s\u200c]*آفتابی"):
        return "🌦️"
    if has(r"باران|بارش|بارندگی|سیل"):
        return "🌧️"
    if has(r"ابری|ابرناک|مه[\s\u200c]*آلود|گرد[\s\u200c]*و[\s\u200c]*خاک"):
        return "🌥️"
    return "🌤️"


def is_football(head, category):
    if FOOT_STRONG_RE.search(head):
        return True
    return bool(FOOT_CLUB_RE.search(head) and (FOOT_CTX_RE.search(head) or category == "sports"))


MARKER = {"🔴": "🔻", "🟡": "🔸", "🔵": "🔹"}


def decide(item):
    """ایموجی اول متن و علامت پاراگراف‌ها رو تعیین می‌کنه. اول متن فقط یک ایموجی (یا چند پرچم)."""
    title = item["title"]
    paras = item.get("paras") or []
    summary = item.get("summary", "")
    head = title + " " + (paras[0] if paras else "")
    full = title + " " + summary
    cls = pick_emoji(item["category"], title, summary)
    if is_oil_price(title):
        return "🛢️", MARKER["🟡"]
    if HOUSING_RE.search(head):
        return "🏘️", MARKER["🟡"]
    if has_strike_event(head):
        return "🔴", MARKER["🔴"]
    if is_car_post(head, full):
        return "🚙", MARKER["🟡"]
    if PLANE_RE.search(" ".join(title.split()[:6])):
        return "✈️", MARKER[cls]
    if DRUG_RE.search(head):
        return "💊", MARKER[cls]
    if is_football(head, item["category"]):
        return "⚽", MARKER["🔵"]
    # شخص‌ها و کلمه‌های 🔴: هر کدوم که توی تیتر/بند اول زودتر اومده
    cands = []
    for prx, code in PERSON_FLAGS:
        m = prx.search(head)
        if m:
            cands.append((m.start(), flag_of(code)))
    m = RED_RE.search(head)
    if m:
        cands.append((m.start(), "🔴"))
    if cands:
        return min(cands)[1], MARKER["🔴"]
    if item.get("red_src") or RED_RE.search(full) or RED_SRC_RE.search(full) or _dyn_match("red", full):
        return "🔴", MARKER["🔴"]
    if YELLOW_RE.search(full) or _dyn_match("yellow", full):
        return "🟡", MARKER["🟡"]
    if _dyn_match("blue", full):
        return "🔵", MARKER["🔵"]
    if PETROL_RE.search(full) or CIVIL_RE.search(full) or EDU_RE.search(full) or (
            (FOOD_RE.search(head) or FRUIT_RE.search(head)) and PRICE_CTX_RE.search(full)):
        return "🔵", MARKER["🔵"]
    if MOBILE_RE.search(head):
        return "📱", MARKER["🔵"]
    if DOLLAR_PRICE_RE.search(head) and not OTHER_CUR_RE.search(full):
        return "💵", MARKER["🟡"]
    if WEATHER_RE.search(head):
        return weather_emoji(head), MARKER["🔵"]
    flags = flags_for(title)
    if flags:
        return flags, MARKER[cls]
    return cls, MARKER[cls]


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
BLOCKED_WORDS = ["خوشچشم", "عوستاد", "رائفیپور", "رایفیپور", "عرزشی"]

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
CHANNEL_BLOCKED = {}


def is_blocked(text, extra=()):
    key = re.sub(r"[\s\u200c_\-]", "", text)
    words = [re.sub(r"[\s\u200c_\-]", "", w) for w in list(BLOCKED_WORDS) + list(DYNAMIC_RULES.get("blocked", [])) + list(extra)]
    if any(w and w in key for w in words):
        return True
    # تطبیق با مرز کلمه برای کلمه‌های پویا
    try:
        r = _dyn_re("blocked")
        if r and r.search(text or ""):
            return True
    except Exception:
        pass
    return False


def looks_like_joke(raw):
    return any(ch in raw for ch in JOKE_EMOJIS) or bool(JOKE_RE.search(raw))


def has_word(text, w):
    return re.search(rf"(?<![{_L}])" + re.escape(w) + rf"(?![{_L}])", text) is not None


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


CHANNEL_SKIP_FROM, CHANNEL_SKIP_TO = 1 * 60, 6 * 60   # پست‌هایی که بین ۰۱:۰۰ تا ۰۶:۰۰ تهران منتشر شدن (از همه‌ی منبع‌ها) ارسال نمی‌شن


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
    h_orig = h
    h = re.sub(rf"#[\w{_L}]+", "", h)
    out = []
    for line in h.split("\n"):
        line = re.sub(r"[ \t]{2,}", " ", line).strip()
        line = re.sub(r"[ \t]+([،؛.!؟])", r"\1", line)        # فاصله‌ی اضافه قبل از ویرگول (بعد از حذف هشتگ)
        line = re.sub(r"^[\s،؛]+", "", line) if "#" in h_orig else line
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


# ====== فیلتر تبلیغ و پست‌های ممنوع کانال‌ها ======
CHANNEL_SKIP_WORDS = {"arz_talaaa": ["صبحبخیر", "شببخیر"]}   # بدون فاصله
GREETING_KEYS = ("صبحبخیر", "شببخیر", "صبحتونبخیر", "شبتونبخیر", "صبحشمابخیر", "شبشمابخیر", "صبحتانبخیر", "شبتانبخیر")


def is_greeting_post(text):
    """پیام صبح بخیر/شب بخیر (جز کیوسک) منتشر نمی‌شه. متن بلندِ خبری که فقط یک‌جا این عبارت رو داره حساب نمی‌شه."""
    key = re.sub(r"[\s\u200c_\-،,.!؟?؛:]+", "", text or "")
    pos = [key.find(g) for g in GREETING_KEYS if g in key]
    if not pos:
        return False
    return len(key) < 400 or min(pos) < 80

WATCH_LINK_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.S | re.I)
TRAIL_EMOJI_RE = re.compile("[" + EMOJI_CHARS + r"\s]+$")


_WAPO = r"(?:واشنگتن[\s\u200c]*پست|پست[\s\u200c]*واشنگتن|Washington[\s\u200c]*Post)"
WAPO_END_PATTERNS = [
    re.compile(r"^\s*(?:منبع\s*:?\s*)?" + _WAPO + r"\s*\.?\s*$", re.I),                                  # کل خط = منبع
    re.compile(r"\s*[\-\u2013\u2014|:(\[«]\s*(?:منبع\s*:?\s*)?" + _WAPO + r"\s*[)\]»]?\s*\.?\s*$", re.I),  # ... - واشنگتن پست
    re.compile(r"\s*(?:منبع\s*:|(?:به\s+نقل\s+از|به\s+گزارش|طبق\s+گزارش))\s*" + _WAPO + r"\s*\.?\s*$", re.I),  # منبع: ... / به نقل از ...
]


def strip_end_source(lines):
    """نام «واشنگتن پست» فقط وقتی به‌عنوان منبعِ آخر پست اومده پاک می‌شه؛ وسط متن دست‌نخورده می‌مونه."""
    lines = list(lines)
    if lines:
        lines[-1] = strip_trailing_sedavasima(lines[-1])
        lines[-1] = apply_dynamic_strip_end(lines[-1])
        if not lines[-1].strip():
            lines.pop()
            return lines
        t = lines[-1]
        for rxp in WAPO_END_PATTERNS:
            t = rxp.sub("", t)
        t = t.rstrip(" \t-\u2013\u2014|:،,")
        if t.strip():
            lines[-1] = t
        else:
            lines.pop()
    return lines


def has_watch_link(html_):
    """«مشاهده فیلم» که روش لینک گذاشته شده (معمولاً تبلیغ یا ارجاع به جای دیگه‌ست)."""
    for m in WATCH_LINK_RE.finditer(html_ or ""):
        t = re.sub(r"<[^>]+>|[\s\u200c]", "", m.group(1))
        if "مشاهدهفیلم" in t or "مشاهدهیفیلم" in t:
            return True
    return False


def has_signature(p, name):
    """امضای خود کانال (آیدی یا لینکش) باید توی چند خط آخر پست باشه؛ وگرنه تبلیغه."""
    h = re.sub(r"(?i)<br\s*/?>", "\n", p.get("html") or "")
    lines = [l for l in h.split("\n") if re.sub(r"<[^>]+>", "", l).strip()]
    tail = "\n".join(lines[-4:])
    n = re.escape(name)
    return bool(re.search(rf"(?i)@{n}(?![A-Za-z0-9_])|(?:t|telegram)\.me/{n}(?![A-Za-z0-9_])", tail))


def text_without_signature(p, name):
    """متن پست، بدون خط امضای خود کانال (مثل «🆔 @name» یا «کانال ما» که لینک کانال روشه)."""
    h = re.sub(r"(?i)<br\s*/?>", "\n", p.get("html") or "")
    lines = h.split("\n")
    n = re.escape(name)
    sig = re.compile(rf"(?i)@{n}(?![A-Za-z0-9_])|(?:t|telegram)\.me/{n}(?![A-Za-z0-9_])")
    nonempty = [i for i, l in enumerate(lines) if re.sub(r"<[^>]+>", "", l).strip()]
    drop = set()
    for i in nonempty[-4:]:
        plain = re.sub(r"<[^>]+>", "", lines[i]).strip()
        if sig.search(lines[i]) and len(plain) <= 60:
            drop.add(i)
    kept = [l for i, l in enumerate(lines) if i not in drop]
    return html.unescape(re.sub(r"<[^>]+>", "", "\n".join(kept)))


def trim_trailing_emoji(lines):
    lines = list(lines)
    while lines:
        t = TRAIL_EMOJI_RE.sub("", lines[-1]).rstrip()
        if t:
            lines[-1] = t
            break
        lines.pop()
    return lines


def fetch_tg(category, name, domestic):
    items = []
    posts = []
    skipped_night = 0
    ads = 0
    try:
        r = requests.get(f"https://t.me/s/{name}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        posts = parse_tg_page(r.text)
        print(f"tg:{name} http={r.status_code} bytes={len(r.text)} posts_with_text={len(posts)}")
        READ_STATUS[name] = len(posts)
        if not posts:
            print(f"  ! هیچ پستی خونده نشد: پیش‌نمایش عمومی کانال بسته‌ست یا دسترسی بلاکه (آیدی: {name})")
        for p in posts:
            raw = p["text"]
            if is_blocked(raw, CHANNEL_BLOCKED.get(name, ())):
                print("  blocked word, skipped:", raw[:40].replace("\n", " "))
                log_rejected(name, "کلمه‌ی ممنوع", raw, p["post_id"])
                continue
            if name in JOKE_CHANNELS and looks_like_joke(raw):
                print("  joke, skipped:", raw[:40].replace("\n", " "))
                log_rejected(name, "شبیه شوخی", raw, p["post_id"])
                continue
            key = re.sub(r"[\s\u200c_\-]", "", raw)
            if is_betting(raw):
                print("  betting ad, skipped:", raw[:30].replace("\n", " "))
                log_rejected(name, "تبلیغ شرط‌بندی", raw, p["post_id"])
                continue
            if is_greeting_post(raw) or any(w in key for w in CHANNEL_SKIP_WORDS.get(name, ())):
                print("  greeting post, skipped:", raw[:30].replace("\n", " "))
                log_rejected(name, "پیام صبح/شب بخیر (غیر از کیوسک)", raw, p["post_id"])
                continue
            if has_watch_link(p.get("html")):
                print("  'مشاهده فیلم' link, skipped:", raw[:30].replace("\n", " "))
                log_rejected(name, "لینک «مشاهده فیلم»", raw, p["post_id"])
                continue
            if not has_signature(p, name):
                ads += 1
                print("  ad (no channel signature), skipped:", raw[:30].replace("\n", " "))
                log_rejected(name, "تبلیغ: بدون امضای کانال", raw, p["post_id"])
                continue
            red_src = bool(RED_SRC_RE.search(raw))
            text = clean_tg(text_without_signature(p, name))
            lines = strip_end_source([l.strip() for l in text.split("\n") if l.strip()])
            # خط‌های تبلیغ فیلترشکن/کانفیگ/اینترنت ملی ته پست حذف می‌شه
            j = len(lines)
            while j > 0 and VPN_PROMO_RE.search(lines[j - 1]) and len(lines[j - 1]) <= 160:
                j -= 1        # خط‌های پشت‌سرهمِ آخر پست که شبیه تبلیغ هستن
            if j < len(lines) and any(STRONG_PROMO_RE.search(l) for l in lines[j:]):
                lines = lines[:j]   # فقط اگه واقعاً تبلیغ فیلترشکن/کانفیگ بود پاک می‌شه
            if not lines:
                print("  VPN promo only, skipped")
                log_rejected(name, "تبلیغ فیلترشکن/کانفیگ", raw, p["post_id"])
                continue
            text = "\n".join(lines)
            kind = detect_pricelist(lines)
            if kind:
                # لیست قیمت: ایموجی‌های داخل متن دست‌نخورده می‌مونه، فقط ایموجی اول عوض می‌شه
                title = clean(strip_leading_emoji(lines[0]), 200)
                paras = trim_trailing_emoji([x for x in (strip_sources(l) for l in lines[1:]) if x])
            else:
                text = strip_emoji(text)  # ایموجی‌های خود کانال حذف می‌شه
                lines = strip_end_source([l for l in text.split("\n") if l.strip()])
                if not lines or len(text) < 15:
                    continue
                rest = lines[1:]
                title = clean(lines[0], 200)
                if len(lines) > 1 and len(lines[0].split()) <= 2:   # مثلاً «فوری»: تیتر واقعی خط بعدیه
                    title = clean(lines[0] + " " + lines[1], 200)
                    rest = lines[2:]
                paras = [x for x in clean_paras("\n".join(rest), 12000) if x != title]
            if not title:
                continue
            if name in POLITICAL_SKIP_CHANNELS and not kind and is_political(title + " " + (paras[0] if paras else "")):
                print("  political post, skipped:", title[:40])
                log_rejected(name, "خبر سیاسی (از این کانال نمی‌خوای)", raw, p["post_id"])
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
                          "red_src": red_src, "src": name, "media": p["media"], "image": None, "video": None, "ts": ts})
    except Exception as ex:
        print("telegram channel error:", name, ex)
        READ_STATUS[name] = 0
    AD_STATS[name] = (ads, len(posts))
    items.sort(key=lambda x: x["ts"])
    print(f"{len(items):3d} items  tg:{name}" + (f"  ({skipped_night} پست ساعت ۰۱ تا ۰۶ رد شد)" if skipped_night else "")
          + (f"  ({ads} تبلیغ رد شد)" if ads else ""))
    return items


# ====== پست کوتاه برای همه‌ی خبرهای ایندیپندنت فارسی (نسخه‌ی o؛ قبلاً فقط علمی، نسخه‌ی k) ======
# فید این سایت به‌جای خلاصه، متن کامل مقاله (چند هزار کاراکتر) رو می‌ده؛ پس
# خبرهاش خیلی طولانی می‌شدن و عکس‌شون هم جدا از متن می‌رفت. همه‌ی خبرهاش کوتاه
# می‌شن (تیتر + شروع متن، تا ۶۰۰ کاراکتر) تا عکس و متن با هم در یک پست برن.


def _short_paras(paras, limit=600):
    """پست کوتاه: فقط پاراگراف‌های اول تا سقف کاراکتر؛ از مرز پاراگراف، بدون «…».
    اگه پاراگراف اولِ تنها از سقف رد شد، از مرز کلمه کوتاه می‌شه."""
    out, total = [], 0
    for p in paras:
        if total + len(p) <= limit:
            out.append(p)
            total += len(p)
        elif not out:
            cut = p[:limit].rsplit(" ", 1)[0]
            out.append(cut or p[:limit])
        else:
            break
    return out


def fetch_feed(category, url, domestic):
    if url.startswith("tg:"):
        return fetch_tg(category, url[3:], domestic)
    items = []
    night_skipped = 0
    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        for e in feed.entries:
            uid = e.get("id") or e.get("link")
            if not uid or not e.get("title"):
                continue
            title = clean(e.title, 200)
            if not title:
                continue
            if is_betting(title + " " + e.get("summary", "")):
                log_rejected(urlparse(url).netloc, "تبلیغ شرط‌بندی", title)
                continue
            if is_greeting_post(title + " " + e.get("summary", "")):
                log_rejected(urlparse(url).netloc, "پیام صبح/شب بخیر (غیر از کیوسک)", title)
                continue
            if "euronews" in url and (re.match(r"\s*مجله[\s\u200c]*خبری", title) or "mglh-khbri" in (e.get("link") or "")):
                continue   # «مجله خبری» یورونیوز منتشر نمی‌شه
            paras = strip_end_source([p for p in clean_paras(e.get("summary", ""), 12000) if p != title])
            # ایندیپندنت فارسی، همه‌ی خبرها: متن کامل مقاله‌ست، نه خلاصه؛ کوتاه
            # می‌شه تا عکس و متن با هم در یک پست (کپشن) برن، نه جدا از هم
            short_post = "independentpersian" in url
            if short_post:
                paras = _short_paras(paras, 600)
            summary = " ".join(paras)
            if len(summary) < 20:
                paras, summary = [], ""
            ts = calendar.timegm(e.published_parsed) if e.get("published_parsed") else 0
            if ts and in_skip_hours(ts):
                night_skipped += 1
                continue
            image, video = find_media(e)
            items.append({"id": uid, "title": title, "summary": summary, "paras": paras,
                          "category": category, "domestic": domestic, "image": image, "video": video, "ts": ts,
                          "src": urlparse(url).netloc, "short": short_post})
    except Exception as ex:
        print("feed error:", url, ex)
    RSS_READ[url] = len(items)
    items.sort(key=lambda x: x["ts"])
    print(f"{len(items):3d} items  {url}" + (f"  ({night_skipped} خبر ساعت ۰۱ تا ۰۶ رد شد)" if night_skipped else ""))
    return items


# ====== پروکسی‌ها ======
PROXY_INFO = {"total": 0, "checked": 0}


def fetch_remote_proxies():
    """لیست پروکسی رو هر بار تازه از گیت‌هاب می‌خونه (اجرای حلقه‌ای یک ساعت با نسخه‌ی قدیمیِ فایل کار می‌کرد)."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    try:
        r = requests.get(f"https://raw.githubusercontent.com/{repo}/{ref}/{PROXY_FILE}",
                         headers={"Cache-Control": "no-cache"}, timeout=15)
        if r.ok and r.text.strip():
            return r.text
    except requests.RequestException:
        pass
    return None


def load_proxies():
    text = fetch_remote_proxies()
    if text is None and os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, encoding="utf-8") as f:
            text = f.read()
    links = []
    for line in (text or "").splitlines():
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


def prepare_proxies(max_checks=150):
    """پروکسی‌ها رو هم‌زمان چک می‌کنه (سریع، تا ساعت‌های رایگان گیت‌هاب هدر نره). همه‌ی سالم‌ها استفاده می‌شن."""
    from concurrent.futures import ThreadPoolExecutor
    ALIVE.clear()
    links = load_proxies()
    random.shuffle(links)
    sample = links[:max_checks]
    if sample:
        with ThreadPoolExecutor(max_workers=20) as ex:
            ok = list(ex.map(proxy_alive, sample))
        ALIVE.extend(l for l, good in zip(sample, ok) if good)
    PROXY_INFO["total"], PROXY_INFO["checked"] = len(links), len(sample)
    print(f"proxies: {len(links)} in file, {len(sample)} checked, {len(ALIVE)} alive")


# ====== فایل قوانین قابل ویرایش (rules.txt) ======
RULES_SECTIONS = {"[ممنوع]": "blocked", "[blocked]": "blocked", "[🔴]": "red", "[red]": "red", "[🟡]": "yellow", "[yellow]": "yellow", "[🔵]": "blue", "[blue]": "blue", "[پاک شود از آخر متن]": "strip_end", "[strip_end]": "strip_end"}
RULES_SECTION_TITLES = {"blocked": "[ممنوع]", "red": "[🔴]", "yellow": "[🟡]", "blue": "[🔵]", "strip_end": "[پاک شود از آخر متن]"}

def parse_rules_text(text):
    out = {"blocked": [], "red": [], "yellow": [], "blue": [], "strip_end": []}
    cur = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in RULES_SECTIONS:
            cur = RULES_SECTIONS[line]
            continue
        if cur is None:
            continue
        if cur == "strip_end":
            if len(line) >= 3 and line not in out[cur]:
                out[cur].append(line)
        else:
            if len(line.replace(" ", "").replace("\u200c", "")) >= 3 and line not in out[cur]:
                out[cur].append(line)
    return out

def fetch_remote_rules():
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    try:
        r = requests.get(f"https://raw.githubusercontent.com/{repo}/{ref}/{RULES_FILE}",
                         headers={"Cache-Control": "no-cache"}, timeout=15)
        if r.ok and r.text.strip():
            return r.text
    except requests.RequestException:
        pass
    return None

def load_rules():
    """rules.txt رو هر دور تازه می‌خونه (مثل proxies.txt). اگه خراب/نبود، قوانین قبلی می‌مونه."""
    global DYNAMIC_RULES, DYNAMIC_RULES_PREV
    text = fetch_remote_rules()
    if text is None and os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, encoding="utf-8") as f:
                text = f.read()
        except Exception as ex:
            print("rules read error:", ex)
            return DYNAMIC_RULES
    if text is None:
        return DYNAMIC_RULES
    try:
        parsed = parse_rules_text(text)
    except Exception as ex:
        print("rules parse error:", ex)
        return DYNAMIC_RULES
    # حداقل اعتبارسنجی: اگه هیچ بخشی پر نبود، فایل خراب حساب می‌شه
    if not any(parsed.values()):
        print("rules file empty/corrupt, keeping previous rules")
        return DYNAMIC_RULES
    DYNAMIC_RULES_PREV = dict(DYNAMIC_RULES)
    DYNAMIC_RULES = parsed
    print(f"rules loaded: blocked={len(parsed['blocked'])} red={len(parsed['red'])} yellow={len(parsed['yellow'])} blue={len(parsed['blue'])} strip_end={len(parsed['strip_end'])}")
    return DYNAMIC_RULES

def format_rules_text(rules=None):
    rules = rules or DYNAMIC_RULES
    lines = []
    for key in ("blocked", "red", "yellow", "blue", "strip_end"):
        lines.append(RULES_SECTION_TITLES[key])
        for w in rules.get(key, []):
            lines.append(w)
        lines.append("")
    return "\n".join(lines).strip() + "\n"

def save_rules_file():
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        f.write(format_rules_text())

def commit_rules():
    """rules.txt رو مثل posted.json توی گیت‌هاب ذخیره می‌کنه."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    import subprocess
    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True)
    try:
        git("config", "user.name", "news-bot")
        git("config", "user.email", "bot@users.noreply.github.com")
        git("pull", "--rebase", "--autostash")
        git("add", RULES_FILE)
        if git("diff", "--cached", "--quiet").returncode != 0:
            git("commit", "-m", "update rules")
            r = git("push")
            if r.returncode != 0:
                print("rules git push failed:", r.stderr[:200])
    except Exception as ex:
        print("commit rules error:", repr(ex))

def rules_safety_check(total_candidates, blocked_rejected):
    """اگه کلمه‌های ممنوع پویا بیش از نصف نامزدها (و حداقل ۵ تا) رو رد کنن، هشدار بده و لیست قبلی برگرده."""
    if total_candidates >= 5 and blocked_rejected and blocked_rejected / max(total_candidates, 1) > 0.5:
        try:
            alert("rules_blocked", f"⚠️ قانون‌های ممنوع جدید بیش از نصف خبرها ({blocked_rejected} از {total_candidates}) رو رد کرد؛ لیست قبلی برگردونده شد. rules.txt رو چک کن.", 1)
        except Exception:
            pass
        global DYNAMIC_RULES
        if DYNAMIC_RULES_PREV:
            DYNAMIC_RULES = dict(DYNAMIC_RULES_PREV)
        RULES_BLOCKED_SUSPENDED[0] = True
        print("rules safety: dynamic blocked suspended, previous list restored")
        return True
    return False

# شمارنده‌ی ردشدن با کلمه‌ی ممنوع در همین دور (برای ایمنی قوانین)
RULES_REJECT_STATS = {"total": 0, "blocked": 0}



# ====== ارسال ======
PARSE_MODE = ["HTML"]
UPLOAD_FAILS = [0]   # اگه آپلود دو بار تایم‌اوت شد، بقیه‌ی اجرا بدون آپلود ادامه پیدا می‌کنه
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
        lead, marker = decide(item)
    first = f"{lead} <b>{esc(item['title'])}</b>"
    tail = [proxy_parts()[0], CHANNEL]
    paras = list(item.get("paras") or [])
    mark = (not kind) and len(paras) >= 2   # فقط خبرِ چندپاراگرافی علامت می‌گیره
    # نقل‌قول جمع‌شونده فقط برای خبر معمولی طولانی، نه لیست قیمت و نه کیوسک
    # (نسخه‌ی d: فقط تیتر دیده می‌شه؛ پاراگراف اول هم مثل بقیه داخل نقل‌قول می‌ره)
    if not kind:
        _plain_len = len(item.get("title", "")) + sum(len(x) for x in paras)
        if _plain_len > 600 or len(paras) >= 3:
            title_text = (item.get("title") or "").strip()
            quoted_paras = list(paras)
            if quoted_paras and quoted_paras[0].strip() == title_text:
                quoted_paras = quoted_paras[1:]   # پاراگراف اول اگه عین تیتر بود، تکراریه؛ داخل نقل‌قول نمی‌ره
            visible = [first]   # فقط تیتر دیده می‌شه؛ پاراگراف اول هم داخل نقل‌قول می‌ره
            quoted = [f"{marker} {esc(x)}" if mark else esc(x) for x in quoted_paras]
            def assemble_q(q):
                parts = list(visible)
                if q:
                    parts.append("<blockquote expandable>" + "\n\n".join(q) + "</blockquote>")
                parts += tail
                return "\n\n".join(parts)
            text = assemble_q(quoted)
            while len(text) > max_len and quoted:
                quoted.pop()   # اول از آخرِ نقل‌قول کم می‌شه؛ تیتر همیشه می‌مونه
                text = assemble_q(quoted)
            return text
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


def _fit_one_message(text, max_len=4000):
    """متن رو برای «یک پیام» جا می‌کنه (نسخه‌ی j: هر خبر دقیقاً یک پست).
    فقط از مرز پاراگراف کم می‌شه؛ وسط جمله «…» گذاشته نمی‌شه. سقف ۴۰۰۰
    زیر سقف ۴۰۹۶ تلگرامه تا پیام هیچ‌وقت به‌خاطر بلندی رد نشه."""
    if len(text) <= max_len:
        return text
    blocks = text.split("\n\n")
    out, total = [], 0
    for b in blocks:
        add = len(b) + (2 if out else 0)
        if out and total + add > max_len:
            break
        out.append(b)
        total += add
    if not out:   # یک بلوکِ تنها که خودش از سقف رد شد: از مرز کلمه
        return blocks[0][:max_len].rsplit(" ", 1)[0]
    return "\n\n".join(out)


# ====== هشدار به ادمین (چت خصوصی) ======
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "").strip()   # از GitHub Secrets؛ توی فایل نوشته نمی‌شه
STATE_REF = [None]            # حالت همین دور (برای فاصله‌ی بین هشدارها)
READ_STATUS = {}              # تعداد پست‌های خونده‌شده از هر کانال در همین اجرا
NO_POST_ALERT_MIN = 90        # اگه این‌قدر دقیقه توی ساعت‌های فعال پستی نرفت: هشدار
EMPTY_STREAK_ALERT = 3        # اگه کانالی این‌قدر بار پشت‌سرهم خونده نشد: هشدار
AUTH_HINTS = ("chat not found", "not enough rights", "bot was kicked", "bot is not a member",
              "chat_write_forbidden", "have no rights", "unauthorized")


def alert(key, text, cooldown_h=3):
    """به ادمین پیام می‌ده؛ برای هر کلید حداقل cooldown_h ساعت فاصله می‌ذاره (۰ = همیشه)."""
    if not ADMIN_CHAT_ID:
        return False
    state = STATE_REF[0]
    now = time.time()
    if state is not None and cooldown_h:
        if now - state.setdefault("alerts", {}).get(key, 0) < cooldown_h * 3600:
            return False
    ok = admin_send(text)
    if ok and state is not None:
        state.setdefault("alerts", {})[key] = now
    return ok


def minutes_since_active_start(m):
    """دقیقه‌ی گذشته از شروع بازه‌ی فعال (۰۸:۳۰ تهران)."""
    return (m - 510) % 1440


def check_no_post(state, now, m):
    last = state.get("last_post") or now
    gap = (now - last) / 60
    if gap > NO_POST_ALERT_MIN and minutes_since_active_start(m) > NO_POST_ALERT_MIN:
        alert("nopost", f"⚠️ حدود {int(gap)} دقیقه‌ست توی کانال پستی نرفته.\n"
                        "Actions را ببین؛ اگه اجرایی در حال کار نبود، Run workflow با mode=auto بزن.", 3)


# ====== آمار روزانه، گزارش و فرمان‌های ادمین ======
AD_STATS = {}          # نام کانال -> (تبلیغ ردشده، کل پست‌های خونده‌شده)
RSS_READ = {}          # آدرس RSS -> تعداد خبر خونده‌شده
RATE_LIMITS = [0]      # تعداد خطای ۴۲۹ تلگرام در همین اجرا
FEW_PROXIES = 5
POLL_SECONDS = 10      # هر چند ثانیه فرمان‌های ادمین خونده بشه (در حالت حلقه)


def admin_send(text, html_mode=False, reply_markup=None):
    if not ADMIN_CHAT_ID:
        return False
    data = {"chat_id": ADMIN_CHAT_ID, "text": text[:3900], "disable_web_page_preview": "true"}
    if html_mode:
        data["parse_mode"] = "HTML"
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    # اگه ارسال اول ناموفق بود، یک بار دیگه تلاش می‌کنه تا تأییدیه به ادمین برسه
    # (مثلاً وقتی «بسنت» ثبت شد ولی پیام «✅ اضافه شد» نرسید)
    for _attempt in (1, 2):
        try:
            r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=20)
            if r.ok:
                return True
            print("  admin send failed:", r.status_code, r.text[:120])
        except requests.RequestException as ex:
            print("  admin send network error:", type(ex).__name__)
        if _attempt == 1:
            time.sleep(3)
    return False


def day_stats(state, day_id):
    st = state.get("stats") or {}
    if st.get("day") != day_id:
        if st.get("day"):
            week = state.setdefault("stats_week", [])
            week.append({"day": st.get("day"), "posted": st.get("posted", 0), "src": dict(st.get("src", {})), "rejected": st.get("rejected", 0), "ads": st.get("ads", 0), "errors": st.get("errors", 0), "runs": st.get("runs", 0)})
            # فقط ۷ روز آخر نگه داشته می‌شه
            seen_days = {}
            for e in week:
                seen_days[e.get("day")] = e
            state["stats_week"] = [seen_days[k] for k in sorted(seen_days)[-7:]]
            # با عوض شدن «روز» کانال، خبرهای مهم امروز می‌شن خبرهای دیروز (برای صبحانه خبری)
            if state.get("today_top"):
                state["prev_top"] = list(state.get("today_top") or [])[-50:]
            state["today_top"] = []
            state["today_top_day"] = day_id
        st = {"day": day_id, "posted": 0, "src": {}, "ads": 0, "rejected": 0, "runs": 0, "errors": 0, "first": None}
        state["stats"] = st
    st.setdefault("rejected", 0)
    return st


def count_post(state, src):
    st = state.get("stats")
    if st is None:
        return
    st["posted"] = st.get("posted", 0) + 1
    d = st.setdefault("src", {})
    d[src] = d.get(src, 0) + 1


def build_report(state, ks, day_id):
    st = state.get("stats") or {}
    ok = lambda v: "✓" if v else "✗"
    src = st.get("src", {})
    lines = [f"📊 گزارش روز {day_id} — GodNews24", f"✅ پست ارسال‌شده: {st.get('posted', 0)}"]
    if src:
        lines.append("   " + " | ".join(f"{k}: {v}" for k, v in sorted(src.items(), key=lambda x: -x[1])))
    lines += [f"🛡 پست‌های ردشده: {st.get('rejected', st.get('ads', 0))}",
              f"📰 کیوسک: صبح بخیر {ok(ks.get('morning'))} | نگاه گذرا {ok(ks.get('summary'))} | شب بخیر {ok(ks.get('night'))}",
              f"🔁 تعداد اجراها: {st.get('runs', 0)} | شروع امروز: {st.get('first') or '—'}",
              f"⚠️ خطاها: {st.get('errors', 0)}"]
    if state.get("paused"):
        lines.append("⏸ ارسال الان متوقفه (با /resume ادامه می‌دم)")
    return "\n".join(lines)


def maybe_report(state, ks, day_id):
    """گزارش روزانه: یک بار در روز، بعد از پیام شب بخیر."""
    if not ADMIN_CHAT_ID or state.get("report_day") == day_id:
        return False
    if admin_send(build_report(state, ks, day_id)):
        state["report_day"] = day_id
        return True
    return False


def fmt_ago(ts):
    if not ts:
        return "—"
    mins = int((time.time() - ts) / 60)
    return f"{mins} دقیقه پیش" if mins < 120 else f"{mins // 60} ساعت پیش"


def status_text(state):
    st = state.get("stats") or {}
    src = st.get("src", {}) or {}
    src_line = " | ".join(f"{k}: {v}" for k, v in sorted(src.items(), key=lambda x: -x[1])) if src else "—"
    muted = state.get("muted_sources") or []
    lines = [
        f"🤖 نسخه‌ی ربات: {BOT_VERSION}",
        f"🕒 ساعت تهران: {tehran_now():%H:%M}",
        "⏸ ارسال متوقفه" if state.get("paused") else "▶️ ارسال فعاله",
        f"آخرین پست: {fmt_ago(state.get('last_post'))}",
        f"آخرین نوبت کانال‌ها: {fmt_ago(state.get('last_tg'))}",
        f"آخرین نوبت بقیه‌ی منابع: {fmt_ago(state.get('last_other'))}",
        f"امروز: {st.get('posted', 0)} پست | {st.get('rejected', st.get('ads', 0))} پست‌های ردشده | {st.get('errors', 0)} خطا",
        f"پست امروز از هر منبع: {src_line}",
        f"پروکسی سالم (آخرین چک): {state.get('alive_count', '—')} از {state.get('proxy_checked', '—')} بررسی‌شده "
        f"({state.get('proxy_total', '—')} در فایل)",
        f"حالت حلقه: {'روشن' if LOOP_MINUTES > 0 else 'خاموش'}",
    ]
    _dg = state.get("digests") or {}
    _dg_day = (tehran_now() - timedelta(hours=8)).strftime("%Y-%m-%d")
    if _dg.get("day") == _dg_day:
        lines.append(f"🍳 صبحانه: {'✅' if _dg.get('morning') else '—'} | 🍽️ شام: {'✅' if _dg.get('dinner') else '—'}")
    else:
        lines.append("🍳 صبحانه: — | 🍽️ شام: —")
    if muted:
        lines.append(f"🔇 منبع‌های بی‌صدا: {', '.join(muted)}")
    return "\n".join(lines)

def stats_text(state):
    st = state.get("stats") or {}
    week = state.get("stats_week") or []
    total_posted = st.get("posted", 0) + sum(e.get("posted", 0) for e in week)
    total_rej = st.get("rejected", 0) + sum(e.get("rejected", 0) for e in week)
    total_err = st.get("errors", 0) + sum(e.get("errors", 0) for e in week)
    total_runs = st.get("runs", 0) + sum(e.get("runs", 0) for e in week)
    src_tot = {}
    for e in list(week) + [st]:
        for k, v in (e.get("src") or {}).items():
            src_tot[k] = src_tot.get(k, 0) + v
    lines = ["📈 آمار ۷ روز اخیر (شامل امروز):", f"پست: {total_posted} | پست‌های ردشده: {total_rej} | خطا: {total_err} | اجراها: {total_runs}"]
    if src_tot:
        lines.append("از هر منبع: " + " | ".join(f"{k}: {v}" for k, v in sorted(src_tot.items(), key=lambda x: -x[1])))
    for e in sorted(week, key=lambda x: x.get("day", "")):
        lines.append(f"{e.get('day')}: {e.get('posted', 0)} پست، {e.get('rejected', 0)} ردشده")
    lines.append(f"امروز ({st.get('day', '')}): {st.get('posted', 0)} پست، {st.get('rejected', st.get('ads', 0))} ردشده")
    return "\n".join(lines)


def test_text():
    base = f"https://api.telegram.org/bot{TOKEN}"
    try:
        me = requests.get(base + "/getMe", timeout=15).json()
        bot_id, uname = me["result"]["id"], me["result"].get("username")
        cm = requests.get(base + "/getChatMember", params={"chat_id": CHANNEL, "user_id": bot_id}, timeout=15).json()
        if cm.get("ok"):
            res = cm["result"]
            can = res.get("can_post_messages", res.get("status") == "creator")
            return (f"🤖 ربات @{uname}\n📣 کانال {CHANNEL}: وضعیت {res.get('status')}، "
                    f"اجازه‌ی ارسال: {'✓' if can else '✗'}")
        return f"❌ دسترسی به کانال بررسی نشد: {cm.get('description')}"
    except Exception as ex:
        return f"❌ تست ناموفق بود: {type(ex).__name__}"


def rejected_text(state, mode):
    today = rejected_day()
    log = [e for e in (state.get("rejected") or []) if e.get("day") == today]   # فقط پست‌های امروز
    if mode == "errors":
        rows, title = [e for e in log if e["why"].startswith("خطا")], "❌ پست‌هایی که امروز ارسالشون خطا داد"
    else:
        rows, title = log, "📋 پست‌های ردشده‌ی امروز (تبلیغ و بقیه)"
    if not rows:
        return [title + "\n\nمورد ثبت‌شده‌ای نیست."]
    counts = {}
    for e in rows:
        g = "تبلیغ" if e["why"].startswith("تبلیغ") else e["why"]
        counts[g] = counts.get(g, 0) + 1
    shown = rows[-40:][::-1]
    head = f"{title}\nمجموع: {len(rows)} | " + "، ".join(f"{k}: {v}" for k, v in counts.items()) + "\n"
    chunks, cur = [], head
    for i, e in enumerate(shown, 1):
        line = (f"\n{i}) [{e['src']}] {tehran_hm(e['t'])} — {e['why']}\n«{e['text']}»"
                + (f"\n⚠️ {e['extra']}" if e.get("extra") else "") + (f"\n{e['link']}" if e.get("link") else "") + "\n")
        if len(cur) + len(line) > 3500:
            chunks.append(cur)
            cur = ""
        cur += line
    if len(rows) > len(shown):
        cur += f"\n… و {len(rows) - len(shown)} مورد قدیمی‌تر\n"
    chunks.append(cur)
    return chunks


HELP_TEXT = ("دستورها:\n/status ← وضعیت لحظه‌ای و پست امروز از هر منبع\n/pause ← توقف ارسال به کانال\n/resume ← ادامه‌ی ارسال\n"
             "/skipped ← همه‌ی پست‌های ردشده‌ی امروز (تبلیغ، کلمه‌ی ممنوع، سیاسی، شوخی و...)\n"
             "/errors ← پست‌هایی که امروز ارسالشون خطا داد\n"
             "/test ← بررسی دسترسی ربات به کانال و نمونه‌ی قالب پست\n"
             "/send متن یا عکس ← ارسال خبر دلخواه (متن یا عکس/ویدیو) به کانال\n/delete ← پاک کردن آخرین پست ربات\n"
             "/mute منبع ← بی‌صدا کردن موقت یک منبع\n/unmute منبع ← برگردوندن منبع\n/muted ← لیست منبع‌های بی‌صدا\n"
             "/stats ← آمار ۷ روز اخیر\n"
             "صبحانه خبری ساعت ۰۹:۰۰ و شام خبری ساعت ۲۳:۰۰ خودکار فرستاده می‌شن\n/rules ← لیست قوانین فعلی\n/block کلمه ← اضافه کردن کلمه به ممنوع\n/add 🔴|🟡|🔵 کلمه ← اضافه کردن کلمه به ایموجی\n/strip عبارت ← اضافه کردن عبارت به پاک‌شونده‌های آخر متن\n/unstrip عبارت ← حذف عبارت از پاک‌شونده‌های آخر متن\n/menu ← نمایش منوی دکمه‌ای")


# ====== منوی دکمه‌ای (ReplyKeyboard) در چت خصوصی ادمین ======
# دکمه‌ها فقط دستورهای بدون آرگومان‌اند؛ متن دکمه به دستور نگاشت می‌شه.
MENU_BUTTONS = [
    ("📊 وضعیت", "/status"),
    ("📈 آمار", "/stats"),
    ("⏸ توقف", "/pause"),
    ("▶️ ادامه", "/resume"),
    ("📜 قوانین", "/rules"),
    ("🚫 ردشده‌ها", "/skipped"),
    ("⚠️ خطاها", "/errors"),
    ("🧪 تست", "/test"),
    ("🔇 بی‌صداها", "/muted"),
    ("❓ راهنما", "/help"),
    ("✉️ ارسال خبر", "/send"),
    ("🗑 حذف آخرین پست", "/delete"),
    ("🔕 بی‌صدا کردن", "/mute"),
    ("🔔 برگردوندن منبع", "/unmute"),
    ("🚫 مسدود کردن", "/block"),
    ("➕ اضافه به ایموجی", "/add"),
    ("✂️ پاک‌شونده اضافه", "/strip"),
    ("↩️ پاک‌شونده حذف", "/unstrip"),
]
MENU_TEXT_TO_CMD = {label: cmd for label, cmd in MENU_BUTTONS}

# دکمه‌هایی که آرگومان می‌خوان: اول این پیام رو می‌فرسته، پیام بعدی ادمین آرگومان حساب می‌شه.
# (chr(10) یعنی خط جدید؛ برای اینکه تو متن سورس بک‌اسلش-n ننویسیم.)
MENU_PROMPTS = {
    "/send": chr(10).join(["متن یا عکس/ویدیوی خبر رو بفرست تا به کانال بفرستم.", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
    "/mute": chr(10).join(["اسم منبع رو بفرست (مثلاً AloNews).", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
    "/unmute": chr(10).join(["اسم منبعی که می‌خوای برگرده رو بفرست (مثلاً AloNews).", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
    "/block": chr(10).join(["کلمه‌ی ممنوع رو بفرست.", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
    "/add": chr(10).join(["ایموجی و کلمه رو بفرست، مثلاً: 🔴 کلمه", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
    "/strip": chr(10).join(["عبارت پاک‌شونده رو بفرست (مثلاً / ایسنا).", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
    "/unstrip": chr(10).join(["عبارتی که می‌خوای از پاک‌شونده‌ها حذف بشه رو بفرست.", "برای لغو «لغو» رو بفرست یا /menu رو بزن."]),
}
MENU_PENDING_TIMEOUT = 600  # ثانیه؛ اگه ادمین تا این مدت جواب نده، انتظار لغو می‌شه

# همه‌ی دستورهایی که handle_command می‌شناسه؛ برای اینکه وقتی منتظر آرگومانیم،
# متنی که با «/» شروع می‌شه ولی دستور نیست (مثلاً «/ ایسنا») آرگومان حساب بشه.
KNOWN_COMMANDS = {"/start", "/help", "/menu", "/status", "/stats", "/rules",
                  "/block", "/add", "/strip", "/unstrip", "/send", "/delete",
                  "/mute", "/unmute", "/muted", "/skipped", "/errors", "/ads",
                  "/pause", "/resume", "/test"}

def menu_keyboard():
    rows = []
    for i in range(0, len(MENU_BUTTONS), 2):
        rows.append([{"text": label} for label, _ in MENU_BUTTONS[i:i + 2]])
    return {"keyboard": rows, "resize_keyboard": True}


# ====== دستورهای جدید: /send /delete /mute /stats /rules ======
SOURCE_ALIASES = {
    "alonews": "AloNews", "arz_talaaa": "arz_talaaa", "arztalaaa": "arz_talaaa",
    "euronews": "euronews", "dw": "dw", "france24": "france24", "alarabiya": "alarabiya",
    "independent": "independent", "independentpersian": "independent",
    "isna": "isna", "varzesh3": "varzesh3", "digiato": "digiato",
}

def normalize_source(raw):
    return (raw or "").strip().lstrip("@").lower()

def source_muted_key(state, url):
    muted = [m.lower() for m in (state.get("muted_sources") or [])]
    if not muted:
        return False
    if url.startswith("tg:"):
        return url[3:].lower() in muted
    low = url.lower()
    for m in muted:
        if m in low:
            return True
    return False

def _send_admin_text(text):
    return admin_send(text)


def _pending_media(msg):
    """اگه پیام عکس یا ویدیو داره، (نوع، file_id بزرگ‌ترین سایز) رو برمی‌گردونه؛ وگرنه (None, None)."""
    video = msg.get("video") or {}
    if video.get("file_id"):
        return "video", video["file_id"]
    photo = msg.get("photo") or []
    if photo and photo[-1].get("file_id"):
        return "photo", photo[-1]["file_id"]
    return None, None


def send_media_to_channel(state, kind, file_id, caption):
    """عکس/ویدیوی ادمین رو با همون قاعده‌ی /send متنی به کانال می‌فرسته:
    پروکسی (لینک روی کلمه‌ی «پروکسی») و @GodNews24 آخر کپشن؛ اگه کپشن + دنباله از ۱۰۲۴ حرف
    بیشتر شد، رسانه بدون کپشن می‌ره و متن کامل جدا فرستاده می‌شه."""
    if not file_id:
        admin_send("❌ فایل رسانه پیدا نشد؛ دوباره بفرست.")
        return
    # کپشن با HTML فرستاده می‌شه تا لینک پروکسی روی خود کلمه‌ی «پروکسی» بشینه
    # (مثل پست‌های عادی خبر)، نه اینکه آدرس کامل لینک دیده بشه؛ متن کاربر
    # escape می‌شه تا «<» و «&» توی کپشن، HTML رو خراب نکنه.
    text = (caption or "").rstrip()
    if text.endswith(CHANNEL):
        full = html.escape(text)
    else:
        p_html = proxy_parts()[0]
        tail = []
        if "://" in p_html:   # فقط وقتی لینک پروکسی واقعی هست؛ وگرنه خط پروکسی رد می‌شه
            tail.append(p_html)
        tail.append(CHANNEL)
        full = "\n\n".join(x for x in (html.escape(text), "\n".join(tail)) if x)
    method, field = ("sendVideo", "video") if kind == "video" else ("sendPhoto", "photo")
    LAST_TG_IDS.clear()
    old_mode = PARSE_MODE[0]
    PARSE_MODE[0] = "HTML"
    try:
        if len(full) <= 1024:
            ok = tg(method, **{field: file_id, "caption": full})
        else:
            ok = tg(method, **{field: file_id})
            if ok:
                ok = tg("sendMessage", text=full, disable_web_page_preview="true")
    finally:
        PARSE_MODE[0] = old_mode
    if ok:
        ids = list(LAST_TG_IDS)
        if ids:
            state["last_post_ids"] = ids[-10:]
            state["last_post"] = time.time()
            try:
                save_state(state)
            except Exception:
                pass
        admin_send(f"✅ فرستاده شد. message_id: {ids[-1] if ids else '—'}")
    else:
        admin_send(f"❌ ارسال نشد. {LAST_TG_ERROR[0]}")

def handle_command(state, cmd, full_text=""):
    full_text = full_text or cmd
    parts = full_text.strip().split(None, 1)
    arg = parts[1].strip() if len(parts) > 1 else ""
    if cmd in ("/start", "/help"):
        admin_send(HELP_TEXT, reply_markup=menu_keyboard())
    elif cmd == "/menu":
        admin_send("منوی ربات 👇\nروی دکمه بزن؛ دستور همون دکمه اجرا می‌شه.", reply_markup=menu_keyboard())
    elif cmd == "/status":
        admin_send(status_text(state))
    elif cmd == "/stats":
        admin_send(stats_text(state))
    elif cmd == "/rules":
        r = DYNAMIC_RULES
        lines = ["📜 قوانین فعلی (rules.txt):"]
        for key, label in (("blocked", "ممنوع"), ("red", "🔴"), ("yellow", "🟡"), ("blue", "🔵"), ("strip_end", "پاک شود از آخر متن")):
            words = r.get(key, [])
            lines.append(f"{label} ({len(words)}): " + ("، ".join(words) if words else "—"))
        admin_send("\n".join(lines))
    elif cmd == "/block":
        w = arg.strip()
        if len(w.replace(" ", "").replace("\u200c", "")) < 3:
            admin_send("کلمه باید حداقل ۳ حرف باشد. مثال: /block کلمه")
        elif w in DYNAMIC_RULES.get("blocked", []):
            admin_send(f"«{w}» همین حالا هم ممنوع است.")
        else:
            DYNAMIC_RULES.setdefault("blocked", []).append(w)
            try:
                save_rules_file(); commit_rules()
            except Exception as ex:
                print("save rules error:", ex)
            admin_send(f"✅ «{w}» به ممنوع اضافه شد.")
    elif cmd == "/add":
        toks = arg.split(None, 1)
        if len(toks) < 2 or toks[0] not in ("🔴", "🟡", "🔵"):
            admin_send("مثال: /add 🔴 کلمه  یا  /add 🟡 کلمه")
        else:
            emoji, w = toks[0], toks[1].strip()
            key = {"🔴": "red", "🟡": "yellow", "🔵": "blue"}[emoji]
            if len(w.replace(" ", "").replace("\u200c", "")) < 3:
                admin_send("کلمه باید حداقل ۳ حرف باشد.")
            elif w in DYNAMIC_RULES.get(key, []):
                admin_send(f"«{w}» همین حالا هم در {emoji} است.")
            else:
                DYNAMIC_RULES.setdefault(key, []).append(w)
                try:
                    save_rules_file(); commit_rules()
                except Exception as ex:
                    print("save rules error:", ex)
                admin_send(f"✅ «{w}» به {emoji} اضافه شد.")
    elif cmd == "/strip":
        ph = arg.strip()
        if len(ph) < 3:
            admin_send("عبارت باید حداقل ۳ حرف باشد. مثال: /strip / ایسنا")
        elif any((x or "").strip() == ph for x in DYNAMIC_RULES.get("strip_end", [])):
            admin_send(f"«{ph}» همین حالا هم در پاک‌شونده‌های آخر متن است.")
        else:
            DYNAMIC_RULES.setdefault("strip_end", []).append(ph)
            try:
                save_rules_file(); commit_rules()
            except Exception as ex:
                print("save rules error:", ex)
            admin_send(f"✅ «{ph}» به پاک‌شونده‌های آخر متن اضافه شد.")
    elif cmd == "/unstrip":
        ph = arg.strip()
        if not ph:
            admin_send("عبارت را هم بفرست. مثال: /unstrip / ایسنا")
        elif not any((x or "").strip() == ph for x in DYNAMIC_RULES.get("strip_end", [])):
            admin_send(f"«{ph}» در پاک‌شونده‌های آخر متن نیست.")
        else:
            DYNAMIC_RULES["strip_end"] = [x for x in DYNAMIC_RULES.get("strip_end", []) if (x or "").strip() != ph]
            try:
                save_rules_file(); commit_rules()
            except Exception as ex:
                print("save rules error:", ex)
            admin_send(f"✅ «{ph}» از پاک‌شونده‌های آخر متن حذف شد.")
    elif cmd == "/send":
        if not arg:
            admin_send("متن را هم بفرست. مثال: /send سلام به کانال")
            return
        text = arg.rstrip()
        if not text.endswith(CHANNEL):
            # آخر متن: پروکسی (متن ساده، چون /send متن ساده می‌فرسته) و بعد @GodNews24
            p_plain = proxy_parts()[1]
            tail = []
            if "://" in p_plain:   # فقط وقتی لینک پروکسی واقعی هست؛ وگرنه خط پروکسی رد می‌شه
                tail.append(p_plain)
            tail.append(CHANNEL)
            text = text + "\n\n" + "\n".join(tail)
        LAST_TG_IDS.clear()
        old_mode = PARSE_MODE[0]
        PARSE_MODE[0] = None
        try:
            ok = tg("sendMessage", text=text, disable_web_page_preview="true")
        finally:
            PARSE_MODE[0] = old_mode
        if ok:
            ids = list(LAST_TG_IDS)
            if ids:
                state["last_post_ids"] = ids[-10:]
                state["last_post"] = time.time()
                try:
                    save_state(state)
                except Exception:
                    pass
            admin_send(f"✅ فرستاده شد. message_id: {ids[-1] if ids else '—'}")
        else:
            admin_send(f"❌ ارسال نشد. {LAST_TG_ERROR[0]}")
    elif cmd == "/delete":
        ids = list(state.get("last_post_ids") or [])
        if not ids:
            admin_send("پستی برای پاک کردن ندارم.")
            return
        done, failed = [], []
        for mid in ids:
            try:
                r = requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteMessage", data={"chat_id": CHANNEL, "message_id": mid}, timeout=20)
                (done if r.ok else failed).append(mid)
            except Exception:
                failed.append(mid)
        if failed:
            state["last_post_ids"] = failed
            admin_send(f"✅ پاک شد: {done}\n❌ پاک نشد: {failed}")
        else:
            state["last_post_ids"] = []
            admin_send(f"✅ آخرین پست پاک شد: {done}")
        try:
            save_state(state)
        except Exception:
            pass
    elif cmd == "/mute":
        key = normalize_source(arg)
        canon = SOURCE_ALIASES.get(key, key)
        if not key:
            admin_send("منبع را هم بگو. مثال: /mute AloNews")
        elif canon in [normalize_source(x) for x in (state.get("muted_sources") or [])]:
            admin_send(f"«{canon}» همین حالا هم بی‌صداست.")
        else:
            state.setdefault("muted_sources", []).append(canon)
            admin_send(f"🔇 «{canon}» تا /unmute بی‌صدا شد.")
    elif cmd == "/unmute":
        key = normalize_source(arg)
        canon = SOURCE_ALIASES.get(key, key)
        muted = state.get("muted_sources") or []
        new_muted = [x for x in muted if normalize_source(x) != canon]
        if len(new_muted) == len(muted):
            admin_send(f"«{canon}» بی‌صدا نبود.")
        else:
            state["muted_sources"] = new_muted
            admin_send(f"🔊 «{canon}» برگشت.")
    elif cmd == "/muted":
        muted = state.get("muted_sources") or []
        admin_send("🔇 منبع‌های بی‌صدا: " + ("، ".join(muted) if muted else "هیچ‌کدام"))
    elif cmd in ("/ads", "/errors", "/skipped"):
        for chunk in rejected_text(state, cmd[1:]):
            admin_send(chunk)
    elif cmd == "/pause":
        state["paused"] = True
        admin_send("⏸ ارسال به کانال متوقف شد. با /resume ادامه می‌دم.")
    elif cmd == "/resume":
        state["paused"] = False
        admin_send("▶️ ارسال از دور بعدی ادامه پیدا می‌کنه.")
    elif cmd == "/test":
        admin_send(test_text())
        sample = {"title": "نمونه‌ی خبر برای آزمایش قالب پست", "summary": "", "category": "general", "kind": None,
                  "paras": ["این بند اول نمونه است.", "این بند دوم نمونه است."]}
        if not admin_send(build_text(sample), html_mode=True):
            admin_send("نمونه‌ی قالب ارسال نشد.")
    else:
        admin_send("دستور ناشناخته. /help رو بزن.")


def process_commands(state):
    """فرمان‌های ادمین (فقط از چت خصوصی خودش) رو می‌خونه. True یعنی حافظه تغییر کرده."""
    if not ADMIN_CHAT_ID:
        return False
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                         params={"offset": state.get("tg_offset", 0), "timeout": 0,
                                 "allowed_updates": json.dumps(["message"])}, timeout=20)
        data = r.json()
    except Exception as ex:
        print("getUpdates error:", type(ex).__name__)
        return False
    if not data.get("ok"):
        print("getUpdates failed:", str(data)[:120])
        return False
    changed = False
    for u in data.get("result", []):
        state["tg_offset"] = u["update_id"] + 1
        changed = True
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != ADMIN_CHAT_ID:
            continue
        # پیام عکس/ویدیو «text» نداره، کپشن داره؛ اگه فقط text رو بخونیم عکس‌ها
        # بی‌صدا رد می‌شن (همین باگ /send بود).
        text = (msg.get("text") or "").strip()
        caption = (msg.get("caption") or "").strip()
        if not text:
            text = caption
        kind, fid = _pending_media(msg)
        if not text and not fid:
            continue
        pending = state.get("menu_pending")
        if pending and time.time() - float(state.get("menu_pending_ts") or 0) > MENU_PENDING_TIMEOUT:
            state["menu_pending"] = None
            state.pop("menu_pending_ts", None)
            pending = None
        if text in ("لغو", "❌ لغو"):
            if pending:
                state["menu_pending"] = None
                state.pop("menu_pending_ts", None)
                admin_send("لغو شد.", reply_markup=menu_keyboard())
            continue
        first = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if text in MENU_TEXT_TO_CMD:
            cmd = MENU_TEXT_TO_CMD[text]
            if cmd in MENU_PROMPTS:
                state["menu_pending"] = cmd
                state["menu_pending_ts"] = time.time()
                admin_send(MENU_PROMPTS[cmd])
            else:
                state["menu_pending"] = None
                state.pop("menu_pending_ts", None)
                handle_command(state, cmd, text)
        elif text.startswith("/") and first in KNOWN_COMMANDS:
            state["menu_pending"] = None
            state.pop("menu_pending_ts", None)
            if first == "/send" and fid:
                # کپشنِ «/send ...» روی عکس/ویدیو: بقیه‌ی کپشن، کپشن رسانه می‌شه.
                arg = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
                send_media_to_channel(state, kind, fid, arg)
            else:
                handle_command(state, first, text)
        elif pending:
            cmd = pending
            state["menu_pending"] = None
            state.pop("menu_pending_ts", None)
            if cmd == "/send" and fid:
                send_media_to_channel(state, kind, fid, text)
            else:
                handle_command(state, cmd, cmd + " " + text)
        elif text.startswith("/"):
            handle_command(state, first, text)
    return changed


def poll_commands():
    if not ADMIN_CHAT_ID:
        return
    state = load_state()
    STATE_REF[0] = state
    if process_commands(state):
        save_state(state)
        commit_state()


LAST_TG_ERROR = [""]


def tehran_hm(ts):
    t = datetime.fromtimestamp(ts, timezone.utc) + timedelta(hours=3, minutes=30)
    return f"{t:%H:%M}"


def rejected_day():
    return (tehran_now() - timedelta(hours=8, minutes=30)).strftime("%Y-%m-%d")   # لیست‌ها هر روز ساعت ۰۸:۳۰ تهران (با «صبح بخیر») از نو شروع می‌شن


def log_rejected(src, why, text, post_id=None, extra=""):
    """پست ردشده یا ناموفق رو برای دستورهای /ads و /errors و /skipped ثبت می‌کنه (هر پست فقط یک بار)."""
    st = STATE_REF[0]
    if st is None:
        return
    log = st.setdefault("rejected", [])
    key = f"{src}/{post_id}" if post_id else f"{src}:{why}:{(text or '')[:40]}"
    if any(e.get("k") == key for e in log):
        return
    log.append({"k": key, "t": int(time.time()), "day": rejected_day(), "src": src, "why": why,
                "text": re.sub(r"\s+", " ", text or "").strip()[:140],
                "link": f"https://t.me/{post_id}" if post_id else "", "extra": (extra or "")[:120]})
    del log[:-80]
    _st = st.get("stats") if isinstance(st, dict) else None
    if _st is not None:
        _st["rejected"] = _st.get("rejected", 0) + 1
        if (why or "").startswith("تبلیغ"):
            _st["ads"] = _st.get("ads", 0) + 1


def clear_error(src, post_id):
    """اگه پستی که قبلاً خطا داده بود بعداً با موفقیت رفت، از لیست /errors پاک می‌شه."""
    st = STATE_REF[0]
    if st is None or not post_id:
        return
    key = f"{src}/{post_id}"
    st["rejected"] = [e for e in st.get("rejected", []) if not (e.get("k") == key and e["why"].startswith("خطا"))]


def tg(method, files=None, **data):
    data["chat_id"] = CHANNEL
    if PARSE_MODE[0] and method != "sendMediaGroup":
        data["parse_mode"] = PARSE_MODE[0]
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    timeout = (10, 60 if files else 30)
    try:
        r = requests.post(url, data=data, files=files, timeout=timeout)
        if r.status_code == 429:  # محدودیت سرعت تلگرام: صبر و یک بار تلاش دوباره
            RATE_LIMITS[0] += 1
            try:
                wait = int(r.json().get("parameters", {}).get("retry_after", 5))
            except Exception:
                wait = 5
            time.sleep(min(wait, 30))
            r = requests.post(url, data=data, files=files, timeout=timeout)
    except requests.RequestException as ex:   # قطعی/کندیِ شبکه نباید کل اجرا رو خراب کنه
        print("  telegram network error:", method, type(ex).__name__)
        LAST_TG_ERROR[0] = f"{method}: {type(ex).__name__}"
        if files:
            UPLOAD_FAILS[0] += 1
        return False
    if not r.ok:
        print("  telegram error:", method, r.status_code, r.text[:150])
        LAST_TG_ERROR[0] = f"{method} {r.status_code}: {r.text[:80]}"
        low = r.text.lower()
        if r.status_code in (401, 403) or any(h in low for h in AUTH_HINTS):
            alert("tg_auth", f"🚫 تلگرام خطا داد ({method} {r.status_code}): {r.text[:160]}\n"
                             "احتمالاً ربات ادمین کانال نیست، حذف شده یا توکن عوض شده.", 1)
        return False
    try:
        res = r.json().get("result")
        ids = []
        if isinstance(res, dict) and res.get("message_id"):
            ids = [res["message_id"]]
        elif isinstance(res, list):
            ids = [m.get("message_id") for m in res if isinstance(m, dict) and m.get("message_id")]
        if ids:
            LAST_TG_IDS.extend(ids)
    except Exception:
        pass
    return True


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
    """همه‌ی رسانه‌های یک خبر رو با هم برمی‌گردونه (عکس و فیلم با هم، حداکثر ۱۰ تا)
    تا در یک پست (یک sendMediaGroup) برن، نه جدا از هم."""
    if item.get("media"):
        return item["media"][:10]
    out = []
    if item.get("video"):
        out.append(("video", item["video"]))
    if item.get("image"):
        out.append(("photo", item["image"]))
    return out


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


def _record_sent_ids():
    st = STATE_REF[0]
    if st is not None and LAST_TG_IDS:
        st["last_post_ids"] = list(LAST_TG_IDS[-10:])

def send(item):
    """هر خبر دقیقاً یک پست می‌شه (نسخه‌ی j: هیچ خبری تکه‌تکه نمی‌ره).
    همه‌ی عکس‌ها و فیلم‌های یک خبر با هم در یک پست می‌رن (یک sendMediaGroup).
    اگه گروه رسانه کاملاً شکست خورد، به‌جای یک عکسِ تنها که بقیه‌ی رسانه‌ها رو
    دور می‌ریزه، فقط متن فرستاده می‌شه. تک‌رسانه‌ای بودن با send_single مشکلی نداره.
    متن با build_text تا سقف یک پیام (۴۰۰۰) جا می‌شه؛ وسط جمله «…» نمی‌آد."""
    LAST_TG_IDS.clear()
    media = media_list(item)
    full_text = build_text(item)  # یک پیام، حداکثر ۴۰۰۰ کاراکتر
    up = str(item.get("id", "")).startswith("tg:")   # تلگرام لینک عکس کانال‌ها رو نمی‌تونه بگیره؛ مستقیم آپلود
    ok = False
    if not media:
        ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
    elif item.get("short"):
        # پست کوتاه (ایندیپندنت فارسی): عکس و متن با هم در یک پست می‌رن (کپشن)؛
        # اگه کپشن به هر دلیلی نرفت، متن تنها در یک پیام می‌ره
        caption = build_text(item, max_len=1000)
        if len(media) >= 2:
            if send_group(media, caption, up):
                ok = True
            else:
                print("  media group failed; sending text only (no single-media fallback that drops media)")
                ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
        elif send_single(media[0][0], media[0][1], caption, up):
            ok = True
        else:
            ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
    elif len(full_text) > 1000:
        # متن طولانی با عکس: اول عکس بدون کپشن، بعد متن کامل در یک پیام جداگانه
        # (کپشن تلگرام بیشتر از ۱۰۲۴ کاراکتر نمی‌گیره؛ خود خبر تکه نمی‌شه)
        if len(media) >= 2:
            if send_group(media, "", up):
                ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
            else:
                print("  media group failed; sending text only (no single-media fallback that drops media)")
                ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
        elif send_single(media[0][0], media[0][1], "", up):
            ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
        else:
            ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
    elif len(media) >= 2:
        if send_group(media, build_text(item, max_len=1000), up):
            ok = True
        else:
            print("  media group failed; sending text only (no single-media fallback that drops media)")
            ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
    elif send_single(media[0][0], media[0][1], build_text(item, max_len=1000), up):
        ok = True
    else:
        ok = tg("sendMessage", text=full_text, disable_web_page_preview="true")
    if ok:
        _record_sent_ids()
    return ok


def plain_of(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def deliver(text, media):
    """همه‌ی رسانه‌ها با هم در یک گروه می‌رن؛ اگه گروه کاملاً شکست خورد، فقط متن
    فرستاده می‌شه (نه یک عکس تنها که بقیه‌ی رسانه‌ها رو دور بریزه).
    نسخه‌ی j: متن همیشه در یک پیام می‌ره؛ اگه از سقف یک پیام رد شد، فقط از مرز
    پاراگراف جا می‌شه (بدون «…» وسط جمله)."""
    text = _fit_one_message(text)
    if media and len(text) > 1000:   # کپشن تلگرام حداکثر ۱۰۲۴ کاراکتره: اول عکس، بعد متن
        if len(media) >= 2:
            if send_group(media, "", True):
                return tg("sendMessage", text=text, disable_web_page_preview="true")
            print("  media group failed; sending text only (no single-media fallback that drops media)")
            return tg("sendMessage", text=text, disable_web_page_preview="true")
        if send_single(media[0][0], media[0][1], "", True):
            return tg("sendMessage", text=text, disable_web_page_preview="true")
        return tg("sendMessage", text=text, disable_web_page_preview="true")
    if len(media) >= 2:
        if send_group(media, text, True):
            return True
        print("  media group failed; sending text only (no single-media fallback that drops media)")
        return tg("sendMessage", text=text, disable_web_page_preview="true") if text else False
    if media and send_single(media[0][0], media[0][1], text, True):
        return True
    if text:
        return tg("sendMessage", text=text, disable_web_page_preview="true")
    return False


def send_special(text, media, proxy):
    """متن (HTML) رو می‌فرسته. ته پیام: [پروکسی] و بعد آیدی کانال خودمون."""
    text = text.strip()
    LAST_TG_IDS.clear()
    p_html, p_plain = proxy_parts()
    if deliver("\n\n".join(x for x in (text, p_html if proxy else "", CHANNEL) if x), media):
        _record_sent_ids()
        return True
    PARSE_MODE[0] = None   # اگه تلگرام فرمت HTML رو نپذیرفت، به‌صورت متن ساده
    try:
        parts = (plain_of(text), p_plain if proxy else "", CHANNEL)
        _ok = deliver("\n\n".join(x for x in parts if x), media)
        if _ok:
            _record_sent_ids()
        return _ok
    finally:
        PARSE_MODE[0] = "HTML"


# ====== خلاصه‌ی صبحانه و شام خبری (نسخه‌ی d؛ قالب نسخه‌ی h) ======
# هر خبر معمولیِ موفق در state["today_top"] ثبت می‌شه (حداکثر ۵۰ تا؛ لیست قیمت
# و کیوسک ثبت نمی‌شن). با عوض شدن «روز» کانال، today_top به prev_top منتقل می‌شه
# تا صبحانه خبری بتونه از خبرهای شب قبل هم استفاده کنه.
def record_top(state, item, day_id):
    """خبر معمولیِ تازه‌منتشرشده رو برای خلاصه‌های روز ثبت می‌کنه."""
    try:
        if item.get("kind"):
            return   # لیست قیمت ثبت نمی‌شه
        title = (item.get("title") or "").strip()
        if not title:
            return
        lead, _marker = decide(item)
        red = (lead == "🔴" or bool(item.get("red_src"))
               or bool(RED_RE.search(title)) or _dyn_match("red", title))
        top = state.setdefault("today_top", [])
        if any((e.get("t") or "") == title for e in top):
            return
        top.append({"t": title, "e": lead, "red": red, "ts": time.time(), "src": item.get("src", "?")})
        state["today_top"] = top[-50:]
        state["today_top_day"] = day_id
    except Exception as ex:
        print("record top error:", repr(ex))


def _dedupe_top(entries):
    """خبرهای تکراری (هم‌تیتر) رو حذف می‌کنه؛ تازه‌ترین نسخه می‌مونه."""
    by_title = {}
    for e in entries or []:
        t = (e.get("t") or "").strip()
        if not t:
            continue
        if t not in by_title or (e.get("ts") or 0) > (by_title[t].get("ts") or 0):
            by_title[t] = e
    return list(by_title.values())


def rank_top(entries):
    """مهم‌ترین‌ها اول: اول 🔴ها، بعد تازه‌ترین‌ها."""
    return sorted((e for e in _dedupe_top(entries) if (e.get("t") or "").strip()),
                  key=lambda e: (0 if e.get("red") else 1, -(e.get("ts") or 0)))


def build_digest_text(title, entries):
    """متن خلاصه (نسخه‌ی h): تیتر بدون تاریخ، خبرها بدون شماره و با یک خط
    خالی بین هر خبر، آخرش پروکسی و بعد @GodNews24.
    حداکثر ۱۰ خبر، حداکثر ۴۰۰۰ کاراکتر؛ خالی باشه رشته‌ی خالی برمی‌گرده."""
    ranked = rank_top(entries)[:10]
    if not ranked:
        return ""

    def assemble(max_title):
        parts = [title]
        for e in ranked:
            t = (e.get("t") or "").strip()
            if len(t) > max_title:
                t = t[:max_title].rsplit(" ", 1)[0]   # بدون «…»؛ از مرز کلمه کوتاه می‌شه
            parts.append(f"{e.get('e') or '🔵'} {t}")
        parts.append(proxy_parts()[0])
        parts.append(CHANNEL)
        return "\n\n".join(parts)

    text = assemble(200)
    for max_title in (150, 100, 60):
        if len(text) <= 4000:
            break
        text = assemble(max_title)
    while len(text) > 4000 and ranked:
        ranked = ranked[:-1]
        text = assemble(60)
    return text if ranked and len(text) <= 4000 else ""


def send_digest(state, kind, day_id, th):
    """یک خلاصه می‌فرسته (kind: "morning" یا "dinner"). خالی باشه بی‌صدا رد می‌شه
    و «فرستاده‌شده» علامت نمی‌خوره تا نوبت بعد دوباره امتحان بشه. خرابی‌ش
    هیچ‌وقت ارسال خبرها رو خراب نمی‌کنه."""
    dg = state.get("digests") or {}
    if dg.get("day") != day_id:
        dg = {"day": day_id, "morning": False, "dinner": False}
        state["digests"] = dg
    if dg.get(kind):
        return False
    if kind == "morning":
        entries = list(state.get("prev_top") or []) + list(state.get("today_top") or [])
        title = "🍳 صبحانه خبری گادنیوز ۲۴"
    else:
        entries = list(state.get("today_top") or [])
        title = "🍽️ شام خبری گادنیوز ۲۴"
    text = build_digest_text(title, entries)
    if not text:
        return False
    try:
        if tg("sendMessage", text=text, disable_web_page_preview="true"):
            dg[kind] = True
            state["digests"] = dg
            count_post(state, "digest")
            state["last_post"] = time.time()
            _record_sent_ids()
            print("digest posted:", kind)
            return True
    except Exception as ex:
        print("digest error:", kind, repr(ex))
    return False


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


def fetch_remote_state():
    """posted.json تازه رو از گیت‌هاب می‌خونه تا دور جدید با حافظه‌ی دور قبلی شروع بشه."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return None
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    try:
        headers = {"Cache-Control": "no-cache"}
        tok = os.environ.get("GITHUB_TOKEN")
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        r = requests.get(f"https://raw.githubusercontent.com/{repo}/{ref}/{STATE_FILE}", headers=headers, timeout=15)
        if r.ok and r.text.strip():
            data = json.loads(r.text)
            if isinstance(data, dict):
                return data
    except Exception as ex:
        print("remote state error:", ex)
    return None

def merge_remote_state(state, remote):
    if not remote:
        return False
    local_seen = list(state.get("seen") or [])
    remote_seen = list(remote.get("seen") or [])
    local_last = state.get("last_tg") or 0
    remote_last = remote.get("last_tg") or 0
    if not local_seen and not remote_seen:
        return False
    if not (len(remote_seen) > len(local_seen) or remote_last > local_last or not local_seen):
        return False
    merged_seen, seen_set = [], set()
    for x in local_seen + remote_seen:
        if x not in seen_set:
            seen_set.add(x)
            merged_seen.append(x)
    state["seen"] = merged_seen[-5000:]
    merged_seeded = list(dict.fromkeys(list(state.get("seeded") or []) + list(remote.get("seeded") or [])))
    state["seeded"] = merged_seeded
    titles = list(state.get("titles") or []) + list(remote.get("titles") or [])
    titles.sort(key=lambda t: t.get("t", 0) if isinstance(t, dict) else 0)
    state["titles"] = titles[-400:]
    for k in ("last_tg", "last_other", "last_post"):
        state[k] = max(state.get(k) or 0, remote.get(k) or 0)
    state["muted_sources"] = list(dict.fromkeys(list(state.get("muted_sources") or []) + list(remote.get("muted_sources") or [])))
    if remote.get("last_post_ids"):
        state["last_post_ids"] = list(dict.fromkeys(list(state.get("last_post_ids") or []) + list(remote.get("last_post_ids") or [])))[-10:]
    # خبرهای مهم روز (برای صبحانه/شام خبری): اگه روزشون فرق داشت، تازه‌تر می‌مونه؛
    # اگه هم‌روز بودن، با هم ادغام می‌شن تا چیزی گم نشه
    for _key in ("today_top", "prev_top"):
        _lcl, _rmt = list(state.get(_key) or []), list(remote.get(_key) or [])
        if not _rmt:
            continue
        if _key == "today_top":
            _ld, _rd = state.get("today_top_day"), remote.get("today_top_day")
            if _rd and _ld and _rd != _ld:
                if _rd > _ld:
                    state[_key] = _rmt[-50:]
                    state["today_top_day"] = _rd
                continue
        _merged = _dedupe_top(_lcl + _rmt)
        _merged.sort(key=lambda e: e.get("ts") or 0)
        state[_key] = _merged[-50:]
    _rdg, _ldg = remote.get("digests") or {}, state.get("digests") or {}
    if _rdg.get("day", "") > _ldg.get("day", ""):
        state["digests"] = _rdg   # پرچم‌های خلاصه‌ی روز تازه‌تر
    elif _rdg.get("day") and _rdg.get("day") == _ldg.get("day"):
        state["digests"] = {"day": _ldg["day"],
                            "morning": bool(_ldg.get("morning") or _rdg.get("morning")),
                            "dinner": bool(_ldg.get("dinner") or _rdg.get("dinner"))}
    week = {}
    for e in list(state.get("stats_week") or []) + list(remote.get("stats_week") or []):
        if isinstance(e, dict) and e.get("day"):
            week[e["day"]] = e
    if week:
        state["stats_week"] = [week[k] for k in sorted(week)[-7:]]
    rk, lk = remote.get("kiosk") or {}, state.get("kiosk") or {}
    if rk.get("day", "") > lk.get("day", ""):
        state["kiosk"] = rk
    print(f"remote state merged: seen {len(local_seen)} -> {len(state['seen'])}")
    return True

def is_quiet_hours():
    t = tehran_now()
    m = t.hour * 60 + t.minute
    return QUIET_START <= m < QUIET_END


def run_once():
    UPLOAD_FAILS[0] = 0
    READ_STATUS.clear()
    AD_STATS.clear()
    RSS_READ.clear()
    RATE_LIMITS[0] = 0
    state = load_state()
    STATE_REF[0] = state
    try:
        load_rules()
    except Exception as ex:
        print("load rules error:", ex)
    RULES_REJECT_STATS["total"] = 0
    RULES_REJECT_STATS["blocked"] = 0
    try:
        _remote = fetch_remote_state()
        if _remote:
            merge_remote_state(state, _remote)
    except Exception as ex:
        print("merge remote state error:", ex)
    if process_commands(state):   # فرمان‌های ادمین (/pause ، /status و ...)
        save_state(state)
    now = time.time()
    # اجرای دستی از دکمه‌ی Run workflow: همه‌چیز؛ اجرای خودکار (mode=auto) طبق زمان‌بندی
    force = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("RUN_MODE", "manual") != "auto"
    th = tehran_now()
    m = th.hour * 60 + th.minute
    day_id = (th - timedelta(hours=8)).strftime("%Y-%m-%d")   # «روز» کانال: ۰۸:۳۰ تا ۰۱:۰۰ بعد
    ks = state.get("kiosk") or {}
    if ks.get("day") != day_id:
        ks = {"day": day_id, "morning": False, "summary": False, "night": False}
    stats = day_stats(state, day_id)
    dg = state.get("digests") or {}
    if dg.get("day") != day_id:
        dg = {"day": day_id, "morning": False, "dinner": False}
        state["digests"] = dg

    only_night = False
    if not force and is_quiet_hours():
        if m < NIGHT_END and not ks["night"]:
            only_night = True   # اجرا دیر شروع شده؛ فقط پیام «شب بخیر» فرستاده می‌شه
        else:
            print("ساعت سکوته (۰۱:۰۰ تا ۰۸:۳۰ تهران)؛ خبری منتشر نمی‌شه.")
            if m < 240 and maybe_report(state, ks, day_id):   # گزارش روزانه (اگه تو دور شب بخیر نرسیده بود)
                save_state(state)
            return "quiet"

    if state.get("paused") and not force:
        print("ارسال متوقف شده (/pause)؛ با /resume ادامه پیدا می‌کنه.")
        return "paused"

    # توی حالت حلقه، خودِ حلقه زمان رو تنظیم می‌کنه؛ پس تحمل تأخیر کوچیکه تا فاصله‌ها نامنظم نشن
    slack = 1 if LOOP_MINUTES > 0 else SLACK_MIN
    run_tg = not only_night and (force or now - state.get("last_tg", 0) >= (TG_EVERY_MIN - slack) * 60)
    # «بقیه‌ی منابع» فقط همراه نوبت کانال‌ها می‌آد، نه جدا (که فاصله‌ها بهم نریزه)
    run_other = not only_night and (force or (run_tg and now - state.get("last_other", 0) >= (OTHER_EVERY_MIN - slack) * 60))

    print(f"run: v={BOT_VERSION} event={os.environ.get('GITHUB_EVENT_NAME')} mode={os.environ.get('RUN_MODE')} "
          f"tehran={th:%H:%M} force={force} run_tg={run_tg} run_other={run_other} only_night={only_night}")
    if not (run_tg or run_other or only_night):
        since = (now - state.get("last_tg", 0)) / 60
        print(f"هنوز موقع اجرا نیست ({since:.0f} دقیقه از آخرین نوبت کانال‌ها گذشته).")
        return "notdue"

    stats["runs"] = stats.get("runs", 0) + 1
    if stats.get("first") is None:
        stats["first"] = f"{th:%H:%M}"
        if not force and 510 <= m < 780 and m - 510 > 30:
            alert("late", f"⚠️ امروز ربات ساعت {th:%H:%M} شروع شد (حدود {m - 510} دقیقه بعد از ۰۸:۳۰).", 0)

    prepare_proxies()
    state["alive_count"] = len(ALIVE)
    state["proxy_total"], state["proxy_checked"] = PROXY_INFO["total"], PROXY_INFO["checked"]
    if ALIVE and len(ALIVE) < FEW_PROXIES:
        alert("fewproxy", f"⚠️ فقط {len(ALIVE)} پروکسی سالم مونده؛ proxies.txt را به‌روز کن.", 24)
    if ADMIN_CHAT_ID and not state.get("admin_hello"):
        if alert("hello", "✅ هشدارهای ربات GodNews24 فعال شد. اگه مشکلی پیش بیاد اینجا خبر می‌دم.", 0):
            state["admin_hello"] = True
    if not ALIVE:
        total = PROXY_INFO["total"]
        alert("noproxy", "⚠️ پروکسی سالمی پیدا نشد؛ فایل proxies.txt را به‌روز کن."
              if total else "⚠️ فایل proxies.txt خالی است و پروکسی ندارم.", 12)
    state.setdefault("last_post", now)
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

    if any(k == "morning" for k, _ in pre):
        state["rejected"] = []   # با «صبح بخیر» کیوسک (اولین پیام روز) لیست ردشده‌های دیروز پاک می‌شه

    # ---- بقیه‌ی منابع (منبع‌های بی‌صدا حذف می‌شن)
    tg_feeds = [f for f in FEEDS if f[1].startswith("tg:") and not source_muted_key(state, f[1])]
    other_feeds = [f for f in FEEDS if not f[1].startswith("tg:") and not source_muted_key(state, f[1])]
    if len(tg_feeds) + len(other_feeds) < len(FEEDS):
        print("muted sources skipped:", state.get("muted_sources"))

    if run_tg:
        cands = collect(tg_feeds, seen, seeded, seed_n=TG_MAX_POSTS)
        n = random.randint(TG_MIN_POSTS, TG_MAX_POSTS)
        chosen = choose(cands, n, seen, recent_sets, kept_sets)
        print(f"کانال‌های تلگرامی: {len(cands)} خبر تازه، {len(chosen)} تا انتخاب شد (سقف {n})")
        _examined = sum(READ_STATUS.values()) + len(cands)
        _blocked_n = sum(1 for e in (state.get("rejected") or []) if e.get("day") == rejected_day() and e.get("why") == "کلمه‌ی ممنوع")
        # ایمنی قوانین: اگه بیش از نصف بررسی‌شده‌ها با کلمه‌ی ممنوع رد شده باشن، لیست قبلی برگرده
        if _examined >= 5:
            _today_blocked = len([e for e in (state.get("rejected") or []) if e.get("day") == rejected_day() and e.get("why") == "کلمه‌ی ممنوع"])
            rules_safety_check(_examined, _today_blocked)
        to_post += chosen
        state["last_tg"] = now
        streak = state.setdefault("empty_streak", {})
        for _cat, _url, _dom in tg_feeds:
            nm = _url[3:]
            if nm in READ_STATUS:
                streak[nm] = streak.get(nm, 0) + 1 if READ_STATUS[nm] == 0 else 0
                if streak[nm] >= EMPTY_STREAK_ALERT:
                    alert(f"empty:{nm}", f"⚠️ خوندن کانال @{nm} {streak[nm]} بار پشت‌سرهم ناموفق بود "
                                        "(پیش‌نمایش عمومی بسته شده یا دسترسی بلاکه).", 6)
        ad_streak = state.setdefault("ad_streak", {})
        for nm, (ads_n, total_n) in AD_STATS.items():
            # آمار ردشده فقط از log_rejected() می‌آد؛ اینجا فقط برای هشدار استفاده می‌شه
            high = total_n >= 8 and ads_n / total_n >= 0.5
            ad_streak[nm] = ad_streak.get(nm, 0) + 1 if high else 0
            if ad_streak[nm] >= 2:
                alert(f"ads:{nm}", f"⚠️ بیشتر از نصف پست‌های @{nm} ({ads_n} از {total_n}) به‌عنوان تبلیغ رد شد. "
                                  "شاید شکل امضای کانال عوض شده.", 12)

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
        rz = state.setdefault("rss_zero", {})
        for _c, _u, _d in other_feeds:
            if _u in RSS_READ:
                rz[_u] = rz.get(_u, 0) + 1 if RSS_READ[_u] == 0 else 0
                if rz[_u] >= 4:
                    alert(f"rss0:{_u}", f"⚠️ منبع {_u} {rz[_u]} نوبت پشت‌سرهم خبری نداد "
                                       "(آدرس RSS عوض شده یا بلاکه).", 168)

    started = time.time()
    try:
        for kind, p in pre:
            LAST_TG_ERROR[0] = ""
            if run_special(kind, p, seen, ks):
                state["last_post"] = time.time()
                count_post(state, "kiosk")
                save_state(state)
            else:
                log_rejected("kiosk", f"خطا در ارسال ({kind})", p.get("text", ""), p.get("post_id"), LAST_TG_ERROR[0])
            time.sleep(3)

        for item in sorted(to_post, key=lambda x: x["ts"]):
            if time.time() - started > RUN_BUDGET_SEC:
                print("زمان این اجرا تموم شد؛ بقیه‌ی خبرها نوبت بعد.")
                break
            LAST_TG_ERROR[0] = ""
            if send(item):
                state["last_post"] = time.time()
                count_post(state, item.get("src", "?"))
                record_top(state, item, day_id)   # برای صبحانه/شام خبری (لیست قیمت ثبت نمی‌شه)
                seen[item["id"]] = None
                recent.append({"t": time.time(), "k": sorted(item["tok"])})
                state["seen"] = list(seen)
                state["titles"] = recent[-400:]
                save_state(state)
                print("posted:", item["title"][:60])
                if str(item["id"]).startswith("tg:"):
                    clear_error(item.get("src", "?"), item["id"][3:])
            else:
                log_rejected(item.get("src", "?"), "خطا در ارسال", item["title"],
                             item["id"][3:] if str(item["id"]).startswith("tg:") else None, LAST_TG_ERROR[0])
            time.sleep(3)

        # صبحانه خبری: ۰۹:۰۰ تا ۱۱:۰۰ تهران، یک بار در روز (خالی باشه رد می‌شه و علامت نمی‌خوره)
        if not only_night and 540 <= m < 660 and not dg.get("morning"):
            try:
                if send_digest(state, "morning", day_id, th):
                    save_state(state)
            except Exception as ex:
                print("morning digest error:", repr(ex))

        # شام خبری (نسخه‌ی i): فقط در همان دوری که «شب بخیر» فرستاده می‌شه،
        # درست قبل از اون — یعنی پیام یکی‌مانده‌به‌آخر. قبلاً ساعت ۲۳:۰۰ به‌تنهایی
        # شام رو می‌فرستاد و بعدش تا شب بخیر خبرهای معمولی می‌اومدن، پس شام
        # یکی‌مانده‌به‌آخر نبود. اگه شب بخیر توی این دور پیدا نشد، شام هم نمی‌ره
        # تا دوری که شب بخیر پیدا بشه؛ توی only_night (اجرای دیرهنگام ۰۱:۰۰ تا
        # ۰۱:۴۰) هم همین‌جا، قبل از شب بخیر، فرستاده می‌شه.
        if not dg.get("dinner") and (post or only_night):
            try:
                if send_digest(state, "dinner", day_id, th):
                    save_state(state)
            except Exception as ex:
                print("dinner digest error:", repr(ex))

        for kind, p in post:
            LAST_TG_ERROR[0] = ""
            if run_special(kind, p, seen, ks):
                state["last_post"] = time.time()
                count_post(state, "kiosk")
                save_state(state)
            else:
                log_rejected("kiosk", f"خطا در ارسال ({kind})", p.get("text", ""), p.get("post_id"), LAST_TG_ERROR[0])
    except Exception as ex:   # هر خطایی بیاد، حافظه ذخیره می‌شه تا خبر تکراری نره
        print("خطا در ارسال:", repr(ex))
        log_rejected("bot", "خطا: برنامه", repr(ex))
        stats["errors"] = stats.get("errors", 0) + 1
        alert("error", f"❌ خطا در ارسال: {repr(ex)[:300]}", 1)
    finally:
        if not only_night and not force:
            check_no_post(state, time.time(), m)
        if not force:
            if morning_time and not only_night:
                if m >= 600 and not ks["morning"]:
                    alert("kiosk_morning", "⚠️ تا ساعت ۱۰ پیام «صبح بخیر» کیوسک پیدا نشد.", 20)
                if m >= 660 and not ks["summary"]:
                    alert("kiosk_summary", "⚠️ تا ساعت ۱۱ پیام «نگاهی گذرا» کیوسک پیدا نشد.", 20)
            if only_night and not ks["night"]:
                alert("kiosk_night", "⚠️ پیام «شب بخیر» کیوسک امشب پیدا نشد.", 20)
        state["upload_fail_runs"] = state.get("upload_fail_runs", 0) + 1 if UPLOAD_FAILS[0] >= 2 else 0
        if state["upload_fail_runs"] >= 3:
            alert("upload", "⚠️ آپلود عکس و فیلم چند دور پشت‌سرهم شکست خورد؛ پست‌ها بدون رسانه می‌رن.", 6)
        if RATE_LIMITS[0] >= 3:
            alert("ratelimit", f"⚠️ تلگرام {RATE_LIMITS[0]} بار «خیلی سریع» جواب داد (محدودیت سرعت).", 6)
        if night_time and (ks["night"] or m >= 90):
            maybe_report(state, ks, day_id)
        state["seen"] = list(seen)
        state["seeded"] = list(seeded)
        state["titles"] = recent[-400:]
        state["kiosk"] = ks
        state["digests"] = dg
        save_state(state)
    if only_night:
        return "quiet" if ks["night"] else "night_wait"

# ====== حالت حلقه: یک اجرای طولانی که هر ۲۰ دقیقه یک‌بار خبر می‌ذاره ======
LOOP_MINUTES = int(os.environ.get("LOOP_MINUTES") or 0)


def is_force_run():
    return os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("RUN_MODE", "manual") != "auto"


def repo_is_public():
    """حلقه فقط برای repository عمومی روشن می‌شه (برای خصوصی ساعت‌های رایگان رو تموم می‌کنه)."""
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo:
        return False
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}",
                         headers={"Authorization": f"Bearer {tok}"} if tok else {}, timeout=15)
        return r.status_code == 200 and r.json().get("private") is False
    except Exception:
        return False


def commit_state():
    """بعد از هر دور، حافظه رو توی گیت‌هاب ذخیره می‌کنه (اگه اجرا وسط کار قطع شد، خبر تکراری نره)."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True)

    try:
        git("config", "user.name", "news-bot")
        git("config", "user.email", "bot@users.noreply.github.com")
        _pull = git("pull", "--rebase", "--autostash")
        if _pull.returncode != 0:
            print("git pull --rebase failed (ignored):", (_pull.stderr or "")[:200])
        git("add", STATE_FILE)
        if os.path.exists(RULES_FILE):
            git("add", RULES_FILE)
        if git("diff", "--cached", "--quiet").returncode != 0:
            git("commit", "-m", "update posted")
            r = git("push")
            if r.returncode != 0:
                print("git push failed:", r.stderr[:200])
    except Exception as ex:
        print("commit error:", repr(ex))


def next_round_time(t0):
    """دور بعدی: ۲۰ دقیقه بعد از آخرین نوبتِ کانال‌ها (حتی اگه بین دو اجرا فاصله افتاده باشه)."""
    last = load_state().get("last_tg") or 0
    nxt = last + TG_EVERY_MIN * 60 if last else t0 + TG_EVERY_MIN * 60
    return max(nxt, time.time() + 30)


def dispatch_next():
    """اجرای بعدی رو خودش صدا می‌زنه (به زمان‌بندی دیرکردیِ گیت‌هاب وابسته نمی‌مونیم)."""
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (os.environ.get("GITHUB_ACTIONS") and repo and tok):
        return
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    wf = os.environ.get("GITHUB_WORKFLOW_REF", "").split("@")[0].rsplit("/", 1)[-1] or "news.yml"
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/dispatches",
                          headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                          json={"ref": ref, "inputs": {"mode": "auto"}}, timeout=20)
        print("اجرای بعدی صدا زده شد:", r.status_code)
        if r.status_code != 204:
            alert("dispatch", f"⚠️ صدا زدن اجرای بعدی ناموفق بود (کد {r.status_code}). "
                              "اگه ربات متوقف شد، Run workflow با mode=auto بزن.", 0)
    except Exception as ex:
        print("dispatch error:", repr(ex))
        alert("dispatch", "⚠️ صدا زدن اجرای بعدی ناموفق بود. اگه ربات متوقف شد، Run workflow با mode=auto بزن.", 0)


def seconds_until_active():
    th = tehran_now()
    m = th.hour * 60 + th.minute
    return max(((QUIET_END - m) % 1440) * 60 - th.second, 30)


def main():
    print(f"نسخه‌ی ربات: {BOT_VERSION}")
    loop_minutes = LOOP_MINUTES
    if loop_minutes > 0 and (is_force_run() or not repo_is_public()):
        if not is_force_run():
            print("repository عمومی نیست؛ حالت حلقه خاموش شد (برای حفظ ساعت‌های رایگان).")
            st_ = load_state()
            STATE_REF[0] = st_
            if alert("loop_off", "⚠️ حالت حلقه خاموش شد چون repository عمومی نیست (یا بررسی‌ش ممکن نبود). "
                                 "ربات فقط با زمان‌بندی گیت‌هاب کار می‌کنه.", 24):
                save_state(st_)
        loop_minutes = 0
    if loop_minutes <= 0:
        run_once()
        return
    end = time.time() + loop_minutes * 60
    while True:
        t0 = time.time()
        status = None
        try:
            status = run_once()
        except Exception as ex:
            print("خطا در این دور:", repr(ex))
            alert("loop_error", f"❌ خطا در یک دور ربات: {repr(ex)[:300]}", 1)
        commit_state()
        if status == "quiet":
            nxt = time.time() + seconds_until_active()
            print("ساعت سکوت؛ ربات بیدار می‌مونه (فرمان‌ها رو می‌خونه) تا ساعت ۰۸:۳۰.")
        elif status == "night_wait":
            nxt = time.time() + 300
        elif status == "paused":
            nxt = time.time() + 120
        else:
            nxt = next_round_time(t0)
        stop = nxt > end + 300           # دور بعدی بعد از پایان این اجراست
        wake = min(nxt, end) if stop else nxt
        wait = wake - time.time()
        if wait > 0:
            print(f"دور بعدی تا {wait / 60:.0f} دقیقه‌ی دیگه.")
        while time.time() < wake:
            time.sleep(min(POLL_SECONDS, max(wake - time.time(), 0)))
            try:
                poll_commands()   # در این فاصله فرمان‌های ادمین هم خونده می‌شه
            except Exception as ex:
                print("command poll error:", repr(ex))
        if stop:
            break
    dispatch_next()


if __name__ == "__main__":
    main()
