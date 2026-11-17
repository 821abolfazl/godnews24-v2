# Tests for bot version 2026-11-13-0.08: /marker — a per-leading-emoji
# paragraph marker, set with /marker <lead> <marker> (e.g. /marker ⚽ 🔻),
# stored in rules.txt under [ایموجی پاراگراف], shown in /rules, and applied
# in decide(). /marker <lead> alone removes the override (back to default).
# The /marker button sits before /remove, /strip and /unstrip in the menu.
import os
import sys
import time
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot008", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

sent = []
bot.admin_send = lambda text, reply_markup=None: sent.append(text) or True
bot.proxy_parts = lambda: ('<a href="https://t.me/proxy?server=1.1.1.1&port=443&secret=x">پروکسی</a>😉',
                           'پروکسی😉 https://t.me/proxy?server=1.1.1.1&port=443&secret=x')
bot.save_state = lambda state: None
bot.save_rules_file = lambda: None
bot.commit_rules = lambda: None
bot.tg = lambda method, files=None, **data: True

def fresh_state():
    st = {"rejected": [], "stats": {}}
    bot.STATE_REF[0] = st
    return st

def reset_rules():
    bot.DYNAMIC_RULES["markers"] = []
    sent.clear()

# ---- 1. rules parsing: the markers section ----
text = ("[ممنوع]\nکلمه‌بد\n\n[🔴]\nسپاه\n\n[ایموجی پاراگراف]\n"
        "🔴 🔻\n⚽ 🔹\n⛽️ 🔸\n🔴\n🔴 🔻 🔹\nسلام 🔻\n🔴 سلام\n\n[پاک شود از آخر متن]\n/ ایسنا\n")
parsed = bot.parse_rules_text(text)
check("parse: markers section read", parsed.get("markers") == ["🔴 🔻", "⚽ 🔹", "⛽ 🔸"], parsed.get("markers"))
check("parse: bad marker lines skipped", len(parsed.get("markers", [])) == 3, parsed.get("markers"))
check("parse: other sections still read", parsed.get("red") == ["سپاه"] and parsed.get("strip_end") == ["/ ایسنا"], parsed)
check("parse: markers key exists when section absent",
      bot.parse_rules_text("[🔴]\nسپاه\n").get("markers") == [], bot.parse_rules_text("[🔴]\nسپاه\n"))

formatted = bot.format_rules_text(parsed)
check("format: markers section present", "[ایموجی پاراگراف]\n🔴 🔻\n⚽ 🔹\n⛽ 🔸" in formatted, formatted)
check("format: markers section before strip_end",
      formatted.index("[ایموجی پاراگراف]") < formatted.index("[پاک شود از آخر متن]"), formatted)

# ---- 2. marker_overrides ----
reset_rules()
bot.DYNAMIC_RULES["markers"] = ["🔴 🔻", "⚽ 🔹", "⛽️ 🔸"]
check("overrides: dict built", bot.marker_overrides() == {"🔴": "🔻", "⚽": "🔹", "⛽": "🔸"}, bot.marker_overrides())
check("overrides: empty when no markers", (bot.DYNAMIC_RULES.__setitem__("markers", []), bot.marker_overrides())[1] == {}, bot.marker_overrides())

# ---- 3. decide() applies the override ----
def mk(title, category="general", red_src=False):
    return {"title": title, "paras": [], "summary": "", "category": category, "red_src": red_src}

reset_rules()
lead, mark = bot.decide(mk("پرسپولیس قهرمان شد", "sports"))
check("decide: football default marker is 🔹", (lead, mark) == ("⚽", "🔹"), (lead, mark))
bot.DYNAMIC_RULES["markers"] = ["⚽ 🔻"]
lead, mark = bot.decide(mk("پرسپولیس قهرمان شد", "sports"))
check("decide: football override marker is 🔻", (lead, mark) == ("⚽", "🔻"), (lead, mark))
reset_rules()
lead, mark = bot.decide(mk("خبر مهم", red_src=True))
check("decide: red default marker is 🔻", (lead, mark) == ("🔴", "🔻"), (lead, mark))
bot.DYNAMIC_RULES["markers"] = ["🔴 🔸"]
lead, mark = bot.decide(mk("خبر مهم", red_src=True))
check("decide: red override marker is 🔸", (lead, mark) == ("🔴", "🔸"), (lead, mark))
reset_rules()
lead, mark = bot.decide(mk("هوای تهران امروز آفتابی است"))
check("decide: weather post keeps default 🔹 marker", (lead, mark) == ("🌤️", "🔹"), (lead, mark))

# ---- 4. /marker command ----
reset_rules()
st = fresh_state()
bot.handle_command(st, "/marker", "/marker ⚽ 🔻")
check("marker: set adds the line", bot.DYNAMIC_RULES.get("markers") == ["⚽ 🔻"], bot.DYNAMIC_RULES.get("markers"))
check("marker: set confirms", "✅" in sent[-1] and "⚽" in sent[-1] and "🔻" in sent[-1], sent[-1])
bot.handle_command(st, "/marker", "/marker ⚽ 🔹")
check("marker: set again replaces, no duplicate", bot.DYNAMIC_RULES.get("markers") == ["⚽ 🔹"], bot.DYNAMIC_RULES.get("markers"))
bot.handle_command(st, "/marker", "/marker 🔴 🔸")
check("marker: second emoji adds a line", bot.DYNAMIC_RULES.get("markers") == ["⚽ 🔹", "🔴 🔸"], bot.DYNAMIC_RULES.get("markers"))
bot.handle_command(st, "/marker", "/marker ⚽")
check("marker: single emoji removes the override", bot.DYNAMIC_RULES.get("markers") == ["🔴 🔸"], bot.DYNAMIC_RULES.get("markers"))
check("marker: remove confirms", "✅" in sent[-1] and "پیش‌فرض" in sent[-1], sent[-1])
bot.handle_command(st, "/marker", "/marker ⚽")
check("marker: removing a missing override says so", "تنظیم نشده" in sent[-1], sent[-1])
bot.handle_command(st, "/marker", "/marker سلام")
check("marker: non-emoji rejected", "مثال: /marker" in sent[-1], sent[-1])
bot.handle_command(st, "/marker", "/marker 🔴 🔻 🔹")
check("marker: three tokens rejected", "مثال: /marker" in sent[-1], sent[-1])
bot.handle_command(st, "/marker", "/marker")
check("marker: no args rejected", "مثال: /marker" in sent[-1], sent[-1])
check("marker: rejected inputs leave rules alone", bot.DYNAMIC_RULES.get("markers") == ["🔴 🔸"], bot.DYNAMIC_RULES.get("markers"))

# ---- 5. /rules shows the markers ----
reset_rules()
bot.DYNAMIC_RULES["markers"] = ["🔴 🔻", "⚽ 🔹"]
bot.handle_command(st, "/rules")
check("rules: markers section shown", "ایموجی پاراگراف (2): 🔴 🔻، ⚽ 🔹" in sent[-1], sent[-1])

# ---- 6. placement: before /remove, /strip, /unstrip ----
labels = [label for label, _ in bot.MENU_BUTTONS]
check("menu: marker button exists", "🔻 نشانه‌ی پاراگراف" in labels, labels)
check("menu: marker before remove", labels.index("🔻 نشانه‌ی پاراگراف") < labels.index("➖ حذف از ایموجی"), labels)
check("menu: marker before strip", labels.index("🔻 نشانه‌ی پاراگراف") < labels.index("✂️ پاک‌شونده اضافه"), labels)
check("menu: marker before unstrip", labels.index("🔻 نشانه‌ی پاراگراف") < labels.index("↩️ پاک‌شونده حذف"), labels)
check("menu: /delete, /test, /help still the last three",
      [cmd for _, cmd in bot.MENU_BUTTONS[-3:]] == ["/delete", "/test", "/help"], bot.MENU_BUTTONS[-3:])
check("help: /marker line before /remove", bot.HELP_TEXT.index("/marker") < bot.HELP_TEXT.index("/remove"), bot.HELP_TEXT)
check("known: /marker is a known command", "/marker" in bot.KNOWN_COMMANDS, bot.KNOWN_COMMANDS)
check("prompt: /marker asks for lead + marker", "/marker" in bot.MENU_PROMPTS and "🔴 🔻" in bot.MENU_PROMPTS["/marker"], bot.MENU_PROMPTS.get("/marker"))
check("version: is 0.08", bot.BOT_VERSION == "2026-11-13-0.08", bot.BOT_VERSION)

print()
print(f"Passed: {len(PASS)}, Failed: {len(FAIL)}")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
