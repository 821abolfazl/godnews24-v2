# Tests for bot version 2026-11-13-0.09: kiosk "summary" (breakfast) is
# detected ONLY from the FIRST line of the post.
#
# Bug (2026-11-17): the sports-newspapers post ("صفحه نخست روزنامه‌های ورزشی"
# with the lede "نگاهی گذرا به مهم‌ترین تیترها...") was classified as
# "summary" because kiosk_kind matched "نگاهی گذرا" ANYWHERE in the text.
# Being newer than the real overnight roundup ("🍁 نگاهی گذرا به اخبار
# منتشرشده طی شب گذشته"), pick() chose it, so the sports papers went out
# as the breakfast, the ✅ tick was set, and the real roundup never went out.
import os
import sys
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot009", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

def post(text, n_photos=0):
    return {"text": text, "media": [("photo", f"f{i}") for i in range(n_photos)]}

REAL_SUMMARY = "🍁 نگاهی گذرا به اخبار منتشرشده طی شب گذشته\n🔴 آویگدور لیبرمن، رئیس حزب اسرائیل خانه ما، پایان‌دادن به دوران نتانیاهو را هدف اعلام کرد.\n🔴 گزارش‌ها از فیلترشدن پیام‌رسان تلگرام در عراق خبر می‌دهند."
SPORTS_PAPERS = "🔴 صفحه نخست روزنامه‌های ورزشی سه‌شنبه ۲۶ آبان ۱۴۰۵\n🔸 نگاهی گذرا به مهم‌ترین تیترها و عناوین صفحه نخست روزنامه‌های ورزشی امروز کشور."
MAIN_PAPERS = "🔴 صفحه نخست روزنامه‌های سه‌شنبه ۲۶ آبان ۱۴۰۵\n🔸 نگاهی به تیترها و صفحه نخست روزنامه‌های امروز کشور."
MORNING = "🔴 #صبح_است_ساقیا\nگاهی بزرگ‌ترین دستاورد یک روز، پاسخی‌ست که پس از سال‌ها پرسش پیدا می‌شود.\n🍁 صبح بخیر"
NIGHT = "🔴 #شبهای_روشن\nدر سکوت دلنشین شب، ماه آرام‌تر از همیشه می‌تابد.\n🍁 شب بخیر"

# ---- 1. the 2026-11-17 bug, reproduced with the real texts ----
check("bug: real overnight roundup is summary", bot.kiosk_kind(post(REAL_SUMMARY, 1)) == "summary", bot.kiosk_kind(post(REAL_SUMMARY, 1)))
check("bug: sports papers is NOT summary", bot.kiosk_kind(post(SPORTS_PAPERS, 7)) != "summary", bot.kiosk_kind(post(SPORTS_PAPERS, 7)))
check("bug: sports papers is papers", bot.kiosk_kind(post(SPORTS_PAPERS, 7)) == "papers", bot.kiosk_kind(post(SPORTS_PAPERS, 7)))
check("bug: main papers is papers", bot.kiosk_kind(post(MAIN_PAPERS, 9)) == "papers", bot.kiosk_kind(post(MAIN_PAPERS, 9)))

# ---- 2. pick() chooses the real roundup now ----
# (same rule as run_once's pick: newest post whose kind is "summary")
kposts = [
    {"id": "tg:kioskkhabar/239503", "ts": 1000, "sp": bot.kiosk_kind(post(REAL_SUMMARY, 1))},
    {"id": "tg:kioskkhabar/239517", "ts": 2000, "sp": bot.kiosk_kind(post(SPORTS_PAPERS, 7))},
]
cands = [p for p in kposts if p["sp"] == "summary"]
picked = max(cands, key=lambda x: x["ts"]) if cands else None
check("pick: real roundup is picked, not sports papers",
      picked is not None and picked["id"] == "tg:kioskkhabar/239503", picked)

# ---- 3. first-line rule, edge cases ----
check("edge: 'نگاهی گذرا' only in a later line is not summary",
      bot.kiosk_kind(post("🔴 خبر مهم امروز\n🔸 نگاهی گذرا به اتفاقات دیروز.", 0)) is None)
check("edge: first line with leading blank lines still counts",
      bot.kiosk_kind(post("\n\n🍁 نگاهی گذرا به اخبار دیشب\n🔴 خبر اول.", 1)) == "summary")
check("edge: summary first line without the emoji still counts",
      bot.kiosk_kind(post("نگاهی گذرا به اخبار منتشرشده طی شب گذشته\n🔴 خبر اول.", 0)) == "summary")

# ---- 4. morning / night / papers unchanged ----
check("unchanged: morning still morning", bot.kiosk_kind(post(MORNING, 1)) == "morning", bot.kiosk_kind(post(MORNING, 1)))
check("unchanged: night still night", bot.kiosk_kind(post(NIGHT, 1)) == "night", bot.kiosk_kind(post(NIGHT, 1)))
check("unchanged: plain news is None", bot.kiosk_kind(post("🔴 آتش‌سوزی نفتکش در تنگه هرمز\n🔸 روابط عمومی نیروی دریایی ارتش اعلام کرد.", 1)) is None)

# ---- 5. retitle agrees with the new classification ----
check("retitle: real roundup gets the breakfast title",
      bot.retitle_summary(REAL_SUMMARY).split("\n")[0] == bot.SUMMARY_TITLE, bot.retitle_summary(REAL_SUMMARY).split("\n")[0])
check("retitle: sports papers keeps its own title",
      bot.retitle_summary(SPORTS_PAPERS).split("\n")[0].startswith("🔴 صفحه نخست روزنامه‌های ورزشی"),
      bot.retitle_summary(SPORTS_PAPERS).split("\n")[0])

check("version: is 0.09", bot.BOT_VERSION == "2026-11-13-0.09", bot.BOT_VERSION)

print()
print(f"Passed: {len(PASS)}, Failed: {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
