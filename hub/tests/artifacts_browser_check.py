#!/usr/bin/env python3
"""The artifact viewer in headless Chrome, at desk and phone sizes: #/s/<id>/artifacts and #/p/<project>/artifacts,
the list with its kinds, filter and keys, each kind in its viewer (an HTML page sandboxed so it can't reach the hub's
API, markdown, a table, JSON, code, pictures, SVG only as a picture, a PDF, a published link), the actions, finding
where it was made in the chat, a live reload when the file is written again, the side panel's list, the phone's one
column with its full-screen viewer and back, and the switch: off, the hub is as it was, at once and after a reload.

A made-up session (artifacts_fixture.py) in a throwaway project, hub-test-throwaway-<n>, made here and removed at the
end, against a second instance (the six HUB_* variables, see tests/instance.py), with Chrome's debugging port
HUB_CDP_PORT. Screenshots go to the folder given as the first argument, else a temporary one.
Run: /usr/bin/python3 tests/artifacts_browser_check.py [screenshot folder]
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, PORT as HUB_PORT, WRITE, base, launchd_jobs, quiet_alert, remove_project, sweep
import artifacts_fixture as fx

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-artifacts.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9343"))
REPO = HOME / "projects" / NAME
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read() or b"{}")


def waited(test, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.25)
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
        time.sleep(0.2)

    def click(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (e) e.click(); return !!e; }})()")

    def text(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); return e ? e.innerText : null; }})()")

    def go(self, route, ready, seconds=20):
        self.js(f"location.hash = {json.dumps(route)}")
        return waited(lambda: self.js(ready), seconds)

    def pick(self, name):
        """Click the row whose name is this, and wait for its viewer."""
        self.js(f"[...document.querySelectorAll('.art-row')].find(r => r.querySelector('b').textContent === {json.dumps(name)}).click()")
        return waited(lambda: self.js(f"(() => {{ const b = document.querySelector('.art-body'); return document.querySelector('.art-title b').textContent === {json.dumps(name)} && (b.dataset.shown || '').endsWith('/' + {json.dumps(name)}); }})()"), 10)

    def open_hub(self, route):
        self.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})  # set again: a reload is a new connection
        self.call("Page.navigate", url=CFG["origin"] + "/" + route)
        return waited(lambda: self.js("!!document.querySelector('#side .nav')"), 20)


def rows():
    return c.js("[...document.querySelectorAll('.art-row')].map(r => r.querySelector('b').textContent)") or []


sweep()
launchd_before = launchd_jobs()
config_before = base.CONFIG.read_bytes()
elsewhere = Path(tempfile.mkdtemp(prefix="artifacts-browser.", dir=f"/private/tmp/claude-{os.getuid()}"))
sid = os.urandom(4).hex()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
# Chrome puts a sandboxed frame in a process of its own, where the debugger's extra header (the stand-in for Tailscale's)
# doesn't reach, so the page's own picture would be refused. Behind Tailscale Serve the header is added to every request.
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--disable-features=IsolateSandboxedIframes", f"--user-data-dir={profile}",
                           f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
desk = dict(width=1440, height=900, deviceScaleFactor=1, mobile=False)
handset = dict(width=390, height=844, deviceScaleFactor=2, mobile=True)
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    api("PUT", "/api/settings", {"feature_artifacts": True, "feature_browser": True})
    fx.make(REPO, sid, NAME, "Made one of everything", elsewhere)
    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Emulation.setDeviceMetricsOverride", **desk)
    c.open_hub("#/")
    c.js("localStorage.clear()")

    # ── desk: the list ──
    ok = c.go(f"#/s/{sid}/artifacts", "document.querySelectorAll('.art-row').length >= 15")
    check("the session's artifacts are listed", ok, rows())
    names = rows()
    check("each once, the secret and the deleted left out", len(names) == len(set(names)) and ".env" not in names and "gone.md" not in names, names)
    check("the page's title says what it is", "Artifacts" in (c.js("document.title") or ""), c.js("document.title"))
    check("a desk shows the newest at once beside the list", waited(lambda: c.js("!!document.querySelector('.art-view .art-body').firstElementChild")), c.text(".art-view"))
    chips = c.js("[...document.querySelectorAll('.art-chip')].map(b => b.innerText.replace(/\\s+/g, ' '))")
    check("the kinds to filter by, each with its count", chips and chips[0] == "All 15" and "Pages 1" in chips and "Links 3" in chips, chips)
    c.click('.art-chip[data-key="kind:image"]')
    check("a kind filters the list", sorted(rows()) == ["chart.png", "logo.svg"], rows())
    c.click('.art-chip[data-key="kind:all"]')
    c.js("{ const s = document.querySelector('.art-search'); s.value = 'note'; s.dispatchEvent(new Event('input')); }")
    check("typing filters by name", rows() == ["notes.md"], rows())
    c.js("{ const s = document.querySelector('.art-search'); s.value = 'zzzz'; s.dispatchEvent(new Event('input')); }")
    check("and says when nothing matches", c.text(".art-list") == "Nothing matches.", c.text(".art-list"))
    c.js("{ const s = document.querySelector('.art-search'); s.value = ''; s.dispatchEvent(new Event('input')); }")
    c.shot("01-desk-list")

    # ── each kind in its viewer ──
    c.js("window.__probe = null; window.__svg = false; window.addEventListener('message', (e) => { if (e.data && e.data.artifactProbe) window.__probe = e.data.artifactProbe; if (e.data && e.data.svgRan) window.__svg = true; })")
    check("the HTML page opens", c.pick("report.html"))
    frame = c.js("(() => { const f = document.querySelector('.art-body iframe'); return f && { sandbox: f.getAttribute('sandbox'), src: f.getAttribute('src') }; })()")
    check("in an iframe sandboxed without allow-same-origin", frame and "allow-scripts" in frame["sandbox"] and "allow-same-origin" not in frame["sandbox"], frame)
    probe = waited(lambda: c.js("window.__probe"), 15)
    check("its script runs, in an opaque origin of its own", probe and probe.get("scripts") and probe.get("origin") == "null", probe)
    check("it can't read the hub's API", probe and probe.get("state") == "blocked", probe)
    check("it can't write to the hub's API", probe and probe.get("write") == "blocked", probe)
    check("it can't reach the hub page, its storage or its cookie", probe and probe.get("parent") == "blocked" and probe.get("storage") == "blocked" and probe.get("cookie") == "blocked", probe)
    check("its own folder's picture loads", probe and probe.get("pic") is True, probe)
    check("the hub page can't reach into it either", c.js("document.querySelector('.art-body iframe').contentDocument === null"))
    acts = c.js("[...document.querySelectorAll('.art-acts > *')].map(a => a.getAttribute('title'))")
    check("a page offers: open in the browser, show in chat, copy path, download, open in a new tab", acts == ["Open in the browser", "Show in chat", "Copy path", "Download", "Open in a new tab"], acts)
    hrefs = c.js("[...document.querySelectorAll('.art-acts a')].map(a => a.getAttribute('href'))")
    check("download and new tab point at the file itself", hrefs and hrefs[0].endswith("report.html?download=1") and "/raw/" in hrefs[1], hrefs)
    c.shot("02-desk-html")

    check("markdown opens", c.pick("notes.md"))
    doc = c.js("(() => { const d = document.querySelector('.art-doc .doc'); return d && { h: d.querySelector('h3') && d.querySelector('h3').textContent, strong: !!d.querySelector('strong'), li: d.querySelectorAll('li').length, table: !!d.querySelector('table'), pre: !!d.querySelector('pre') }; })()")
    check("rendered in the hub's own typography: heading, bold, list, table, code", doc == {"h": "Release notes", "strong": True, "li": 2, "table": True, "pre": True}, doc)
    check("it says it has two versions", "2 versions" in (c.text(".art-meta") or ""), c.text(".art-meta"))
    c.shot("03-desk-markdown")
    check("a CSV opens", c.pick("data.csv"))
    table = c.js("[...document.querySelectorAll('.art-table tr')].map(r => [...r.children].map(x => x.textContent))")
    check("as a table", table == [["city", "visits", "share"], ["Lisbon", "120", "0.4"], ["Oslo", "95", "0.31"], ["Kyoto", "88", "0.29"]], table)
    check("numbers to the right", c.js("document.querySelectorAll('.art-table td.num').length") == 6)
    check("JSON opens", c.pick("data.json"))
    tree = c.js("(() => ({ nodes: document.querySelectorAll('.art-json details').length, open: document.querySelectorAll('.art-json details[open]').length, str: document.querySelector('.art-json .j-str').textContent }))()")
    check("as a tree, folding below the second level", tree["nodes"] == 7 and tree["open"] == 3 and tree["str"] == '"demo"', tree)
    check("code opens", c.pick("greet.py"))
    code = c.js("(() => ({ lines: document.querySelectorAll('.art-code > span').length, kw: [...document.querySelectorAll('.art-code .tk-k')].map(x => x.textContent), str: document.querySelectorAll('.art-code .tk-s').length, com: document.querySelectorAll('.art-code .tk-c').length }))()")
    check("with a line per row and light highlighting", code["lines"] == 7 and "def" in code["kw"] and "return" in code["kw"] and code["str"] >= 2 and code["com"] == 1, code)
    check("a picture opens", c.pick("chart.png"))
    check("it loads", waited(lambda: c.js("(() => { const i = document.querySelector('.art-pic img'); return i && i.naturalWidth === 64; })()"), 10))
    c.click('.art-acts button[title="Zoom"]')
    check("zoom opens the hub's image viewer", waited(lambda: c.js("!!document.querySelector('dialog.viewer[open] .v-img')"), 10))
    c.key("Escape")
    check("and Esc closes it", waited(lambda: c.js("!document.querySelector('dialog[open]')"), 5))
    check("an SVG opens", c.pick("logo.svg"))
    svg = c.js("(() => { const b = document.querySelector('.art-body'); return { img: !!b.querySelector('img[src*=\"logo.svg\"]'), inline: !!b.querySelector('svg rect') }; })()")
    check("only ever as a picture, never inline", svg == {"img": True, "inline": False}, svg)
    time.sleep(0.5)
    check("its script never runs", c.js("window.__svg") is False)
    check("a PDF opens in the browser's own viewer", c.pick("brief.pdf") and c.js("!!document.querySelector('.art-body iframe.pdf')"))
    check("a recording opens with its player", c.pick("voice.wav") and c.js("!!document.querySelector('.art-body audio[controls]')"))
    c.js("[...document.querySelectorAll('.art-row')].find(r => r.title.startsWith('https://claude.ai/public/artifacts/')).click()")
    check("a published link opens as its card", waited(lambda: c.js("!!document.querySelector('.art-link')"), 10) and c.js("!!document.querySelector('.art-link .m-link') && document.querySelector('.art-link .btn.primary').href.startsWith('https://claude.ai/public/artifacts/')"))
    link_acts = c.js("[...document.querySelectorAll('.art-acts > *')].map(a => a.getAttribute('title'))")
    check("a link offers show in chat, copy link and open", link_acts == ["Show in chat", "Copy link", "Open in a new tab"], link_acts)

    # ── keys ──
    c.go(f"#/s/{sid}/artifacts", "true")
    c.js("document.querySelector('.art-row.on').focus()")
    first = c.js("document.activeElement.querySelector('b').textContent")
    c.key("ArrowDown")
    second = c.js("document.activeElement.querySelector('b') && document.activeElement.querySelector('b').textContent")
    check("↓ moves to the next and shows it", second and second != first and waited(lambda: c.js(f"document.querySelector('.art-title b').textContent === {json.dumps(second)}"), 5), (first, second))
    check("the hash keeps the pick, without a history step", c.js("decodeURIComponent(location.hash)").endswith("/" + second) or second in c.js("decodeURIComponent(location.hash)"), c.js("location.hash"))
    c.key("ArrowUp")
    check("↑ moves back", c.js("document.activeElement.querySelector('b').textContent") == first)
    c.key("Enter")
    check("↵ moves into the viewer", c.js("document.activeElement.classList.contains('art-body')"))
    c.js("document.querySelector('.art-row.on').focus()")
    c.key("Escape")
    check("Esc goes back to the session", waited(lambda: c.js(f"location.hash === '#/s/{sid}'"), 5), c.js("location.hash"))

    # ── show in chat ──
    c.go(f"#/s/{sid}/artifacts", "document.querySelectorAll('.art-row').length >= 15")
    c.pick("notes.md")
    c.click('.art-acts button[title="Show in chat"]')
    found = waited(lambda: c.js("(() => { const t = document.querySelector('.turn.art-found'); return t && t.textContent.includes('notes.md'); })()"), 10)
    check("show in chat opens the session and lights the turn where it was made", found and c.js("location.hash") == f"#/s/{sid}", c.js("location.hash"))
    c.shot("04-desk-show-in-chat")
    check("the session's panel links to everything it made", waited(lambda: c.js(f"!!document.querySelector('.shared a.art-all[href=\"#/s/{sid}/artifacts\"]')"), 10))

    # ── live: written again, shown again ──
    c.go(f"#/s/{sid}/artifacts", "document.querySelectorAll('.art-row').length >= 15")
    c.pick("notes.md")
    (REPO / "notes.md").write_text(fx.NOTES_V2 + "\nA line written live.\n")
    with open(fx.hub.RECORDS / sid / "transcript.jsonl", "a") as f:
        f.write(json.dumps(fx.say(0, [fx.use("e9", "Edit", {"file_path": str(REPO / "notes.md"), "old_string": "x", "new_string": "y"})])) + "\n")
    live = waited(lambda: c.js("document.querySelector('.art-doc') && document.querySelector('.art-doc').textContent.includes('A line written live.')"), 25)
    check("a file the session writes again reloads in the viewer", live)
    check("and says it was updated, with its new version count", live and "3 versions" in (c.text(".art-meta") or ""), c.text(".art-meta"))

    # ── the project's artifacts ──
    ok = c.go(f"#/p/{NAME}/artifacts", "document.querySelectorAll('.art-row').length >= 15")
    check("the project page lists every session's artifacts", ok, rows())
    check("its top bar has an Artifacts tab, on", c.js("(() => { const t = document.querySelector('.ptab[data-key=\"tab:artifacts\"]'); return t && t.classList.contains('on'); })()"))
    check("each row names its session", "Made one of everything" in (c.text(".art-row small") or ""), c.text(".art-row small"))
    c.shot("05-desk-project")

    # ── the side panel ──
    panel = c.js(f"""(async () => {{
      const s = S.sessions.find((x) => x.id === {json.dumps(sid)});
      const p = PANELS.find((x) => x.id === 'artifacts');
      if (!p || !s) return null;
      const box = document.createElement('div'); box.id = 'panel-test'; box.style.cssText = 'position:fixed;right:0;top:40px;width:340px;height:600px;display:flex;flex-direction:column;background:var(--ground);z-index:50';
      document.body.append(box); box.append(p.render(s, box));
      return {{ listed: panelsFor(s).some((x) => x.id === 'artifacts'), title: p.title, icon: p.icon, feature: p.feature }};
    }})()""")
    check("the side panel offers Artifacts for a Claude session", panel and panel["listed"] and panel["feature"] == "artifacts", panel)
    check("in one column", waited(lambda: c.js("document.querySelectorAll('#panel-test .art.narrow .art-row').length >= 15"), 10))
    c.js("[...document.querySelectorAll('#panel-test .art-row')].find(r => r.querySelector('b').textContent === 'data.csv').click()")
    check("a pick there fills the panel, with a way back", waited(lambda: c.js("document.querySelector('#panel-test .art').classList.contains('viewing') && !!document.querySelector('#panel-test .art-table')"), 10))
    c.shot("06-desk-panel")
    c.click("#panel-test .art-back")
    check("back returns to its list", waited(lambda: c.js("!document.querySelector('#panel-test .art').classList.contains('viewing')"), 5))
    c.js("PANELS.find((x) => x.id === 'artifacts').leave(); document.getElementById('panel-test').remove()")

    # ── phone ──
    c.call("Emulation.setDeviceMetricsOverride", **handset)
    c.open_hub(f"#/s/{sid}/artifacts")
    ok = waited(lambda: c.js("document.querySelectorAll('.art.narrow .art-row').length >= 15 && getComputedStyle(document.querySelector('.art-view')).display === 'none'"), 20)
    check("a phone shows the list alone, in one column", ok)
    c.shot("07-phone-list")
    before = c.js("history.length")
    c.js("[...document.querySelectorAll('.art-row')].find(r => r.querySelector('b').textContent === 'notes.md').click()")
    full = waited(lambda: c.js("document.querySelector('.art').classList.contains('viewing') && getComputedStyle(document.querySelector('.art-side')).display === 'none' && !!document.querySelector('.art-doc')"), 10)
    check("a tap opens it full screen", full)
    check("with a back button and big targets", c.js("(() => { const b = document.querySelector('.art-back'); const r = b.getBoundingClientRect(); return getComputedStyle(b).display !== 'none' && r.width >= 40 && r.height >= 40; })()"))
    check("the hash keeps it, as a step back", c.js("history.length") == before + 1 and "notes.md" in c.js("decodeURIComponent(location.hash)"), c.js("location.hash"))
    c.shot("08-phone-viewer")
    c.js("history.back()")
    check("the phone's back returns to the list", waited(lambda: c.js("!document.querySelector('.art').classList.contains('viewing') && location.hash.endsWith('/artifacts')"), 5), c.js("location.hash"))
    c.js("[...document.querySelectorAll('.art-row')].find(r => r.querySelector('b').textContent === 'data.json').click()")
    waited(lambda: c.js("document.querySelector('.art').classList.contains('viewing')"), 5)
    c.click(".art-back")
    check("so does the back button", waited(lambda: c.js("!document.querySelector('.art').classList.contains('viewing') && location.hash.endsWith('/artifacts')"), 5), c.js("location.hash"))
    check("and focus returns to the row it opened", waited(lambda: c.js("document.activeElement && document.activeElement.classList.contains('art-row') && document.activeElement.textContent.includes('data.json')"), 5))
    c.js("[...document.querySelectorAll('.art-row')].find(r => r.querySelector('b').textContent === 'greet.py').click()")
    waited(lambda: c.js("document.querySelector('.art').classList.contains('viewing')"), 5)
    c.key("Escape")
    check("Esc closes the viewer on a phone too", waited(lambda: c.js("!document.querySelector('.art').classList.contains('viewing')"), 5))
    overflow = c.js("document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll('.art-row')].every(r => r.getBoundingClientRect().right <= innerWidth)")
    check("nothing runs off the side of the phone", overflow)
    c.call("Emulation.setDeviceMetricsOverride", **desk)

    # ── the switch: off is the hub as it was, at once ──
    c.open_hub(f"#/s/{sid}/artifacts")
    waited(lambda: c.js("document.querySelectorAll('.art-row').length >= 15"), 20)
    c.js("window.saveSettings({ feature_artifacts: false })")
    check("off, an open artifacts page gives way to the session at once", waited(lambda: c.js("!document.querySelector('.art') && !!document.querySelector('.pane')"), 10), c.js("location.hash"))
    check("the session's panel no longer links to them", waited(lambda: c.js("!document.querySelector('.art-all')"), 15))
    c.go(f"#/p/{NAME}", "!!document.querySelector('.ptabs')")
    tabs = c.js("[...document.querySelectorAll('.ptab')].map(t => t.dataset.key)")
    check("the project's tabs are as before: Sessions, Memory, Dreams", tabs == ["tab:home", "tab:memory", "tab:dreams"], tabs)
    c.open_hub(f"#/p/{NAME}/artifacts")
    check("after a reload, the old address shows the project's sessions page", waited(lambda: c.js("!document.querySelector('.art') && !!document.querySelector('.ptab.on[data-key=\"tab:home\"]')"), 15))
    c.js("window.saveSettings({ feature_artifacts: true })")
    check("on again, the tab comes back at once", waited(lambda: c.js("!!document.querySelector('.ptab[data-key=\"tab:artifacts\"]')"), 10))
    check("no script errors", not c.errors, c.errors)
finally:
    try:
        api("PUT", "/api/settings", {"feature_artifacts": True})
    except OSError:
        pass
    base.CONFIG.write_bytes(config_before)
    fx.remove(sid)
    shutil.rmtree(elsewhere, ignore_errors=True)
    chrome.terminate()
    shutil.rmtree(profile, ignore_errors=True)
    left = remove_project(NAME)
    check("the throwaway project is gone", not left, left)
    check("no launchd job was made", launchd_jobs() == launchd_before)

print(f"\n{'all passed' if not failures else f'{failures} failed'}  (screenshots in {OUT})")
sys.exit(1 if failures else 0)
