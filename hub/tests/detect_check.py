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
check("a fresh session's empty box is nothing", hub_status.screen_says(screen("start.txt")) == {"working": False, "box": True, "dialog": "", "viewer": False, "question": "", "thinking": False, "retry": None}, hub_status.screen_says(screen("start.txt")))

# ── named sessions (--name): Claude Code 2.1.330 writes the name into the input box's top rule ──
# named-*.txt are real panes of 2.1.330 sessions the hub started, so their box's rule ends in "hub-test-… 840e ─".
named = {name: hub_status.screen_says(screen(f"named-{name}.txt")) for name in ("working", "thinking", "retrying", "idle")}
check("a named session's footer says working", named["working"]["working"] and not named["working"]["thinking"], named["working"])
check("a named session at rest is not working", not named["idle"]["working"] and not named["idle"]["dialog"], named["idle"])
check("the spinner's 'thinking with high effort' is thinking", named["thinking"]["working"] and named["thinking"]["thinking"], named["thinking"])
check("the spinner's 'retrying in 1s · attempt 2/10' is a retry, with its words", named["retrying"]["retry"] == {"said": "Connection refused — a firewall or proxy may be blocking it (ECONNREFUSED)", "attempt": 2, "of": 10}, named["retrying"])
check("'thought for 2s' is no longer thinking", not hub_status.THINKING.search("· Unfurling… (3s · ↓ 249 tokens · thought for 2s)"))
check("working_in sees a named session work (Close refuses then)", hub_status.working_in(screen("named-working.txt")) and not hub_status.working_in(screen("named-idle.txt")))
orb = lambda d, event, track=None: hub_status.orb_of(d["state"], event, track or {}, d)
d = decide(BUSY, {"state": "working", "hook": "UserPromptSubmit", "at": NOW - 2, "turn": NOW - 2}, "named-thinking.txt")
check("a turn whose spinner says thinking has the thinking orb", d["state"] == "working" and orb(d, {"state": "working", "turn": NOW - 2}) == "reasoning", d)
d = decide(BUSY, {"state": "working", "hook": "UserPromptSubmit", "at": NOW - 2, "turn": NOW - 2}, "named-working.txt")
check("a turn that writes without thinking has the working orb", orb(d, {"state": "working", "turn": NOW - 2}) == "working", d)
d = decide(BUSY, {"state": "working", "hook": "UserPromptSubmit", "at": NOW - 2, "turn": NOW - 2}, "named-retrying.txt")
check("a turn the API retries has the retrying orb", orb(d, {"state": "working", "turn": NOW - 2}) == "retrying", d)
d = decide(BUSY, {"state": "working", "hook": "PreToolUse", "at": NOW - 2, "turn": NOW - 3, "tool": {"tool": "Grep", "since": NOW - 2, "done": None}}, "named-thinking.txt")
check("a running search tool wins over the spinner", orb(d, {"state": "working", "turn": NOW - 3, "tool": {"tool": "Grep", "since": NOW - 2, "done": None}}) == "searching", d)
# A permission answered: the dialog is gone and the footer says working, and no hook comes until the tool ends.
ASKING = {"state": "needs", "hook": "Notification", "at": NOW - 5, "message": "Allow Bash: sleep 20?", "turn": NOW - 9, "tool": {"tool": "Bash", "since": NOW - 6, "done": None}}
d = decide(BUSY, ASKING, "named-working.txt")
check("a permission answered, its tool running, reads working at once", d["state"] == "working" and orb(d, ASKING) == "using", d)
check("but not in the moment the prompt is still drawing", decide(BUSY, {**ASKING, "hook": "PermissionRequest", "at": NOW - 0.5}, "named-working.txt")["state"] == "needs")
check("and a prompt still on screen needs you", decide(BUSY, ASKING, "perm-bash.txt")["state"] == "needs")
# A subagent's permission prompt. sub-*.txt are real 2.1.330 panes: the prompt ("Bash command · from the general-purpose
# agent") in place of the input box, and the box back after it was answered, the turn over and the agents listed under
# the footer ("⏺ main", a row each). Claude's status file says "waiting" while the prompt is open and "busy" at once after.
SUB_ASKS = {"state": "needs", "hook": "PermissionRequest", "at": NOW - 4, "message": "Allow Bash: touch made-b.txt?", "turn": NOW - 9,
            "background": {"a1": "Run the command"}, "sub": {"agent": "a1", "tool": "Bash", "since": NOW - 4, "done": None}}
WAITING = {"pid": 1, "status": "waiting", "statusUpdatedAt": (NOW - 3.9) * 1000}
ANSWERED = {"pid": 1, "status": "busy", "statusUpdatedAt": (NOW - 1) * 1000}
for name in ("sub-perm.txt", "sub-perm-queued.txt"):
    check(f"{name}: a subagent's prompt is a permission dialog, and no input box", hub_status.screen_says(screen(name))["dialog"] == "permission" and not hub_status.screen_says(screen(name))["box"], hub_status.screen_says(screen(name)))
for name in ("sub-answered.txt", "sub-answered-three.txt"):
    said = hub_status.screen_says(screen(name))
    check(f"{name}: the input box is back above the agents' list, nothing running in the footer", said["box"] and not said["dialog"] and not said["working"], said)
d = decide(WAITING, SUB_ASKS, "sub-perm.txt")
check("a subagent's prompt on screen needs you, with the hook's words", d["state"] == "needs" and d["asking"] == "Allow Bash: touch made-b.txt?", d)
d = decide(ANSWERED, SUB_ASKS, "sub-answered.txt")
check("answered: the box is back, Claude busy, so back to the background at once", d["state"] == "working" and d["background"] and orb(d, SUB_ASKS) == "background" and d["why"].startswith("screen: answered"), d)
d = decide(ANSWERED, SUB_ASKS, "sub-answered-three.txt")
check("with three agents listed under the footer too", d["state"] == "working" and d["background"], d)
d = decide({**ANSWERED, "status": "idle"}, {**SUB_ASKS, "background": {}}, "sub-answered.txt")
check("denied, with nothing left in the background, is done", d["state"] == "finished", d)
d = decide(ANSWERED, SUB_ASKS, "sub-perm-queued.txt")
check("the next prompt in line keeps it needs, whatever the status says", d["state"] == "needs", d)
d = decide(WAITING, SUB_ASKS, "sub-answered.txt")
check("the box back while Claude's status still says waiting is not answered", d["state"] == "needs", d)
d = decide(ANSWERED, {**SUB_ASKS, "at": NOW - 0.5}, "sub-answered.txt")
check("nor in the moment after the hook, before its prompt has drawn", d["state"] == "needs", d)
d = decide(ANSWERED, SUB_ASKS, "")
check("the status moving on from waiting says it too, with no screen to read", d["state"] == "working" and d["background"] and "status" in d["why"], d)
d = decide({**ANSWERED, "statusUpdatedAt": (NOW - 5) * 1000}, SUB_ASKS, "")
check("but a busy from before the prompt says nothing", d["state"] == "needs", d)
d = decide(ANSWERED, {**SUB_ASKS, "hook": "Notification", "at": NOW - 0.3}, "sub-answered.txt")
check("a Notification comes once the prompt has shown a while, so it needs no time to draw", d["state"] == "working", d)

# Background agents: the turn ended, an agent works on.
BG = {"state": "finished", "hook": "PreToolUse", "at": NOW - 2, "background": {"a1": "Run the tests"}, "sub": {"agent": "a1", "tool": "Bash", "target": "sleep 12", "since": NOW - 2, "done": None}}
d = decide(IDLE, BG, "named-idle.txt")
check("a turn over with an agent at work in the background is working, background", d["state"] == "working" and d["background"] and orb(d, BG) == "background", d)
check("its activity is the agent's step", hub_status.activity_of(BG, True)["target"] == "sleep 12")
check("with nothing left in the background it is done", decide(IDLE, {**BG, "background": {}, "hook": "SubagentStop"}, "named-idle.txt")["state"] == "finished")
check("ten quiet minutes in the background, Claude not busy, is done", decide({"pid": 1, "status": "idle"}, {**BG, "at": NOW - 700}, "named-idle.txt")["state"] == "finished")
# A finish held back a moment keeps the orb it had, instead of a word nothing said.
hub_status._orbs["held"] = "compacting"
row = {"id": "held", "state": "working", "live": {"held": True}}
hub_status.enrich(row, {"id": "held", "kind": "claude", "project": "@hub"}, None, 0, 0, {})
check("a finish held back keeps its last orb", row["orb"] == "compacting", row["orb"])
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

# A subagent's steps: its own tool, never the session's; the turn ends with it in the background, and it leaves.
fire("sub", "UserPromptSubmit")
fire("sub", "PreToolUse", tool_name="Agent", tool_input={"description": "Run the tests"})
inside = fire("sub", "PostToolUse", tool_name="Bash", tool_input={"command": "ls"}, agent_id="a1", agent_type="general-purpose")
check("a subagent's tool call leaves the session's own tool running", inside["state"] == "working" and inside["tool"]["tool"] == "Agent" and not inside["tool"].get("done"), inside)
fire("sub", "PostToolUse", tool_name="Agent", tool_input={"description": "Run the tests"})
ended = fire("sub", "Stop", background_tasks=[{"id": "a1", "type": "subagent", "status": "running", "description": "Run the tests"}])
check("a turn that ends with an agent still running keeps it in background", ended["state"] == "finished" and ended["background"] == {"a1": "Run the tests"}, ended)
step = fire("sub", "PreToolUse", tool_name="Bash", tool_input={"command": "sleep 12"}, agent_id="a1", agent_type="general-purpose")
check("the background agent's step is its own, and no new turn", step["state"] == "finished" and step["sub"]["tool"] == "Bash" and step["turn"] == ended["turn"], step)
asks = fire("sub", "PermissionRequest", tool_name="Bash", tool_input={"command": "rm x"}, agent_id="a1", agent_type="general-purpose")
check("a subagent's permission prompt needs you", asks["state"] == "needs" and asks["message"] == "Allow Bash: rm x?", asks)
check("a step after it means it was answered: back to the background", fire("sub", "PostToolUse", tool_name="Bash", tool_input={"command": "rm x"}, agent_id="a1", agent_type="general-purpose")["state"] == "finished")
gone = fire("sub", "SubagentStop", agent_id="a1", agent_type="general-purpose")
check("its stop takes it out of the background", gone["background"] == {} and gone["sub"] is None, gone)
helper = fire("sub", "SubagentStop", agent_id="zz")
check("a helper's stop with no agent type changes nothing", helper == gone, helper)
# Each subagent's open prompt is kept by its agent id: one answered leaves the other open, and the turn's own Stop, which
# often lands just after its agents asked, doesn't take the need away. A deny sends only PostToolBatch, at once.
fire("two", "UserPromptSubmit")
fire("two", "Stop", background_tasks=[{"id": a, "type": "subagent", "status": "running"} for a in ("a1", "a2")])
fire("two", "PermissionRequest", tool_name="Bash", tool_input={"command": "touch a"}, agent_id="a1", agent_type="general-purpose")
both = fire("two", "PermissionRequest", tool_name="Bash", tool_input={"command": "touch b"}, agent_id="a2", agent_type="general-purpose")
check("two agents asking: both prompts are kept", both["state"] == "needs" and set(both["asks"]) == {"a1", "a2"}, both)
one = fire("two", "PostToolBatch", agent_id="a1", agent_type="general-purpose")
check("one answered (its batch ended): the other still needs you, in its words", one["state"] == "needs" and one["asks"] == {"a2": "Allow Bash: touch b?"} and one["message"] == "Allow Bash: touch b?", one)
none = fire("two", "PostToolBatch", agent_id="a2", agent_type="general-purpose")
check("both answered: back to the background", none["state"] == "finished" and none["asks"] == {} and none["background"], none)
check("the session's own PostToolBatch records nothing", fire("two", "PostToolBatch") == none)
fire("late", "UserPromptSubmit")
fire("late", "PermissionRequest", tool_name="Bash", tool_input={"command": "touch c"}, agent_id="a3", agent_type="general-purpose")
late = fire("late", "Stop", background_tasks=[{"id": "a3", "type": "subagent", "status": "running"}])
check("the turn's Stop after an agent asked still needs you", late["state"] == "needs" and late["message"] == "Allow Bash: touch c?", late)
check("a new prompt from you means no dialog was open", fire("late", "UserPromptSubmit")["asks"] == {})

# The hub keeps what Claude's status said: the prompt the hooks recorded was answered. Without that, a later "waiting"
# of Claude's own (you opened /model while the approved tool runs) read the old prompt as open again.
d = decide(ANSWERED, SUB_ASKS, "sub-answered.txt")
check("answered by Claude's status: decide says which prompt to clear", d.get("resolved") == SUB_ASKS["at"], d)
check("answered by the screen alone, nothing is written", "resolved" not in decide({**ANSWERED, "statusUpdatedAt": (NOW - 5) * 1000}, SUB_ASKS, "sub-answered.txt"))
kept = hub_status.answered_event({**SUB_ASKS, "asks": {"a1": "Allow Bash: touch made-b.txt?"}}, SUB_ASKS["at"], "busy", NOW)
check("the event file after: no prompt open, back to the background", kept["state"] == "finished" and kept["asks"] == {} and kept["background"] and kept["hook"] == "answered", kept)
check("a hook that wrote since is left alone", hub_status.answered_event({**SUB_ASKS, "at": NOW - 1}, SUB_ASKS["at"], "busy", NOW)["state"] == "needs")
check("a main prompt answered with Claude busy is its turn again", hub_status.answered_event({**SUB_ASKS, "background": {}}, SUB_ASKS["at"], "busy", NOW)["state"] == "working")
picker = {**WAITING, "statusUpdatedAt": NOW * 1000}
d = decide(picker, kept, "model-picker.txt")
check("then /model opened while the tool runs: not needs, still in the background", d["state"] == "working" and d["background"], d)
check("where the need left in the file read as needs again", decide(picker, SUB_ASKS, "model-picker.txt")["state"] == "needs")

failed = fire("fail", "StopFailure", error="server_error", last_assistant_message="API Error: Connection refused (ECONNREFUSED)")
check("an API failure keeps the words Claude showed", failed["failure"]["details"] == "Connection refused (ECONNREFUSED)", failed)

print(f"\n{fails} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
