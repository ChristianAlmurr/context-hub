#!/usr/bin/env python3
"""The pages' polish (round 4, feat/polish-pages), in headless Chrome at a desk and on a phone.

A throwaway project, hub-test-throwaway-<n>, with four plain terminals and two dream questions in its store; what the
terminals are doing is laid over /api/state in the page, so no Claude runs.
- A project's first tab is its Overview: what needs you (its asking session and its dream questions), then the prompt,
  then what runs. With nothing running there is one quiet line, never an empty panel.
- A dream question reads the same everywhere: Home's row (the question, then the project and "Dream question"), the
  Overview's, the Dreams page's and the Dream Catcher's, which groups them by project and lists its last runs.
- The sidebar folds subagents and two or more idle terminals; the card for a session that needs you names its project.
- Settings has a Terminal section; the leave-the-terminal key is under Keyboard; the custom accent is a quiet square.
- One date format: under a day relative, then "21 Nov"; a dream's file stem as "21 Nov, 2nd".
- A phone: Memory's files are one 44px picker in named groups, and the prompt's Start is 44px tall.

Runs against a second instance (the six HUB_* variables, see tests/instance.py).
Run: /usr/bin/python3 tests/pages_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, WRITE, hub, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-pages.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9343"))
failures = 0
CTRL, SHIFT, META = 2, 8, 4
Q1 = "The deploy script still names the old bucket. Should it move to the new one?"
Q2 = "Two notes disagree on when the backup runs. Which is right?"


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
        shown = waited(lambda: self.js(f"!window.oldPage && document.querySelectorAll('.pane').length >= {panes} && !!document.querySelector('#side .side-group')"), 30)
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
    now = time.time()
    dreams = hub.store_of(NAME) / "dreams"
    dreams.mkdir(parents=True, exist_ok=True)
    (dreams / "needs.json").write_text(json.dumps({"needs": [
        {"text": f"{Q1} · evidence: deploy.sh:12", "from": "2026-11-20-proposal.md", "last": "2026-11-20-proposal.md", "said": 1, "at": int(now - 7200), "who": "agent", "repo": NAME, "change": "Point it at the new bucket", "why": None, "state": "open"},
        {"text": Q2, "from": "2026-11-20-proposal.md", "last": "2026-11-20-proposal.md", "said": 1, "at": int(now - 3600), "who": "you", "repo": None, "change": None, "why": "Only you know", "state": "open"}]}))
    state = api("GET", "/api/state")
    mine = next(p for p in state["projects"] if p["name"] == NAME)
    check("the state carries a project's first dream questions, as sentences", mine["needs"] == 2 and [a["text"] for a in mine["asks"]] == [Q1, Q2], mine.get("asks"))
    check("the Dream Catcher's page lists its last runs", isinstance(api("GET", "/api/catcher").get("recent"), list))
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
    crew = {"running": 1, "total": 2, "doing": ["Read the docs"], "list": [{"id": "t2", "what": "Read the docs", "type": "Explore", "state": "running"}, {"id": "t1", "what": "Check the tests", "type": "Explore", "state": "done"}]}
    STATES = {A: {"kind": "claude", "state": "needs", "asking": "Which port should the preview use?"},
              B: {"kind": "claude", "state": "working", "activity": {"tool": "Edit", "target": "login.py", "since": now - 30}, "agents": crew},
              C: {"created": now - 7200}, D: {"created": now - 7200}}  # two terminals nobody has touched for two hours
    disp = NAME

    # ── a project's Overview ──
    c.js("window.fakeState = " + json.dumps(STATES))
    c.open(f"#/p/{NAME}", 0)
    c.fake(STATES)
    waited(lambda: c.js("!!document.querySelector('.needs-here')"), 10)
    check("a project's first tab is its Overview", c.js("document.querySelector('#top .ptab[data-key=\"tab:home\"]').firstChild.textContent") == "Overview")
    order = c.js("(() => { const top = (s) => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top : null; }; return [top('.needs-here'), top('.compose-panel'), top('.board')]; })()")
    check("it leads with what needs you, then the prompt, then what runs", order and None not in order and order[0] < order[1] < order[2], order)
    needs = c.js("[...document.querySelectorAll('.needs-here .qrow .q-t')].map(e => e.textContent)")
    check("what needs you holds its asking session and its dream questions, each as a row", needs == ["Pane A", Q1, Q2], needs)
    check("the asking session isn't listed twice", not c.js(f"!!document.querySelector('.board [data-nav=\"{A}\"]')"))
    c.shot("01-overview")

    # ── the sidebar ──
    check("subagents fold to one line until opened", c.js(f"document.querySelectorAll('#side [data-crew=\"{B}\"] .crew-row').length") == 0
          and c.js(f"(document.querySelector('#side [data-crew=\"{B}\"] .crew-word') || {{}}).textContent") == "2 subagents, 1 running")
    fold = c.js(f"(() => {{ const f = document.querySelector('#side [data-key=\"terms:{NAME}\"]'); return f ? [f.textContent, f.getAttribute('aria-expanded')] : null; }})()")
    check("two idle terminals fold into one row; a young one would not", fold == ["Terminals2", "false"] and not c.js(f"!!document.querySelector('#side [data-sid=\"{C}\"]')"), fold)
    c.js(f"document.querySelector('#side [data-key=\"terms:{NAME}\"]').click()"); time.sleep(0.4)
    check("the row opens to show them", c.js(f"!!document.querySelector('#side [data-sid=\"{C}\"]') && !!document.querySelector('#side [data-sid=\"{D}\"]')"))
    c.js(f"document.querySelector('#side [data-key=\"terms:{NAME}\"]').click()"); time.sleep(0.3)
    c.fake({**STATES, C: {"created": now - 60}}); time.sleep(1)
    check("a terminal opened a minute ago stays in view, so one idle one doesn't fold", not c.js(f"!!document.querySelector('#side [data-key=\"terms:{NAME}\"]')") and c.js(f"!!document.querySelector('#side [data-sid=\"{C}\"]')"))
    c.fake(STATES); time.sleep(0.8)

    # ── nothing running: one line, no empty panel ──
    c.fake({sid: {"state": "ended", "alive": False} for sid in ids})
    time.sleep(1.2)
    quiet = c.js("(() => { const q = document.querySelector('.board-quiet .empty-line'); return [q ? q.textContent : null, !!document.querySelector('.board'), [...document.querySelectorAll('.dash.overview .panel')].filter(p => p.children.length <= (p.querySelector(':scope > header') ? 1 : 0)).length]; })()")
    check("with nothing running the Overview says so in one line, and no panel is empty", quiet == ["Nothing is running.", False, 0], quiet)
    c.fake(STATES); time.sleep(0.8)

    # ── Home: the same row ──
    c.js("location.hash = '#/'"); time.sleep(1.5)
    row = c.js(f"(() => {{ const r = document.querySelector('.qrow[data-nav=\"n:{NAME}\"]'); return r ? [r.querySelector('.q-t').textContent, r.querySelector('.q-line').textContent.trim(), !!r.querySelector('.q-line .mark')] : null; }})()")
    check("Home's row is the question, with its project's mark and name, and how many more", row == [Q1, f"{disp} · Dream question · 1 more", True], row)

    # ── Dreams ──
    c.js(f"location.hash = '#/p/{NAME}/dreams'"); time.sleep(2.5)
    dr = c.js("(() => { const box = document.querySelector('.callout.needs'); return box ? [box.querySelector('h2').textContent, [...box.querySelectorAll('.qrow.ask-row p.q-t')].map(e => e.textContent), [...box.querySelectorAll('.need-acts button')].map(b => b.textContent)] : null; })()")
    check("Dreams lists them in the same row, with their choices", dr == ["2 dream questions", [Q1, Q2], ["Approve fix", "Reject", "Done", "Reject"]], dr)

    # ── the Dream Catcher ──
    c.js("location.hash = '#/catcher'"); time.sleep(2.5)
    ca = c.js(f"(() => {{ const w = document.querySelector('.catch-wait'); if (!w) return null; const g = w.querySelector('.catch-project[aria-label=\"{disp}\"]'); return [w.querySelector('h2').firstChild.textContent, g ? [...g.querySelectorAll('.qrow .q-t')].map(e => e.textContent) : null, g ? g.querySelector('.q-line').textContent : null, !!document.querySelector('.catcher-lead')]; }})()")
    check("the Dream Catcher says what it is and lists what waits, by project, in the same row, before it judged them", ca and ca[0] == "Waiting on you" and ca[1] == [Q1, Q2] and ca[2] == "Dream question · not checked yet" and ca[3], ca)
    c.shot("02-catcher")

    # ── a card for what needs you names its project ──
    c.js("location.hash = '#/settings/terminal'"); time.sleep(1.5)
    card = c.js(f"(() => {{ const a = document.querySelector('#alerts [data-key=\"alert:{A}\"]'); return a && a.querySelector('.alert-proj') ? a.querySelector('.alert-proj').textContent.trim() : null; }})()")
    check("the card for a session that needs you names its project", card == f"{disp} ·", card)

    # ── Settings ──
    rows = c.js("[...document.querySelectorAll('.set-row')].map(r => r.dataset.setting)")
    check("Settings has a Terminal section with the terminal's settings", c.js("document.querySelector('.set-title').textContent") == "Terminal" and rows == ["term_font_size", "term_renderer", "term_park_after", "copy_on_select", "term_triggers"], rows)
    check("it sits with Sessions in the list", c.js("[...document.querySelectorAll('.set-group')][1].innerText.includes('Terminal')"))
    c.js("location.hash = '#/settings/keyboard'"); time.sleep(0.8)
    check("the key that leaves a terminal is under Keyboard", c.js("!!document.querySelector('[data-setting=prefix_key]')"))
    c.js("location.hash = '#/settings/appearance'"); time.sleep(0.8)
    swatch = c.js("(() => { const s = getComputedStyle(document.querySelector('.swatch.own')); return [s.backgroundImage, !!document.querySelector('.swatch.own .own-plus svg')]; })()")
    check("the custom accent is a quiet square with a +, no rainbow", swatch == ["none", True], swatch)

    # ── dates ──
    year = time.strftime("%Y")
    dates = c.js("[ago(Date.now() / 1000 - 3 * 3600), stemDay('2026-11-21'), stemDay('2026-11-21-2'), stemDay('2026-11-21-3'), stemDay('2026-11-21-11')]")
    want = ["21 Nov", "21 Nov, 2nd", "21 Nov, 3rd", "21 Nov, 11th"] if year == "2026" else ["21 Nov 2026", "21 Nov 2026, 2nd", "21 Nov 2026, 3rd", "21 Nov 2026, 11th"]
    check("one date format: relative under a day, then the day; a dream's stem as its day", dates == ["3h", *want], dates)

    # ── a phone ──
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True)
    c.open(f"#/p/{NAME}/memory", 0); time.sleep(1.5)
    pick = c.js("(() => { const p = document.querySelector('.picker'); if (!p) return null; const s = p.querySelector('select'); return [Math.round(p.getBoundingClientRect().height), [...s.querySelectorAll('optgroup')].map(g => g.label), s.value.endsWith('/memory/ORG.md'), document.querySelector('.split > .list').offsetParent === null]; })()")
    check("on a phone Memory's files are one 44px picker, in named groups, in place of a chip row", pick and pick[0] >= 44 and pick[1][:2] == ["Principles", "Project"] and pick[2] and pick[3], pick)
    c.shot("03-phone-memory")
    c.js(f"location.hash = '#/p/{NAME}'"); time.sleep(1.5)
    start = c.js("Math.round(document.querySelector('.compose-panel .start').getBoundingClientRect().height)")
    check("the prompt's Start is a 44px target", start and start >= 44, start)
    c.shot("04-phone-overview")
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
