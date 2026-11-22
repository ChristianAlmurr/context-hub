#!/usr/bin/env python3
"""Session tabs and the session side panel, end to end, in headless Chrome with real key and pointer events.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with nine plain terminals. What a session
is doing (needs you, finished, working) is laid over /api/state in the page, so no Claude runs.
- Tabs at a desk: none with one session open (tabs_hide_single), a tab per session opened from the sidebar, each with
  its state's mark, its title and its project; a split changes its own tab; a session on a split tab is opened by
  focusing that tab and its pane, from the sidebar and from Go to; ⌘1–⌘9; middle-click and ⌫ close a tab and leave the
  session running; dragging and ⇧→ reorder; a reload keeps them; too many scroll and list themselves under a button.
- A phone: a count in the top bar opening a sheet of the tabs, which opens and closes them.
- The side panel: Overview first (folder with Copy path, branch, the repository's web address from an ssh remote with no
  name or token kept, memory, session facts), Changes listing what changed and opening the review at a file, Shared as
  before, a panel another feature adds later appearing at once, the last panel and the width kept over a reload, ⇧P
  and the arrows and Esc by keyboard, a full screen on a phone. GET /api/sessions/<id>/overview and POST .../reveal:
  Finder only for a page on this Mac.
- Switched off in Settings › Features (PUT /api/settings), each at once and without a reload: no tab bar, no count, the
  right panel as it was, the keys sheet as it was.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/tabs_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-tabs.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0
SHIFT, META, CTRL = 8, 4, 2


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, {**WRITE, **(headers or {})})
    answer = c.getresponse()
    return answer.status, json.loads(answer.read() or b"{}")


def get(path):
    return api("GET", path)[1]


def put_settings(values):
    return api("PUT", "/api/settings", values)


def waited(test, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.2)
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
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def shot(self, name):
        (OUT / f"{name}.png").write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def press(self, key, code=None, mods=0, text=None):
        vk = {"Enter": 13, "Escape": 27, "Backspace": 8, "Delete": 46, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40, "`": 192}.get(key) or (ord(code[-1]) if code and code[:-1] in ("Key", "Digit") else ord(key.upper()[0]))
        code = code or (f"Key{key.upper()}" if len(key) == 1 and key.isalpha() else f"Digit{key}" if len(key) == 1 and key.isdigit() else key)
        down = dict(type="keyDown", key=key, code=code, modifiers=mods, windowsVirtualKeyCode=vk)
        if text is None and len(key) == 1 and not mods & (CTRL | META):
            text = key
        if text:
            down["text"] = text
        self.call("Input.dispatchKeyEvent", **down)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, modifiers=mods, windowsVirtualKeyCode=vk)
        time.sleep(0.15)

    def mouse(self, kind, x, y, button="left", clicks=1):
        self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button=button, buttons=(1 if button == "left" else 4) if kind == "mousePressed" else 0, clickCount=clicks, pointerType="mouse")

    def click(self, x, y, button="left"):
        self.mouse("mouseMoved", x, y)
        self.mouse("mousePressed", x, y, button)
        self.mouse("mouseReleased", x, y, button)

    def box(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return {{x: r.left, y: r.top, w: r.width, h: r.height}}; }})()")

    def hash(self):
        return self.js("decodeURIComponent(location.hash)")

    def focused(self):
        return self.js("(() => { const e = document.activeElement; return e && e.closest('.xterm') ? e.closest('.pane').dataset.sid : null; })()")

    def tabs(self):
        """The tab bar as it reads: each tab's layout, in order."""
        return self.js("[...document.querySelectorAll('#tabs .tab')].map(t => t.dataset.tab)")

    def active(self):
        return self.js("(document.querySelector('#tabs .tab.on') || {dataset: {}}).dataset.tab || null")

    def open(self, route, panes=1):
        self.js(f"location.hash = {json.dumps(route)}; window.oldPage = true")
        self.call("Page.reload")
        shown = waited(lambda: self.js(f"!window.oldPage && document.querySelectorAll('.pane').length >= {panes} && !!document.querySelector('#side .nav.session')"), 30)
        self.fake()
        time.sleep(0.8)
        return shown

    def go(self, route, wait=1.0):
        self.js(f"location.hash = {json.dumps(route)}")
        time.sleep(wait)

    def fake(self, extra=None):
        if extra is not None:
            self.js(f"window.fakeState = {json.dumps(extra)}")
        self.js("""(() => {
          if (window.fakeOn) return;
          window.fakeOn = true;
          window.EventSource = undefined; if (push.source) push.source.close(); push.source = null; push.base = null;
          window.fakeState = window.fakeState || JSON.parse(localStorage.getItem('fakeState') || '{}');
          const real = window.fetch;
          window.fetch = async (url, options) => {
            const answer = await real(url, options);
            if (!String(url).includes('/api/state')) return answer;
            const data = await answer.json(), f = window.fakeState || {};
            data.sessions = data.sessions.map((s) => f[s.id] ? { ...s, ...f[s.id] } : s);
            return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
          };
        })()""")
        self.js("localStorage.setItem('fakeState', JSON.stringify(window.fakeState)); tick()")
        time.sleep(0.6)

    def settings(self, values):
        """A change made in Settings: kept by the server, then taken by the page as the Settings page takes it."""
        status, data = put_settings(values)
        self.js("loadSettings()")
        time.sleep(0.8)
        return status


sweep()
launchd_before = launchd_jobs()
had = get("/api/settings").get("values", {})
keep = {k: had[k] for k in ("feature_tabs", "feature_side_panel", "tabs_hide_single") if k in had}
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ids = []
try:
    put_settings({"feature_tabs": True, "feature_side_panel": True, "tabs_hide_single": True})
    status, made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    repo = HOME / "projects" / NAME
    for letter in "ABCDEFGHI":
        sid = get("/api/state") and api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})[1]["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": f"Pane {letter}"})
        ids.append(sid)
    A, B, C, D, E, F, G, H, I = ids
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
    STATES = {B: {"state": "needs", "asking": "Which port should the preview use?"}, C: {"state": "working", "orb": "using", "activity": {"tool": "Edit", "target": "login.py", "since": time.time() - 30}}}
    c.fake(STATES)

    # ── Tabs at a desk ──
    check("a session opens", bool(c.open(f"#/s/{A}")), c.hash())
    check("with one tab open the tab bar stays hidden", not c.js("!!document.querySelector('#tabs')") and c.js("JSON.parse(localStorage.getItem('hub.tabs')).list.length") == 1)
    c.js(f"document.querySelector('#side a.nav.session[href=\"#/s/{B}\"]').click()"); time.sleep(1)
    check("opening a second session from the sidebar opens a tab after it, and the bar shows", c.tabs() == [A, B] and c.active() == B, c.tabs())
    check("the new tab is in front, with its terminal focused", c.hash() == f"#/s/{B}" and waited(lambda: c.focused() == B, 5), [c.hash(), c.focused()])
    tab_b = f'#tabs .tab[data-tab="{B}"]'
    check("a tab shows its session's state mark: needs you", c.js(f"(() => {{ const o = document.querySelector('{tab_b} .tab-orb > *'); return !!o && (o.getAttribute('aria-label') || '').includes('Needs you'); }})()"))
    check("its title and, faint, its project", c.js(f"document.querySelector('{tab_b} .tab-t').textContent") == "Pane B" and c.js(f"document.querySelector('{tab_b} .tab-p').textContent") == NAME)
    c.js(f"document.querySelector('#side a.nav.session[href=\"#/s/{C}\"]').click()"); time.sleep(1)
    check("a working session's tab says so", c.js(f"(document.querySelector('#tabs .tab[data-tab=\"{C}\"] .tab-orb > *').getAttribute('aria-label') || '')") in ("Working", "Using a tool"))
    c.shot("01-tabs-desk")
    c.js(f"document.querySelector('#tabs .tab[data-tab=\"{A}\"] .tab-main').click()"); time.sleep(1)
    check("clicking a tab opens it", c.hash() == f"#/s/{A}" and c.active() == A and waited(lambda: c.focused() == A, 5), [c.hash(), c.active()])
    # A split belongs to its tab: adding a pane changes that tab, not the list.
    c.js(f"goLayout(layoutAdd(route().layout, '{D}'))"); time.sleep(1.2)
    check("splitting from a tab changes that tab", c.tabs() == [f"{A},{D}", B, C] and c.active() == f"{A},{D}", c.tabs())
    check("a split tab shows a split mark and how many panes", c.js(f"!!document.querySelector('#tabs .tab.on .tab-split') && document.querySelector('#tabs .tab.on .tab-p').textContent") == "2 panes")
    c.js(f"document.querySelector('#tabs .tab[data-tab=\"{C}\"] .tab-main').click()"); time.sleep(1)
    c.js(f"document.querySelector('#side a.nav.session[href=\"#/s/{D}\"]').click()"); time.sleep(1.2)
    check("a session on a split tab, opened from the sidebar, opens that tab", c.hash() == f"#/s/{A},{D}" and c.tabs() == [f"{A},{D}", B, C], [c.hash(), c.tabs()])
    check("and its pane takes the focus", waited(lambda: c.focused() == D, 5), c.focused())
    c.js(f"document.querySelector('#tabs .tab[data-tab=\"{B}\"] .tab-main').click()"); time.sleep(1)
    c.js(f"goTo('{A}')"); time.sleep(1.2)
    check("Go to does the same", c.hash() == f"#/s/{A},{D}" and waited(lambda: c.focused() == A, 5), [c.hash(), c.focused()])
    c.js(f"document.querySelector('.pane[data-sid=\"{D}\"] [data-key=close]').click()"); time.sleep(1.2)
    check("closing a pane changes the split's tab in its place", c.tabs() == [A, B, C] and c.active() == A, c.tabs())
    # Keys: ⌘ and a digit, the place; ⌘9 the last. From inside a terminal too, and nothing reaches the shell.
    waited(lambda: c.focused() == A, 5)
    c.press("2", "Digit2", META)
    check("⌘2 opens the second tab, from inside a terminal", waited(lambda: c.hash() == f"#/s/{B}", 5) and c.active() == B, c.hash())
    c.press("9", "Digit9", META)
    check("⌘9 opens the last tab", waited(lambda: c.hash() == f"#/s/{C}", 5), c.hash())
    c.press("1", "Digit1", META)
    check("⌘1 the first", waited(lambda: c.hash() == f"#/s/{A}", 5), c.hash())
    lines = subprocess.run(["tmux", "-L", os.environ["HUB_TMUX"], "capture-pane", "-p", "-t", f"hub-{A}"], capture_output=True, text=True).stdout
    check("none of those keys reached the shell", "1" not in lines.strip().split("\n")[-1].split("%")[-1] and "9" not in lines.strip().split("\n")[-1].split("%")[-1], lines.strip().split("\n")[-1:])
    # Middle-click closes a tab; the session keeps running.
    box = c.box(f'#tabs .tab[data-tab="{C}"] .tab-main')
    c.click(box["x"] + 30, box["y"] + 10, "middle"); time.sleep(0.8)
    check("a middle click closes a tab", c.tabs() == [A, B] and c.hash() == f"#/s/{A}", [c.tabs(), c.hash()])
    check("its session keeps running", next(s for s in get("/api/state")["sessions"] if s["id"] == C)["alive"])
    c.js(f"document.querySelector('#tabs .tab[data-tab=\"{B}\"] .tab-x').click()"); time.sleep(1)
    check("× closes a tab, and with one left the bar hides", not c.js("!!document.querySelector('#tabs')") and c.js("JSON.parse(localStorage.getItem('hub.tabs')).list.map(t => t.l)") == [A])
    for sid in (B, C, D):
        c.js(f"document.querySelector('#side a.nav.session[href=\"#/s/{sid}\"]').click()"); time.sleep(0.8)
    check("tabs open in the order the sessions were opened", c.tabs() == [A, B, C, D], c.tabs())
    # Dragging the first tab past the third moves it there.
    a, third = c.box(f'#tabs .tab[data-tab="{A}"]'), c.box(f'#tabs .tab[data-tab="{C}"]')
    x, y = a["x"] + 40, a["y"] + 18
    c.mouse("mouseMoved", x, y); c.mouse("mousePressed", x, y)
    for step in range(1, 13):
        c.mouse("mouseMoved", x + (third["x"] + third["w"] * 0.8 - x) * step / 12, y)
        time.sleep(0.03)
    c.mouse("mouseReleased", third["x"] + third["w"] * 0.8, y); time.sleep(0.6)
    check("dragging a tab reorders the tabs", c.tabs() == [B, C, A, D], c.tabs())
    check("and the drag doesn't open the tab it moved", c.hash() == f"#/s/{D}", c.hash())
    c.js(f"document.querySelector('#tabs .tab[data-tab=\"{B}\"] .tab-main').focus()")
    c.press("ArrowRight", mods=SHIFT)
    check("⇧→ on a tab moves it one place", c.tabs() == [C, B, A, D] and c.js("document.activeElement.closest('.tab').dataset.tab") == B, c.tabs())
    c.press("Delete")
    check("⌫ (Delete) on a tab closes it and focus stays in the bar", c.tabs() == [C, A, D] and c.js("!!document.activeElement.closest('#tabs')"), c.tabs())
    c.open(f"#/s/{A}")
    check("a reload keeps the tabs, their order and which is in front", c.tabs() == [C, A, D] and c.active() == A, [c.tabs(), c.active()])
    # Many tabs: they shrink to a floor, then the row scrolls and a button lists them all.
    for sid in (E, F, G, H, I, B):
        c.js(f"document.querySelector('#side a.nav.session[href=\"#/s/{sid}\"]').click()"); time.sleep(0.5)
    c.call("Emulation.setDeviceMetricsOverride", width=1100, height=800, deviceScaleFactor=1, mobile=False); time.sleep(0.8)
    widths = c.js("[...document.querySelectorAll('#tabs .tab')].map(t => Math.round(t.getBoundingClientRect().width))")
    check("too many tabs shrink no narrower than they can be read", widths and min(widths) >= 119, widths)
    check("the rest scroll, and a button lists every tab", c.js("(() => { const s = document.querySelector('#tabs .tabs-strip'); return s.scrollWidth > s.clientWidth && !document.querySelector('#tabs .tabs-more').hidden; })()"))
    check("the tab in front is in view", c.js("(() => { const s = document.querySelector('#tabs .tabs-strip').getBoundingClientRect(), t = document.querySelector('#tabs .tab.on').getBoundingClientRect(); return t.left >= s.left - 1 && t.right <= s.right + 1; })()"))
    c.js("document.querySelector('#tabs .tabs-more').click()"); time.sleep(0.4)
    check("the list names every tab, the one in front ticked", c.js("document.querySelectorAll('.popup.menu button').length") == 9 and c.js("!!document.querySelector('.popup.menu button.on')"))
    c.shot("02-tabs-overflow")
    c.press("Escape")
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False); time.sleep(0.5)
    # The setting: show the bar for one tab too.
    for sid in [t for t in c.tabs() if t != B]:
        c.js(f"(() => {{ const x = document.querySelector('#tabs .tab[data-tab=\"{sid}\"] .tab-x'); if (x) x.click(); }})()"); time.sleep(0.2)
    check("closing the others leaves one tab and no bar", not c.js("!!document.querySelector('#tabs')"), c.js("JSON.stringify(tabs.list)"))
    c.settings({"tabs_hide_single": False})
    check("with tabs_hide_single off, one tab shows the bar, at once", c.tabs() == [B], c.tabs())
    c.settings({"tabs_hide_single": True})

    # ── The phone ──
    for sid in (C, D):
        c.js(f"document.querySelector('#side a.nav.session[href=\"#/s/{sid}\"]').click()"); time.sleep(0.5)
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.open(f"#/s/{D}")
    check("on a phone there's no tab bar", not c.js("!!document.querySelector('#tabs')"))
    check("the top bar counts the tabs, with a mark when one needs you", c.js("document.querySelector('#top .tabs-count .tabs-n').textContent") == "3" and c.js("!!document.querySelector('#top .tabs-count .tabs-hot')"))
    c.js("document.querySelector('#top .tabs-count').click()"); time.sleep(0.5)
    sheet = c.box("dialog.tabs-sheet")
    check("it opens a sheet of the tabs across the screen's width", sheet and sheet["w"] >= 389 and c.js("document.querySelectorAll('dialog.tabs-sheet .tabs-row').length") == 3, sheet)
    check("the tab in front is marked, and each says what its session is doing", c.js("!!document.querySelector('.tabs-row.on')") and "Which port" in c.js("document.querySelector('dialog.tabs-sheet').innerText"))
    c.shot("03-phone-tabs")
    c.js("document.querySelectorAll('dialog.tabs-sheet .tabs-x')[1].click()"); time.sleep(0.5)
    check("× in the sheet closes a tab", c.js("document.querySelectorAll('dialog.tabs-sheet .tabs-row').length") == 2)
    c.js(f"document.querySelector('dialog.tabs-sheet .tabs-row a[href=\"#/s/{B}\"]').click()"); time.sleep(1)
    check("tapping a tab opens it and the sheet goes", c.hash() == f"#/s/{B}" and not c.js("!!document.querySelector('dialog.tabs-sheet[open]')"), c.hash())
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)

    # ── The side panel ──
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@git.example.com:team/hub-check.git"], capture_output=True)
    (repo / "notes" / "deep" / "folder").mkdir(parents=True, exist_ok=True)
    (repo / "notes" / "deep" / "folder" / "changed-by-the-check.md").write_text("one\ntwo\nthree\n")
    status, o = api("GET", f"/api/sessions/{A}/overview")
    check("the overview names the folder, its branch and git", status == 200 and o["folder"] == f"~/projects/{NAME}" and o["git"] and o["branch"] == "main", o)
    check("an ssh remote becomes the repository's web address", o["repo_url"] == "https://git.example.com/team/hub-check", o.get("repo_url"))
    check("the files it changed are listed with their lines", any(f["path"] == "notes/deep/folder/changed-by-the-check.md" and f["added"] == 3 and f["new"] for f in o["files"]), o["files"])
    subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", "https://someone:hunter2-token@git.example.com/team/hub-check.git"], capture_output=True)
    time.sleep(4.2)
    status, o = api("GET", f"/api/sessions/{A}/overview")
    check("a name or token in the remote is never kept", o["repo_url"] == "https://git.example.com/team/hub-check" and "hunter2" not in json.dumps(o), o.get("repo_url"))
    status, far = api("GET", f"/api/sessions/{A}/overview", headers={"X-Forwarded-For": "100.64.200.9"})
    check("a page on another device isn't on this Mac", status == 200 and far["at_mac"] is False and o["at_mac"] is True, [far.get("at_mac"), o.get("at_mac")])
    status, refused = api("POST", f"/api/sessions/{A}/reveal", {}, headers={"X-Forwarded-For": "100.64.200.9"})
    check("Open in Finder is refused for a page on another device", status >= 400 and "this Mac" in refused.get("error", ""), [status, refused])
    status, _ = api("GET", "/api/sessions/zzzzzzzz/overview")
    check("an unknown session has no overview", status >= 400, status)
    c.open(f"#/s/{A}")
    if not c.js("!!document.querySelector('.stage > .shared')"):
        c.js("pageKeys.p()"); time.sleep(0.8)
    check("the right panel is the side panel, with its tabs", waited(lambda: c.js("!!document.querySelector('.shared.side-panel .sp-tabs')"), 5))
    names = c.js("[...document.querySelectorAll('.sp-tab')].map(t => t.textContent)")
    check("Overview is its first tab, then Changes and Shared", names[:3] == ["Overview", "Changes", "Shared"], names)
    check("Overview is chosen the first time", c.js("document.querySelector('.sp-tab[aria-selected=true]').dataset.panel") == "overview")
    text = waited(lambda: c.js("(document.querySelector('.sp-overview') || {}).innerText || ''") if "main" in (c.js("(document.querySelector('.sp-overview') || {}).innerText || ''") or "") else None, 8) or ""
    check("Overview shows the folder, with Copy path and, on this Mac, Open in Finder", f"~/projects/{NAME}" in text and "Copy path" in text and "Open in Finder" in text, text[:300])
    check("the repository's web address, opening in a new tab", c.js("(() => { const a = [...document.querySelectorAll('.sp-overview a')].find(a => a.href.startsWith('https://git.example.com/team/hub-check')); return !!a && a.target === '_blank' && a.rel.includes('noopener'); })()"))
    check("the branch and the project's memory", "main" in text and c.js(f"!!document.querySelector('.sp-overview a[href=\"#/p/{NAME}/memory\"]')"), text[:300])
    check("and the session's facts", "Started" in text and "Terminal" in text, text[:300])
    c.shot("04-panel-overview")
    c.js("document.querySelector('.sp-tab[data-panel=changes]').click()"); time.sleep(1)
    check("Changes lists the changed files", waited(lambda: "changed-by-the-check.md" in (c.js("(document.querySelector('.sp-files') || {}).innerText") or ""), 5))
    c.shot("05-panel-changes")
    c.js("[...document.querySelectorAll('.sp-file')].find(b => b.textContent.includes('changed-by-the-check.md')).click()")
    check("a file opens the review at that file", waited(lambda: c.js("(() => { const r = document.querySelector('.review'); if (!r) return false; const f = [...r.querySelectorAll('.review-file')].find(s => s.getAttribute('aria-label') === 'notes/deep/folder/changed-by-the-check.md'); if (!f) return false; const top = f.getBoundingClientRect().top, d = r.querySelector('.review-diff').getBoundingClientRect().top; const v = r.querySelector('.review-diff').getBoundingClientRect(); return top >= v.top - 1 && top < v.bottom - 20 && document.activeElement && f.contains(document.activeElement); })()"), 8))
    c.press("Escape")
    c.js("document.querySelector('.sp-tab[data-panel=shared]').click()"); time.sleep(1.2)
    check("Shared shows what the panel showed before", "Subagents, images and links" in (c.js("document.querySelector('.sp-body').innerText") or "") and c.js("!!document.querySelector('.sp-body .sp-shared')"))
    # A panel another feature adds later shows at once, and goes when it says it isn't available.
    c.js("""window.dummyLeft = 0; addPanel({ id: 'dummy', title: 'Dummy', order: 30, render: (s, box) => h('p', { class: 'dummy-body', textContent: 'Dummy for ' + s.title }), leave: () => { window.dummyLeft++; } }); tick()""")
    check("a panel added later appears as a tab at once", waited(lambda: "Dummy" in c.js("[...document.querySelectorAll('.sp-tab')].map(t => t.textContent)"), 5))
    c.js("document.querySelector('.sp-tab[data-panel=dummy]').click()"); time.sleep(0.4)
    check("and draws when chosen", (c.js("(document.querySelector('.sp-body .dummy-body') || {}).textContent") or "").endswith("Pane A"))
    c.js("document.querySelector('.sp-tab[data-panel=changes]').click()"); time.sleep(0.4)
    check("leaving it lets it go", c.js("window.dummyLeft") == 1, c.js("window.dummyLeft"))
    edge = c.box(".panel-edge")
    c.mouse("mouseMoved", edge["x"], 400); c.mouse("mousePressed", edge["x"], 400)
    for step in range(1, 9):
        c.mouse("mouseMoved", edge["x"] - 15 * step, 400); time.sleep(0.03)
    c.mouse("mouseReleased", edge["x"] - 120, 400); time.sleep(0.4)
    wide = c.box(".shared")["w"]
    check("the panel's edge drags it wider, past the old panel's limit", wide > 430, wide)
    c.open(f"#/s/{A}")
    check("a reload keeps it open, as wide, on the panel last chosen", c.js("!!document.querySelector('.shared.side-panel')") and abs(c.box(".shared")["w"] - wide) < 2 and c.js("document.querySelector('.sp-tab[aria-selected=true]').dataset.panel") == "changes",
          [c.box(".shared"), c.js("(document.querySelector('.sp-tab[aria-selected=true]') || {dataset: {}}).dataset.panel")])
    # Keys: ⇧P goes into the panel, the arrows choose another, Esc goes back to the session.
    c.press("`", "Backquote", CTRL); c.press("Escape"); time.sleep(0.3)
    c.press("P", "KeyP", SHIFT)
    check("⇧P puts the focus on the panel's chosen tab", waited(lambda: c.js("document.activeElement && document.activeElement.matches('.sp-tab[aria-selected=true]')"), 3))
    c.press("ArrowRight")
    check("→ chooses the next panel", c.js("document.activeElement.dataset.panel") == "shared" and c.js("document.querySelector('.sp-tab[aria-selected=true]').dataset.panel") == "shared")
    c.press("Escape")
    check("esc goes back to the session's terminal", waited(lambda: c.focused() == A, 3), c.js("document.activeElement.className"))
    c.js("openKeys()"); time.sleep(0.3)
    sheet_text = c.js("document.querySelector('.keys-list').innerText")
    check("the keys sheet lists the tab and panel keys", "The tab in that place" in sheet_text and "Go into it" in sheet_text, sheet_text[-400:])
    c.js("document.querySelector('dialog.keys-help').close()")
    # A phone: the panel is a full screen under the top bar, never a squeezed column.
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.open(f"#/s/{A}")
    c.js("pageKeys.p()"); time.sleep(0.8)
    panel, stage = c.box(".shared.side-panel"), c.box(".stage")
    check("on a phone the panel takes the whole stage", panel and stage and abs(panel["w"] - stage["w"]) < 2 and abs(panel["h"] - stage["h"]) < 2, [panel, stage])
    c.js("document.querySelector('.sp-tab[data-panel=overview]').click()"); time.sleep(1)
    c.shot("06-phone-panel")
    c.js("document.querySelector('.sp-close').click()"); time.sleep(0.5)
    check("its × hides it", not c.js("!!document.querySelector('.stage > .shared')"))
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)

    # ── Both switched off: the hub as it was, at once ──
    c.open(f"#/s/{A}")
    if not c.js("!!document.querySelector('.stage > .shared')"):
        c.js("pageKeys.p()"); time.sleep(0.8)
    check("before: the tab bar and the side panel", c.js("!!document.querySelector('#tabs') && !!document.querySelector('.shared.side-panel')"))
    c.settings({"feature_tabs": False, "feature_side_panel": False})
    check("tabs off: no tab bar, at once", not c.js("!!document.querySelector('#tabs')"))
    check("the main area starts with the top bar again, as before", c.js("document.querySelector('#content').firstElementChild.id") == "top" and not c.js("!!document.querySelector('#content > #tabs')"), c.js("[...document.querySelector('#content').children].map(e => e.id || e.className)"))
    check("side panel off: the right panel as it was, rail first, at once", waited(lambda: c.js("(() => { const s = document.querySelector('.stage > .shared'); return !!s && !s.classList.contains('side-panel') && !s.querySelector('.sp-head') && s.firstElementChild && s.firstElementChild.classList.contains('rail'); })()"), 5))
    check("its button says what it held", c.js("!!document.querySelector('#top .icon[title=\"Agents, images and links\"]')"))
    check("the right panel keeps its old width limit", c.box(".shared")["w"] <= 560, c.box(".shared"))
    before = c.hash()
    c.press("2", "Digit2", META)
    check("⌘2 does nothing", c.hash() == before, c.hash())
    c.js("openKeys()"); time.sleep(0.3)
    sheet_text = c.js("document.querySelector('.keys-list').innerText")
    check("the keys sheet is as it was", "The tab in that place" not in sheet_text and "Go into it" not in sheet_text)
    c.js("document.querySelector('dialog.keys-help').close()")
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.open(f"#/s/{A}")
    check("on a phone, no tab count", not c.js("!!document.querySelector('.tabs-count')"))
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.open(f"#/s/{A}")
    c.settings({"feature_tabs": True, "feature_side_panel": True})
    check("on again: the tabs come back as they were, at once", len(c.tabs() or []) >= 2 and c.js("!!document.querySelector('.shared.side-panel')"), c.tabs())
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        put_settings({k: keep.get(k, True) for k in ("feature_tabs", "feature_side_panel", "tabs_hide_single")})
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
