# Tests for bot version 2026-11-21-0.18.
# tg() retries transient failures once (reported 2026-11-20 21:19/21:20 — two
# AloNews photos failed with sendPhoto ReadTimeout on upload, then 400
# "failed to get HTTP URL content" by URL, and only the text went out):
# 1. Network error (ReadTimeout/connection) -> one retry after 5s; success on
#    the retry returns True and does NOT count as an upload failure.
# 2. Network error twice -> False after exactly 2 posts; with files it counts
#    one upload failure (circuit breaker), without files it does not.
# 3. 400 "failed to get HTTP URL content" -> one retry after 5s; success on
#    the retry returns True.
# 4. Same 400 twice -> False after exactly 2 posts (no endless retry).
# 5. Other 400s (e.g. wrong file identifier) -> False after exactly 1 post,
#    no retry, no sleep.
# 6. 429 -> one retry after retry_after (as before); a second 429 -> False
#    after exactly 2 posts (no infinite loop); RATE_LIMITS counts once.
# 7. Success first try -> True, 1 post, no sleep.
# 8. send_single with upload_first (the exact incident shape): download ok,
#    upload ReadTimeout once, retry succeeds -> True, photo sent.
# 9. Version pin 0.18.
import os
import sys
import time
import importlib.util

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot018", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

import requests

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

check("version is 0.18", bot.BOT_VERSION == "2026-11-21-0.18", bot.BOT_VERSION)

# ---- fake requests.post + fake sleep ----
REAL_POST = requests.post
REAL_SLEEP = time.sleep
POST_CALLS = []
POST_SCRIPT = []
SLEEPS = []

class FakeResp:
    def __init__(self, status, text="", result=None, params=None):
        self.status_code = status
        self.text = text
        self._result = result
        self._params = params
    @property
    def ok(self):
        return 200 <= self.status_code < 300
    def json(self):
        d = {"ok": self.ok}
        if self._result is not None:
            d["result"] = self._result
        if self._params is not None:
            d["parameters"] = self._params
        return d

def ok_resp(mid=555):
    return FakeResp(200, '{"ok":true}', result={"message_id": mid})

def fake_post(url, data=None, files=None, timeout=None):
    POST_CALLS.append((url, data, files))
    action = POST_SCRIPT.pop(0)
    if isinstance(action, Exception):
        raise action
    return action

bot.requests.post = fake_post
bot.time.sleep = lambda s: SLEEPS.append(s)
bot.alert = lambda *a, **k: None
bot.admin_send = lambda text, reply_markup=None: True

def reset():
    POST_CALLS.clear()
    POST_SCRIPT.clear()
    SLEEPS.clear()
    bot.RATE_LIMITS[0] = 0
    bot.UPLOAD_FAILS[0] = 0
    bot.LAST_TG_ERROR[0] = ""
    bot.LAST_TG_IDS.clear()

# ---- 1. network error then success ----
reset()
POST_SCRIPT.extend([requests.ReadTimeout("timed out"), ok_resp()])
check("retry: ReadTimeout then ok -> True", bot.tg("sendPhoto", photo="https://x/y.jpg") is True)
check("retry: ReadTimeout then ok -> 2 posts", len(POST_CALLS) == 2, len(POST_CALLS))
check("retry: ReadTimeout then ok -> no upload fail counted", bot.UPLOAD_FAILS[0] == 0, bot.UPLOAD_FAILS[0])
check("retry: ReadTimeout then ok -> slept 5s once", SLEEPS == [5], SLEEPS)
check("retry: ReadTimeout then ok -> id recorded", bot.LAST_TG_IDS == [555], bot.LAST_TG_IDS)

# ---- 2. network error twice ----
reset()
POST_SCRIPT.extend([requests.ReadTimeout("t1"), requests.ReadTimeout("t2")])
check("retry: ReadTimeout twice with files -> False",
      bot.tg("sendPhoto", files={"photo": ("file.jpg", b"x")}) is False)
check("retry: ReadTimeout twice with files -> 2 posts", len(POST_CALLS) == 2, len(POST_CALLS))
check("retry: ReadTimeout twice with files -> 1 upload fail", bot.UPLOAD_FAILS[0] == 1, bot.UPLOAD_FAILS[0])
reset()
POST_SCRIPT.extend([requests.ConnectionError("down"), requests.ConnectionError("down")])
check("retry: ConnectionError twice no files -> False",
      bot.tg("sendMessage", text="hi") is False)
check("retry: ConnectionError twice no files -> no upload fail", bot.UPLOAD_FAILS[0] == 0, bot.UPLOAD_FAILS[0])

# ---- 3. 400 fetch URL content then success ----
reset()
POST_SCRIPT.extend([FakeResp(400, '{"ok":false,"error_code":400,"description":"Bad Request: failed to get HTTP URL content"}'),
                    ok_resp()])
check("retry: 400 fetch-URL then ok -> True", bot.tg("sendPhoto", photo="https://x/y.jpg") is True)
check("retry: 400 fetch-URL then ok -> 2 posts", len(POST_CALLS) == 2, len(POST_CALLS))
check("retry: 400 fetch-URL then ok -> slept 5s once", SLEEPS == [5], SLEEPS)

# ---- 4. same 400 twice ----
reset()
POST_SCRIPT.extend([FakeResp(400, '{"ok":false,"error_code":400,"description":"Bad Request: failed to get HTTP URL content"}'),
                    FakeResp(400, '{"ok":false,"error_code":400,"description":"Bad Request: failed to get HTTP URL content"}')])
check("retry: 400 fetch-URL twice -> False", bot.tg("sendPhoto", photo="https://x/y.jpg") is False)
check("retry: 400 fetch-URL twice -> exactly 2 posts", len(POST_CALLS) == 2, len(POST_CALLS))

# ---- 5. other 400: no retry ----
reset()
POST_SCRIPT.extend([FakeResp(400, '{"ok":false,"error_code":400,"description":"Bad Request: wrong file identifier"}'),
                    ok_resp()])
check("retry: other 400 -> False", bot.tg("sendPhoto", photo="bad-id") is False)
check("retry: other 400 -> exactly 1 post", len(POST_CALLS) == 1, len(POST_CALLS))
check("retry: other 400 -> no sleep", SLEEPS == [], SLEEPS)

# ---- 6. 429 then success / twice ----
reset()
POST_SCRIPT.extend([FakeResp(429, '{"ok":false,"error_code":429}', params={"retry_after": 7}),
                    ok_resp()])
check("retry: 429 then ok -> True", bot.tg("sendMessage", text="hi") is True)
check("retry: 429 then ok -> 2 posts", len(POST_CALLS) == 2, len(POST_CALLS))
check("retry: 429 then ok -> rate limit counted once", bot.RATE_LIMITS[0] == 1, bot.RATE_LIMITS[0])
check("retry: 429 then ok -> slept retry_after", SLEEPS == [7], SLEEPS)
reset()
POST_SCRIPT.extend([FakeResp(429, '{"ok":false,"error_code":429}', params={"retry_after": 3}),
                    FakeResp(429, '{"ok":false,"error_code":429}', params={"retry_after": 3}),
                    ok_resp()])
check("retry: 429 twice -> False", bot.tg("sendMessage", text="hi") is False)
check("retry: 429 twice -> exactly 2 posts, no loop", len(POST_CALLS) == 2, len(POST_CALLS))
check("retry: 429 twice -> rate limit counted once", bot.RATE_LIMITS[0] == 1, bot.RATE_LIMITS[0])

# ---- 7. success first try ----
reset()
POST_SCRIPT.extend([ok_resp()])
check("retry: ok first try -> True", bot.tg("sendMessage", text="hi") is True)
check("retry: ok first try -> 1 post, no sleep", len(POST_CALLS) == 1 and SLEEPS == [],
      (len(POST_CALLS), SLEEPS))

# ---- 8. send_single upload_first, incident shape ----
reset()
bot.download = lambda url, limit=30 * 1024 * 1024, max_seconds=60: b"fake-photo-bytes"
POST_SCRIPT.extend([requests.ReadTimeout("upload timed out"), ok_resp(777)])
check("retry: send_single upload timeout then ok -> True",
      bot.send_single("photo", "https://cdn.example.com/p.jpg", "caption", True) is True)
check("retry: send_single upload timeout then ok -> 2 posts", len(POST_CALLS) == 2, len(POST_CALLS))
check("retry: send_single upload timeout then ok -> id recorded", bot.LAST_TG_IDS == [777], bot.LAST_TG_IDS)

bot.requests.post = REAL_POST
bot.time.sleep = REAL_SLEEP

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
