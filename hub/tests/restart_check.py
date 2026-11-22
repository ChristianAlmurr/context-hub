#!/usr/bin/env python3
"""A session's state end to end, with real Claude sessions (Haiku, low effort, manual mode) in a throwaway project,
hub-test-throwaway-<n>, made here and removed at the end: why it is in its state, "Done · asks you" and the
asks_as_needs setting in the config's "settings", alive_at while it runs, and the sessions a Mac restart took, resumed
all at once, with a failed one keeping its error.

A restart is played by writing the session's last alive stamp to before the Mac's last start, the way a poll after a
real restart finds it. Runs against a second instance (the six HUB_* variables, see tests/instance.py).
Run: /usr/bin/python3 tests/restart_check.py
"""
import http.client, json, sys, time

from instance import CFG, NAME, OWNER, PORT, STATE, WRITE, answer_first_run, launchd_jobs, quiet_alert, remove_project, sweep, tell
import hub_base as base
import hub_data as hub

fails = 0


def check(label, ok, extra=""):
    global fails
    fails += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:400]}]"), flush=True)


def call(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE if body is not None else OWNER)
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def row(sid):
    return next((s for s in call("GET", "/api/state")[1]["sessions"] if s["id"] == sid), None)


def wait(sid, ok, limit, label):
    end = time.time() + limit
    while time.time() < end:
        r = row(sid)
        if r and ok(r):
            return r
        time.sleep(1)
    check(label, False, {k: (row(sid) or {}).get(k) for k in ("state", "why", "asks", "asking", "said", "alive", "alive_at", "lost")})
    return row(sid)


def set_settings(settings):
    config = json.loads(base.CONFIG.read_text())
    if settings is None:
        config.pop("settings", None)
    else:
        config["settings"] = settings
    base.CONFIG.write_text(json.dumps(config))
    time.sleep(1.6)  # past the server's state cache


def mark_lost(sid):
    """What a poll after a restart finds: the session gone, its stamp from before the Mac started."""
    data = hub.read_alive()
    data["alive"][sid] = hub.boot_time() - 60
    hub.write_alive(data)


sweep()
launchd_before = launchd_jobs()
sids = []
try:
    status, made = call("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", status == 200, made)
    quiet_alert(NAME)
    status, made = call("POST", "/api/sessions", {"project": NAME, "tasks": ["Reply with the single word ready and nothing else."], "model": "haiku", "effort": "low", "mode": "manual"})
    check("a session starts", status == 200, made)
    sid = made["ids"][0]; sids.append(sid)
    answer_first_run(sid)
    done = wait(sid, lambda s: s["state"] == "finished" and "ready" in (s.get("said") or "").lower(), 120, "the first turn finishes")
    if done:
        check("a finished turn says why, by its Stop hook", done["why"].startswith("hook: Stop at "), done.get("why"))
        check("a finished turn that asks nothing has asks false", done["asks"] is False, done.get("asks"))
        check("a running session carries alive_at", isinstance(done.get("alive_at"), (int, float)) and abs(time.time() - done["alive_at"]) < 120, done.get("alive_at"))
        check("a running session is not lost", "lost" not in done, done.get("lost"))

    tell(sid, "Reply with exactly this sentence and nothing else: Shall I write the tests next?")
    asked = wait(sid, lambda s: s["state"] == "finished" and s.get("asks"), 120, "a reply ending in ? is done, with asks")
    if asked:
        check("Done · asks you keeps the question", "tests next?" in asked.get("asking", ""), asked.get("asking"))
        check("its why says the reply ends in ?", asked["why"].endswith("reply ends in ?"), asked.get("why"))
    set_settings({"asks_as_needs": True})
    needs = wait(sid, lambda s: s["state"] == "needs" and s.get("asks"), 20, "with asks_as_needs in the config's settings, it counts as needs")
    set_settings(None)
    wait(sid, lambda s: s["state"] == "finished" and s.get("asks"), 20, "without the setting, it is done again")

    # ── stopped while the Mac is up: not lost ──
    call("POST", f"/api/sessions/{sid}/stop", {})
    gone = wait(sid, lambda s: not s["alive"], 20, "a stopped session ends")
    check("a session stopped while the Mac is up isn't counted as lost", gone and "lost" not in gone and "alive_at" not in gone, gone and {k: gone.get(k) for k in ("lost", "alive_at")})

    # ── the Mac restarts: two sessions were running; one resumes, one can't ──
    status, made = call("POST", "/api/sessions", {"project": NAME, "tasks": ["Reply with the single word two and nothing else."], "model": "haiku", "effort": "low", "mode": "manual"})
    second = made["ids"][0]; sids.append(second)
    answer_first_run(second)
    wait(second, lambda s: s["state"] == "finished" and "two" in (s.get("said") or "").lower(), 120, "the second session's turn finishes")
    call("POST", f"/api/sessions/{second}/stop", {})
    wait(second, lambda s: not s["alive"], 20, "the second session ends")
    mark_lost(sid)
    mark_lost(second)
    lost = wait(sid, lambda s: s.get("lost"), 10, "a session alive before the Mac started is lost")
    check("lost says when it was last seen running", lost and isinstance(lost["lost"]["at"], (int, float)) and lost["lost"]["error"] == "", lost and lost.get("lost"))
    meta_path = STATE / "sessions" / f"{second}.json"
    meta = json.loads(meta_path.read_text())
    meta["folder"] = str(STATE / "a-folder-that-is-gone")
    meta_path.write_text(json.dumps(meta))
    status, res = call("POST", "/api/lost/resume", {})
    check("Resume all resumes the one it can, and says which failed", status == 200 and res.get("resumed") == [sid] and second in res.get("failed", {}), res)
    back = wait(sid, lambda s: s["alive"] and "lost" not in s, 30, "the resumed session runs again, and is no longer lost")
    failed = row(second)
    check("a failed resume stays, with its error", failed and failed.get("lost") and "folder" in failed["lost"]["error"], failed and failed.get("lost"))
    status, res = call("POST", "/api/lost/resume", {"ids": [second]})
    check("resuming one at a time says the same error", status == 200 and second in res.get("failed", {}), res)
    status, res = call("POST", "/api/lost/dismiss", {"ids": [second]})
    check("dismissing forgets it was lost", status == 200 and "lost" not in (row(second) or {}), row(second))
    bare = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    bare.request("POST", "/api/lost/resume", "{}", OWNER)
    check("Resume all without the origin is refused", bare.getresponse().status == 403)
finally:
    try:
        set_settings(None)
        for s in sids:
            call("POST", f"/api/sessions/{s}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before, sorted(set(launchd_jobs()) ^ set(launchd_before)))
print("--- failures:", fails)
sys.exit(1 if fails else 0)
