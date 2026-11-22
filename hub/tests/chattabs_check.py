#!/usr/bin/env python3
"""Chat and Terminal, and which tab is the one in front (chattabs), in headless Chrome at a desk and on a phone.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with three plain terminals. One prints
all the time (a busy terminal) and is laid over /api/state in the page as a running Claude session; its record is a long
real-sized transcript copied into the instance's records folder, so the server builds the chat from it. No Claude runs.
- The switch is fast: from the press on Chat or Terminal to the other view shown and usable (the conversation drawn; the
  terminal's text drawn over an open socket), cold (each way's first) and warm (median of seven), desk and phone. The
  press answers at once (the control shows the new choice), and a warm switch is shown within 100 ms.
- On a phone the chat never lets the terminal size the session: a phone that opens in the chat attaches nothing, and a
  terminal it showed goes quiet behind the chat (tmux's ignore-size) and lets go of its socket after a minute. Terminal
  shows the last screen at once and is live again.
- At a desk both views stay: the terminal keeps its socket and its size behind the chat, so a switch resizes nothing,
  and is sent nothing to draw while hidden (a busy terminal costs the page nothing); shown again, tmux redraws it.
- Which one is in front is told and seen: Chat|Terminal is a tablist whose chosen tab has aria-selected, arrows move
  between them; the chosen tab, the session tab in front (aria-current) and the split's focused pane each carry an
  indicator at least 3:1 against what the others show, in Midnight ink and Paper and with a pale and a dark accent.
  Nothing moves when the choice changes (same box sizes).

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/chattabs_check.py <folder-for-screenshots>   (prints a timings table too)
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-chattabs.")); OUT.mkdir(parents=True, exist_ok=True)
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


def waited(test, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.05)
    return None


def median(values):
    values = sorted(v for v in values if v is not None)
    return values[len(values) // 2] if values else None


# Laid over the page before its own code runs: S is a running Claude session (its /peek answers quietly in the page; its
# /record is the server's own), every terminal socket is kept in a list, and a press starts the clock.
HOOKS = """(() => {
  const kept = (key) => JSON.parse(localStorage.getItem(key) || '{}');
  window.fakeState = kept('fakeState'); window.fakePeek = kept('fakePeek');
  window.EventSource = undefined;
  const real = window.fetch;
  window.fetch = async (url, options) => {
    const m = String(url).match(new RegExp('/api/sessions/([0-9a-f]{8})/peek$')), p = window.fakePeek || {};
    if (m && p[m[1]]) return new Response(JSON.stringify(p[m[1]]), { status: 200, headers: { 'Content-Type': 'application/json' } });
    const answer = await real(url, options);
    if (!String(url).includes('/api/state')) return answer;
    const data = await answer.json(), f = window.fakeState || {};
    data.sessions = data.sessions.map((s) => f[s.id] ? { ...s, ...f[s.id] } : s);
    return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  const RealWS = window.WebSocket;
  window.socks = [];
  window.WebSocket = function (url, protocols) {
    const ws = protocols ? new RealWS(url, protocols) : new RealWS(url);
    if (String(url).includes('/ws/term/')) {
      window.socks.push(ws);
      ws.addEventListener('open', () => { ws.openAt = performance.now(); });
      ws.addEventListener('message', () => { ws.heardAt = performance.now(); });
    }
    return ws;
  };
  window.WebSocket.prototype = RealWS.prototype;
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
  addEventListener('click', () => { if (window.t0 === null) window.t0 = performance.now(); }, true);
  // The press's own work, measured at the end of the same task (after the control's handler ran): the choice is shown
  // as soon as the browser paints next, which a page busy drawing a terminal can put off.
  const handled = () => { if (window.t0 !== null && window.armed && window.handledAt === null && window.chosen(window.armed[0], window.armed[1])) window.handledAt = performance.now() - window.t0; };
  addEventListener('click', handled); addEventListener('keydown', handled);
  addEventListener('keydown', () => { if (window.t0 === null) window.t0 = performance.now(); }, true);
  const shown = (el) => { if (!el || !el.isConnected) return false; const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 40 && r.height > 40 && cs.visibility === 'visible' && cs.display !== 'none' && !el.closest('[hidden]'); };
  window.viewSeen = (sid, want) => {
    const pane = document.querySelector(`.pane[data-sid="${sid}"]`);
    if (!pane) return false;
    if (want === 'chat') return window.viewReady(sid, want);
    const host = pane.querySelector('.term'), rows = host && host.querySelector('.xterm-rows');
    return shown(host) && !!rows && rows.textContent.trim().length > 20;
  };
  window.viewReady = (sid, want) => {
    const pane = document.querySelector(`.pane[data-sid="${sid}"]`);
    if (!pane) return false;
    if (want === 'chat') { const log = pane.querySelector('.chat-log'); return shown(log) && !!log.querySelector('.turn') && !log.querySelector('.loading'); }
    const host = pane.querySelector('.term'), rows = host && host.querySelector('.xterm-rows, .xterm-screen');
    const ws = window.socks.filter((w) => w.url.includes(`/ws/term/${sid}`)).pop();
    return shown(host) && !!rows && ws && ws.readyState === 1 && ws.heardAt > ws.openAt && (host.querySelector('.xterm-rows') ? host.querySelector('.xterm-rows').textContent.trim().length > 20 : true);
  };
  window.chosen = (sid, want) => {
    const pane = document.querySelector(`.pane[data-sid="${sid}"]`);
    const b = pane && [...pane.querySelectorAll('.view-seg button, .view-seg [role=tab]')].find((x) => x.textContent.trim() === (want === 'chat' ? 'Chat' : 'Terminal'));
    return !!b && (b.getAttribute('aria-selected') === 'true' || b.getAttribute('aria-pressed') === 'true');
  };
  // Armed before a press: the time to the control showing the choice (resp) and to the view shown and usable (ready).
  window.arm = (sid, want) => {
    window.t0 = null; window.timed = null; window.armed = [sid, want]; window.handledAt = null;
    const t = { resp: null, seen: null, ready: null };
    const iv = setInterval(() => {
      if (window.t0 === null) return;
      const now = performance.now() - window.t0;
      if (t.resp === null && window.chosen(sid, want)) t.resp = now;
      if (t.seen === null && window.viewSeen(sid, want)) t.seen = now;
      if (t.ready === null && window.viewReady(sid, want)) t.ready = now;
      if (t.resp !== null && t.ready !== null) { clearInterval(iv); t.handled = window.handledAt; window.timed = t; }
      if (now > 15000) { clearInterval(iv); window.timed = t; }
    }, 2);
  };
})()"""


def contrast(a, b):
    def lum(rgb):
        def ch(c):
            c /= 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# What the chosen and an unchosen item show, read from computed styles: the colour of the chosen one's indicator (its
# ::after bar when it has one, else its fill), and what sits under an unchosen one (its own fill, or the first
# ancestor's). Colours with alpha are laid over what is under them.
STYLE = """((on, off) => {
  const rgba = (s) => { const m = String(s).match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const under = (el) => { const layers = []; for (let e = el; e; e = e.parentElement) { const c = rgba(getComputedStyle(e).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let out = [0, 0, 0]; layers.reverse().forEach((c) => { out = out.map((v, i) => v * (1 - c[3]) + c[i] * c[3]); }); return out; };
  const bar = (el) => { const a = getComputedStyle(el, '::after'); const c = rgba(a.backgroundColor); return a.content !== 'none' && c && c[3] > 0 && parseFloat(a.height) >= 2 ? c : null; };
  const lay = (c, base) => c ? base.map((v, i) => v * (1 - c[3]) + c[i] * c[3]) : base;
  const offBg = under(off), onBg = under(on), mark = bar(on);
  const cs = (el) => { const s = getComputedStyle(el); return { color: s.color, weight: s.fontWeight, bg: s.backgroundColor, shadow: s.boxShadow, w: Math.round(el.getBoundingClientRect().width * 10) / 10, h: Math.round(el.getBoundingClientRect().height * 10) / 10 }; };
  return { indicator: mark ? lay(mark, onBg) : onBg, offBg, on: cs(on), off: cs(off), barred: !!mark };
})"""


def look(c, on_sel, off_sel, words=""):
    """The indicator read on on_sel and off_sel; their words (colour, weight) read on `words` inside each, when given."""
    if not c.js(f"!!document.querySelector({json.dumps(on_sel)}) && !!document.querySelector({json.dumps(off_sel)})"):
        return None
    seen = c.js(f"{STYLE}(document.querySelector({json.dumps(on_sel)}), document.querySelector({json.dumps(off_sel)}))")
    if words:
        text = c.js(f"[{json.dumps(on_sel)}, {json.dumps(off_sel)}].map(s => {{ const e = document.querySelector(s).querySelector({json.dumps(words)}), cs = getComputedStyle(e); return {{ color: cs.color, weight: cs.fontWeight }}; }})")
        seen["on"].update(text[0]); seen["off"].update(text[1])
    return seen


sweep()
launchd_before = launchd_jobs()
had = get("/api/settings").get("values", {})
KEEP = ("feature_tabs", "tabs_hide_single", "theme", "accent")
keep = {k: had[k] for k in KEEP if k in had}
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
TMUXC = ["tmux", "-L", os.environ["HUB_TMUX"]]
TRANSCRIPT = os.environ.get("CHATTABS_TRANSCRIPT", "")
timings = []
try:
    put_settings({"feature_tabs": True, "tabs_hide_single": False, "theme": "dark", "accent": ""})
    status, made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    ids = []
    for letter in "ABC":
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})[1]["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": f"Pane {letter}"})
        ids.append(sid)
    S, B, C_ = ids
    # A busy terminal: it prints a screenful twenty times a second.
    subprocess.run(TMUXC + ["send-keys", "-t", f"hub-{S}", "while :; do ls -la /usr/bin | head -60; sleep 0.05; done", "Enter"], check=True)
    # A long conversation: a real-sized transcript where the hub keeps a record's copy (records/<sid>/transcript.jsonl).
    records = Path(os.environ["HUB_STATE"]) / "records" / S
    records.mkdir(parents=True, exist_ok=True)
    source = Path(TRANSCRIPT) if TRANSCRIPT else None
    if source and source.is_file():
        shutil.copyfile(source, records / "transcript.jsonl")
    else:  # made up, long: 600 exchanges with steps between them
        lines = []
        for i in range(600):
            lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": f"Question {i}: look at hub/ui/app.js and tell me what the switch does, and why it is slow at step {i}."}, "timestamp": "2026-11-22T10:00:00Z", "uuid": f"u{i}"}))
            lines.append(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "Read", "input": {"file_path": "/tmp/x.js"}}]}, "timestamp": "2026-11-22T10:00:01Z", "uuid": f"a{i}"}))
            lines.append(json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": "ok"}]}, "timestamp": "2026-11-22T10:00:02Z", "uuid": f"r{i}"}))
            lines.append(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": ("The switch rebuilds the pane. " * 20) + f"\n\n- point one {i}\n- point two\n\n`code {i}`"}]}, "timestamp": "2026-11-22T10:00:03Z", "uuid": f"b{i}"}))
        (records / "transcript.jsonl").write_text("\n".join(lines) + "\n")
    t = time.time(); rec = get(f"/api/sessions/{S}/record"); first_record = time.time() - t
    t = time.time(); get(f"/api/sessions/{S}/record"); again_record = time.time() - t
    check("the long conversation is served", len(rec.get("items", [])) > 50, {k: rec.get(k) for k in ("earlier",)} | {"items": len(rec.get("items", []))})
    print(f"INFO  record: {len(rec.get('items', []))} items, {len(json.dumps(rec)) // 1024} KB; first {first_record * 1000:.0f} ms, cached {again_record * 1000:.0f} ms")

    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)
    c.call("Page.addScriptToEvaluateOnNewDocument", source=HOOKS)
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)
    CL = {"kind": "claude", "mode": "auto", "model": "opus", "state": "finished", "orb": "finished"}
    FAKE = {S: CL, B: CL}
    PEEK = {S: {"dialog": None, "live": True, "text": "", "options": []}, B: {"dialog": None, "live": True, "text": "", "options": []}}
    c.js(f"localStorage.clear(); localStorage.setItem('fakeState', {json.dumps(json.dumps(FAKE))}); localStorage.setItem('fakePeek', {json.dumps(json.dumps(PEEK))}); localStorage.setItem('shared', 'false')")
    c.js(f"localStorage.setItem('hub.tabs', {json.dumps(json.dumps({'list': [{'l': S}, {'l': B}, {'l': C_}], 'last': S}))})")

    def opened(route, view_key, view, wait_for):
        c.js(f"localStorage.setItem({json.dumps(view_key)}, {json.dumps(json.dumps(view))}); location.hash = {json.dumps(route)}; window.oldPage = true")
        c.call("Page.reload")
        ok = waited(lambda: c.js("!window.oldPage && !!document.querySelector('.pane .pane-top')"), 30)
        ok = ok and waited(lambda: c.js(f"window.viewReady({json.dumps(S)}, {json.dumps(wait_for)})"), 30)
        time.sleep(1.5)
        return ok

    def switch(want, how="click"):
        """One press on Chat or Terminal in S's pane: the times to the choice shown and to the view usable, in ms."""
        c.js(f"window.arm({json.dumps(S)}, {json.dumps(want)})")
        word = "Chat" if want == "chat" else "Terminal"
        at = c.js(f"""(() => {{ const pane = document.querySelector('.pane[data-sid="{S}"]');
          const b = [...pane.querySelectorAll('.view-seg button, .view-seg [role=tab]')].find((x) => x.textContent.trim() === '{word}');
          if (!b) return null; const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()""")
        if not at:
            return None
        c.click(*at)
        got = waited(lambda: c.js("window.timed"), 20)
        time.sleep(0.6)  # what the switch started settles before the next press
        return got

    def clients():
        out = subprocess.run(TMUXC + ["list-clients", "-t", f"hub-{S}", "-F", "#{client_width}x#{client_height}"], capture_output=True, text=True).stdout.split()
        return out

    def run_device(label, view_key, start, other):
        check(f"{label}: S opens in its {start}", bool(opened(f"#/s/{S}", view_key, start, start)))
        cold_there = switch(other)
        cold_back = switch(start)
        warm_there, warm_back = [], []
        for _ in range(7):
            warm_there.append(switch(other))
            warm_back.append(switch(start))
        rows = [(f"{start}→{other}", cold_there, warm_there), (f"{other}→{start}", cold_back, warm_back)]
        for name, cold, warm in rows:
            wr = median([w and w["ready"] for w in warm]); wp = median([w and w["resp"] for w in warm]); ws_ = median([w and w["seen"] for w in warm])
            wh = median([w and w.get("handled") for w in warm])
            timings.append((label, name, cold and cold.get("handled"), cold and cold["resp"], cold and cold["seen"], cold and cold["ready"], wh, wp, ws_, wr))
            check(f"{label} {name}: the press's own work is done within 50 ms, cold and warm", cold and cold.get("handled") is not None and cold["handled"] < 50 and wh is not None and wh < 50, [cold, wh])
            check(f"{label} {name}: a warm switch shows the view within 100 ms", ws_ is not None and ws_ < 100, [w and w["seen"] for w in warm])
            # Seen is polled every 2 ms beside a page busy drawing a terminal, so one cold sample gets more room than a median.
            check(f"{label} {name}: the choice is seen within 100 ms warm (median) and 150 ms cold", cold and cold["resp"] is not None and cold["resp"] < 150 and wp is not None and wp < 100, [cold, wp])
            check(f"{label} {name}: a warm switch is usable within 100 ms", wr is not None and wr < 100, [w and w["ready"] for w in warm])
            check(f"{label} {name}: a cold switch is usable within 1.5 s", cold and cold["ready"] is not None and cold["ready"] < 1500, cold)

    # ── At a desk ──
    run_device("desk", "deskView", "terminal", "chat")
    switch("chat")
    sizes = clients()
    check("desk: with the chat in front the terminal keeps its socket and its size", c.js(f"window.socks.filter(w => w.url.includes('/ws/term/{S}') && w.readyState === 1).length") == 1 and len(sizes) == 1, sizes)
    before_heard = c.js(f"(window.socks.filter(w => w.url.includes('/ws/term/{S}')).pop() || {{}}).heardAt || 0"); time.sleep(1.5)
    check("desk: and is sent nothing to draw while hidden, though it prints all the time", c.js(f"(window.socks.filter(w => w.url.includes('/ws/term/{S}')).pop() || {{}}).heardAt || 0") == before_heard)
    c.shot("desk-chat-dark")
    switch("terminal")
    c.shot("desk-terminal-dark")
    # ── On a phone ──
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    run_device("phone", "phoneView", "chat", "terminal")
    flags = lambda: subprocess.run(TMUXC + ["list-clients", "-t", f"hub-{S}", "-F", "#{client_flags}"], capture_output=True, text=True).stdout.split()
    waited(lambda: all("ignore-size" in f for f in flags()), 5)
    check("phone: with the chat in front the terminal never sizes the session (every client of it ignore-size)", all("ignore-size" in f for f in flags()), flags())
    check("phone: and after a minute of the chat it lets go: no socket, no tmux client", bool(waited(lambda: not clients() and c.js(f"window.socks.filter(w => w.url.includes('/ws/term/{S}') && w.readyState < 2).length") == 0, 75)), clients())
    switch("terminal")
    check("phone: Terminal again attaches a client that sizes the session", clients() and not any("ignore-size" in f for f in flags()), flags())
    switch("chat")
    c.shot("phone-chat-dark")
    switch("terminal")
    c.shot("phone-terminal-dark")
    switch("chat")
    c.call("Emulation.setTouchEmulationEnabled", enabled=False)
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)

    # ── Which one is in front ──
    opened(f"#/s/h({S},{B})", "deskView", "terminal", "terminal")
    c.js(f"if (!tabs.list.some(t => t.l === {json.dumps(C_)})) tabs.list.push({{ l: {json.dumps(C_)}, z: null }}); keepTabs(); drawTabs()"); time.sleep(0.5)
    check("two session tabs, the split's in front", c.js("document.querySelectorAll('#tabs .tab').length") >= 2 and c.js("document.querySelectorAll('#tabs .tab.on .tab-main[aria-current=page]').length") == 1, c.js("document.querySelector('#tabs') && document.querySelector('#tabs').outerHTML.slice(0, 300)"))
    roles = c.js(f"""(() => {{ const seg = document.querySelector('.pane[data-sid="{S}"] .view-seg'); if (!seg) return null;
      return {{ role: seg.getAttribute('role'), tabs: [...seg.children].map(b => [b.getAttribute('role'), b.getAttribute('aria-selected'), b.tabIndex, b.textContent.trim()]) }}; }})()""")
    check("Chat|Terminal is a tablist, the terminal its selected tab", roles and roles["role"] == "tablist" and [t[:2] for t in roles["tabs"]] == [["tab", "false"], ["tab", "true"]], roles)
    check("only the selected tab is in the tab order", roles and [t[2] for t in roles["tabs"]] == [-1, 0], roles)
    c.js(f"document.querySelector('.pane[data-sid=\"{S}\"] .view-seg [aria-selected=true]').focus()")
    c.js(f"window.arm({json.dumps(S)}, 'chat')")
    c.press("ArrowLeft")
    got = waited(lambda: c.js("window.timed"), 10)
    check("← moves to Chat and shows it", c.js(f"window.chosen({json.dumps(S)}, 'chat')") and got and got["ready"] is not None, got)
    check("focus stays on the chosen tab", c.js("(document.activeElement || {}).textContent") == "Chat", c.js("(document.activeElement || {}).outerHTML"))
    c.js(f"window.arm({json.dumps(S)}, 'terminal')"); c.press("ArrowRight"); waited(lambda: c.js("window.timed"), 10); time.sleep(0.5)
    c.js(f"document.querySelector('.pane[data-sid=\"{B}\"]').dispatchEvent(new PointerEvent('pointerdown', {{ bubbles: true }}))"); time.sleep(0.4)
    for theme in ("dark", "light"):
        for accent in ("", "#f5e663", "#3a2a00"):
            put_settings({"theme": theme, "accent": accent}); c.js("loadSettings()"); time.sleep(1.2)
            name = f"{theme}{' accent ' + accent if accent else ''}"
            for what, on, off in (("Chat|Terminal", f".pane[data-sid='{S}'] .view-seg [aria-selected=true]", f".pane[data-sid='{S}'] .view-seg [aria-selected=false]"),
                                  ("session tab", "#tabs .tab.on", "#tabs .tab:not(.on)"),
                                  ("focused pane", ".pane.active .pane-top", ".pane:not(.active) .pane-top")):
                seen = look(c, on, off, ".tab-main" if what == "session tab" else "")
                ratio = contrast(seen["indicator"], seen["offBg"]) if seen else 0
                check(f"{name}: the {what} in front has an indicator 3:1 against the others ({ratio:.2f})", ratio >= 3, seen)
                if what != "focused pane":
                    check(f"{name}: the {what} in front reads in its text too (colour and weight)", seen and seen["on"]["color"] != seen["off"]["color"] and seen["on"]["weight"] != seen["off"]["weight"], seen and (seen["on"], seen["off"]))
            if not accent:
                c.shot(f"desk-tabs-{theme}")
    before = c.js(f"[...document.querySelectorAll('.pane[data-sid=\"{S}\"] .view-seg > *')].map(b => {{ const r = b.getBoundingClientRect(); return [r.left, r.width, r.height]; }})")
    c.js(f"document.querySelector('.pane[data-sid=\"{S}\"] .view-seg [aria-selected=false]').click()"); time.sleep(0.8)
    after = c.js(f"[...document.querySelectorAll('.pane[data-sid=\"{S}\"] .view-seg > *')].map(b => {{ const r = b.getBoundingClientRect(); return [r.left, r.width, r.height]; }})")
    check("nothing in the control moves when the choice changes", before == after, [before, after])
    c.shot("desk-split-light-chat")
    # The phone's light theme, the switch and the sessions row above a split.
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    time.sleep(1.2)
    c.shot("phone-split-light")
    seen = look(c, ".pane-switch [aria-selected=true]", ".pane-switch [aria-selected=false]")
    ratio = contrast(seen["indicator"], seen["offBg"]) if seen else 0
    check(f"phone, light: the split's session in front has an indicator 3:1 against the others ({ratio:.2f})", ratio >= 3, seen)
    put_settings({"theme": "dark"}); c.js("loadSettings()"); time.sleep(1.2)
    c.shot("phone-split-dark")
    seen = look(c, ".pane-switch [aria-selected=true]", ".pane-switch [aria-selected=false]")
    ratio = contrast(seen["indicator"], seen["offBg"]) if seen else 0
    check(f"phone, dark: the split's session in front has an indicator 3:1 against the others ({ratio:.2f})", ratio >= 3, seen)
    check("no script errors", not c.errors, c.errors)
finally:
    put_settings({**{"feature_tabs": True, "tabs_hide_single": True, "theme": "dark", "accent": ""}, **keep})
    chrome.terminate()
    try:
        chrome.wait(10)
    except subprocess.TimeoutExpired:
        chrome.kill()
    shutil.rmtree(profile, ignore_errors=True)
    left = remove_project(NAME)
    check("the throwaway project is removed", not left, left)
    check("launchd's folder holds what it held", launchd_jobs() == launchd_before)

print("\n| Where | Switch | Cold: handler done | Cold: choice seen | Cold: view shown | Cold: usable | Warm: handler done | Warm: choice seen | Warm: view shown | Warm: usable |\n|---|---|---|---|---|---|---|---|---|---|")
fmt = lambda v: "n/a" if v is None else f"{v:.0f} ms"
for row in timings:
    print("| " + " | ".join([row[0], row[1]] + [fmt(v) for v in row[2:]]) + " |")
print(f"\n{failures} failed" if failures else "\nAll passed")
sys.exit(1 if failures else 0)
