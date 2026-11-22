#!/usr/bin/env python3
"""The phone, in headless Chrome as an iPhone: no page zooms in, no page scrolls sideways, and a finger hits every control.

A throwaway project, hub-test-throwaway-<n>, with two plain terminals; what they are doing is laid over /api/state in
the page, so no Claude runs. At 393×852 (an iPhone 15/16, 3× pixels), 375×667 (the small one) and on its side, 852×393,
each as a touch screen with Safari's user agent:
- Every text field on every page, the ones a page makes as it opens too (Go to, a sidebar rename, the terminal's hidden
  input, the composers), is at least 16px. iOS Safari zooms the page in when a smaller one takes focus, and stays there.
  Chrome can't zoom like that, so the size is what is checked.
- No page is wider than the screen, and nothing sticks out past its edge unless a scroller of its own holds it.
- Every control in the top bar, the drawer, the bottom bar and the page takes a 44×44px touch (Apple's minimum),
  probed at the control's centre ±21px with elementFromPoint, so a hit area grown with a pseudo-element counts.
- The top bar's first and last glyphs sit on the page's 16px gutter.
- A menu opened in the drawer goes when the page changes under it.
- At a desk (1440×900, a mouse) the sidebar's rows, the top bar and the composer keep their sizes.

Runs against a second instance (the six HUB_* variables, see tests/instance.py).
Run: /usr/bin/python3 tests/mobile_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-mobile.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9348"))
SAFARI = "Mozilla/5.0 (iPhone; CPU iPhone OS 26_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1"
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:600]}]" if not ok else ""), flush=True)
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

    def device(self, width, height, touch=True):
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=3 if touch else 1, mobile=touch)
        self.call("Emulation.setTouchEmulationEnabled", **({"enabled": True, "maxTouchPoints": 5} if touch else {"enabled": False}))
        self.call("Emulation.setUserAgentOverride", userAgent=SAFARI if touch else "", platform="iPhone" if touch else "")

    def go(self, route, wait=2.0):
        self.js(f"location.hash = {json.dumps(route)}")
        time.sleep(wait)

    def fake(self, states):
        """What each session is doing, laid over every /api/state this page reads."""
        self.js(f"window.fakeState = {json.dumps(states)}")
        self.js("""(() => {
          if (window.fakeOn) return;
          window.fakeOn = true;
          window.EventSource = undefined; if (push.source) push.source.close(); push.source = null; push.base = null;  // the live stream would bring the real state past this overlay
          const real = window.fetch;
          window.fetch = async (url, options) => {
            const answer = await real(url, options);
            if (!String(url).includes('/api/state')) return answer;
            const data = await answer.json(), f = window.fakeState || {};
            data.sessions = data.sessions.map((s) => f[s.id] ? { ...s, ...f[s.id] } : s).concat(f.extra || []);
            return new Response(JSON.stringify(data), { status: 200, headers: { 'Content-Type': 'application/json' } });
          };
        })(); tick()""")
        time.sleep(1)


# Every text field in the page, shown or not, under 16px.
SMALL_FIELDS = """(() => [...document.querySelectorAll('input, textarea, select')]
  .filter((e) => !['checkbox', 'radio', 'range', 'color', 'file', 'hidden', 'button', 'submit', 'reset'].includes(e.type))
  .map((e) => ({ f: (e.className || e.getAttribute('aria-label') || e.tagName).toString().slice(0, 60), px: parseFloat(getComputedStyle(e).fontSize) }))
  .filter((x) => x.px < 16))()"""
# Sideways: the page wider than the screen, or a visible element past an edge that no scroller of its own clips.
SIDEWAYS = """(() => {
  const W = document.documentElement.clientWidth, out = [];
  if (document.documentElement.scrollWidth > W) out.push('page ' + document.documentElement.scrollWidth);
  if (document.body.scrollWidth > document.body.clientWidth) out.push('body ' + document.body.scrollWidth);
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (!r.width || !r.height || cs.visibility === 'hidden' || r.bottom < 0 || r.top > innerHeight) continue;
    if (r.right <= W + 1 && r.left >= -1) continue;
    if (e.matches('.skip-link')) continue;  // parked off the left edge until it takes focus, which scrolls nothing
    if (e.closest('#side') && !document.body.classList.contains('side-open') && innerWidth <= 760) continue;  // the shut drawer waits off the edge
    let p = e.parentElement, held = false;
    while (p && p !== document.body) { if (getComputedStyle(p).overflowX !== 'visible') { const q = p.getBoundingClientRect(); if (q.right <= W + 1 && q.left >= -1) { held = true; break; } } p = p.parentElement; }
    if (!held) out.push(((e.className && e.className.toString()) || e.tagName).slice(0, 50) + ' ' + Math.round(r.left) + '..' + Math.round(r.right));
  }
  return out.slice(0, 8);
})()"""
# A control's touch: from its centre, 21px each way must still land on it (or what it holds). Only controls wholly in
# sight are counted (a tap at the centre and at each edge reaches them); one half under the bottom bar or scrolled away isn't. The session pane's own
# header (.pane-top) is the session view's and is checked by its own tests.
SMALL_TARGETS = """((scope) => {
  const W = innerWidth, H = innerHeight;
  const on = (e, x, y) => { if (x < 0 || y < 0 || x >= W || y >= H) return true; const t = document.elementFromPoint(x, y); return !!t && (t === e || e.contains(t)); };
  return [...document.querySelectorAll(scope.map((s) => s + ' :is(a[href], button, [role=button], summary, select)').join(','))]
    .filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height && [[.5, .5], [.5, .03], [.5, .97], [.03, .5], [.97, .5]].every(([a, b]) => on(e, r.left + r.width * a, r.top + r.height * b)); })
    .filter((e) => !e.closest('.xterm, [data-nav], .pane-top'))
    .map((e) => { const r = e.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
      return { t: (e.getAttribute('aria-label') || e.textContent || e.className).toString().trim().slice(0, 40), w: on(e, x - 21, y) && on(e, x + 21, y), h: on(e, x, y - 21) && on(e, x, y + 21), size: Math.round(r.width) + 'x' + Math.round(r.height) }; })
    .filter((x) => !x.w || !x.h).map((x) => x.t + ' ' + x.size);
})"""


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
    for title in ("Refactor the authentication middleware so tokens refresh without a second sign-in", "dev server"):
        sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
        api("POST", f"/api/sessions/{sid}/rename", {"title": title})
        ids.append(sid)
    A, B = ids
    page = waited(lambda: next((t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page"), None), 20)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    now = time.time()
    STATES = {A: {"state": "working", "activity": {"tool": "Edit", "target": "src/middleware/authentication/refresh-token.ts", "since": now - 95}, "turn": now - 300},
              B: {"state": "needs", "asking": "Which port should the preview server use for the device frame on the phone?"}}
    ROUTES = [("home", "#/"), ("project", f"#/p/{NAME}"), ("memory", f"#/p/{NAME}/memory"), ("dreams", f"#/p/{NAME}/dreams"),
              ("session", f"#/s/{A}"), ("new", f"#/p/{NAME}/new"), ("settings", "#/settings"), ("appearance", "#/settings/appearance"), ("catcher", "#/catcher")]

    for label, (width, height) in (("iphone", (393, 852)), ("small", (375, 667)), ("side", (852, 393))):
        c.device(width, height)
        c.call("Page.navigate", url=CFG["origin"] + "/#/")
        time.sleep(1); c.js("localStorage.clear()"); c.call("Page.reload")
        check(f"{label}: the page loads", bool(waited(lambda: c.js("!!document.querySelector('#side .nav')"), 20)))
        c.fake(STATES)
        for name, route in ROUTES:
            c.go(route, 3.0 if name == "session" else 2.0)
            c.shot(f"{label}-{name}")
            check(f"{label} {name}: no text field under 16px, so focus never zooms", not c.js(SMALL_FIELDS), c.js(SMALL_FIELDS))
            check(f"{label} {name}: nothing wider than the screen", not c.js(SIDEWAYS), c.js(SIDEWAYS))
            if width <= 760:  # on its side a phone has the desk's layout, with the drawer's rows a little taller (see the README)
                small = c.js(f"({SMALL_TARGETS})(['#top', '#view', '#phone-bar', '#alerts'])")
                check(f"{label} {name}: every control takes a 44px touch", not small, small)
        if width > 760:
            continue  # on its side the phone has the desk's layout; the checks above are what it owes a finger there
        c.go("#/")
        glyphs = c.js("""(() => { const W = innerWidth, first = document.querySelector('#top .menu-btn svg').getBoundingClientRect();
          const last = [...document.querySelectorAll('#top .actions-top > *')].filter((e) => e.offsetWidth).pop().querySelector('svg').getBoundingClientRect();
          return [Math.round(first.left), Math.round(W - last.right)]; })()""")
        check(f"{label}: the top bar's first and last glyphs sit on the 16px gutter", all(abs(g - 16) <= 3 for g in glyphs), glyphs)
        c.js("document.querySelector('#top .menu-btn').click()"); time.sleep(0.8)
        c.shot(f"{label}-drawer")
        small = c.js(f"({SMALL_TARGETS})(['#side'])")
        check(f"{label}: every row and button in the drawer takes a 44px touch", not small, small)
        waited(lambda: c.js("!!document.querySelector('#side .side-row.project .nav .label') && !!document.querySelector('#side .nav.session .label')"), 10)
        # A session's second line shows only while it is live, which the made-up states don't always hold through a
        # redraw; a stand-in line in a session's row measures the same rule.
        sizes = c.js("""(() => { const px = (s) => { const e = document.querySelector(s); return e ? parseFloat(getComputedStyle(e).fontSize) : s; };
          const lines = document.querySelector('#side .nav.session .lines') || document.querySelector('#side .nav.session'), probe = document.createElement('span');
          probe.className = 'sub'; probe.textContent = 'Edit login.py'; lines.append(probe);
          const out = [px('#side .side-row.project .nav .label'), px('#side .nav.session .label'), parseFloat(getComputedStyle(probe).fontSize)]; probe.remove(); return out; })()""")
        check(f"{label}: the drawer reads at 16px for a project, 15px for a session and 13px for what it does", sizes == [16, 15, 13], sizes)
        check(f"{label}: the open drawer leaves the page in sight to tap shut", c.js("innerWidth - document.querySelector('#side').getBoundingClientRect().right") >= 56)
        c.js(f"document.querySelector('#side .side-row[data-sid=\"{A}\"] .hover-add.more').click()"); time.sleep(0.5)
        check(f"{label}: a session's ⋯ in the drawer opens its menu", c.js("!!document.querySelector('.popup.menu')"))
        small = c.js(f"({SMALL_TARGETS})(['.popup.menu'])")
        check(f"{label}: every item in that menu takes a 44px touch", not small, small)
        c.js("[...document.querySelectorAll('.popup.menu button')].find((b) => b.textContent.startsWith('Rename')).click()"); time.sleep(0.5)
        check(f"{label}: the drawer's rename field is 16px", c.js("(() => { const i = document.querySelector('#side .side-input'); return !!i && parseFloat(getComputedStyle(i).fontSize) >= 16; })()"))
        c.js("document.querySelector('#side .side-input')?.blur()"); time.sleep(0.3)
        c.js(f"document.querySelector('#side .side-row[data-sid=\"{A}\"] .hover-add.more').click()"); time.sleep(0.4)
        c.go(f"#/p/{NAME}", 1.0)
        check(f"{label}: a menu opened in the drawer goes when the page changes", not c.js("!!document.querySelector('.popup.menu')"))
        c.go(f"#/s/{A}", 3.0)
        check(f"{label}: the terminal's own input is 16px, so a tap into the terminal never zooms",
              c.js("(() => { const t = document.querySelector('.xterm-helper-textarea'); return !!t && parseFloat(getComputedStyle(t).fontSize) >= 16; })()"))
        check(f"{label}: the session's project is a 44px way back, still named for a screen reader",
              c.js(f"(() => {{ const a = document.querySelector('#top .crumbs > a[href=\"#/p/{NAME}\"]'); if (!a) return false; const r = a.getBoundingClientRect(); return r.width >= 44 && r.height >= 44 && a.textContent.includes({json.dumps(NAME)}); }})()"))
        keys = c.js("(() => { const row = document.querySelector('.keys'); return row ? [row.scrollWidth <= row.clientWidth + 1, Math.min(...[...row.querySelectorAll('button')].map((b) => b.getBoundingClientRect().height))] : null; })()")
        check(f"{label}: the terminal's key row fits the screen with 44px keys", keys and keys[0] and keys[1] >= 44, keys)
        c.go("#/", 1.5)
        c.js("document.querySelector('[data-key=\"pb:goto\"]').click()"); time.sleep(0.8)
        check(f"{label}: Go to opens with its search at 16px", c.js("(() => { const i = document.querySelector('dialog.palette[open] input'); return !!i && parseFloat(getComputedStyle(i).fontSize) >= 16; })()"))
        c.shot(f"{label}-goto")
        c.js("document.querySelector('dialog.palette[open]')?.close()")

    # A desk keeps its sizes: the phone's rules reach no further than a phone or a touch screen.
    c.device(1440, 900, touch=False)
    c.call("Page.reload")
    waited(lambda: c.js("!!document.querySelector('#side .nav')"), 20)
    c.fake(STATES)
    c.go(f"#/p/{NAME}")
    desk = c.js("""(() => ({ row: Math.round(document.querySelector('#side .side-row.project').getBoundingClientRect().height),
      top: Math.round(document.querySelector('#top').getBoundingClientRect().height),
      font: parseFloat(getComputedStyle(document.querySelector('#side .side-row.project .nav')).fontSize),
      composer: parseFloat(getComputedStyle(document.querySelector('.composer textarea')).fontSize) }))()""")
    check("a desk keeps its 28px sidebar rows, 14px names, 40px top bar and 14px composer", desk == {"row": 28, "top": 40, "font": 14, "composer": 14}, desk)
    c.shot("desk-project")
    check("no script errors", not c.errors, c.errors[:3])
finally:
    try:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
