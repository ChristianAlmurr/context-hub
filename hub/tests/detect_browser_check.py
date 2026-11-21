#!/usr/bin/env python3
"""A session's state in the page, in headless Chrome: "Done · asks you" with its quiet tag in the sidebar and on Home,
why a session is in its state in the row's tooltip and in Peek, and Home's notice after a Mac restart: Resume all, one
at a time, and a failed resume that keeps its error. Desk (1440x900) and phone (390x844).

Run: /usr/bin/python3 tests/detect_browser_check.py <output-folder>
Runs against a second instance (the six HUB_* variables, see tests/instance.py). Makes a throwaway project,
hub-test-throwaway-<n>, with three short Haiku sessions, and removes all of it. A restart is played as in restart_check.py.
"""
import base64, http.client, json, os, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, STATE, WRITE, answer_first_run, launchd_jobs, quiet_alert, remove_project, sweep, tell
from instance import PORT as HUB_PORT
import hub_data as hub

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:300]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read() or b"{}")


def row(sid):
    return next((s for s in api("GET", "/api/state")["sessions"] if s["id"] == sid), None)


def wait(sid, ok, limit=120):
    end = time.time() + limit
    while time.time() < end:
        r = row(sid)
        if r and ok(r):
            return r
        time.sleep(1)
    return row(sid)


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
        self.buffer = data.split(b"\r\n\r\n", 1)[1]
        self.n = 0
        self.errors = []

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
            if message.get("method") == "Log.entryAdded" and message["params"]["entry"]["level"] == "error":
                self.errors.append(message["params"]["entry"]["text"][:200])

    def js(self, expression):
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def shot(self, name):
        data = self.call("Page.captureScreenshot", format="png")["data"]
        (OUT / f"{name}.png").write_bytes(base64.b64decode(data))

    def size(self, width, height, mobile=False):
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=mobile)


sweep()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ids = []
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    task = {"project": NAME, "isolate": False, "mode": "manual", "model": "haiku", "effort": "low"}
    ids += api("POST", "/api/sessions", {**task, "tasks": ["Reply with exactly this sentence and nothing else: Shall I write the tests next?"]})["ids"]
    answer_first_run(ids[0])
    ids += api("POST", "/api/sessions", {**task, "tasks": ["Reply with the single word ready and nothing else."]})["ids"]
    ids += api("POST", "/api/sessions", {**task, "tasks": ["Reply with the single word steady and nothing else."]})["ids"]
    asks, good, bad = ids
    check("the first session finishes with asks", (wait(asks, lambda s: s["state"] == "finished" and s.get("asks")) or {}).get("asks"))
    for sid in (good, bad):
        wait(sid, lambda s: s["state"] == "finished" and s.get("said"))
        api("POST", f"/api/sessions/{sid}/stop", {})
        wait(sid, lambda s: not s["alive"], 20)
    data = hub.read_alive()
    for sid in (good, bad):
        data["alive"][sid] = hub.boot_time() - 60
    hub.write_alive(data)
    meta_path = STATE / "sessions" / f"{bad}.json"
    meta = json.loads(meta_path.read_text())
    meta["folder"] = str(STATE / "a-folder-that-is-gone")
    meta_path.write_text(json.dumps(meta))
    check("both stopped sessions read as lost", all((wait(sid, lambda s: s.get("lost"), 10) or {}).get("lost") for sid in (good, bad)))

    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Log.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.size(1440, 900)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    drawn = lambda what, seconds=20: next((True for _ in range(seconds * 4) if c.js(what) or time.sleep(0.25)), False)
    check("Home shows the restart notice", drawn("!!document.querySelector('.panel.lost')"))
    check("it says how many were running", c.js("document.querySelector('#lost-h').textContent") == "2 sessions were running when the Mac restarted", c.js("(document.querySelector('#lost-h') || {}).textContent"))
    check("it leads Home, above the queue", c.js("document.querySelector('.dash > .panel').classList.contains('lost')"))
    check("Resume all says how many", c.js("document.querySelector('[data-key=\"lost:all\"]').textContent") == "Resume all 2")
    check("each lost session has its own Resume", c.js("document.querySelectorAll('.lost-row .lost-one').length") == 2)
    c.js(f"document.querySelector('.side-row[data-sid=\"{asks}\"]') || document.querySelector('[data-key=\"chev:{NAME}\"]')?.click()")
    drawn(f"!!document.querySelector('.side-row[data-sid=\"{asks}\"]')", 5)
    check("the sidebar row of a finished turn that asks carries the quiet tag", drawn(f"!!document.querySelector('.side-row[data-sid=\"{asks}\"] .asks-tag')", 5))
    tip = c.js(f"(document.querySelector('.side-row[data-sid=\"{asks}\"]') || {{}}).title") or ""
    check("its tooltip says Done · asks you, and why", "Done · asks you: Shall I write the tests next?" in tip and "Why: hook: Stop at" in tip and "reply ends in ?" in tip, tip)
    c.js("document.querySelector('[data-key=\"tab:done\"]').click()")
    check("Home's Done tab shows the tag and the question", drawn(f"(document.querySelector('.qrow[data-nav=\"{asks}\"] .q-line') || {{}}).textContent === 'asks youShall I write the tests next?'", 5), c.js(f"(document.querySelector('.qrow[data-nav=\"{asks}\"] .q-line') || {{}}).textContent"))
    c.js("window.scrollTo(0, 0)")
    c.shot("detect-home-desk")
    c.js(f"window.hubPeek('{asks}')")
    check("Peek says Done · asks you, and why", drawn("(document.querySelector('.peek-when') || {}).textContent === 'Done · asks you' && (document.querySelector('.peek-why') || {}).textContent?.startsWith('Why: hook: Stop at')", 8), c.js("[(document.querySelector('.peek-when') || {}).textContent, (document.querySelector('.peek-why') || {}).textContent]"))
    c.shot("detect-peek-desk")
    c.js("document.querySelector('.peek-pop [aria-label=Close]').click()")

    c.js("document.querySelector('[data-key=\"lost:all\"]').click()")
    check("after Resume all, the one that failed stays with its error", drawn(f"(document.querySelector('.lost-row[data-sid=\"{bad}\"] .q-line.err') || {{}}).textContent?.includes('folder')", 20), c.js("document.querySelector('.panel.lost')?.innerText"))
    check("the one that resumed leaves the notice", drawn(f"!document.querySelector('.lost-row[data-sid=\"{good}\"]')", 10))
    check("the notice now counts one", c.js("document.querySelector('#lost-h').textContent") == "1 session was running when the Mac restarted")
    check("the failed one offers Try again", c.js(f"document.querySelector('.lost-row[data-sid=\"{bad}\"] .lost-one').textContent") == "Try again")
    check("the resumed session runs again", (wait(good, lambda s: s["alive"], 20) or {}).get("alive"))
    c.size(390, 844, mobile=True)
    time.sleep(1.5)
    c.shot("detect-home-phone")
    check("on a phone the notice's buttons are at least 40px tall", c.js("Math.min(...[...document.querySelectorAll('.lost-acts .btn')].map(b => b.getBoundingClientRect().height))") >= 40)
    check("on a phone nothing in the notice spills sideways", c.js("document.querySelector('.panel.lost').scrollWidth <= document.querySelector('.panel.lost').clientWidth + 1"))
    c.js("document.querySelector('[data-key=\"lost:dismiss\"]').click()")
    check("Not now hides the notice", drawn("!document.querySelector('.panel.lost')", 10))
    check("no errors in the page", not c.errors, c.errors)
finally:
    try:
        for sid in ids:
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        chrome.terminate(); chrome.wait()
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before, sorted(set(launchd_jobs()) ^ set(launchd_before)))
print("--- failures:", failures)
sys.exit(1 if failures else 0)
