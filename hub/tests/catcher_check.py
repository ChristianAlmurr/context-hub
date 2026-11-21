#!/usr/bin/env python3
"""Offline checks of the Dream Catcher: no Claude session and no server but one this script runs in itself.

- Its verdicts are read by one function (catcher_verdicts.parse) for the session's check and for the hub, and what the
  person keeps (ORG.md and Steering, unchecked facts, deletions, decisions and preferences, credentials and money, a
  need only they can put right) allows only "leave".
- The kit's guard still stops every person command in an ordinary session: approve, reject, dismiss, withdraw, forget,
  apply --yours. The catcher's session runs under the same guard.
- The hub carries out a finished run's verdicts through its own functions (a tick, the kit's approve and reject), writes
  each down as it goes with who decided and why, never does one twice, carries on after a crash, leaves a store a dream
  holds alone, and with the switch off only recommends until the person accepts. A proposal is applied only when no item
  in it waits on the person; the apply session is stubbed here.
- The routes are the person's: refused without the owner's login.
- dream-catcher-install.sh makes a store through the kit's installer (in a temporary home).
The store is a throwaway project (tests/instance.py), removed at the end.
Run: /usr/bin/python3 tests/catcher_check.py (with the six HUB_* variables of a second instance, as for the other tests)
"""
import asyncio, http.client, json, os, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from instance import HOME, KIT, NAME, quiet_alert, remove_project, sweep, write_dream  # noqa: E402  (refuses the installed hub)
import catcher_verdicts as verdicts  # noqa: E402
import hub_catcher as catcher  # noqa: E402
import hub_data as hub  # noqa: E402

fails = 0
APP = Path(__file__).resolve().parent.parent


def refused(work) -> bool:
    try:
        work()
    except hub.Refused:
        return True
    return False


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{extra}]"), flush=True)
    fails += 0 if ok else 1


# ── verdicts: one reader, and what only the person decides ──
item = lambda **kw: {"kind": "proposal", "text": "", "details": [], "file": "project/gotchas.md", "action": "add", "section_kind": "", **kw}
cases = [
    ("an ordinary added line", item(text='1. project/gotchas.md — add — "- [2026-11-20] Builds need the lock"'), ""),
    ("ORG.md", item(file="ORG.md", section_kind="yours", action="edit"), "ORG.md and Steering are yours to change"),
    ("Steering", item(file="Steering", section_kind="yours"), "ORG.md and Steering are yours to change"),
    ("an unchecked fact", item(section_kind="unchecked"), "nothing could check this fact: your tick is the check"),
    ("a deletion", item(action="delete"), "it deletes a memory line"),
    ("a decision", item(file="project/decisions.md", text="Decision: ship on Tuesdays"), "it records a decision or preference of a person"),
    ("a preference in another file", item(text="The owner prefers short answers"), "it records a decision or preference of a person"),
    ("a credential", item(text="The deploy token lives in the keychain"), "it touches credentials or money"),
    ("money", item(text="The invoice export rounds to cents"), "it touches credentials or money"),
    ("a need only the person can put right", {"kind": "need", "who": "you", "text": "x", "details": []}, "only you can put it right"),
    ("a need an agent can fix", {"kind": "need", "who": "agent", "text": "The README names a script that is gone", "details": []}, ""),
    ("an inbox proposal for ORG.md", {"kind": "inbox", "text": "Propose: ORG.md should say X", "details": []}, "it proposes a change to ORG.md or Steering"),
]
for label, it, want in cases:
    check(f"held back: {label}", verdicts.held_back(it) == want, verdicts.held_back(it))

manifest = {"items": [{"key": "a", "held": ""}, {"key": "b", "held": "ORG.md and Steering are yours to change"}, {"key": "c", "held": ""}]}
line = lambda key, verdict, reason="It is true and useful.", evidence="read gotchas.md:3": json.dumps({"key": key, "verdict": verdict, "reason": reason, "evidence": evidence})
found, problems = verdicts.parse(manifest, "\n".join([line("a", "approve"), line("b", "leave"), line("c", "reject")]))
check("a full set of verdicts reads with no problem", problems == [] and {k: v["verdict"] for k, v in found.items()} == {"a": "approve", "b": "leave", "c": "reject"}, str(problems))
for label, text, words in (
        ("an item held for the person can only be left", "\n".join([line("a", "approve"), line("b", "approve"), line("c", "reject")]), "can only be left for the person"),
        ("an unknown key", "\n".join([line("a", "approve"), line("b", "leave"), line("c", "reject"), line("zz", "approve")]), "isn't the key of an item"),
        ("an item said twice", "\n".join([line("a", "approve"), line("a", "reject"), line("b", "leave"), line("c", "reject")]), "has a verdict already"),
        ("a missing item", "\n".join([line("a", "approve"), line("b", "leave")]), "1 items have no verdict yet: c"),
        ("a reason over two lines", "\n".join([line("a", "approve", "one\ntwo"), line("b", "leave"), line("c", "reject")]), "reason must be one line"),
        ("no evidence", "\n".join([line("a", "approve", evidence=""), line("b", "leave"), line("c", "reject")]), "evidence must be one line"),
        ("a verdict that isn't one", "\n".join([line("a", "tick"), line("b", "leave"), line("c", "reject")]), "must be one of approve, reject, leave"),
        ("a line that isn't JSON", "\n".join(["{nope", line("a", "approve"), line("b", "leave"), line("c", "reject")]), "isn't JSON")):
    check(f"refused: {label}", any(words in p for p in verdicts.parse(manifest, text)[1]), str(verdicts.parse(manifest, text)[1]))

run_dir = Path(tempfile.mkdtemp(prefix="catcher-run.", dir=f"/private/tmp/claude-{os.getuid()}"))
try:
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    (run_dir / "verdicts.jsonl").write_text("\n".join([line("a", "approve"), line("b", "leave")]))
    ran = subprocess.run(["/usr/bin/python3", str(APP / "catcher_verdicts.py"), "check", str(run_dir)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    check("the session's check names what is wrong and doesn't finish", ran.returncode == 1 and "no verdict yet: c" in ran.stdout and "report.md is missing" in ran.stdout and not (run_dir / "finished.json").exists(), ran.stdout)
    (run_dir / "verdicts.jsonl").write_text("\n".join([line("a", "approve"), line("b", "leave"), line("c", "reject")]) + "\n")
    (run_dir / "report.md").write_text("1 approved, 1 rejected, 1 left for you.\n")
    ran = subprocess.run(["/usr/bin/python3", str(APP / "catcher_verdicts.py"), "check", str(run_dir)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    check("with everything right, the check finishes the run, with nothing of the hub's loaded", ran.returncode == 0 and "finished" in ran.stdout and json.loads((run_dir / "finished.json").read_text())["verdicts"] == 3, ran.stdout + ran.stderr)
finally:
    shutil.rmtree(run_dir, ignore_errors=True)

# ── the kit's guard still stops the person's commands in an ordinary session ──
guard = KIT / "scripts" / "guard_memory.py"
for command in ("python3 scripts/dream_proposal.py approve 'old.sh'", "python3 scripts/dream_proposal.py reject 'old.sh'", "amk proposal dismiss 2026-11-20-proposal.md",
                "python3 scripts/dream_proposal.py dismiss 2026-11-20-proposal.md", "python3 scripts/dream_proposal.py withdraw 'x'", "python3 scripts/dream_proposal.py forget 'x'",
                "python3 scripts/dream_apply.py --yours", "cd ~/agent-memory/x && python3 ~/tools/agent-memory-kit/scripts/dream_proposal.py approve x"):
    ran = subprocess.run(["python3", str(guard)], input=json.dumps({"tool_input": {"command": command}, "cwd": str(HOME)}), capture_output=True, text=True)
    check(f"the guard stops: {command}", ran.returncode == 2 and "Blocked" in ran.stderr, f"{ran.returncode} {ran.stderr[:200]}")
ran = subprocess.run(["python3", str(guard)], input=json.dumps({"tool_input": {"command": f"/usr/bin/python3 {APP / 'catcher_verdicts.py'} check /tmp/x"}, "cwd": str(HOME)}), capture_output=True, text=True)
check("and lets the catcher's own check through", ran.returncode == 0, ran.stderr)
settings = json.loads(hub.HUB_SETTINGS.read_text()) if hub.HUB_SETTINGS.exists() else None
flags = hub.catcher_flags()
check("a catcher session carries the hub session's guard and its own rules", flags[0] == "--dangerously-skip-permissions" and "You are the Dream Catcher" in flags[2] and hub.HUB_BRIEF in flags[2]
      and (settings is None or any("guard_memory.py" in h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"])))

# ── carrying out verdicts, in a throwaway project ──
sweep()
repo, store = HOME / "projects" / NAME, HOME / "agent-memory" / NAME
real = {"scope": catcher.scope, "auto": catcher.auto, "apply": hub.apply_dream, "runs": catcher.RUNS, "own": catcher.own_store, "dreamer": hub.kit.dreamer}
applied = []
try:
    made = hub.create_project({"name": NAME})
    quiet_alert(NAME)
    check("a throwaway project is made", (store / "ORG.md").exists(), str(made))
    today = time.strftime("%Y-%m-%d")
    agent_need = f"The README names a script that is gone · evidence: s-1 · fix: {NAME} — drop the line about old.sh"
    yours_need = "The deploy key has expired · evidence: s-2 · yours: a credential"
    proposal = write_dream(repo, f"""# Dream {{DAY}} — 4 sessions, 4 proposed changes

## Summary
A dream written for this test.

## Needs you
- {agent_need}
- {yours_need}

## Proposed changes (tick to approve)
- [ ] 1. project/gotchas.md — add — "- [{today}] The export hangs on empty input → pass --allow-empty (checked: ran it)"
      why: two sessions lost time · seen: 2/4 sessions · cost: ~6 · evidence: a1b2c3d4
- [ ] 2. project/gotchas.md — add — "- [{today}] The importer is slow"
      why: one session said so · seen: 1/4 sessions · cost: ~1 · evidence: e5f6a7b8
- [ ] 3. project/decisions.md — add — "Decision: releases go out on Tuesdays. Why: the team is in. (by Sam)"
      why: the person decided it · seen: 1/4 sessions · cost: ~0 · evidence: c9d0e1f2

## ORG.md and Steering (yours to change)
- [ ] 4. ORG.md — edit — "- Keys live in the keychain, never in a repo."
      why: the folder the line names is gone · evidence: ls
      replaces: "- Keys live in ~/.keys · never in a repo."

## Trend
Nothing to compare.
""")
    (store / "inbox").mkdir(exist_ok=True)
    (store / "inbox" / f"{today}-scout.md").write_text("The importer's fixtures belong in project/importer.md.\n")
    catcher.scope = lambda: [store]
    catcher.own_store = lambda: None
    catcher.RUNS = Path(tempfile.mkdtemp(prefix="catcher-runs.", dir=f"/private/tmp/claude-{os.getuid()}"))
    hub.apply_dream = lambda name, body: applied.append((name, body["file"])) or {"ids": ["00000000"]}
    found = catcher.gather()
    keys = {(i["kind"], i.get("n") or i.get("text", "")[:20]): i for i in found["items"]}
    check("what waits is listed: four proposal items, two needs, one inbox file", sorted(i["kind"] for i in found["items"]) == ["inbox"] + ["need"] * 2 + ["proposal"] * 4, str([i["kind"] for i in found["items"]]))
    held = {i.get("n"): i["held"] for i in found["items"] if i["kind"] == "proposal"}
    check("the decision and ORG.md items are held for the person, the others not", held == {1: "", 2: "", 3: "it records a decision or preference of a person", 4: "ORG.md and Steering are yours to change"}, str(held))
    check("the need only the person can put right is held, the agent's not", {i["who"]: i["held"] for i in found["items"] if i["kind"] == "need"} == {"agent": "", "you": "only you can put it right"})

    def fake_run(found, said, auto):
        """A finished run without a session: the manifest, the session's verdicts and report, and the session's check."""
        catcher.auto = lambda: auto
        run = time.strftime("%Y%m%d-%H%M%S") + f"-{len(list(catcher.RUNS.iterdir()))}"
        folder = catcher.RUNS / run
        folder.mkdir()
        (folder / "manifest.json").write_text(json.dumps({**found, "run": run, "history": []}))
        (folder / "run.json").write_text(json.dumps({"id": run, "started": time.time(), "sid": None}))
        (folder / "verdicts.jsonl").write_text("\n".join(json.dumps({"key": i["key"], "verdict": said(i), "reason": f"Because {i['kind']}.", "evidence": "read it"}) for i in found["items"]) + "\n")
        (folder / "report.md").write_text("A report.\n")
        check("the run's check passes", verdicts.check(folder) == [])
        return run, folder

    text_of = lambda: (store / "dreams" / proposal).read_text()
    ticked = lambda n: f"- [x] {n}." in text_of()
    need_state = lambda words: next(e.get("state", "open") for e in json.loads((store / "dreams" / "needs.json").read_text())["needs"] if words in e["text"])

    # a run with the switch on: approve 1 and the agent's need, reject 2, leave the rest
    choose = lambda i: "leave" if i["held"] else {1: "approve", 2: "reject"}.get(i.get("n"), "approve" if i["kind"] in ("need", "inbox") else "leave")
    run, folder = fake_run(found, choose, True)
    acts_before = hub.ACTIONS.read_text().splitlines() if hub.ACTIONS.exists() else []
    catcher.settle(run)
    rows = catcher.results(folder)
    check("item 1 is ticked, by the hub's own tick", ticked(1) and not ticked(2) and not ticked(3) and not ticked(4), text_of())
    check("the agent's need is approved for the fixer through the kit, the person's left open", need_state("old.sh") == "approved" and need_state("deploy key") == "open")
    check("every item has its result, and what waits is counted", sorted(r["result"] for r in rows.values()) == ["done"] * 4 + ["left"] * 3 and json.loads((folder / "settled.json").read_text())["waiting"] == 3, str(rows))
    new_acts = [json.loads(l) for l in hub.ACTIONS.read_text().splitlines()[len(acts_before):]]
    check("each act is logged as the Dream Catcher's, with its reason", sorted(a["action"] for a in new_acts) == ["approve", "tick"] and all(a["by"] == "dream-catcher" and a["why"].startswith("Because") for a in new_acts), str(new_acts))
    recent = hub.recent_actions(NAME, store)
    check("and Done in your name says it was the Dream Catcher", any(r.get("by") == "dream-catcher" and r["what"] == "Approved a fix" for r in recent) and any(r.get("by") == "dream-catcher" and r["what"].startswith("Ticked") for r in recent), str(recent[:3]))
    check("no proposal is applied while items in it wait on the person", applied == [])
    before = (text_of(), (folder / "results.jsonl").read_text(), hub.ACTIONS.read_text())
    (folder / "settled.json").unlink()
    catcher.settle(run)
    check("carrying out the same run again does nothing twice", (text_of(), (folder / "results.jsonl").read_text(), hub.ACTIONS.read_text()) == before)

    # a crash halfway: a line cut off, no settled.json; the next pass does what is left and nothing twice
    found = catcher.gather()
    check("what was decided is no longer listed: item 1 and the agent's need", sorted((i["kind"], i.get("n")) for i in found["items"]) == [("inbox", None), ("need", None), ("proposal", 2), ("proposal", 3), ("proposal", 4)], str([(i["kind"], i.get("n")) for i in found["items"]]))
    run, folder = fake_run(found, lambda i: "leave" if i["held"] else "reject" if i["kind"] == "proposal" else "approve", False)
    first = next(i for i in found["items"] if i["kind"] == "inbox")
    (folder / "results.jsonl").write_text(json.dumps({"key": first["key"], "verdict": "approve", "result": "recommended", "said": "", "by": "dream-catcher", "at": 1}) + "\n" + '{"key": "p:cut')
    catcher.settle(run)
    rows = catcher.results(folder)
    check("with the switch off nothing is done: 2 is recommended, the held ones left", not ticked(2) and rows[next(i["key"] for i in found["items"] if i.get("n") == 2)]["result"] == "recommended"
          and sum(1 for r in rows.values() if r["result"] == "left") == 3 and len((folder / "results.jsonl").read_text().splitlines()) == 1 + 1 + 4, (folder / "results.jsonl").read_text())
    said = catcher.accept({"run": run})
    rows = catcher.results(folder)
    check("Accept all recommended carries them out as the person's", said["said"].startswith("2 recommended") and rows[next(i["key"] for i in found["items"] if i.get("n") == 2)]["result"] == "done" and not ticked(2), str(said))
    check("still nothing is applied: 3 and 4 wait on the person", applied == [])
    for n in (3, 4):
        key = next(i["key"] for i in found["items"] if i.get("n") == n)
        check(f"the person ticks {n} from the catcher's page", catcher.decide({"run": run, "key": key, "verdict": "approve"})["result"] == "done" and ticked(n))
    yours = next(i["key"] for i in found["items"] if i["kind"] == "need")
    check("approving a need only the person can put right is refused", refused(lambda: catcher.decide({"run": run, "key": yours, "verdict": "approve"})))
    check("the person marks it done", catcher.decide({"run": run, "key": yours, "verdict": "done"})["result"] == "done" and "deploy key" not in (store / "dreams" / "needs.json").read_text())
    catcher.apply_ready(folder, json.loads((folder / "manifest.json").read_text()), "")
    check("with every item decided and some ticked, the proposal is applied, once", applied == [(NAME, proposal)])
    catcher.apply_ready(folder, json.loads((folder / "manifest.json").read_text()), "")
    check("and not twice", applied == [(NAME, proposal)])

    # a store a dream holds is left alone, at the start and when a verdict would be carried out
    hub.kit.dreamer = lambda s: "A dream (test) holds this memory."
    found = catcher.gather()
    check("a store a dream holds is skipped, with why", found["items"] == [] and found["skipped"] == [{"store": NAME, "why": "A dream (test) holds this memory."}], str(found["skipped"]))
    check("and a verdict for it waits", catcher.carry_out({"store": NAME, "kind": "need", "text": agent_need}, "reject", "dream-catcher", "x")[0] == "skipped" and need_state("old.sh") == "approved")
    hub.kit.dreamer = real["dreamer"]

    # the summary the sidebar polls
    s = catcher.summary()
    check("the sidebar's summary names the latest run and what waits", s["run"] == run and s["phase"] == "settled" and isinstance(s["waiting"], int), str(s))
finally:
    catcher.scope, catcher.auto, hub.apply_dream, catcher.own_store, hub.kit.dreamer = real["scope"], real["auto"], real["apply"], real["own"], real["dreamer"]
    if catcher.RUNS != real["runs"]:
        shutil.rmtree(catcher.RUNS, ignore_errors=True)
    catcher.RUNS = real["runs"]
    left = remove_project(NAME)
    check("the throwaway project is removed", not left, str(left))

# ── the routes are the person's ──
import server  # noqa: E402
loop = asyncio.new_event_loop()
try:
    srv = loop.run_until_complete(asyncio.start_server(server.handle, "127.0.0.1", 0))
    port = srv.sockets[0].getsockname()[1]
    threading.Thread(target=loop.run_forever, daemon=True).start()

    def call(method, path, headers, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        c.request(method, path, json.dumps(body) if body is not None else None, headers)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")

    nobody = {"Host": server.APP_HOST, "Origin": server.ORIGIN, "Content-Type": "application/json"}
    for route in ("run", "accept", "decide", "auto"):
        check(f"/api/catcher/{route} without the owner's login is Not yours", call("POST", f"/api/catcher/{route}", nobody, {}) == (403, {"error": "Not yours."}))
    check("the page without the owner's login is Not yours", call("GET", "/api/catcher", {"Host": server.APP_HOST})[0] == 403)
    owner = {"Host": server.APP_HOST, "Tailscale-User-Login": server.OWNER} if server.OWNER else None
    if owner:
        status, page = call("GET", "/api/catcher", owner)
        check("the page answers the owner", status == 200 and "auto" in page and "own" in page, str(page)[:200])
        check("a run that doesn't exist is refused", call("POST", "/api/catcher/accept", {**owner, "Origin": server.ORIGIN, "Content-Type": "application/json"}, {"run": "../x"})[0] == 409)
finally:
    loop.call_soon_threadsafe(loop.stop)

# ── its own store, made by the kit's installer, in a temporary home ──
home = Path(tempfile.mkdtemp(prefix="catcher-home.", dir=f"/private/tmp/claude-{os.getuid()}"))
try:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home), "HUB_KIT": str(KIT), "AGENT_KIT_NO_SCHEDULE": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    ran = subprocess.run(["sh", str(APP / "dream-catcher-install.sh")], env=env, capture_output=True, text=True, timeout=120)
    made = home / "agent-memory" / "dream-catcher"
    check("the install script makes its folder and its store through the kit", ran.returncode == 0 and (made / "ORG.md").exists() and (made / "roots.txt").read_text().strip() == str(home / "projects" / "dream-catcher")
          and (home / "projects" / "dream-catcher" / "memory").is_symlink() and os.access(made / "notify.sh", os.X_OK), ran.stdout[-400:] + ran.stderr[-400:])
    again = subprocess.run(["sh", str(APP / "dream-catcher-install.sh")], env=env, capture_output=True, text=True, timeout=120)
    check("and running it again keeps them", again.returncode == 0 and (made / "ORG.md").exists(), again.stderr[-300:])
finally:
    subprocess.run(["chflags", "-R", "nouchg", str(home)], capture_output=True)
    shutil.rmtree(home, ignore_errors=True)

print(f"--- failures: {fails}")
sys.exit(1 if fails else 0)
