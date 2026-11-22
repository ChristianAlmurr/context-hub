#!/usr/bin/env python3
"""Getting around many sessions, end to end, in headless Chrome with real key events.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with six plain terminals. What a session
is doing (needs you, finished, working, a branch, a closed one) is laid over /api/state in the page, so no Claude runs.
- The prefix (⌃`) pressed inside a terminal: it leaves the terminal, the status line lists the next keys, and none of
  them reach the shell. n goes to the session that needs you, then the finished one; l goes back; j and k walk the
  sidebar; focus lands in the terminal it opens each time. Esc leaves you out; a page's own ⌃` with no key goes back in.
- Panes by direction and by swap, zoom (the prefix's z, a double-click on a header, Esc), kept over a reload with every
  other terminal untouched underneath.
- Six panes on a wide screen when max_panes says so, four on a narrower one.
- Boards: saved from the Split menu, listed on Home with their rolled-up mark, opened with the prefix and ⇧1, renamed,
  deleted.
- Go to (⌘K): attention order, filters, every word across name, branch and what it asks, closed sessions under a line
  with Resume, the commands it had, and how fast it filters 300 sessions.
- A phone (390 wide): a search button opens Go to full screen; the alert bar's Next goes to what needs you.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/navigation_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, TMUX, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-nav.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
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
    for letter in "ABCDEF":
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": f"Pane {letter}"})
        ids.append(sid)
    A, B, C, D, E, F = ids
    waited(lambda: all(last_line(sid) for sid in ids), 20)
    prompts = {sid: last_line(sid) for sid in ids}
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
    # C asks you something, D finished a turn you haven't read, E is at work on a branch of its own, and one closed
    # Claude session that can be resumed is listed with them.
    STATES = {C: {"state": "needs", "asking": "Which port should the preview use?"}, D: {"state": "finished", "said": "All tests pass now."},
              E: {"state": "working", "activity": {"tool": "Edit", "target": "login.py", "since": time.time() - 30}, "branch": "hub/fix-login-ab12"},
              "extra": [{"id": "0ff1ce00", "project": NAME, "title": "Pane Old", "kind": "claude", "state": "closed", "alive": False, "resumable": True, "closedAt": time.time() - 7200,
                         "created": time.time() - 9000, "note": "Done: moved the importer to its own module"}]}
    c.fake(STATES)
    pane = lambda sid: f'.pane[data-sid="{sid}"]'

    # ── The prefix, from inside a terminal ──
    check("a session opens with its terminal focused", bool(c.open(f"#/s/{A}")) and waited(lambda: c.focused() == A, 10), c.focused())
    c.press("`", "Backquote", CTRL)
    check("⌃` leaves the terminal and the status line lists the next keys", c.focused() is None and c.js("document.querySelector('#status').classList.contains('armed')")
          and all(w in c.js("document.querySelector('#status').innerText") for w in ("next for you", "last", "go to")), c.js("document.querySelector('#status').innerText"))
    c.shot("01-prefix-armed")
    c.press("Escape")
    check("esc leaves you out of the terminal, on the same page", c.focused() is None and not c.js("document.querySelector('#status').classList.contains('armed')") and c.hash() == f"#/s/{A}", c.hash())
    c.js("pageKeys.Enter()"); time.sleep(0.3)
    c.prefix("n")
    check("prefix n opens the session that needs you, with its terminal focused", c.hash() == f"#/s/{C}" and waited(lambda: c.focused() == C, 10), [c.hash(), c.focused()])
    c.prefix("n")
    check("prefix n again opens the finished one you haven't read", c.hash() == f"#/s/{D}" and waited(lambda: c.focused() == D, 10), [c.hash(), c.focused()])
    c.prefix("l")
    check("prefix l goes back to the last session", c.hash() == f"#/s/{C}" and waited(lambda: c.focused() == C, 10), [c.hash(), c.focused()])
    order = c.js("sideOrder().map((s) => s.id)")
    c.prefix("j")
    check("prefix j opens the next session in the sidebar's order", c.hash() == f"#/s/{order[(order.index(C) + 1) % len(order)]}" and waited(lambda: c.focused() is not None, 10), [c.hash(), order])
    c.prefix("k")
    check("prefix k goes back up", c.hash() == f"#/s/{C}" and waited(lambda: c.focused() == C, 10), c.hash())
    typed = {sid: last_line(sid) for sid in (A, C, D)}
    check("none of the prefix's keys reached a shell", all(typed[sid] == prompts[sid] for sid in typed), [typed, {sid: prompts[sid] for sid in typed}])
    c.press("Escape"); c.js("document.activeElement.blur()")
    c.press("`", "Backquote", CTRL)
    time.sleep(2)
    check("outside the terminal, ⌃` with no key after it goes back in, as it always did", c.focused() == C, c.focused())

    # ── Panes by direction, swap and zoom ──
    split = f"h({A},v({B},{C}))"
    check("a split of three opens", bool(c.open(f"#/s/{split}", 3)), c.hash())
    c.js(f"pageKeys.jump(0)"); time.sleep(0.3)
    c.prefix("ArrowRight")
    check("prefix → moves to the pane on the right", waited(lambda: c.focused() == B, 5), c.focused())
    c.prefix("ArrowDown")
    check("prefix ↓ moves to the pane below", waited(lambda: c.focused() == C, 5), c.focused())
    c.prefix(("ArrowLeft", "ArrowLeft", SHIFT))
    check("prefix ⇧← swaps with the pane on the left, and focus stays with the session", c.hash() == f"#/s/h({C},v({B},{A}))" and waited(lambda: c.focused() == C, 5), [c.hash(), c.focused()])
    sizes = c.js(f"[...document.querySelectorAll('.pane')].map(p => [p.dataset.sid, p.querySelector('.xterm-screen') ? p.querySelector('.xterm-screen').clientWidth : 0])")
    c.prefix("z")
    full, panes = c.box(pane(C)), c.box(".panes")
    check("prefix z zooms the pane: it fills the split and the hash keeps it", c.hash() == f"#/s/h({C},v({B},{A}))~{C}" and abs(full["w"] - panes["w"]) < 2 and abs(full["h"] - panes["h"]) < 2, [c.hash(), full, panes])
    check("the other panes are hidden, not taken away", c.js(f"[...document.querySelectorAll('.pane:not(.zoom-on)')].every(p => getComputedStyle(p).visibility === 'hidden' && p.inert && !!p.querySelector('.xterm'))"))
    check("focus is in the zoomed pane's terminal", waited(lambda: c.focused() == C, 5), c.focused())
    c.shot("02-zoomed")
    c.open(f"#/s/h({C},v({B},{A}))~{C}", 3)
    check("a reload keeps the zoom", c.js(f"document.querySelector('{pane(C)}').classList.contains('zoom-on')") and c.js("!!document.querySelector('#top .zoom-pill')"))
    c.press("`", "Backquote", CTRL); c.press("Escape")
    c.press("Escape")
    time.sleep(0.6)
    check("esc outside the terminal restores the split", c.hash() == f"#/s/h({C},v({B},{A}))" and not c.js("!!document.querySelector('.zoom-on')"), c.hash())
    after = c.js(f"[...document.querySelectorAll('.pane')].map(p => [p.dataset.sid, p.querySelector('.xterm-screen') ? p.querySelector('.xterm-screen').clientWidth : 0])")
    check("every pane has its size back", sorted(after) == sorted(sizes), [after, sizes])
    x, y = c.box(f"{pane(B)} .pane-top .name")["x"] + 20, c.box(f"{pane(B)} .pane-top")["y"] + 18
    c.mouse("mousePressed", x, y, 1); c.mouse("mouseReleased", x, y, 1); c.mouse("mousePressed", x, y, 2); c.mouse("mouseReleased", x, y, 2)
    time.sleep(0.6)
    check("a double-click on a pane's header zooms it", c.hash().endswith(f"~{B}"), c.hash())
    c.prefix("ArrowDown")
    check("moving by direction while zoomed takes the zoom along", c.hash().endswith(f"~{A}") and waited(lambda: c.focused() == A, 5), [c.hash(), c.focused()])
    c.prefix("z")
    check("prefix z again restores it", "~" not in c.hash(), c.hash())

    # ── Six panes on a wide screen ──
    six = f"h(v({A},{D}),v({B},{E}),v({C},{F}))"
    c.js("SETTINGS.max_panes = 6; window.dispatchEvent(new Event('hub:settings'))")
    c.open(f"#/s/{six}", 4)
    check("at 1440 wide a split stays at four panes", c.js("document.querySelectorAll('.pane').length") == 4, c.js("document.querySelectorAll('.pane').length"))
    c.call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
    c.js("SETTINGS.max_panes = 6")
    c.open(f"#/s/{six}", 6)
    c.js("SETTINGS.max_panes = 6; window.dispatchEvent(new Event('hub:settings')); dispatchEvent(new Event('resize')); render()")
    check("with max_panes 6 a wide screen takes six", c.js("document.querySelectorAll('.pane').length") == 6 and "6 of 6" in c.js("document.querySelector('#top').innerText"), c.js("document.querySelector('#top').innerText"))
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.js("SETTINGS.max_panes = 4; window.dispatchEvent(new Event('hub:settings'))")

    # ── Boards ──
    c.open(f"#/s/{split}", 3)
    c.js("[...document.querySelectorAll('#top .btn')].find(b => b.textContent.includes('Split')).click()"); time.sleep(0.3)
    check("the Split menu offers to save the split as a board", c.item("Save as a board"))
    time.sleep(0.3)
    c.js("(() => { const i = document.querySelector('dialog .name-input'); i.value = 'Review trio'; i.closest('form').requestSubmit(); })()")
    board = waited(lambda: next((b for b in api("GET", "/api/state").get("boards", []) if b["name"] == "Review trio"), None), 10)
    check("the board is kept on the server with its layout", bool(board) and board["layout"] == split, board)
    check("the toast says how to open it", waited(lambda: "⇧1" in (c.js("document.getElementById('toast').innerText") or ""), 5), c.js("document.getElementById('toast').innerText"))
    check("the split's top bar now carries the board's name", "Review trio" in c.js("document.querySelector('#top').innerText"))
    c.js("location.hash = '#/'"); time.sleep(1.2)
    check("Home lists the board, its sessions and the key that opens it", "Review trio" in (c.js("(document.querySelector('.board-list') || {}).innerText") or "") and "⇧1" in c.js("document.querySelector('.board-list').innerText"))
    check("its mark rolls up to needs you, since one of its sessions does", c.js("!!document.querySelector('.board-row .row-orb.s-needs')"))
    c.shot("03-home-boards")
    c.prefix(("!", "Digit1", SHIFT))
    check("prefix ⇧1 opens the board", c.hash() == f"#/s/{split}" and waited(lambda: c.focused() is not None, 10), c.hash())
    api("POST", "/api/boards", {"op": "rename", "id": board["id"], "name": "Review three"})
    c.js("tick()"); time.sleep(0.8)
    check("a rename shows in the split's top bar", "Review three" in c.js("document.querySelector('#top').innerText"))
    c.js("location.hash = '#/'"); time.sleep(1)
    c.js("document.querySelector('.board-more').click()"); time.sleep(0.3)
    c.item("Delete board"); time.sleep(0.3)
    c.js("[...document.querySelectorAll('dialog.confirm .btn')].find(b => b.textContent === 'Delete board').click()")
    check("Delete board takes it off Home and the server", waited(lambda: not api("GET", "/api/state").get("boards") and not c.js("!!document.querySelector('.board-list')"), 10))

    # ── Go to ──
    c.open(f"#/s/{A}")
    c.js(f"setRead(['{D}'], false)")  # read when prefix n opened it; unread again for the order below
    c.press("k", "KeyK", META)
    rows = c.js("[...document.querySelectorAll('dialog.palette .opt')].map(o => o.querySelector('.t').firstChild.textContent)")
    check("⌘K opens Go to with filters for Needs you, Working and Done", c.js("[...document.querySelectorAll('.goto-chip')].map(b => b.firstChild.textContent)") == ["All", "Needs you", "Working", "Done"])
    live = [r for r in rows if r.startswith("Pane ") and r != "Pane Old"]
    check("before you type, sessions come in attention order: needs you, unread, working", live[:3] == ["Pane C", "Pane D", "Pane E"], rows)
    check("it keeps its commands", all(r in rows for r in ("Home", "New project", "Keyboard shortcuts")), rows)
    check("a closed session is listed under a line, with Resume", c.js("(() => { const sep = document.querySelector('.pal-sep'); const old = [...document.querySelectorAll('.opt.past')].find(o => o.textContent.includes('Pane Old')); return !!sep && !!old && !!old.querySelector('.opt-act') && !!(sep.compareDocumentPosition(old) & 4); })()"))
    c.shot("04-goto")
    def search(text):
        c.js(f"(() => {{ const i = document.querySelector('dialog.palette input'); i.value = {json.dumps(text)}; i.dispatchEvent(new Event('input')); }})()")
        time.sleep(0.15)
        return c.js("[...document.querySelectorAll('dialog.palette .opt')].map(o => o.querySelector('.t').firstChild.textContent)")
    check("words match the branch", search("fix-login") == ["Pane E"], search("fix-login"))
    check("every word must match, across the question it asks and its name", search("preview pane") == ["Pane C"], search("preview pane"))
    check("is:working filters as the chip does", search("is:working") == ["Pane E"] and c.js("document.querySelector('.goto-chip.on').dataset.filter") == "working", search("is:working"))
    search("")
    c.js("document.querySelector('.goto-chip[data-filter=needs]').click()"); time.sleep(0.15)
    check("the Needs you chip shows only what needs you", c.js("[...document.querySelectorAll('dialog.palette .opt')].map(o => o.querySelector('.t').firstChild.textContent)") == ["Pane C"])
    search("importer")
    check("a closed session is found by its handoff", c.js("[...document.querySelectorAll('dialog.palette .opt')].map(o => o.querySelector('.t').firstChild.textContent)") == [] and "Nothing needs you" in c.js("document.querySelector('dialog.palette .results').innerText"))
    c.js("document.querySelector('.goto-chip[data-filter=all]').click()"); time.sleep(0.15)
    check("and shows once All is chosen", search("importer") == ["Pane Old"])
    check("the foot says where the chosen one lives", NAME in c.js("document.querySelector('.foot-place').textContent"))
    search("all tests")
    c.press("Enter")
    check("↵ goes to the chosen session", c.hash() == f"#/s/{D}" and waited(lambda: c.focused() == D, 10), c.hash())
    # As quick with three hundred sessions: building the list, and one keystroke's filtering.
    many = [{"id": f"{n:08x}", "project": NAME, "title": f"Load {n}", "kind": "shell", "state": "shell", "alive": True, "created": time.time() - n} for n in range(1, 301)]
    c.fake({**STATES, "extra": STATES["extra"] + many})
    took = c.js("(() => { const t0 = performance.now(); openPalette(); const t1 = performance.now(); const i = document.querySelector('dialog.palette input'); i.value = 'load 29'; i.dispatchEvent(new Event('input')); const t2 = performance.now(); document.querySelector('dialog.palette').close(); return [t1 - t0, t2 - t1]; })()")
    check("with 300 sessions it opens and filters within a frame or two", took and took[0] < 80 and took[1] < 40, took)
    c.fake(STATES)

    # ── A phone ──
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.open(f"#/s/{A}")
    check("the phone's top bar has a search button", c.js("getComputedStyle(document.querySelector('#top .find-btn')).display") != "none")
    c.js("document.querySelector('#top .find-btn').click()"); time.sleep(0.4)
    box = c.box("dialog.palette")
    check("it opens Go to across the whole screen", box and box["w"] >= 389 and box["h"] >= 800, box)
    c.shot("05-phone-goto")
    c.js("document.querySelector('dialog.palette').close()")
    nxt = waited(lambda: c.js("!!document.querySelector('#alerts.alert-bar .alert-next')"), 10)
    check("the phone's alert bar has a Next button", bool(nxt))
    c.shot("06-phone-alert-next")
    c.js("document.querySelector('#alerts .alert-next').click()"); time.sleep(0.8)
    check("Next opens the session that needs you", c.hash() == f"#/s/{C}", c.hash())
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)

    # ── The key sheet ──
    c.open(f"#/s/{A}")
    c.js("openKeys()"); time.sleep(0.3)
    check("the key sheet lists the prefix's keys under its own heading", "After ⌃`" in c.js("document.querySelector('.keys-list').innerText") and "Zoom" in c.js("document.querySelector('.keys-list').innerText"))
    c.js("document.querySelector('dialog.keys-help').close()")
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        for b in api("GET", "/api/state").get("boards", []):
            if b["name"].startswith("Review"):
                api("POST", "/api/boards", {"op": "delete", "id": b["id"]})
        for sid in ids:
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
