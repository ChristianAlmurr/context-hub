#!/usr/bin/env python3
"""Splits and closing, end to end, in headless Chrome with real pointer events.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with five plain terminals and one real
Claude session (Haiku, low effort, Skip permissions):
- Dragging sessions into a split: a sidebar row onto a pane's right half, then onto another pane's bottom half (nested),
  a pane's header onto another pane's centre (they swap), onto the whole split's edge, a fifth session refused, Esc
  cancelling a drag. Each drop is checked in the hash the page goes to.
- The gutters: dragged with the mouse and moved with the arrow keys, and both sizes still there after a reload.
- An old link, #/s/a,b,c,d, opens the old grid; each pane's split menu splits down, moves and closes from the keyboard.
- A phone (390 wide): one pane at a time with a row to switch, and the right panel shut even when the desk left it open.
- Closing the Claude session with "Commit them first": the commit lands in the throwaway repo, the handoff has its
  Committed line, and the notice shows on the page the person went to.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/split_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, re, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE, answer_first_run, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-split.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0
NOTE = "close-note.txt"
TASK = f"Create a file named {NOTE} in this folder containing the single line: hello from the split check. Then reply with the single word done."


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read() or b"{}")


def row(sid):
    return next((s for s in api("GET", "/api/state").get("sessions", []) if s["id"] == sid), None)


def waited(test, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.3)
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

    def key(self, key):
        codes = {"Enter": 13, "Escape": 27, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40}
        self.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=key, windowsVirtualKeyCode=codes[key])
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=key, windowsVirtualKeyCode=codes[key])
        time.sleep(0.15)

    def mouse(self, kind, x, y, pressed=False):
        self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left" if kind != "mouseMoved" or pressed else "none",
                  buttons=1 if pressed else 0, clickCount=1 if kind != "mouseMoved" else 0, pointerType="mouse")

    def drag(self, start, end, release=True, shot=None):
        """A mouse pressed on one point, moved to another in small steps, and let go there."""
        (x0, y0), (x1, y1) = start, end
        self.mouse("mouseMoved", x0, y0)
        self.mouse("mousePressed", x0, y0, True)
        for i in range(1, 13):
            self.mouse("mouseMoved", x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * i / 12, True)
            time.sleep(0.02)
        time.sleep(0.25)
        if shot:
            self.shot(shot)
        if release:
            self.mouse("mouseReleased", x1, y1)
            time.sleep(1.5)

    def box(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return {{x: r.left, y: r.top, w: r.width, h: r.height}}; }})()")

    def at(self, selector, fx=0.5, fy=0.5):
        b = waited(lambda: self.box(selector), 15)
        if not b:
            raise AssertionError(f"nothing at {selector}")
        return (b["x"] + b["w"] * fx, b["y"] + b["h"] * fy)

    def hash(self):
        return self.js("decodeURIComponent(location.hash)")

    def open(self, route, panes=1):
        """A page loaded afresh at a route, once it shows that many panes."""
        self.js(f"location.hash = {json.dumps(route)}; window.oldPage = true")
        self.call("Page.reload")
        shown = waited(lambda: self.js(f"!window.oldPage && document.querySelectorAll('.pane').length >= {panes} && !!document.querySelector('#side .nav.session')"), 30)
        time.sleep(1)
        return shown

    def click_item(self, words):
        """The menu item that starts with these words, clicked."""
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
    for letter in "ABCDE":
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": f"Pane {letter}"})
        ids.append(sid)
    A, B, C, D, E = ids
    claude = api("POST", "/api/sessions", {"project": NAME, "tasks": [TASK], "isolate": False, "mode": "bypassPermissions", "model": "haiku", "effort": "low"})["ids"][0]
    ids.append(claude)
    answer_first_run(claude)
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
    side = lambda sid: f'#side a.nav.session[data-drag-sid="{sid}"]'
    pane = lambda sid: f'.pane[data-sid="{sid}"]'

    # ── Dragging into a split ──
    check("a session opens on its own", bool(c.open(f"#/s/{A}")), c.hash())
    c.drag(c.at(side(B), 0.3), c.at(pane(A), 0.85), shot="01-drag-right")
    check("a sidebar row dropped on a pane's right half opens it beside, as the old a,b link", c.hash() == f"#/s/{A},{B}", c.hash())
    c.drag(c.at(side(C), 0.3), c.at(pane(B), 0.5, 0.85), shot="02-drag-down")
    check("one dropped on the bottom half of the right pane stacks it under that pane", c.hash() == f"#/s/h({A},v({B},{C}))", c.hash())
    check("the nested layout shows a column inside a row", c.js("document.querySelectorAll('.layout-split.across > .layout-split.down > .pane').length") == 2)
    c.drag(c.at(pane(A) + " .pane-top .name", 0.2), c.at(pane(C)), shot="03-swap")
    check("a pane's header dropped on another pane's centre swaps them", c.hash() == f"#/s/h({C},v({B},{A}))", c.hash())
    before = c.hash()
    c.drag(c.at(side(D), 0.3), c.at(pane(C), 0.3), release=False)
    check("while dragging, the half it would take is shown", c.js("!!document.querySelector('.drop-preview:not([hidden])')"))
    c.key("Escape")
    c.mouse("mouseReleased", *c.at(pane(C), 0.3))
    time.sleep(1)
    check("Esc cancels the drag: nothing moves and the preview is gone", c.hash() == before and not c.js("!!document.querySelector('.drop-preview')"), c.hash())
    panes = c.box(".panes")
    c.drag(c.at(side(D), 0.3), (panes["x"] + 8, panes["y"] + panes["h"] / 2), shot="04-edge")
    check("one dropped on the whole split's left edge runs its full height", c.hash() == f"#/s/h({D},{C},v({B},{A}))", c.hash())
    c.drag(c.at(side(E), 0.3), c.at(pane(A), 0.5, 0.8), release=False, shot="05-fifth")
    check("a fifth session is refused while dragging", "limit" in (c.js("(document.querySelector('.drop-preview.refused') || {}).textContent") or ""))
    c.mouse("mouseReleased", *c.at(pane(A), 0.5, 0.8))
    time.sleep(1)
    check("and dropping it changes nothing", c.hash() == f"#/s/h({D},{C},v({B},{A}))", c.hash())

    # ── Gutters ──
    check("the swap layout opens again", bool(c.open(f"#/s/h({C},v({B},{A}))", 3)), c.hash())
    gutter = c.box(".layout-split.across > .gutter")
    c.drag((gutter["x"] + 1, gutter["y"] + gutter["h"] / 2), (gutter["x"] - 200, gutter["y"] + gutter["h"] / 2))
    across = c.js("Number(document.querySelector('.layout-split.across > .gutter').getAttribute('aria-valuenow'))")
    check("dragging the gutter makes the left pane narrower", across is not None and across < 45, across)
    c.js("document.querySelector('.layout-split.down > .gutter').focus()")
    c.key("ArrowDown"); c.key("ArrowDown")
    down = c.js("Number(document.querySelector('.layout-split.down > .gutter').getAttribute('aria-valuenow'))")
    check("the arrow keys move the other gutter in steps of 5", down == 60, down)
    c.open(f"#/s/h({C},v({B},{A}))", 3)
    kept = c.js("[...document.querySelectorAll('.layout-split .gutter')].map(g => Number(g.getAttribute('aria-valuenow')))")
    check("both sizes are kept for this layout over a reload", kept == [across, 60], kept)
    c.shot("06-resized")

    # ── An old link, and the pane menu ──
    c.open(f"#/s/{A},{B},{C},{D}", 4)
    check("an old #/s/a,b,c,d link opens the old grid, two rows of two", c.js("document.querySelectorAll('.layout-split.down > .layout-split.across').length") == 2, c.hash())
    c.js(f"document.querySelector('{pane(A)} .pane-split').click()"); time.sleep(0.3)
    check("a pane's menu says four is the limit and offers Move and Close", c.js("[...document.querySelectorAll('.popup.menu button, .popup.menu .menu-group')].map(e => e.textContent)")[:1] == ["Four panes is the limit"])
    c.click_item("Close pane"); time.sleep(1.5)
    check("Close pane leaves the other three", c.hash() == f"#/s/v({B},h({C},{D}))", c.hash())
    c.js(f"document.querySelector('{pane(B)} .pane-split').click()"); time.sleep(0.3)
    c.click_item("Split down"); time.sleep(0.3)
    c.click_item(f"{NAME} · Pane E") or c.click_item("Pane E"); time.sleep(1.5)
    check("Split down… then a session puts it under the pane", c.hash() == f"#/s/v({B},{E},h({C},{D}))", c.hash())
    c.js(f"document.querySelector('{pane(E)} .pane-split').click()"); time.sleep(0.3)
    c.click_item("Move"); time.sleep(0.3)
    groups = c.js("[...document.querySelectorAll('.popup.menu .menu-group')].length")
    c.js("[...document.querySelectorAll('.popup.menu button')].filter(b => b.textContent.startsWith('To its right'))[2].click()"); time.sleep(1.5)
    check("Move… offers each other pane, and To its right moves it there", groups == 3 and c.hash() == f"#/s/v({B},h({C},{D},{E}))", [groups, c.hash()])
    c.shot("07-keyboard")

    # ── A phone ──
    c.js(f"localStorage.setItem('shared', 'true'); localStorage.setItem('panelBy', JSON.stringify({{ {json.dumps(B)}: {{ on: true }}, {json.dumps(E)}: {{ on: true }} }}))")  # the desk left both panels open
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.open(f"#/s/v({B},h({C},{D},{E}))", 4)
    time.sleep(1)
    visible = c.js("[...document.querySelectorAll('.pane')].filter(p => p.offsetParent).map(p => p.dataset.sid)")
    tabs = c.js("[...document.querySelectorAll('.pane-switch button')].map(b => b.textContent)")
    check("a phone shows one pane of the split, with a row of its four sessions", visible == [B] and len(tabs) == 4, [visible, tabs])
    check("the right panel starts shut on a phone, whatever the desk chose", not c.js("!!document.querySelector('.stage > .shared')"))
    c.js("document.querySelectorAll('.pane-switch button')[3].click()"); time.sleep(1.5)
    visible = c.js("[...document.querySelectorAll('.pane')].filter(p => p.offsetParent).map(p => p.dataset.sid)")
    check("a tap in the row switches to that session", visible == [E] and c.js("document.querySelectorAll('.pane-switch button')[3].getAttribute('aria-selected')") == "true", visible)
    check("and its panel stays shut too", not c.js("!!document.querySelector('.stage > .shared')"))
    c.js("document.querySelector('#top .icon[aria-pressed]').click()"); time.sleep(1)
    check("the panel button still opens it on the phone", c.js("!!document.querySelector('.stage > .shared')"))
    c.js("document.querySelector('#top .icon[aria-pressed]').click()"); time.sleep(1)
    check("and the desk's own choice for that pane is left as it was", c.js(f"JSON.parse(localStorage.getItem('panelBy'))[{json.dumps(E)}].on") is True and not c.js("!!document.querySelector('.stage > .shared')"))
    c.shot("08-phone")
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    time.sleep(1.5)
    check("back at a desk the splits come back", c.js("[...document.querySelectorAll('.pane')].filter(p => p.offsetParent).length") == 4 and c.js("document.querySelectorAll('.layout-split').length") == 2)

    # ── Closing with a commit ──
    done = waited(lambda: (lambda r: r if r and r["state"] == "finished" else None)(row(claude)), 180)
    check("the Claude session wrote its file and finished", bool(done) and (HOME / "projects" / NAME / NOTE).exists(), done and done.get("said"))
    c.open(f"#/s/{claude}")
    waited(lambda: c.js("!!document.querySelector('.pane .close-session')"), 20)
    c.js("document.querySelector('.pane .close-session').click()")
    sheet = waited(lambda: c.js("(document.querySelector('dialog.close-sheet') || {}).innerText"), 10) or ""
    check("the close dialog lists the uncommitted file and offers to commit first", NOTE in sheet and "Commit them first" in sheet, sheet)
    check("Commit them first is on by default", c.js("[...document.querySelectorAll('dialog.close-sheet label.check')].find(l => l.textContent.includes('Commit')).querySelector('input').checked"))
    c.js("document.querySelector('dialog.close-sheet .commit-hint').value = 'add the split check note'")
    c.shot("09-close-dialog")
    c.js("[...document.querySelectorAll('dialog.close-sheet .actions button')].find(b => b.textContent === 'Close session').click()")
    time.sleep(1.5)
    c.js("location.hash = '#/'")  # the person goes elsewhere
    closed = waited(lambda: (lambda r: r if r and r["state"] == "closed" else None)(row(claude)), 400)
    result = (closed or {}).get("closeResult") or {}
    log = subprocess.run(["git", "-C", str(HOME / "projects" / NAME), "log", "--format=%h %s", "-5", "--", NOTE], capture_output=True, text=True).stdout.split("\n")[0]
    check("the commit lands in the repo, with the file Claude made", bool(log) and any(log.startswith(c_["hash"]) for c_ in result.get("commits", [])), [log, result])
    check("the handoff has its Committed line", bool(re.search(r"^\W*Committed:", (closed or {}).get("note", ""), re.M | re.I)), (closed or {}).get("note"))
    notice = waited(lambda: (lambda t: t if t and "Closed" in t and "Committed" in t else None)(c.js("document.getElementById('toast').innerText")), 15)
    check("the notice shows on the page the person went to, with what was committed", bool(notice) and c.hash() == "#/", [notice, c.hash()])
    c.shot("10-closed-notice")
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
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
