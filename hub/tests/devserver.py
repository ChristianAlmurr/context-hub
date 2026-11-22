"""A tiny dev server on loopback, standing in for Vite or Next in the browser checks: pages, redirects, cookies, a
large body in both framings, a server-sent stream, a WebSocket echo (hot reload's shape), and a page that tries to
reach the hub's API from inside the preview and writes down what happened.

    server = DevServer(); server.port; server.seen (what it was asked); server.reports (what pages told it); server.stop()
"""
import base64, gzip, hashlib, http.server, json, socket, socketserver, struct, threading, time
from urllib.parse import parse_qs, urlsplit

BIG = bytes(range(256)) * (8 * 1024 * 1024 // 256)  # 8 MB that a cut or a reorder would show
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>body {{ font: 16px/1.5 -apple-system, system-ui, sans-serif; margin: 0; padding: 24px; background: #fdfcf8; color: #1d2433; }}
h1 {{ font-size: 28px; margin: 0 0 8px; }} .card {{ padding: 16px; border-radius: 12px; background: #eef1f8; margin-top: 16px; }}
nav a {{ margin-right: 12px; color: #2f5ff0; }} @media (max-width: 500px) {{ h1 {{ font-size: 22px; }} }}</style></head>
<body><nav><a id="home" href="/">Home</a><a id="next" href="/next">Next</a></nav><h1>{title}</h1>
<p>A page from a dev server on this Mac, shown through the hub's preview.</p><div class="card">Width: <b id="w"></b></div>
<script>document.getElementById("w").textContent = innerWidth + " px";</script>{extra}</body></html>"""

ATTACK = """<script>
(async () => {
  const hub = new URLSearchParams(location.search).get("hub");
  const out = {};
  const tryIt = async (name, make) => { try { const r = await make(); out[name] = "status " + r.status; } catch (e) { out[name] = "blocked"; } };
  await tryIt("read_state", () => fetch(hub + "/api/state", { credentials: "include" }));
  await tryIt("read_state_nocors", () => fetch(hub + "/api/state", { credentials: "include", mode: "no-cors" }).then((r) => ({ status: r.type })));
  await tryIt("write", () => fetch(hub + "/api/settings", { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ theme: "light" }) }));
  await new Promise((done) => { try { const ws = new WebSocket(hub.replace(/^http/, "ws") + "/ws/term/abcdef12"); ws.onopen = () => { out.terminal = "open"; done(); }; ws.onerror = () => { out.terminal = "refused"; done(); }; setTimeout(done, 3000); } catch (e) { out.terminal = "refused"; done(); } });
  try { out.top = String(window.top.location.href); } catch (e) { out.top = "blocked"; }
  await fetch("/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(out) });
})();
</script>"""


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def send(self, status, body=b"", kind="text/html; charset=utf-8", headers=()):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def chunked(self, pieces, kind="application/octet-stream", pause=0.0):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for piece in pieces:
            self.wfile.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
            self.wfile.flush()
            if pause:
                time.sleep(pause)
        self.wfile.write(b"0\r\n\r\n")

    def body(self):
        if "chunked" in self.headers.get("Transfer-Encoding", ""):
            data = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0], 16)
                if not size:
                    self.rfile.readline()
                    return data
                data += self.rfile.read(size)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        server = self.server.owner
        url = urlsplit(self.path)
        server.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
        if self.headers.get("Upgrade", "").lower() == "websocket" and url.path == "/ws":
            return self.websocket()
        if url.path == "/":
            return self.send(200, PAGE.format(title="Lab page", extra="").encode())
        if url.path == "/next":
            return self.send(200, PAGE.format(title="Next page", extra="").encode())
        if url.path == "/attack":
            return self.send(200, PAGE.format(title="Attack page", extra=ATTACK).encode())
        if url.path == "/redirect":
            return self.send(302, headers=[("Location", f"http://localhost:{server.port}/next")])
        if url.path == "/redirect-other":
            return self.send(302, headers=[("Location", f"http://127.0.0.1:{server.other}/x?y=1")])
        if url.path == "/redirect-hub":
            return self.send(302, headers=[("Location", f"http://localhost:{server.hub_port}/")])
        if url.path == "/redirect-away":
            return self.send(302, headers=[("Location", "https://example.com/somewhere")])
        if url.path == "/cookie":
            return self.send(200, b"ok", "text/plain", [("Set-Cookie", "sid=abc; Domain=localhost; Path=/app; HttpOnly"), ("Set-Cookie", "__hub_port=1; Path=/"), ("Set-Cookie", "plain=1")])
        if url.path == "/headers":
            return self.send(200, json.dumps({k.lower(): v for k, v in self.headers.items()}).encode(), "application/json")
        if url.path == "/big":
            return self.chunked([BIG[i:i + 100_000] for i in range(0, len(BIG), 100_000)])
        if url.path == "/big-cl":
            return self.send(200, BIG, "application/octet-stream")
        if url.path == "/sse":
            return self.chunked([f"data: {n}\n\n".encode() for n in range(4)], "text/event-stream", pause=0.4)
        if url.path == "/framing":
            return self.send(200, PAGE.format(title="Framing", extra="").encode(), headers=[("X-Frame-Options", "DENY"), ("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; frame-ancestors 'none'")])
        if url.path == "/gz":
            return self.send(200, gzip.compress(PAGE.format(title="Packed", extra="").encode()), headers=[("Content-Encoding", "gzip")])
        if url.path == "/quirks":
            return self.send(200, b"<!-- a comment first -->\n<!DOCTYPE html><title>Q</title><p>q</p>")
        self.send(404, b"not here", "text/plain")

    def do_POST(self):
        server = self.server.owner
        data = self.body()
        server.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": data})
        if self.path == "/report":
            server.reports.append(json.loads(data or b"{}"))
            return self.send(200, b"{}", "application/json")
        self.send(200, data, "application/octet-stream")

    def websocket(self):
        key = self.headers.get("Sec-WebSocket-Key", "")
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        self.server.owner.ws_origins.append(self.headers.get("Origin", ""))
        self.wfile.write(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode())
        self.wfile.flush()
        sock = self.connection
        while True:
            head = sock.recv(2)
            if len(head) < 2:
                return
            opcode, size = head[0] & 0x0F, head[1] & 0x7F
            if size == 126:
                size = struct.unpack(">H", sock.recv(2))[0]
            mask = sock.recv(4)
            payload = b""
            while len(payload) < size:
                payload += sock.recv(size - len(payload))
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 8:
                return
            sock.sendall(bytes([0x80 | opcode, len(payload)]) + payload)


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class DevServer:
    def __init__(self, hub_port=0, port=0):
        self.seen, self.reports, self.ws_origins = [], [], []
        self.hub_port = hub_port
        self.httpd = _Server(("127.0.0.1", port), Handler)
        self.httpd.owner = self
        self.port = self.httpd.server_address[1]
        self.other = free_port()
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
