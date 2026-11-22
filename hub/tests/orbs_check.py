#!/usr/bin/env python3
"""The status orb (ui/orbs.js), in headless Chrome: every state draws, and reads apart from the others, at every size the
hub uses; every live orb moves, each live state in its own colour; nothing draws off screen, in a hidden tab or under
reduced motion; the marks that must lead or recede do; and thirty moving orbs stay cheap.
- Every state draws at 14, 16, 20 and 30, on the 2px grid, with its own word, and no two states share a still frame.
- Moving states move; still ones (done, idle, the terminal, ended, closed, offline, error, asks) never do.
- Six working orbs side by side: all six move. The live states (working, thinking, searching, a tool, compacting,
  retrying, needs you, closing) each have a colour of their own.
- Off screen, in a hidden tab, or under reduced motion ("on", or the system's with "system"): nothing changes.
- Needs you and "asks you" are rose and the fullest marks; a done turn once read is the faintest.
- No CSS animation runs on any orb. Thirty moving orbs on screen take under 5% of the page's main thread.

Needs no project: it draws orbs straight onto the hub's page. Runs against a second instance (tests/instance.py).
Run: /usr/bin/python3 tests/orbs_check.py
"""
import base64, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-orbs.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0
STATES = ["working", "reasoning", "searching", "using", "compacting", "background", "closing", "needs", "asks", "finished", "idle", "shell",
          "no-claude", "ended", "closed", "offline", "error", "retrying", "dreaming"]
MOVING = {"working", "reasoning", "searching", "using", "compacting", "background", "closing", "needs", "retrying", "dreaming"}


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


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



# How many of the orbs in `box` change their drawing over `ms`.
CHANGED = """(async (sel, ms) => { const orbs = [...document.querySelectorAll(sel + ' svg.orb')]; const a = orbs.map((o) => o.innerHTML);
  await new Promise((r) => setTimeout(r, ms)); return orbs.map((o, i) => o.innerHTML !== a[i]); })"""


def changed(c, sel, ms=900):
    return c.js(f"{CHANGED}({json.dumps(sel)}, {ms})")


profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    page = None
    for _ in range(80):
        try:
            page = next((t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page"), None)
        except OSError:
            page = None
        if page:
            break
        time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.media(prefers_color_scheme="dark", prefers_reduced_motion="no-preference")
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    for _ in range(60):
        if c.js("!!window.hubOrb && typeof SETTINGS === 'object'"):
            break
        time.sleep(0.25)
    time.sleep(1)
    c.settings(reduce_motion="off")
    # A board of its own over the page, every state at every size.
    c.js("""(() => { const b = document.createElement('div'); b.id = 'orb-board'; b.style.cssText = 'position:fixed;inset:0;z-index:999;background:var(--ground);display:flex;flex-direction:column;gap:4px;padding:8px;overflow:hidden';
      document.body.append(b); })()""")
    c.js(f"""(() => {{ const b = document.getElementById('orb-board');
      for (const state of {json.dumps(STATES)}) {{ const row = document.createElement('div'); row.className = 'r-' + state; row.style.cssText = 'display:flex;gap:8px;align-items:center';
        for (const size of [14, 16, 20, 30]) {{ const cell = document.createElement('span'); cell.className = 'sz-' + size; cell.append(hubOrb(state, {{ size }})); row.append(cell); }}
        b.append(row); }} }})()""")
    sizes = c.js("[...document.querySelectorAll('#orb-board .r-working svg.orb')].map((o) => [o.getAttribute('width'), o.getAttribute('viewBox')])")
    check("an orb is drawn on the 2px grid: 14 is 7 cells, 16 is 8, 20 is 10, 30 is 15", sizes == [["14", "0 0 7 7"], ["16", "0 0 8 8"], ["20", "0 0 10 10"], ["30", "0 0 15 15"]], sizes)
    empty = c.js("[...document.querySelectorAll('#orb-board svg.orb')].filter((o) => ![...o.querySelectorAll('path')].some((p) => (p.getAttribute('d') || '').length)).map((o) => o.dataset.orb + o.getAttribute('width'))")
    check("every state draws at every size", empty == [], empty)
    words = c.js("Object.fromEntries([...document.querySelectorAll('#orb-board .sz-16 svg.orb')].map((o) => [o.dataset.orb, o.getAttribute('aria-label')]))")
    check("each orb says its state in words", words.get("needs") == "Needs you" and words.get("asks") == "Done, asks you" and words.get("no-claude") == "Claude isn't running" and all(words.values()), words)
    # Still frames: each state's drawing at rest, at the sidebar's size, must differ from every other's.
    stills = c.js(f"Object.fromEntries({json.dumps(STATES)}.map((s) => [s, hubOrb(s, {{ size: 14, still: true }}).innerHTML]))")
    same = [(a, b) for i, a in enumerate(STATES) for b in STATES[i + 1:] if stills[a] == stills[b]]
    check("no two states look the same at rest, even at 14px", not same, same)
    flags = changed(c, "#orb-board", 1200)
    by_state = {}
    for i, f in enumerate(flags):
        by_state.setdefault(STATES[i // 4], []).append(f)
    moving_now = {s for s, f in by_state.items() if all(f)}
    resting = {s for s, f in by_state.items() if not any(f)}
    check("every moving state moves, at every size", MOVING <= moving_now, sorted(MOVING - moving_now))
    check("done, idle, the terminal, ended, closed, offline, error and asks hold still", set(STATES) - MOVING <= resting, sorted((set(STATES) - MOVING) - resting))
    anims = c.js("[...document.querySelectorAll('svg.orb, svg.orb *')].reduce((n, el) => n + el.getAnimations().length, 0)")
    check("no CSS animation runs on any orb", anims == 0, anims)
    # Colour and strength.
    colour = lambda state: c.js(f"getComputedStyle(document.querySelector('#orb-board .r-{state} svg.orb')).color")
    trouble = c.js("(() => { const s = document.createElement('span'); s.style.color = 'var(--trouble)'; document.body.append(s); const v = getComputedStyle(s).color; s.remove(); return v; })()")
    check("needs you and asks you are rose", colour("needs") == trouble and colour("asks") == trouble, [colour("needs"), colour("asks"), trouble])
    ink = c.js("""Object.fromEntries([...document.querySelectorAll('#orb-board .sz-16 svg.orb')].map((o) => [o.dataset.orb,
      [...o.querySelectorAll('path')].reduce((n, p) => n + ((p.getAttribute('d') || '').match(/M/g) || []).length * Number(getComputedStyle(p).fillOpacity), 0)]))""")
    strongest = max(ink, key=ink.get)
    check("needs you (or asks you) carries the most ink of any orb", strongest in ("needs", "asks"), sorted(ink.items(), key=lambda kv: -kv[1])[:4])
    read = c.js("""(() => { const row = document.createElement('div'); row.className = 'qrow read'; const o = hubOrb('finished', { size: 16 }); row.append(o); document.getElementById('orb-board').append(row);
      const unread = document.querySelector('#orb-board .r-finished .sz-16 .l1'); return [Number(getComputedStyle(o.querySelector('.l1')).fillOpacity), Number(getComputedStyle(unread).fillOpacity)]; })()""")
    check("a done turn once read loses its lit cap", read[0] < 0.5 and read[1] == 1, read)
    # Every live orb moves: six in one row of the sidebar's kind, all of them.
    live = ["working", "reasoning", "searching", "using", "compacting", "retrying", "needs", "closing"]
    colours = {state: colour(state) for state in live}
    check("each live state has a colour of its own", len(set(colours.values())) == len(live), colours)
    c.js("""(() => { const b = document.getElementById('orb-board'); b.replaceChildren(); const r = document.createElement('div'); r.id = 'one-region';
      for (let i = 0; i < 6; i++) { const row = document.createElement('div'); row.className = 'side-row'; row.append(hubOrb('working', { size: 14 })); r.append(row); } b.append(r); })()""")
    time.sleep(0.3)
    flags = changed(c, "#one-region", 1200)
    check("six working orbs side by side: all six move", all(flags) and len(flags) == 6, flags)
    # Thirty moving orbs on screen: what the page's main thread spends on them, against the same page with none.
    def busy(seconds=4):
        before = {m["name"]: m["value"] for m in c.call("Performance.getMetrics")["metrics"]}
        time.sleep(seconds)
        after = {m["name"]: m["value"] for m in c.call("Performance.getMetrics")["metrics"]}
        return (after["TaskDuration"] - before["TaskDuration"]) / (after["Timestamp"] - before["Timestamp"])
    c.call("Performance.enable", timeDomain="threadTicks")
    c.js("(() => { const b = document.getElementById('orb-board'); b.replaceChildren(); })()")
    time.sleep(0.5)
    idle_share = busy()
    c.js(f"""(() => {{ const b = document.getElementById('orb-board'); const r = document.createElement('div'); r.id = 'thirty'; r.style.cssText = 'display:flex;flex-wrap:wrap;gap:6px';
      const states = {json.dumps(live)}; for (let i = 0; i < 30; i++) r.append(hubOrb(states[i % states.length], {{ size: [14, 16, 20][i % 3] }})); b.append(r); }})()""")
    time.sleep(0.5)
    thirty_share = busy()
    cost = thirty_share - idle_share
    print(f"      main thread busy: {idle_share:.1%} with no orbs, {thirty_share:.1%} with 30 moving orbs: {cost:.1%} for the orbs", flush=True)
    check("thirty moving orbs cost under 5% of the main thread", cost < 0.05, f"{cost:.1%}")
    c.js("(() => { const b = document.getElementById('orb-board'); b.replaceChildren(); const r = document.createElement('div'); r.id = 'one-region'; for (let i = 0; i < 6; i++) r.append(hubOrb('working', { size: 14 })); b.append(r); })()")
    # Off screen, hidden tab, reduced motion.
    c.js("document.getElementById('orb-board').style.transform = 'translateY(-5000px)'")
    time.sleep(0.5)
    check("off screen, nothing draws", not any(changed(c, "#one-region", 1200)))
    c.js("document.getElementById('orb-board').style.transform = ''")
    time.sleep(0.5)
    check("back on screen, it moves again", any(changed(c, "#one-region", 1200)))
    c.js("Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'))")
    time.sleep(0.3)
    check("in a hidden tab, nothing draws", not any(changed(c, "#one-region", 1200)))
    c.js("delete document.hidden; document.dispatchEvent(new Event('visibilitychange'))")
    time.sleep(0.3)
    check("shown again, it moves again", any(changed(c, "#one-region", 1200)))
    c.settings(reduce_motion="on")
    check("reduce motion on: still", not any(changed(c, "#one-region", 1200)))
    c.settings(reduce_motion="system")
    c.media(prefers_reduced_motion="reduce")
    check("system, and the system asks for less: still", not any(changed(c, "#one-region", 1200)))
    c.media(prefers_reduced_motion="no-preference")
    check("system, live as the system changes: moves", any(changed(c, "#one-region", 1200)))
    c.js("document.getElementById('orb-board').remove()")
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:
    check("the run went to its end", False, repr(error))
finally:
    chrome.terminate()
    chrome.wait()
    shutil.rmtree(profile, ignore_errors=True)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
