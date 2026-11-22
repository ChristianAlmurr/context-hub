#!/usr/bin/env python3
"""Where things live (round 3's navigation), in headless Chrome at a desk and on a phone.

A throwaway project, hub-test-throwaway-<n>, with four plain terminals; what they are doing is laid over /api/state in
the page, so no Claude runs.
- The sidebar: places (Go to, Home, Dream Catcher), the Projects header with sort, new folder and new project, and a
  labelled Settings row at its foot in every way it is drawn (tree, sorted by what needs you, the rail). No
  notifications row anywhere in it.
- Home's count is the count on Home's own Needs you tab.
- Page headers: Home's primary action and its ⋯; a project's ⋯ is the project menu with Project settings; a session
  names its project and itself.
- Notifications: a one-time ask on Home while this browser was never asked, gone for good after Not now.
- Keys: g , and ⌘, open Settings; , on a project page still opens its settings; ⌘K still opens Go to.
- A phone: a bottom bar (Home with its count, Projects, Go to, Settings) off a session; the counts row on a session;
  a project's name and its tabs on two rows; Settings as a grouped list, a section with Settings to go back.

Runs against a second instance (the six HUB_* variables, see tests/instance.py).
Run: /usr/bin/python3 tests/nav_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, TMUX, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-ia.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9343"))
failures = 0
CTRL, SHIFT, META = 2, 8, 4


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read() or b"{}")


def waited(test, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.2)
    return None


def last_line(sid):
    """The shell's line the cursor is on: only its prompt, if nothing was typed into it."""
    lines = [line.rstrip() for line in subprocess.run(TMUX + ["capture-pane", "-p", "-t", f"hub-{sid}"], capture_output=True, text=True).stdout.split("\n") if line.strip()]
    return lines[-1] if lines else ""


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

    def press(self, key, code=None, mods=0, text=None):
        """One key, down and up, as a keyboard sends it: a printable key carries its text, so a key nobody caught types."""
        vk = {"Enter": 13, "Escape": 27, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40, "`": 192, "/": 191}.get(key) or (ord(code[-1]) if code and code[:-1] in ("Key", "Digit") else ord(key.upper()[0]))
        code = code or (f"Key{key.upper()}" if len(key) == 1 and key.isalpha() else key)
        down = dict(type="keyDown", key=key, code=code, modifiers=mods, windowsVirtualKeyCode=vk)
        if text is None and len(key) == 1 and not mods & (CTRL | META):
            text = key
        if text:
            down["text"] = text
        self.call("Input.dispatchKeyEvent", **down)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, modifiers=mods, windowsVirtualKeyCode=vk)
        time.sleep(0.12)

    def prefix(self, *keys):
        """⌃` and then each key: a key is a name, or (name, code, modifiers)."""
        self.press("`", "Backquote", CTRL)
        for k in keys:
            if isinstance(k, tuple):
                self.press(*k)
            else:
                self.press(k)
        time.sleep(0.6)

    def mouse(self, kind, x, y, clicks=1):
        self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", buttons=1 if kind == "mousePressed" else 0, clickCount=clicks, pointerType="mouse")

    def box(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return {{x: r.left, y: r.top, w: r.width, h: r.height}}; }})()")

    def hash(self):
        return self.js("decodeURIComponent(location.hash)")

    def focused(self):
        """The session whose terminal has the keyboard, or None."""
        return self.js("(() => { const e = document.activeElement; return e && e.closest('.xterm') ? e.closest('.pane').dataset.sid : null; })()")

    def open(self, route, panes=1):
        """A page loaded afresh at a route, once it shows that many panes, with the made-up states laid over again."""
        self.js(f"location.hash = {json.dumps(route)}; window.oldPage = true")
        self.call("Page.reload")
        shown = waited(lambda: self.js(f"!window.oldPage && document.querySelectorAll('.pane').length >= {panes} && !!document.querySelector('#side .nav.session')"), 30)
        self.fake()
        time.sleep(1)
        return shown

    def fake(self, extra=None):
        """What each session is doing, laid over every /api/state this page reads (window.fakeState: id → fields)."""
        if extra is not None:
            self.js(f"window.fakeState = {json.dumps(extra)}")
        self.js("""(() => {
          if (window.fakeOn) return;
          window.fakeOn = true;
          window.EventSource = undefined; if (push.source) push.source.close(); push.source = null; push.base = null;  // the live stream would bring the real state past this overlay
          window.fakeState = window.fakeState || JSON.parse(localStorage.getItem('fakeState') || '{}');
          const real = window.fetch;
          window.fetch = async (url, options) => {
            const answer = await real(url, options);
            if (!String(url).includes('/api/state')) return answer;
            const data = await answer.json(), f = window.fakeState || {};
            data.sessions = data.sessions.map((s) => f[s.id] ? { ...s, ...f[s.id] } : s).concat(f.extra || []);
            return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
          };
        })()""")
        self.js("localStorage.setItem('fakeState', JSON.stringify(window.fakeState)); tick()")
        time.sleep(0.6)

    def item(self, words):
        return self.js(f"(() => {{ const b = [...document.querySelectorAll('.popup.menu button')].find(b => b.textContent.startsWith({json.dumps(words)})); if (b) b.click(); return !!b; }})()")



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
    for letter in "ABCD":
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": f"Pane {letter}"})
        ids.append(sid)
    A, B, C, D = ids
    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)
    c.js("localStorage.clear()")
    STATES = {C: {"state": "needs", "asking": "Which port should the preview use?"}, D: {"state": "finished", "said": "All tests pass now."},
              B: {"state": "working", "activity": {"tool": "Edit", "target": "login.py", "since": time.time() - 30}}}
    c.fake(STATES)
    # This browser has never been asked about notifications, whatever headless Chrome says.
    ASK = "Object.defineProperty(Notification, 'permission', { get: () => window.fakePermission || 'default', configurable: true })"

    # ── The sidebar ──
    c.open("#/", panes=0)
    c.js(ASK); c.js("sideKey = ''; render()"); time.sleep(0.4)
    keys = c.js("[...document.querySelectorAll('#side .side-list [data-key]')].slice(0, 4).map(e => e.dataset.key)")
    check("the sidebar opens with its places: Go to, Home, the Dream Catcher", keys[:3] == ["goto", "home", "catcher"], keys)
    check("Go to names its key", c.js("document.querySelector('#side [data-key=goto]').innerText").replace("\n", " ") == "Go to ⌘K", c.js("document.querySelector('#side [data-key=goto]').innerText"))
    acts = c.js("[...document.querySelectorAll('#side .side-title.with-act')].find(t => t.firstChild.textContent === 'Projects').querySelectorAll('[data-key]').length")
    check("the Projects header carries sort, new folder and new project", acts == 3 and c.js("!!document.querySelector('#side .side-title [data-key=side-order]') && !!document.querySelector('#side .side-title [data-key=new-project]')"), acts)
    check("the brand is only the brand", not c.js("!!document.querySelector('#side .brand button')"))
    row = "#side .side-end [data-key=settings]"
    check("Settings is a labelled row at the foot", c.js(f"document.querySelector('{row} .label').textContent") == "Settings" and c.js(f"document.querySelector('{row} kbd').textContent") == "⌘," and c.js(f"document.querySelector('{row}').getBoundingClientRect().width") > 150)
    check("no notifications row in the sidebar", not c.js("[...document.querySelectorAll('#side *')].some(e => /notifications/i.test(e.textContent) && e.children.length === 0)"))
    check("its gear is a gear, not a sun", "M6.9 1.8" in c.js(f"document.querySelector('{row} svg').innerHTML"))
    c.js(f"document.querySelector('{row}').click()"); time.sleep(0.8)
    check("it opens Settings and marks itself", c.hash().startswith("#/settings") and c.js(f"document.querySelector('{row}').getAttribute('aria-current')") == "page")
    c.js("location.hash = '#/'"); time.sleep(0.8)
    home_n = c.js("(document.querySelector('#side [data-key=home] .count') || {}).textContent")
    tab_n = c.js("document.querySelector('[data-key=\"tab:needs\"] b').textContent")
    check("Home's count is its Needs you tab's count", home_n == tab_n and home_n, [home_n, tab_n])
    c.shot("01-desk-home")
    c.js("document.querySelector('#side [data-key=side-order]').click()"); time.sleep(0.8)
    check("sorted by what needs you, the toggle heads the Sessions section", c.js("document.querySelector('#side [data-key=side-order]').closest('.side-title').firstChild.textContent") == "Sessions"
          and c.js("document.querySelector('#side [data-key=side-order]').getAttribute('aria-pressed')") == "true")
    check("and Settings is still at the foot", c.js(f"!!document.querySelector('{row}')"))
    c.js("document.querySelector('#side [data-key=side-order]').click()"); time.sleep(0.5)
    c.press("b", "KeyB", META); time.sleep(0.6)
    check("the rail keeps Go to and Settings, each named", c.js("document.body.classList.contains('rail')") and c.js("document.querySelector('#side [data-key=goto]').getAttribute('aria-label')") == "Go to"
          and c.js(f"document.querySelector('{row}').getAttribute('aria-label')") == "Settings")
    c.press("b", "KeyB", META); time.sleep(0.6)
    check("⌘B unfolds it again", not c.js("document.body.classList.contains('rail')"))

    # ── Notifications: asked once, on Home ──
    check("Home asks once about notifications, under the queue", c.js("(() => { const a = document.querySelector('.panel.notify-ask'); return !!a && a.previousElementSibling.classList.contains('triage'); })()"))
    c.js("document.querySelector('[data-key=notify-later]').click()"); time.sleep(0.6)
    check("Not now ends it for this browser", not c.js("!!document.querySelector('.panel.notify-ask')") and c.js("localStorage.getItem('notifyAsked')") is not None, c.js("Object.keys(localStorage)"))
    c.open("#/", panes=0); c.js(ASK); c.js("render()"); time.sleep(0.4)
    check("and after a reload it stays gone", not c.js("!!document.querySelector('.panel.notify-ask')"))
    c.js("location.hash = '#/settings/notifications'"); time.sleep(1)
    check("Settings › Notifications keeps the browser's own switch", c.js("!!document.querySelector('[data-key=notify-browser]')"))

    # ── Page headers ──
    c.js("location.hash = '#/'"); time.sleep(0.8)
    check("Home's header: its title, New session, then ⋯", c.js("[...document.querySelectorAll('#top .actions-top > :not(.find-btn)')].map(e => e.dataset.key)") == ["home-new", "home-more"])
    c.js("document.querySelector('[data-key=home-more]').click()"); time.sleep(0.3)
    check("Home's ⋯ holds New project and New folder", c.js("[...document.querySelectorAll('.popup.menu button')].map(b => b.innerText.trim())") == ["New project", "New folder…"])
    c.press("Escape"); time.sleep(0.2)
    c.js(f"location.hash = '#/p/{NAME}'"); time.sleep(1.2)
    check("a project's header has no lone gear", not c.js("[...document.querySelectorAll('#top .icon')].some(b => b.title === 'Project settings')"))
    c.js("document.querySelector('[data-key=project-more]').click()"); time.sleep(0.3)
    items = c.js("[...document.querySelectorAll('.popup.menu button')].map(b => b.innerText.trim())")
    check("its ⋯ is the project's menu, Project settings among it", "Project settings…" in items and "New session" in items, items)
    c.item("Project settings…"); time.sleep(0.4)
    check("which opens the project's settings", c.js("(document.querySelector('dialog[open]') || {}).getAttribute && document.querySelector('dialog[open]').getAttribute('aria-label')") == "Project settings")
    c.js("document.querySelector('dialog[open]').close()"); time.sleep(0.2)
    c.press(","); time.sleep(0.4)
    check(", on a project page still opens its settings", c.js("!!document.querySelector('dialog[open][aria-label=\"Project settings\"]')"))
    c.js("document.querySelector('dialog[open]').close()"); time.sleep(0.2)
    c.shot("02-desk-project")
    c.open(f"#/s/{A}")
    top = c.js("document.querySelector('#top .crumbs').innerText")
    check("a session's header names its project and itself", NAME in top and "Pane A" in top and c.js("!document.querySelector('#top .tail').classList.contains('sr-only')"), top)
    c.shot("03-desk-session")

    # ── Keys ──
    c.js("location.hash = '#/'"); time.sleep(0.6); c.js("document.querySelector('#side .brand').click()")
    c.press("g"); c.press(",", "Comma"); time.sleep(0.5)
    check("g , opens Settings", c.hash().startswith("#/settings"), c.hash())
    c.js("location.hash = '#/'"); time.sleep(0.6)
    c.press(",", "Comma", META); time.sleep(0.5)
    check("⌘, opens Settings", c.hash().startswith("#/settings"), c.hash())
    c.press("k", "KeyK", META); time.sleep(0.4)
    check("⌘K still opens Go to", c.js("!!document.querySelector('dialog.palette[open]')"))
    c.js("document.querySelector('dialog.palette').close()")
    check("the key sheet lists g ,", "g ," in c.js("KEYS[0][1].map(k => k[0]).join('|')"))

    # ── A phone ──
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.open("#/", panes=0); time.sleep(0.6)
    bar = c.js("[...document.querySelectorAll('#phone-bar .pb-item')].map(e => e.dataset.key)")
    check("off a session the phone has a bottom bar: Home, Projects, Go to, Settings", bar == ["pb:home", "pb:projects", "pb:goto", "pb:settings"], bar)
    same = "(() => { const b = document.querySelector('[data-key=\"pb:home\"] .pb-badge'), t = document.querySelector('[data-key=\"tab:needs\"] b'); return !!b && !!t && b.textContent === t.textContent && b.textContent !== '0'; })()"
    check("its Home carries Home's count, and is the page you're on", bool(waited(lambda: c.js(same), 10))
          and c.js("document.querySelector('[data-key=\"pb:home\"]').getAttribute('aria-current')") == "page")
    check("it sits at the foot, inside the screen", abs(c.js("document.querySelector('#phone-bar').getBoundingClientRect().bottom") - 844) < 2)
    check("no counts on the menu off a session: the bar carries them", not c.js("!!document.querySelector('#top .menu-hot')") and c.js("document.querySelector('#top .menu-btn').getAttribute('aria-label')") == "Menu")
    c.shot("04-phone-home")
    c.js("document.querySelector('[data-key=\"pb:projects\"]').click()"); time.sleep(0.6)
    check("Projects opens the drawer", c.js("document.body.classList.contains('side-open')") and c.js("document.querySelector('[data-key=\"pb:projects\"]').getAttribute('aria-expanded')") == "true")
    check("the drawer's foot is Settings, labelled, with no keycap", c.js("document.querySelector('#side .side-end [data-key=settings]').innerText.trim()") == "Settings")
    c.shot("05-phone-drawer")
    c.js("closeSide()")
    c.js("document.querySelector('[data-key=\"pb:settings\"]').click()"); time.sleep(0.8)
    check("Settings on a phone is a list in groups", c.js("[...document.querySelectorAll('.set-group-t')].map(e => e.textContent)") == ["You", "Sessions", "System"] and c.js("document.querySelector('.set-body').offsetParent === null"))
    c.shot("06-phone-settings")
    c.js("document.querySelector('.set-nav [data-key=\"tab:notifications\"]').click()"); time.sleep(0.8)
    check("a section is a page, with Settings to go back", c.js("!!document.querySelector('#top [data-key=settings-back]')") and c.js("document.querySelector('.set-nav').offsetParent === null")
          and c.js("document.documentElement.scrollWidth <= innerWidth"))
    c.press("Escape"); time.sleep(0.6)
    check("Esc goes back to the list", c.hash() == "#/settings", c.hash())
    c.js(f"location.hash = '#/p/{NAME}'"); time.sleep(1.2)
    name = c.box("#top .crumbs .tail"); tabs = c.box("#top .ptabs"); more = c.box("#top [data-key=project-more]")
    check("a project shows its name, and its tabs on a row of their own under it", name and tabs and tabs["y"] >= name["y"] + name["h"] - 1 and tabs["w"] >= 380 and c.js("document.querySelector('#top .crumbs .tail').innerText").strip() == NAME, [name, tabs])
    check("nothing in the header overlaps", more and name["x"] + name["w"] <= more["x"] + 1, [name, more])
    c.shot("07-phone-project")
    c.open(f"#/s/{A}")
    label = c.js("document.querySelector('#top .menu-btn').getAttribute('aria-label')")
    check("on a session the bar steps aside for the chat, and the menu button carries the counts", c.js("document.querySelector('#phone-bar').hidden") and (label == "Menu" or label.startswith("Menu, ")), label)
    check("and its search button is in the top bar", c.js("getComputedStyle(document.querySelector('#top .find-btn')).display") != "none")
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:
    check("the run went to its end", False, repr(error))
finally:
    try:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        for sid in ids:
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
