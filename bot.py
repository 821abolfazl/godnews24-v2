import os
import re
import json
import html
import time
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

# (دسته, آدرس RSS)
# دسته‌ها: general, politics, economy, sports, tech
FEEDS = [
    ("general", "https://www.isna.ir/rss"),
    ("general", "https://www.mehrnews.com/rss"),
    ("general", "https://www.irna.ir/rss"),
    ("general", "https://www.farsnews.ir/rss"),
    ("general", "https://www.khabaronline.ir/rss"),
    ("general", "https://parsi.euronews.com/rss?format=mrss"),
    ("general", "https://rss.dw.com/xml/rss-per-all"),
    ("economy", "https://donya-e-eqtesad.com/rss"),
    ("economy", "https://www.eghtesadnews.com/rss"),
    ("sports", "https://www.varzesh3.com/rss/all"),
    ("tech", "https://digiato.com/feed"),
    ("tech", "https://www.zoomit.ir/feed/"),
]

# ====== دسته‌بندی و ایموجی ======
FLASH_KW = ["فوری", "عاجل", "انفجار", "حمله", "جنگ", "موشک", "زلزله", "کشته", "ترور"]
POLITICS_KW = ["رئیس‌جمهور", "رییس‌جمهور", "رهبر انقلاب", "مجلس", "دولت", "وزیر",
               "تحریم", "مذاکره", "شورای امنیت", "ترامپ", "نتانیاهو", "بایدن",
               "سیاست", "انتخابات", "سپاه", "پزشکیان", "اسرائیل", "آمریکا"]
ECON_KW = ["دلار", "یورو", "طلا", "سکه", "بورس", "تورم", "بانک", "ارز", "نفت",
           "اقتصاد", "بازار", "قیمت", "رمزارز", "بیت‌کوین", "بیت کوین", "مسکن",
           "یارانه", "بنزین", "صادرات", "واردات"]


def pick_emoji(category, title):
    flash = any(k in title for k in FLASH_KW)
    if flash:
        return "🔴"
    if category == "economy" or any(k in title for k in ECON_KW):
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
    if not os.path.exists(STATE_FILE):
        return {"seen": [], "seeded": []}
    with open(STATE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):  # فرمت قدیمی
        return {"seen": data, "seeded": []}
    return data


def save_state(state):
    state["seen"] = state["seen"][-4000:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


# ====== دریافت خبر ======
def fetch_feed(category, url):
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
            summary = clean(e.get("summary", ""), 350)
            if summary == title or len(summary) < 20:
                summary = ""
            ts = time.mktime(e.published_parsed) if e.get("published_parsed") else 0
            image, video = find_media(e)
            items.append({"id": uid, "title": title, "summary": summary,
                          "category": category, "image": image, "video": video, "ts": ts})
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
def build_text(item, with_summary=True):
    esc = html.escape
    parts = [f"{pick_emoji(item['category'], item['title'])} <b>{esc(item['title'])}</b>"]
    if with_summary and item["summary"]:
        parts.append(esc(item["summary"]))
    link = random.choice(ALIVE) if ALIVE else PROXY_LINK
    if link:
        parts.append(f'<a href="{html.escape(link, quote=True)}">پروکسی</a>😉')
    else:
        parts.append("پروکسی😉")
    parts.append(CHANNEL)
    return "\n\n".join(parts)


def tg(method, **data):
    data.update({"chat_id": CHANNEL, "parse_mode": "HTML"})
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=60)
    if not r.ok:
        print("  telegram error:", method, r.status_code, r.text[:150])
    return r.ok


def send(item):
    caption = build_text(item)
    if len(caption) > 1000:
        caption = build_text(item, with_summary=False)
    if item["video"] and tg("sendVideo", video=item["video"], caption=caption):
        return True
    if item["image"] and tg("sendPhoto", photo=item["image"], caption=caption):
        return True
    return tg("sendMessage", text=build_text(item), disable_web_page_preview="true")


def main():
    prepare_proxies()
    state = load_state()
    seen = set(state["seen"])
    seeded = set(state["seeded"])
    candidates = {}

    for category, url in FEEDS:
        items = fetch_feed(category, url)
        if not items:
            continue
        if url not in seeded:
            # منبع جدید: فقط آخرین خبر منتشر می‌شه، بقیه به‌عنوان قدیمی ثبت می‌شن
            for i in items[:-1]:
                seen.add(i["id"])
            fresh = [items[-1]]
            seeded.add(url)
        else:
            fresh = items
        for i in fresh:
            if i["id"] not in seen:
                candidates[i["id"]] = i

    to_post = sorted(candidates.values(), key=lambda x: x["ts"])[:MAX_PER_RUN]
    for item in to_post:
        if send(item):
            seen.add(item["id"])
            print("posted:", item["title"][:60])
        time.sleep(3)

    state["seen"] = list(seen)
    state["seeded"] = list(seeded)
    save_state(state)


if __name__ == "__main__":
    main()
