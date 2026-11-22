#!/usr/bin/env python3
"""Worktree checkouts and their branches, end to end, in a throwaway project, hub-test-throwaway-<n>, made here and
removed at the end: what a project's Worktrees list says (ahead, uncommitted, merged), removing a checkout and deleting a
branch with every guard (never the main checkout, a second confirmation for uncommitted files and unmerged commits,
nothing while a session runs there), "Clean up merged" with its preview, no git at all in a no_vcs folder, and a real
Claude session started in its own worktree and closed with "Remove the checkout".

Runs against a second instance (the six HUB_* variables, see tests/instance.py).
Run: /usr/bin/python3 tests/worktrees_check.py
"""
import http.client, json, os, subprocess, sys, tempfile, time
from pathlib import Path

from instance import CFG, HOME, NAME, OWNER, PORT, STATE, WRITE, answer_first_run, launchd_jobs, quiet_alert, remove_project, sweep

fails = 0
def check(label, ok, extra=""):
    global fails; fails += 0 if ok else 1
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:400]}]"), flush=True)
def call(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=90)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE if body is not None else OWNER)
    r = c.getresponse(); return r.status, json.loads(r.read() or b"{}")
def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)
def row(sid):
    return next((s for s in call("GET", "/api/state")[1]["sessions"] if s["id"] == sid), None)
def wait(sid, ok, limit, label):
    end = time.time() + limit
    while time.time() < end:
        r = row(sid)
        if r and ok(r): return r
        time.sleep(2)
    check(label, False, row(sid)); return row(sid)
def trees():
    status, data = call("GET", f"/api/p/{NAME}/worktrees")
    return status, {r["branch"]: r for e in data.get("repos", []) for r in e["rows"]}
def tree(name, base="HEAD"):
    path = REPO / ".claude" / "worktrees" / name
    made = git(REPO, "worktree", "add", "-q", "-b", f"hub/{name}", str(path), base)
    assert made.returncode == 0, made.stderr
    return path
def commit(folder, file, text):
    (Path(folder) / file).write_text(text)
    git(folder, "add", file); return git(folder, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", f"Add {file}")

REPO = HOME / "projects" / NAME
TILDE = lambda p: str(p).replace(str(HOME), "~", 1)
sweep()
launchd_before = launchd_jobs()
sids = []
try:
    status, made = call("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", status == 200, made)
    quiet_alert(NAME)
    excl = Path(git(REPO, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()) / "info" / "exclude"
    excl.write_text(excl.read_text() + "\n/.claude/worktrees/\n")

    # ── the list ──
    status, data = call("GET", f"/api/p/{NAME}/worktrees")
    check("a project with no worktrees lists none", status == 200 and all(not e["rows"] for e in data["repos"]), data)
    merged = tree("merged-aaaa"); commit(merged, "done.txt", "done\n")
    m = git(REPO, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "merge", "-q", "--no-ff", "-m", "Merge", "hub/merged-aaaa")
    check("the test branch merges into main", m.returncode == 0, m.stderr)
    open_ = tree("open-bbbb"); commit(open_, "half.txt", "half\n"); (open_ / "scratch.txt").write_text("unsaved\n")
    fresh = tree("fresh-cccc")
    status, rows = trees()
    check("the list has the three checkouts and not the main one", status == 200 and set(rows) == {"hub/merged-aaaa", "hub/open-bbbb", "hub/fresh-cccc"}, rows.keys())
    check("a merged branch says merged", rows["hub/merged-aaaa"]["merged"] and rows["hub/merged-aaaa"]["ahead"] == 0, rows["hub/merged-aaaa"])
    o = rows["hub/open-bbbb"]
    check("an open branch says 1 ahead, 1 uncommitted, not merged", o["ahead"] == 1 and o["changed"] == 1 and not o["merged"] and o["files"] == ["scratch.txt"], o)
    check("its base is main", o["base"] == "main", o)
    check("a branch with no commits is new, not merged", rows["hub/fresh-cccc"]["fresh"] and not rows["hub/fresh-cccc"]["merged"], rows["hub/fresh-cccc"])
    check("the path is said from ~", o["path"] == TILDE(open_), o["path"])

    # ── removing a checkout: the guards ──
    repo = TILDE(REPO)
    for label, path in (("the main checkout", repo), ("a folder outside .claude/worktrees", str(REPO / ".claude")),
                        ("a path that climbs out", str(REPO / ".claude" / "worktrees" / ".." / "..")), ("a folder git doesn't list", str(REPO / ".claude" / "worktrees" / "nothing"))):
        status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": repo, "path": path})
        check(f"removing {label} is refused", status == 409, res)
    check("the main checkout is untouched", (REPO / ".git").is_dir() and (REPO / "done.txt").exists())
    status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": "/tmp", "path": str(open_)})
    check("a folder that isn't the project's is refused", status == 409, res)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": repo, "path": TILDE(open_)})
    check("a dirty checkout isn't removed without a second yes", status == 409 and res.get("dirty") == 1 and res.get("files") == ["scratch.txt"], res)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": repo, "path": TILDE(open_), "force": True, "expect": 3})
    check("a second yes for a different number of files is refused", status == 409 and open_.is_dir(), res)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": repo, "path": TILDE(open_), "force": True, "expect": 1})
    check("with the second yes it is removed", status == 200 and res.get("lost") == 1 and not open_.exists(), res)
    check("its branch is kept", git(REPO, "rev-parse", "-q", "--verify", "refs/heads/hub/open-bbbb").returncode == 0)
    status, rows = trees()
    check("the branch is still listed, without a checkout", rows.get("hub/open-bbbb", {}).get("path") is None and rows["hub/open-bbbb"]["ahead"] == 1, rows.get("hub/open-bbbb"))

    # ── deleting a branch ──
    for label, branch in (("main", "main"), ("a branch the hub didn't make", "feature"), ("a name that looks like a flag", "-D")):
        git(REPO, "branch", "feature")
        status, res = call("POST", f"/api/p/{NAME}/worktrees/branch", {"repo": repo, "branch": branch})
        check(f"deleting {label} is refused", status == 409, res)
    check("main and feature are still there", git(REPO, "rev-parse", "-q", "--verify", "refs/heads/feature").returncode == 0 and git(REPO, "rev-parse", "-q", "--verify", "refs/heads/main").returncode == 0)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/branch", {"repo": repo, "branch": "hub/merged-aaaa"})
    check("a checked-out branch isn't deleted", status == 409 and "checked out" in res.get("error", ""), res)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/branch", {"repo": repo, "branch": "hub/open-bbbb"})
    check("an unmerged branch isn't deleted without a strong yes", status == 409 and res.get("ahead") == 1, res)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/branch", {"repo": repo, "branch": "hub/open-bbbb", "force": True, "expect": 2})
    check("a yes for a different number of commits is refused", status == 409, res)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/branch", {"repo": repo, "branch": "hub/open-bbbb", "force": True, "expect": 1})
    check("with the strong yes it is deleted", status == 200 and res.get("lost") == 1 and git(REPO, "rev-parse", "-q", "--verify", "refs/heads/hub/open-bbbb").returncode != 0, res)

    # ── Clean up merged ──
    dirty_merged = tree("dirty-dddd", "main"); (dirty_merged / "notes.txt").write_text("keep me\n")
    gone = tree("gone-eeee"); commit(gone, "g.txt", "g\n"); git(REPO, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "merge", "-q", "--no-ff", "-m", "Merge g", "hub/gone-eeee")
    git(REPO, "worktree", "remove", str(gone))  # a merged branch whose checkout is already gone
    status, plan = call("POST", f"/api/p/{NAME}/worktrees/clean", {})
    planned = {i["branch"] for i in plan.get("plan", [])}
    skipped = {i["branch"]: i["why"] for i in plan.get("skip", [])}
    check("the preview plans the merged ones", status == 200 and planned == {"hub/merged-aaaa", "hub/gone-eeee"}, plan)
    check("the preview changes nothing", merged.is_dir() and git(REPO, "rev-parse", "-q", "--verify", "refs/heads/hub/gone-eeee").returncode == 0)
    check("a new branch is neither planned nor skipped", "hub/fresh-cccc" not in planned and "hub/fresh-cccc" not in skipped, plan)
    git(dirty_merged, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "x")
    git(REPO, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "merge", "-q", "--no-ff", "-m", "Merge d", "hub/dirty-dddd")
    status, plan = call("POST", f"/api/p/{NAME}/worktrees/clean", {})
    skipped = {i["branch"]: i["why"] for i in plan.get("skip", [])}
    check("a merged checkout with uncommitted files is skipped, with why", "uncommitted" in skipped.get("hub/dirty-dddd", ""), plan)
    keys = [i["key"] for i in plan["plan"]] + ["~/nothing|x|hub/x"]
    status, res = call("POST", f"/api/p/{NAME}/worktrees/clean", {"keys": keys})
    check("clean up does what the preview said", status == 200 and {i["branch"] for i in res["done"]} == {"hub/merged-aaaa", "hub/gone-eeee"}, res)
    check("a key the preview didn't hold is left alone", any(i.get("key") == "~/nothing|x|hub/x" for i in res["left"]), res)
    check("the merged checkout and both branches are gone", not merged.exists() and git(REPO, "rev-parse", "-q", "--verify", "refs/heads/hub/merged-aaaa").returncode != 0 and git(REPO, "rev-parse", "-q", "--verify", "refs/heads/hub/gone-eeee").returncode != 0)
    check("the dirty one is still there", (dirty_merged / "notes.txt").exists())
    check("the main checkout still has its work", (REPO / "done.txt").exists() and (REPO / "g.txt").exists() and (REPO / ".git").is_dir())

    # ── no_vcs: no git at all ──
    with tempfile.TemporaryDirectory() as scratch:
        config = Path(scratch) / "config.json"
        config.write_text(json.dumps({**CFG, "no_vcs": [str(REPO.relative_to(HOME))]}))
        probe = r'''
import json, subprocess, sys
ran = []
real = subprocess.run
def spy(cmd, *a, **k):
    if str(cmd[0]).endswith("git"): ran.append(list(map(str, cmd)))
    return real(cmd, *a, **k)
subprocess.run = spy
import hub_worktrees as w, hub_base
out = {"list": w.route_list(sys.argv[1])}
for what, call in (("remove", lambda: w.route_remove(sys.argv[1], {"repo": sys.argv[2], "path": sys.argv[3], "force": True, "expect": 1})),
                   ("branch", lambda: w.route_branch(sys.argv[1], {"repo": sys.argv[2], "branch": "hub/fresh-cccc"})),
                   ("clean", lambda: w.route_clean(sys.argv[1], {}))):
    try: out[what] = call()
    except hub_base.Refused as why: out[what] = "refused: " + str(why)
out["tree"] = w.session_tree({"isolate": True, "repo": sys.argv[2], "folder": sys.argv[3]})
out["ran"] = [c for c in ran if any(sys.argv[2] in part for part in c)]
print(json.dumps(out))
'''
        env = {**os.environ, "HUB_CONFIG": str(config)}
        got = subprocess.run(["/usr/bin/python3", "-c", probe, NAME, str(REPO), str(dirty_merged)], cwd=str(Path(__file__).resolve().parent.parent), env=env, capture_output=True, text=True)
        try:
            out = json.loads(got.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            out = {"error": got.stderr[-400:]}
        check("in a no_vcs folder the list says so and lists nothing", out.get("list", {}).get("repos", [{}])[0].get("noVcs") is True and not out["list"]["repos"][0]["rows"], out)
        check("in a no_vcs folder remove and delete are refused", str(out.get("remove", "")).startswith("refused") and str(out.get("branch", "")).startswith("refused"), out)
        check("in a no_vcs folder clean up plans nothing", out.get("clean") == {"plan": [], "skip": []}, out)
        check("a session's row in a no_vcs folder carries no worktree", out.get("tree", 1) is None, out)
        check("no git command ran in the no_vcs folder", out.get("ran") == [], out.get("ran"))
    check("the dirty checkout survived the no_vcs run", (dirty_merged / "notes.txt").exists())

    # ── a real session in its own worktree, closed with "Remove the checkout" ──
    def start():
        status, made = call("POST", "/api/sessions", {"project": NAME, "tasks": ["Reply with the single word ready and nothing else"], "isolate": True, "mode": "plan", "model": "haiku", "effort": "low"})
        check("a session starts in its own worktree", status == 200, made)
        sid = made["ids"][0]; sids.append(sid)
        answer_first_run(sid)
        return sid, wait(sid, lambda r: r["state"] == "finished", 150, "it answers")
    sid, r = start()
    meta = json.loads((STATE / "sessions" / f"{sid}.json").read_text())
    folder = Path(meta["folder"])
    check("its meta keeps where the branch came from", meta.get("tree", {}).get("base") == "main" and len(meta["tree"].get("start", "")) == 40 and meta["tree"]["branch"].startswith("hub/"), meta.get("tree"))
    t = (r or {}).get("tree") or {}
    check("its row carries the branch, new and clean", t.get("branch") == meta["tree"]["branch"] and t.get("fresh") and t.get("changed") == 0 and t.get("checkout"), t)
    status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": repo, "path": str(folder), "force": True, "expect": 0})
    check("its checkout isn't removed while it runs", status == 409 and "running" in res.get("error", "") and folder.is_dir(), res)
    (folder / "left.txt").write_text("not committed\n")
    status, chk = call("GET", f"/api/sessions/{sid}/closing")
    check("the close check carries the worktree", status == 200 and (chk.get("tree") or {}).get("changed") == 1, chk)
    status, res = call("POST", f"/api/sessions/{sid}/close", {"note": False, "removeTree": True})
    check("a dirty checkout is kept at close, and says what is left", status == 200 and (res.get("tree") or {}).get("kept") and res["tree"].get("files") == ["left.txt"] and folder.is_dir(), res)
    r = row(sid)
    check("the closed row says the checkout was kept", ((r.get("closeResult") or {}).get("tree") or {}).get("kept"), r and r.get("closeResult"))
    status, res = call("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": repo, "path": TILDE(folder), "force": True, "expect": 1})
    check("the second yes removes it", status == 200 and not folder.exists(), res)
    check("its branch is kept", git(REPO, "rev-parse", "-q", "--verify", f"refs/heads/{meta['tree']['branch']}").returncode == 0)
    time.sleep(16)  # past the sidebar's cache
    r = row(sid)
    check("its row now says the checkout is gone", (r.get("tree") or {}).get("checkout") is False and not r.get("resumable"), r and r.get("tree"))

    sid2, r = start()
    folder2 = Path(json.loads((STATE / "sessions" / f"{sid2}.json").read_text())["folder"])
    status, res = call("POST", f"/api/sessions/{sid2}/close", {"note": True, "removeTree": True})
    check("a close with a handoff starts", status == 200 and res.get("closing"), res)
    check("the checkout stays while Claude writes the handoff", folder2.is_dir())
    r = wait(sid2, lambda r: r["state"] == "closed", 300, "it closes")
    check("a clean checkout is removed once the handoff is in", not folder2.exists() and (((r or {}).get("closeResult") or {}).get("tree") or {}).get("removed"), r and r.get("closeResult"))
    status, res = call("POST", f"/api/sessions/{sid}/close", {"note": False})
    check("closing without asking removes nothing (already closed)", status == 200)
    check("the main checkout is untouched after all of it", (REPO / ".git").is_dir() and (REPO / "done.txt").exists())
finally:
    for sid in sids:
        try:
            call("POST", f"/api/sessions/{sid}/dismiss", {})
        except OSError:
            pass
    left = remove_project(NAME)
    check("the throwaway project is gone", not left, left)
    check("launchd's folder holds what it held before", launchd_jobs() == launchd_before, sorted(set(launchd_jobs()) ^ set(launchd_before)))
print("--- failures:", fails)
sys.exit(1 if fails else 0)
