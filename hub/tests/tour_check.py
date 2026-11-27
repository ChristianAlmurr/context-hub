#!/usr/bin/env python3
"""The first-run tour (feat/tour), through the API and in headless Chrome at a desk and on a phone, dark and light.

- The server decides once whether the tour is due, and keeps it in settings-notes.json: "open" on a new state folder
  (a first install, or a Mac that joins through sync), "offer" on a hub in use before the tour (it showed the welcome
  card, or kept a read mark), "done" once it is finished, skipped or dismissed. The version note alone doesn't count
  as use, since About can write it before Settings is first read.
- On a fresh state Home opens the tour by itself: a modal dialog, labelled, with "1 of 6", Next, Skip tour and no Back.
  Arrows, Enter and Back walk it; Tab stays in its card; Esc skips; Done finishes. Either way it never comes back by
  itself, in this browser, after its data is cleared, or in another browser.
- Settings › About, Go to and Home's offer start it again.
- A hub in use before the tour gets no tour, only the offer, which goes for good once dismissed.
- Going to another page mid-tour leaves no overlay behind. A step whose element isn't on screen centres its card.
- A phone: the card docks at the foot, above the bottom bar; text 16px, controls 44px, nothing off the side.
- Reduced motion stills the spotlight.

Runs against a second instance (the six HUB_* variables, see tests/instance.py). Makes no project: Home lists the
stores already in ~/agent-memory. It rewrites the instance's settings-notes.json and puts back what was there.
Run: /usr/bin/python3 tests/tour_check.py [folder-for-screenshots]
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, WRITE, base, launchd_jobs
from instance import PORT as HUB_PORT
import hub_settings

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-tour.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9371"))
NOTES = base.STATE / "settings-notes.json"
READS = base.STATE / "reads.json"
STEPS = ["hub", "projects", "sessions", "memory", "settings", "sync"]
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def waited(test, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.2)
    return None


def notes(value=None):
    """Read the notes, or write them whole (None removes the tour's key only when value is "fresh")."""
    if value is None:
        try:
            return json.loads(NOTES.read_text())
        except (OSError, ValueError):
            return {}
    NOTES.write_text(json.dumps(value))


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

    def press(self, key, text=None, modifiers=0):
        vk = {"Enter": 13, "Escape": 27, "Tab": 9, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40}[key]
        down = dict(type="keyDown", key=key, code=key, windowsVirtualKeyCode=vk, modifiers=modifiers)
        if text:
            down["text"] = text  # Enter submits a form only with its "\r"
        self.call("Input.dispatchKeyEvent", **down)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=key, windowsVirtualKeyCode=vk, modifiers=modifiers)
        time.sleep(0.2)

    def fresh(self, route="#/", clear=True):
        """The page loaded afresh at a route; with clear, this browser's own data is gone too, as after clearing site data."""
        wipe = "try { localStorage.clear(); } catch {}" if clear else ""
        self.js("(() => { " + wipe + " location.hash = " + json.dumps(route) + "; window.oldPage = true; })()")
        self.call("Page.reload")
        waited(lambda: self.js("!window.oldPage && !!document.querySelector('#side .brand')"), 20)
        time.sleep(0.8)

    def tour(self):
        return self.js("""(() => { const d = document.querySelector('dialog.tour'); if (!d) return null; const pop = d.querySelector('.tour-pop'), spot = d.querySelector('.tour-spot');
          const r = pop.getBoundingClientRect(), s = spot.getBoundingClientRect(), a = document.activeElement;
          return { open: d.open, step: d.dataset.step, count: d.querySelector('.tour-count').textContent, title: d.querySelector('h2').textContent, text: d.querySelector('p').textContent,
            label: document.getElementById(d.getAttribute('aria-labelledby')) && document.getElementById(d.getAttribute('aria-labelledby')).textContent, role: d.getAttribute('role') || 'dialog',
            centred: d.classList.contains('centred'), spot: spot.hidden ? null : [s.left, s.top, s.width, s.height], pop: [r.left, r.top, r.width, r.height, r.bottom],
            back: !d.querySelector('[data-key=tour-back]').hidden, next: d.querySelector('[data-key=tour-next]').textContent, focus: a && a.dataset ? a.dataset.key || a.tagName : null, inPop: pop.contains(a),
            live: d.querySelector('[aria-live]') && d.querySelector('[aria-live]').textContent, count_open: document.querySelectorAll('dialog[open]').length }; })()""")

    def tour_shows(self, seconds=6):
        return waited(lambda: (self.tour() or {}).get("open"), seconds)


def reset(value):
    """The tour's own note set as a test wants it; everything else in the notes kept."""
    held = notes()
    held.pop("tour", None)
    held.update(value)
    notes(held)


saved_notes = NOTES.read_text() if NOTES.exists() else None
had_reads = READS.exists()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = None
try:
    # ── the server's decision ──
    if READS.exists():
        READS.rename(READS.with_suffix(".tour-check"))
    sessions = base.STATE / "sessions"
    kept = [p for p in sessions.glob("*.json")] if sessions.is_dir() else []
    if kept:
        print(f"note: this instance has {len(kept)} sessions, so its state folder counts as in use; the fresh checks set the note by hand")
    notes({})
    if not kept:
        check("a new state folder: the tour is open", hub_settings.tour() == "open", notes())
        check("and the decision is kept", notes().get("tour") == "open", notes())
        notes({"seen": "abc123"})
        check("the version note alone (About can write it first) still counts as new", hub_settings.tour() == "open", notes())
        notes({})
        READS.write_text("{}")
        check("a hub with read marks was in use: it gets the offer", hub_settings.tour() == "offer", notes())
        READS.unlink()
    notes({"welcome": "done"})
    check("a hub that showed the welcome card was in use: it gets the offer, not the tour", hub_settings.tour() == "offer", notes())
    notes({})
    status, page = api("GET", "/api/settings")
    check("GET /api/settings says the tour's state", status == 200 and page.get("tour") in ("open", "offer"), page.get("tour"))
    check("and asks it before the welcome note is written", kept or page.get("tour") == "open", page.get("tour"))
    status, said = api("POST", "/api/settings/tour", {"anything": "ignored"})
    check("POST /api/settings/tour ends it, whatever it is sent", status == 200 and said == {"tour": "done"} and notes().get("tour") == "done", [status, said])
    check("and GET says done after", api("GET", "/api/settings")[1].get("tour") == "done")
    status, _ = api("GET", "/api/settings/tour")
    check("GET on the tour's own path changes nothing", notes().get("tour") == "done", status)

    # ── the page, at a desk ──
    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    page = None
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
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "no-preference"}])
    api("PUT", "/api/settings", {"theme": "dark"})
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)

    def walk(prefix):
        """Every step, a screenshot each, by the arrow key; back to the first by the other arrow."""
        seen = []
        for i, step in enumerate(STEPS):
            t = waited(lambda: (c.tour() or {}).get("step") == step and c.tour(), 3) or c.tour() or {}
            seen.append(t.get("step"))
            c.shot(f"{prefix}-{i + 1}-{step}")
            if i < len(STEPS) - 1:
                c.press("ArrowRight")
                time.sleep(0.3)
        return seen

    reset({"tour": "open"})
    c.fresh("#/")
    t = c.tour_shows()
    check("a fresh hub opens the tour on Home by itself", t, c.js("document.body.innerText.slice(0, 200)"))
    t = c.tour() or {}
    check("it is a modal dialog, named by its step's title", t.get("open") and t.get("role") == "dialog" and t.get("label") == t.get("title") == "This is Context Hub" and c.js("document.querySelector('dialog.tour').matches(':modal')"), t)
    check("it says 1 of 6, offers Next and Skip tour, and no Back", t.get("count") == "1 of 6" and t.get("next") == "Next" and not t.get("back") and c.js("!!document.querySelector('[data-key=tour-skip]')"), t)
    check("focus is in its card, on Next", t.get("focus") == "tour-next" and t.get("inPop"), t)
    check("the first step lights the hub's name in the sidebar", t.get("spot") and t["spot"][0] < 260, t)
    check("the copy is plain: no exclamation marks", "!" not in c.js("[...document.querySelectorAll('.tour-pop')].map(e => e.innerText).join(' ')"))
    seen = walk("desk-dark")
    check("the arrow key walks all six steps in order", seen == STEPS, seen)
    t = c.tour()
    check("the last step is Sync, says end-to-end encrypted, and offers Set up sync and Done", t["title"] == "Sync" and "end-to-end encrypted" in t["text"] and t["next"] == "Done" and c.js("!document.querySelector('[data-key=tour-sync]').hidden"), t)
    check("each step change is said to a screen reader", "6 of 6. Sync." in (t.get("live") or ""), t.get("live"))
    c.press("ArrowLeft"); time.sleep(0.3)
    check("the left arrow goes back a step", c.tour()["step"] == "settings", c.tour()["step"])
    c.js("document.querySelector('[data-key=tour-back]').click()"); time.sleep(0.3)
    check("and so does Back", c.tour()["step"] == "memory", c.tour()["step"])
    c.js("document.querySelector('[data-key=tour-next]').focus()")
    c.press("Enter", "\r"); time.sleep(0.3)
    check("Enter on Next goes on", c.tour()["step"] == "settings", c.tour()["step"])
    stops = []
    for _ in range(6):
        c.press("Tab"); stops.append(c.tour()["inPop"])
    c.press("Tab", modifiers=8); stops.append(c.tour()["inPop"])
    check("Tab and shift-Tab stay inside the card", all(stops), stops)
    check("keys meant for the page don't reach it while the tour is open", (c.js("(() => { const before = location.hash; document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: 'g', bubbles: true })); document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: 'h', bubbles: true })); return location.hash === before; })()")))
    # Settings on a desk: the sidebar's Settings row.
    check("the Settings step lights the sidebar's Settings row", c.tour()["spot"] and c.tour()["spot"][0] < 260 and c.tour()["spot"][1] > 600, c.tour())
    c.press("ArrowRight"); time.sleep(0.3)
    c.js("document.querySelector('[data-key=tour-next]').click()"); time.sleep(0.6)
    check("Done ends it and leaves no dialog behind", not c.js("!!document.querySelector('dialog.tour')") and c.js("document.querySelectorAll('dialog[open]').length") == 0)
    check("focus goes back to the page", c.js("document.activeElement && document.activeElement !== document.body && !document.activeElement.closest('dialog')"), c.js("document.activeElement && document.activeElement.outerHTML.slice(0, 80)"))
    check("finishing is kept on the server", waited(lambda: notes().get("tour") == "done", 5), notes())
    check("and in this browser", c.js("localStorage.getItem('hub.tour')") == '"done"', c.js("localStorage.getItem('hub.tour')"))
    c.fresh("#/", clear=False)
    check("a reload doesn't bring it back", not c.tour_shows(2.5))
    c.fresh("#/", clear=True)
    check("nor does clearing this browser's data: the server keeps it", not c.tour_shows(2.5))

    # The server heard nothing (the request lost): this browser's own note still keeps it shut, and tells the server.
    c.js("localStorage.setItem('hub.tour', JSON.stringify('done'))")
    reset({"tour": "open"})
    c.fresh("#/", clear=False)
    check("a browser that ended it keeps it shut when the server never heard", not c.tour_shows(2.5))
    check("and tells the server", waited(lambda: notes().get("tour") == "done", 5), notes())

    # Esc skips; so does Skip tour.
    reset({"tour": "open"})
    c.fresh("#/")
    c.tour_shows()
    c.press("ArrowRight"); time.sleep(0.2)
    c.press("Escape"); time.sleep(0.5)
    check("Esc skips: the tour is gone", not c.js("!!document.querySelector('dialog.tour')"))
    check("and a skip is kept as done", waited(lambda: notes().get("tour") == "done", 5), notes())
    check("Esc went no further: Home is still in front", c.js("location.hash") in ("#/", ""), c.js("location.hash"))
    c.fresh("#/")
    check("a skipped tour doesn't come back after a reload", not c.tour_shows(2.5))
    reset({"tour": "open"})
    c.fresh("#/")
    c.tour_shows()
    c.js("document.querySelector('[data-key=tour-skip]').click()"); time.sleep(0.5)
    check("Skip tour skips it too", not c.js("!!document.querySelector('dialog.tour')") and waited(lambda: notes().get("tour") == "done", 5), notes())

    # Take it again: Settings › About, then Go to.
    c.js("location.hash = '#/settings/about'"); time.sleep(1.5)
    has = waited(lambda: c.js("!!document.querySelector('[data-key=take-tour]')"), 8)
    check("Settings › About has Take the tour", has)
    c.js("document.querySelector('[data-key=take-tour]').click()")
    t = c.tour_shows()
    check("it goes Home and starts the tour at its first step", t and c.js("location.hash") in ("#/", "") and c.tour()["step"] == "hub", [c.js("location.hash"), c.tour()])
    c.press("Escape"); time.sleep(0.4)
    c.js("document.querySelector('#view').focus()")
    c.call("Input.dispatchKeyEvent", type="keyDown", key="k", code="KeyK", windowsVirtualKeyCode=75, modifiers=4)
    c.call("Input.dispatchKeyEvent", type="keyUp", key="k", code="KeyK", windowsVirtualKeyCode=75, modifiers=4)
    time.sleep(0.4)
    c.call("Input.insertText", text="take the tour"); time.sleep(0.4)
    listed = c.js("document.querySelector('dialog.palette[open]') && document.querySelector('dialog.palette[open]').innerText")
    check("Go to lists Take the tour", listed and "Take the tour" in listed, (listed or "")[:200])
    c.press("Enter", "\r")
    check("and starts it", c.tour_shows())
    c.press("Escape"); time.sleep(0.4)

    # Going to another page mid-tour leaves nothing behind.
    reset({"tour": "open"})
    c.fresh("#/")
    c.tour_shows()
    c.press("ArrowRight"); time.sleep(0.2)
    c.js("location.hash = '#/settings'"); time.sleep(0.8)
    check("going to another page mid-tour ends it, with no overlay left", not c.js("!!document.querySelector('dialog.tour, .tour-spot, .tour-pop')") and c.js("document.querySelectorAll('dialog[open]').length") == 0)
    check("the page there works: Settings is drawn and focusable", c.js("!!document.querySelector('.page.settings')") and c.js("(() => { const a = document.querySelector('.set-nav a'); a.focus(); return document.activeElement === a; })()"))
    check("and leaving counts as done", waited(lambda: notes().get("tour") == "done", 5), notes())
    reset({"tour": "open"})
    c.fresh("#/")
    c.tour_shows()
    c.js("history.back()"); time.sleep(0.8)
    check("going back in history mid-tour leaves no overlay either", not c.js("!!document.querySelector('dialog.tour')") or c.js("location.hash") in ("#/", ""), c.js("location.hash"))

    # A step whose element isn't there: its card centres.
    reset({"tour": "open"})
    c.fresh("#/")
    c.tour_shows()
    c.js("document.head.append(Object.assign(document.createElement('style'), { id: 'no-cards', textContent: '.cards { display: none !important; }' }))")
    for _ in range(3):
        c.press("ArrowRight"); time.sleep(0.25)
    t = c.tour()
    check("with no project card on screen, Memory and dreams centres its card and lights nothing", t["step"] == "memory" and t["centred"] and t["spot"] is None and abs((t["pop"][0] + t["pop"][2] / 2) - 720) < 4, t)
    c.shot("desk-dark-centred")
    c.js("document.getElementById('no-cards').remove()")
    time.sleep(0.6)
    t = c.tour()
    check("and lights the card once there is one", not t["centred"] and t["spot"], t)

    # Reduced motion: the spotlight jumps.
    moving = c.js("getComputedStyle(document.querySelector('.tour-spot')).transitionDuration")
    c.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
    time.sleep(0.3)
    still = c.js("getComputedStyle(document.querySelector('.tour-spot')).transitionDuration")
    check("the spotlight glides, and with reduced motion it jumps", moving and moving.startswith("0.2s") and max(float(x.strip().rstrip("s")) for x in still.split(",")) < 0.01, [moving, still])
    c.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "no-preference"}])
    c.press("Escape"); time.sleep(0.4)

    # A hub in use before the tour: no tour, an offer, once.
    reset({"tour": "offer"})
    c.fresh("#/")
    check("a hub in use before the tour gets no tour pushed at it", not c.tour_shows(2.5))
    offer = waited(lambda: c.js("!!document.querySelector('.tour-offer')"), 5)
    check("Home offers it instead", offer, c.js("document.querySelector('#view').innerText.slice(0, 300)"))
    c.shot("desk-dark-offer")
    c.js("document.querySelector('[data-key=tour-offer-take]').click()")
    check("the offer's Take the tour starts it", c.tour_shows())
    check("and the offer is gone", not c.js("!!document.querySelector('.tour-offer')"))
    c.press("Escape"); time.sleep(0.4)
    reset({"tour": "offer"})
    c.fresh("#/")
    waited(lambda: c.js("!!document.querySelector('.tour-offer')"), 5)
    c.js("document.querySelector('[data-key=tour-offer-dismiss]').click()"); time.sleep(0.5)
    check("dismissing the offer takes it away", not c.js("!!document.querySelector('.tour-offer')") and waited(lambda: notes().get("tour") == "done", 5), notes())
    c.fresh("#/")
    check("for good", not c.js("!!document.querySelector('.tour-offer')") and not c.tour_shows(1.5))

    # Light, at a desk.
    api("PUT", "/api/settings", {"theme": "light"})
    reset({"tour": "open"})
    c.fresh("#/")
    c.tour_shows()
    check("the light theme is on", c.js("document.documentElement.dataset.theme") == "light", c.js("document.documentElement.dataset.theme"))
    walk("desk-light")
    check("the card is the raised paper of the light theme", c.js("getComputedStyle(document.querySelector('.tour-pop')).backgroundColor") == "rgb(255, 254, 253)", c.js("getComputedStyle(document.querySelector('.tour-pop')).backgroundColor"))
    c.press("Escape"); time.sleep(0.4)

    # ── a phone ──
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True)
    for theme in ("light", "dark"):
        api("PUT", "/api/settings", {"theme": theme})
        reset({"tour": "open"})
        c.fresh("#/")
        check(f"on a phone ({theme}) the tour opens too", c.tour_shows())
        t = c.tour()
        bar = c.js("(() => { const b = document.getElementById('phone-bar'); return b.hidden ? null : b.getBoundingClientRect().top; })()")
        check(f"on a phone ({theme}) its card docks at the foot, full width less 8px, above the bottom bar", t["pop"][0] == 8 and abs(t["pop"][2] - 374) < 1 and bar and t["pop"][4] <= bar and t["pop"][4] > bar - 24, [t["pop"], bar])
        if theme == "light":
            sizes = c.js("[...document.querySelectorAll('.tour-pop p, .tour-pop button:not([hidden]), .tour-pop a:not([hidden])')].map(e => [parseFloat(getComputedStyle(e).fontSize), e.getBoundingClientRect().height, e.textContent])")
            check("on a phone its text is 16px and every control at least 44px tall", sizes and all(s[0] >= 16 for s in sizes) and all(s[1] >= 44 for s in sizes if s[2] in ("Next", "Skip tour", "Back", "Done", "Set up sync")), sizes)
            check("on a phone nothing runs off the side", c.js("document.documentElement.scrollWidth <= innerWidth"))
        seen = walk(f"phone-{theme}")
        check(f"on a phone ({theme}) it walks all six steps", seen == STEPS, seen)
        if theme == "light":
            c.press("ArrowLeft"); c.press("ArrowLeft"); c.press("ArrowLeft"); c.press("ArrowLeft"); time.sleep(0.3)
            t = c.tour()
            projects = c.js("(() => { const r = document.querySelector('[data-key=\"pb:projects\"]').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
            check("on a phone Projects lights the bottom bar's Projects, and the card sits above it", t["step"] == "projects" and t["spot"] and abs(t["spot"][0] - (projects[0] - 4)) < 2 and t["pop"][4] <= t["spot"][1] + 4, [t, projects])
        c.press("Escape"); time.sleep(0.4)
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:
    check("the run went to its end", False, repr(error))
finally:
    try:
        if chrome:
            chrome.terminate()
            chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
    finally:
        api("PUT", "/api/settings", {"theme": "dark"})
        if saved_notes is None:
            NOTES.unlink(missing_ok=True)
        else:
            NOTES.write_text(saved_notes)
        spare = READS.with_suffix(".tour-check")
        if spare.exists():
            spare.rename(READS)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
