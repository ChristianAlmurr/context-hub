#!/usr/bin/env python3
"""Live state and smooth terminals, end to end: the server's state loop and its stream, the page that follows it, and
the terminal's renderer, write batching, parking and copy feedback.

- The screen cache, in process: a pane that printed nothing is not captured again, and one that printed always is,
  even when it printed in the same second as the last capture.
- GET /api/stream: refused without the owner, then the whole state once, then only what changed. A session started
  arrives as a diff within a second, a rename too, and the rows the stream gives add up to what /api/state says.
- The page: it follows the stream and its 3-second poll rests; a stream closed under it comes back on its own.
- Terminals: the DOM renderer without WebGL (and the WebGL one with it), output written once a frame, sockets let
  go in a tab hidden for a while and connected again on return, and "Copied" when tmux copies through OSC 52.

Plain terminals only (no Claude), in a throwaway project, hub-test-throwaway-<n>, made here and removed at the end.
Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/push_check.py [folder-for-screenshots]
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, threading, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, OWNER, TMUX, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hub_data as hub
import hub_push as push

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-push.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE if body is not None else OWNER)
    return json.loads(c.getresponse().read() or b"{}")


def waited(test, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.1)
    return None


class Stream:
    """GET /api/stream read in the background: each event, with the time it came."""

    def __init__(self, headers=OWNER):
        self.s = socket.create_connection(("127.0.0.1", HUB_PORT), timeout=60)
        self.s.sendall(("GET /api/stream HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n").encode())
        self.file = self.s.makefile("rb")
        self.status = self.file.readline().decode().strip()
        self.head = {}
        while True:
            line = self.file.readline().decode().strip()
            if not line:
                break
            key, _, value = line.partition(":")
            self.head[key.strip().lower()] = value.strip()
        self.events, self.retry = [], None
        if self.status.endswith("200 OK"):
            threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        kind = None
        try:
            for raw in self.file:
                line = raw.decode().rstrip("\n")
                if line.startswith("retry: "):
                    self.retry = int(line[7:])
                elif line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    self.events.append((kind, json.loads(line[6:]), time.time()))
        except (OSError, ValueError):
            pass

    def state(self):
        """The state as a page would build it from the events so far, or None if a step is missing."""
        base, seq = None, None
        for kind, data, _ in list(self.events):
            if kind == "full":
                base, seq = json.loads(json.dumps(data["state"])), data["seq"]
            elif kind == "diff" and base is not None:
                if data["base"] != seq:
                    return None
                rows = {s["id"]: s for s in base["sessions"]}
                rows.update({s["id"]: s for s in data["rows"]})
                for sid in data["gone"]:
                    rows.pop(sid, None)
                base["sessions"] = [rows[sid] for sid in (data["order"] or [s["id"] for s in base["sessions"]]) if sid in rows]
                base.update(data["set"])
                for key in data["unset"]:
                    base.pop(key, None)
                base["at"], seq = data["at"], data["seq"]
        return base

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


class CDP:
    def __init__(self, url):
        rest = url.split("//")[1]
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        data = b""
        while b"\r\n\r\n" not in data:
            data += self.s.recv(4096)
        self.buffer, self.n, self.errors = data.split(b"\r\n\r\n", 1)[1], 0, []

    def _read(self, n):
        while len(self.buffer) < n:
            chunk = self.s.recv(1 << 20)
            if not chunk:
                raise ConnectionError
            self.buffer += chunk
        out, self.buffer = self.buffer[:n], self.buffer[n:]
        return out

    def recv(self):
        data = b""
        while True:
            a, b = self._read(2)
            size = b & 0x7F
            if size == 126:
                size = struct.unpack(">H", self._read(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self._read(8))[0]
            data += self._read(size)
            if a & 0x80:
                return json.loads(data)

    def call(self, method, **params):
        self.n += 1
        payload, mask = json.dumps({"id": self.n, "method": method, "params": params}).encode(), os.urandom(4)
        size = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | size]) if size < 126 else bytes([0x80 | 126]) + struct.pack(">H", size) if size < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", size))
        self.s.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))
        while True:
            message = self.recv()
            if message.get("id") == self.n:
                return message.get("result", {})
            if message.get("method") == "Runtime.exceptionThrown":
                self.errors.append(message["params"]["exceptionDetails"].get("text", "") + " " + str(message["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:200])

    def js(self, expression):
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def shot(self, name):
        (OUT / f"{name}.png").write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))


def browser(*flags):
    """A headless Chrome and a page on the hub, as Tailscale Serve would let it in."""
    profile = tempfile.mkdtemp(prefix="hub-chrome.")
    chrome = subprocess.Popen([CHROME, "--headless=new", *flags, f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tabs = waited(lambda: (lambda: json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")))() if _up() else None, 20)
    c = CDP(next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"])
    c.call("Runtime.enable")
    c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})  # what Tailscale Serve adds on the way in
    c.call("Browser.grantPermissions", origin=CFG["origin"], permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)  # the clipboard takes writes only from a focused page
    return chrome, profile, c


def _up():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
        return True
    except OSError:
        return False


def screen_text(c):
    """What the first terminal shows, read from its buffer: the same whichever renderer draws it."""
    return c.js("(() => { const t = [...liveTerms][0]; if (!t) return ''; const b = t.term.buffer.active; const out = []; for (let i = 0; i < t.term.rows; i++) out.push(b.getLine(b.viewportY + i).translateToString(true)); return out.join('\\n'); })()") or ""


sweep()
launchd_before = launchd_jobs()
ids, procs = [], []
try:
    # ── the screen cache, in this process, on this instance's tmux ──
    target = f"hub-push-check-{os.getpid()}"
    subprocess.run(TMUX + ["new-session", "-d", "-s", target, "-x", "80", "-y", "10", "exec /bin/cat"], check=True)
    try:
        captures = []
        plain = push._plain_pane
        push._plain_pane = lambda t, *a, **k: (captures.append(t), plain(t, *a, **k))[1]
        push._here.on = True
        try:
            waited(lambda: push._probe() and time.time() - push._activity.get(target, time.time()) >= 1.1, 5)  # its first output's second has passed
            first = push._pane(target)
            again = push._pane(target)
            check("a pane that printed nothing since its capture is not captured again", len(captures) == 1 and again == first, captures)
            subprocess.run(TMUX + ["send-keys", "-t", target, "-l", "fresh words"])
            time.sleep(0.15)
            push._probe()
            now = push._pane(target)
            check("a pane that printed is captured again, with what it printed", len(captures) == 2 and "fresh words" in now, [len(captures), now[:80]])
            # More output in the same second as that capture: the second must end before a capture is trusted again.
            # More output, likely in the same second as that capture: once that second is over, the pane is taken again.
            subprocess.run(TMUX + ["send-keys", "-t", target, "-l", " and more"])
            later = waited(lambda: (push._probe(), "and more" in push._pane(target))[1], 4)
            check("output in the same second as a capture is never missed", bool(later), push._pane(target)[:80])
        finally:
            push._here.on = False
            push._plain_pane = plain
    finally:
        subprocess.run(TMUX + ["kill-session", "-t", target], capture_output=True)

    # ── the stream ──
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    stranger = Stream({"Host": OWNER["Host"]})
    check("the stream is refused to anyone but the owner", stranger.status.split(" ", 1)[1].startswith("403"), stranger.status)
    stranger.close()
    feed = Stream()
    check("the stream answers as Server-Sent Events, never cached", feed.status.endswith("200 OK") and feed.head.get("content-type") == "text/event-stream" and feed.head.get("cache-control") == "no-store", [feed.status, feed.head])
    full = waited(lambda: next((d for k, d, _ in feed.events if k == "full"), None), 10)
    polled = api("GET", "/api/state")
    check("it starts with the whole state, the same shape /api/state has", bool(full) and set(full["state"]) == set(polled) and isinstance(full["seq"], int), [sorted((full or {}).get("state", {})), sorted(polled)])
    check("the browser is told to wait 2 seconds before it reconnects", feed.retry == 2000, feed.retry)
    count = len(feed.events)
    asked = time.time()
    sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
    ids.append(sid)
    arrived = waited(lambda: next((t for k, d, t in feed.events[count:] if k == "diff" and any(r["id"] == sid for r in d["rows"])), None), 5)
    check("a session started reaches the stream within a second", bool(arrived) and arrived - asked < 1.0, arrived and round(arrived - asked, 2))
    diff = next((d for k, d, _ in feed.events[count:] if k == "diff" and any(r["id"] == sid for r in d["rows"])), {})
    check("a diff carries the rows that changed, not the whole list", [r["id"] for r in diff.get("rows", [])] == [sid] and diff.get("order") and sid in diff["order"], {k: (v if k != "rows" else [r["id"] for r in v]) for k, v in diff.items() if k != "set"})
    count, asked = len(feed.events), time.time()
    api("POST", f"/api/sessions/{sid}/rename", {"title": "Renamed by the push check"})
    renamed = waited(lambda: next((t for k, d, t in feed.events[count:] if k == "diff" and any(r["id"] == sid and r["title"].endswith("Renamed by the push check") for r in d["rows"])), None), 5)
    check("a rename reaches the stream within a second", bool(renamed) and renamed - asked < 1.0, renamed and round(renamed - asked, 2))
    row = next((s for s in api("GET", "/api/state")["sessions"] if s["id"] == sid), {})
    check("/api/state shows a write at once, as it did before", row.get("title", "").endswith("Renamed by the push check"), row.get("title"))
    time.sleep(2.5)
    built, polled = feed.state(), api("GET", "/api/state")
    same = lambda a, b: [(s["id"], s["state"], s["title"]) for s in a["sessions"]] == [(s["id"], s["state"], s["title"]) for s in b["sessions"]]
    check("the rows the stream gave add up to what /api/state says", bool(built) and same(built, polled), [built and len(built["sessions"]), len(polled["sessions"])])
    check("projects come through the stream too", bool(built) and NAME in [p["name"] for p in built["projects"]])
    pings = waited(lambda: [d for k, d, _ in feed.events if k == "ping"], 12)
    last = [d["seq"] for k, d, _ in feed.events if k in ("full", "diff")][-1]
    check("a quiet stream still hears from the server every 10 seconds, with the step it is at", bool(pings) and pings[-1]["seq"] >= last, [pings[-1:] if pings else None, last])
    feed.close()

    # ── the page ──
    chrome, profile, c = browser("--disable-gpu")
    procs.append((chrome, profile))
    c.call("Page.navigate", url=CFG["origin"] + f"/#/s/{sid}")
    live = waited(lambda: c.js("pushLive() && [...liveTerms].length === 1 && liveTerms.values().next().value.link === 'open'"), 20)
    check("the page follows the stream, with the terminal open", bool(live))
    before = c.js("performance.getEntriesByType('resource').filter(e => e.name.endsWith('/api/state')).length")
    time.sleep(7)
    after = c.js("performance.getEntriesByType('resource').filter(e => e.name.endsWith('/api/state')).length")
    check("while the stream is live the poll only checks on it, every other turn", after - before <= 2, [before, after])
    api("POST", f"/api/sessions/{sid}/rename", {"title": "Seen on the page"})
    shown = waited(lambda: c.js(f"(S.sessions.find(s => s.id === '{sid}') || {{}}).title || ''").endswith("Seen on the page"), 3)
    check("a change shows on the page without a poll", bool(shown))
    c.js("push.source.close(); push.source = null; push.base = null")
    back = waited(lambda: c.js("pushLive()"), 8)
    check("a stream that dies comes back on its own", bool(back))
    # ── its terminal ──
    check("with no WebGL the terminal keeps the DOM renderer", c.js("liveTerms.values().next().value.renderer") == "dom" and c.js("!!document.querySelector('.pane .xterm-rows')"))
    subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "-l", "printf 'line %s\\n' $(seq 1 400); echo all-written"])
    subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "Enter"])
    check("a burst of output is written whole", bool(waited(lambda: "all-written" in screen_text(c) and "line 400" in screen_text(c), 8)), screen_text(c)[-200:])
    c.js("(() => { window.__writes = 0; const t = liveTerms.values().next().value.term; const w = t.write.bind(t); t.write = (d, cb) => { window.__writes++; return w(d, cb); }; })()")
    subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "-l", "for i in $(seq 1 60); do echo tick $i; done"])
    subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "Enter"])
    waited(lambda: "tick 60" in screen_text(c), 8)
    check("many small pieces of output are written once a frame, not once each", 0 < c.js("window.__writes") <= 30, c.js("window.__writes"))
    # Copy: tmux hands a selection to the terminal as OSC 52, and the pane says so, quietly.
    c.js("liveTerms.values().next().value.term.write('\\x1b]52;c;' + btoa('copied by the push check') + '\\x07')")
    chip = waited(lambda: c.js("(() => { const e = document.querySelector('.pane .term-copied.show'); return e && e.textContent; })()"), 3)
    check("a copy says Copied in the pane", chip == "Copied", chip)
    c.shot("push-copied")
    check("and the words reach the clipboard", c.js("navigator.clipboard.readText().catch(() => '')") == "copied by the push check")
    gone_again = waited(lambda: not c.js("!!document.querySelector('.pane .term-copied.show')"), 4)
    check("the Copied note goes by itself", bool(gone_again))
    # A tab hidden for a while lets its terminal go, and connects it again on return.
    c.js("SETTINGS.term_park_after = 0.5; Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'))")
    parked = waited(lambda: c.js("(() => { const t = liveTerms.values().next().value; return t.parked && t.ws.readyState === 3; })()"), 5)
    check("a terminal in a tab hidden for a while lets its socket go", bool(parked))
    time.sleep(0.5)
    check("and doesn't try to reconnect while hidden", c.js("liveTerms.values().next().value.ws.readyState") == 3 and c.js("liveTerms.values().next().value.link") == "open")
    subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "-l", "echo typed-while-away"])
    subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "Enter"])
    c.js("delete document.hidden; document.dispatchEvent(new Event('visibilitychange'))")
    rejoined = waited(lambda: c.js("(() => { const t = liveTerms.values().next().value; return !t.parked && t.ws.readyState === 1 && t.link === 'open'; })()"), 6)
    check("back in view it connects again at once", bool(rejoined))
    check("and tmux draws what happened meanwhile", bool(waited(lambda: "typed-while-away" in screen_text(c), 6)), screen_text(c)[-200:])
    c.js("SETTINGS = {}")
    check("no script errors", not c.errors, c.errors[:5])
    chrome.terminate(); chrome.wait(); procs.pop()

    # ── with WebGL ──
    chrome, profile, c = browser("--use-angle=swiftshader", "--enable-unsafe-swiftshader")
    procs.append((chrome, profile))
    c.call("Page.navigate", url=CFG["origin"] + f"/#/s/{sid}")
    waited(lambda: c.js("[...liveTerms].length === 1 && liveTerms.values().next().value.link === 'open'"), 20)
    if c.js("!!document.createElement('canvas').getContext('webgl2')"):
        check("with WebGL the terminal draws on the GPU", c.js("liveTerms.values().next().value.renderer") == "webgl" and not c.js("!!document.querySelector('.pane .xterm-rows')"))
        subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "-l", "echo drawn-by-webgl"])
        subprocess.run(TMUX + ["send-keys", "-t", f"hub-{sid}", "Enter"])
        check("and shows what the session prints", bool(waited(lambda: "drawn-by-webgl" in screen_text(c), 6)))
        c.shot("push-webgl")
        check("the setting term_renderer: dom keeps a terminal on the DOM renderer", c.js("(() => { SETTINGS.term_renderer = 'dom'; const r = termRenderer(new Terminal()); SETTINGS = {}; return r; })()") == "dom")
    else:
        print("SKIP  this Chrome has no WebGL 2, so the WebGL renderer isn't checked", flush=True)
    check("no script errors with WebGL", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        for chrome, profile in procs:
            chrome.terminate()
            chrome.wait()
            shutil.rmtree(profile, ignore_errors=True)
        for sid in ids:
            api("POST", f"/api/sessions/{sid}/stop", {})
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
