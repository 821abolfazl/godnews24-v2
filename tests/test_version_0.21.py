# Tests for bot version 2026-11-22-0.21.
# The 2026-11-22 incident: run #737 froze silently in the wait between
# rounds — no new log line, no command reply, no posts, past the 70-minute
# job timeout. The only unbounded blocking calls in the whole bot were the
# git subprocess calls in commit_state() and commit_rules() (every other
# network call already had a timeout). A stalled `git pull` / `git push`
# could therefore freeze the process forever with zero log output.
# Fix: every git call now has timeout=GIT_TIMEOUT_SEC (60s); on timeout the
# bot prints, clears a possibly stale .git/index.lock, and keeps going
# (the state stays on disk, the next commit retries). Also, the return
# codes of config / add / commit are now checked and printed — before,
# a failed `git commit` failed silently (push then "succeeded" with
# nothing to push), which is how the frozen run's posted state never
# reached the repo and the next run re-posted 4 items.
import os
import sys
import io
import json
import shutil
import tempfile
import contextlib
import importlib.util
import subprocess
from unittest.mock import patch

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_CHAT_ID"] = "123"
os.environ["GITHUB_ACTIONS"] = "true"
sys.path.insert(0, "/home/hatch/workspace/godnews24")
os.chdir("/home/hatch/workspace/godnews24")

spec = importlib.util.spec_from_file_location("bot021", "/home/hatch/workspace/godnews24/bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

PASS = []
FAIL = []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""))

check("version is 0.21", bot.BOT_VERSION == "2026-11-22-0.21", bot.BOT_VERSION)
check("git timeout is 60s", getattr(bot, "GIT_TIMEOUT_SEC", None) == 60, getattr(bot, "GIT_TIMEOUT_SEC", None))

bot.PROXY_CHECKED_ONCE[0] = True

ADMIN_MSGS = []
def fake_admin_send(text, reply_markup=None):
    ADMIN_MSGS.append(text)
    return True
bot.admin_send = fake_admin_send

CALLS = []

class Res:
    def __init__(self, rc=0, err=""):
        self.returncode = rc
        self.stderr = err
        self.stdout = ""

def run_ok(cmd, **kw):
    CALLS.append((cmd, kw))
    if cmd[:2] == ["git", "diff"]:
        return Res(1)   # changes staged -> commit + push happen
    return Res(0)

def run_no_changes(cmd, **kw):
    CALLS.append((cmd, kw))
    return Res(0)   # diff --quiet returns 0 -> nothing to commit

def run_timeout_on_pull(cmd, **kw):
    CALLS.append((cmd, kw))
    if cmd[:2] == ["git", "pull"]:
        raise subprocess.TimeoutExpired(cmd, 60)
    return Res(0)

def run_fail_commit(cmd, **kw):
    CALLS.append((cmd, kw))
    if cmd[:2] == ["git", "diff"]:
        return Res(1)
    if cmd[:2] == ["git", "commit"]:
        return Res(1, "fake commit error")
    return Res(0)

def run_fail_add(cmd, **kw):
    CALLS.append((cmd, kw))
    if cmd[:2] == ["git", "diff"]:
        return Res(1)
    if cmd[:2] == ["git", "add"]:
        return Res(1, "fake add error")
    return Res(0)

def run_capture(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()

def verbs(calls):
    return [c[0][1] for c in calls]

# ---- 1. commit_state: normal flow, every git call bounded ----
CALLS.clear()
with patch("subprocess.run", side_effect=run_ok):
    out = run_capture(bot.commit_state)
check("commit_state normal: commit+push called",
      "commit" in verbs(CALLS) and "push" in verbs(CALLS), verbs(CALLS))
check("commit_state normal: every git call has timeout=60",
      CALLS and all(c[1].get("timeout") == 60 for c in CALLS), CALLS)
check("commit_state normal: no failure printed",
      "failed" not in out and "timed out" not in out, out)

# ---- 2. commit_state: no changes -> no commit, no push ----
CALLS.clear()
with patch("subprocess.run", side_effect=run_no_changes):
    out = run_capture(bot.commit_state)
check("commit_state no changes: no commit/push",
      "commit" not in verbs(CALLS) and "push" not in verbs(CALLS), verbs(CALLS))

# ---- 3. commit_state: hung git -> bot survives, lock cleared ----
tmp = tempfile.mkdtemp()
os.makedirs(os.path.join(tmp, ".git"))
open(os.path.join(tmp, ".git", "index.lock"), "w").write("stale")
old_cwd = os.getcwd()
os.chdir(tmp)
try:
    CALLS.clear()
    with patch("subprocess.run", side_effect=run_timeout_on_pull):
        out = run_capture(bot.commit_state)
    check("commit_state timeout: returns normally (no raise)", True)
    check("commit_state timeout: timeout printed", "timed out" in out, out)
    check("commit_state timeout: stale index.lock removed",
          not os.path.exists(os.path.join(tmp, ".git", "index.lock")))
    check("commit_state timeout: hung call had timeout=60",
          CALLS and all(c[1].get("timeout") == 60 for c in CALLS), CALLS)
finally:
    os.chdir(old_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 4. commit_state: failed commit is loud, push skipped ----
CALLS.clear()
with patch("subprocess.run", side_effect=run_fail_commit):
    out = run_capture(bot.commit_state)
check("commit_state failed commit: failure printed", "git commit failed" in out, out)
check("commit_state failed commit: push skipped", "push" not in verbs(CALLS), verbs(CALLS))

# ---- 5. commit_state: failed add is loud, commit skipped ----
CALLS.clear()
with patch("subprocess.run", side_effect=run_fail_add):
    out = run_capture(bot.commit_state)
check("commit_state failed add: failure printed", "git add failed" in out, out)
check("commit_state failed add: commit skipped", "commit" not in verbs(CALLS), verbs(CALLS))

# ---- 6. commit_rules: normal flow, every git call bounded ----
CALLS.clear()
with patch("subprocess.run", side_effect=run_ok):
    out = run_capture(bot.commit_rules)
check("commit_rules normal: commit+push called",
      "commit" in verbs(CALLS) and "push" in verbs(CALLS), verbs(CALLS))
check("commit_rules normal: every git call has timeout=60",
      CALLS and all(c[1].get("timeout") == 60 for c in CALLS), CALLS)

# ---- 7. commit_rules: hung git -> bot survives, lock cleared ----
tmp = tempfile.mkdtemp()
os.makedirs(os.path.join(tmp, ".git"))
open(os.path.join(tmp, ".git", "index.lock"), "w").write("stale")
old_cwd = os.getcwd()
os.chdir(tmp)
try:
    CALLS.clear()
    with patch("subprocess.run", side_effect=run_timeout_on_pull):
        out = run_capture(bot.commit_rules)
    check("commit_rules timeout: returns normally (no raise)", True)
    check("commit_rules timeout: timeout printed", "timed out" in out, out)
    check("commit_rules timeout: stale index.lock removed",
          not os.path.exists(os.path.join(tmp, ".git", "index.lock")))
finally:
    os.chdir(old_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

# ---- 8. commit_rules: failed commit is loud, push skipped ----
CALLS.clear()
with patch("subprocess.run", side_effect=run_fail_commit):
    out = run_capture(bot.commit_rules)
check("commit_rules failed commit: failure printed", "rules git commit failed" in out, out)
check("commit_rules failed commit: push skipped", "push" not in verbs(CALLS), verbs(CALLS))

# ---- 9. the incident scenario: a /status arrives while git hangs ----
# poll_commands must still answer the admin and save the state; the hung
# git must not swallow the reply or freeze the loop.
tmp = tempfile.mkdtemp()
tmp_state = {"seen": [], "seeded": [], "titles": [], "tg_offset": 0, "last_post_ids": []}
with open(os.path.join(tmp, "posted.json"), "w", encoding="utf-8") as f:
    json.dump(tmp_state, f, ensure_ascii=False)
old_cwd = os.getcwd()
os.chdir(tmp)
try:
    ADMIN_MSGS.clear()
    CALLS.clear()
    class Resp:
        def __init__(self, j):
            self._j = j
        def json(self):
            return self._j
    real_get = bot.requests.get
    bot.requests.get = lambda url, params=None, timeout=None: Resp(
        {"ok": True, "result": [{"update_id": 99, "message": {"message_id": 1, "chat": {"id": 123}, "text": "/status"}}]})
    try:
        with patch("subprocess.run", side_effect=run_timeout_on_pull):
            out = run_capture(bot.poll_commands)
    finally:
        bot.requests.get = real_get
    check("poll_commands hung git: /status still answered",
          len(ADMIN_MSGS) == 1 and "ربات" in ADMIN_MSGS[0], ADMIN_MSGS)
    check("poll_commands hung git: timeout printed, no raise", "timed out" in out, out)
    with open(os.path.join(tmp, "posted.json"), encoding="utf-8") as f:
        saved = json.load(f)
    check("poll_commands hung git: state saved to disk (offset advanced)",
          saved.get("tg_offset") == 100, saved.get("tg_offset"))
finally:
    os.chdir(old_cwd)
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    raise SystemExit(1)
