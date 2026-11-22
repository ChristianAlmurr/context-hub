#!/usr/bin/env python3
"""The session view's chrome and its questions (polish-session), in headless Chrome, at a desk and on a phone.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with four plain terminals. Three are laid
over /api/state in the page as Claude sessions (working, asking a permission, asking a question), and their /peek and
/record answer in the page too, so no Claude runs.
- Two bars above a session: the tabs in the top bar's row at a desk (76px), the top bar and the pane head on a phone
  (88px), the strip folded into the pane head, and the same with tabs off.
- The pane head: one control height, one control with a ring (Chat|Terminal), Close session in ⋯, no Split in the header
  at a desk while each pane's split menu holds the whole split's actions.
- A turn over an hour old says since when, quietly.
- While Claude asks in a chat: one text field, one send, the question said once, its title 18px at weight 500.
- The side panel's tabs: words for reading, icons for tools, and the chosen one always in view, at 280px.
- The phone's counts on the menu button. Tabs or the side panel switched off: nothing of theirs, and nothing lost.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/session_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-session.")); OUT.mkdir(parents=True, exist_ok=True)
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
            const m = String(url).match(new RegExp('/api/sessions/([0-9a-f]{8})/(peek|record)$')), p = window.fakePeek || {};
            if (m && p[m[1]]) return new Response(JSON.stringify(m[2] === 'peek' ? p[m[1]] : window.fakeRecord), { status: 200, headers: { 'Content-Type': 'application/json' } });
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




def chrome_height(c):
    """How far the first pane's content starts below the top of the main area, less what only tells or asks: the update
    banner and a card for another session that needs you."""
    return c.js("""(() => { const content = document.querySelector('#content').getBoundingClientRect().top;
      const pane = document.querySelector('.pane:not(.away)'), head = pane.querySelector('.pane-top');
      const told = [...document.querySelectorAll('#content > .banner, #content > #alerts')].reduce((n, e) => n + e.offsetHeight, 0);
      return Math.round(head.getBoundingClientRect().bottom - content - told); })()""")


def bars(c):
    """The horizontal bars stacked above the first pane, by what they are."""
    return c.js("""(() => { const out = [], top = document.querySelector('#top'), tabs = document.querySelector('#content > #tabs');
      if (tabs) out.push('tabs'); if (top && top.offsetHeight) out.push('top');
      const alerts = [...document.querySelectorAll('#content > *')].filter((e) => e.offsetHeight && !['top', 'tabs', 'view'].includes(e.id) && e.getBoundingClientRect().top < document.querySelector('.pane:not(.away)').getBoundingClientRect().top);
      alerts.filter((e) => !e.matches('.banner, #alerts')).forEach((e) => out.push(e.id || e.className));
      const pane = document.querySelector('.pane:not(.away)');
      [...pane.children].filter((e) => e.offsetHeight && e.getBoundingClientRect().bottom <= pane.querySelector('.pane-top').getBoundingClientRect().bottom + 1).forEach((e) => out.push(e.className.split(' ')[0]));
      const strip = pane.querySelector(':scope > .pane-strip:not([hidden])'); if (strip) out.push('pane-strip');
      return out; })()""")


sweep()
launchd_before = launchd_jobs()
had = get("/api/settings").get("values", {})
KEEP = ("feature_tabs", "feature_side_panel", "tabs_hide_single", "feature_browser", "feature_preview", "feature_artifacts")
keep = {k: had[k] for k in KEEP if k in had}
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ids = []
try:
    put_settings({k: True for k in KEEP})
    status, made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    for letter in "ABCD":
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})[1]["ids"][0]
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
    # What a session is doing is laid over the page's own answers before its code runs, so a pane is built as Claude's.
    c.call("Page.addScriptToEvaluateOnNewDocument", source="""(() => {
      const kept = (key) => JSON.parse(localStorage.getItem(key) || '{}');
      window.fakeState = kept('fakeState'); window.fakePeek = kept('fakePeek'); window.fakeRecord = kept('fakeRecord');
      window.EventSource = undefined; window.fakeOn = true;
      const real = window.fetch;
      window.fetch = async (url, options) => {
        const m = String(url).match(new RegExp('/api/sessions/([0-9a-f]{8})/(peek|record)$')), p = window.fakePeek || {};
        if (m && p[m[1]]) return new Response(JSON.stringify(m[2] === 'peek' ? p[m[1]] : window.fakeRecord), { status: 200, headers: { 'Content-Type': 'application/json' } });
        const answer = await real(url, options);
        if (!String(url).includes('/api/state')) return answer;
        const data = await answer.json(), f = window.fakeState || {};
        data.sessions = data.sessions.map((s) => f[s.id] ? { ...s, ...f[s.id] } : s);
        return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
      };
    })()""")
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)
    NOW = time.time()
    CL = {"kind": "claude", "mode": "auto", "model": "opus"}
    STATES = {A: {**CL, "state": "working", "orb": "using", "activity": {"tool": "Read", "target": "hub/ui/app.js", "since": NOW - 4}, "turn": {"since": NOW - 64}},
              B: {**CL, "state": "needs", "orb": "waiting", "asking": "Allow Bash: ls -la /tmp | head -3?"},
              C: {**CL, "state": "needs", "orb": "waiting", "asking": "Pick a color for the new dashboard theme?"}}
    PERMISSION = {"kind": "permission", "question": "Do you want to proceed?", "options": [{"n": 1, "label": "Yes", "text": "amend", "row": 0}, {"n": 2, "label": "Yes, and don't ask again", "row": 1},
                  {"n": 3, "label": "No, and tell Claude what to do differently", "text": "type", "value": "", "row": 2}], "multi": False, "text_option": 3, "cursor": 0, "detail": "Bash command\nls -la /tmp | head -3"}
    QUESTION = {"kind": "question", "question": "Pick a color for the new dashboard theme?", "options": [{"n": 1, "label": "Red", "description": "Warm and loud", "row": 0}, {"n": 2, "label": "Blue", "description": "Calm", "row": 1},
                {"n": 3, "label": "Type something", "text": "type", "value": "", "row": 2}, {"n": 4, "label": "Chat about this", "apart": True, "row": 3}], "multi": False, "steps": [{"label": "Color", "done": False}, {"label": "Submit", "submit": True}], "step": 0}
    PEEK = {A: {"dialog": None, "live": True, "text": "", "options": []}, B: {"dialog": PERMISSION, "live": True, "text": "", "options": []}, C: {"dialog": QUESTION, "live": True, "text": "", "options": []}}
    RECORD = {"earlier": 0, "items": [{"kind": "you", "text": "Clean the tmp folder."}, {"kind": "claude", "text": "First I'll look at what is there."}]}
    c.js(f"localStorage.clear(); localStorage.setItem('hub.tabs', {json.dumps(json.dumps({'list': [{'l': A}, {'l': B}, {'l': C}], 'last': A}))}); localStorage.setItem('deskView', '\"terminal\"'); localStorage.setItem('shared', 'false')")
    c.js(f"window.fakePeek = {json.dumps(PEEK)}; window.fakeRecord = {json.dumps(RECORD)}; localStorage.setItem('fakePeek', JSON.stringify(window.fakePeek)); localStorage.setItem('fakeRecord', JSON.stringify(window.fakeRecord))")
    c.fake(STATES)
    c.call("Page.reload"); time.sleep(3)  # the page takes the tabs from storage before a hash change could write its own over them
    keep_fakes = "window.fakePeek = JSON.parse(localStorage.getItem('fakePeek') || '{}'); window.fakeRecord = JSON.parse(localStorage.getItem('fakeRecord') || '{}')"

    def opened(route, panes=1):
        c.js(f"location.hash = {json.dumps(route)}; window.oldPage = true")
        c.call("Page.reload")
        shown = waited(lambda: c.js(f"!window.oldPage && document.querySelectorAll('.pane').length >= {panes} && !!document.querySelector('#side .nav.session')"), 30)
        c.js(keep_fakes)
        c.fake()
        time.sleep(1.0)
        return shown

    # ── At a desk: two bars ──
    check("a working session opens", bool(opened(f"#/s/{A}")))
    check("the tabs are the top bar's row", c.js("!!document.querySelector('#top.with-tabs > #tabs .tab.on')") and not c.js("!!document.querySelector('#content > #tabs')"))
    check("the page keeps its name for screen readers", "Pane A" in (c.js("document.querySelector('#top h1').textContent") or ""), c.js("document.querySelector('#top h1').textContent"))
    height = chrome_height(c)
    check("two bars above the session, about 76px", height <= 80 and bars(c) == ["top", "pane-top"], [height, bars(c)])
    check("the strip is in the pane's head", c.js("!!document.querySelector('.pane-top > .pane-strip:not([hidden])')") and "Read" in c.js("document.querySelector('.pane-strip').innerText"))
    heights = c.js("[...document.querySelectorAll('.pane-top button, .pane-top a, .pane-top .seg')].filter(e => e.offsetParent && !e.closest('.seg') || e.matches('.seg')).filter(e => e.offsetParent).map(e => Math.round(e.getBoundingClientRect().height))")
    check("every control in the head is 28px tall", heights and set(heights) == {28}, heights)
    ringed = c.js("[...document.querySelectorAll('.pane-top *')].filter(e => e.offsetParent && /inset/.test(getComputedStyle(e).boxShadow) && getComputedStyle(e).boxShadow !== 'none').map(e => e.className)")
    check("one control has a ring: Chat|Terminal", ringed == ["seg view-seg"], ringed)
    check("no Close session button in the head", not c.js("!!document.querySelector('.pane-top .close-session')"))
    c.js("document.querySelector('.pane-top [data-key=more]').click()"); time.sleep(0.3)
    items = c.js("[...document.querySelectorAll('.popup.menu button')].map(b => b.querySelector('b').textContent)")
    check("⋯ holds Close session and Delete", "Close session" in items and "Delete session…" in items, items)
    c.press("Escape")
    check("no Split in the header at a desk", not c.js("[...document.querySelectorAll('#top .btn')].some(b => b.textContent.includes('Split'))"))
    c.press("`", "Backquote", CTRL); c.press("s")
    check("s opens the split menu at the pane", c.js("!!document.querySelector('.popup.menu')") and "New session beside this one" in (c.js("document.querySelector('.popup.menu').innerText") or ""))
    c.press("Escape")
    c.shot("01-desk-working")
    STATES[A]["turn"] = {"since": NOW - 3 * 3600}
    c.fake(STATES); time.sleep(1.2)
    clock = c.js("(document.querySelector('.pane-strip .strip-time') || {}).textContent || ''")
    check("a turn over an hour old says since when, quietly", clock.startswith("since ") and c.js("document.querySelector('.pane-strip .strip-time').classList.contains('long')"), clock)
    STATES[A]["turn"] = {"since": NOW - 64}
    c.fake(STATES)

    # ── A split: each pane's menu holds the split's own actions ──
    check("a split opens", bool(opened(f"#/s/h({A},{D})", 2)))
    c.js("document.querySelector('.pane.active .pane-split').click()"); time.sleep(0.3)
    listed = c.js("[...document.querySelectorAll('.popup.menu button')].map(b => b.textContent)")
    check("a pane's split menu saves the split as a board, and evens it out", any(x.startswith("Save as a board") for x in listed) and any(x.startswith("Even out") for x in listed), listed)
    c.press("Escape")
    check("still two bars above each pane", chrome_height(c) <= 80, chrome_height(c))

    # ── Questions in a chat ──
    c.js("localStorage.setItem('deskView', '\"chat\"')")
    for sid, kind in ((B, "permission"), (C, "question")):
        check(f"a {kind} opens in the chat", bool(opened(f"#/s/{sid}")) and bool(waited(lambda: c.js("!!document.querySelector('.chat-ask .qa')"), 10)))
        inputs = c.js("[...document.querySelectorAll('.pane input[type=text], .pane textarea')].filter(e => e.offsetParent && !e.closest('[inert]')).length")
        sends = c.js("[...document.querySelectorAll('.pane .qa-go, .pane .chat-send')].filter(e => e.offsetParent).length")
        check(f"one text field and one send while Claude asks ({kind})", inputs == 1 and sends == 1, [inputs, sends])
        text = STATES[sid]["asking"] if kind == "question" else "ls -la /tmp"
        said = c.js(f"(document.querySelector('.pane').innerText.split({json.dumps(text)}).length - 1)")
        check(f"the question is said once ({kind})", said == 1, said)
        style = c.js("(() => { const s = getComputedStyle(document.querySelector('.qa-q')); return [s.fontSize, s.fontWeight, s.lineHeight]; })()")
        check(f"its title is 18px at weight 500 ({kind})", style == ["18px", "500", "24px"], style)
        check(f"the keys are in the question's row ({kind})", c.js("!!document.querySelector('.qa .chat-tool[aria-label=Keys]')"))
        c.shot(f"02-desk-{kind}")
    PEEK[B] = {"dialog": None, "live": True, "text": "", "options": []}
    c.js(f"window.fakePeek = {json.dumps(PEEK)}; localStorage.setItem('fakePeek', JSON.stringify(window.fakePeek))")
    STATES[B] = {**CL, "state": "finished", "orb": "idle", "said": "Done."}
    c.fake(STATES)
    opened(f"#/s/{B}")
    check("with nothing asked the message box is back", waited(lambda: c.js("!!document.querySelector('.chat-row textarea') && !!document.querySelector('.chat-row textarea').offsetParent && !!document.querySelector('.chat-row .chat-tool[aria-label=Keys]')"), 8))
    c.js("localStorage.setItem('deskView', '\"terminal\"')")

    # ── The side panel's tabs at 280px ──
    opened(f"#/s/{A}")
    c.js("localStorage.setItem('sidePanel', '\"preview\"')")
    c.js("pageKeys.p()"); time.sleep(1.2)
    c.js(f"(() => {{ const all = JSON.parse(localStorage.getItem('panelBy') || '{{}}'); all[{json.dumps(A)}] = {{ on: true, w: 280 }}; localStorage.setItem('panelBy', JSON.stringify(all)); }})()")
    opened(f"#/s/{A}")
    waited(lambda: c.js("!!document.querySelector('.sp-tab[aria-selected=true]')"), 8); time.sleep(0.6)
    look = c.js("""(() => { const row = document.querySelector('.sp-tabs').getBoundingClientRect(), on = document.querySelector('.sp-tab[aria-selected=true]').getBoundingClientRect();
      return { panel: Math.round(document.querySelector('.shared').getBoundingClientRect().width), chosen: document.querySelector('.sp-tab[aria-selected=true]').dataset.panel, inside: on.left >= row.left - 1 && on.right <= row.right + 1 }; })()""")
    check("at 280px the chosen tab, the last, is in view", look and look["panel"] == 280 and look["chosen"] == "preview" and look["inside"], look)
    kinds = c.js("[...document.querySelectorAll('.sp-tab')].map(t => [t.dataset.panel, t.classList.contains('sp-tool'), t.title || ''])")
    check("Overview, Changes and Shared are words; Artifacts, Browser and Devices are icons with their names", [k[:2] for k in kinds[:3]] == [["overview", False], ["changes", False], ["shared", False]]
          and all(k[1] and k[2] for k in kinds[3:]) and [k[0] for k in kinds[3:]] == ["artifacts", "browser", "preview"], kinds)
    c.js("document.querySelector('.sp-tab[data-panel=overview]').click()"); time.sleep(0.6)
    look = c.js("(() => { const row = document.querySelector('.sp-tabs').getBoundingClientRect(), on = document.querySelector('.sp-tab[aria-selected=true]').getBoundingClientRect(); return on.left >= row.left - 1 && on.right <= row.right + 1; })()")
    check("and so is the first, chosen again", look)
    c.shot("03-desk-panel-280")
    c.js("pageKeys.p()"); time.sleep(0.5)

    # ── Switches off: today's view, nothing lost ──
    c.settings({"feature_tabs": False, "feature_side_panel": False})
    opened(f"#/s/{A}")
    check("tabs off: the header names the project and the session, and no tab bar", not c.js("!!document.querySelector('#tabs')") and "Pane A" in c.js("document.querySelector('#top .crumbs').innerText") and not c.js("document.querySelector('#top').classList.contains('with-tabs')"))
    check("and still two bars", chrome_height(c) <= 80 and bars(c) == ["top", "pane-top"], [chrome_height(c), bars(c)])
    c.js("pageKeys.p()"); time.sleep(0.8)
    check("side panel off: the right panel as it was", c.js("(() => { const s = document.querySelector('.stage > .shared'); return !!s && !s.querySelector('.sp-head'); })()"))
    c.js("pageKeys.p()"); time.sleep(0.4)
    c.settings({"feature_tabs": True, "feature_side_panel": True})

    # ── A phone: the top bar and the pane head ──
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.js("localStorage.setItem('phoneView', '\"terminal\"')")
    opened(f"#/s/{A}")
    height = chrome_height(c)
    check("on a phone two bars above the session, about 88px", height <= 92, [height, bars(c)])
    label = c.js("document.querySelector('#top .menu-btn').getAttribute('aria-label')")
    check("the menu button carries the counts, and a mark for what needs you", label.startswith("Menu, 1 needs you") and c.js("!!document.querySelector('#top .menu-btn .menu-hot.c-needs')"), label)
    check("the pane head says the state, and leaves the name to the top bar", c.js("!!document.querySelector('.pane-top > .pane-strip:not([hidden])') && getComputedStyle(document.querySelector('.pane-top > .name')).display === 'none'"))
    c.shot("04-phone-working")
    c.js("localStorage.setItem('phoneView', '\"chat\"')")
    opened(f"#/s/{C}")
    waited(lambda: c.js("!!document.querySelector('.chat-ask .qa')"), 10)
    inputs = c.js("[...document.querySelectorAll('.pane input[type=text], .pane textarea')].filter(e => e.offsetParent && !e.closest('[inert]')).length")
    check("on a phone too, one text field while Claude asks", inputs == 1, inputs)
    c.shot("05-phone-question")
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        put_settings({k: keep.get(k, True) for k in KEEP})
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
