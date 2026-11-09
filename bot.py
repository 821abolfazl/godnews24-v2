import os
import re
import json
import html
import time
import requests
import feedparser

# منابع خبری RSS (هر کدام را می‌توانی حذف یا اضافه کنی)
FEEDS = [
    "https://feeds.bbci.co.uk/persian/rss.xml",
    "https://parsi.euronews.com/rss?format=mrss",
]

TOKEN = os.environ["BOT_TOKEN"]          # از GitHub Secrets خوانده می‌شود
CHANNEL = os.environ.get("CHANNEL", "@GodNews24")
STATE_FILE = "posted.json"
MAX_PER_RUN = 5      # حداکثر تعداد پست در هر اجرا
FIRST_RUN_POSTS = 3  # در اولین اجرا فقط چند خبر آخر منتشر شود


def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen[-2000:], f, ensure_ascii=False)


def clean(text, limit=300):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text).strip()
    return text[:limit] + "…" if len(text) > limit else text


def fetch_entries():
    items = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                uid = e.get("id") or e.get("link")
                if not uid or not e.get("title"):
                    continue
                ts = time.mktime(e.published_parsed) if e.get("published_parsed") else 0
                items.append({
                    "id": uid,
                    "title": clean(e.title, 200),
                    "summary": clean(e.get("summary", "")),
                    "link": e.get("link", ""),
                    "ts": ts,
                })
        except Exception as ex:
            print("feed error:", url, ex)
    items.sort(key=lambda x: x["ts"])  # قدیمی به جدید
    return items


def send(item):
    parts = [f"<b>{html.escape(item['title'])}</b>"]
    if item["summary"] and item["summary"] != item["title"]:
        parts.append(html.escape(item["summary"]))
    parts.append(f'🔗 <a href="{html.escape(item["link"])}">ادامه خبر</a>')
    parts.append(CHANNEL)
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHANNEL,
            "text": "\n\n".join(parts),
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        },
        timeout=30,
    )
    print(r.status_code, item["title"][:50])
    return r.ok


def main():
    seen = load_seen()
    items = fetch_entries()
    first_run = seen is None
    seen = seen or []

    new = [i for i in items if i["id"] not in seen]

    if first_run:
        # بقیه را بدون ارسال ثبت می‌کنیم تا کانال پر از خبر قدیمی نشود
        to_post = new[-FIRST_RUN_POSTS:]
        for i in new:
            seen.append(i["id"])
        for i in to_post:
            send(i)
            time.sleep(3)
    else:
        for i in new[:MAX_PER_RUN]:
            if send(i):
                seen.append(i["id"])
            time.sleep(3)

    save_seen(seen)


if __name__ == "__main__":
    main()
