"""What a session is doing right now, for the 3-second poll: the tool it runs, when its turn started, a finer status
for the orb, an error when Claude is gone or the API gave up, how full its context is, what it changed in its folder,
and the ports its processes listen on. Also what acts on that: Clear, Stop a port, Peek and its answer.

Everything here is cheap on the poll. Hook events are one small file. Transcripts are read from where the last read
stopped. git and lsof run in the background and the poll takes the last answer they gave, so a slow folder never
slows the page. What can't be known is left out (null), and never shown as working.
"""
import calendar, json, os, re, signal, subprocess, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hub_base import ENV, HOME, HUB_PROJECT, Refused, run

SEARCHING = {"Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch", "ToolSearch", "NotebookRead"}
RETRY_FRESH = 120  # an API retry older than this, with nothing after it, is no longer "retrying"
TAIL = 2_000_000  # the first read of a long transcript starts this far from its end: only the latest turn matters here
LAST_TEXT = 6000


# ── hook events ──
def event_path(sid: str) -> Path:
    import hub_data as hub
    return hub.EVENTS / f"{sid}.json"


def read_event(sid: str) -> dict:
    try:
        value = json.loads(event_path(sid).read_text())
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def change_event(sid: str, change):
    """The hook's own read-change-write, under its lock, so a Clear never undoes an event that lands at the same time."""
    import fcntl
    path = event_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.parent / f".{sid}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            event = json.loads(path.read_text())
        except (OSError, ValueError):
            event = {}
        change(event)
        spare = path.parent / f".{sid}.clear"
        spare.write_text(json.dumps(event))
        os.replace(spare, path)


# ── transcripts, read from where the last read stopped ──
_tracks, _track_lock = {}, threading.Lock()


def _fresh(path: str) -> dict:
    return {"path": path, "offset": 0, "used": None, "model": "", "retry": None, "said": "", "said_at": "", "prompt_at": "", "last_at": ""}


def _absorb(track: dict, raw: bytes):
    try:
        entry = json.loads(raw)
    except ValueError:
        return
    if not isinstance(entry, dict) or entry.get("isSidechain"):
        return
    kind, at = entry.get("type"), str(entry.get("timestamp", ""))
    if kind == "system":
        if entry.get("subtype") == "api_error":
            error = entry.get("error") if isinstance(entry.get("error"), dict) else {}
            track["retry"] = {"at": at, "said": str(error.get("formatted") or error.get("message") or "")[:200],
                              "attempt": entry.get("retryAttempt"), "of": entry.get("maxRetries")}
        elif entry.get("subtype") == "compact_boundary":
            track["used"] = None  # the next reply says how much the summary takes
        return
    if kind not in ("user", "assistant"):
        return
    track["last_at"], track["retry"] = at, None
    message = entry.get("message") or {}
    if kind == "user":
        content = message.get("content")
        if isinstance(content, str) or (isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "text" for b in content)):
            if not entry.get("isMeta"):
                track["prompt_at"] = at
        return
    usage = message.get("usage") if isinstance(message.get("usage"), dict) else None
    if usage:
        parts = [usage.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")]
        track["used"] = sum(p for p in parts if isinstance(p, int))
    track["model"] = str(message.get("model") or track["model"])
    content = message.get("content")
    if isinstance(content, list):
        text = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
        if text and not text.startswith("<"):
            track["said"], track["said_at"] = text[-LAST_TEXT:], at


def track_of(sid: str, transcript) -> dict:
    """What the transcript says about the latest turn. Reads only what was added since the last poll."""
    if transcript is None:
        return _fresh("")
    path = str(transcript)
    try:
        size = os.stat(path).st_size
    except OSError:
        return _fresh(path)
    with _track_lock:
        track = _tracks.get(sid)
        if track is None or track["path"] != path or size < track["offset"]:
            track = _tracks[sid] = _fresh(path)
            track["offset"] = max(0, size - TAIL)
            track["skip"] = track["offset"] > 0  # starting mid-file: the first line is a fragment
        if size > track["offset"]:
            with open(path, "rb") as handle:
                handle.seek(track["offset"])
                chunk = handle.read()
            end = chunk.rfind(b"\n")
            if end >= 0:
                lines = chunk[:end].split(b"\n")
                if track.pop("skip", False):
                    lines = lines[1:]
                for raw in lines:
                    _absorb(track, raw)
                track["offset"] += end + 1
        return dict(track)


def forget(sid: str):
    with _track_lock:
        _tracks.pop(sid, None)
    _changes.pop(sid, None)


def context_limit(model: str, used) -> int:
    """The window a model reads: 1M for the current families, 200K for Haiku 4.5 and older models."""
    match = re.search(r"(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d{1,2})(?!\d))?", model or "")
    big = True
    if match:
        family, major, minor = match[1], int(match[2]), int(match[3] or 0)
        big = family in ("fable", "mythos") or major >= 5 or (family in ("opus", "sonnet") and major == 4 and minor >= 6)
    elif re.search(r"claude-3", model or ""):
        big = False
    limit = 1_000_000 if big else 200_000
    return 1_000_000 if isinstance(used, int) and used > limit else limit


# ── processes: one ps per poll ──
def processes() -> dict:
    """Every process's children: one ps for the whole poll."""
    children = {}
    for row in run("ps", "-axo", "pid=,ppid=", timeout=10).stdout.splitlines():
        parts = row.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            children.setdefault(int(parts[1]), []).append(int(parts[0]))
    return children


def commands_of(pids) -> dict:
    """{pid: its command line} for a few processes (the panes), in one ps."""
    pids = [str(p) for p in pids if p]
    if not pids:
        return {}
    out = {}
    for row in run("ps", "-ww", "-o", "pid=,args=", "-p", ",".join(pids), timeout=10).stdout.splitlines():
        parts = row.strip().split(None, 1)
        if parts and parts[0].isdigit():
            out[int(parts[0])] = parts[1] if len(parts) > 1 else ""
    return out


def waiting_on_claude(command: str) -> bool:
    """A pane's shell still running `claude …; exec zsh -l` as given (sh -c or zsh -c), not yet the shell it ends in."""
    words = command.split(None, 2)
    return len(words) >= 2 and words[1] == "-c" and "claude" in command


def tree_of(root: int, children: dict) -> set:
    seen, stack = set(), [root]
    while stack:
        pid = stack.pop()
        if pid not in seen:
            seen.add(pid)
            stack += children.get(pid, [])
    return seen


# ── what runs in the background: git and lsof answer the next poll, never this one ──
_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="hub-status")
_changes, _pending, _bg_lock = {}, set(), threading.Lock()
_listening = {"at": 0.0, "ports": {}, "busy": False}
CHANGES_TTL, CHANGES_TTL_IDLE, PORTS_TTL = 15, 300, 4


def _refresh_changes(sid: str, folder: str, stamp):
    import hub_diff
    try:
        value = hub_diff.numstat(folder)
    except Exception as error:  # a folder git can't read shows no changes, and says so in the log once
        print(f"error: changes of {sid}: {type(error).__name__}: {error}", flush=True)
        value = None
    with _bg_lock:
        _changes[sid] = (stamp, value, time.time())
        _pending.discard(sid)


def changes_of(sid: str, folder: str, stamp, alive: bool):
    """{added, removed, files} for the session's folder, as of the last background count. None until the first."""
    with _bg_lock:
        known = _changes.get(sid)
        old = known is None or known[0] != stamp or time.time() - known[2] > (CHANGES_TTL if alive else CHANGES_TTL_IDLE)
        if old and sid not in _pending and folder:
            _pending.add(sid)
            _pool.submit(_refresh_changes, sid, folder, stamp)
    return known[1] if known else None


def listening_now() -> dict:
    """{pid: {ports}} for every TCP socket listening on this Mac that lsof lets this user see."""
    found, pid = {}, None
    for line in run("lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpn", timeout=10).stdout.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith("n") and pid:
            port = line.rsplit(":", 1)[-1]
            if port.isdigit():
                found.setdefault(pid, set()).add(int(port))
    return found


def _refresh_listening():
    try:
        ports = listening_now()
    except (OSError, subprocess.SubprocessError):
        ports = None
    with _bg_lock:
        if ports is not None:
            _listening["ports"] = ports
        _listening["at"], _listening["busy"] = time.time(), False


def listening() -> dict:
    with _bg_lock:
        if time.time() - _listening["at"] > PORTS_TTL and not _listening["busy"]:
            _listening["busy"] = True
            _pool.submit(_refresh_listening)
        return _listening["ports"]


def owned(pane: int, claude: int, children: dict) -> set:
    """What a session may stop: its pane's processes, but never the pane's shell, Claude itself, or this hub."""
    return tree_of(pane, children) - {pane, claude, os.getpid()} if pane else set()


def ports_of(pane: int, claude: int, children: dict) -> list:
    if not pane:
        return []
    table = listening()
    return sorted({port for pid in owned(pane, claude, children) for port in table.get(pid, ())})


# ── the poll: one session's live fields ──
def iso_epoch(text: str):
    """A transcript's timestamp (UTC, ISO 8601) as epoch seconds."""
    try:
        return calendar.timegm(time.strptime(text[:19], "%Y-%m-%dT%H:%M:%S")) if text else None
    except ValueError:
        return None


def orb_of(state: str, event: dict, track: dict) -> str:
    if state == "error":
        return "retrying"
    if state == "needs":
        return "waiting"
    if state != "working":
        return "idle"
    retry = track.get("retry")
    if retry and (iso_epoch(retry["at"]) or 0) > time.time() - RETRY_FRESH:
        return "retrying"
    if event.get("compacting"):
        return "compacting"
    tool = event.get("tool") if isinstance(event.get("tool"), dict) else None
    if not event:
        return "working"
    if tool and not tool.get("done") and (tool.get("since") or 0) >= (event.get("turn") or 0):
        return "searching" if tool.get("tool") in SEARCHING else "using"
    return "reasoning"


def activity_of(event: dict):
    tool = event.get("tool") if isinstance(event.get("tool"), dict) else None
    if not tool or not tool.get("tool") or (tool.get("since") or 0) < (event.get("turn") or 0):
        return None  # a tool from an earlier turn isn't this turn's
    return {"tool": str(tool["tool"]), "target": str(tool.get("target") or ""), "since": tool.get("since")}


GONE = "Claude stopped while it was working, and its process is gone."


def error_of(event: dict, claude_alive: bool, pane_alive: bool) -> str:
    """One plain sentence when the session failed, or nothing. A Clear after the failure hides it."""
    if (event.get("cleared") or 0) >= (event.get("at") or 0):
        return ""
    if event.get("state") == "error":
        failure = event.get("failure") or {}
        said = str(failure.get("details") or failure.get("error") or event.get("message") or "").strip()
        return f"The API stopped this turn: {said.rstrip('.')}." if said else "The API stopped this turn with an error."
    if pane_alive and not claude_alive and event.get("state") in ("working", "needs"):
        return GONE
    return ""


def enrich(row: dict, meta: dict, transcript, pane_pid: int, claude_pid: int, children: dict):
    """Adds the data contract's fields to a session row whose state is already decided."""
    sid = meta["id"]
    event = read_event(sid) if meta.get("kind") == "claude" else {}
    track = track_of(sid, transcript) if meta.get("kind") == "claude" else _fresh("")
    state = row.get("state")
    row["activity"] = activity_of(event) if meta.get("kind") == "claude" else None
    turn = event.get("turn") or iso_epoch(track.get("prompt_at"))
    row["turn"] = {"since": turn} if state == "working" and turn else None
    row["orb"] = orb_of(state, event, track)
    used = track.get("used")
    row["context"] = {"used": used, "limit": context_limit(track.get("model") or "", used)} if isinstance(used, int) and used > 0 else None
    folder = meta.get("folder") or meta.get("repo") or ""
    try:
        stamp = event_path(sid).stat().st_mtime_ns
    except OSError:
        stamp = 0
    row["changes"] = None if meta.get("project") == HUB_PROJECT else changes_of(sid, folder, stamp, bool(row.get("alive")))  # a hub session works in the home folder, not a repo
    row["ports"] = ports_of(pane_pid, claude_pid, children) if row.get("alive") else []
    if state == "working" and row["orb"] == "retrying":
        retry = track.get("retry") or {}
        row["retry"] = {"said": retry.get("said", ""), "attempt": retry.get("attempt"), "of": retry.get("of")}


# ── acting on it ──
def clear(sid: str):
    """Clear a failed state: what failed stays in the transcript, the session reads as idle again."""
    import hub_data as hub
    hub.session_meta(sid)
    now = time.time()
    change_event(sid, lambda e: (e.update(cleared=now, at=now, failure=None, compacting=None), e.update(state="finished") if e.get("state") in ("error", "working", "needs") else None))
    return {"ok": True}


def stop_port(sid: str, body: dict):
    """Stop what listens on one port, only when it is a process this session started. Asked first, in the page."""
    import hub_data as hub
    meta = hub.session_meta(sid)
    port = (body or {}).get("port")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise Refused("Say which port to stop.")
    panes = dict(r.split() for r in hub.tmux("list-panes", "-t", f"hub-{sid}", "-F", "#{session_name} #{pane_pid}").stdout.splitlines() if len(r.split()) == 2)
    pane = int(panes.get(f"hub-{sid}", 0) or 0)
    if not pane:
        raise Refused("That session has ended.")
    children = processes()
    info = hub.claude_info(pane, children) if meta.get("kind") == "claude" else None
    mine = owned(pane, int((info or {}).get("pid") or 0), children)
    table = listening_now()
    targets = sorted(pid for pid in mine if port in table.get(pid, ()))
    if not targets:
        raise Refused(f"Nothing this session started listens on :{port}.")
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    end = time.time() + 3
    while time.time() < end and any(_alive(pid) for pid in targets):
        time.sleep(0.1)
    for pid in targets:
        if _alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    with _bg_lock:
        _listening["at"] = 0.0  # the next poll asks again
    return {"stopped": targets}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # a child that exited and wasn't reaped is gone too
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    return run("ps", "-o", "stat=", "-p", str(pid)).stdout.strip()[:1] not in ("", "Z")


# ── peek: the last reply or question, and an answer without opening the session ──
REPLY_OPTION = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-B]")
OPTION_ROW = re.compile(r"^( *)(\d{1,2})[.)] +(\S.*?)\s*$")
RULE = re.compile(r"^\s*[─━▔]{6,}\s*$")  # a solid rule: the top of a dialog, or what sets "Chat about this" apart
DASHES = re.compile(r"^\s*╌{6,}\s*$")  # a dashed rule inside a dialog, round a command or a plan
TAB_ROW = re.compile(r"^\s*(?:←\s+)?[☐☒] \S")
TAB_ITEM = re.compile(r"([☐☒✔]) (.+?)(?=\s{2,}|\s*→|\s*$)")
CHECKBOX = re.compile(r"^\[([ ✔✓xX×])\]\s*(.*)$")
TYPE_SOMETHING = re.compile(r"^Type something\.?$")
PLAN_FEEDBACK = "shift+tab to approve with this feedback"


def _plain(pane: str):
    raw = (pane or "").splitlines()[-80:]
    return raw, [ANSI.sub("", line).replace("\xa0", " ").rstrip() for line in raw]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _current_tab(raw: str, steps: list):
    """The step drawn on a coloured background in the tab row: the question on screen. Only colours say it."""
    lit, on = "", False
    for index, part in enumerate(re.split(r"\x1b\[([0-9;]*)m", raw)):
        if index % 2:
            codes = part.split(";") if part else ["0"]
            at = 0
            while at < len(codes):
                code = codes[at]
                if code in ("0", "") or code in ("49", "27"):
                    on = False
                elif code == "7":
                    on = True
                elif code == "48":
                    on, at = True, at + (2 if codes[at + 1:at + 2] == ["5"] else 4)
                elif code.isdigit() and (40 <= int(code) <= 47 or 100 <= int(code) <= 107):
                    on = True
                elif code == "38":
                    at += 2 if codes[at + 1:at + 2] == ["5"] else 4
                at += 1
        elif on:
            lit += part
    lit = lit.strip(" ☐☒✔")
    return next((i for i, step in enumerate(steps) if lit and step["label"] == lit), None)


def _paragraph_above(lines: list, at: int, stop_at_rule=True) -> tuple:
    """The block of non-blank lines that ends just above line `at`: (first line's index, its lines)."""
    j = at - 1
    while j >= 0 and not lines[j].strip():
        j -= 1
    end = j
    while j >= 0 and lines[j].strip() and not RULE.match(lines[j]) and not DASHES.match(lines[j]) and not TAB_ROW.match(lines[j]):
        j -= 1
    return j + 1, [line.strip() for line in lines[j + 1:end + 1]]


def _detail_above(lines: list, top: int) -> str:
    """What a dialog shows above its question: a permission's command or diff, a plan. From its top rule down."""
    kept, j, crossed = [], top - 1, False
    while j >= 0 and len(kept) < 200:
        line = lines[j]
        if RULE.match(line):
            if any(k.strip() for k in kept) or crossed:
                break
            crossed = True
        elif not DASHES.match(line) and not line.strip().startswith("Tip:") and not TAB_ROW.match(line):
            kept.insert(0, line)
        j -= 1
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    width = min((_indent(k) for k in kept if k.strip()), default=0)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(k[width:] for k in kept))
    return text[:4000]


def _plan_text(text: str) -> str:
    """A plan as Markdown again: the lines the terminal wrapped joined back, without Claude Code's own heading."""
    out = []
    for line in text.split("\n"):
        if line.strip() in ("Ready to code?", "Here is Claude's plan:"):
            continue
        item = re.match(r"\s*(?:[-*•]|\d+[.)])\s", line)
        if out and out[-1].strip() and line.startswith(" ") and line.strip() and not item:
            out[-1] += " " + line.strip()
        else:
            out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _wraps(line_len: int, next_text: str, width: int) -> bool:
    """A line the terminal wrapped: the next line's first word would not have fitted on it."""
    first = next_text.split(" ", 1)[0]
    return width > 0 and line_len + 1 + len(first) > width


def dialog_in(pane: str):
    """A numbered choice Claude Code is showing: a permission prompt, a plan to approve, AskUserQuestion, a picker.

    Only a choice that is live: its cursor (❯) is on one of its rows (an option, or the unnumbered Next or Submit of a
    multiple choice), and no input line comes after it. A numbered list higher up the screen is text, not a choice.
    `pane` may carry colours (capture-pane -e): they are read only to tell which question of several is on screen."""
    raw, lines = _plain(pane)
    cursor = max((i for i, line in enumerate(lines) if line.lstrip().startswith("❯")), default=None)
    if cursor is None:
        return None
    flat = list(lines)
    flat[cursor] = lines[cursor].replace("❯", " ", 1)
    width = max((len(line) for line in lines), default=0)
    match = OPTION_ROW.match(flat[cursor])
    if match:
        col = len(match[1])
    else:  # the cursor on an unnumbered row: its options are right above it
        col, j = None, cursor - 1
        while j >= max(0, cursor - 40):
            above = OPTION_ROW.match(flat[j])
            if above:
                col = len(above[1])
                break
            if not flat[j].strip() or RULE.match(flat[j]):
                return None
            j -= 1
        if col is None or _indent(flat[cursor]) < col:
            return None

    def inside(i):
        return 0 <= i < len(flat) and flat[i].strip() and not RULE.match(flat[i]) and _indent(flat[i]) >= col

    def numbered(i):
        found = 0 <= i < len(flat) and OPTION_ROW.match(flat[i])
        return bool(found) and len(found[1]) == col

    start = cursor
    while inside(start - 1) or (RULE.match(flat[start - 1] if start > 0 else "") and inside(start - 2)):
        start -= 1 if inside(start - 1) else 2
    end = cursor
    while inside(end + 1) or (end + 2 < len(flat) and RULE.match(flat[end + 1]) and numbered(end + 2)):
        end += 1 if inside(end + 1) else 2
    while start < end and not numbered(start):
        start += 1
    if not numbered(start):
        return None

    options, rows, ruled = [], [], False
    for i in range(start, end + 1):
        line = flat[i]
        if RULE.match(line):
            ruled = True
            continue
        found = OPTION_ROW.match(line)
        if found and len(found[1]) == col:
            option = {"n": int(found[2]), "label": found[3], "_lines": [], "_len": len(line), "_col": col + len(found[2]) + 2}
            if option["n"] != len(options) + 1:
                return None
            if ruled:
                option["apart"] = True
            if i == cursor:
                option["_cursor"] = True
            options.append(option)
            rows.append(option)
            continue
        text = line.strip()
        last = options[-1]
        multi_row = CHECKBOX.match(last["label"]) and _indent(line) <= last["_col"]
        if i == cursor or _indent(line) == col or text.startswith("▸") or multi_row:
            rows.append({"label": text.lstrip("▸ ").strip(), "_cursor": i == cursor})
            continue
        last["_lines"].append((len(line), text))
    if len(options) < 2:
        return None

    # what the screen above the options says: the tab row of several questions, the question, a command or plan
    top = start
    tab_at = next((j for j in range(start - 1, max(-1, start - 30), -1) if TAB_ROW.match(lines[j]) or RULE.match(lines[j])), None)
    steps, step = [], None
    if tab_at is not None and TAB_ROW.match(lines[tab_at]):
        steps = [{"label": label.strip(), "done": mark == "☒"} | ({"submit": True} if mark == "✔" else {}) for mark, label in TAB_ITEM.findall(lines[tab_at])]
        step = _current_tab(raw[tab_at], steps)
    asks = bool(steps) or any(o["label"] == "Chat about this" for o in options)
    if asks and tab_at is not None:
        region = [line.strip() for line in lines[tab_at + 1:start]]
    else:
        first, region = _paragraph_above(lines, start)
        top = first
    region = [line for line in region if line]

    dialog = {"kind": "choice", "question": "", "options": [], "multi": False}
    review = []
    if asks and region and region[0] == "Review your answers":
        dialog["kind"] = "review"
        dialog["question"] = "Review your answers"
        for line in region[1:]:
            if line.startswith("●"):
                review.append({"question": line.lstrip("● ").strip(), "answer": ""})
            elif line.startswith("→") and review:
                review[-1]["answer"] = line.lstrip("→ ").strip()
            elif line.startswith("⚠"):
                dialog["warning"] = line.lstrip("⚠ ").strip()
        dialog["review"] = review
        if steps and step is None:
            step = next((i for i, s in enumerate(steps) if s.get("submit")), None)
    else:
        asked_at = next((i for i in range(len(region) - 1, -1, -1) if re.match(r"Do you want ", region[i])), None)
        if asks:
            dialog["kind"], dialog["question"] = "question", " ".join(region[-6:])
        elif asked_at is not None:  # what it would do is above the question: the detail
            dialog["kind"], dialog["question"] = "permission", " ".join(region[asked_at:])
            top += asked_at
        elif any(o["label"].startswith("Tell Claude what to change") or any(PLAN_FEEDBACK in t for _, t in o["_lines"]) for o in options):
            dialog["kind"], dialog["question"] = "plan", " ".join(region)
        elif len(region) > 1:  # a picker's title, then a line about it
            dialog["question"], dialog["detail"] = region[0], " ".join(region[1:])[:600]
        else:
            dialog["question"] = " ".join(region)
    if steps:
        if step is None and len([s for s in steps if not s.get("submit")]) == 1 and dialog["kind"] != "review":
            step = 0
        dialog["steps"], dialog["step"] = steps, step

    # each option: its label, the description under it, whether it is ticked, whether it takes words
    for option in options:
        label, extra = option["label"], option["_lines"]
        if dialog["kind"] in ("question", "plan"):
            while extra and _wraps(option["_len"], extra[0][1], width):  # a long label the terminal wrapped
                option["_len"] = extra[0][0]
                label += " " + extra.pop(0)[1]
            description = " ".join(t for _, t in extra if t != PLAN_FEEDBACK)
        else:
            label += "".join(" " + t for _, t in extra)
            description = ""
        box = CHECKBOX.match(label)
        checked = None
        if box:
            dialog["multi"], checked, label = True, box[1] != " ", box[2]
        if re.search(r"\s✔$", label):
            checked, label = True, label[:-1].rstrip()
        split = re.split(r"\s{2,}", label, 1)
        if len(split) == 2 and split[1] and not description:  # a picker's two columns: the name, then what it is
            label, description = split
            if re.search(r"\s✔$", label):
                checked, label = True, label[:-1].rstrip()
        label = re.sub(r"\s+", " ", label).strip()
        out = {"n": option["n"], "label": label[:200]}
        if description:
            out["description"] = re.sub(r"\s+", " ", description).strip()[:400]
        if checked is not None or (dialog["multi"] and not option.get("apart")):
            out["checked"] = bool(checked)
        if option.get("apart"):
            out["apart"] = True
        option["_out"] = out
        dialog["options"].append(out)

    # which option takes words, and how: typed straight into its row, or Tab first to add to it
    plain_options = [o for o in dialog["options"] if not o.get("apart")]
    if dialog["kind"] == "question" and plain_options:
        last = plain_options[-1]
        last["text"] = "type"
        last["value"] = "" if TYPE_SOMETHING.match(last["label"]) else last["label"]
        if not last["value"]:
            last["label"] = "Type something"
    elif dialog["kind"] == "plan":
        for o, src in zip(dialog["options"], options):
            if o["label"].startswith("Tell Claude what to change") or any(PLAN_FEEDBACK in t for _, t in src["_lines"]):
                o["text"] = "type"
                o["value"] = "" if o["label"].startswith("Tell Claude what to change") else o["label"]
                if not o["value"]:
                    o["label"] = "Tell Claude what to change"
    elif dialog["kind"] == "permission":
        for o in dialog["options"]:
            if o["label"] in ("Yes", "No"):
                o["text"] = "amend"
            elif re.match(r"(Yes|No), and tell Claude what to do", o["label"]):
                o["text"], o["value"] = "type", ""
    texts = [o for o in dialog["options"] if o.get("text")]
    dialog["text_option"] = texts[-1]["n"] if texts else None

    # every row the cursor can stand on, in screen order, and where it stands now
    order, extra_rows = [], []
    for row in rows:
        index = len(order)
        if "_out" in row:
            row["_out"]["row"] = index
        else:
            entry = {"row": index, "label": row["label"][:120]}
            if re.fullmatch(r"Next|Submit", row["label"]) and dialog["multi"]:
                dialog["next"] = entry
            else:
                extra_rows.append(entry)
        order.append(row)
        if row.get("_cursor"):
            dialog["cursor"] = index
    if extra_rows:
        dialog["rows"] = extra_rows
    dialog.setdefault("cursor", None)
    if dialog["kind"] in ("permission", "plan"):
        detail = _detail_above(lines, top)
        if dialog["kind"] == "plan":
            detail = _plan_text(detail)
        if detail:
            dialog["detail"] = detail
    dialog["question"] = dialog["question"].strip(" │╭╮╰╯─")[:240]
    return dialog


def menu_dialog(pane: str):
    """A menu without numbers (trust this folder, some pickers): its rows, read so a phone can pick one with a tap.
    Only when the screen ends on it: a cursor (❯) on one of two or more rows of the same indent, and a key hint below."""
    raw, lines = _plain(pane)
    cursor = max((i for i, line in enumerate(lines) if line.lstrip().startswith("❯")), default=None)
    if cursor is None or OPTION_ROW.match(lines[cursor].replace("❯", " ", 1)):
        return None
    flat = list(lines)
    flat[cursor] = lines[cursor].replace("❯", " ", 1)
    col = _indent(flat[cursor])

    def row(i):
        return 0 <= i < len(flat) and flat[i].strip() and not RULE.match(flat[i]) and _indent(flat[i]) == col

    start, end = cursor, cursor
    while row(start - 1):
        start -= 1
    while row(end + 1):
        end += 1
    if end == start:
        return None
    after = [line for line in lines[end + 1:] if line.strip()][:3]
    if not after or not any(hint in line for line in after for hint in MENU_HINTS) or RULE.match(after[0]):
        return None
    top = next((j for j in range(start - 1, -1, -1) if RULE.match(lines[j])), -1)
    paragraphs, block = [], []
    for line in lines[top + 1:start]:
        if line.strip():
            block.append(line.strip())
        elif block:
            paragraphs.append(" ".join(block)); block = []
    if block:
        paragraphs.append(" ".join(block))
    asked = next((p for p in reversed(paragraphs) if "?" in p), paragraphs[0] if paragraphs else "")
    detail = "\n\n".join(p for p in paragraphs if p != asked)
    out = {"kind": "menu", "question": asked[:240], "options": [], "multi": False, "text_option": None, "cursor": cursor - start,
           "rows": [{"row": i - start, "label": flat[i].strip()[:120]} for i in range(start, end + 1)]}
    if detail:
        out["detail"] = detail[:2000]
    return out


def options_in(text: str) -> list:
    """Numbered options at the end of a reply that asks a question: 1., 2., … in order."""
    rows = [line for line in (text or "").splitlines() if line.strip()]
    found = []
    for line in reversed(rows[-12:]):
        match = REPLY_OPTION.match(line)
        if not match:
            if found:
                break
            continue
        found.insert(0, {"n": int(match[1]), "label": re.sub(r"[*_`]+", "", match[2]).strip()[:160]})
    return found if len(found) >= 2 and [o["n"] for o in found] == list(range(1, len(found) + 1)) else []


def screen_of(target: str) -> str:
    """The pane with its colours: the parsers read them to tell which question of several is on screen."""
    import hub_data as hub
    return hub.tmux("capture-pane", "-p", "-e", "-t", target).stdout


def peek(sid: str, rows: list) -> dict:
    """`rows` are the sessions as the last poll saw them, so a peek costs no more than the poll did."""
    import hub_data as hub
    meta = hub.session_meta(sid)
    s = next((row for row in rows if row["id"] == sid), None) or {}
    target = f"hub-{sid}"
    alive = target in hub.tmux_sessions()
    track = track_of(sid, hub.transcript_of(sid)) if meta.get("kind") == "claude" else _fresh("")
    out = {"id": sid, "title": meta.get("title", ""), "state": s.get("state", "ended"), "orb": s.get("orb", "idle"), "activity": s.get("activity"), "turn": s.get("turn"),
           "error": s.get("error", ""), "asking": s.get("asking", ""), "text": track.get("said", ""), "at": track.get("said_at", ""), "dialog": None, "options": [],
           "live": alive and meta.get("kind") == "claude" and s.get("state") not in ("closing", "closed", "ended")}
    screen = screen_of(target) if alive else ""
    pane = "\n".join(_plain(screen)[1]) if screen else ""
    if out["state"] == "needs" and screen:
        out["dialog"] = dialog_in(screen) or menu_dialog(screen)
    if out["dialog"]:
        out["options"] = out["dialog"]["options"]
    elif out["state"] in ("needs", "finished"):
        out["options"] = options_in(out["text"])
    out["typed"] = bool(hub.typed_now(target)) if pane and not out["dialog"] else False
    out["menu"] = menu_in(pane) if pane and not out["dialog"] else ""
    return out


MENU_HINTS = ("Enter to confirm", "Esc to cancel", "Enter to select", "to navigate", "Esc to reject", "Space to select", "Tab to amend")


def menu_in(pane: str) -> str:
    """A menu Claude Code shows that isn't a numbered choice (trust this folder, a picker): its last lines as text, so a
    phone can read it and answer with the arrow keys. Nothing when the screen ends on Claude's own input box."""
    lines = [line.rstrip() for line in pane.splitlines() if line.strip()]
    tail = lines[-6:]
    if not any(hint in line for line in tail for hint in MENU_HINTS):
        return ""
    keep = lines[-18:]
    width = min((len(line) - len(line.lstrip()) for line in keep), default=0)
    return "\n".join(line[width:] for line in keep)[:2000]


KEYS = {"esc": "Escape", "enter": "Enter", "up": "Up", "down": "Down", "left": "Left", "right": "Right", "tab": "Tab", "btab": "BTab", "space": "Space", "ctrl-c": "C-c"}


def press(sid: str, body: dict):
    """One key from a phone's chat view, which has no terminal open: only the keys its buttons offer."""
    import hub_data as hub
    meta, target = hub.live_claude(sid)
    key = KEYS.get(str((body or {}).get("key", "")))
    if not key:
        raise Refused("That key can't be sent from here.")
    hub.tmux("send-keys", "-t", target, key)
    return {"ok": True}


# ── answering a choice on screen: the keys a person would press, each checked against the screen it leaves ──
GONE_CHOICE = "That choice is no longer on screen."
KEY_GAP, SETTLE = 0.05, 0.25


def _now(target: str):
    screen = screen_of(target)
    return dialog_in(screen) or menu_dialog(screen)


def _keys(target: str, *keys):
    import hub_data as hub
    for key in keys:
        hub.tmux("send-keys", "-t", target, key)
        time.sleep(KEY_GAP)


def _type(target: str, text: str, sid: str):
    """Words into the row the cursor is on, as one bracketed paste: typed keys would be read as choices."""
    import hub_data as hub
    hub.tmux("set-buffer", "-b", f"hub-answer-{sid}", text)
    hub.tmux("paste-buffer", "-p", "-d", "-b", f"hub-answer-{sid}", "-t", target)


def _row_of(dialog: dict, n: int):
    return next((o for o in dialog["options"] if o["n"] == n), None)


def _goto(target: str, row: int) -> dict:
    """Move the cursor to a row with ↑/↓, reading the screen after each move: Claude may skip a row or wrap."""
    for _ in range(4):
        dialog = _now(target)
        if not dialog:
            raise Refused(GONE_CHOICE)
        if dialog.get("cursor") == row:
            return dialog
        if dialog.get("cursor") is None:
            raise Refused("The cursor isn't on the choice. Answer it in the terminal.")
        delta = row - dialog["cursor"]
        _keys(target, *(["Down"] * delta if delta > 0 else ["Up"] * -delta))
        time.sleep(SETTLE)
    raise Refused("The cursor didn't reach that option. Answer it in the terminal.")


def _off_text(target: str, dialog: dict) -> dict:
    """Digits and ←/→ go into a row that takes words while the cursor is on it, so the cursor leaves it first."""
    here = next((o for o in dialog["options"] if o.get("row") == dialog.get("cursor")), None)
    if here and here.get("text") == "type":
        first = next(o for o in dialog["options"] if not o.get("text"))
        return _goto(target, first["row"])
    return dialog


def _same_words(shown: str, sent: str) -> bool:
    shown, sent = " ".join(shown.split()), " ".join(sent.split())
    return bool(sent) and (shown.startswith(sent[:24]) or sent.startswith(shown[:24]) and len(shown) >= 4)


def _write_into(target: str, sid: str, option: dict, text: str):
    """Words into a row that takes them: the cursor goes to it, Tab first where the row is added to, what was typed
    there before is cleared, then the words go in. The screen must show them before anything is pressed after."""
    dialog = _goto(target, option["row"])
    if option.get("text") == "amend":
        _keys(target, "Tab")
        time.sleep(SETTLE)
    _keys(target, "C-e", "C-u")  # the caret can stand anywhere in what is there: to its end, then clear back to the start
    if text:
        _type(target, text, sid)
    for _ in range(8):
        time.sleep(SETTLE)
        dialog = _now(target)
        if not dialog:
            raise Refused(GONE_CHOICE)
        shown = _row_of(dialog, option["n"]) or {}
        value = shown.get("value") if shown.get("value") is not None else re.sub(r"^(Yes|No), ", "", shown.get("label", ""))
        if (not text and not shown.get("value")) or (text and _same_words(value, text)):
            return dialog
    raise Refused("Your words didn't show in Claude's choice, so nothing was sent. Answer it in the terminal.")


def _set_picks(target: str, sid: str, dialog: dict, picks: set, text):
    """A multiple choice set to exactly what was ticked: only the boxes that differ are toggled, then the words."""
    for _ in range(3):
        dialog = _off_text(target, dialog)
        wrong = [o for o in dialog["options"] if not o.get("text") and not o.get("apart") and bool(o.get("checked")) != (o["n"] in picks)]
        if not wrong:
            break
        for option in wrong:
            if option["n"] <= 9:
                _keys(target, str(option["n"]))
            else:
                _goto(target, option["row"])
                _keys(target, "Enter")
        time.sleep(SETTLE)
        dialog = _now(target)
        if not dialog or not dialog.get("multi"):
            raise Refused(GONE_CHOICE)
    else:
        raise Refused("The ticks didn't take. Answer it in the terminal.")
    typed = next((o for o in dialog["options"] if o.get("text") == "type"), None)
    if typed and text is not None and " ".join(text.split()) != " ".join((typed.get("value") or "").split()):
        dialog = _write_into(target, sid, typed, text)
    return dialog


def _choose(target: str, dialog: dict, option: dict):
    """One numbered option: its digit, or ↑/↓ and Enter when a digit can't reach it (10 and over, or the cursor in a
    row that takes words, where a digit would be typed)."""
    here = next((o for o in dialog["options"] if o.get("row") == dialog.get("cursor")), None)
    if option["n"] > 9 or (here and here.get("text") == "type") or option.get("row") is None:
        _goto(target, option["row"])
        _keys(target, "Enter")
    else:
        _keys(target, str(option["n"]))


def _step(target: str, dialog: dict, step: int) -> dict:
    """Another question of several: ←/→ along the tab row, checked against the tab it lands on."""
    steps = dialog.get("steps") or []
    if not 0 <= step < len(steps):
        raise Refused("That question isn't one of these.")
    for _ in range(len(steps) + 2):
        if dialog.get("step") == step:
            return dialog
        if dialog.get("step") is None:
            raise Refused("Which question is on screen can't be read. Move between them in the terminal.")
        dialog = _off_text(target, dialog)
        delta = step - dialog["step"]
        _keys(target, *(["Right"] * delta if delta > 0 else ["Left"] * -delta))
        time.sleep(SETTLE)
        dialog = _now(target)
        if not dialog:
            raise Refused(GONE_CHOICE)
    raise Refused("That question didn't open. Move to it in the terminal.")


def answer(sid: str, body: dict):
    """Answers what Claude is showing, or sends a reply.

    On a choice: `choice` picks a numbered option, with `text` for one that takes words (typed into its row, or added
    with Tab); `picks` sets a multiple choice's ticks and its typed row, `next` then moves on; `step` opens another of
    several questions; `row` picks an unnumbered row. Without a choice on screen, `text` goes in as one paste and Enter,
    the way Close sends its prompt."""
    import hub_data as hub
    meta, target = hub.live_claude(sid)
    body = body or {}
    choice, text = body.get("choice"), body.get("text")
    if text is not None and not isinstance(text, str):
        raise Refused("Write a reply first.")
    if isinstance(text, str) and len(text) > 20000:
        raise Refused("That reply is too long to send from here.")
    asked = any(key in body for key in ("choice", "picks", "step", "row", "next"))
    dialog = _now(target) if asked or text is not None else None
    if asked and dialog:
        if "step" in body:
            step = body["step"]
            if not isinstance(step, int) or isinstance(step, bool):
                raise Refused("Say which question to open.")
            _step(target, dialog, step)
            return {"ok": True}
        if "picks" in body or body.get("next"):
            picks = body.get("picks", [])
            if not dialog.get("multi"):
                raise Refused("This choice takes one answer.")
            if not isinstance(picks, list) or not all(isinstance(p, int) and not isinstance(p, bool) for p in picks):
                raise Refused("Say which options to tick.")
            words = " ".join(text.split()) if isinstance(text, str) else None
            dialog = _set_picks(target, sid, dialog, set(picks), words)
            if body.get("next"):
                if not dialog.get("next"):
                    raise Refused("There is no Next on screen.")
                _goto(target, dialog["next"]["row"])
                _keys(target, "Enter")
            return {"ok": True, "sent": dialog["next"]["label"] if body.get("next") else "ticks"}
        if "row" in body:
            row = body["row"]
            known_rows = [r["row"] for r in dialog.get("rows", [])] + ([dialog["next"]["row"]] if dialog.get("next") else [])
            if not isinstance(row, int) or isinstance(row, bool) or row not in known_rows:
                raise Refused("That isn't one of the rows on screen.")
            _goto(target, row)
            _keys(target, "Enter")
            return {"ok": True}
        if not isinstance(choice, int) or isinstance(choice, bool) or not 1 <= choice <= 99:
            raise Refused("Choose one of the numbered options.")
        option = _row_of(dialog, choice)
        if not option:
            raise Refused("That isn't one of the options on screen.")
        if isinstance(text, str) and text.strip():
            if not option.get("text"):
                raise Refused("That option takes no words. Choose it without them.")
            words = " ".join(text.split())
            if dialog.get("multi"):
                _write_into(target, sid, option, words)
                return {"ok": True, "sent": words}
            _write_into(target, sid, option, words)
            _keys(target, "Enter")
            return {"ok": True, "sent": words}
        if option.get("text") == "type" and not option.get("value"):
            raise Refused("Write what to send for that option first.")
        _choose(target, dialog, option)
        return {"ok": True, "sent": option["label"]}
    if asked and not dialog and any(key in body for key in ("picks", "step", "row", "next")):
        raise Refused(GONE_CHOICE)
    if choice is not None:
        if not isinstance(choice, int) or isinstance(choice, bool) or not 1 <= choice <= 99:
            raise Refused("Choose one of the numbered options.")
        text = str(choice)
    if not isinstance(text, str) or not text.strip():
        raise Refused("Write a reply first.")
    if dialog:
        raise Refused("Claude is showing a choice. Answer it with its number.")
    if hub.typed_now(target):
        raise Refused("Something is already typed in this session. Send or clear it there first.")
    hub.paste_prompt(target, text.strip(), f"hub-reply-{sid}")
    return {"ok": True}
