#!/usr/bin/env python3
"""Offline checks of how a session's state is decided: what the screen says, what the hooks say, which one wins, why,
and how a finish is held until it is sure. No server and no Claude session.

The screens in tests/screens/ are real panes of Claude Code 2.1.330 (see dialog_check.py). done-quotes.txt is a finished
reply that quotes the words the old checks looked for anywhere on screen ("trust this folder", "Enter to confirm",
"esc to interrupt") and ends in a question; working-footer.txt is a turn in progress, its "esc to interrupt" in the footer.
Run: /usr/bin/python3 tests/detect_check.py (with the six HUB_* variables of a second instance, as for the other tests)
"""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hub_status

SCREENS = Path(__file__).resolve().parent / "screens"
fails = 0


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:600]}]"), flush=True)
    fails += 0 if ok else 1


def screen(name):
    return (SCREENS / name).read_text(encoding="utf-8")


NOW = time.time()
IDLE = {"pid": 1, "status": "idle", "statusUpdatedAt": (NOW - 5) * 1000}
BUSY = {"pid": 1, "status": "busy", "statusUpdatedAt": (NOW - 5) * 1000}
STOP = {"state": "finished", "hook": "Stop", "at": NOW - 4}
TOOL = {"state": "working", "hook": "PostToolUse", "at": NOW - 4}
ASKED = "Then press Enter to confirm.\nShould I go ahead?"


def decide(info, event, name, last="", starting=False, asks_as_needs=False):
    return hub_status.decide(info, event, starting, screen(name) if name else "", last, asks_as_needs)


# ── the screen, read only where Claude draws its own lines ──
done, working = screen("done-quotes.txt"), screen("working-footer.txt")
check("a finished reply that quotes the trap words is not working on screen", not hub_status.screen_says(done)["working"], hub_status.screen_says(done))
check("a finished reply that quotes the trap words shows no dialog", not hub_status.screen_says(done)["dialog"], hub_status.screen_says(done))
check("esc to interrupt in the footer is working", hub_status.screen_says(working)["working"], hub_status.screen_says(working))
check("Claude's input box is no dialog while it works", not hub_status.screen_says(working)["dialog"], hub_status.screen_says(working))
typed = done.replace("❯ \n", "❯ remember: esc to interrupt, Enter to confirm\n", 1)
check("words typed in the input box are not the footer", not hub_status.screen_says(typed)["working"] and not hub_status.screen_says(typed)["dialog"], hub_status.screen_says(typed))
check("the trust menu is a first-run dialog", hub_status.screen_says(screen("trust.txt"))["dialog"] == "menu", hub_status.screen_says(screen("trust.txt")))
for name, kind in (("perm-bash.txt", "permission"), ("perm-edit.txt", "permission"), ("plan.txt", "plan"), ("q1.txt", "question"), ("single.txt", "question")):
    check(f"{name} is a {kind} dialog", hub_status.screen_says(screen(name))["dialog"] == kind, hub_status.screen_says(screen(name)))
check("the model picker is a viewer, not a dialog that needs you", hub_status.screen_says(screen("model-picker.txt"))["dialog"] == "" and hub_status.screen_says(screen("model-picker.txt"))["viewer"], hub_status.screen_says(screen("model-picker.txt")))
check("a fresh session's empty box is nothing", hub_status.screen_says(screen("start.txt")) == {"working": False, "dialog": "", "viewer": False, "question": ""}, hub_status.screen_says(screen("start.txt")))
hint = "\n".join(done.splitlines()[:-4] + [" Do you want to use this API key?", " ❯ Yes", "   No", "", " Enter to confirm · Esc to cancel"])
check("a key hint at the very bottom is a dialog", hub_status.screen_says(hint)["dialog"] in ("menu", "first-run"), hub_status.screen_says(hint))

# ── the state: a finished reply quoting trap words must NOT read as needing you ──
d = decide(IDLE, STOP, "done-quotes.txt", last="Then press Enter to confirm.")
check("a finished reply quoting trap words is done, not needs", d["state"] == "finished" and not d["asks"], d)
check("its why names the Stop hook and when", d["why"].startswith("hook: Stop at "), d)
d = decide(None, {}, "done-quotes.txt", starting=True)
check("a starting session whose screen quotes trap words isn't needs", d["state"] == "finished", d)
d = decide({**IDLE, "statusUpdatedAt": (NOW - 1) * 1000}, TOOL, "done-quotes.txt")
check("a stale working the status file settled, with trap words quoted, is done", d["state"] == "finished" and "status" in d["why"], d)

# ── a dialog on screen needs you, whatever the hooks say ──
for event in (TOOL, STOP, {}):
    d = decide(BUSY if event is TOOL else IDLE, event, "perm-bash.txt")
    check(f"a permission prompt on screen is needs (hook said {event.get('hook') or 'nothing'})", d["state"] == "needs" and d["why"] == "screen: permission prompt", d)
d = decide(None, {}, "trust.txt", starting=True)
check("the trust menu while starting is needs", d["state"] == "needs" and d["why"] == "screen: menu", d)
d = decide(IDLE, {"state": "needs", "hook": "PermissionRequest", "at": NOW - 2, "message": "Allow Bash: ls?"}, "perm-bash.txt")
check("a permission request the hook saw keeps its words", d["state"] == "needs" and d["asking"] == "Allow Bash: ls?", d)
d = decide(IDLE, STOP, "model-picker.txt")
check("the model picker open doesn't need you", d["state"] == "finished", d)

# ── working ──
d = decide(BUSY, TOOL, "working-footer.txt")
check("a turn in progress is working, said by its hook", d["state"] == "working" and d["why"].startswith("hook: PostToolUse at "), d)
d = decide(None, {}, "working-footer.txt", starting=True)
check("while starting, the footer's spinner is working", d["state"] == "working" and d["why"] == "screen: spinner", d)

# ── done · asks you ──
d = decide(IDLE, STOP, "done-quotes.txt", last=ASKED)
check("a finished turn ending in ? is done, with asks", d["state"] == "finished" and d["asks"] is True and d["asking"] == "Should I go ahead?", d)
check("its why says the reply ends in ?", d["why"].endswith("reply ends in ?"), d)
d = decide(IDLE, STOP, "done-quotes.txt", last=ASKED, asks_as_needs=True)
check("with asks_as_needs, it counts as needs, and still says asks", d["state"] == "needs" and d["asks"] is True, d)
d = decide(IDLE, STOP, "done-quotes.txt", last="All done.")
check("a finished turn that asks nothing has asks false", d["state"] == "finished" and d["asks"] is False, d)

# ── no flicker: a finish is held until it is confirmed ──
hold = hub_status.Settle()
row = lambda state, why="screen", decisive=False: {"state": state, "why": why, "asks": False, "asking": "", "decisive": decisive}
t = 1000.0
check("working is reported at once", hold.report("a", row("working"), t)["state"] == "working")
check("a first sighting of a finish is held as working", hold.report("a", row("finished", "status file"), t + 1)["state"] == "working")
check("a held finish says why", hold.report("a", row("finished", "status file"), t + 1.2)["why"].startswith("holding"))
check("working again drops the held finish", hold.report("a", row("working"), t + 1.4)["state"] == "working")
check("a finish seen again later starts over", hold.report("a", row("finished"), t + 2)["state"] == "working")
check("a finish that held past the wait is reported", hold.report("a", row("finished"), t + 2 + hub_status.HOLD)["state"] == "finished")
check("a finished session stays finished", hold.report("a", row("finished"), t + 9)["state"] == "finished")
check("a decisive finish (the Stop hook, no spinner) is reported at once", hold.report("b", row("working"), t)["state"] == "working" and hold.report("b", row("finished", decisive=True), t + 0.1)["state"] == "finished")
check("needs is never held", hold.report("c", row("working"), t)["state"] == "working" and hold.report("c", row("needs"), t + 0.1)["state"] == "needs")
check("an asks-as-needs finish is held like a finish", hold.report("d", row("working"), t)["state"] == "working" and hold.report("d", {**row("needs"), "asks": True}, t + 0.1)["state"] == "working")
hold.forget_except({"a"})
check("sessions that are gone are forgotten", set(hold.seen) == {"a"}, hold.seen)

# ── a finish that the stop hook decided is decisive ──
check("the Stop hook with no spinner is decisive", decide(IDLE, STOP, "done-quotes.txt")["decisive"])
check("the status file alone is not decisive", not decide(IDLE, TOOL, "done-quotes.txt")["decisive"])

# ── a working the hooks left behind with no Stop after it: idle, no hook for ten minutes, nothing on screen ──
OLD = {"state": "working", "at": NOW - 21 * 3600, "turn": NOW - 22 * 3600}  # an older hook's idle compaction, as a live session had it
d = decide({"pid": 1, "status": "shell", "statusUpdatedAt": (OLD["at"] - 1) * 1000}, OLD, "done-quotes.txt")
check("a working no hook spoke of for hours, Claude not busy, is done", d["state"] == "finished" and "no hook for" in d["why"], d)
check("but a long tool call while Claude is busy is still working", decide({**BUSY, "statusUpdatedAt": (OLD["at"] - 1) * 1000}, OLD, "done-quotes.txt")["state"] == "working")
check("and so is one with the spinner on screen", decide({"pid": 1, "status": "shell"}, OLD, "working-footer.txt")["state"] == "working")
check("ten quiet minutes are needed for that", decide({"pid": 1, "status": "shell", "statusUpdatedAt": (NOW - 60) * 1000}, {**OLD, "at": NOW - 60}, "done-quotes.txt")["state"] == "working")

# ── the hook: when a turn starts, and a compaction keeps the state it found ──
HOOK = Path(__file__).resolve().parent.parent / "hub_event.py"
lab = Path(tempfile.mkdtemp(prefix="hub-turn."))
bare = {k: v for k, v in os.environ.items() if not k.startswith("HUB_")}


def fire(sid, name, **extra):
    subprocess.run(["/usr/bin/python3", str(HOOK)], input=json.dumps({"hook_event_name": name, "transcript_path": "", **extra}), text=True,
                   env={**bare, "HUB_SESSION": sid, "HUB_STATE": str(lab)}, check=True)
    return json.loads((lab / "events" / f"{sid}.json").read_text())


fire("idlecomp", "UserPromptSubmit")
started = fire("idlecomp", "PreToolUse", tool_name="Bash", tool_input={"command": "ls"})["turn"]
fire("idlecomp", "PostToolUse", tool_name="Bash", tool_input={"command": "ls"})
fire("idlecomp", "Stop")
seen = [fire("idlecomp", "PreCompact", trigger="auto")["state"], fire("idlecomp", "SessionStart", source="compact")["state"], fire("idlecomp", "PostCompact", trigger="auto")["state"]]
check("Claude compacting by itself while idle leaves the session finished", seen == ["finished"] * 3, seen)
time.sleep(1.1)
woke = fire("idlecomp", "PreToolUse", tool_name="Read", tool_input={"file_path": "/x"})
check("a turn a background task starts, with no prompt, gets its own clock", woke["state"] == "working" and woke["turn"] > started + 1, [started, woke["turn"]])
fire("incomp", "UserPromptSubmit")
turn = fire("incomp", "PreToolUse", tool_name="Bash", tool_input={"command": "ls"})["turn"]
pre = fire("incomp", "PreCompact", trigger="auto")
seen = [pre["state"], bool(pre["compacting"]), fire("incomp", "SessionStart", source="compact")["state"], fire("incomp", "PostCompact", trigger="auto")["state"]]
check("a compaction inside a turn shows as compacting, and the turn goes on after it", seen == ["working", True, "working", "working"], seen)
time.sleep(1.1)
check("and keeps the turn's clock", fire("incomp", "PostToolUse", tool_name="Bash", tool_input={"command": "ls"})["turn"] == turn)
fire("manual", "Stop")
seen = [fire("manual", "PreCompact", trigger="manual")["state"], fire("manual", "SessionStart", source="compact")["state"], fire("manual", "PostCompact", trigger="manual")["state"]]
check("a compaction you asked for shows as working, then finished again", seen == ["working", "working", "finished"], seen)
fire("perm", "UserPromptSubmit")
asked = fire("perm", "PermissionRequest", tool_name="Bash", tool_input={"command": "ls"})["turn"]
time.sleep(1.1)
check("answering a permission goes on with the same turn", fire("perm", "PostToolUse", tool_name="Bash", tool_input={"command": "ls"})["turn"] == asked)

print(f"\n{fails} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
