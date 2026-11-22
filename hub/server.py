#!/usr/bin/env python3
"""Dream Hub: a private console for the memory kit and for Claude sessions. Standard library only.

Binds to loopback. Two ways in, chosen by the config:
- "login": reached only through Tailscale Serve, which sets Tailscale-User-Login; every request must carry that login.
- "key" (no "login"): this Mac only; the browser opens /?key=<key> once and from then on carries it in a cookie.
Every request must carry the app's Host; writes and terminals must also carry the app's Origin.
"""
import asyncio, base64, errno, fcntl, gzip, hashlib, hmac, json, mimetypes, os, re, resource, signal, struct, subprocess, sys, termios, time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import hub_artifacts as artifacts
import hub_browser as browser
import hub_catcher as catcher
import hub_data as hub
import hub_diff
import hub_overview
import hub_preview as preview
import hub_settings
import hub_push
import hub_status
import hub_update
import hub_worktrees

if __name__ == "__main__" and "--check" in sys.argv[1:]:  # before the config is needed: it may be what's broken
    sys.exit(hub_settings.cli_check())

HOST, PORT = "127.0.0.1", hub.PORT
UI = hub.APP / "ui"
CONFIG = json.loads(hub.CONFIG.read_text())
OWNER, ORIGIN = str(CONFIG.get("login") or ""), CONFIG["origin"]
KEY = str(CONFIG.get("key") or "")  # used only when there is no login: the hub on this Mac alone, without Tailscale
if not OWNER and len(KEY) < 32:
    raise SystemExit(f"{hub.CONFIG} needs a \"login\" (the hub behind Tailscale Serve) or a \"key\" of 32 characters or more (the hub on this Mac only). install.sh writes one.")
APP_HOST = urlsplit(ORIGIN).netloc
COOKIE = "hub_key"
MAX_BODY = 1_000_000
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_UPLOAD = 40_000_000
SECURITY = ("Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'none'\r\n"
            "X-Frame-Options: DENY\r\nX-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\nCache-Control: no-store\r\n")
PING_EVERY, SILENT_LIMIT = 25, 70  # seconds; a terminal viewer silent past the limit is closed, freeing its socket, pty and tmux client
OPEN_FILES = 4096  # launchd's default of 256 is too tight for many panes on several devices
STATE_TTL = 1.5
_state_cache = (0.0, None)
_writes = 0  # every write counts up, so a state read across one is never cached


async def respond(writer, status, body=b"", kind="application/json"):
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode()
    writer.write((f"HTTP/1.1 {status}\r\nContent-Type: {kind}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n{SECURITY}\r\n").encode() + body)
    await writer.drain()


async def respond_file(writer, data_or_path, mime, headers):
    """Shared files open sandboxed, so a file from a session can never run as this app."""
    is_path = isinstance(data_or_path, Path)
    size = data_or_path.stat().st_size if is_path else len(data_or_path)
    start, end, status, extra = 0, size - 1, "200 OK", ""
    match = re.match(r"bytes=(\d*)-(\d*)$", headers.get("range", ""))
    if match and size and (match[1] or match[2]):
        start = int(match[1]) if match[1] else max(0, size - int(match[2]))
        end = min(int(match[2]), size - 1) if match[1] and match[2] else size - 1
        if start > end:
            start, end = 0, size - 1
        else:
            status, extra = "206 Partial Content", f"Content-Range: bytes {start}-{end}/{size}\r\n"
    length = max(0, end - start + 1)
    if is_path:
        with open(data_or_path, "rb") as f:
            f.seek(start)
            body = f.read(min(length, 64_000_000))
    else:
        body = data_or_path[start:end + 1]
    policy = "" if mime == "application/pdf" else "Content-Security-Policy: sandbox; default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'\r\n"
    writer.write((f"HTTP/1.1 {status}\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\nAccept-Ranges: bytes\r\n{extra}{policy}"
                  "X-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\nCache-Control: private, max-age=60\r\nConnection: close\r\n\r\n").encode() + body)
    await writer.drain()


async def respond_artifact(writer, path, headers, download=False):
    """A session's artifact, as hub_artifacts.resolve allowed it: its own type, its own sandbox, read in ranges."""
    size = path.stat().st_size
    start, end, status, extra = 0, size - 1, "200 OK", ""
    match = re.match(r"bytes=(\d*)-(\d*)$", headers.get("range", ""))
    if match and size and (match[1] or match[2]):
        start = int(match[1]) if match[1] else max(0, size - int(match[2]))
        end = min(int(match[2]), size - 1) if match[1] and match[2] else size - 1
        if start > end:
            start, end = 0, size - 1
        else:
            status, extra = "206 Partial Content", f"Content-Range: bytes {start}-{end}/{size}\r\n"
    length = max(0, end - start + 1)
    policy = artifacts.policy_of(path, ORIGIN)
    if download:
        safe = re.sub(r'[^\w. -]+', "_", path.name)[:120] or "file"
        extra += f'Content-Disposition: attachment; filename="{safe}"\r\n'
    writer.write((f"HTTP/1.1 {status}\r\nContent-Type: {artifacts.mime_of(path)}\r\nContent-Length: {length}\r\nAccept-Ranges: bytes\r\n{extra}"
                  + (f"Content-Security-Policy: {policy}\r\n" if policy else "")
                  + "X-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n"
                  "Cache-Control: no-cache\r\nConnection: close\r\n\r\n").encode())
    with open(path, "rb") as f:
        f.seek(start)
        while length > 0:
            chunk = f.read(min(length, 1 << 20))
            if not chunk:
                break
            writer.write(chunk)
            length -= len(chunk)
            await writer.drain()
    await writer.drain()


def cookie(headers, name: str) -> str:
    for part in headers.get("cookie", "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return ""


def identified(headers) -> bool:
    if OWNER:
        login = headers.get("tailscale-user-login", "")
        return hmac.compare_digest(login.encode(), OWNER.encode()) and headers.get("host") == APP_HOST
    return hmac.compare_digest(cookie(headers, COOKIE).encode(), KEY.encode()) and headers.get("host") == APP_HOST


async def let_in(writer):
    """The one answer to /?key=<the key>: the key goes into a cookie only this origin gets, and the page loads without it."""
    writer.write((f"HTTP/1.1 303 See Other\r\nLocation: /\r\nSet-Cookie: {COOKIE}={KEY}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000\r\n"
                  f"Content-Length: 0\r\nConnection: close\r\n{SECURITY}\r\n").encode())
    await writer.drain()


def same_origin(headers) -> bool:
    return hmac.compare_digest(headers.get("origin", "").encode(), ORIGIN.encode())


def cached_state():
    global _state_cache
    pushed = hub_push.fresh()  # the state loop's, while a page watches and it is fresh
    if pushed is not None:
        return pushed
    now = time.monotonic()
    if now - _state_cache[0] > STATE_TTL or _state_cache[1] is None:
        writes = _writes
        fresh = {**hub.state(), "catcher": catcher.summary()}
        if writes == _writes:  # one read while a write landed may hold what was there before it: it isn't kept for the next poll
            _state_cache = (now, fresh)
        return fresh
    return _state_cache[1]


def route(method, parts, query, body):
    """Plain functions, run off the event loop. Returns JSON-ready data."""
    one = lambda key: query.get(key, [""])[0]
    if parts[:2] == ["api", "browser"]:  # the built-in browser and device preview (hub_browser.py); a 404 while both are off
        return browser.route(method, parts[2:], query)
    if method == "GET":
        if parts == ["api", "state"]:
            return {**cached_state(), "reads": hub.reads_of()}  # read marks are one small file, so a mark made a moment ago shows at once
        if parts == ["api", "folders"]:
            return hub.folders()
        if parts == ["api", "catcher"]:
            return catcher.page()
        if parts == ["api", "home"]:
            return hub.platform()
        if parts == ["api", "settings"]:
            return hub_settings.page()
        if parts == ["api", "settings", "health"]:
            return hub_settings.health(fresh=one("fresh") == "1")
        if parts == ["api", "settings", "about"]:
            return hub_settings.about()
        if parts == ["api", "settings", "worktree-preview"]:
            return hub_worktrees.preview(one("template") or "", one("project") or "")
        if parts == ["api", "update"]:  # the last update check and the version this hub runs; starts a daily check if one is due
            return hub_update.status()
        if parts == ["api", "preview", "link"]:
            try:
                return preview.link_card(one("url"))
            except preview.NotFetched as refused:  # an answer, not an error: the card says why there is nothing to show
                return {"refused": str(refused)}
        if parts == ["api", "preview", "cached"]:
            return preview.cached_cards(query.get("url", []))
        if len(parts) == 4 and parts[:2] == ["api", "p"]:
            name, what = parts[2], parts[3]
            if what == "home":
                return hub.home_of(name)
            if what == "memory":
                return hub.memory_files(name)
            if what == "file":
                return hub.read_memory(name, one("path"))
            if what == "search":
                return hub.search_memory(name, one("q"))
            if what == "dreams":
                return hub.dreams_of(name)
            if what == "dream":
                return hub.read_dream(name, one("file"))
            if what == "agents":
                return hub.project_agents(name)
            if what == "pins":
                return hub.pins_of(hub.store_of(name))
            if what == "worktrees":
                return hub_worktrees.route_list(name)
            if what == "artifacts":
                return artifacts.project_list(name)
        if len(parts) == 4 and parts[:2] == ["api", "sessions"]:
            if parts[3] == "shared":
                return hub.shared_items(parts[2])
            if parts[3] == "artifacts":
                return artifacts.session_list(parts[2])
            if parts[3] == "artifact-text":
                return artifacts.text_of(parts[2], one("path"))
            if parts[3] == "preview":
                return hub.preview(parts[2], one("path"))
            if parts[3] == "info":
                return preview.file_info(parts[2], one("path"))
            if parts[3] == "agents":
                return hub.session_agents(parts[2])
            if parts[3] == "record":
                return hub.session_record(parts[2])
            if parts[3] == "closing":
                return hub.close_check(parts[2])
            if parts[3] == "deleting":
                return hub.delete_check(parts[2])
            if parts[3] == "diff":
                return hub_diff.diff(parts[2], one("path"))
            if parts[3] == "peek":
                return hub_status.peek(parts[2], cached_state()["sessions"])
    if method == "PUT" and parts == ["api", "settings"]:
        return hub_settings.write(body)
    if method == "POST":
        if len(parts) == 3 and parts[:2] == ["api", "settings"]:
            action = {"seen": hub_settings.seen, "welcome": hub_settings.dismiss_welcome, "forget-starts": hub_settings.forget_starts}.get(parts[2])
            if action:
                return action(body)
        if parts == ["api", "update", "check"]:  # takes nothing from the request
            return hub_update.check_now()
        if parts == ["api", "update", "apply"]:  # takes nothing from the request: runs the clone's own update.sh
            return hub_update.apply()
        if parts == ["api", "projects"]:
            return hub.create_project(body)
        if parts == ["api", "sessions"]:
            return hub.start_sessions(body)
        if parts == ["api", "groups"]:
            return hub.set_groups(body)
        if parts == ["api", "lost", "resume"]:  # the sessions the Mac's restart took: all of them, or the ids named
            return hub.resume_lost(body)
        if parts == ["api", "lost", "dismiss"]:
            return hub.dismiss_lost(body)
        if parts == ["api", "reads"]:
            return hub.set_reads(body)
        if parts == ["api", "boards"]:
            return hub.set_boards(body)
        if len(parts) == 3 and parts[:2] == ["api", "catcher"]:
            action = {"run": catcher.start, "accept": catcher.accept, "decide": catcher.decide, "auto": catcher.set_auto}.get(parts[2])
            if action:
                return action(body)
        if len(parts) == 4 and parts[:2] == ["api", "sessions"]:
            action = {"stop": hub.stop_session, "dismiss": hub.dismiss_session, "delete": hub.delete_session, "phone": hub.connect_phone, "resume": hub.resume_session}.get(parts[3])
            if action:
                return action(parts[2])
            if parts[3] == "clear":
                return hub_status.clear(parts[2])
            action = {"mode": hub.set_mode, "model": hub.set_model, "rename": hub.rename_session, "close": hub.close_session,
                      "port-stop": hub_status.stop_port, "answer": hub_status.answer, "key": hub_status.press, "review": hub_diff.review}.get(parts[3])
            if action:
                return action(parts[2], body)
        if len(parts) >= 4 and parts[:2] == ["api", "p"]:
            name, what = parts[2], "/".join(parts[3:])
            action = {"file": hub.write_memory, "dream/tick": hub.tick, "dream/fact": hub.fact_sign, "dream/done": hub.close_need, "dream/approve": hub.approve_need, "dream/reject": hub.reject_need, "dream/apply": hub.apply_dream, "dream/dismiss": hub.dismiss_dream, "dream/forget": hub.forget_item, "dream/release": hub.release_dream, "dream/yours": hub.yours_session, "dream/session": hub.waiting_session, "dream/withdraw": hub.withdraw_item, "schedule": hub.set_schedule, "profile": hub.set_profile, "start": hub.set_start, "commit-kit": hub.commit_kit}.get(what)
            if action:
                return action(name, body)
            action = {"worktrees/remove": hub_worktrees.route_remove, "worktrees/branch": hub_worktrees.route_branch, "worktrees/clean": hub_worktrees.route_clean}.get(what)
            if action:
                return action(name, body)
            if what == "dream/run":
                return hub.start_dream(name)
            if what == "dream/fix":
                return hub.start_fix(name)
    return None


_packed = {}  # path -> (stamp, gzipped bytes): the interface's text files, compressed once per version


async def serve_static(writer, path, headers=None):
    """The interface's files. Checked on every load (no-cache), but a file the browser already has comes back as a bare
    304, and text goes gzipped: about a megabyte becomes a quarter of one, which a phone notices."""
    rel = "index.html" if path in ("/", "") else unquote(path).lstrip("/")
    if not rel.startswith("ui/") and rel != "index.html":
        return await respond(writer, "404 Not Found", {"error": "Not found"})
    file = (UI / rel[3:] if rel.startswith("ui/") else UI / "index.html").resolve()
    if UI.resolve() not in file.parents or not file.is_file():
        return await respond(writer, "404 Not Found", {"error": "Not found"})
    headers = headers or {}
    known = file.stat()
    stamp = f'"{known.st_mtime_ns:x}-{known.st_size:x}"'
    mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    security = SECURITY
    if rel == "index.html" and browser.frame_sources(SECURITY) != SECURITY:  # the page may frame the preview while the browser is on
        security, stamp = browser.frame_sources(SECURITY), stamp[:-1] + '-frames"'
    cache = security.replace("Cache-Control: no-store", "Cache-Control: no-cache") + f"ETag: {stamp}\r\nVary: Accept-Encoding\r\n"
    if stamp in [tag.strip() for tag in headers.get("if-none-match", "").split(",")]:
        writer.write(f"HTTP/1.1 304 Not Modified\r\nConnection: close\r\n{cache}\r\n".encode())
        return await writer.drain()
    body, packed = file.read_bytes(), ""
    if "gzip" in headers.get("accept-encoding", "") and (mime.startswith("text/") or mime in ("application/javascript", "application/json", "image/svg+xml", "application/manifest+json")) and len(body) > 1024:
        kept = _packed.get(file)
        if not kept or kept[0] != stamp:
            kept = _packed[file] = (stamp, gzip.compress(body, 6))
        body, packed = kept[1], "Content-Encoding: gzip\r\n"
    writer.write((f"HTTP/1.1 200 OK\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\n{packed}Connection: close\r\n{cache}\r\n").encode() + body)
    await writer.drain()


# ── terminal over WebSocket ──
def frame(opcode, payload):
    head = bytes([0x80 | opcode])
    size = len(payload)
    if size < 126:
        head += bytes([size])
    elif size < 65536:
        head += bytes([126]) + struct.pack(">H", size)
    else:
        head += bytes([127]) + struct.pack(">Q", size)
    return head + payload


async def read_message(reader):
    data, kind = b"", None
    while True:
        first, second = await reader.readexactly(2)
        opcode, size = first & 0x0F, second & 0x7F
        if not second & 0x80:
            raise ConnectionError("unmasked client frame")
        if size == 126:
            size = struct.unpack(">H", await reader.readexactly(2))[0]
        elif size == 127:
            size = struct.unpack(">Q", await reader.readexactly(8))[0]
        if size > MAX_BODY:
            raise ConnectionError("frame too large")
        mask = await reader.readexactly(4)
        body = await reader.readexactly(size)
        body = bytes(b ^ mask[i % 4] for i, b in enumerate(body))
        if opcode >= 8:
            return opcode, body
        kind = kind if opcode == 0 else opcode
        data += body
        if first & 0x80:
            return kind, data


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(2, min(rows, 400)), max(2, min(cols, 600)), 0, 0))


def controlling_tty():
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


async def terminal(reader, writer, headers, sid, query):
    target = f"hub-{sid}"
    if target not in await asyncio.get_event_loop().run_in_executor(None, hub.tmux_sessions):
        return await respond(writer, "404 Not Found", {"error": "That session has ended."})
    try:
        cols, rows = int(query.get("cols", ["120"])[0]), int(query.get("rows", ["36"])[0])
    except ValueError:
        return await respond(writer, "400 Bad Request", {"error": "Bad request."})
    key = headers.get("sec-websocket-key", "")
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    writer.write(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
    await writer.drain()

    master, slave = os.openpty()
    try:
        set_size(master, cols, rows)
        process = subprocess.Popen([hub.TMUX, *hub.SOCKET, "-u", "attach-session", "-t", target], stdin=slave, stdout=slave, stderr=slave,
                                   env=hub.ENV, start_new_session=True, preexec_fn=controlling_tty, close_fds=True)
    except BaseException:
        os.close(master)
        raise
    finally:
        os.close(slave)
    loop = asyncio.get_event_loop()
    closed = loop.create_future()
    heard = [time.monotonic()]  # browsers answer every ping, so a viewer that stays silent has gone (a phone asleep, a dropped network)

    def on_output():
        try:
            data = os.read(master, 65536)
        except OSError as error:
            data = b"" if error.errno == errno.EIO else None
        if not data:
            loop.remove_reader(master)
            if not closed.done():
                closed.set_result(True)
            return
        writer.write(frame(2, data))

    async def keepalive():
        while True:
            await asyncio.sleep(PING_EVERY)
            if time.monotonic() - heard[0] > SILENT_LIMIT:
                return
            writer.write(frame(9, b""))
            await asyncio.wait_for(writer.drain(), SILENT_LIMIT)  # a viewer that stops reading is gone too

    async def on_input():
        while True:
            opcode, data = await read_message(reader)
            heard[0] = time.monotonic()
            if opcode == 8:
                return
            if opcode == 9:
                writer.write(frame(10, data))
            elif opcode == 1:
                message = json.loads(data)
                if message.get("t") == "i":
                    os.write(master, message.get("d", "").encode())
                elif message.get("t") == "r":
                    set_size(master, int(message["c"]), int(message["r"]))

    loop.add_reader(master, on_output)
    tasks = [asyncio.ensure_future(on_input()), asyncio.ensure_future(keepalive()), closed]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except (ConnectionError, asyncio.IncompleteReadError, ValueError, KeyError, OSError):
        pass
    finally:
        for task in tasks:
            task.cancel()
        try:
            loop.remove_reader(master)
            os.close(master)
        except OSError:
            pass
        process.terminate()  # detaches this viewer; the session keeps running in tmux
        try:
            await loop.run_in_executor(None, process.wait, 5)
        except subprocess.TimeoutExpired:
            process.kill()
            await loop.run_in_executor(None, process.wait)
        ended = closed.done() and target not in await loop.run_in_executor(None, hub.tmux_sessions)
        try:
            writer.write(frame(8, struct.pack(">H", 4000) + b"ended" if ended else b""))  # 4000: the session is gone, don't reconnect
            await asyncio.wait_for(writer.drain(), 5)
        except (ConnectionError, RuntimeError, asyncio.TimeoutError):
            pass
        writer.transport.abort()  # never wait on a peer that has gone


async def handle(reader, writer):
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
        lines = raw.decode("latin-1").split("\r\n")
        method, target, _ = lines[0].split(" ", 2)
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        url = urlsplit(target)
        parts = [unquote(p) for p in url.path.split("/") if p]
        query = parse_qs(url.query)
        if not OWNER and method == "GET" and not parts and headers.get("host") == APP_HOST and hmac.compare_digest(query.get("key", [""])[0].encode(), KEY.encode()):
            return await let_in(writer)
        if not identified(headers):
            return await respond(writer, "403 Forbidden", {"error": "Not yours."})
        if parts[:1] == ["api"] and not artifacts.raw_route(parts) and (headers.get("origin") == "null" or headers.get("sec-fetch-site") in ("cross-site", "same-site")):
            return await respond(writer, "403 Forbidden", {"error": "Wrong origin."})  # a sandboxed page (an HTML artifact) or another site: never the API
        if parts[:1] in (["api"], ["ws"]) and browser.refuses(headers):
            return await respond(writer, "403 Forbidden", {"error": "Wrong origin."})  # a page from the preview listener never reaches the API
        upgrade = headers.get("upgrade", "").lower() == "websocket"
        if upgrade or method != "GET":
            if not same_origin(headers):
                return await respond(writer, "403 Forbidden", {"error": "Wrong origin."})
        if upgrade:
            if len(parts) == 3 and parts[:2] == ["ws", "term"] and hub.SESSION_ID.match(parts[2]):
                return await terminal(reader, writer, headers, parts[2], query)
            return await respond(writer, "404 Not Found", {"error": "Not found"})
        if method == "GET" and parts == ["api", "stream"]:
            return await hub_push.stream(reader, writer, SECURITY)
        if parts[:1] != ["api"]:
            if method != "GET":
                return await respond(writer, "405 Method Not Allowed", {"error": "No."})
            return await serve_static(writer, url.path, headers)
        if parts[:2] == ["api", "preview"] and headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            return await respond(writer, "403 Forbidden", {"error": "Wrong origin."})  # another site in the browser can't make the hub fetch for it
        loop = asyncio.get_event_loop()
        try:
            if method == "GET" and parts == ["api", "preview", "image"]:
                data, mime = await loop.run_in_executor(None, preview.picture, query.get("id", [""])[0])
                return await respond_file(writer, data, mime, headers)
            if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] == "thumb":
                data, mime = await loop.run_in_executor(None, preview.thumbnail, parts[2], query.get("path", [""])[0], query.get("ref", [""])[0], query.get("px", [""])[0])
                return await respond_file(writer, data, mime, headers)
            if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "sessions"] and parts[3] in ("file", "blob"):
                if parts[3] == "file":
                    path = await loop.run_in_executor(None, hub.resolve_shared, parts[2], query.get("path", [""])[0])
                    return await respond_file(writer, path, hub.mime_of(path), headers)
                data, mime = await loop.run_in_executor(None, hub.blob_of, parts[2], query.get("ref", [""])[0])
                return await respond_file(writer, data, mime, headers)
            if method == "GET" and artifacts.raw_route(parts):
                path = await loop.run_in_executor(None, artifacts.resolve, parts[2], "/" + "/".join(parts[4:]))
                return await respond_artifact(writer, path, headers, download=query.get("download", [""])[0] == "1")
            if method == "GET" and len(parts) == 4 and parts[:2] == ["api", "p"] and parts[3] == "icon":
                path = await loop.run_in_executor(None, hub.icon_file, parts[2])
                return await respond_file(writer, path, mimetypes.guess_type(path.name)[0] or "image/png", headers)
            if method == "POST" and len(parts) == 4 and headers.get("content-type") == "application/octet-stream" and (parts[1], parts[3]) in (("sessions", "upload"), ("p", "icon")):
                size = int(headers.get("content-length", "0"))
                if size > MAX_UPLOAD:
                    return await respond(writer, "413 Payload Too Large", {"error": "That file is over 40 MB."})
                data = await reader.readexactly(size)
                if parts[1] == "sessions":
                    result = await loop.run_in_executor(None, hub.save_upload, parts[2], query.get("name", ["file"])[0], data)
                else:
                    result = await loop.run_in_executor(None, hub.save_icon, parts[2], data)
                return await respond(writer, "200 OK", result)
            # The side panel's Overview, and Open in Finder: both ask whether the page is on this Mac, so they see the headers.
            if len(parts) == 4 and parts[:2] == ["api", "sessions"] and (method, parts[3]) in (("GET", "overview"), ("POST", "reveal")):
                result = await loop.run_in_executor(None, hub_overview.overview if parts[3] == "overview" else hub_overview.reveal, parts[2], headers)
                return await respond(writer, "200 OK", result)
        except hub.Refused as refused:
            return await respond(writer, refused.status, {"error": str(refused), **refused.more})
        body = {}
        if method in ("POST", "PUT"):
            size = int(headers.get("content-length", "0"))
            if size > MAX_BODY or headers.get("content-type", "").split(";")[0] != "application/json":
                return await respond(writer, "400 Bad Request", {"error": "Bad request."})
            body = json.loads(await reader.readexactly(size) or b"{}") if size else {}
            if not isinstance(body, dict):
                return await respond(writer, "400 Bad Request", {"error": "Bad request."})
        try:
            result = await asyncio.get_event_loop().run_in_executor(None, route, method, parts, query, body)
            if method != "GET" and parts != ["api", "reads"]:  # a read mark isn't in the cached state: it is read fresh each poll
                global _state_cache, _writes
                _writes += 1
                _state_cache = (0.0, None)  # the next poll must show what this write changed
                hub_push.kick(write=True)  # and so must the open pages, now
            if method == "PUT" and parts == ["api", "settings"]:
                await browser.sync()  # the preview listener follows its switches at once
        except hub.Refused as refused:
            return await respond(writer, refused.status, {"error": str(refused), **refused.more})
        if result is None:
            return await respond(writer, "404 Not Found", {"error": "Not found"})
        await respond(writer, "200 OK", result)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, asyncio.LimitOverrunError):
        pass
    except Exception as error:  # keep the details in the log, not the browser
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        try:
            await respond(writer, "500 Internal Server Error", {"error": "Something went wrong."})
        except ConnectionError:
            pass
    finally:
        try:
            writer.close()
        except RuntimeError:
            pass


def raise_file_limit():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    want = OPEN_FILES if hard == resource.RLIM_INFINITY else min(OPEN_FILES, hard)
    if soft != resource.RLIM_INFINITY and soft < want:
        resource.setrlimit(resource.RLIMIT_NOFILE, (want, hard))


async def main():
    raise_file_limit()
    hub.prepare()
    hub_update.check()  # in the background; a request never waits for it
    catcher.watch()  # carries out a Dream Catcher run once it finishes, whether or not a page is open
    hub_push.start()  # keeps the state fresh while a page watches, and pushes its changes
    browser.start()  # the preview listener, while the browser or the device preview is on
    server = await asyncio.start_server(handle, HOST, PORT, limit=65536)
    print(f"Dream Hub on {HOST}:{PORT}, {'owner check on' if OWNER else 'key check on (this Mac only)'}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    asyncio.run(main())
