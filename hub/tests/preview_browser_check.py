#!/usr/bin/env python3
"""The built-in browser (#/browser) and the device preview (#/preview), in headless Chrome at a desk's size and a phone's.

Run: /usr/bin/python3 tests/preview_browser_check.py <output-folder>
Runs against a second instance (the six HUB_* variables, see tests/instance.py; HUB_PREVIEW_PORT when the listener
isn't on the hub's port + 1; HUB_CDP_PORT for Chrome). Starts a tiny dev server on loopback (tests/devserver.py) and a
plain terminal session in the instance that prints its address, which it ends again. Saves screenshots to the folder.
Checks: suggestions (the session's printed address, servers listening), a page framed through the preview with its
helper (address, title, back), the last address kept, Copy link, a server that isn't running and then starts, the
page from inside the preview failing to reach the hub's API, the device preview (several devices, fit, rotate, keeping
in step, reload all), the phone layouts, the side panels, Go to, and both switches off giving back today's hub, live.
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from urllib.parse import quote

from instance import CFG, PORT as HUB_PORT, OWNER, WRITE, TMUX
import hub_base as base
from devserver import DevServer, free_port

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="preview-browser-check.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = int(os.environ.get("HUB_CDP_PORT", "9342"))
PREVIEW = int(os.environ.get("HUB_PREVIEW_PORT") or HUB_PORT + 1)
CONFIG = Path(os.path.realpath(base.CONFIG))
ORIGIN = CFG["origin"]
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:600]}]"), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE if method != "GET" else OWNER)
    r = c.getresponse()
    data = r.read()
    try:
        return json.loads(data)
    except ValueError:
        return {}


class CDP:
    def __init__(self, url):
        hostport, path = url.split("//")[1].split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        data = b""
        while b"\r\n\r\n" not in data:
            data += self.s.recv(4096)
        self.buffer, self.n, self.errors = data.split(b"\r\n\r\n", 1)[1], 0, []

    def _read(self, n):
        while len(self.buffer) < n:
            self.buffer += self.s.recv(1 << 20)
        out, self.buffer = self.buffer[:n], self.buffer[n:]
        return out

    def recv(self):
        data = b""
        while True:
            a, b = self._read(2)
            size = b & 0x7F
            size = struct.unpack(">H", self._read(2))[0] if size == 126 else struct.unpack(">Q", self._read(8))[0] if size == 127 else size
            data += self._read(size)
            if a & 0x80:
                return json.loads(data)

    def call(self, method, **params):
        self.n += 1
        payload, mask = json.dumps({"id": self.n, "method": method, "params": params}).encode(), os.urandom(4)
        size = len(payload)
        head = bytes([0x81]) + (bytes([0x80 | size]) if size < 126 else bytes([0x80 | 126]) + struct.pack(">H", size) if size < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", size))
        self.s.sendall(head + mask + bytes(ch ^ mask[i % 4] for i, ch in enumerate(payload)))
        while True:
            message = self.recv()
            if message.get("id") == self.n:
                return message.get("result", {})
            if message.get("method") == "Runtime.exceptionThrown":
                self.errors.append(str(message["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:300])

    def js(self, expression):
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def shot(self, name):
        (OUT / f"{name}.png").write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def size(self, width, height, mobile=False):
        self.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2 if mobile else 1, mobile=mobile)


as_found = CONFIG.read_bytes()
dev = DevServer(hub_port=HUB_PORT)
late_port = free_port()
late = None
sid = None
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = None
try:
    api("PUT", "/api/settings", {"feature_browser": True, "feature_preview": True})
    # A plain terminal that prints a dev server's address, as `npm run dev` does.
    sid = api("POST", "/api/sessions", {"project": "@hub", "tasks": [], "kind": "shell"})["ids"][0]
    time.sleep(1.0)
    subprocess.run([*TMUX, "send-keys", "-t", f"hub-{sid}", f"clear; printf '  ➜  Local:   http://localhost:{dev.port}/next\\n'", "Enter"], check=True)
    time.sleep(0.6)
    said = api("GET", f"/api/browser/suggest?sid={sid}")
    check("the session's printed address is found", any(p["url"] == f"http://localhost:{dev.port}/next" for p in said.get("printed", [])), said)
    check("and the dev server is among the servers listening, with its page's title", any(l["port"] == dev.port and l["title"] == "Lab page" for l in said.get("listening", [])), said.get("listening"))

    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={CDP_PORT}", "--window-size=1440,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            target = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(target["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)
    c.call("Browser.grantPermissions", permissions=["clipboardReadWrite", "clipboardSanitizedWrite"], origin=ORIGIN)
    wait = lambda what, seconds=15: next((True for _ in range(seconds * 4) if c.js(what) or time.sleep(0.25)), False)
    c.size(1440, 900)
    url = f"http://localhost:{dev.port}/"

    # ── the browser at a desk ──
    c.call("Page.navigate", url=f"{ORIGIN}/#/")
    wait("typeof S === 'object' && S.sessions.length > 0")
    c.js("location.hash = '#/browser'")
    check("with nothing open, Copy link and New tab wait", wait("!!document.querySelector('[data-key=bro-copy]')") and c.js("document.querySelector('[data-key=bro-copy]').disabled && document.querySelector('[data-key=bro-tab]').disabled"))
    check("#/browser opens on the servers to pick from", wait(f"!!document.querySelector('[data-key=\"pick:{url}\"]')"), c.js("document.querySelector('#view').innerText.slice(0, 400)"))
    check("its title is Browser", c.js("document.title").startswith("Browser"), c.js("document.title"))
    c.shot("browser-picks")
    c.js(f"document.querySelector('[data-key=\"pick:{url}\"]').click()")
    check("a pick opens the page in a frame from the preview's origin", wait("!!document.querySelector('.bro-frame')") and c.js("document.querySelector('.bro-frame').src").startswith(f"http://127.0.0.1:{PREVIEW}/__hub/go?port={dev.port}"))
    check("the helper in the page reports its title and address", wait("document.querySelector('.bro-frame').title === 'Lab page'") and c.js("document.querySelector('.bro-url').value") == f"localhost:{dev.port}", c.js("[document.querySelector('.bro-frame').title, document.querySelector('.bro-url').value]"))
    check("the frame is sandboxed: no top navigation", "allow-top-navigation" not in c.js("document.querySelector('.bro-frame').getAttribute('sandbox')") and "allow-scripts" in c.js("document.querySelector('.bro-frame').getAttribute('sandbox')"))
    check("the green mark says it's a server on this Mac", c.js("document.querySelector('.bro-where').classList.contains('local')"))
    time.sleep(0.6)
    c.shot("browser-desk")
    c.js("document.querySelector('.bro-frame').contentWindow.postMessage({ hubFrame: 'go', path: '/next' }, hubBrowser.state.base)")
    check("moving inside the page moves the address", wait(f"document.querySelector('.bro-url').value === 'localhost:{dev.port}/next' && document.querySelector('.bro-frame').title === 'Next page'"), c.js("document.querySelector('.bro-url').value"))
    check("and Back is offered", c.js("!document.querySelector('[data-key=bro-back]').disabled"))
    c.js("document.querySelector('[data-key=bro-back]').click()")
    check("Back goes back", wait(f"document.querySelector('.bro-url').value === 'localhost:{dev.port}' && document.querySelector('.bro-frame').title === 'Lab page'"), c.js("document.querySelector('.bro-url').value"))
    check("the last address is kept", json.loads(c.js("localStorage.getItem('hub.browser.last')") or "{}").get("_") == url)
    c.js("document.querySelector('[data-key=bro-copy]').click()")
    time.sleep(0.5)
    check("Copy link copies the preview's own link, which opens on any device", c.js("navigator.clipboard.readText()") == f"http://127.0.0.1:{PREVIEW}/p/{dev.port}/", c.js("navigator.clipboard.readText()"))
    before = sum(1 for s in dev.seen if s["path"] == "/")
    c.js("document.querySelector('[data-key=bro-reload]').click()")
    check("Reload reloads the page", next((True for _ in range(20) if sum(1 for s in dev.seen if s['path'] == '/') > before or time.sleep(0.2)), False))
    c.js("(() => { const i = document.querySelector('.bro-url'); i.focus(); })()")
    check("the address bar offers the same picks as you type", wait("!document.querySelector('.bro-pop').hidden && document.querySelectorAll('.bro-opt').length > 0"))
    c.call("Input.dispatchKeyEvent", type="keyDown", key="ArrowDown", code="ArrowDown", windowsVirtualKeyCode=40)
    check("arrows walk them, as a combobox", c.js("document.querySelector('.bro-url').getAttribute('aria-activedescendant')") == "bro-opt-0")
    c.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    check("Esc closes them", c.js("document.querySelector('.bro-pop').hidden"))
    c.js(f"(() => {{ const i = document.querySelector('.bro-url'); i.value = 'localhost:{late_port}'; i.form.requestSubmit(); }})()")
    check("a server that isn't running gets a plain card, not a frame error", wait(f"(document.querySelector('.bro-card-title') || {{}}).textContent === 'Nothing is running on :{late_port}'") and not c.js("!!document.querySelector('.bro-frame')"))
    c.shot("browser-down")
    late = DevServer(hub_port=HUB_PORT, port=late_port)
    check("and the page opens by itself once it starts", wait("!!document.querySelector('.bro-frame') && document.querySelector('.bro-frame').title === 'Lab page'", 12))

    # ── a device that can't reach the preview (a phone before the Tailscale mapping) ──
    c.js("""(() => { window.__fetch = window.fetch; hubBrowser.state.base = null;
      window.fetch = (u, o) => String(u).startsWith('/api/browser/info') ? window.__fetch(u, o).then((r) => r.json()).then((d) => new Response(JSON.stringify({ ...d, bases: ['http://127.0.0.1:9'] }), { status: 200 })) : window.__fetch(u, o); })()""")
    c.js(f"(() => {{ const i = document.querySelector('.bro-url'); i.value = 'localhost:{dev.port}'; i.form.requestSubmit(); }})()")
    check("a device that can't reach the preview is told why, with the one command to run on the Mac", wait("(document.querySelector('.bro-card-title') || {}).textContent === \"This device can't reach the preview yet\"", 12)
          and c.js("document.querySelector('.bro-cmd code').textContent") == f"tailscale serve --bg --https={PREVIEW} http://127.0.0.1:{PREVIEW}", c.js("document.querySelector('.bro-stage').innerText"))
    c.shot("browser-unreachable")
    c.js("window.fetch = window.__fetch")
    c.js("document.querySelector('[data-key=bro-again]').click()")
    check("Try again finds it once it answers", wait("!!document.querySelector('.bro-frame') && document.querySelector('.bro-frame').title === 'Lab page'", 12))

    # ── at a desk before the mapping: an https hub frames this Mac's loopback, another site, so its cookies are partitioned ──
    c.js("""(() => { hubBrowser.state.base = null;
      window.fetch = (u, o) => String(u).startsWith('/api/browser/info') ? window.__fetch(u, o).then((r) => r.json()).then((d) => new Response(JSON.stringify({ ...d, bases: ['http://localhost:%d'] }), { status: 200 })) : window.__fetch(u, o); })()""" % PREVIEW)
    c.js(f"(() => {{ const i = document.querySelector('.bro-url'); i.value = 'localhost:{dev.port}/next'; i.form.requestSubmit(); }})()")
    check("a preview on another site than the hub still opens, its pass kept as a partitioned cookie", wait("!!document.querySelector('.bro-frame') && document.querySelector('.bro-frame').title === 'Next page'", 12),
          c.js("[hubBrowser.state.base, (document.querySelector('.bro-frame') || {}).src, document.querySelector('.bro-stage').innerText]"))
    c.js("window.fetch = window.__fetch; hubBrowser.state.base = null")

    # ── a page inside the preview can't reach the hub ──
    c.js(f"(() => {{ const i = document.querySelector('.bro-url'); i.value = 'localhost:{dev.port}/attack?hub={quote(ORIGIN, safe='')}'; i.form.requestSubmit(); }})()")
    got = next((dev.reports[-1] for _ in range(60) if dev.reports or time.sleep(0.25)), None)
    check("a page in the preview can't read the hub's API", got and got.get("read_state") == "blocked", got)
    check("nor write to it", got and got.get("write") in ("blocked", "status 403"), got)
    check("nor open a terminal", got and got.get("terminal") == "refused", got)
    check("nor reach the hub's page around it", got and got.get("top") == "blocked", got)
    check("and the hub's settings are as they were", "theme" not in (api("GET", "/api/settings").get("values") or {}) or api("GET", "/api/settings")["values"]["theme"] == json.loads(as_found).get("settings", {}).get("theme", "dark"))

    # ── the session's own page ──
    c.js(f"location.hash = '#/browser/{sid}'")
    c.js("localStorage.removeItem('hub.browser.last')")
    c.call("Page.reload")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    wait("typeof S === 'object' && S.sessions.length > 0")
    check("for a session, what it printed leads", wait(f"!!document.querySelector('[data-key=\"pick:http://localhost:{dev.port}/next\"]')") and "From this session" in c.js("document.querySelector('.bro-card').innerText"), c.js("(document.querySelector('.bro-card') || document.body).innerText.slice(0, 300)"))
    check("and the session's name is in the top bar", c.js(f"document.querySelector('#top a.crumb').getAttribute('href')") == f"#/s/{sid}")

    # ── the device preview at a desk ──
    c.js("localStorage.removeItem('hub.preview')")
    c.js(f"location.hash = '#/preview/-/{quote(url, safe='')}'")
    check("#/preview shows the page on an iPhone, an iPad and a laptop, side by side", wait("document.querySelectorAll('.pv-dev').length === 3") and c.js("[...document.querySelectorAll('.pv-dev')].map(d => d.dataset.device).join()") == "iphone,ipad,laptop")
    fits = "(() => { const st = document.querySelector('.pv-stage').getBoundingClientRect(); return [...document.querySelectorAll('.pv-dev')].every(d => { const r = d.getBoundingClientRect(); return r.left >= st.left - 1 && r.right <= st.right + 1 && r.bottom <= st.bottom + 1; }); })()"
    check("scaled to fit the screen, all at one scale", wait(fits) and len(set(c.js("[...document.querySelectorAll('.pv-frame')].map(f => f.style.transform)"))) == 1 and "%" in c.js("document.querySelector('.pv-size').textContent"))
    check("each frame is the device's real size inside", c.js("[...document.querySelectorAll('.pv-frame')].map(f => f.style.width + 'x' + f.style.height).join()") == "390pxx844px,820pxx1180px,1440pxx900px")
    time.sleep(1.2)
    c.shot("preview-desk")
    c.js("document.querySelector('[data-key=\"pv-dev:small\"]').click()")
    check("a device switched on joins in its place", wait("document.querySelectorAll('.pv-dev').length === 4") and c.js("[...document.querySelectorAll('.pv-dev')].map(d => d.dataset.device).join()") == "iphone,small,ipad,laptop")
    c.js("document.querySelector('[data-key=\"pv-turn:iphone\"]').click()")
    check("Rotate turns one device", wait("document.querySelector('[data-device=iphone] .pv-size').textContent.startsWith('844 × 390')"), c.js("document.querySelector('[data-device=iphone] .pv-size').textContent"))
    wait("[...document.querySelectorAll('.pv-frame')].length === 4")
    time.sleep(1.5)
    nexts = sum(1 for s in dev.seen if s["path"] == "/next")
    c.js("document.querySelector('.pv-frame').contentWindow.postMessage({ hubFrame: 'go', path: '/next' }, hubBrowser.state.base)")
    check("moving in one device moves them all", next((True for _ in range(40) if sum(1 for s in dev.seen if s['path'] == '/next') >= nexts + 4 or time.sleep(0.25)), False)
          and wait(f"document.querySelector('.bro-url').value === 'localhost:{dev.port}/next'"), sum(1 for s in dev.seen if s["path"] == "/next") - nexts)
    time.sleep(0.8)
    nexts = sum(1 for s in dev.seen if s["path"] == "/next")
    c.js("document.querySelector('[data-key=pv-reload]').click()")
    check("Reload all reloads every device", next((True for _ in range(40) if sum(1 for s in dev.seen if s['path'] == '/next') >= nexts + 4 or time.sleep(0.25)), False), sum(1 for s in dev.seen if s["path"] == "/next") - nexts)
    c.js("document.querySelector('[data-key=pv-fit]').click()")
    check("Fit off shows them at full size, to scroll", wait("document.querySelector('.pv-stage').classList.contains('scroll')") and "%" not in c.js("document.querySelector('.pv-size').textContent"))
    c.js("document.querySelector('[data-key=pv-fit]').click()")
    c.js("document.querySelector('[data-key=\"pv-turn:iphone\"]').click()")
    c.js("document.querySelector('[data-key=\"pv-dev:small\"]').click()")

    # ── the side panels ──
    check("the browser and the device preview are panels, each behind its switch", c.js("JSON.stringify(PANELS.filter(p => ['browser', 'preview'].includes(p.id)).map(p => [p.id, p.feature]))") == '[["browser","browser"],["preview","preview"]]')
    c.js(f"(() => {{ const box = document.createElement('div'); box.id = 'panel-test'; box.style.cssText = 'position:fixed;right:0;top:0;width:380px;height:760px;display:flex;flex-direction:column;z-index:99;background:var(--panel)'; document.body.append(box); box.append(PANELS.find(p => p.id === 'browser').render(session('{sid}'), box)); }})()")
    check("the browser panel works beside a session, narrow", wait("!!document.querySelector('#panel-test .bro.compact')") and c.js("document.querySelector('#panel-test .bro-field').getBoundingClientRect().width") > 300)
    c.js("PANELS.find(p => p.id === 'browser').leave(); document.getElementById('panel-test').remove()")

    # ── Go to ──
    c.js("location.hash = '#/'")
    wait("!document.querySelector('.bro, .pv')")
    c.js("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))")
    wait("!!document.querySelector('dialog.palette')")
    c.js("(() => { const i = document.querySelector('dialog.palette input'); i.value = 'device preview'; i.dispatchEvent(new Event('input')); })()")
    check("Go to offers the browser and the device preview", c.js("[...document.querySelectorAll('dialog.palette .opt')].some(o => o.textContent.includes('Device preview'))"))
    c.js("document.querySelector('dialog.palette').close()")

    # ── the phone ──
    c.size(390, 844, mobile=True)
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.js(f"location.hash = '#/browser/-/{quote(url, safe='')}'")
    check("on a phone the page fills the screen under the bar", wait("!!document.querySelector('.bro-frame') && document.querySelector('.bro-frame').title === 'Lab page'"))
    check("the address takes a line of its own, with room to read it", c.js("document.querySelector('.bro-field').getBoundingClientRect().width") > 340 and c.js("getComputedStyle(document.querySelector('.bro-url')).fontSize") == "16px")
    check("nothing runs off the side", c.js("document.documentElement.scrollWidth <= innerWidth"))
    check("the buttons are big enough to tap", c.js("Math.min(...[...document.querySelectorAll('.bro-bar .bro-btn')].map(b => b.getBoundingClientRect().height))") >= 36)
    time.sleep(0.8)
    c.shot("browser-phone")
    c.js(f"location.hash = '#/preview/-/{quote(url, safe='')}'")
    check("the preview on a phone shows one device, with a picker", wait("document.querySelectorAll('.pv-dev').length === 1 && !!document.querySelector('.pv-pick')"))
    c.js("(() => { const s = document.querySelector('.pv-pick'); s.value = 'ipad'; s.dispatchEvent(new Event('change')); })()")
    check("the picker changes the device", wait("document.querySelector('.pv-dev').dataset.device === 'ipad'"))
    check("which fits the phone's screen", c.js("document.querySelector('.pv-screen').getBoundingClientRect().right <= innerWidth") and c.js("document.documentElement.scrollWidth <= innerWidth"))
    c.js("(() => { const s = document.querySelector('.pv-pick'); s.value = 'iphone'; s.dispatchEvent(new Event('change')); })()")
    wait("document.querySelector('.pv-dev').dataset.device === 'iphone'")
    time.sleep(1.2)
    c.shot("preview-phone")
    c.size(1440, 900)
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})

    # ── both switches off: today's hub, at once ──
    shape = "[...document.querySelectorAll('#view *, #side *, #top *')].map(e => e.tagName + '.' + e.className).join('|')"
    c.js(f"location.hash = '#/browser/-/{quote(url, safe='')}'")
    wait("!!document.querySelector('.bro-frame')")
    c.js("saveSettings({ feature_browser: false, feature_preview: false })")
    check("switching both off leaves the browser at once, for Home", wait("route().name === 'now' && !document.querySelector('.bro, .pv')"), c.js("location.hash"))
    check("their routes lead Home", c.js("location.hash = '#/preview'; route().name") == "now")
    check("their panels are gone", c.js("panelsFor(session('%s') || {}).filter(p => ['browser', 'preview'].includes(p.id)).length" % sid) == 0)
    # Other checks may add or remove throwaway projects meanwhile, so Home is compared on and off a moment apart, a few times.
    c.js("location.hash = '#/'")
    same = False
    for _ in range(4):
        time.sleep(0.8)
        off = c.js(shape)
        c.js("saveSettings({ feature_browser: true, feature_preview: true })")
        time.sleep(0.8)
        on = c.js(shape)
        c.js("saveSettings({ feature_browser: false, feature_preview: false })")
        if on == off:
            same = True
            break
    check("Home, the sidebar and the top bar are built exactly the same with them off", same)
    time.sleep(0.5)
    c.js("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))")
    wait("!!document.querySelector('dialog.palette')")
    c.js("(() => { const i = document.querySelector('dialog.palette input'); i.value = 'browser'; i.dispatchEvent(new Event('input')); })()")
    check("Go to has no browser", not c.js("[...document.querySelectorAll('dialog.palette .opt')].some(o => /^(Browser|Device preview)/.test(o.querySelector('.t').textContent))"))
    c.js("document.querySelector('dialog.palette').close()")
    c.js("saveSettings({ feature_browser: true, feature_preview: true })")
    c.js(f"location.hash = '#/browser/-/{quote(url, safe='')}'")
    check("switched on again, it works without a reload", wait("!!document.querySelector('.bro-frame') && document.querySelector('.bro-frame').title === 'Lab page'"))
    check("no script errors on the way", not c.errors, c.errors)
finally:
    if chrome:
        chrome.terminate()
    shutil.rmtree(profile, ignore_errors=True)
    if sid:
        api("POST", f"/api/sessions/{sid}/stop", {})
        api("POST", f"/api/sessions/{sid}/dismiss", {})
    CONFIG.write_bytes(as_found)
    dev.stop()
    if late:
        late.stop()

print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
