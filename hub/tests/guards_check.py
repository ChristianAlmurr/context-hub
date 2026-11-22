#!/usr/bin/env python3
"""Offline checks of guards that touch folders the hub doesn't own. No Claude session, and no hub but one this script
runs in itself on a spare loopback port.

- The hub never runs git or jj in a repo listed in hub_base.NO_VCS, or anywhere inside one.
- A Steering save writes every repo of a store or none of them, and refuses when their blocks differ.
- Deleting a session moves only that session's own files, from the folders they belong in, to the Trash, ends only its
  own tmux session, and refuses anything else. The home folder, its Trash and the kit's state are a temporary folder
  here, so nothing real is moved.
- Approving a fix, rejecting a need and running the fixer are the person's: refused without the owner's login, from
  another origin and as a GET; a need only the person can do can't be approved; the fixer is never started twice or
  with nothing approved. The store is a throwaway one in the temporary home; no fixer and no Claude is started.
Run: /usr/bin/python3 tests/guards_check.py (with the six HUB_* variables of a second instance, as for the other tests)
"""
import asyncio, http.client, json, os, shutil, stat, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hub_base as base
import hub_data as hub
import hub_diff

fails = 0


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{extra}]"), flush=True)
    fails += 0 if ok else 1


# ── repos the hub never runs git or jj in ──
if not base.NO_VCS:  # nothing listed in this hub's config: check the rule on two made-up entries
    base.NO_VCS = (base.HOME / "projects" / "partner-repo", base.HOME / "projects" / "company-monorepo")
for repo in base.NO_VCS:
    for where in (repo, repo / "apps" / "inner", Path("~") / repo.relative_to(base.HOME)):
        done = base.run("git", "-C", where, "status")
        check(f"git -C {where} never runs", done.returncode == 128 and "never runs git" in done.stderr, done.stderr)
    check(f"git run in {repo.name} as its working folder never runs", base.run("git", "status", cwd=repo).returncode == 128)
    check(f"jj -R {repo.name} never runs", base.run("jj", "-R", repo, "log").returncode == 128)
    check(f"the diff reader treats {repo.name} as no repo", hub_diff.git(str(repo), "status").returncode == 128 and hub_diff.numstat(str(repo)) is None)
here = Path(__file__).resolve().parent.parent
check("a repo not on the list still runs git", base.run("git", "-C", here, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true")
check("a folder beside a listed one is not caught by its name", not base.off_limits(base.NO_VCS[-1].parent / (base.NO_VCS[-1].name + "-other")))

# ── Steering: every repo or none ──
place = Path(tempfile.mkdtemp(prefix="steering."))
try:
    repos = []
    for name in ("one", "two", "three"):
        folder = place / name / ".claude" / "commands"
        folder.mkdir(parents=True)
        (folder / "dream.md").write_text(f"# Dream for {name}\n\nSteps.\n\n## Steering (edit per project)\n- Matters here: the old thing.\n")
        repos.append(str(place / name))
    dream = lambda repo: (Path(repo) / ".claude" / "commands" / "dream.md").read_text()
    opened = hub.sha("- Matters here: the old thing.")
    hub.save_steering(repos, "- Matters here: the new thing.\n", opened)
    blocks = {dream(r).split("## Steering", 1)[1] for r in repos}
    check("a save writes the same block into every repo", len(blocks) == 1 and "the new thing" in blocks.pop() and all(dream(r).startswith(f"# Dream for {Path(r).name}") for r in repos))
    try:
        hub.save_steering(repos, "- Matters here: a stale save.\n", opened)
        check("a save from a stale copy is refused", False)
    except base.Refused:
        check("a save from a stale copy is refused, and nothing changes", all("the new thing" in dream(r) for r in repos))
    current = hub.sha("- Matters here: the new thing.")
    odd = Path(repos[2]) / ".claude" / "commands" / "dream.md"
    odd.write_text(odd.read_text().replace("the new thing", "something else"))
    try:
        hub.save_steering(repos, "- Matters here: overwrite.\n", current)
        check("blocks that differ between repos are refused", False)
    except base.Refused as said:
        check("blocks that differ between repos are refused, and nothing is written", "isn't the same" in str(said) and "overwrite" not in "".join(dream(r) for r in repos))
    odd.write_text(odd.read_text().replace("something else", "the new thing"))
    gone = Path(repos[1]) / ".claude" / "commands" / "dream.md"
    kept = gone.read_text()
    gone.unlink()
    try:
        hub.save_steering(repos, "- Matters here: half.\n", current)
        check("a repo without dream.md stops the save", False)
    except base.Refused:
        check("a repo without dream.md stops the save before any repo is written", all("half" not in dream(r) for r in (repos[0], repos[2])))
    gone.write_text(kept)
    locked = Path(repos[2]) / ".claude" / "commands"
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)  # the third folder can't take a new file
    try:
        hub.save_steering(repos, "- Matters here: never half.\n", current)
        check("a folder that can't be written stops the save", False)
    except base.Refused:
        check("a folder that can't be written leaves every repo as it was", all("never half" not in dream(r) for r in repos)
              and not any(p.name.endswith(".hub-tmp") for r in repos for p in (Path(r) / ".claude" / "commands").iterdir()))
    finally:
        locked.chmod(stat.S_IRWXU)
finally:
    shutil.rmtree(place, ignore_errors=True)

# ── deleting a session: through the hub's own request handler, with a temporary home, Trash and kit state ──
import server  # noqa: E402  (reads this instance's config; serves nothing until asked below)

home = Path(tempfile.mkdtemp(prefix="delete-home.", dir=f"/private/tmp/claude-{os.getuid()}"))
real = (hub.HOME, hub.TRASH, hub.kit.HOME, hub.kit.KIT_STATE)
made_ids = []
loop = asyncio.new_event_loop()
try:
    hub.HOME, hub.TRASH, hub.kit.HOME, hub.kit.KIT_STATE = home, home / ".Trash", home, home / "kit-state"
    (home / ".Trash").mkdir()
    projects = home / ".claude" / "projects" / "-tmp-throwaway"
    projects.mkdir(parents=True)
    (home / "kit-state" / "sessions" / "hub-test-delete").mkdir(parents=True)
    srv = loop.run_until_complete(asyncio.start_server(server.handle, "127.0.0.1", 0))
    port = srv.sockets[0].getsockname()[1]
    threading.Thread(target=loop.run_forever, daemon=True).start()
    OWNER = {"Host": server.APP_HOST, "Tailscale-User-Login": server.OWNER}
    WRITE = {**OWNER, "Origin": server.ORIGIN, "Content-Type": "application/json"}

    def call(method, path, headers, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        c.request(method, path, json.dumps(body) if body is not None else None, headers)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")

    def fake(title, closing=False, claude_id=None):
        """A session the hub knows, made of files only: its record in the state folder, a transcript with a subagent
        folder in Claude Code's place, the hub's copy of it and an upload."""
        sid = os.urandom(4).hex()
        made_ids.append(sid)
        claude_id = claude_id or "%08x-0000-4000-8000-%012x" % (int(sid, 16), int(time.time()))
        transcript = projects / f"{claude_id}.jsonl"
        transcript.write_text('{"type":"user"}\n')
        (projects / claude_id / "subagents").mkdir(parents=True)
        (projects / claude_id / "subagents" / "agent-a1.jsonl").write_text("{}\n")
        meta = {"id": sid, "project": "hub-test-delete", "repo": str(home), "title": title, "kind": "claude", "created": time.time() - 3600,
                "folder": str(home), "transcript": str(transcript), "claude_session": claude_id, **({"closing": True} if closing else {})}
        (hub.META / f"{sid}.json").write_text(json.dumps(meta))
        (hub.EVENTS / f"{sid}.json").write_text(json.dumps({"transcript": str(transcript), "state": "ended"}))
        (hub.RECORDS / sid).mkdir(parents=True, exist_ok=True)
        (hub.RECORDS / sid / "transcript.jsonl").write_text("{}\n")
        (hub.UPLOADS / sid).mkdir(parents=True, exist_ok=True)
        (hub.UPLOADS / sid / "shot.png").write_bytes(b"png")
        return sid, transcript

    sid, transcript = fake("Throwaway to delete")
    # refusals: who asks, how, and for what
    check("delete without the owner's login is Not yours", call("POST", f"/api/sessions/{sid}/delete", {"Host": server.APP_HOST, "Origin": server.ORIGIN, "Content-Type": "application/json"}, {}) == (403, {"error": "Not yours."}))
    check("delete from another origin is refused", call("POST", f"/api/sessions/{sid}/delete", {**WRITE, "Origin": "https://example.com"}, {})[0] == 403)
    check("delete is not a GET", call("GET", f"/api/sessions/{sid}/delete", OWNER)[0] == 404)
    for bad in ("../../etc", "%2e%2e%2f%2e%2e%2fetc", "ABCDEF12", "abcdef1", "abcdef123", "abcdef12%0a", "abcdef12%2f..", "*"):
        status, said = call("POST", f"/api/sessions/{bad}/delete", WRITE, {})
        check(f"delete of {bad!r} is refused in plain words", (status, said.get("error")) in ((409, "That isn't a session."), (404, "Not found")), f"{status} {said}")
    gone_id = "0000aaaa" if "0000aaaa" not in made_ids else "0000bbbb"
    check("delete of a session the hub doesn't know is refused", call("POST", f"/api/sessions/{gone_id}/delete", WRITE, {}) == (409, {"error": "That session doesn't exist."}))
    closing, closing_file = fake("Closing one", closing=True)
    check("a session that is closing is refused, and nothing moves", call("POST", f"/api/sessions/{closing}/delete", WRITE, {})[0] == 409 and closing_file.exists() and (hub.META / f"{closing}.json").exists())
    # what the dialog is told, from the kit's own record
    (home / "kit-state" / "hub-test-delete.json").write_text(json.dumps({"last_dream": int(time.time()) - 1800, "last_reason": "", "checked": None, "verdict": None, "tries": [], "reminded": None}))
    (home / "kit-state" / "sessions" / "hub-test-delete" / f"{transcript.stem}.md").write_text("session: x\n")
    status, told = call("GET", f"/api/sessions/{sid}/deleting", OWNER)
    check("the dialog is told the session, its size, that it isn't running, and what the kit has", status == 200 and told["title"] == "Throwaway to delete" and not told["alive"] and told["size"] and told["uploads"] == 1 and told["record"]
          and told["kit"]["read"] == "part" and told["kit"]["archive"].endswith(f"sessions/hub-test-delete/{transcript.stem}.md"), str(told))
    (home / "kit-state" / "hub-test-delete.json").write_text(json.dumps({"last_dream": int(time.time()), "tries": []}))
    for path in (transcript, hub.RECORDS / sid / "transcript.jsonl"):
        os.utime(path, (time.time() - 60, time.time() - 60))
    check("a session that ended before the last dream reads as read", call("GET", f"/api/sessions/{sid}/deleting", OWNER)[1]["kit"]["read"] == "all")
    (home / "kit-state" / "hub-test-delete.json").unlink()
    check("with no record of a dream, the kit is said to have read none of it", call("GET", f"/api/sessions/{sid}/deleting", OWNER)[1]["kit"] == {"read": "none", "dreamed": None, "archive": told["kit"]["archive"], "keep_days": 180})
    # paths the hub recorded that aren't the session's own transcript are never moved
    outside = home / "secret.jsonl"; outside.write_text("keep\n")
    named = projects / "not-a-session.jsonl"; named.write_text("keep\n")
    linked = projects / "11111111-2222-4333-8444-555555555555.jsonl"; linked.symlink_to(outside)
    for i, wrong in enumerate((str(outside), str(projects / ".." / ".." / ".." / "secret.jsonl"), str(named), str(linked))):
        odd, odd_file = fake(f"Odd path {i}")
        meta = json.loads((hub.META / f"{odd}.json").read_text())
        meta["transcript"] = wrong
        (hub.META / f"{odd}.json").write_text(json.dumps(meta))
        (hub.EVENTS / f"{odd}.json").write_text(json.dumps({"transcript": wrong}))
        status, done = call("POST", f"/api/sessions/{odd}/delete", WRITE, {})
        check(f"a recorded transcript path that isn't one ({Path(wrong).name}) is left where it is", status == 200 and outside.read_text() == "keep\n" and named.exists() and linked.is_symlink()
              and odd_file.exists() and "secret.jsonl" not in done["moved"], f"{status} {done}")
    # the happy path
    status, done = call("POST", f"/api/sessions/{sid}/delete", WRITE, {})
    folder = home / ".Trash" / Path(done.get("trash", "x")).name
    check("delete answers with what moved and where", status == 200 and done["ok"] and not done["stopped"] and done["moved"] == [transcript.name, transcript.stem + "/", "hub record/", "uploads/"], f"{status} {done}")
    check("the transcript and its subagents are in one new folder in the Trash", (folder / transcript.name).exists() and (folder / transcript.stem / "subagents" / "agent-a1.jsonl").exists() and not transcript.exists() and not (projects / transcript.stem).exists())
    check("the hub's copy, the uploads and the session's record went with them, with a note of where each was",
          (folder / "hub record" / "transcript.jsonl").exists() and (folder / "uploads" / "shot.png").exists() and (folder / "hub session.json").exists() and str(transcript) in (folder / "Where these came from.txt").read_text())
    check("nothing of it is left in the hub's state", not any(p.exists() for p in (hub.META / f"{sid}.json", hub.EVENTS / f"{sid}.json", hub.RECORDS / sid, hub.UPLOADS / sid)))
    check("it is gone from the list, as after a restart (the list is read from the state folder)", sid not in {s["id"] for s in hub.sessions_state()})
    check("the kit's archive copy is kept", (home / "kit-state" / "sessions" / "hub-test-delete" / f"{transcript.stem}.md").exists())
    check("a second delete is refused", call("POST", f"/api/sessions/{sid}/delete", WRITE, {}) == (409, {"error": "That session doesn't exist."}))
    twice = {"id": "abcd0123", "title": "Same name"}
    first, second = hub._trash_folder(twice), hub._trash_folder(twice)
    check("two deletes of the same name in the same second get two folders", first != second and first.is_dir() and second.is_dir())
    # a running session: only its own tmux session is ended, by its exact name
    live, live_file = fake("Running one")
    hub.tmux("new-session", "-d", "-s", f"hub-{live}", "sleep 600")
    hub.tmux("new-session", "-d", "-s", f"hub-{live}-decoy", "sleep 600")
    status, told = call("GET", f"/api/sessions/{live}/deleting", OWNER)
    check("the dialog is told it is running", status == 200 and told["alive"], str(told))
    status, done = call("POST", f"/api/sessions/{live}/delete", WRITE, {})
    sessions = hub.tmux_sessions()
    check("a running session is stopped first, and only it", status == 200 and done["stopped"] and f"hub-{live}" not in sessions and f"hub-{live}-decoy" in sessions and not live_file.exists(), f"{status} {done} {sessions}")
    hub.tmux("kill-session", "-t", f"=hub-{live}-decoy")
finally:
    loop.call_soon_threadsafe(loop.stop)
    hub.HOME, hub.TRASH, hub.kit.HOME, hub.kit.KIT_STATE = real
    for sid in made_ids:
        hub.tmux("kill-session", "-t", f"=hub-{sid}")
        hub.tmux("kill-session", "-t", f"=hub-{sid}-decoy")
        for path in (hub.META / f"{sid}.json", hub.EVENTS / f"{sid}.json"):
            path.unlink(missing_ok=True)
        for path in (hub.RECORDS / sid, hub.UPLOADS / sid):
            shutil.rmtree(path, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)

# ── the fixer: approve, reject and run are the person's, through the kit's own commands ──
home = Path(tempfile.mkdtemp(prefix="fix-home.", dir=f"/private/tmp/claude-{os.getuid()}"))
name, real_stores = "hub-test-fix", hub.STORES
loop = asyncio.new_event_loop()
try:
    hub.STORES = home / "agent-memory"
    store, repo = hub.STORES / name, home / "repo"
    (store / "dreams").mkdir(parents=True)
    repo.mkdir()
    (store / "ORG.md").write_text("# Principles\n")
    (store / "roots.txt").write_text(f"{repo}\n")
    base.run("git", "-C", repo, "init", "-q")
    agent, yours, third = ("The README names a script that is gone · evidence: s-1 · fix: repo — drop the line about old.sh",
                           "The deploy key has expired · evidence: s-2 · yours: a credential",
                           "The changelog is a year out of date · evidence: s-3 · fix: repo — add the missing heading")
    entry = lambda text, at: {"text": text, "key": text.split(" · evidence: ")[0].casefold(), "from": "2026-11-10-proposal.md", "at": at, "last": "2026-11-10-proposal.md", "seen": at, "said": 1,
                              **({"who": "agent", "repo": "repo", "change": text.rsplit(" — ", 1)[1]} if " · fix: " in text else {"who": "you", "why": "a credential"})}
    (store / "dreams" / "needs.json").write_text(json.dumps({"needs": [entry(agent, 1), entry(yours, 2), entry(third, 3)]}))
    base.run("git", "-C", store, "init", "-q")
    base.run("git", "-C", store, "add", "-A")
    base.run("git", "-C", store, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
    srv = loop.run_until_complete(asyncio.start_server(server.handle, "127.0.0.1", 0))
    port = srv.sockets[0].getsockname()[1]
    threading.Thread(target=loop.run_forever, daemon=True).start()
    states = lambda: {e["text"]: e.get("state", "open") for e in json.loads((store / "dreams" / "needs.json").read_text())["needs"]}
    for route in ("approve", "reject", "fix"):
        path = f"/api/p/{name}/dream/{route}"
        check(f"{route} without the owner's login is Not yours", call("POST", path, {"Host": server.APP_HOST, "Origin": server.ORIGIN, "Content-Type": "application/json"}, {"words": agent}) == (403, {"error": "Not yours."}))
        check(f"{route} from another origin is refused", call("POST", path, {**WRITE, "Origin": "https://example.com"}, {"words": agent})[0] == 403)
        check(f"{route} is not a GET", call("GET", path, OWNER)[0] == 404)
    check("nothing was decided by the refused requests", set(states().values()) == {"open"}, str(states()))
    status, said = call("POST", f"/api/p/{name}/dream/fix", WRITE, {})
    check("the fixer is not started with nothing approved", status == 409 and said["error"] == "Nothing is approved for the fixer.", f"{status} {said}")
    status, said = call("POST", f"/api/p/{name}/dream/approve", WRITE, {"words": "deploy key"})
    check("a need only the person can do can't be approved, in the kit's words", status == 409 and said["error"].startswith("Only you can put this right (a credential)") and states()[yours] == "open", f"{status} {said}")
    status, said = call("POST", f"/api/p/{name}/dream/approve", WRITE, {"words": "old.sh"})
    check("the person approves a fix through the kit, which commits it", status == 200 and said["said"].startswith(f"approved: {agent}") and states()[agent] == "approved"
          and base.run("git", "-C", store, "log", "-1", "--format=%s").stdout.strip() == "needs: what 2026-11-10-proposal.md said needs the person is approved for the fixer", f"{status} {said}")
    shown = hub.needs_of(store)["open"]
    check("the hub reads who can fix each and its state", [(n["who"], n["state"], n["repo"]) for n in shown] == [("agent", "approved", "repo"), ("you", "open", None), ("agent", "open", "repo")], str(shown))
    check("it is listed as done in the person's name", hub.recent_actions(name, store)[0]["what"] == "Approved a fix")
    status, said = call("POST", f"/api/p/{name}/dream/approve", WRITE, {"words": "old.sh"})
    check("approving it twice is refused", status == 409 and "approved, so it can't be approved now" in said["error"], f"{status} {said}")
    status, said = call("POST", f"/api/p/{name}/dream/reject", WRITE, {"words": "changelog"})
    check("the person rejects a need, and it leaves the hub's list", status == 200 and states()[third] == "rejected" and third not in [n["text"] for n in hub.needs_of(store)["open"]]
          and hub.recent_actions(name, store)[0]["what"] == "Rejected something a dream said needs you", f"{status} {said}")
    check("what waits for the person counts open and stopped needs only", hub.waits_for_person(store) == 1)
    hub.tmux("new-session", "-d", "-s", hub.fix_session(name), "sleep 600")
    status, said = call("POST", f"/api/p/{name}/dream/fix", WRITE, {})
    check("the fixer is not started while it runs", status == 409 and said["error"] == "The fixer is already running.", f"{status} {said}")
finally:
    hub.tmux("kill-session", "-t", f"={hub.fix_session(name)}")
    loop.call_soon_threadsafe(loop.stop)
    hub.STORES = real_stores
    shutil.rmtree(home, ignore_errors=True)

# ── the Automatic dreams switch: with no hour the kit picks one free of every store's dream and fixer ──
asked, real_run, real_schedules = [], hub.kit.run, hub.kit.SCHEDULES
hub.kit.run = lambda *a, **k: asked.append([str(x) for x in a]) or type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()
hub.kit.SCHEDULES = True
try:
    hub.kit.set_schedule("/repo", True)
    hub.kit.set_schedule("/repo", True, 7)
    hub.kit.set_schedule("/repo", False)
    check("switched on with no hour, the kit is asked without one (it puts the store on its hourly scheduler)", asked[0][2:] == ["/repo"] and asked[0][1].endswith("schedule-dream.sh"), str(asked))
    check("switched on with an hour, that hour is passed; switched off, both jobs are removed", asked[1][2:] == ["/repo", "--hour", "7"] and asked[2][2:] == ["/repo", "--remove"], str(asked))
finally:
    hub.kit.run, hub.kit.SCHEDULES = real_run, real_schedules

print(f"--- failures: {fails}")
sys.exit(1 if fails else 0)
