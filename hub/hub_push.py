"""The state, kept fresh on the server and pushed to open pages as it changes.

A page used to learn of a change only when its 3-second poll came round, and each poll recomputed everything, with a
screen capture of every live session. Now, while a page is watching, one loop looks for a change four times a second
in what is cheap to read: each tmux window's last output (`#{window_activity}`) and the files the hooks, the hub and
Claude write. When something moved it recomputes the state with the hub's own functions, re-capturing only the panes
that printed since their last capture, and sends each open page what changed: the rows of the sessions that did, and
any other part of the state that did. GET /api/stream is that feed (Server-Sent Events); /api/state stays, and answers
from the loop's state while it is fresh.

Nobody watching (no stream open, no poll lately), the loop does nothing.
"""
import asyncio, json, os, sys, threading, time

import hub_catcher as catcher
import hub_data as hub
import hub_status as status

PROBE = 0.25  # seconds between looks for a change, while a page watches
QUIET = 0.4  # a pane that keeps printing (a spinner, a build) recomputes at most this often; one that was quiet, at once
WOKE = 2  # seconds without output after which a pane's next output counts as news
REFRESH = 2.0  # the longest a watched state goes without a recompute: transcripts, timers, ports
PROJECTS = 3.0  # projects (stores, setup, dream checks) cost more: recomputed beside the loop this often, as the poll did, and after a write
WATCHED = 20.0  # a poll counts as a page watching for this long
PROCESSES = 2.0  # the process table, read with ps, is reused this long within the loop (and dropped after a write)
KEEP = 15.0  # a pane's capture is reused for at most this long, even with no output: a resize reflows it without any
PING = 10.0  # a stream hears from the server at least this often, so a page can tell a quiet feed from a dead one
BACKLOG = 64  # messages a slow page may fall behind before its stream is closed; it reconnects and starts over
STREAMS = 32  # open streams at most

_wake, _loop = None, None  # an asyncio.Event set by kick(), and the server's event loop
_lock = threading.Lock()
_latest, _latest_at, _latest_gen = None, 0.0, -1  # the last state the loop computed, when (monotonic), and on which writes
_base, _base_gen = None, -1  # the last whole state (its projects, groups and the rest stand until the next), and on which writes
_writes = 0  # writes so far: a state computed before the last one is not handed out
_seq, _rows, _top = 0, {}, {}  # what the pages were last sent: a number, and each session row and top-level part as JSON
_streams = []  # one queue per open stream
_polled = 0.0  # when /api/state was last asked for (monotonic)

# ── screens: reuse a capture while the pane has printed nothing since it was taken ──
_plain_pane = hub.pane_of
_screens = {}  # (target, args) -> (window_activity seen, wall time the capture started, text)
_activity = {}  # tmux session name -> its window's last output, in whole seconds
_here = threading.local()
_plain_ps = {"processes": status.processes, "commands_of": status.commands_of}
_ps = {}  # (name, args) -> (monotonic time, value)


def _cached_ps(name):
    """hub_status's ps readers, from the loop's thread only, reused for PROCESSES seconds. Every caller gets its own copy."""
    plain = _plain_ps[name]

    def read(*args):
        if not getattr(_here, "on", False):
            return plain(*args)
        args = tuple(tuple(a) if not isinstance(a, (str, int)) else a for a in args)  # a generator of pids becomes a key
        kept = _ps.get((name, args))
        if kept is None or time.monotonic() - kept[0] > PROCESSES:
            kept = _ps[(name, args)] = (time.monotonic(), plain(*args))
        return {key: list(value) if isinstance(value, list) else value for key, value in kept[1].items()}
    return read


def _pane(target, *args, **kwargs):
    """hub.pane_of, from the loop's thread only, without a capture when nothing has printed since the last one.

    window_activity is in whole seconds, so a capture is reused only if it started after the second its pane last
    printed in had ended: anything printed in that second is in it. A capture started in that same second is taken
    again next time."""
    if not getattr(_here, "on", False):
        return _plain_pane(target, *args, **kwargs)
    key = (target, args, tuple(sorted(kwargs.items())))
    seen, kept, now = _activity.get(target), _screens.get(key), time.time()
    if kept and seen is not None and kept[0] == seen and kept[1] >= seen + 1 and now - kept[1] < KEEP:
        return kept[2]
    text = _plain_pane(target, *args, **kwargs)
    if seen is not None:
        _screens[key] = (seen, now, text)
    return text


def _probe():
    """What moved since the last look: each window's last output, and the files that say what a session is doing."""
    out = hub.tmux("list-windows", "-a", "-F", "#{session_name} #{window_activity}").stdout
    activity = {}
    for line in out.splitlines():
        name, _, when = line.partition(" ")
        if when.isdigit():
            activity[name] = int(when)
    marks = []
    for folder in (hub.EVENTS, hub.META, hub.CLAUDE_SESSIONS):  # hook events, the hub's own session files, Claude's status files
        try:
            with os.scandir(folder) as found:
                marks.append(sorted((entry.name, entry.stat().st_mtime_ns) for entry in found if entry.name.endswith(".json")))
        except OSError:
            marks.append(None)
    woke = any(when - _activity.get(name, 0) >= WOKE for name, when in activity.items() if name in _activity and when != _activity[name])
    _activity.clear()
    _activity.update(activity)
    for key in [key for key in _screens if key[0] not in activity]:
        del _screens[key]  # a session that has gone
    # A capture taken in the same second as its pane's last output may have missed the end of that second: once the
    # second is over, it is taken again, even if the pane prints nothing more.
    now = time.time()
    unsettled = any(kept[1] < kept[0] + 1 <= now for kept in _screens.values())
    return activity, marks, woke, unsettled


def _whole() -> dict:
    """Everything, projects too. Slow at times (a store's git, a dream job), so it runs beside the sessions loop."""
    _here.on = True
    try:
        return {**hub.state(), "catcher": catcher.summary(), "reads": hub.reads_of()}
    finally:
        _here.on = False


def _sessions():
    """The sessions, fresh, on the last whole state; and the writes that whole state had seen."""
    base, gen = _base, _base_gen
    _here.on = True
    try:
        return {**base, "sessions": hub.sessions_state(), "catcher": catcher.summary(), "reads": hub.reads_of(), "at": time.time()}, gen
    finally:
        _here.on = False


def _event(kind: str, data) -> bytes:
    return f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def _send(stream, message):
    if stream["behind"]:
        return
    if stream["queue"].qsize() >= BACKLOG:  # nothing more for it: the stream closes, and the page reconnects and starts over
        stream["behind"] = True
        while not stream["queue"].empty():
            stream["queue"].get_nowait()
        stream["queue"].put_nowait(None)
    else:
        stream["queue"].put_nowait(message)


def _publish(state: dict, gen: int):
    """Keeps the state for /api/state, and sends open pages what changed in it."""
    global _latest, _latest_at, _latest_gen, _seq, _rows, _top
    rows = {row["id"]: json.dumps(row, sort_keys=True) for row in state.get("sessions", [])}
    top = {key: json.dumps(value, sort_keys=True) for key, value in state.items() if key not in ("sessions", "at")}
    changed = [sid for sid, text in rows.items() if _rows.get(sid) != text]
    gone = [sid for sid in _rows if sid not in rows]
    order = list(rows) != list(_rows)
    parts = [key for key, text in top.items() if _top.get(key) != text]
    dropped = [key for key in _top if key not in top]
    with _lock:
        _latest, _latest_at, _latest_gen = state, time.monotonic(), gen
    diff = None
    if changed or gone or order or parts or dropped or not _seq:
        _seq += 1
        _rows, _top = rows, top
        by_id = {row["id"]: row for row in state.get("sessions", [])}
        diff = _event("diff", {"seq": _seq, "base": _seq - 1, "at": state.get("at"), "rows": [by_id[sid] for sid in changed], "gone": gone,
                               "order": list(rows) if order else None, "set": {key: state[key] for key in parts}, "unset": dropped})
    full = None
    for stream in _streams:
        if stream["synced"]:
            if diff:
                _send(stream, diff)
        else:
            full = full or _event("full", {"seq": _seq, "state": state})
            stream["synced"] = True
            _send(stream, full)


def watched() -> bool:
    return bool(_streams) or time.monotonic() - _polled < WATCHED


def fresh(limit: float = REFRESH + 2 * PROBE):
    """The loop's state if it is newer than `limit` seconds and no write came since; else None. Counts as a page watching.
    While pages watch, the loop's state is never older than REFRESH plus a look, and a change shows in it within a
    second, so a poll gets it as it is rather than a recompute."""
    global _polled
    _polled = time.monotonic()
    if _wake is not None and _loop is not None:
        _loop.call_soon_threadsafe(_wake.set)  # a page that polls is watching: the loop wakes if it was resting
    with _lock:
        if _latest is not None and _latest_gen == _writes and time.monotonic() - _latest_at < limit:
            return _latest
    return None


def kick(write: bool = False):
    """A write landed (or a page arrived): look again now, and after a write recompute everything."""
    global _writes
    if write:
        _ps.clear()
        with _lock:
            _writes += 1
    if _wake is not None:
        _wake.set()


async def _run():
    global _base, _base_gen
    loop = asyncio.get_event_loop()
    marks, at, projects_at, whole, seen_writes = None, 0.0, 0.0, None, 0

    def landed(done, gen):
        global _base, _base_gen
        try:
            _base, _base_gen = done.result(), gen
        except Exception as error:
            print(f"error: state loop: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        _wake.set()  # sent with the next sessions

    while True:
        try:
            await asyncio.wait_for(_wake.wait(), PROBE)
        except asyncio.TimeoutError:
            pass
        woken = _wake.is_set()
        _wake.clear()
        if not watched():
            marks = None
            continue
        try:
            write, seen_writes = _writes != seen_writes, _writes
            if _base is None:
                gen = _writes
                _base, _base_gen = await loop.run_in_executor(None, _whole), gen
                projects_at = time.monotonic()
            elif (_base_gen != _writes or time.monotonic() - projects_at > PROJECTS) and (whole is None or whole.done()):
                projects_at, gen = time.monotonic(), _writes
                whole = loop.run_in_executor(None, _whole)
                whole.add_done_callback(lambda done, gen=gen: landed(done, gen))
            now = await loop.run_in_executor(None, _probe)
            since = time.monotonic() - at
            files = marks is None or now[1][:2] != marks[1][:2]  # a hook or the hub wrote: a state may have changed
            # Claude's status files are every Claude's on this Mac, the hub's or not, so they count as a busy pane does.
            screens = marks is not None and (now[0] != marks[0] or now[3] or now[1][2] != marks[1][2]) and (since > QUIET or now[2])
            if not (woken or write or files or screens or since > REFRESH):
                continue
            marks = now
            state, gen = await loop.run_in_executor(None, _sessions)
            at = time.monotonic()
            _publish(state, gen)
        except Exception as error:  # the loop keeps going; the poll still answers on its own
            print(f"error: state loop: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
            await asyncio.sleep(1)


def start():
    """Called once from the server's main(): the loop, and the screen cache in front of hub.pane_of."""
    global _wake, _loop
    _loop = asyncio.get_event_loop()
    _wake = asyncio.Event()
    hub.pane_of = _pane
    status.processes, status.commands_of = _cached_ps("processes"), _cached_ps("commands_of")
    return asyncio.ensure_future(_run())


async def stream(reader, writer, security: str):
    """GET /api/stream: the whole state once, then what changes, as Server-Sent Events, until the page goes."""
    if len(_streams) >= STREAMS:
        writer.write(f"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n{security}\r\n".encode())
        await writer.drain()
        return
    writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\nX-Accel-Buffering: no\r\n{security}\r\n".encode())
    writer.write(b"retry: 2000\n\n")  # how long the browser waits before it reconnects on its own
    me = {"queue": asyncio.Queue(), "synced": False, "behind": False}
    with _lock:
        ready = _latest is not None and _latest_gen == _writes and time.monotonic() - _latest_at < REFRESH
    if ready and _seq:
        me["synced"] = True
        me["queue"].put_nowait(_event("full", {"seq": _seq, "state": _latest}))
    _streams.append(me)
    kick()
    gone = asyncio.ensure_future(reader.read(1))  # a page sends nothing on this connection: anything at all, or its end, means it has gone
    try:
        await writer.drain()
        while not gone.done():
            getting = asyncio.ensure_future(me["queue"].get())
            done, _ = await asyncio.wait([getting, gone], timeout=PING, return_when=asyncio.FIRST_COMPLETED)
            if getting not in done:
                getting.cancel()
                if gone.done():
                    break
                message = _event("ping", {"seq": _seq})
            else:
                message = getting.result()
            if message is None:  # fell too far behind
                break
            writer.write(message)
            await asyncio.wait_for(writer.drain(), PING * 2)  # a page that stops reading is gone too
    except (ConnectionError, asyncio.TimeoutError, RuntimeError):
        pass
    finally:
        gone.cancel()
        if me in _streams:
            _streams.remove(me)
