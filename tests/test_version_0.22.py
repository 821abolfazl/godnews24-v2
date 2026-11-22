# Tests for bot version 2026-11-22-0.22.
# Two bugs reported 2026-11-22 (19:36):
# 1. Leading sources were deleted: a post starting with «به گزارش خبرگزاری
#    تسنیم، ...» or «تسنیم: ...» lost its source, though the agreed rule was
#    that only a source at the END of the post is removed. Cause: SOURCE_RULES
#    «به گزارش/به نقل از X»، «خبرنگار/خبرگزاری X» and «^X:» were unanchored,
#    so they matched at the start too (and strip_sources runs per line, so
#    the ^ rule hit every paragraph). Fix: the «^X:» rule is gone; the
#    «به گزارش/خبرگزاری X» and «(X)» rules are anchored to the end.
#    Trailing sources («منبع: تسنیم»، «... - تسنیم») are still stripped.
# 2. /send posted a pasted post as-is: if it carried a source ID
#    (@username, t.me link, trailing «منبع: ...») the ID went to the channel.
#    Cause: the /send text branch and _send_caption never cleaned the text
#    (strip_sources is only used by the automatic news flow), and there was
#    no rule for @username / bare t.me links at all. Fix: clean_send_text
#    (strip_sources per line + ID rules, paragraphs kept) is used by both
#    the /send text branch and _send_caption; own @GodNews24 / t.me/GodNews24
#    are never stripped.
# 3. Version pin 0.22.
import os
import sys
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot022", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

check("version is 0.22", bot.BOT_VERSION == "2026-11-22-0.22", bot.BOT_VERSION)

# ---- 1. leading source stays ----
check("lead: «به گزارش خبرگزاری تسنیم، ...» می‌ماند",
      bot.strip_sources("به گزارش خبرگزاری تسنیم، انفجار در تهران رخ داد.") ==
      "به گزارش خبرگزاری تسنیم، انفجار در تهران رخ داد.",
      bot.strip_sources("به گزارش خبرگزاری تسنیم، انفجار در تهران رخ داد."))
check("lead: «تسنیم: ...» می‌ماند",
      bot.strip_sources("تسنیم: انفجار در تهران رخ داد.").startswith("تسنیم:"),
      bot.strip_sources("تسنیم: انفجار در تهران رخ داد."))
check("lead: «خبرگزاری تسنیم: ...» می‌ماند",
      bot.strip_sources("خبرگزاری تسنیم: انفجار در تهران رخ داد.").startswith("خبرگزاری تسنیم:"),
      bot.strip_sources("خبرگزاری تسنیم: انفجار در تهران رخ داد."))
check("lead: «به نقل از تسنیم، ...» می‌ماند",
      bot.strip_sources("به نقل از تسنیم، قیمت دلار افزایش یافت.").startswith("به نقل از تسنیم"),
      bot.strip_sources("به نقل از تسنیم، قیمت دلار افزایش یافت."))
check("lead: تیتر «تسنیم: ...» در clean می‌ماند",
      bot.clean("تسنیم: انفجار در تهران رخ داد.", 200).startswith("تسنیم:"),
      bot.clean("تسنیم: انفجار در تهران رخ داد.", 200))
check("lead: پاراگراف «به گزارش تسنیم، ...» در clean_paras می‌ماند",
      bot.clean_paras("به گزارش تسنیم، انفجار رخ داد.\nپاراگراف دوم اینجاست.") ==
      ["به گزارش تسنیم، انفجار رخ داد.", "پاراگراف دوم اینجاست."],
      bot.clean_paras("به گزارش تسنیم، انفجار رخ داد.\nپاراگراف دوم اینجاست."))
check("lead: «به نقل از یک منبع: ...» (FT) هنوز کامل می‌ماند",
      "سنتکام" in bot.clean("فایننشال تایمز به نقل از یک منبع: فرماندهی مرکزی آمریکا (سنتکام) خبر داد", 200),
      bot.clean("فایننشال تایمز به نقل از یک منبع: فرماندهی مرکزی آمریکا (سنتکام) خبر داد", 200))

# ---- 1b. trailing source still stripped ----
check("trail: «منبع: تسنیم» آخر متن پاک می‌شود",
      bot.clean("متن خبر مهم است. منبع: تسنیم", 200) == "متن خبر مهم است.",
      bot.clean("متن خبر مهم است. منبع: تسنیم", 200))
check("trail: «منبع: خبرگزاری فارس» آخر متن پاک می‌شود",
      bot.clean("متن خبر مهم است. منبع: خبرگزاری فارس", 200) == "متن خبر مهم است.",
      bot.clean("متن خبر مهم است. منبع: خبرگزاری فارس", 200))
check("trail: «- تسنیم» آخر متن پاک می‌شود",
      bot.clean("انفجار در تهران رخ داد - تسنیم", 200) == "انفجار در تهران رخ داد",
      bot.clean("انفجار در تهران رخ داد - تسنیم", 200))
check("trail: «به گزارش تسنیم» آخر متن پاک می‌شود",
      bot.clean("انفجار در تهران رخ داد به گزارش تسنیم", 200) == "انفجار در تهران رخ داد",
      bot.clean("انفجار در تهران رخ داد به گزارش تسنیم", 200))
check("trail: «(تسنیم)» آخر متن پاک می‌شود",
      bot.clean("انفجار در تهران رخ داد (تسنیم)", 200) == "انفجار در تهران رخ داد",
      bot.clean("انفجار در تهران رخ داد (تسنیم)", 200))
check("trail: «(تسنیم)» وسط متن می‌ماند",
      "(تسنیم)" in bot.clean("انفجار (تسنیم) در تهران رخ داد و تلفات داشت", 200),
      bot.clean("انفجار (تسنیم) در تهران رخ داد و تلفات داشت", 200))

# ---- 2. /send: ID stripping ----
check("send: «@AloNews» آخر متن پاک می‌شود",
      "@AloNews" not in bot.clean_send_text("خبر مهم رخ داد.\n\n@AloNews")
      and "خبر مهم رخ داد." in bot.clean_send_text("خبر مهم رخ داد.\n\n@AloNews"),
      bot.clean_send_text("خبر مهم رخ داد.\n\n@AloNews"))
check("send: لینک «https://t.me/AloNews/123» پاک می‌شود",
      "t.me" not in bot.clean_send_text("خبر مهم رخ داد.\nhttps://t.me/AloNews/123"),
      bot.clean_send_text("خبر مهم رخ داد.\nhttps://t.me/AloNews/123"))
check("send: لینک «t.me/AloNews/123» بدون https هم پاک می‌شود",
      "t.me" not in bot.clean_send_text("خبر مهم رخ داد.\nt.me/AloNews/123"),
      bot.clean_send_text("خبر مهم رخ داد.\nt.me/AloNews/123"))
check("send: «منبع: تسنیم» آخر متن پاک می‌شود",
      bot.clean_send_text("خبر مهم رخ داد.\nمنبع: تسنیم") == "خبر مهم رخ داد.",
      bot.clean_send_text("خبر مهم رخ داد.\nمنبع: تسنیم"))
check("send: «@GodNews24» خودمان پاک نمی‌شود",
      "@GodNews24" in bot.clean_send_text("خبر مهم رخ داد.\n@GodNews24"),
      bot.clean_send_text("خبر مهم رخ داد.\n@GodNews24"))
check("send: «t.me/GodNews24/123» خودمان پاک نمی‌شود",
      "t.me/GodNews24" in bot.clean_send_text("خبر مهم رخ داد.\nt.me/GodNews24/123"),
      bot.clean_send_text("خبر مهم رخ داد.\nt.me/GodNews24/123"))
check("send: پاراگراف‌بندی حفظ می‌شود",
      bot.clean_send_text("پاراگراف اول اینجاست.\n\nپاراگراف دوم اینجاست.") ==
      "پاراگراف اول اینجاست.\n\nپاراگراف دوم اینجاست.",
      bot.clean_send_text("پاراگراف اول اینجاست.\n\nپاراگراف دوم اینجاست."))
check("send: منبع اول خبر در /send هم می‌ماند",
      bot.clean_send_text("به گزارش تسنیم، انفجار رخ داد.").startswith("به گزارش تسنیم"),
      bot.clean_send_text("به گزارش تسنیم، انفجار رخ داد."))
check("send: کپشن رسانه آیدی را پاک می‌کند و @GodNews24 را نگه می‌دارد",
      "@AloNews" not in bot._send_caption("خبر مهم.\n@AloNews")
      and "@GodNews24" in bot._send_caption("خبر مهم.\n@AloNews"),
      bot._send_caption("خبر مهم.\n@AloNews"))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
