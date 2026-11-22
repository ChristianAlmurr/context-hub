#!/usr/bin/env python3
"""The preview listener behind the built-in browser and the device preview (hub_browser.py), checked over the wire.

Run: /usr/bin/python3 tests/preview_proxy_check.py
Runs against a second instance (the six HUB_* variables, see tests/instance.py, and HUB_PREVIEW_PORT when the
listener isn't on the hub's port + 1). Starts a tiny dev server on loopback (tests/devserver.py) and checks:
the owner check, tickets, refusal of the hub's own ports and of anything but loopback, proxying (pages, redirects,
cookies, large bodies in both framings, a stream, WebSockets), that the hub's API refuses the preview's origin, the
Health row, and that with both switches off the listener stops and the hub serves exactly what it did before.
Puts the instance's config.json back as it was.
"""
import ast, base64, hashlib, http.client, json, os, socket, struct, sys, time
from pathlib import Path

from instance import CFG, PORT as HUB_PORT, OWNER, WRITE
import hub_base as base
from devserver import BIG, DevServer, free_port

PREVIEW = int(os.environ.get("HUB_PREVIEW_PORT") or HUB_PORT + 1)
PV_HOST = f"127.0.0.1:{PREVIEW}"
PV_ORIGIN = f"http://{PV_HOST}"
LOGIN = {"Tailscale-User-Login": CFG["login"]} if CFG.get("login") else {}
CONFIG = Path(os.path.realpath(base.CONFIG))
failures = 0
# The hub page's Content-Security-Policy as server.py has always sent it (its SECURITY), read from the file itself.
_security = next(node.value for node in ast.parse((Path(__file__).resolve().parent.parent / "server.py").read_text()).body
                 if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SECURITY")
TODAY = ast.literal_eval(_security).split("\r\n")[0].split(": ", 1)[1]


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:600]}]"), flush=True)
    failures += 0 if ok else 1


def hub(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=30)
    c.request(method, path, json.dumps(body) if body is not None else None, headers if headers is not None else (WRITE if method != "GET" else OWNER))
    r = c.getresponse()
    data = r.read()
    try:
        return r.status, json.loads(data), r
    except ValueError:
        return r.status, data, r


def pv(method, path, headers=None, body=None, jar=None):
    """A request to the preview listener, as the owner's browser makes it, with the cookies in `jar`."""
    c = http.client.HTTPConnection("127.0.0.1", PREVIEW, timeout=30)
    sent = {"Host": PV_HOST, **LOGIN, **(headers or {})}
    if jar:
        sent["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items()) + (f"; {sent['Cookie']}" if "Cookie" in sent else "")
    c.request(method, path, body, sent)
    r = c.getresponse()
    data = r.read()
    if jar is not None:
        for key, value in r.getheaders():
            if key.lower() == "set-cookie":
                name, _, rest = value.partition("=")
                jar[name.strip()] = rest.split(";")[0]
    return r.status, data, r


def ticket(port):
    status, data, _ = hub("GET", f"/api/browser/ticket?port={port}")
    return data.get("ticket") if status == 200 else None


def listening(port) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), 0.5).close()
        return True
    except OSError:
        return False


def put(values):
    return hub("PUT", "/api/settings", values)[0]


def websocket(path, origin, jar):
    """Opens a WebSocket through the listener, sends one text frame, returns (status line, echoed text)."""
    s = socket.create_connection(("127.0.0.1", PREVIEW), 5)
    key = base64.b64encode(os.urandom(16)).decode()
    cookies = "; ".join(f"{k}={v}" for k, v in jar.items())
    head = (f"GET {path} HTTP/1.1\r\nHost: {PV_HOST}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            f"Origin: {origin}\r\nCookie: {cookies}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in LOGIN.items()) + "\r\n")
    s.sendall(head.encode())
    got = b""
    while b"\r\n\r\n" not in got:
        piece = s.recv(4096)
        if not piece:
            break
        got += piece
    line = got.split(b"\r\n", 1)[0].decode()
    if " 101 " not in line:
        s.close()
        return line, None
    payload, mask = b"hot reload", os.urandom(4)
    s.sendall(bytes([0x81, 0x80 | len(payload)]) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
    rest = got.split(b"\r\n\r\n", 1)[1]
    while len(rest) < 2 + len(payload):
        rest += s.recv(4096)
    s.close()
    return line, rest[2:2 + rest[1]].decode()


as_found = CONFIG.read_bytes()
dev = DevServer(hub_port=HUB_PORT)
other = DevServer(hub_port=HUB_PORT, port=dev.other)  # the port a redirect sends to
try:
    put({"feature_browser": True, "feature_preview": True})
    time.sleep(0.3)
    # ── the listener and who may use it ──
    check("the preview listener is up while the browser is on", listening(PREVIEW))
    status, data, _ = pv("GET", "/__hub/ping", headers={"Tailscale-User-Login": ""})
    check("it answers a ping, saying only what it is", status == 200 and data.startswith(b"dream-hub-preview "), data)
    status, data, _ = hub("GET", "/api/browser/info")
    check("the hub says where the preview is", status == 200 and data["port"] == PREVIEW and data["listening"] and PV_ORIGIN in data["bases"] and data["command"] == f"tailscale serve --bg --https={PREVIEW} http://127.0.0.1:{PREVIEW}", data)
    status, _, _ = hub("GET", "/api/browser/info", headers={"Host": OWNER["Host"]})
    check("and only to the owner", status == 403)
    status, _, _ = pv("GET", "/", headers={"Tailscale-User-Login": "someone-else@example.com"})
    check("the listener turns away anyone but the owner", status == 403)
    status, _, _ = pv("GET", "/", headers={"Host": f"evil.example:{PREVIEW}"})
    check("and a request for another host (a rebound name)", status == 403)
    status, _, _ = pv("GET", f"/__hub/go?port={dev.port}&path=/&t=1.abc")
    check("a made-up ticket opens nothing", status == 403)
    status, _, _ = pv("GET", f"/__hub/go?port={dev.port}&path=/&t={ticket(other.port)}")
    check("a ticket for another port opens nothing", status == 403)
    for port, what in ((HUB_PORT, "the hub's own port"), (PREVIEW, "the listener's own port"), (base.INSTALLED["port"], "the installed hub's port"), (0, "port 0"), (70000, "a port past 65535")):
        status, data, _ = hub("GET", f"/api/browser/ticket?port={port}")
        status2, _, _ = pv("GET", f"/p/{port}/")
        check(f"{what} is refused: no ticket, and no way in through the bar", status == 409 and status2 in (403, 404), (status, data, status2))
    status, _, _ = pv("GET", f"/__hub/go?port={HUB_PORT}&path=/&t={ticket(dev.port)}")
    check("a ticket can't be turned on the hub's own port", status == 403)

    # ── into a page ──
    jar = {}
    status, data, r = pv("GET", f"/__hub/go?port={dev.port}&path=/&t={ticket(dev.port)}", jar=jar)
    check("a ticket sets the pass and the port, and goes to the page at the root", status == 302 and r.getheader("Location") == "/" and "__hub_pv" in jar and jar.get("__hub_port", "").startswith(f"{dev.port}-"), (status, r.getheaders()))
    cookies = [v for k, v in r.getheaders() if k.lower() == "set-cookie"]
    check("both cookies are HttpOnly, so a page can't read or change them", cookies and all("HttpOnly" in c for c in cookies), cookies)
    status, data, r = pv("GET", "/__hub/go?port=%d&path=//evil.example/&t=%s" % (dev.port, ticket(dev.port)), jar=dict(jar))
    check("a path that would leave the preview goes to / instead", status == 302 and r.getheader("Location") == "/", r.getheader("Location"))
    status, data, r = pv("GET", "/__hub/go?port=%d&path=/a%%0d%%0aSet-Cookie:%%20x=1&t=%s" % (dev.port, ticket(dev.port)), jar=dict(jar))
    check("a path can't add a header of its own", status == 302 and r.getheader("Location") == "/a%0D%0ASet-Cookie:%20x=1" and not any(v.startswith("x=1") for k, v in r.getheaders() if k.lower() == "set-cookie"), r.getheaders())
    status, data, r = pv("GET", "/p/%d//evil.example/x" % dev.port, headers={"Sec-Fetch-Site": "none"}, jar=dict(jar))
    check("nor can an address typed into the bar lead off the preview", status == 302 and r.getheader("Location") == "/", r.getheader("Location"))
    status, data, r = pv("GET", "/", headers={"Sec-Fetch-Dest": "iframe", "Accept": "text/html"}, jar=dict(jar))
    text = data.decode()
    check("the page comes through, at the root", status == 200 and "Lab page" in text, text[:200])
    check("with the helper after the doctype, so the page stays in standards mode", text.lower().startswith("<!doctype html>\n") is False and text.lower().startswith("<!doctype html><script src=\"/__hub/frame.js\"") and f'data-hub="{CFG["origin"]}"' in text, text[:160])
    check("and it may only be framed by the hub", f"frame-ancestors 'self' {CFG['origin']}" in (r.getheader("Content-Security-Policy") or ""), r.getheaders())
    status, data, _ = pv("GET", "/quirks", headers={"Sec-Fetch-Dest": "document"}, jar=dict(jar))
    check("a doctype after a comment still comes first", data.startswith(b"<!-- a comment first -->\n<!DOCTYPE html><script src=\"/__hub/frame.js\""), data[:120])
    status, data, r = pv("GET", "/gz", headers={"Sec-Fetch-Dest": "document", "Accept-Encoding": "gzip"}, jar=dict(jar))
    seen = dev.seen[-1]["headers"]
    check("a page is asked for plain, so the helper can go in", seen.get("accept-encoding") == "identity", seen)
    check("a page that comes packed anyway passes through untouched", status == 200 and r.getheader("Content-Encoding") == "gzip" and b"frame.js" not in data, r.getheaders())
    status, data, r = pv("GET", "/app.js", headers={"Sec-Fetch-Dest": "script"}, jar=dict(jar))
    check("a script isn't touched", b"frame.js" not in data)
    status, data, r = pv("GET", "/__hub/frame.js", jar=dict(jar))
    check("the helper is served by the listener itself", status == 200 and b"hubFrame" in data and "javascript" in r.getheader("Content-Type"))

    # ── what goes to the dev server ──
    status, data, _ = pv("GET", "/headers", headers={"Cookie": "mine=1; hub_key=secret", "Origin": PV_ORIGIN, "Referer": f"{PV_ORIGIN}/somewhere"}, jar=dict(jar))
    told = json.loads(data)
    check("the dev server is asked as localhost on its own port", told.get("host") == f"localhost:{dev.port}", told)
    check("it never gets the hub's cookies or the owner's login", "__hub_pv" not in told.get("cookie", "") and "__hub_port" not in told.get("cookie", "") and "hub_key" not in told.get("cookie", "")
          and told.get("cookie") == "mine=1" and "tailscale-user-login" not in told, told)
    check("the preview's Origin and Referer reach it as its own", told.get("origin") == f"http://localhost:{dev.port}" and told.get("referer") == f"http://localhost:{dev.port}/somewhere", told)

    # ── what comes back ──
    status, _, r = pv("GET", "/redirect", jar=dict(jar))
    check("a redirect to its own address stays in the preview", status == 302 and r.getheader("Location") == "/next", r.getheader("Location"))
    status, _, r = pv("GET", "/redirect-other", jar=dict(jar))
    where = r.getheader("Location") or ""
    check("a redirect to another port on this Mac goes through a fresh ticket", where.startswith(f"/__hub/go?port={dev.other}&path=%2Fx%3Fy%3D1&t="), where)
    status, _, r2 = pv("GET", where, jar=dict(jar))
    check("which works", status == 302 and r2.getheader("Location") == "/x?y=1", (status, r2.getheaders()))
    status, _, r = pv("GET", "/redirect-hub", jar=dict(jar))
    check("a redirect to the hub's own port is left as it is, so it leads nowhere", r.getheader("Location") == f"http://localhost:{HUB_PORT}/", r.getheader("Location"))
    status, _, r = pv("GET", "/redirect-away", jar=dict(jar))
    check("a redirect off this Mac is left as it is", r.getheader("Location") == "https://example.com/somewhere")
    status, _, r = pv("GET", "/cookie", jar=dict(jar))
    cookies = [v for k, v in r.getheaders() if k.lower() == "set-cookie"]
    check("a dev server's cookie keeps its path and loses its Domain", "sid=abc; Path=/app; HttpOnly" in [c.replace("; ", ";").replace(";", "; ") for c in cookies] or any(c.startswith("sid=abc") and "Domain" not in c and "Path=/app" in c for c in cookies), cookies)
    check("and it can't set the listener's own", not any(c.startswith("__hub_port") for c in cookies) and any(c.startswith("plain=1") for c in cookies), cookies)
    status, data, r = pv("GET", "/framing", headers={"Sec-Fetch-Dest": "iframe"}, jar=dict(jar))
    policies = [v for k, v in r.getheaders() if k.lower() == "content-security-policy"]
    check("a dev server's refusal to be framed is lifted for the hub only", r.getheader("X-Frame-Options") is None and all("'none'" not in p for p in policies) and any(f"frame-ancestors 'self' {CFG['origin']}" in p for p in policies)
          and any("default-src 'self'" in p for p in policies), r.getheaders())
    status, data, r = pv("GET", "/big", jar=dict(jar))
    check("8 MB in chunks comes through whole", status == 200 and hashlib.sha256(data).digest() == hashlib.sha256(BIG).digest(), len(data))
    status, data, r = pv("GET", "/big-cl", jar=dict(jar))
    check("8 MB with a length comes through whole, with its length", status == 200 and data == BIG and r.getheader("Content-Length") == str(len(BIG)), len(data))
    status, data, r = pv("POST", "/echo", headers={"Content-Type": "application/octet-stream", "Origin": PV_ORIGIN}, body=BIG[:3_000_000], jar=dict(jar))
    check("a large upload reaches the dev server whole", status == 200 and data == BIG[:3_000_000], len(data))
    c = http.client.HTTPConnection("127.0.0.1", PREVIEW, timeout=30)
    c.putrequest("POST", "/echo", skip_host=True)
    for k, v in {"Host": PV_HOST, **LOGIN, "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items()), "Transfer-Encoding": "chunked", "Origin": PV_ORIGIN}.items():
        c.putheader(k, v)
    c.endheaders()
    c.send(b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n")
    r = c.getresponse()
    check("a chunked upload too", r.read() == b"hello world")
    s = socket.create_connection(("127.0.0.1", PREVIEW), 10)
    s.sendall((f"GET /sse HTTP/1.1\r\nHost: {PV_HOST}\r\nCookie: {'; '.join(f'{k}={v}' for k, v in jar.items())}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in LOGIN.items()) + "\r\n").encode())
    started, got, early = time.monotonic(), b"", None
    while True:
        piece = s.recv(4096)
        if not piece:
            break
        got += piece
        if early is None and b"data: 0" in got:
            early, first = time.monotonic() - started, b"data: 0"
    s.close()
    first, rest = (b"data: 0" if early is not None else b""), got
    check("a stream is passed on as it comes, not when it ends", first.startswith(b"data: 0") and early < 1.0 and b"data: 3" in rest, (first, early, rest[-300:]))
    line, echoed = websocket("/ws?token=x", PV_ORIGIN, jar)
    check("a WebSocket (hot reload) goes through and echoes", " 101 " in line and echoed == "hot reload", (line, echoed))
    check("and the dev server sees it come from its own origin", dev.ws_origins and dev.ws_origins[-1] == f"http://localhost:{dev.port}", dev.ws_origins)
    line, _ = websocket("/ws", "https://evil.example", jar)
    check("a WebSocket from another site is refused", " 403 " in line, line)
    status, _, _ = pv("POST", "/echo", headers={"Origin": "https://evil.example", "Content-Type": "text/plain"}, body=b"x", jar=dict(jar))
    check("a write from another site is refused", status == 403)
    status, _, _ = pv("GET", "/", headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}, jar=dict(jar))
    check("another site can't pull from the preview", status == 403)
    status, _, _ = pv("GET", f"/p/{other.port}/", headers={"Sec-Fetch-Site": "same-origin"}, jar=dict(jar))
    check("a page can't move the preview to another port", status == 403)
    status, _, r = pv("GET", f"/p/{other.port}/x?q=1", headers={"Sec-Fetch-Site": "none"}, jar=dict(jar))
    check("an address typed into the bar can", status == 302 and r.getheader("Location") == "/x?q=1" and f"__hub_port={other.port}-" in r.getheader("Set-Cookie", ""), r.getheaders())
    nothing = free_port()
    status, _, _ = hub("GET", f"/api/browser/probe?port={nothing}")
    status2, data, r = pv("GET", "/", headers={"Sec-Fetch-Dest": "document"}, jar={**jar, "__hub_port": f"{nothing}-{ticket(nothing)}"})
    check("a port cookie the listener didn't sign is ignored", status2 == 404, status2)
    jar2 = {}
    pv("GET", f"/__hub/go?port={nothing}&path=/&t={ticket(nothing)}", jar=jar2)
    status, data, r = pv("GET", "/", headers={"Sec-Fetch-Dest": "iframe"}, jar=jar2)
    check("a server that isn't running gives a small page that tries again", status == 502 and b"Nothing is running on :%d" % nothing in data and b'http-equiv="refresh"' in data, data[:200])
    check("the probe says so first", hub("GET", f"/api/browser/probe?port={nothing}")[1] == {"port": nothing, "up": False} and hub("GET", f"/api/browser/probe?port={dev.port}")[1]["up"] is True)

    # ── the hub's API refuses the preview's origin ──
    status, data, _ = hub("PUT", "/api/settings", {"theme": "light"}, {**WRITE, "Origin": PV_ORIGIN})
    check("a write from the preview's origin is refused by the hub", status == 403, data)
    status, _, _ = hub("GET", "/api/state", headers={**OWNER, "Origin": PV_ORIGIN})
    check("so is a read", status == 403)
    status, _, _ = hub("GET", "/api/state", headers={**OWNER, "Sec-Fetch-Site": "same-site"})
    check("and a read from any page of another port (same-site), Origin or not", status == 403)
    status, _, _ = hub("GET", "/api/state")
    check("while the hub's own page still reads", status == 200)
    s = socket.create_connection(("127.0.0.1", HUB_PORT), 5)
    s.sendall((f"GET /ws/term/abcdef12 HTTP/1.1\r\nHost: {OWNER['Host']}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {base64.b64encode(os.urandom(16)).decode()}\r\n"
               f"Sec-WebSocket-Version: 13\r\nOrigin: {PV_ORIGIN}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in LOGIN.items()) + "\r\n").encode())
    answer = s.recv(200)
    s.close()
    check("and a terminal can't be opened from it", b" 403 " in answer.split(b"\r\n")[0], answer[:80])

    # ── Health ──
    status, data, _ = hub("GET", "/api/settings/health?fresh=1")
    row = next((p for p in data.get("parts", []) if p["name"] == "Browser and preview"), None)
    check("Health has a row for the preview, fine on a loopback hub", row and row["ok"] is True and PV_ORIGIN in row["text"], row)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import hub_browser
    hub_browser.HOSTNAME, hub_browser.PUBLIC, hub_browser._served = "hub.example.invalid", f"https://hub.example.invalid:{PREVIEW}", lambda: False
    row = hub_browser.health_row()
    check("behind Tailscale with no mapping, Health says so and gives the one command, built from config", row and row["ok"] is False and row["fix"] == f"tailscale serve --bg --https={PREVIEW} http://127.0.0.1:{PREVIEW}" and "phone" in row["text"], row)

    # ── off is today's hub ──
    status, _, r = hub("GET", "/", headers={**OWNER})
    on_policy = r.getheader("Content-Security-Policy")
    check("on, the hub's page may frame the preview", f"frame-src 'self' {PV_ORIGIN}" in on_policy, on_policy)
    check("both switches off", put({"feature_browser": False, "feature_preview": False}) == 200)
    gone = next((True for _ in range(20) if not listening(PREVIEW) or time.sleep(0.2)), False)
    check("the listener stops listening", gone)
    status, _, r = hub("GET", "/", headers={**OWNER})
    check("the hub's page has today's policy again, word for word", r.getheader("Content-Security-Policy") == TODAY, r.getheader("Content-Security-Policy"))
    check("and its API for the browser is gone", hub("GET", "/api/browser/info")[0] == 404 and hub("GET", f"/api/browser/ticket?port={dev.port}")[0] == 404)
    status, _, _ = hub("GET", "/api/state", headers={**OWNER, "Sec-Fetch-Site": "same-site"})
    check("and the API answers as it did before (no new refusal)", status == 200)
    check("Health has no preview row", not any(p["name"] == "Browser and preview" for p in hub("GET", "/api/settings/health?fresh=1")[1]["parts"]))
    check("the device preview alone brings the listener back", put({"feature_preview": True}) == 200 and next((True for _ in range(20) if listening(PREVIEW) or time.sleep(0.2)), False))
finally:
    CONFIG.write_bytes(as_found)
    dev.stop()
    other.stop()

print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
