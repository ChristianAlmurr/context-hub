#!/usr/bin/env python3
"""Appearance, end to end, in headless Chrome: theme, accent, terminal font size, density and motion.

Every value is set as the Settings page sets it (SETTINGS, then the "hub:settings" event), so this runs with or without
that page. A throwaway project, hub-test-throwaway-<n>, with one plain terminal, made here and removed at the end:
- Dark is the default and its colours are the ones it always had; the media viewer stays dark in every theme.
- Light: every text colour passes WCAG AA on every surface, the terminal takes Morning paper's palette, the phone's chrome colour
  follows, and a reload is light from its first frame (the cache in localStorage, before the server answers).
- System follows prefers-color-scheme live, with no event.
- An accent that would fail contrast (yellow, pale, dark) is moved until it passes; a nonsense colour is ignored; "" restores.
- The terminal's font size changes live and the terminal refits; compact density tightens the sidebar rows.
- reduce_motion "on" stills the cubes whatever the system says, "off" lets them move under a system that asks for less.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/theme_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-theme.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0
# Midnight ink as it was before themes: these must never move.
DARK = {"--ground": "#0b1020", "--panel": "#11182b", "--field": "#18213a", "--raise": "#212c4a", "--ink": "#eef2ff", "--soft": "#b4beda",
        "--faint": "#8a97ba", "--accent": "#2f62f5", "--accent-ink": "#8fb0ff", "--accent-wash": "#16245a", "--go": "#2dd4a0", "--trouble": "#ff5c8a", "--term": "#0a0f1e"}
TEXTS = ["--ink", "--soft", "--faint", "--accent-ink", "--go", "--trouble", "--done"]
SURFACES = ["--ground", "--panel", "--field", "--raise", "--term"]


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
        hostport, path = url.split("//")[1].split("/", 1)
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

    def settings(self, **values):
        """What the Settings page does on a change: the new values in SETTINGS, then the event."""
        self.js(f"Object.assign(SETTINGS, {json.dumps(values)}); window.dispatchEvent(new Event('hub:settings'))")
        time.sleep(0.3)

    def token(self, name, el="document.documentElement"):
        return self.js(f"getComputedStyle({el}).getPropertyValue({json.dumps(name)}).trim().toLowerCase()")

    def media(self, **features):
        self.call("Emulation.setEmulatedMedia", features=[{"name": k.replace("_", "-"), "value": v} for k, v in features.items()])
        time.sleep(0.3)


sweep()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sid = None
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    sid = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]
    page = waited(lambda: next((t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page"), None))
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    # What the page is on its first frame, before app.js or the server could say anything.
    c.call("Page.addScriptToEvaluateOnNewDocument", source="requestAnimationFrame(() => { window.firstFrame = { theme: document.documentElement.dataset.theme || 'dark', ground: getComputedStyle(document.documentElement).getPropertyValue('--ground').trim() }; });")
    c.media(prefers_color_scheme="dark", prefers_reduced_motion="no-preference")
    c.call("Page.navigate", url=CFG["origin"] + f"/#/s/{sid}")
    check("the page loads", waited(lambda: c.js("!!document.querySelector('.xterm-screen')")), c.js("document.body.innerText.slice(0, 200)"))
    time.sleep(1)

    # Dark, the default: unchanged.
    check("dark is the default", c.js("document.documentElement.dataset.theme") is None and c.js("window.firstFrame.theme") == "dark")
    moved = {k: (c.token(k), v) for k, v in DARK.items() if c.token(k) != v}
    check("Midnight ink's colours are the ones it had", not moved, moved)
    check("the terminal keeps its dark colours", c.js("[...liveTerms][0].term.options.theme.background") == "#0a0f1e")
    check("and xterm's own 256 colours", c.js("(t => [t._core._themeService.colors.ansi[237].css, t._core._themeService.colors.ansi[231].css])([...liveTerms][0].term)") == ["#3a3a3a", "#ffffff"])
    check("the phone's chrome is the dark ground", c.js("document.querySelector('meta[name=theme-color]').content") == "#0b1020")

    # Light.
    c.settings(theme="light")
    check("light applies at once", c.js("document.documentElement.dataset.theme") == "light" and c.token("--ground") == "#efeeea")
    low = []
    for t in TEXTS:
        for s in SURFACES:
            ratio = c.js(f"hubAppearance.contrast({json.dumps(c.token(t))}, {json.dumps(c.token(s))})")
            if ratio < 4.5:
                low.append(f"{t} on {s}: {ratio:.2f}")
    check("every light text colour passes AA on every surface", not low, low)
    pairs = {"on-accent on accent": ("--on-accent", "--accent"), "ground on trouble (a count, Delete)": ("--ground", "--trouble"), "ground on ink (a hovered button)": ("--ground", "--ink"), "ink on accent-wash (your bubble)": ("--ink", "--accent-wash")}
    low = [f"{k}: {r:.2f}" for k, (a, b) in pairs.items() if (r := c.js(f"hubAppearance.contrast({json.dumps(c.token(a))}, {json.dumps(c.token(b))})")) < 4.5]
    check("light's filled pairs pass AA", not low, low)
    check("the terminal takes Morning paper's palette, and lifts faint colours", c.js("(t => t.options.theme.background === '#fdfcfa' && t.options.minimumContrastRatio === 4.5)([...liveTerms][0].term)"))
    check("the phone's chrome follows the theme", c.js("document.querySelector('meta[name=theme-color]').content") == "#efeeea")
    # Morning paper's marks and edges: 3:1 on every surface (WCAG 1.4.11), as are the project colours; chart colours
    # used as words in code (numbers, keywords) pass AA. The ANSI 16 pass AA on the terminal's paper.
    def worst(a, grounds):
        return min(c.js(f"hubAppearance.contrast({json.dumps(a)}, {json.dumps(c.token(g))})") for g in grounds)
    pcs = ["--pc-" + n for n in ("blue", "jade", "pink", "gold", "sky", "violet", "orange", "lime", "slate")] + [f"--id-{i}" for i in range(6)]
    low = [f"{m}: {r:.2f}" for m in ["--mark", "--k-r", "--k-err", "--k-x", "--k-m"] + pcs if (r := worst(c.token(m), SURFACES)) < 3]
    low += [f"--k-a/--k-e as words: {r:.2f}" for m in ("--k-a", "--k-e") if (r := worst(c.token(m), SURFACES)) < 4.5]
    check("light marks, project colours and chart colours reach 3:1 on every surface (words in code 4.5:1)", not low, low)
    alpha = c.js("(() => { const v = getComputedStyle(document.documentElement).getPropertyValue('--edge').trim(); const n = v.match(/[\\d.]+/g).map(Number); return n; })()")
    over = lambda g: "#" + "".join(f"{round(alpha[i] * alpha[3] + int(g[1 + 2 * i:3 + 2 * i], 16) * (1 - alpha[3])):02x}" for i in range(3))
    low = [f"edge on {s}: {r:.2f}" for s in SURFACES if (r := c.js(f"hubAppearance.contrast({json.dumps(over(c.token(s)))}, {json.dumps(c.token(s))})")) < 3]
    check("a field's edge reaches 3:1 on every light surface", not low, low)
    clash = [f"{i} is {c.token(i)}" for i in ("--id-1", "--id-2") if c.token(i) in (c.token("--go"), c.token("--trouble"), c.token("--done"))]
    check("no project identity colour is a state's colour", not clash, clash)
    ansi = c.js("(t => ['black','red','green','yellow','blue','magenta','cyan','white','brightBlack','brightRed','brightGreen','brightYellow','brightBlue','brightMagenta','brightCyan','brightWhite'].map(k => [k, t.options.theme[k]]))([...liveTerms][0].term)")
    low = [f"{k}: {r:.2f}" for k, v in ansi if (r := c.js(f"hubAppearance.contrast({json.dumps(v)}, '#fdfcfa')")) < 4.5]
    check("the light terminal's 16 colours pass AA on its paper", not low, low)
    # Claude Code paints for a dark terminal, through tmux's 256 colours: in light its band behind your own message
    # (237) is a faint tint of the paper, not a dark strip, its white words (231) are the ink, and its black the paper.
    pal = c.js("(t => [16, 22, 52, 231, 237].map(i => t._core._themeService.colors.ansi[i].css))([...liveTerms][0].term)")
    band = c.js(f"hubAppearance.contrast({json.dumps(pal[4])}, '#fdfcfa')")
    check(f"Claude Code's dark bands turn faint on paper (your message's band {pal[4]}, {band:.2f}:1)", band < 1.3 and pal[0] == "#fdfcfa" and pal[3] == "#131928" and all(c.js(f"hubAppearance.contrast({json.dumps(x)}, '#fdfcfa')") < 1.6 for x in pal[1:3]), pal)
    c.js("document.body.insertAdjacentHTML('beforeend', '<dialog class=viewer id=probe-viewer></dialog>')")
    check("the media viewer stays dark in light", c.token("--ground", "document.getElementById('probe-viewer')") == "#0b1020")
    c.js("document.getElementById('probe-viewer').remove()")
    c.shot("1-light")
    c.js("location.reload()")
    waited(lambda: c.js("!!(window.firstFrame && document.querySelector('.xterm-screen'))"))
    check("a reload is light from its first frame", c.js("window.firstFrame") == {"theme": "light", "ground": "#efeeea"}, c.js("window.firstFrame"))
    # This browser's cached light stands in only until the server answers; the server's settings (never saved here, so
    # dark) then win, as on any other device.
    check("then the server's own settings win once they come", waited(lambda: c.js("document.documentElement.dataset.theme || 'dark'") == "dark") is not None, c.js("document.documentElement.dataset.theme"))
    c.settings()  # the server's settings come, and say nothing: the default, dark
    check("once the server has answered, its word stands", c.js("document.documentElement.dataset.theme") is None)

    # System.
    c.settings(theme="system")
    c.media(prefers_color_scheme="light")
    check("system follows the system to light, with no event", c.js("document.documentElement.dataset.theme") == "light")
    check("and the terminal follows it", c.js("[...liveTerms][0].term.options.theme.background") == "#fdfcfa")
    c.media(prefers_color_scheme="dark")
    check("and back to dark", c.js("document.documentElement.dataset.theme") is None)
    check("and the terminal's 256 colours are xterm's own again", c.js("[...liveTerms][0].term._core._themeService.colors.ansi[237].css") == "#3a3a3a")

    # Accent.
    for theme in ("dark", "light"):
        for colour in ("#ffd400", "#f4f4ff", "#1a0f3d", "rebeccapurple"):
            c.settings(theme=theme, accent=colour)
            surfaces = [c.token(s) for s in ["--ground", "--panel", "--field", "--raise", "--accent-wash"]]
            ink, fill, on = c.token("--accent-ink"), c.token("--accent"), c.token("--on-accent")
            worst = min(c.js(f"hubAppearance.contrast({json.dumps(ink)}, {json.dumps(s)})") for s in surfaces)
            words = c.js(f"hubAppearance.contrast({json.dumps(on)}, {json.dumps(fill)})")
            edge = min(c.js(f"hubAppearance.contrast({json.dumps(fill)}, {json.dumps(c.token(s))})") for s in ["--panel", "--field"])
            check(f"accent {colour} in {theme}: links and focus pass AA ({worst:.2f}), a button's words too ({words:.2f}), and the button stands out ({edge:.2f})", worst >= 4.5 and words >= 4.5 and edge >= 3, [ink, fill, on])
    c.settings(accent="not a colour")
    check("a colour that isn't one is ignored", c.js("document.documentElement.dataset.accent") is None and c.token("--accent") == "#254fc5")
    c.settings(accent="#e0457b")
    check("an accent reaches the terminal's cursor", c.js("[...liveTerms][0].term.options.theme.cursor") == c.token("--accent-ink"))
    c.shot("2-accent")
    c.settings(theme="dark", accent="")
    check("no accent puts the theme's own back", c.token("--accent") == "#2f62f5" and c.token("--accent-ink") == "#8fb0ff")

    # Terminal font size.
    before = c.js("(t => [t.options.fontSize, t.cols])([...liveTerms][0].term)")
    c.settings(term_font_size=18)
    time.sleep(0.5)
    after = c.js("(t => [t.options.fontSize, t.cols])([...liveTerms][0].term)")
    check("the terminal's font size changes live and it refits", before[0] == 13 and after[0] == 18 and after[1] < before[1], [before, after])
    c.settings(term_font_size=13)

    # Density.
    c.js("location.hash = '#/'")
    time.sleep(1.5)
    row = lambda: c.js("Math.round(document.querySelector('#side .nav').getBoundingClientRect().height)")
    roomy = row()
    c.settings(density="compact")
    check("compact tightens the sidebar's rows", roomy == 28 and row() == 24, [roomy, row()])
    c.shot("3-compact")
    c.settings(density="comfortable")

    # Motion.
    moving = "(() => { const r = document.querySelector('.cube-build rect, .cube-lift .top, .cube-turn rect, .cube-shimmer rect'); return r ? getComputedStyle(r).animationName : 'no cube'; })()"
    c.js("document.getElementById('view').append(hubOrb('working', { size: 16 }))")
    check("a cube moves by default", c.js(moving) not in ("none", "no cube"), c.js(moving))
    c.settings(reduce_motion="on")
    check("reduce motion on stills it, whatever the system says", c.js(moving) == "none" and c.js("reduced()") is True)
    c.media(prefers_reduced_motion="reduce")
    c.settings(reduce_motion="off")
    check("off lets it move under a system that asks for less", c.js(moving) not in ("none", "no cube") and c.js("reduced()") is False, c.js(moving))
    c.settings(reduce_motion="system")
    check("system follows the system again", c.js(moving) == "none" and c.js("reduced()") is True)
    c.media(prefers_reduced_motion="no-preference")
    check("live, as the system changes", c.js(moving) != "none" and c.js("reduced()") is False)

    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        if sid:
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
