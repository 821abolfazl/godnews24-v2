import os
import re
import json
import html
import time
from datetime import datetime
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
MAX_PER_RUN = 8

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
DOMESTIC_CHANCE = 0.3   # فقط در حدود ۳۰٪ اجراها یک خبر داخلی منتشر می‌شه
DEDUP_HOURS = 8         # خبرهای شبیه به هم در این بازه تکراری حساب می‌شن

# ====== دسته‌بندی و ایموجی ======
FLASH_KW = ["فوری", "عاجل", "انفجار", "حمله", "جنگ", "موشک", "زلزله", "کشته", "ترور"]
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


def pick_emoji(category, title):
    # ورزشی و فناوری و معمولی: 🔵
    if category in ("sports", "tech") or any(k in title for k in SPORT_KW):
        return "🔵"
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
    "CY": ["قبرس"], "BG": ["بلغارستان"], "HR": ["کرواسی"], "PA": ["پاناما"],
}
_L = "\u0600-\u06FF\u200c"
COUNTRY_RE = []
for _code, _names in COUNTRIES.items():
    _alt = "|".join(re.escape(n) for n in sorted(_names, key=len, reverse=True))
    COUNTRY_RE.append((_code, re.compile(
        rf"(?<![{_L}])(?:{_alt})(?:\u200c?(?:های|ها|یی|ایی|ای|ی)){{0,2}}(?![{_L}])")))
NOT_COUNTRY = ["دریای عمان", "اقیانوس هند", "آذربایجان شرقی", "آذربایجان غربی",
               "خلیج فارس", "تنگه هرمز"]


def flags_for(title, limit=2):
    if re.search("[\U0001F1E6-\U0001F1FF]", title):
        return ""  # خودش پرچم داره
    t = title.replace("ي", "ی").replace("ك", "ک")
    for bad in NOT_COUNTRY:
        t = t.replace(bad, " ")
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
    text = item["title"] + " " + item["summary"][:80]
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[^\w\s]", " ", text)
    return {w for w in text.split() if len(w) >= 3}


def is_dup(tok, others):
    if not tok:
        return False
    for o in others:
        union = len(tok | o)
        if union and len(tok & o) / union >= 0.5:
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


def fetch_tg(category, name, domestic):
    items = []
    try:
        from bs4 import BeautifulSoup
        r = requests.get(f"https://t.me/s/{name}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        for box in soup.select("div.tgme_widget_message"):
            post_id = box.get("data-post")
            body = box.select_one(".tgme_widget_message_text")
            if not post_id or not body:
                continue
            for br in body.find_all("br"):
                br.replace_with("\n")
            text = clean_tg(body.get_text())
            lines = [l for l in text.split("\n") if l.strip()]
            if not lines or len(text) < 15:
                continue
            title = clean(lines[0], 200)
            paras = [p for p in clean_paras("\n".join(lines[1:]), 700) if p != title]
            summary = " ".join(paras)
            if not title:
                continue
            image, video = None, None
            a = box.select_one("a.tgme_widget_message_photo_wrap")
            if a:
                m = re.search(r"url\('([^']+)'\)", a.get("style", ""))
                image = m.group(1) if m else None
            v = box.select_one("video")
            if v and str(v.get("src", "")).startswith("http"):
                video = v["src"]
            t = box.select_one("time")
            ts = 0
            if t and t.get("datetime"):
                try:
                    ts = datetime.fromisoformat(t["datetime"]).timestamp()
                except ValueError:
                    pass
            items.append({"id": "tg:" + post_id, "title": title, "summary": summary, "paras": paras,
                          "category": category, "domestic": domestic,
                          "image": image, "video": video, "ts": ts})
    except Exception as ex:
        print("telegram channel error:", name, ex)
    items.sort(key=lambda x: x["ts"])
    print(f"{len(items):3d} items  tg:{name}")
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
        with socket.create_connection((host, port), timeout=4):
            return True
    except Exception:
        return False


def prepare_proxies(want=10, max_checks=60):
    links = load_proxies()
    random.shuffle(links)
    for link in links[:max_checks]:
        if proxy_alive(link):
            ALIVE.append(link)
            if len(ALIVE) >= want:
                break
    print(f"proxies: {len(links)} in file, {len(ALIVE)} alive")


# ====== ارسال ======
MARKER = {"🔴": "🔻", "🟡": "🔶", "🔵": "🔷"}


def build_text(item, max_len=4000):
    esc = html.escape
    base = pick_emoji(item["category"], item["title"])
    marker = MARKER[base]
    flags = flags_for(item["title"])
    if is_oil_price(item["title"]):
        lead = "🛢️"          # قیمت نفت: فقط همین ایموجی
        if base == "🔵":
            marker = "🔶"
    elif flags:
        lead = flags          # اگه پرچم هست، ایموجی دسته‌بندی گذاشته نمی‌شه
    else:
        lead = base
    first = f"{lead} <b>{esc(item['title'])}</b>"

    link = random.choice(ALIVE) if ALIVE else PROXY_LINK
    if link:
        proxy = f'<a href="{html.escape(link, quote=True)}">پروکسی</a>😉'
    else:
        proxy = "پروکسی😉"
    tail = [proxy, CHANNEL]

    paras = list(item.get("paras") or [])
    mark = len(paras) >= 2   # فقط خبرِ چندپاراگرافی علامت می‌گیره

    def assemble(ps):
        body = [f"{marker} {esc(p)}" if mark else esc(p) for p in ps]
        return "\n\n".join([first] + body + tail)

    text = assemble(paras)
    while len(text) > max_len and paras:
        paras.pop()
        text = assemble(paras)
    return text


def tg(method, **data):
    data.update({"chat_id": CHANNEL, "parse_mode": "HTML"})
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=60)
    if not r.ok:
        print("  telegram error:", method, r.status_code, r.text[:150])
    return r.ok


def send(item):
    caption = build_text(item, max_len=1000)
    if item["video"] and tg("sendVideo", video=item["video"], caption=caption):
        return True
    if item["image"] and tg("sendPhoto", photo=item["image"], caption=caption):
        return True
    return tg("sendMessage", text=build_text(item), disable_web_page_preview="true")


def main():
    prepare_proxies()
    state = load_state()
    seen = dict.fromkeys(state["seen"])   # ترتیب حفظ می‌شه
    seeded = set(state["seeded"])
    now = time.time()
    recent = [t for t in state["titles"] if now - t["t"] < DEDUP_HOURS * 3600]
    candidates = {}

    for category, url, domestic in FEEDS:
        items = fetch_feed(category, url, domestic)
        if not items:
            continue
        if url not in seeded:
            # منبع جدید: فقط آخرین خبر منتشر می‌شه، بقیه به‌عنوان قدیمی ثبت می‌شن
            for i in items[:-1]:
                seen[i["id"]] = None
            fresh = [items[-1]]
            seeded.add(url)
        else:
            fresh = items
        for i in fresh:
            if i["id"] not in seen:
                candidates[i["id"]] = i

    allc = list(candidates.values())

    # خبرهای داخلی: خیلی کم
    domestic = sorted([i for i in allc if i["domestic"]], key=lambda x: -x["ts"])
    picked = domestic[:MAX_DOMESTIC_PER_RUN] if random.random() < DOMESTIC_CHANCE else []
    for i in domestic:
        if i not in picked:
            seen[i["id"]] = None
    pool = sorted([i for i in allc if not i["domestic"]], key=lambda x: x["ts"]) + picked

    # حذف خبرهای تکراری (با خبرهای اخیر و با همدیگه)
    recent_sets = [set(t["k"]) for t in recent]
    kept_sets, final = [], []
    for item in pool:
        tok = tokens_of(item)
        if is_dup(tok, recent_sets) or is_dup(tok, kept_sets):
            seen[item["id"]] = None
            print("duplicate skipped:", item["title"][:50])
            continue
        item["tok"] = tok
        kept_sets.append(tok)
        final.append(item)

    to_post = sorted(final, key=lambda x: x["ts"])[:MAX_PER_RUN]
    for item in to_post:
        if send(item):
            seen[item["id"]] = None
            recent.append({"t": time.time(), "k": sorted(item["tok"])})
            print("posted:", item["title"][:60])
        time.sleep(3)

    state["seen"] = list(seen)
    state["seeded"] = list(seeded)
    state["titles"] = recent[-300:]
    save_state(state)


if __name__ == "__main__":
    main()
