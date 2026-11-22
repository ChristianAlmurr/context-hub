"""The built-in browser and the device preview: pages from dev servers on this Mac, shown on desk and phone.

A dev server listens on this Mac's loopback (localhost:5173, say), so a phone can't open it: "localhost" there is the
phone. The hub can't show it on its own origin either, because a page that ran there could call /api and type into a
terminal. So the pages come through a second listener, on its own port (HUB_PREVIEW_PORT, the hub's port + 1 unless
set): a different origin, which the hub's API refuses (server.py), and which itself refuses anyone but the owner.

How a page is reached:
- The hub page asks the hub for a ticket for one port (GET /api/browser/ticket): signed, for two minutes, for that port only.
- The frame opens /__hub/go?port=5173&path=/about&t=<ticket> on the listener. That sets two cookies, a pass (who you
  are, for twelve hours) and the port, and redirects to /about. From then on every request at the root goes to that
  port, so the app runs at "/" as it does on localhost: its router, its absolute links, its hot reload all work.
- /p/<port>/<path> does the same for an address typed or pasted into the browser's own bar, and nothing else: a page
  can't move the listener to another port, because only a ticket or the person's own typing can.

Only loopback is proxied (127.0.0.1, then ::1), never the hub's own ports, and nothing else. The owner check is the
hub's: the Tailscale login, or in a key-only hub the key's cookie, or the pass a ticket gave. Writes and WebSockets must
come from the preview's own origin. The hub's cookies never reach a dev server, and a dev server can't set the listener's.

Cookies set by a dev server keep their path and lose their Domain: they behave as they do on localhost, where every
port already shares one set of cookies. One port at a time per browser: opening another port moves every frame there.

For the phone, the listener needs a Tailscale Serve mapping, made once by the person (see `serve_command`). Settings ›
Health says when it is missing. At the desk on this Mac, the listener's loopback address works without it.
"""
import asyncio, concurrent.futures, hashlib, hmac, html, http.client, json, os, re, secrets, socket, ssl, subprocess, threading, time
from urllib.parse import parse_qs, quote, urlsplit

import hub_base as base
import hub_settings

# ── which listener this is ──
def _preview_port() -> int:
    raw = os.environ.get("HUB_PREVIEW_PORT", "").strip()
    if raw:
        if not (raw.isascii() and raw.isdigit() and 1 <= int(raw) <= 65535):
            raise SystemExit(f"HUB_PREVIEW_PORT must be a port from 1 to 65535, and {raw!r} isn't.")
        if int(raw) == base.PORT:
            raise SystemExit("HUB_PREVIEW_PORT can't be the hub's own port.")
        return int(raw)
    return base.PORT + 1 if base.PORT < 65535 else base.PORT - 1


PREVIEW_PORT = _preview_port()
_cfg = base.settings_in(base.CONFIG)
ORIGIN = str(_cfg.get("origin") or f"http://127.0.0.1:{base.PORT}")
OWNER = str(_cfg.get("login") or "")
KEY = str(_cfg.get("key") or "")
_hub = urlsplit(ORIGIN)
SCHEME = _hub.scheme or "http"
HOSTNAME = (_hub.hostname or "127.0.0.1").lower()
LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_netloc = f"[{HOSTNAME}]" if ":" in HOSTNAME else HOSTNAME
PUBLIC = f"{SCHEME}://{_netloc}:{PREVIEW_PORT}"  # the preview as the person's devices reach it: the hub's host, this port
LOCAL = f"http://127.0.0.1:{PREVIEW_PORT}"  # on this Mac, with no mapping
ORIGINS = list(dict.fromkeys([PUBLIC, LOCAL, f"http://localhost:{PREVIEW_PORT}"]))
HOSTNAMES = {HOSTNAME, "127.0.0.1", "localhost"}
INSTANCE = secrets.token_hex(8)  # /__hub/ping says it, so Health knows the answer came from this listener
SECRET = secrets.token_bytes(32)  # tickets, passes and port cookies; new at each start
PASS, PORT_COOKIE = "__hub_pv", "__hub_port"
OURS = {PASS, PORT_COOKIE, "hub_key"}  # never sent to a dev server, never set by one
TICKET_TTL, PASS_TTL = 120, 12 * 3600
HOP = {"connection", "keep-alive", "proxy-connection", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "expect"}


def refused_port(port) -> bool:
    """The hub's own ports (this one's, its listener's, the installed hub's and its listener's) and anything that isn't a port."""
    own = {base.PORT, PREVIEW_PORT, base.INSTALLED["port"], base.INSTALLED["port"] + 1}
    return not isinstance(port, int) or not 1 <= port <= 65535 or port in own


def on() -> bool:
    """The listener runs while either feature is on: the device preview shows its pages too."""
    try:
        return bool(hub_settings.value("feature_browser")) or bool(hub_settings.value("feature_preview"))
    except Exception:
        return True


def serve_command() -> str:
    """What the person runs once on the Mac so the phone can reach the preview. Never run by the hub."""
    return f"tailscale serve --bg --https={PREVIEW_PORT} http://127.0.0.1:{PREVIEW_PORT}"


# ── tickets, passes, the port cookie ──
def sign(scope: str, ttl: int) -> str:
    until = int(time.time()) + ttl
    mac = hmac.new(SECRET, f"{scope}|{until}".encode(), hashlib.sha256).hexdigest()[:40]
    return f"{until}.{mac}"


def valid(token: str, scope: str) -> bool:
    until, _, mac = str(token or "").partition(".")
    if not until.isdigit() or int(until) < time.time():
        return False
    want = hmac.new(SECRET, f"{scope}|{until}".encode(), hashlib.sha256).hexdigest()[:40]
    return hmac.compare_digest(mac.encode(), want.encode())


def cookie(headers: dict, name: str) -> str:
    for part in headers.get("cookie", "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value
    return ""


def port_of(headers: dict):
    """The port this browser's frames are on, from its signed cookie."""
    port, _, token = cookie(headers, PORT_COOKIE).partition("-")
    return int(port) if port.isdigit() and valid(token, f"port:{port}") and not refused_port(int(port)) else None


def owner(headers: dict) -> bool:
    """The hub's own check: the right host, then the Tailscale login (or the key's cookie in a key-only hub), or a pass."""
    host = headers.get("host", "")
    name = host[1:].split("]")[0] if host.startswith("[") else host.rsplit(":", 1)[0]
    if name.lower() not in HOSTNAMES:
        return False
    if OWNER and hmac.compare_digest(headers.get("tailscale-user-login", "").encode(), OWNER.encode()):
        return True
    if not OWNER and len(KEY) >= 32 and hmac.compare_digest(cookie(headers, "hub_key").encode(), KEY.encode()):
        return True
    return valid(cookie(headers, PASS), "pass")


def _cookie_attrs(headers: dict) -> str:
    """Same-site frames (the hub's host, another port) take Lax. Framed across sites (an https hub framing this Mac's
    loopback), a cookie must be SameSite=None, Secure and partitioned to be kept at all."""
    if headers.get("sec-fetch-site") == "cross-site":
        return "Path=/; HttpOnly; SameSite=None; Secure; Partitioned"
    return "Path=/; HttpOnly; SameSite=Lax" + ("; Secure" if SCHEME == "https" and headers.get("host", "").split(":")[0].lower() == HOSTNAME else "")


def _set_cookies(headers: dict, port=None) -> list:
    attrs = _cookie_attrs(headers)
    out = [f"Set-Cookie: {PASS}={sign('pass', PASS_TTL)}; Max-Age={PASS_TTL}; {attrs}"]
    if port is not None:
        out.append(f"Set-Cookie: {PORT_COOKIE}={port}-{sign(f'port:{port}', PASS_TTL)}; Max-Age={PASS_TTL}; {attrs}")
    return out


# ── the listener ──
_server = None
_bind_error = ""
_open = set()  # writers of connections in flight, so switching off ends them too
_lock = None  # made in the loop, see sync()


async def sync():
    """Listen while a feature needs it, stop when neither does. Called at start, after a settings write, and every two seconds."""
    global _server, _bind_error, _lock
    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        want = on()
        if want and _server is None:
            try:
                _server = await asyncio.start_server(handle, "127.0.0.1", PREVIEW_PORT, limit=262144)
                _bind_error = ""
                print(f"Preview listener on 127.0.0.1:{PREVIEW_PORT}", flush=True)
            except OSError as error:
                if not _bind_error:
                    print(f"error: the preview listener can't use port {PREVIEW_PORT}: {error.strerror}", flush=True)
                _bind_error = error.strerror or str(error)
        elif not want and _server is not None:
            _server.close()
            _server = None
            for writer in list(_open):
                writer.transport.abort()
            _open.clear()
            print("Preview listener off", flush=True)


async def watch():
    while True:
        try:
            await sync()
        except Exception as error:  # the hub goes on whatever the listener does
            print(f"error: preview listener: {type(error).__name__}: {error}", flush=True)
        await asyncio.sleep(2)


def start():
    asyncio.ensure_future(watch())


async def _reply(writer, status: str, body: bytes = b"", kind="text/plain; charset=utf-8", extra=()):
    head = [f"HTTP/1.1 {status}", f"Content-Type: {kind}", f"Content-Length: {len(body)}", "Connection: close",
            "Cache-Control: no-store", "X-Content-Type-Options: nosniff", "Referrer-Policy: no-referrer", *extra]
    writer.write(("\r\n".join(head) + "\r\n\r\n").encode("latin-1") + body)
    await writer.drain()


def _page(title: str, text: str, refresh=0) -> bytes:
    """A small page of the listener's own, in either colour scheme: never a browser's error page inside a frame."""
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">{meta}'
            f"<title>{title}</title><style>:root{{color-scheme:dark light;font:15px/22px -apple-system,system-ui,sans-serif}}"
            "body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b1020;color:#eef2ff}"
            "@media (prefers-color-scheme:light){body{background:#f5f7fb;color:#121a2f}p{color:#3f4a66}}"
            "main{max-width:34ch;padding:24px;text-align:center}h1{font-size:17px;margin:0 0 8px}p{margin:0;color:#b4beda}</style></head>"
            f"<body><main><h1>{title}</h1><p>{text}</p></main></body></html>").encode()


async def _html(writer, status, title, text, refresh=0):
    await _reply(writer, status, _page(title, text, refresh), "text/html; charset=utf-8", ("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self' " + ORIGIN,))


FRAME_JS = """(() => {
  // The hub's browser helper: says where this frame is, and goes back, forward or reloads when the hub asks.
  const hub = document.currentScript && document.currentScript.dataset.hub;
  if (!hub || window.parent === window) return;
  let last = "";
  const say = () => {
    const now = location.href + "\\n" + document.title;
    if (now === last) return;
    last = now;
    parent.postMessage({ hubFrame: "loc", href: location.href, title: document.title }, hub);
  };
  for (const name of ["pushState", "replaceState"]) {
    const was = history[name];
    history[name] = function () { const out = was.apply(this, arguments); setTimeout(say, 0); return out; };
  }
  addEventListener("popstate", say); addEventListener("hashchange", say); addEventListener("load", say);
  document.addEventListener("DOMContentLoaded", () => {
    say();
    const t = document.querySelector("title");
    if (t) new MutationObserver(say).observe(t, { childList: true, characterData: true, subtree: true });
  });
  addEventListener("message", (e) => {
    if (e.source !== parent || e.origin !== hub || !e.data || typeof e.data.hubFrame !== "string") return;
    const ask = e.data.hubFrame;
    if (ask === "back") history.back();
    else if (ask === "forward") history.forward();
    else if (ask === "reload") location.reload();
    else if (ask === "go" && typeof e.data.path === "string" && /^\\/(?!\\/)/.test(e.data.path)) location.assign(e.data.path);
    else if (ask === "where") { last = ""; say(); }
  });
})();
"""
SNIPPET = f'<script src="/__hub/frame.js" data-hub="{html.escape(ORIGIN)}"></script>'.encode()


def _local_path(text: str) -> str:
    """A path on the preview itself, safe in a Location header: never another host (//host, a backslash), never a
    control character or anything outside ASCII, which are percent-encoded."""
    text = text or "/"
    if not text.startswith("/") or text.startswith("//") or "\\" in text:
        return "/"
    return quote(text, safe="/?#&=%:@!$'()*+,;~-._[]")


def _parse(raw: bytes):
    lines = raw.decode("latin-1").split("\r\n")
    method, target, _ = lines[0].split(" ", 2)
    pairs = []
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            pairs.append((key.strip(), value.strip()))
    return method, target, pairs


_running = set()  # every handler in flight, held: asyncio keeps only a weak reference to a task, and a stream that waits
                  # long on the dev server was otherwise collected half way ("Task was destroyed but it is pending")


async def handle(reader, writer):
    _open.add(writer)
    me = asyncio.current_task()
    _running.add(me)
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
        method, target, pairs = _parse(raw)
        headers = {}
        for key, value in pairs:
            headers[key.lower()] = value
        url = urlsplit(target)
        path, query = url.path or "/", parse_qs(url.query)
        if path == "/__hub/ping":  # says only that this is the hub's preview listener: Health asks it through Tailscale
            return await _reply(writer, "200 OK", f"dream-hub-preview {INSTANCE}".encode())
        if not on():
            return await _reply(writer, "404 Not Found", b"The browser is switched off.")
        host = headers.get("host", "")
        name = host[1:].split("]")[0] if host.startswith("[") else host.rsplit(":", 1)[0]
        if name.lower() not in HOSTNAMES:
            return await _reply(writer, "403 Forbidden", b"Not yours.")
        site, mode = headers.get("sec-fetch-site", ""), headers.get("sec-fetch-mode", "")
        if site == "cross-site" and mode != "navigate" and mode != "websocket":
            return await _reply(writer, "403 Forbidden", b"Not from another site.")
        origin = headers.get("origin", "")
        upgrade = headers.get("upgrade", "").lower() == "websocket"
        if (upgrade or method not in ("GET", "HEAD", "OPTIONS")) and origin and origin not in ORIGINS:
            return await _reply(writer, "403 Forbidden", b"Wrong origin.")
        one = lambda key: query.get(key, [""])[0]
        if path == "/__hub/hello":  # the hub page checks it can reach this listener, and its pass sticks, before it frames anything
            if one("t"):
                if not valid(one("t"), "hello"):
                    return await _reply(writer, "403 Forbidden", b"Not yours.")
                return await _reply(writer, "302 Found", b"", extra=[*_set_cookies(headers), "Location: /__hub/hello?back=1"])
            if not owner(headers):
                return await _reply(writer, "403 Forbidden", b"Not yours.")
            body = (f'<!doctype html><meta charset="utf-8"><script>parent.postMessage({{hubHello: 1}}, {json.dumps(ORIGIN)});</script>').encode()
            return await _reply(writer, "200 OK", body, "text/html; charset=utf-8", (f"Content-Security-Policy: frame-ancestors {ORIGIN}",))
        if path == "/__hub/go":
            port = int(one("port")) if one("port").isdigit() else 0
            if refused_port(port):
                return await _html(writer, "403 Forbidden", "That port isn't shown", "It belongs to the hub itself.")
            if not valid(one("t"), f"go:{port}"):
                return await _html(writer, "403 Forbidden", "This link has run out", "Open the page again from the hub.")
            where = _local_path(one("path"))
            return await _reply(writer, "302 Found", b"", extra=[*_set_cookies(headers, port), f"Location: {where}"])
        if not owner(headers):
            return await _html(writer, "403 Forbidden", "Open this from the hub", "This page shows your dev servers, so it opens only from Dream Hub.")
        if path == "/__hub/frame.js":
            return await _reply(writer, "200 OK", FRAME_JS.encode(), "text/javascript; charset=utf-8")
        entry = re.match(r"^/p/(\d{1,5})(/.*)?$", path)
        if entry:  # typed or pasted into the address bar (no page asked for it), or with a ticket
            port = int(entry[1])
            if refused_port(port):
                return await _html(writer, "403 Forbidden", "That port isn't shown", "It belongs to the hub itself.")
            if site not in ("", "none") and not valid(one("t"), f"go:{port}"):
                return await _html(writer, "403 Forbidden", "Open this from the hub", "A page can't switch the browser to another server.")
            rest = _local_path((entry[2] or "/") + (f"?{url.query}" if url.query and not one("t") else ""))
            return await _reply(writer, "302 Found", b"", extra=[*_set_cookies(headers, port), f"Location: {rest}"])
        port = port_of(headers)
        if port is None:
            return await _html(writer, "404 Not Found", "Pick a page in the hub", "Open the browser in Dream Hub and choose a server.")
        if upgrade:
            return await _websocket(reader, writer, method, target, pairs, headers, port)
        return await _proxy(reader, writer, method, target, pairs, headers, port)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError, asyncio.LimitOverrunError):
        pass
    except Exception as error:  # the details go to the log, not the page
        print(f"error: preview: {type(error).__name__}: {error}", flush=True)
        try:
            await _reply(writer, "500 Internal Server Error", b"Something went wrong.")
        except (ConnectionError, RuntimeError):
            pass
    finally:
        _open.discard(writer)
        _running.discard(me)
        try:
            writer.close()
        except RuntimeError:
            pass


# ── to the dev server and back ──
_family = {}  # port -> the loopback address that answered last


async def _connect(port: int):
    tried = [_family.get(port, "127.0.0.1")]
    tried += [a for a in ("127.0.0.1", "::1") if a not in tried]
    last = None
    for address in tried:
        try:
            pair = await asyncio.wait_for(asyncio.open_connection(address, port, limit=262144), 3)
            _family[port] = address
            return pair
        except (OSError, asyncio.TimeoutError) as error:
            last = error
    raise ConnectionRefusedError(str(last))


def _from_preview(value: str, port: int) -> str:
    """An Origin or Referer of the preview's, as the dev server would see it on localhost."""
    for origin in ORIGINS:
        if value == origin or value.startswith(origin + "/"):
            return f"http://localhost:{port}" + value[len(origin):]
    return value


def _upstream_head(method, target, pairs, port, document=False, websocket=False, chunked=False) -> bytes:
    lines = [f"{method} {target} HTTP/1.1", f"Host: localhost:{port}"]
    for key, value in pairs:
        low = key.lower()
        if low in HOP or low == "host" or low.startswith("tailscale-") or low.startswith("sec-websocket") and not websocket:
            continue
        if low == "cookie":
            value = "; ".join(p.strip() for p in value.split(";") if p.strip() and p.strip().partition("=")[0] not in OURS)
            if not value:
                continue
        elif low in ("origin", "referer"):
            value = _from_preview(value, port)
        elif low == "accept-encoding" and document:
            value = "identity"  # a page comes plain, so the helper can go in
        lines.append(f"{key}: {value}")
    if chunked:
        lines.append("Transfer-Encoding: chunked")
    if websocket:
        lines += ["Connection: Upgrade", "Upgrade: websocket"]
    else:
        lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")


def _location(value: str, port: int) -> str:
    """A redirect to the dev server's own address stays in the preview; one to another port on this Mac goes through a
    ticket the listener signs itself; anything else is left as it is."""
    parts = urlsplit(value)
    if not parts.netloc or (parts.hostname or "").lower() not in LOOPBACK:
        return value
    try:
        there = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return value
    rest = (parts.path or "/") + (f"?{parts.query}" if parts.query else "") + (f"#{parts.fragment}" if parts.fragment else "")
    if there == port:
        return rest
    if refused_port(there):
        return value
    return f"/__hub/go?port={there}&path={quote(rest, safe='')}&t={sign(f'go:{there}', TICKET_TTL)}"


def _set_cookie(value: str):
    """A dev server's cookie, kept to its path and this host; one named like the listener's own is dropped."""
    name = value.split("=", 1)[0].strip()
    if name in OURS:
        return None
    attrs = [a for a in value.split(";") if not a.strip().lower().startswith("domain=")]
    return ";".join(attrs)


def _no_frame_ancestors(value: str):
    kept = [d for d in value.split(";") if d.strip() and not d.strip().lower().startswith("frame-ancestors")]
    return ";".join(kept).strip() or None


async def _pump(src, dst, limit=None):
    """Copy bytes until the end (or `limit` bytes)."""
    left = limit
    while left is None or left > 0:
        data = await src.read(65536 if left is None else min(65536, left))
        if not data:
            break
        if left is not None:
            left -= len(data)
        dst.write(data)
        await dst.drain()


async def _proxy(reader, writer, method, target, pairs, headers, port):
    document = headers.get("sec-fetch-dest", "") in ("document", "iframe") or (not headers.get("sec-fetch-dest") and "text/html" in headers.get("accept", ""))
    try:
        up_r, up_w = await _connect(port)
    except ConnectionRefusedError:
        if document and method == "GET":
            return await _html(writer, "502 Bad Gateway", f"Nothing is running on :{port}", "Start the dev server and this page loads by itself.", refresh=3)
        return await _reply(writer, "502 Bad Gateway", f"Nothing is running on port {port}.".encode())
    sending = None
    try:
        chunked_in = "chunked" in headers.get("transfer-encoding", "").lower()
        up_w.write(_upstream_head(method, target, pairs, port, document=document, chunked=chunked_in))
        size = int(headers.get("content-length", "0") or 0)
        if chunked_in:  # the chunks go through as they came; the dev server reads them
            sending = asyncio.ensure_future(_pump(reader, up_w))
        elif size:
            sending = asyncio.ensure_future(_pump(reader, up_w, size))
        await up_w.drain()
        while True:  # 1xx answers (100 Continue, 103 Early Hints) are the dev server's business, not the browser's
            head = await asyncio.wait_for(up_r.readuntil(b"\r\n\r\n"), 180)
            status_line, *rest = head.decode("latin-1").split("\r\n")
            code = int(status_line.split(" ", 2)[1])
            if not 100 <= code < 200:
                break
        out, kind, encoding, length, chunked = [status_line.replace("HTTP/1.0", "HTTP/1.1", 1)], "", "", None, False
        for line in rest:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key, value, low = key.strip(), value.strip(), key.strip().lower()
            if low == "transfer-encoding":
                chunked = "chunked" in value.lower()
                continue
            if low in HOP or low in ("x-frame-options", "strict-transport-security", "alt-svc"):
                continue
            if low == "content-length":
                length = int(value) if value.isdigit() else None
                continue
            if low == "content-type":
                kind = value.lower()
            elif low == "content-encoding":
                encoding = value.lower()
            elif low == "location":
                value = _location(value, port)
            elif low == "set-cookie":
                value = _set_cookie(value)
            elif low in ("content-security-policy", "content-security-policy-report-only"):
                value = _no_frame_ancestors(value)
            if value is not None:
                out.append(f"{key}: {value}")
        out.append(f"Content-Security-Policy: frame-ancestors 'self' {ORIGIN}")
        no_body = method == "HEAD" or code in (204, 304)
        inject = document and code == 200 and kind.startswith("text/html") and encoding in ("", "identity") and not no_body
        if chunked:
            length = None
        if no_body:
            if length is not None:
                out.append(f"Content-Length: {length}")
        elif inject or length is None:
            out.append("Transfer-Encoding: chunked")
        else:
            out.append(f"Content-Length: {length}")
        out.append("Connection: close")
        writer.write(("\r\n".join(out) + "\r\n\r\n").encode("latin-1"))
        await writer.drain()
        if no_body:
            return
        rechunk = inject or length is None
        pending = b"" if inject else None

        async def send(data: bytes):
            if not data:
                return
            writer.write(f"{len(data):x}\r\n".encode() + data + b"\r\n" if rechunk else data)
            await writer.drain()

        async for data in _body(up_r, chunked, length):
            if pending is not None:
                pending += data
                if len(pending) < 2048:
                    continue
                data, pending = _with_helper(pending), None
            await send(data)
        if pending is not None:
            await send(_with_helper(pending))
        if rechunk:
            writer.write(b"0\r\n\r\n")
            await writer.drain()
    finally:
        if sending:
            sending.cancel()
        up_w.transport.abort()


async def _body(up_r, chunked: bool, length):
    """The dev server's body as it arrives, in pieces of at most 64 KB, without its chunking."""
    if chunked:
        while True:
            size = int((await up_r.readline()).split(b";")[0].strip() or b"0", 16)
            if size == 0:
                while (await up_r.readline()) not in (b"\r\n", b"\n", b""):
                    pass  # trailers
                return
            while size:
                data = await up_r.readexactly(min(65536, size))
                size -= len(data)
                yield data
            await up_r.readexactly(2)
    elif length is not None:
        while length > 0:
            data = await up_r.read(min(65536, length))
            if not data:
                return
            length -= len(data)
            yield data
    else:
        while True:
            data = await up_r.read(65536)
            if not data:
                return
            yield data


def _with_helper(page: bytes) -> bytes:
    """The helper goes after the doctype (before it would put the page in quirks mode), else first."""
    found = re.match(rb"^(\xef\xbb\xbf)?\s*(<!--.*?-->\s*)*<!doctype[^>]*>", page, re.I | re.S)
    at = found.end() if found else 0
    return page[:at] + SNIPPET + page[at:]


async def _websocket(reader, writer, method, target, pairs, headers, port):
    """Hot reload: the upgrade goes to the dev server as if from localhost, then bytes flow both ways untouched."""
    try:
        up_r, up_w = await _connect(port)
    except ConnectionRefusedError:
        return await _reply(writer, "502 Bad Gateway", f"Nothing is running on port {port}.".encode())
    try:
        up_w.write(_upstream_head(method, target, pairs, port, websocket=True))
        await up_w.drain()
        head = await asyncio.wait_for(up_r.readuntil(b"\r\n\r\n"), 30)
        lines = head.decode("latin-1").split("\r\n")
        kept = [line for line in lines[1:] if line and not line.lower().startswith(("set-cookie:", "strict-transport-security:"))]
        writer.write(("\r\n".join([lines[0], *kept]) + "\r\n\r\n").encode("latin-1"))
        await writer.drain()
        ways = [asyncio.ensure_future(_pump(reader, up_w)), asyncio.ensure_future(_pump(up_r, writer))]
        try:
            await asyncio.wait(ways, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for way in ways:
                way.cancel()
    finally:
        up_w.transport.abort()
        writer.transport.abort()


# ── what the hub page asks (GET /api/browser/…, behind the hub's own checks) ──
def info() -> dict:
    return {"port": PREVIEW_PORT, "bases": [PUBLIC] if PUBLIC == LOCAL else [PUBLIC, LOCAL], "ticket": sign("hello", TICKET_TTL),
            "listening": _server is not None, "problem": _bind_error, "command": serve_command(), "local": HOSTNAME in LOOPBACK}


def ticket(port_text: str) -> dict:
    port = int(port_text) if str(port_text).isdigit() else 0
    if refused_port(port):
        raise base.Refused("That port belongs to the hub, so it isn't shown.")
    return {"ticket": sign(f"go:{port}", TICKET_TTL), "port": port}


def probe(port_text: str) -> dict:
    """Whether anything listens on that loopback port now."""
    port = int(port_text) if str(port_text).isdigit() else 0
    if refused_port(port):
        raise base.Refused("That port belongs to the hub, so it isn't shown.")
    for address in ("127.0.0.1", "::1"):
        try:
            socket.create_connection((address, port), 0.6).close()
            return {"port": port, "up": True}
        except OSError:
            continue
    return {"port": port, "up": False}


URL_IN_TEXT = re.compile(r"\bhttps?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])(?::(\d{1,5}))?(/[^\s'\"<>`)\]\\]*)?", re.I)


def urls_in(text: str) -> list:
    """Loopback addresses a session printed, newest first, as localhost, without the hub's own ports."""
    found = []
    for match in URL_IN_TEXT.finditer(text):
        port = int(match[2]) if match[2] else 80
        if refused_port(port):
            continue
        path = (match[3] or "/").rstrip(".,;:!?'\"")
        found.append({"url": f"http://localhost:{port}{path}", "port": port, "path": path})
    seen, out = set(), []
    for item in reversed(found):
        if item["url"] not in seen:
            seen.add(item["url"])
            out.append(item)
    return out[:8]


def printed(sid: str) -> list:
    import hub_data as hub
    if not hub.SESSION_ID.match(sid or ""):
        return []
    text = ""
    path = hub.transcript_of(sid)
    if path is not None:
        try:
            with open(path, "rb") as f:
                f.seek(max(0, path.stat().st_size - 1_500_000))
                text += f.read().decode("utf-8", errors="replace")
        except OSError:
            pass
    target = f"hub-{sid}"
    if target in hub.tmux_sessions():
        text += "\n" + hub.tmux("capture-pane", "-p", "-J", "-S", "-3000", "-t", target).stdout  # the screen last: it is the newest
    return urls_in(text)


_listen_cache = {"at": 0.0, "rows": []}
VERSION_NAME = re.compile(r"^\d+\.\d+\.\d+$")  # Claude Code runs under its version's name; its own ports are no pages
_titles = {}
_probes = concurrent.futures.ThreadPoolExecutor(6, thread_name_prefix="browser-probe")
_listen_lock = threading.Lock()


def _web_title(port: int):
    """(speaks HTTP, the page's title) from a quick GET / on the port; kept for 20 seconds."""
    kept = _titles.get(port)
    if kept and time.time() - kept[0] < 20:
        return kept[1]
    answer = (False, "")
    for address in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((address, port), 0.4) as sock:
                sock.settimeout(0.8)
                sock.sendall(f"GET / HTTP/1.0\r\nHost: localhost:{port}\r\nAccept: text/html\r\nUser-Agent: DreamHub-Browser\r\n\r\n".encode())
                data = b""
                while len(data) < 32768:
                    piece = sock.recv(8192)
                    if not piece:
                        break
                    data += piece
                    if b"</title>" in data.lower():
                        break
            if b"Not yours." in data or b"dream-hub-preview" in data or b"Open this from the hub" in data:
                answer = (False, "")  # another Dream Hub, or its preview: never a page to open here
            elif data.startswith(b"HTTP/"):
                found = re.search(rb"<title[^>]*>([^<]{1,120})</title>", data, re.I)
                answer = (True, re.sub(r"\s+", " ", found[1].decode("utf-8", "replace")).strip() if found else "")
            break
        except OSError:
            continue
    _titles[port] = (time.time(), answer)
    return answer


def _ages(rows: dict) -> dict:
    """Seconds each listening process has run, by pid, from one ps call; an empty map if ps fails."""
    pids = sorted({str(r["pid"]) for r in rows.values() if r.get("pid")})
    if not pids:
        return {}
    try:
        done = subprocess.run(["ps", "-o", "pid=,etime=", "-p", ",".join(pids)], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return {}
    ages = {}
    for line in done.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        days, _, clock = parts[1].rpartition("-")
        units = [int(x) for x in clock.split(":") if x.isdigit()]
        seconds = 0
        for unit in units:
            seconds = seconds * 60 + unit
        ages[int(parts[0])] = seconds + (int(days) * 86400 if days.isdigit() else 0)
    return ages


def listening() -> list:
    """Web servers listening on loopback (or every address), run by this user, from lsof: kept for five seconds."""
    with _listen_lock:
        if time.time() - _listen_cache["at"] < 5:
            return _listen_cache["rows"]
        rows, pid, command = {}, None, ""
        try:
            done = subprocess.run(["lsof", "-nP", "-a", "-u", str(os.getuid()), "-iTCP", "-sTCP:LISTEN", "-Fpcn"], capture_output=True, text=True, timeout=3)
            lines = done.stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            lines = []
        for line in lines:
            if line.startswith("p"):
                pid, command = line[1:], ""
            elif line.startswith("c"):
                command = line[1:]
            elif line.startswith("n"):
                address, _, port = line[1:].rpartition(":")
                if not port.isdigit() or address not in ("*", "127.0.0.1", "[::1]", "localhost", "[::]", "0.0.0.0"):
                    continue
                port = int(port)
                if not refused_port(port) and port not in rows and not VERSION_NAME.match(command) and command.lower() != "claude":
                    rows[port] = {"port": port, "name": command, "pid": int(pid) if pid and pid.isdigit() else None}
        # The youngest processes first (a dev server was most likely just started), at most 24 looked at, shown by port.
        # Age comes from ps, not the pid: pids wrap, so a new server can have a low one.
        ages = _ages(rows)
        ports = sorted(sorted(rows, key=lambda p: ages.get(rows[p]["pid"], 1 << 40))[:24])
        for port, (web, title) in zip(ports, _probes.map(_web_title, ports)):
            rows[port].update(web=web, title=title)
        out = [rows[p] for p in ports if rows[p].get("web")]
        _listen_cache.update(at=time.time(), rows=out)
        return out


_frames = {}  # url -> (at, answer)


def frameable(url: str) -> dict:
    """Whether a public page lets itself be shown inside another: its X-Frame-Options and frame-ancestors, read under
    the link cards' guards (public addresses only, two seconds, no cookies)."""
    import hub_preview as preview
    url = str(url or "").strip()
    if not re.match(r"^https?://", url, re.I) or len(url) > 2048:
        return {"frameable": False, "why": "Only web addresses open here."}
    kept = _frames.get(url)
    if kept and time.time() - kept[0] < 600:
        return kept[1]
    answer = {"frameable": None, "why": ""}
    deadline = time.monotonic() + preview.TIMEOUT
    here = url
    try:
        for _ in range(preview.MAX_HOPS + 1):
            scheme, host, port, path, address = preview.checked_address(here)
            conn = preview._Pinned(host, port, address, max(0.2, deadline - time.monotonic()), scheme == "https")
            try:
                conn.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", host if port in (80, 443) else f"{host}:{port}")
                conn.putheader("User-Agent", preview.AGENT)
                conn.putheader("Accept", "text/html")
                conn.endheaders()
                response = conn.getresponse()
                if response.status in (301, 302, 303, 307, 308) and response.getheader("Location"):
                    from urllib.parse import urljoin
                    here = urljoin(here, response.getheader("Location").strip())
                    continue
                xfo = (response.getheader("X-Frame-Options") or "").strip().lower()
                ancestors = ""
                for value in response.headers.get_all("Content-Security-Policy") or []:
                    for directive in value.split(";"):
                        if directive.strip().lower().startswith("frame-ancestors"):
                            ancestors = directive.strip().lower()
                if xfo in ("deny", "sameorigin") or (ancestors and "*" not in ancestors.split()[1:] and ORIGIN.lower() not in ancestors):
                    answer = {"frameable": False, "why": f"{host} doesn't let other pages show it."}
                else:
                    answer = {"frameable": True, "why": ""}
                break
            finally:
                conn.close()
    except preview.NotFetched as refused:
        answer = {"frameable": None, "why": str(refused)}
    except (OSError, http.client.HTTPException, ssl.SSLError, ValueError):
        answer = {"frameable": None, "why": "That page couldn't be reached."}
    _frames[url] = (time.time(), answer)
    return answer


def route(method: str, parts: list, query: dict) -> dict:
    """GET /api/browser/<what>. None (a 404) while both features are off, as before they existed."""
    if method != "GET" or not on():
        return None
    one = lambda key: query.get(key, [""])[0]
    what = parts[0] if parts else ""
    if what == "info":
        return info()
    if what == "ticket":
        return ticket(one("port"))
    if what == "probe":
        return probe(one("port"))
    if what == "suggest":
        return {"printed": printed(one("sid")), "listening": listening()}
    if what == "frameable":
        return frameable(one("url"))
    return None


# ── what the server's own page uses ──
def frame_sources(security: str) -> str:
    """The hub page's policy, letting it frame the preview's origins and https pages while a feature is on. Unchanged when off."""
    if not on():
        return security
    return security.replace("default-src 'self'; ", f"default-src 'self'; frame-src 'self' {' '.join(ORIGINS)} https:; ", 1)


def refuses(headers: dict) -> bool:
    """A request to the hub's API that came from a page of the preview's (or any page but the hub's own). The hub refuses it."""
    if not on():
        return False
    if headers.get("origin", "") in ORIGINS:
        return True
    return headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none")


# ── Settings › Health ──
def _ping(origin: str) -> bool:
    parts = urlsplit(origin)
    try:
        if parts.scheme == "https":
            conn = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=2.5, context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=2.5)
        conn.request("GET", "/__hub/ping")
        said = conn.getresponse().read(200).decode("utf-8", "replace")
        conn.close()
        return said.strip() == f"dream-hub-preview {INSTANCE}"
    except (OSError, http.client.HTTPException, ssl.SSLError, ValueError):
        return False


def _served() -> bool:
    """Whether `tailscale serve status` lists this port. Read only: the hub never changes Tailscale."""
    for cli in ("tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale"):
        try:
            done = subprocess.run([cli, "serve", "status", "--json"], capture_output=True, text=True, timeout=4, env=base.ENV)
        except (OSError, subprocess.SubprocessError):
            continue
        if done.returncode == 0:
            try:
                data = json.loads(done.stdout or "{}")
            except ValueError:
                return False
            return str(PREVIEW_PORT) in (data.get("TCP") or {}) or any(key.endswith(f":{PREVIEW_PORT}") for key in (data.get("Web") or {}))
    return False


def health_row():
    """One row for Settings › Health while a feature is on: can the person's devices reach the preview."""
    if not on():
        return None
    name = "Browser and preview"
    if _bind_error:
        return {"name": name, "ok": False, "text": f"Port {PREVIEW_PORT} is taken ({_bind_error}), so pages from your dev servers can't be shown.",
                "fix": "Start the hub with HUB_PREVIEW_PORT set to a free port."}
    if HOSTNAME in LOOPBACK:
        return {"name": name, "ok": True, "text": f"Pages from your dev servers open through {PUBLIC}, on this Mac.", "fix": ""}
    if _ping(PUBLIC) or _served():
        return {"name": name, "ok": True, "text": f"Pages from your dev servers open on every device, through port {PREVIEW_PORT}.", "fix": ""}
    return {"name": name, "ok": False, "text": f"Your phone can't open pages from your dev servers yet: port {PREVIEW_PORT} isn't served over Tailscale. This Mac's own browser can. Run the fix once, on the Mac.",
            "fix": serve_command()}
