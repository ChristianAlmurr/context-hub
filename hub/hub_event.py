#!/usr/bin/env python3
"""Claude Code hook for sessions started by Context Hub: records one plain state per session, where its transcript is,
and what it is doing: the tool running now (or last this turn), when the turn started, a compaction, an API failure.

It runs on every tool call, so it reads and writes one small file and never fails the session: anything it can't do
it leaves undone."""
import fcntl, json, os, sys, time

STATES = {"UserPromptSubmit": "working", "PreToolUse": "working", "PostToolUse": "working", "PostToolUseFailure": "working",
          "PreCompact": "working", "PostCompact": "working", "Stop": "finished", "StopFailure": "error",
          "SessionEnd": "ended", "SessionStart": "finished", "PermissionRequest": "needs", "SubagentStart": "working", "SubagentStop": "working", "PostToolBatch": "working"}
SUBAGENT_TOOLS = ("PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch", "PermissionRequest", "SubagentStart", "SubagentStop")


def target_of(tool: str, given: dict, cwd: str) -> str:
    """What a tool works on, in a few words: a path from the session's folder, a command, a pattern, a page."""
    if not isinstance(given, dict):
        return ""
    path = given.get("file_path") or given.get("notebook_path") or given.get("path") or ""
    if tool == "Bash":
        return " ".join(str(given.get("command", "")).split())[:160]
    if tool in ("Grep", "Glob"):
        return str(given.get("pattern", ""))[:120]
    if tool == "WebFetch":
        return str(given.get("url", ""))[:160]
    if tool == "WebSearch":
        return str(given.get("query", ""))[:120]
    if tool in ("Agent", "Task"):
        return str(given.get("description", ""))[:120]
    if tool == "Skill":
        return str(given.get("skill", ""))[:80]
    if path:
        path = str(path)
        if cwd and path.startswith(cwd.rstrip("/") + "/"):
            return path[len(cwd.rstrip("/")) + 1:][:200]
        home = os.path.expanduser("~")
        return ("~" + path[len(home):] if path.startswith(home + "/") else path)[:200]
    return ""


def main():
    sid = os.environ.get("HUB_SESSION", "")
    if not sid.isalnum():
        return
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(event, dict):
        return
    name = event.get("hook_event_name", "")
    state = STATES.get(name)
    if name == "Notification":
        kind = str(event.get("notification_type", ""))
        message = str(event.get("message", ""))
        if kind in ("permission_prompt", "elicitation_dialog") or "permission" in message.lower():
            state = "needs"
    if not state:
        return
    if name == "PostToolBatch" and not event.get("agent_id"):
        return  # the session's own batch: its PostToolUse said all there is
    if name in ("SubagentStart", "SubagentStop") and not event.get("agent_type"):
        return  # Claude Code's own helpers (titles, summaries) report no agent type, and are no work of the session's
    # The hub that started this session says where its state is. A session from before hubs did has no HUB_STATE and
    # belongs to the installed hub. An empty or relative value is a mistake, and guessing a folder would cross two hubs.
    home = os.environ.get("HUB_STATE")
    if home is None:
        home = os.path.expanduser("~/.local/state/agent-hub")
    elif not os.path.isabs(home):
        sys.exit(f"HUB_STATE must be an absolute path, and {home!r} isn't.")
    folder = os.path.join(home, "events")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{sid}.json")
    now = time.time()
    # Tool calls can run side by side, so the read and the write are one step under a lock.
    with open(os.path.join(folder, f".{sid}.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(path) as f:
                was = json.load(f)
            was = was if isinstance(was, dict) else {}
        except (OSError, ValueError):
            was = {}
        tool, given, cwd = str(event.get("tool_name", "")), event.get("tool_input") or {}, str(event.get("cwd", ""))
        record = {"state": state, "hook": name, "at": now, "message": str(event.get("message", ""))[:200],
                  "transcript": str(event.get("transcript_path", "")) or was.get("transcript", ""),
                  "turn": was.get("turn"), "tool": was.get("tool"), "compacting": None, "failure": None, "cleared": was.get("cleared")}
        before = was.get("state")
        record["background"] = was.get("background") or {}
        # Each subagent's open permission prompt, by agent id, with its words. Its next hook of any kind (a step, the end
        # of its batch, which comes at once when you deny it, or its stop) says it was answered. While one is open the
        # session needs you, whatever else its hooks say; the hub clears them all when Claude's status says no dialog
        # waits any more (hub_status.resolve_needs).
        asks = record["asks"] = dict(was.get("asks") or {}) if isinstance(was.get("asks"), dict) else {}
        agent = str(event.get("agent_id") or "")
        if agent and name in SUBAGENT_TOOLS:
            # A subagent's own steps say what the subagent does, never what the session's own turn does: its tool goes to
            # `sub`, and the session keeps its state, turn and tool. A subagent that runs in the background after the turn
            # ended (Claude Code 2.1.330 starts agents in the background) keeps the session in `background` until it stops.
            # Its permission prompt needs you like any other; a step after it means it was answered.
            record.update(tool=was.get("tool"), sub=was.get("sub"), message=str(was.get("message", ""))[:200])
            answered = "finished" if record["background"] else "working"  # back to the background, or to the turn it is part of
            if name == "PermissionRequest":
                target = target_of(tool, given, cwd)
                asks[agent] = record["message"] = f"Allow {tool}{': ' + target if target else ''}?"[:200]
            else:
                asks.pop(agent, None)
            state = record["state"] = "needs" if name == "PermissionRequest" else answered if before == "needs" else before or "working"
            if name == "PreToolUse":
                record["sub"] = {"agent": agent, "tool": tool, "target": target_of(tool, given, cwd), "since": now, "done": None}
            elif name in ("PostToolUse", "PostToolUseFailure") and isinstance(was.get("sub"), dict):
                record["sub"] = {**was["sub"], "done": now}
            elif name == "SubagentStop":
                record["background"] = {k: v for k, v in record["background"].items() if k != agent}
                if isinstance(record.get("sub"), dict) and record["sub"].get("agent") == agent:
                    record["sub"] = None
            if record["state"] == "working" and before not in ("working", "needs"):
                record["state"] = before or "finished"  # a background agent's step is not a new turn of the session's own
        elif name in ("SubagentStart", "SubagentStop"):
            return
        elif name == "UserPromptSubmit":
            record.update(turn=now, tool=None, asks={})  # no prompt can be sent while a dialog is open
        elif name == "PreToolUse":
            record["tool"] = {"tool": tool, "target": target_of(tool, given, cwd), "since": now, "done": None, "failed": False}
            record["turn"] = record["turn"] or now
        elif name in ("PostToolUse", "PostToolUseFailure"):
            last = was.get("tool") if isinstance(was.get("tool"), dict) else None
            if not last or last.get("tool") != tool:  # a call that started before the hook knew of it
                last = {"tool": tool, "target": target_of(tool, given, cwd), "since": now}
            record["tool"] = {**last, "done": now, "failed": name == "PostToolUseFailure"}
        # A compaction keeps the state it found. Claude compacts by itself while idle ("Compacted while idle"), and no Stop
        # follows that, so reading it as working left a finished session "Thinking" since its last turn, for hours. In a
        # turn, or when you asked for it, it shows as compacting, and the state it found comes back after it.
        elif name == "PreCompact":
            busy = before in ("working", "needs") or str(event.get("trigger", "")) == "manual"
            record.update(state="working" if busy else before or "finished", compacting=now if busy else None, before_compact=before)
        elif name == "SessionStart" and str(event.get("source", "")) == "compact":
            record.update(state=before or "finished", compacting=was.get("compacting"), before_compact=was.get("before_compact"))
        elif name == "PostCompact":
            back = was.get("before_compact", before)
            record["state"] = "working" if back in ("working", "needs", None) else back
        elif name == "SessionEnd":
            record.update(background={}, asks={})
        elif name == "Stop":
            # What still runs when the turn ends: background agents and shells, by id, with a few words for each.
            tasks = event.get("background_tasks") if isinstance(event.get("background_tasks"), list) else []
            record["background"] = {str(t.get("id")): str(t.get("description") or t.get("type") or "")[:120] for t in tasks
                                    if isinstance(t, dict) and t.get("id") and t.get("status") in ("running", "pending", None)}
        elif name == "StopFailure":
            error = event.get("error")
            words = error if isinstance(error, str) else json.dumps(error) if error else ""
            # Claude Code 2.1.330 sends a bare kind ("server_error") and says what happened in the last message it showed.
            shown = str(event.get("last_assistant_message") or "").strip()
            shown = shown[len("API Error:"):].strip() if shown.startswith("API Error:") else ""
            details = str(event.get("error_details") or shown or "")
            record["failure"] = {"at": now, "error": words[:120], "details": details[:300]}
            record["message"] = (details or words)[:200]
        elif name == "PermissionRequest":
            target = target_of(tool, given, cwd)
            record["message"] = f"Allow {tool}{': ' + target if target else ''}?"[:200]
            if isinstance(was.get("tool"), dict) and was["tool"].get("tool") == tool:
                record["tool"] = was["tool"]
        elif name == "Notification" and was.get("state") == "needs" and str(was.get("message", "")).startswith("Allow "):
            record["message"] = was["message"]  # the permission request already said what it asks, in fewer words
        # A subagent's prompt still open needs you, whatever the hook that came now: the turn's own Stop often lands just
        # after its agents asked, and another agent's step says nothing of this one's prompt.
        if asks and record["state"] != "needs" and record["state"] in ("working", "finished"):
            record.update(state="needs", message=list(asks.values())[-1])
        # A turn that starts without a prompt (a background task's notice wakes Claude up) is a new turn all the same: its
        # clock starts with its first step, not with the prompt of the turn before.
        if record["state"] == "working" and name in ("PreToolUse", "PostToolUse", "PostToolUseFailure") and before not in ("working", "needs"):
            record["turn"] = now
        tmp = os.path.join(folder, f".{sid}.{os.getpid()}")
        with open(tmp, "w") as f:
            json.dump(record, f)
        os.replace(tmp, path)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # a hook that fails would show in the session; what it records is never worth that
        pass
