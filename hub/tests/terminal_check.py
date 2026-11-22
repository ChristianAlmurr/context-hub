#!/usr/bin/env python3
"""The terminal's extras from herdr's most-asked, end to end, in headless Chrome with real pointer and key events.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with five plain terminals (no Claude runs).
Each feature is checked on, then with its switch off through PUT /api/settings, where it must do what the hub did before:
- Long links in one piece: a link over six rows opens whole from its first row, by a click and a ⌘-click; off, the
  first row opens only its first four rows, as before. A loopback link goes to the hub's browser when that says how.
- On a phone, ask before opening a link: a tap offers Open and Copy; off, a tap opens it at once, as before.
- Selecting text: a real drag copies at once ("clipboard"), is held for ⌘C ("manual"), or never copies ("off").
- Double-click copies a whole path; off, only the part between two slashes, as tmux's own separators say.
- Page keys: ⇧PgUp scrolls tmux's history half a screen and ⇧PgDn back; PgUp and PgDn page through Go to; held arrows
  repeat. Off, ⇧PgUp leaves the pane as it was and PgDn leaves Go to's choice where it was.
- Pane layouts: the prefix's space cycles side by side, main and stack, and grid; e evens out; o rotates; the Split menu
  lists them. Off, none of the keys moves a pane.
- Scratch terminal: the prefix's t opens a shell over the session, in its folder, in tmux session pop-<sid> that no
  list shows; hidden it keeps running; Close ends it, and asks first while a program runs in it; it ends with its
  session. Full screen on a phone. Off, no button and no key.
- Stopping a plain terminal asks the same question from its pane, a split's pane menu, the sidebar and Go to.
- Alerts from output: a line that matches a pattern is told as a notice, once, only in its pattern's project; the
  patterns editor tries a pattern on pasted output; a bad pattern is refused. Off, nothing is told.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/terminal_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, TMUX, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-terminal.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0
CTRL, SHIFT, META = 2, 8, 4
MINE = {"feature_wrapped_links": True, "feature_link_chip": False, "feature_scratch": True, "copy_on_select": "clipboard", "feature_word_copy": True,
        "feature_pane_layouts": True, "feature_page_keys": True, "feature_triggers": True, "term_triggers": []}


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None, status=False):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    r = c.getresponse()
    data = json.loads(r.read() or b"{}")
    return (r.status, data) if status else data


def waited(test, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.2)
    return None


def tmux(*args):
    return subprocess.run(TMUX + list(args), capture_output=True, text=True)


def screen(target):
    return tmux("capture-pane", "-p", "-J", "-t", target).stdout


def typed(sid, text):
    tmux("send-keys", "-t", f"hub-{sid}", "-l", text)
    tmux("send-keys", "-t", f"hub-{sid}", "Enter")


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

    def key(self, key, code, vk, mods=0, text=None, repeat=False):
        down = dict(type="keyDown", key=key, code=code, modifiers=mods, windowsVirtualKeyCode=vk, autoRepeat=repeat)
        if text:
            down["text"] = text
        self.call("Input.dispatchKeyEvent", **down)
        if not repeat:
            self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, modifiers=mods, windowsVirtualKeyCode=vk)
        time.sleep(0.12)

    def prefix(self, key, code, vk, mods=0):
        self.key("`", "Backquote", 192, CTRL)
        self.key(key, code, vk, mods, text=key if len(key) == 1 and not mods & (CTRL | META) else None)
        time.sleep(0.6)

    def hash(self):
        return self.js("decodeURIComponent(location.hash)")

    def open(self, route, panes=1):
        self.js(f"location.hash = {json.dumps(route)}; window.oldPage = true")
        self.call("Page.reload")
        shown = waited(lambda: self.js(f"!window.oldPage && document.querySelectorAll('.pane').length >= {panes} && [...liveTerms].filter((t) => t.link === 'open').length >= {panes}"), 30)
        self.stubs()
        time.sleep(0.8)
        return shown

    def stubs(self):
        """What the page opens and copies, kept where the test can read them: headless Chrome has no clipboard to write."""
        self.js("window.opened = []; window.open = (u) => { window.opened.push(u); return null; };"
                "window.copiedTexts = []; navigator.clipboard.writeText = (t) => { window.copiedTexts.push(t); return Promise.resolve(); };")

    def settings(self, **values):
        api("PUT", "/api/settings", values)
        self.js("loadSettings()")
        time.sleep(0.5)

    def cell(self, sid, needle, nth=0, offset=0, pop=False):
        """Where on screen a piece of text sits in a session's terminal: the middle of its character at `offset`."""
        return self.js(f"""(() => {{
          const st = [...liveTerms].find((t) => t.session.id === {json.dumps(sid)} && !!t.session.pop === {json.dumps(pop)}); if (!st) return null;
          const t = st.term, b = t.buffer.active, el = t.element.querySelector('.xterm-screen').getBoundingClientRect();
          let seen = 0;
          for (let y = 0; y < t.rows; y++) {{ const line = b.getLine(b.viewportY + y); if (!line) continue; const s = line.translateToString(true); const i = s.indexOf({json.dumps(needle)});
            if (i >= 0 && seen++ === {nth}) return {{ x: el.left + (i + {offset} + 0.5) * el.width / t.cols, y: el.top + (y + 0.5) * el.height / t.rows, row: y, cols: t.cols }}; }}
          return null; }})()""")

    def click(self, at, mods=0, clicks=1):
        self.call("Input.dispatchMouseEvent", type="mouseMoved", x=at["x"], y=at["y"], modifiers=mods)
        time.sleep(0.3)
        for n in range(1, clicks + 1):
            self.call("Input.dispatchMouseEvent", type="mousePressed", x=at["x"], y=at["y"], button="left", buttons=1, clickCount=n, modifiers=mods)
            self.call("Input.dispatchMouseEvent", type="mouseReleased", x=at["x"], y=at["y"], button="left", buttons=0, clickCount=n, modifiers=mods)
        time.sleep(0.4)

    def drag(self, a, b):
        self.call("Input.dispatchMouseEvent", type="mouseMoved", x=a["x"], y=a["y"])
        self.call("Input.dispatchMouseEvent", type="mousePressed", x=a["x"], y=a["y"], button="left", buttons=1, clickCount=1)
        for i in range(1, 7):
            self.call("Input.dispatchMouseEvent", type="mouseMoved", x=a["x"] + (b["x"] - a["x"]) * i / 6, y=a["y"] + (b["y"] - a["y"]) * i / 6, button="left", buttons=1)
            time.sleep(0.04)
        self.call("Input.dispatchMouseEvent", type="mouseReleased", x=b["x"], y=b["y"], button="left", buttons=0, clickCount=1)
        time.sleep(0.8)

    def tap(self, at):
        self.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": at["x"], "y": at["y"]}])
        time.sleep(0.05)
        self.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
        time.sleep(0.6)

    def dialog_text(self):
        return self.js("(() => { const d = document.querySelector('dialog.confirm[open]'); return d ? d.innerText : null; })()")

    def answer(self, word):
        self.js(f"(() => {{ const b = [...document.querySelectorAll('dialog.confirm[open] button')].find((b) => b.textContent.trim() === {json.dumps(word)}); if (b) b.click(); }})()")
        time.sleep(0.5)

    def item(self, words):
        return self.js(f"(() => {{ const b = [...document.querySelectorAll('.popup.menu button')].find(b => b.textContent.startsWith({json.dumps(words)})); if (b) b.click(); return !!b; }})()")


def desk(c):
    c.call("Emulation.setTouchEmulationEnabled", enabled=False)
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)


def phone(c):
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)


sweep()
launchd_before = launchd_jobs()
before = api("GET", "/api/settings")["values"]
profile = tempfile.mkdtemp(prefix="hub-chrome.")
work = Path(tempfile.mkdtemp(prefix="hub-terminal-files."))
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ids = []
try:
    api("PUT", "/api/settings", {**MINE, "theme": "dark"})
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    for letter in "ABCDE":
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": f"Term {letter}"})
        ids.append(sid)
    A, B, C, D, E = ids
    waited(lambda: all(screen(f"hub-{sid}").strip() for sid in ids), 20)

    # ── The server's side, without a page ──
    code, said = api("PUT", "/api/settings", {"term_triggers": [{"pattern": "(unclosed", "project": ""}]}, status=True)
    check("a pattern that doesn't compile is refused, saying why", code >= 400 and "pattern" in json.dumps(said), [code, said])
    code, said = api("PUT", "/api/settings", {"term_triggers": [{"pattern": "x", "project": "Not A Project"}]}, status=True)
    check("a pattern's project must be a project's name", code >= 400, [code, said])
    tried = api("POST", "/api/terminal/test", {"pattern": "error|failed", "text": "all good\nBuild FAILED\nnpm ERR! error"})
    check("trying a pattern finds the lines it would tell, without case", tried.get("ok") and tried.get("lines") == ["Build FAILED", "npm ERR! error"], tried)
    check("trying a broken pattern says what's wrong", api("POST", "/api/terminal/test", {"pattern": "(", "text": "x"}).get("ok") is False)
    check("a double-click takes a whole path while the switch is on (tmux's word-separators)", waited(lambda: "/" not in tmux("show-options", "-gv", "word-separators").stdout, 6), tmux("show-options", "-gv", "word-separators").stdout)
    check("⇧PgUp and ⇧PgDn are bound in tmux while page keys are on", waited(lambda: "S-PPage" in tmux("list-keys", "-T", "root").stdout, 6))
    api("PUT", "/api/settings", {"feature_word_copy": False, "feature_page_keys": False})
    check("off, tmux's own word-separators are back", waited(lambda: "/" in tmux("show-options", "-gv", "word-separators").stdout, 6), tmux("show-options", "-gv", "word-separators").stdout)
    check("off, ⇧PgUp and ⇧PgDn are tmux's defaults again", waited(lambda: "S-PPage" not in tmux("list-keys").stdout, 6))
    api("PUT", "/api/settings", {"feature_word_copy": True, "feature_page_keys": True})
    waited(lambda: "S-PPage" in tmux("list-keys", "-T", "root").stdout, 6)
    sessions_before = len(api("GET", "/api/state")["sessions"])
    opened = api("POST", "/api/terminal/scratch", {"sid": A, "op": "open"})
    check("a scratch shell opens in the session's folder", opened.get("alive") and opened.get("folder", "").endswith(NAME) and f"pop-{A}" in tmux("ls", "-F", "#{session_name}").stdout, opened)
    check("no list shows the scratch shell as a session", len(api("GET", "/api/state")["sessions"]) == sessions_before and api("GET", "/api/terminal/scratch").get("live") == [A])
    code, said = api("POST", "/api/terminal/scratch", {"sid": "zzzz", "op": "open"}, status=True)
    check("a scratch shell needs a real session", code >= 400, [code, said])
    api("POST", "/api/terminal/scratch", {"sid": A, "op": "close"})
    check("Close ends the scratch shell", f"pop-{A}" not in tmux("ls", "-F", "#{session_name}").stdout)

    # ── The page ──
    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    desk(c)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)
    c.js("localStorage.clear()")

    # ── Long links in one piece ──
    url = "https://example.com/" + "/".join(f"segment{i:03d}-of-a-long-link" for i in range(40)) + "?end=1"
    (work / "link.txt").write_text(f"see {url} there\nlocal http://127.0.0.1:5173/preview/page there\n")
    check("the page opens on a session", bool(c.open(f"#/s/{A}")))
    typed(A, f"clear; cat {work / 'link.txt'}")  # after the page has the terminal at its size, so nothing reflows
    first = waited(lambda: c.cell(A, "see https://", offset=8), 10)
    rows = c.js(f"Math.ceil({len(url) + 4} / [...liveTerms][0].term.cols)")
    check("the link runs over more than four rows", first and rows > 4, [first, rows, screen(f"hub-{A}")[:300]])
    c.click(first)
    check("a click on its first row opens the whole link", c.js("window.opened") == [url], c.js("window.opened"))
    c.js("window.opened = []")
    c.click(first, mods=META)
    check("a ⌘-click opens the whole link too", c.js("window.opened") == [url], c.js("window.opened"))
    c.shot("01-desk-long-link")
    c.js("window.opened = []; window.realBrowser = window.hubBrowser; window.hubBrowser = { ...(window.hubBrowser || {}), open: ({ url }) => { window.inHub = url; } }")
    c.click(c.cell(A, "http://127.0.0.1", offset=4))
    check("a loopback link opens in the hub's browser when it says how", c.js("window.inHub") == "http://127.0.0.1:5173/preview/page" and not c.js("window.opened"), [c.js("window.inHub"), c.js("window.opened")])
    c.settings(feature_wrapped_links=False)
    c.js("window.opened = []; window.inHub = null")
    c.click(first)
    cut = c.js("window.opened")
    check("off: the first row opens what four rows hold, as before", len(cut) == 1 and url.startswith(cut[0]) and len(cut[0]) < len(url), cut)
    c.js("window.opened = []")
    c.click(c.cell(A, "http://127.0.0.1", offset=4))
    check("off: a loopback link opens as any link did", c.js("window.opened") == ["http://127.0.0.1:5173/preview/page"] and not c.js("window.inHub"), [c.js("window.opened"), c.js("window.inHub")])
    c.settings(feature_wrapped_links=True)
    c.js("window.hubBrowser = window.realBrowser")

    # ── On a phone, ask before opening a link ──
    phone(c)
    c.settings(feature_link_chip=True)
    check("the session opens on a phone", bool(c.open(f"#/s/{A}")))
    typed(A, f"clear; cat {work / 'link.txt'}")
    at = waited(lambda: c.cell(A, "see https://", offset=8), 10)
    c.tap(at)
    check("a tap on a link offers Open and Copy, and opens nothing yet", c.js("!!document.querySelector('.link-chip')") and not c.js("window.opened")
          and c.js("[...document.querySelectorAll('.link-chip button')].map((b) => b.textContent).join()") == "Open,Copy", c.js("window.opened"))
    c.shot("02-phone-link-chip")
    c.js("[...document.querySelectorAll('.link-chip button')].find((b) => b.textContent === 'Copy').click()"); time.sleep(0.3)
    check("Copy copies the whole link", c.js("window.copiedTexts") == [url], c.js("window.copiedTexts"))
    c.tap(at)
    c.js("[...document.querySelectorAll('.link-chip button')].find((b) => b.textContent === 'Open').click()"); time.sleep(0.3)
    check("Open opens it", c.js("window.opened") == [url] and not c.js("!!document.querySelector('.link-chip')"), c.js("window.opened"))
    c.settings(feature_link_chip=False)
    c.js("window.opened = []")
    c.tap(at)
    tapped = c.js("window.opened")
    check("off: a tap opens the link at once, as before (and only what four rows hold)", len(tapped) == 1 and url.startswith(tapped[0]) and not c.js("!!document.querySelector('.link-chip')"), tapped)

    # ── Scratch on a phone: the whole screen ──
    c.js("pageKeys.scratch()")
    waited(lambda: c.js("!!document.querySelector('.scratch .xterm')"), 10)
    box = c.js("(() => { const r = document.querySelector('.scratch').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    check("on a phone the scratch terminal fills the screen", box and box[0] == 0 and box[1] == 0 and box[2] == 390 and box[3] >= 800, box)
    c.shot("03-phone-scratch")
    c.js("hideScratch()")
    desk(c)

    # ── Selecting text ──
    (work / "words.txt").write_text("copy-me-please and more\nopen ~/projects/demo/src/app-main now\n")
    check("a second session opens", bool(c.open(f"#/s/{B}")))
    typed(B, f"clear; cat {work / 'words.txt'}")
    start = waited(lambda: c.cell(B, "copy-me-please"), 10)
    end = c.cell(B, "copy-me-please", offset=14)  # tmux leaves out the cell the pointer lets go on
    c.drag(start, end)
    check("a drag copies what it selects when you let go (Copies it)", waited(lambda: c.js("window.copiedTexts.includes('copy-me-please')"), 5), c.js("window.copiedTexts"))
    c.settings(copy_on_select="manual")
    c.js("window.copiedTexts = []")
    c.drag(start, end)
    check("Copy with ⌘C: a drag copies nothing yet, and says it's held", not c.js("window.copiedTexts.length") and c.js("!document.querySelector('.pane .term-held').hidden"), c.js("window.copiedTexts"))
    c.shot("04-held-for-copy")
    c.key("c", "KeyC", 67, META)
    check("⌘C copies what was selected", waited(lambda: c.js("window.copiedTexts.includes('copy-me-please')"), 4) and c.js("document.querySelector('.pane .term-held').hidden"), c.js("window.copiedTexts"))
    c.settings(copy_on_select="off")
    c.js("window.copiedTexts = []")
    c.drag(start, end)
    c.key("c", "KeyC", 67, META)
    check("Never copies: neither the drag nor ⌘C copies", not c.js("window.copiedTexts.length") and c.js("document.querySelector('.pane .term-held').hidden"), c.js("window.copiedTexts"))
    c.settings(copy_on_select="clipboard")
    c.js("window.copiedTexts = []")
    path_at = c.cell(B, "~/projects", offset=13)
    c.click(path_at, clicks=2)
    check("a double-click copies the whole path", waited(lambda: c.js("window.copiedTexts.includes('~/projects/demo/src/app-main')"), 4), c.js("window.copiedTexts"))
    c.settings(feature_word_copy=False)
    waited(lambda: "/" in tmux("show-options", "-gv", "word-separators").stdout, 6)
    c.js("window.copiedTexts = []")
    path_at = c.cell(B, "~/projects", offset=13)
    c.click(path_at, clicks=2)
    got = waited(lambda: c.js("window.copiedTexts"), 4) or []
    check("off: a double-click copies only the part between slashes, as before", got and got[-1] == "demo", got)
    c.settings(feature_word_copy=True)

    # ── Page keys ──
    check("a third session opens", bool(c.open(f"#/s/{C}")))
    typed(C, "clear; seq 1 400")
    waited(lambda: "400" in screen(f"hub-{C}"), 5)
    mode = lambda: tmux("display-message", "-p", "-t", f"hub-{C}", "#{pane_in_mode} #{scroll_position} #{pane_height}").stdout.split()
    c.js("[...liveTerms][0].term.focus()")
    c.key("PageUp", "PageUp", 33, SHIFT)
    now = waited(lambda: mode()[0] == "1" and mode(), 4) or mode()
    check("⇧PgUp scrolls the history half a screen", now[0] == "1" and abs(int(now[1]) - int(now[2]) // 2) <= 1, now)
    c.key("PageUp", "PageUp", 33, SHIFT)
    twice = mode()
    c.key("PageDown", "PageDown", 34, SHIFT)
    check("⇧PgDn scrolls back half a screen", int(mode()[1]) == int(twice[1]) - int(twice[2]) // 2 or abs(int(mode()[1]) - int(now[1])) <= 1, [twice, mode()])
    tmux("send-keys", "-t", f"hub-{C}", "-X", "cancel")
    c.settings(feature_page_keys=False)
    c.js("[...liveTerms][0].term.focus()")
    c.key("PageUp", "PageUp", 33, SHIFT)
    time.sleep(0.5)
    check("off: ⇧PgUp leaves the pane as it was", mode()[0] == "0", mode())
    c.settings(feature_page_keys=True)
    c.js("openPalette()"); time.sleep(0.5)
    chosen = lambda: c.js("[...document.querySelectorAll('.palette .opt')].findIndex((o) => o.classList.contains('on'))")
    c.key("PageDown", "PageDown", 34)
    paged = chosen()
    check("PgDn pages down Go to's list", paged > 3, paged)
    c.key("PageUp", "PageUp", 33)
    check("PgUp pages back up", chosen() == 0, chosen())
    for _ in range(3):
        c.key("ArrowDown", "ArrowDown", 40, repeat=True)
    check("a held arrow repeats in Go to", chosen() == 3, chosen())
    c.js("document.querySelector('dialog.palette').close()")
    c.settings(feature_page_keys=False)
    c.js("openPalette()"); time.sleep(0.5)
    c.key("PageDown", "PageDown", 34)
    check("off: PgDn leaves Go to's choice where it was", chosen() == 0, chosen())
    c.js("document.querySelector('dialog.palette').close()")
    c.settings(feature_page_keys=True)

    # ── Pane layouts ──
    check("a split of four opens", bool(c.open(f"#/s/{A},{B},{C},{D}", 4)))
    c.prefix(" ", "Space", 32)
    check("the prefix's space lays the panes side by side", c.hash() == f"#/s/h({A},{B},{C},{D})", c.hash())
    c.prefix(" ", "Space", 32)
    check("again: main and stack", c.hash() == f"#/s/h({A},v({B},{C},{D}))", c.hash())
    c.shot("05-main-and-stack")
    sizes = lambda: c.js(f"JSON.parse(localStorage.getItem('hub.layoutSizes') || localStorage.getItem('layoutSizes') || '{{}}')[{json.dumps(f'h({A},v({B},{C},{D}))')}]")
    c.prefix("e", "KeyE", 69)
    check("the prefix's e evens out the sizes", (sizes() or [[0]])[0] == [0.5, 0.5], sizes())
    c.prefix("o", "KeyO", 79)
    check("the prefix's o rotates the panes, every one a place on", c.hash() == f"#/s/h({D},v({A},{B},{C}))", c.hash())
    c.prefix(" ", "Space", 32)
    check("space once more: the grid", c.hash() == f"#/s/{D},{A},{B},{C}", c.hash())
    c.js("document.querySelector('#top .btn:not(.zoom-pill)').click()"); time.sleep(0.3)
    listed = c.js("[...document.querySelectorAll('.popup.menu button')].map((b) => b.textContent)")
    check("the Split menu lists the layouts and Rotate", all(any(x.startswith(w) for x in listed) for w in ("Side by side", "Main and stack", "Grid", "Rotate")), listed)
    c.key("Escape", "Escape", 27)
    c.settings(feature_pane_layouts=False)
    was = c.hash()
    for k in ((" ", "Space", 32), ("e", "KeyE", 69), ("o", "KeyO", 79)):
        c.prefix(*k)
    check("off: the prefix's space, e and o move no pane", c.hash() == was, c.hash())
    c.js("document.querySelector('#top .btn:not(.zoom-pill)').click()"); time.sleep(0.3)
    check("off: the Split menu is as it was", not c.js("[...document.querySelectorAll('.popup.menu button')].some((b) => b.textContent.startsWith('Rotate'))"))
    c.key("Escape", "Escape", 27)
    c.settings(feature_pane_layouts=True)

    # ── Scratch terminal ──
    check("one session opens", bool(c.open(f"#/s/{A}")))
    check("its header has a scratch button", c.js("!!document.querySelector('.pane-top .pane-scratch')"))
    c.prefix("t", "KeyT", 84)
    check("the prefix's t opens the scratch terminal over the session", waited(lambda: c.js("!!document.querySelector('.scratch .xterm') && [...liveTerms].some((t) => t.session.pop && t.link === 'open')"), 10))
    check("it says the session's folder", NAME in (c.js("document.querySelector('.scratch-where').title") or ""))
    c.js("[...liveTerms].find((t) => t.session.pop).term.focus()")
    c.call("Input.insertText", text="echo scratch-$((6*7))")
    c.key("Enter", "Enter", 13, text="\r")
    check("what's typed runs in the scratch shell, not the session", waited(lambda: "scratch-42" in screen(f"pop-{A}"), 6) and "scratch-42" not in screen(f"hub-{A}"), screen(f"pop-{A}")[-200:])
    check("the session's pane keeps its place under it", c.js("document.querySelectorAll('.pane').length") == 1 and c.hash() == f"#/s/{A}")
    c.shot("06-desk-scratch")
    c.prefix("t", "KeyT", 84)
    check("the prefix's t again hides it, and it keeps running", not c.js("!!document.querySelector('.scratch')") and f"pop-{A}" in tmux("ls", "-F", "#{session_name}").stdout)
    check("the button marks a scratch shell running", waited(lambda: c.js("!!document.querySelector('.pane-top .pane-scratch.live')"), 4))
    c.js("document.querySelector('.pane-top .pane-scratch').click()")
    waited(lambda: c.js("!!document.querySelector('.scratch .xterm')"), 6)
    check("shown again, it is the same shell", waited(lambda: "scratch-42" in c.js("[...liveTerms].find((t) => t.session.pop).term.buffer.active.getLine(0) ? [...Array(30)].map((_, i) => ([...liveTerms].find((t) => t.session.pop).term.buffer.active.getLine(i) || {translateToString: () => ''}).translateToString(true)).join('\\n') : ''"), 6))
    c.js("document.querySelector('[data-key=scratch-hide]').focus()")
    c.key("Escape", "Escape", 27)
    check("Esc hides it when the keys aren't in the shell", not c.js("!!document.querySelector('.scratch')") and c.hash() == f"#/s/{A}", c.hash())
    c.js("pageKeys.scratch()")
    waited(lambda: c.js("!!document.querySelector('.scratch .xterm')"), 6)
    tmux("send-keys", "-t", f"pop-{A}", "sleep 60", "Enter")
    waited(lambda: "sleep" in tmux("display-message", "-p", "-t", f"pop-{A}", "#{pane_current_command}").stdout, 5)
    c.js("document.querySelector('[data-key=scratch-close]').click()"); time.sleep(0.8)
    asked = c.dialog_text()
    check("Close asks first while a program runs in it", asked and "sleep" in asked and "Stop" in asked, asked)
    c.answer("Keep running")
    check("Keep running keeps it", f"pop-{A}" in tmux("ls", "-F", "#{session_name}").stdout and c.js("!!document.querySelector('.scratch')"))
    c.js("document.querySelector('[data-key=scratch-close]').click()"); time.sleep(0.8)
    c.answer("Stop")
    check("Stop ends it", waited(lambda: f"pop-{A}" not in tmux("ls", "-F", "#{session_name}").stdout, 5) and not c.js("!!document.querySelector('.scratch')"))
    api("POST", "/api/terminal/scratch", {"sid": E, "op": "open"})
    api("POST", f"/api/sessions/{E}/stop", {})
    check("a scratch shell ends with its session", waited(lambda: f"pop-{E}" not in tmux("ls", "-F", "#{session_name}").stdout, 8))
    c.settings(feature_scratch=False)
    c.open(f"#/s/{A}")
    c.prefix("t", "KeyT", 84)
    check("off: no scratch button, and the prefix's t opens nothing", not c.js("!!document.querySelector('.pane-top .pane-scratch')") and not c.js("!!document.querySelector('.scratch')"))
    c.settings(feature_scratch=True)

    # ── Stopping a plain terminal asks the same question everywhere ──
    asks = {}
    c.open(f"#/s/{D}")
    c.js("document.querySelector('.pane-top [data-key=stop]').click()"); time.sleep(0.6)
    asks["pane"] = c.dialog_text(); c.answer("Keep running")
    c.js(f"sessionMenu(document.querySelector('#side [data-sid=\"{D}\"] a') || document.body, session('{D}'))"); time.sleep(0.3)
    c.item("Stop terminal"); time.sleep(0.6)
    asks["sidebar"] = c.dialog_text(); c.answer("Keep running")
    c.js("openPalette()"); time.sleep(0.4)
    c.js("[...document.querySelectorAll('.palette .opt')].find((o) => o.textContent.startsWith('Stop terminal')).click()"); time.sleep(0.6)
    asks["go to"] = c.dialog_text(); c.answer("Keep running")
    c.open(f"#/s/{C},{D}", 2)
    c.js(f"document.querySelector('.pane[data-sid=\"{D}\"] .pane-split').click()"); time.sleep(0.3)
    c.item("Stop terminal"); time.sleep(0.6)
    asks["split"] = c.dialog_text(); c.answer("Keep running")
    check("the pane, a split's menu, the sidebar and Go to ask the same question", asks["pane"] and len(set(asks.values())) == 1 and "Term D”?" in asks["pane"], {k: (v or "")[:40] for k, v in asks.items()})
    check("Keep running keeps it running", any(s["id"] == D and s["alive"] for s in api("GET", "/api/state")["sessions"]))
    c.shot("07-stop-question")

    # ── Alerts from output ──
    c.open("#/settings/terminal")  # the patterns sit in Settings › Terminal (round 4); the switch stays in Features
    c.js("document.querySelector('[data-key=triggers-edit]').click()"); time.sleep(0.3)
    c.js("(() => { const i = document.querySelector('.trigger-row input'); i.value = 'deploy (failed|broke)'; i.dispatchEvent(new Event('input')); const t = document.querySelector('[data-key=trigger-sample]'); t.value = 'step 1 ok\\ndeploy failed at 12:01'; t.dispatchEvent(new Event('input')); })()")
    check("the editor tries the pattern on pasted output", waited(lambda: "1 line" in (c.js("document.querySelector('.trigger-result').innerText") or ""), 5), c.js("document.querySelector('.trigger-result').innerText"))
    c.shot("08-patterns-editor")
    c.js("document.querySelector('[data-key=trigger-keep]').click()"); time.sleep(0.8)
    check("Keep saves it", api("GET", "/api/settings")["values"]["term_triggers"] == [{"pattern": "deploy (failed|broke)", "project": ""}], api("GET", "/api/settings")["values"]["term_triggers"])
    c.js("location.hash = '#/'"); time.sleep(1)
    typed(B, "clear; echo deploy failed: $((40+2)) reasons")
    told = waited(lambda: c.js("(() => { const n = document.querySelector('[data-notice^=\"t:\"]'); return n ? n.innerText : null; })()"), 12)
    check("a matching line is told as a notice, with the line", told and "deploy failed: 42 reasons" in told, told)
    hits = api("GET", "/api/state").get("triggers", [])
    check("the server kept it, with its session and pattern", any(h["sid"] == B and h["pattern"] == "deploy (failed|broke)" for h in hits), hits)
    c.shot("09-alert-notice")
    count = len(hits)
    typed(B, "clear; echo deploy failed: $((40+2)) reasons")
    time.sleep(4)
    check("the same line again isn't told twice", len(api("GET", "/api/state").get("triggers", [])) == count, api("GET", "/api/state").get("triggers"))
    api("PUT", "/api/settings", {"term_triggers": [{"pattern": "only-here-\\d+", "project": "hub-test-throwaway-0"}]})
    time.sleep(2)
    typed(B, "echo only-here-7")
    time.sleep(4)
    check("a pattern for another project stays quiet here", len(api("GET", "/api/state").get("triggers", [])) == count)
    api("PUT", "/api/settings", {"term_triggers": [{"pattern": "deploy (failed|broke)", "project": NAME}], "feature_triggers": False})
    c.js("loadSettings()")
    time.sleep(2)
    typed(B, "echo deploy broke twice")
    time.sleep(4)
    check("off: nothing is told", len(api("GET", "/api/state").get("triggers", [])) == count and not c.js("!!document.querySelector('[data-notice^=\"t:\"]') && document.querySelector('[data-notice^=\"t:\"]').innerText.includes('twice')"))
    api("PUT", "/api/settings", {"feature_triggers": True})
    time.sleep(2)
    typed(C, "echo deploy broke a third time")
    check("on again, in its own project, it tells", waited(lambda: any("third" in h["line"] for h in api("GET", "/api/state").get("triggers", [])), 10))
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
        api("PUT", "/api/settings", {name: before.get(name, value) for name, value in {**MINE, "theme": "dark"}.items()})
        for sid in ids:
            tmux("kill-session", "-t", f"=pop-{sid}")
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
