#!/usr/bin/env python3
"""Attention, end to end, in headless Chrome: done and unread everywhere, read marks shared across devices, the sidebar
sorted by what needs you, rows updated in place, notices with their settings, sounds, and the phone's counts.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with five plain terminals. What each one
is doing (needs you, finished, working) is laid over the real /api/state in the page, so every state is reached at once
and none needs Claude; read marks, and everything else, go to the real server.
- A finished turn you haven't read lights its row, its project's mark, the tab's title and its icon; opening it reads it
  on the server, and a second page (a phone) sees it read.
- "Sort by what needs you": needs, then done, then working, then idle, each row with its project; the order follows a
  change, and rows glide unless motion is reduced. attentionOrder() is the same order.
- A poll that only changes what a session is doing keeps its row, its focus and the list's scroll.
- Notices: told after two polls, not after a flash of one; replaced per session; silent for the session you look at and
  for a muted project; off by default for a finish.
- Sounds: hubPlaySound plays each tone once the page has had a click.
- The phone's counts row, which opens Home on that tab.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/attention_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-attention.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0

# Laid over /api/state in the page: each session's fields from localStorage "test.fake", and a new `at` on every answer,
# so each poll counts as one.
FAKE = """(() => {
  const real = window.fetch.bind(window);
  window.fetch = async (url, options) => {
    const answer = await real(url, options);
    if (typeof url !== "string" || !url.startsWith("/api/state") || !answer.ok) return answer;
    const data = await answer.clone().json();
    const fake = JSON.parse(localStorage.getItem("test.fake") || "{}");
    data.sessions.forEach((s) => { if (fake[s.id]) Object.assign(s, fake[s.id]); });
    // Only the test's own polls count as new ones: the page's clock may poll in between, and must not count twice.
    if (window.manualPoll || !window.lastAt) window.lastAt = Date.now() / 1000;
    data.at = window.lastAt;
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  const Real = window.Notification;
  window.told = [];
  window.Notification = function (title, options) { window.told.push({ title, ...(options || {}) }); return { close() {}, set onclick(f) {} }; };
  window.Notification.permission = "granted";
  window.Notification.requestPermission = async () => "granted";
})();"""


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read())


def reads():
    """The server's read marks. Another test run beside this one can leave a half-made store for a moment, which the
    whole state can't be read past; so this asks again."""
    for _ in range(40):
        state = api("GET", "/api/state")
        if "sessions" in state:
            return state.get("reads", {})
        time.sleep(0.5)
    return {}


def waited(test, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.25)
    return None


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
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True, userGesture=False).get("result", {}).get("value")

    def shot(self, name):
        (OUT / f"{name}.png").write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def click(self, selector):
        b = waited(lambda: self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e || !e.offsetParent) return null; const r = e.getBoundingClientRect(); return {{x: r.left + r.width / 2, y: r.top + r.height / 2}}; }})()"), 10)
        if not b:
            raise AssertionError(f"nothing to click at {selector}")
        for kind in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", type=kind, x=b["x"], y=b["y"], button="left", buttons=1 if kind == "mousePressed" else 0, clickCount=1)
        time.sleep(0.3)

    def poll(self, times=1):
        """That many polls, each a fresh state, then the page settled."""
        for _ in range(times):
            self.js("window.manualPoll = true; tick().finally(() => { window.manualPoll = false; })")
        time.sleep(0.2)


def page_of(width, height, mobile):
    target = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")))
    c = CDP(target["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})  # what Tailscale Serve adds on the way in
    c.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2 if mobile else 1, mobile=mobile)
    c.call("Page.addScriptToEvaluateOnNewDocument", source=FAKE)
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)  # each page is in front, as a person's would be
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    waited(lambda: c.js("typeof hub !== 'undefined' && hub.ready && !!document.querySelector('#side .nav.session')"), 30)
    return c


def fake(c, sid, fields):
    c.js(f"(() => {{ const f = JSON.parse(localStorage.getItem('test.fake') || '{{}}'); f[{json.dumps(sid)}] = {json.dumps(fields)}; localStorage.setItem('test.fake', JSON.stringify(f)); }})()")


sweep()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    ids = []
    for word in ("Asks a question", "Wrote the report", "Builds the site", "Idle shell", "Second finish"):
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": word})
        ids.append(sid)
    NEEDS, DONE, WORKING, IDLE, DONE2 = ids
    waited(lambda: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version"), 10)

    # ── The server's read marks ──
    marked = api("POST", "/api/reads", {"marks": {DONE: "finished:first"}})
    check("a read mark is kept on the server", marked.get("reads", {}).get(DONE) == "finished:first", marked)
    check("and comes back with the state", reads().get(DONE) == "finished:first")
    check("a mark for something that isn't a session is refused", "error" in api("POST", "/api/reads", {"marks": {"../../x": "y"}}))
    check("marking unread takes the mark away", DONE not in api("POST", "/api/reads", {"marks": {DONE: None}}).get("reads", {}))

    desk = page_of(1440, 900, False)
    desk.js("localStorage.removeItem('test.fake')")
    fake(desk, NEEDS, {"state": "needs", "asking": "Should I deploy it now?"})
    fake(desk, WORKING, {"state": "working", "activity": {"tool": "Edit", "target": "site.css", "since": time.time() - 30}, "turn": {"since": time.time() - 40}})
    fake(desk, DONE, {"state": "finished", "said": "The report is written."})
    desk.poll(2)
    group = f'#side .side-group[data-project="{NAME}"]'

    # ── Done and unread, everywhere ──
    row = lambda sid: f'#side .side-row[data-sid="{sid}"]'
    check("an unread finish lights its row", desk.js(f"document.querySelector('{row(DONE)}').classList.contains('done-unread')"))
    check("the tab's title counts what is waiting, done and working", desk.js("document.title").startswith("(1 waiting, 1 done, 1 working)"), desk.js("document.title"))
    desk.js(f"localStorage.setItem('expanded', JSON.stringify({{ {json.dumps(NAME)}: false }})); sideKey = ''; drawSide()")
    fake(desk, NEEDS, {"state": "working"})
    desk.poll(1)
    check("with nothing waiting, the project's mark rolls up the unread finish before the working one", desk.js(f"!!document.querySelector('{group} .side-row.project .state .orb-finished')"), desk.js(f"document.querySelector('{group} .side-row.project .state').innerHTML.slice(0, 80)"))
    check("the tab's icon shows a finish", "8fb0ff" in (desk.js("document.querySelector('link[rel=icon]').href") or ""))
    fake(desk, NEEDS, {"state": "needs", "asking": "Should I deploy it now?"})
    desk.poll(1)
    check("needs you still leads the project's mark", desk.js(f"!!document.querySelector('{group} .side-row.project .state .orb-needs')"))
    desk.js(f"localStorage.setItem('expanded', '{{}}'); sideKey = ''; drawSide()")

    # ── Opening reads it, on the server; another device sees it read ──
    desk.js(f"location.hash = '#/s/{DONE}'")
    read = waited(lambda: reads().get(DONE), 10)
    check("opening a finished session marks it read on the server", read == "finished:The report is written.", read)
    desk.js("location.hash = '#/'")
    desk.poll(1)
    check("a read finish goes quiet in the sidebar", desk.js(f"document.querySelector('{row(DONE)}').classList.contains('done-read')"))
    phone = page_of(390, 844, True)
    phone.poll(1)
    check("the phone sees it read too", phone.js(f"isRead(session('{DONE}'))") is True)

    # ── The phone's counts row ──
    fake(desk, DONE2, {"state": "finished", "said": "Second thing finished."})
    phone.js(f"location.hash = '#/s/{IDLE}'")
    phone.poll(2)
    counts = phone.js("document.querySelector('.counts-bar') && !document.querySelector('.counts-bar').hidden ? document.querySelector('.counts-bar').textContent : ''")
    check("the phone shows how many need you, are done and are working", counts == "1 needs you·1 done·1 working", counts)
    phone.shot("attention-phone-counts")
    phone.click(".counts-bar .c-done")
    check("a count opens Home on that tab", waited(lambda: phone.js("(document.querySelector('.qtab.on') || {}).textContent || ''").startswith("Done"), 10), phone.js("(document.querySelector('.qtab.on') || {}).textContent"))
    check("Home has no counts row: it has its tabs", phone.js("document.querySelector('.counts-bar').hidden") is True)

    # ── Sorted by what needs you ──
    desk.poll(1)
    desk.click('#side [data-key="side-order"]')
    order = desk.js("[...document.querySelectorAll('#side .side-band')].map((b) => b.className.match(/band-(\\w+)/)[1])")
    check("the toggle sorts the sidebar by what needs you, in bands", order == ["needs", "done", "working", "idle"], order)
    listed = desk.js("[...document.querySelectorAll('#side .side-row[data-sid]')].map((r) => r.dataset.sid)")
    check("needs first, then done and unread (newest first), then working, then idle", listed[:3] == [NEEDS, DONE2, WORKING] and set(listed[3:]) == {DONE, IDLE}, listed)
    check("attentionOrder() is the same order", desk.js("attentionOrder().map((s) => s.id)") == listed)
    check("each row names its project", desk.js(f"document.querySelector('{row(WORKING)} .head .proj').textContent") == NAME)
    check("the toggle says it is on", desk.js("document.querySelector('[data-key=\"side-order\"]').getAttribute('aria-pressed')") == "true")
    fake(desk, WORKING, {"state": "needs", "asking": "Which colour?"})
    desk.js("window.glides = 0; const was = Element.prototype.animate; Element.prototype.animate = function (...a) { window.glides++; return was.apply(this, a); }")
    desk.poll(1)
    listed = desk.js("[...document.querySelectorAll('#side .side-row[data-sid]')].map((r) => r.dataset.sid)")
    check("a session that comes to need you moves up, newest change first", listed[:2] == [WORKING, NEEDS], listed)
    check("rows glide to their new place", desk.js("window.glides") > 0)
    desk.shot("attention-desk-sorted")
    desk.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
    fake(desk, WORKING, {"state": "working", "activity": {"tool": "Edit", "target": "site.css", "since": time.time() - 30}, "turn": {"since": time.time() - 40}})
    desk.js("window.glides = 0")
    desk.poll(1)
    check("with reduced motion, rows move without gliding", desk.js("window.glides") == 0, desk.js("window.glides"))
    desk.call("Emulation.setEmulatedMedia", features=[])

    # ── Rows updated in place ──
    for mode in ("attention", "project"):
        desk.js(f"document.querySelector('{row(WORKING)}').kept = 1; document.querySelector('{row(WORKING)} a.nav').focus()")
        fake(desk, WORKING, {"state": "working", "activity": {"tool": "Bash", "target": f"npm test {mode}", "since": time.time() - 5}, "turn": {"since": time.time() - 40}})
        desk.poll(1)
        check(f"by {mode}: a new tool updates the row's line", f"npm test {mode}" in desk.js(f"document.querySelector('{row(WORKING)} .sub').textContent"))
        check(f"by {mode}: the row is the same one, still focused", desk.js(f"document.querySelector('{row(WORKING)}').kept === 1 && document.activeElement === document.querySelector('{row(WORKING)} a.nav')"))
        if mode == "attention":
            desk.click('#side [data-key="side-order"]')
    check("the sidebar is by project again", desk.js("!document.querySelector('#side .side-band') && !!document.querySelector('#side .side-group[data-project]')"))

    # ── Notices ──
    desk.js("SETTINGS = { ...SETTINGS, notify_done: 'banner' }")
    fake(desk, IDLE, {"state": "working"})
    desk.poll(1)
    fake(desk, IDLE, {"state": "finished", "said": "Tests pass."})
    desk.poll(1)
    check("a finish isn't told after one poll", desk.js(f"!document.querySelector('[data-notice=\"s:{IDLE}\"][data-kind=\"done\"]')"))
    desk.poll(1)
    check("it is told once it has held for two", desk.js(f"!!document.querySelector('[data-notice=\"s:{IDLE}\"][data-kind=\"done\"]')"))
    desk.shot("attention-desk-notice")
    fake(desk, IDLE, {"state": "needs", "asking": "Push it?"})
    desk.js("SETTINGS = { ...SETTINGS, notify_needs: 'banner' }")
    desk.poll(2)
    check("a newer notice replaces the same session's older one", desk.js(f"document.querySelectorAll('[data-notice=\"s:{IDLE}\"]').length") == 1 and desk.js(f"!!document.querySelector('[data-notice=\"s:{IDLE}\"][data-kind=\"needs\"]')"))
    fake(desk, DONE, {"state": "needs", "asking": "A flash"})
    desk.poll(1)
    fake(desk, DONE, {"state": "working"})
    desk.poll(2)
    check("a needs that lasted one poll is never told", desk.js(f"!document.querySelector('[data-notice=\"s:{DONE}\"]')"))
    desk.js(f"location.hash = '#/s/{DONE}'")
    time.sleep(1.5)
    desk.js(f"document.querySelector('.pane[data-sid=\"{DONE}\"]') && document.querySelector('.pane[data-sid=\"{DONE}\"]').querySelector('textarea, .xterm-helper-textarea, [tabindex]').focus()")
    fake(desk, DONE, {"state": "finished", "said": "Finished while you watched."})
    desk.poll(2)
    check("nothing is told for the session you are looking at", desk.js(f"!document.querySelector('[data-notice=\"s:{DONE}\"]')"))
    check("and its finish is read at once", waited(lambda: reads().get(DONE) == "finished:Finished while you watched.", 10))
    desk.js("location.hash = '#/'")
    desk.js(f"SETTINGS = {{ ...SETTINGS, muted_projects: [{json.dumps(NAME)}] }}")
    fake(desk, DONE2, {"state": "working"})
    desk.poll(1)
    fake(desk, DONE2, {"state": "finished", "said": "Muted finish."})
    desk.poll(2)
    check("a muted project tells nothing", desk.js(f"!document.querySelector('[data-notice=\"s:{DONE2}\"]')"))
    desk.js("SETTINGS = { ...SETTINGS, muted_projects: [], notify_done: 'off' }")
    fake(desk, DONE2, {"state": "working"})
    desk.poll(1)
    fake(desk, DONE2, {"state": "finished", "said": "Off by default."})
    desk.poll(2)
    check("a finish tells nothing when its setting is off", desk.js(f"!document.querySelector('[data-notice=\"s:{DONE2}\"]')"))
    desk.js("SETTINGS = { ...SETTINGS, notify_done: 'system' }; window.told = []; Object.defineProperty(document, 'hasFocus', { value: () => false, configurable: true })")
    fake(desk, DONE2, {"state": "working"})
    desk.poll(1)
    fake(desk, DONE2, {"state": "finished", "said": "Told by the system."})
    desk.poll(2)
    told = desk.js("window.told")
    check("'system' is the browser's notification while the hub isn't in front, tagged per session", told == [{"title": f"{NAME} · Second finish", "body": "Told by the system.", "tag": f"hub-{DONE2}"}], told)
    desk.js("delete document.hasFocus")

    # ── Sounds ──
    check("the hub offers its sounds", desk.js("window.hubSounds") == ["chime", "knock", "bell"])
    desk.click("#side .brand")
    played = [desk.js(f"window.hubPlaySound({json.dumps(name)}, 0.01)") for name in ("chime", "knock", "bell")]
    check("each sound plays once the page has had a click", played == [True, True, True], played)
    check("an unknown sound plays nothing", desk.js("window.hubPlaySound('nope')") is False)

    check("no script errors on the desk", not desk.errors, desk.errors)
    check("no script errors on the phone", not phone.errors, phone.errors)
finally:
    chrome.terminate()
    left = remove_project(NAME)
    check("the throwaway project is gone", not left, left)
    check("no launchd job was made", launchd_jobs() == launchd_before)
print(f"\n{'All passed' if not failures else f'{failures} failed'}. Screenshots in {OUT}")
sys.exit(1 if failures else 0)
