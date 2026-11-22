"""The terminal's extras, from herdr's most-asked: a scratch shell over a session, tmux's copy and scroll keys as
Settings says, and alerts when a session prints a line that matches a pattern.

- Scratch: a plain shell in the session's folder, in a tmux session of its own named pop-<sid>. Not hub-<sid>, so
  nothing lists it as a session: sessions are the hub's own files (META), and a terminal attaches to hub-<sid> unless it
  asks for the scratch. Hidden, it keeps running; Close ends it, and so does its session ending.
- tmux, as Settings › Features says: a double-click takes a whole path or link (word-separators), and ⇧PgUp and ⇧PgDn
  scroll half a screen. The page only sends ⇧PgUp and ⇧PgDn while that switch is on: xterm.js kept them before.
  Applied again whenever the tmux server is a new one, or the setting changed.
- Alerts: one look every STEP seconds at each window's last output (one tmux call). Only a session that printed since,
  and that has a pattern for its project, is captured; a line counts once, the first time it is seen, so a screen
  redrawn or scrolled never tells again. What matched is kept (HITS) and sent to open pages with the state; a page
  that opens later tells what it hasn't told yet. Nothing is captured while the switch is off or no pattern is set.
"""
import json, re, threading, time
from pathlib import Path

import hub_data as hub
import hub_settings as settings

SCRATCH = "pop-"  # pop-<sid>: a session's scratch shell
STEP = 1.5  # seconds between looks at the panes
TOKEN_SEPARATORS = " \"'`();<>[]{}|,"  # what ends a double-clicked word, so paths, links, flags and emails stay whole (never ending in ; which tmux reads as a new command)
SHELLS = {"zsh", "-zsh", "bash", "-bash", "sh", "-sh", "fish", "login"}
HITS = hub.STATE / "triggers.json"
KEEP_HITS = 50  # the last alerts, for a page that opens later
ONCE_FOR = 900  # a line already told isn't told again for this long
PER_MINUTE = 3  # at most this many alerts from one session a minute
LINE = 400  # characters of a line that are matched

_lock = threading.Lock()
_applied = {"server": None, "word": None, "page": None, "patterns": None}
_activity = {}  # tmux session name -> (its window_activity, when it was looked at)
_lines = {}  # sid -> the lines its last capture held
_typing = {}  # sid -> the line its cursor was on then
_told = {}  # (sid, line) -> when it was told
_hits = []
_seq = 0
_projects = {}  # sid -> its project, from the hub's own file


def _load_hits():
    global _hits, _seq
    try:
        kept = json.loads(HITS.read_text())
        _hits = [h for h in kept if isinstance(h, dict) and isinstance(h.get("id"), int)][-KEEP_HITS:]
        _seq = max([h["id"] for h in _hits] or [0])
    except (OSError, ValueError):
        _hits, _seq = [], 0


def hits() -> list:
    with _lock:
        return [dict(h) for h in _hits]


# ── tmux, as Settings says ──
def _bindings(on: bool):
    """⇧PgUp and ⇧PgDn: half a screen up or down tmux's history. A full-screen program (vim, less) gets the key itself."""
    if on:
        for table in ("copy-mode", "copy-mode-vi"):
            hub.tmux("bind-key", "-T", table, "S-PPage", "send-keys", "-X", "halfpage-up")
            hub.tmux("bind-key", "-T", table, "S-NPage", "send-keys", "-X", "halfpage-down")
        hub.tmux("bind-key", "-n", "S-PPage", "if-shell", "-F", "#{alternate_on}", "send-keys S-PPage", "copy-mode -e ; send-keys -X halfpage-up")
        hub.tmux("bind-key", "-n", "S-NPage", "if-shell", "-F", "#{alternate_on}", "send-keys S-NPage")
    else:
        for table in ("copy-mode", "copy-mode-vi"):
            hub.tmux("unbind-key", "-T", table, "S-PPage")
            hub.tmux("unbind-key", "-T", table, "S-NPage")
        hub.tmux("unbind-key", "-n", "S-PPage")
        hub.tmux("unbind-key", "-n", "S-NPage")


def sync(server):
    """Puts tmux's options where Settings says, once per tmux server and per change."""
    word, page = settings.value("feature_word_copy") is True, settings.value("feature_page_keys") is True
    if server is None:
        _applied.update(server=None)
        return
    if _applied["server"] == server and _applied["word"] == word and _applied["page"] == page:
        return
    if _applied["server"] != server or _applied["word"] != word:
        if word:
            hub.tmux("set-option", "-g", "word-separators", TOKEN_SEPARATORS)
        else:
            hub.tmux("set-option", "-gu", "word-separators")
    if _applied["server"] != server or _applied["page"] != page:
        _bindings(page)
    _applied.update(server=server, word=word, page=page)


# ── scratch shells ──
def _meta(sid: str) -> dict:
    if not hub.SESSION_ID.match(sid or ""):
        raise hub.Refused("That isn't a session.")
    try:
        return json.loads((hub.META / f"{sid}.json").read_text())
    except (OSError, ValueError):
        raise hub.Refused("That session is gone.")


def _scratch_folder(meta: dict) -> str:
    for folder in (meta.get("folder"), meta.get("repo")):
        if folder and Path(folder).is_dir():
            return folder
    return str(Path.home())


def _busy(name: str) -> str:
    """What runs in the scratch shell now, if it isn't the shell itself waiting."""
    out = hub.tmux("display-message", "-p", "-t", f"={name}:", "#{pane_current_command}")
    command = out.stdout.strip() if out.returncode == 0 else ""
    return "" if command in SHELLS else command


def scratch(body: dict) -> dict:
    sid, op = str(body.get("sid", "")), body.get("op")
    meta = _meta(sid)
    name = f"{SCRATCH}{sid}"
    live = name in hub.tmux_sessions()
    if op == "open":
        if f"hub-{sid}" not in hub.tmux_sessions():
            raise hub.Refused("That session isn't running, so it has no scratch terminal.")
        folder = _scratch_folder(meta)
        if not live:
            made = hub.tmux("new-session", "-d", "-s", name, "-x", "120", "-y", "32", "-c", folder, "-e", f"PATH={hub.ENV['PATH']}")
            if made.returncode != 0:
                raise hub.Refused("The scratch terminal didn't start. Try again.")
        return {"alive": True, "folder": folder, "busy": _busy(name)}
    if op == "close":
        if live:
            hub.tmux("kill-session", "-t", f"={name}")
        return {"alive": False}
    if op == "state":
        return {"alive": live, "busy": _busy(name) if live else ""}
    raise hub.Refused("Open, close or state.")


def scratches() -> dict:
    return {"live": sorted(n[len(SCRATCH):] for n in hub.tmux_sessions() if n.startswith(SCRATCH))}


# ── alerts from output ──
def _patterns() -> list:
    if settings.value("feature_triggers") is not True:
        return []
    out = []
    for t in settings.value("term_triggers") or []:
        try:
            out.append((re.compile(t["pattern"], re.I), t["pattern"], t.get("project", "")))
        except re.error:
            continue
    return out


def _project_of(sid: str) -> str:
    if sid not in _projects:
        try:
            _projects[sid] = json.loads((hub.META / f"{sid}.json").read_text()).get("project", "")
        except (OSError, ValueError):
            return ""
    return _projects[sid]


CUT = "\x01hub-cursor "  # marks where one tmux command's output ends and the next's begins


def _screen(name: str) -> list:
    """The pane's last lines, wrapped rows joined, without the line the cursor is on: that one is still being typed (a
    prompt, Claude's input box), and every key would make it a new line. One tmux call, so all three are of one moment."""
    target = f"={name}:"
    out = hub.tmux("capture-pane", "-p", "-J", "-S", "-60", "-t", target, ";", "display-message", "-p", "-t", target, CUT + "#{cursor_y}", ";",
                   "capture-pane", "-p", "-t", target).stdout
    text, _, rest = out.partition(CUT)
    at, _, rows = rest.partition("\n")
    rows = rows.split("\n")
    typing = rows[int(at)].strip() if at.isdigit() and int(at) < len(rows) else ""
    lines = [line.rstrip()[:LINE] for line in text.splitlines() if line.strip()]
    return [line for line in lines if not (typing and line.endswith(typing[:LINE]))], typing


def matches(pattern: str, text: str) -> list:
    """The lines of `text` that `pattern` finds, as an alert would."""
    rx = re.compile(pattern, re.I)
    return [line for line in text.splitlines() if line.strip() and rx.search(line[:LINE])]


def test(body: dict) -> dict:
    pattern, text = body.get("pattern"), body.get("text", "")
    if not isinstance(pattern, str) or not isinstance(text, str) or len(text) > 20000:
        raise hub.Refused("A pattern and some text to try it on.")
    try:
        return {"ok": True, "lines": matches(pattern, text)[:20]}
    except re.error as error:
        return {"ok": False, "error": f"That pattern doesn't work: {error}.", "lines": []}


def _scan(sid: str, name: str, wanted: list, now: float) -> list:
    lines, typing = _screen(name)
    before, typed = _lines.get(sid), _typing.get(sid, "")
    _lines[sid], _typing[sid] = set(lines), typing.strip()
    if before is None:
        return []  # the first look is what was there already
    out = []
    recent = sum(1 for h in _hits if h["sid"] == sid and now - h["at"] < 60)
    for line in lines:
        if line in before or now - _told.get((sid, line), 0) < ONCE_FOR:
            continue
        if len(typed) >= 2 and line.strip().startswith(typed):
            continue  # what the person typed, sent: the line the cursor was on at the last look, finished
        for rx, pattern, _ in wanted:
            if rx.search(line):
                _told[(sid, line)] = now
                if recent < PER_MINUTE:
                    out.append({"sid": sid, "pattern": pattern, "line": line.strip()[:200], "at": now})
                    recent += 1
                break
    return out


def _turn():
    global _seq
    listed = hub.tmux("list-windows", "-a", "-F", "#{pid}\t#{session_name}\t#{window_activity}")
    rows = [line.split("\t") for line in listed.stdout.splitlines() if line.count("\t") == 2] if listed.returncode == 0 else []
    sync(rows[0][0] if rows else None)
    names = {r[1] for r in rows}
    for name in names:  # a scratch shell goes with its session
        if name.startswith(SCRATCH) and f"hub-{name[len(SCRATCH):]}" not in names:
            hub.tmux("kill-session", "-t", f"={name}")
    patterns, now, found = _patterns(), time.time(), []
    key = [(p[1], p[2]) for p in patterns]
    if key != _applied.get("patterns"):  # turned on, off or changed: what is on screen now is where each session starts
        _applied["patterns"] = key
        _lines.clear()
        _activity.clear()
    for _, name, when in rows:
        if not name.startswith("hub-") or not patterns:
            continue
        sid = name[4:]
        wanted = [p for p in patterns if not p[2] or p[2] == _project_of(sid)]
        if not wanted:
            continue
        # window_activity is in whole seconds: a look taken in the second the pane last printed in is taken again after it.
        last = _activity.get(name)
        if last and last[0] == when and last[1] >= (int(when) if when.isdigit() else 0) + 1 and sid in _lines:
            continue
        _activity[name] = (when, now)
        found += _scan(sid, name, wanted, now)
    for gone in [sid for sid in _lines if f"hub-{sid}" not in names]:
        _lines.pop(gone, None)
        _typing.pop(gone, None)
        _projects.pop(gone, None)
    for key in [k for k, at in _told.items() if now - at > ONCE_FOR]:
        del _told[key]
    if not found:
        return
    with _lock:
        for h in found:
            _seq += 1
            h["id"] = _seq
            h["project"] = _project_of(h["sid"])
            _hits.append(h)
        del _hits[:-KEEP_HITS]
        try:
            spare = HITS.with_suffix(".tmp")
            spare.write_text(json.dumps(_hits))
            spare.replace(HITS)
        except OSError:
            pass
    import hub_push  # the open pages hear at once
    hub_push.kick()


def _run():
    while True:
        time.sleep(STEP)
        try:
            _turn()
        except Exception as error:  # the loop keeps going
            print(f"error: terminal loop: {type(error).__name__}: {error}", flush=True)


def start():
    """Called once from the server's main()."""
    _load_hits()
    threading.Thread(target=_run, name="terminal", daemon=True).start()


def route(method: str, parts: list, body: dict):
    if method == "GET" and parts == ["scratch"]:
        return scratches()
    if method == "POST" and parts == ["scratch"]:
        return scratch(body)
    if method == "POST" and parts == ["test"]:
        return test(body)
    return None
