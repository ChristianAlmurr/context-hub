#!/usr/bin/env python3
"""Hub-wide sessions under the hub's home project (README, "Hub sessions"), at a desk and on a phone:
- with a home project: no "Hub sessions" row in the sidebar or the rail; a hub-wide session sits under the home project
  with the hub mark before its name; the home project's Overview has a "Hub-wide sessions" panel with a "New hub-wide
  session" button that opens the start page (model and effort, no mode), and its ⋯ menu offers the same; Home's queue
  says the session is the home project's; and #/p/@hub lands on the home project's Overview;
- with none (another person's install): still no "Hub sessions" row: the session sits under Home with the hub mark, #/p/@hub lands on Home, and #/p/@hub/new is the start page;
- the home project's Artifacts tab lists hub-wide sessions' artifacts with the hub mark, its own without, and the viewer
  says Hub-wide (two made-up sessions from artifacts_fixture.py, one hub-wide and one of the instance's real home
  project, whose list the page is given for the throwaway one; skipped when the instance has no home project).

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with one plain terminal; and one hub-wide
plain terminal (in the home folder, as every hub-wide session), stopped and dismissed at the end. The page sees only
those two sessions, the throwaway project (laid over /api/state as the home project, named "Context Hub") and two
made-up ones, so nothing private is on screen. What each session is doing is laid over the real state.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/hubwide_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, OWNER, WRITE, base, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT
import artifacts_fixture as fx

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-hubwide.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9349"))
OTHERS = ["atlas", "harbor"]  # made-up projects the page shows beside the throwaway one
failures = 0

# The throwaway project plays the home project unless test.nohome is set; only the test's own sessions are shown.
FAKE = """(() => {
  window.EventSource = undefined;  // the stream would bring the real state past this overlay: the page polls instead
  const real = window.fetch.bind(window);
  window.fetch = async (url, options) => {
    // The throwaway project plays the home project, so its Artifacts list is the instance's real home project's list.
    const artHome = localStorage.getItem("test.arthome"), artMine = `/api/p/${encodeURIComponent(localStorage.getItem("test.project"))}/artifacts`;
    if (artHome && typeof url === "string" && url.startsWith(artMine)) url = `/api/p/${encodeURIComponent(artHome)}/artifacts` + url.slice(artMine.length);
    const answer = await real(url, options);
    if (typeof url !== "string" || !url.startsWith("/api/state") || !answer.ok) return answer;
    const data = await answer.clone().json();
    const name = localStorage.getItem("test.project"), ids = JSON.parse(localStorage.getItem("test.ids") || "[]");
    const mine = data.projects.find((p) => p.name === name);
    data.projects = mine ? [{ ...mine, display: "Context Hub" }, ...%s.map((n) => ({ ...mine, name: n, display: n, needs: 0, latest: null, dreaming: false, setup: [] }))] : [];
    data.hubwide = { ...data.hubwide, home: localStorage.getItem("test.nohome") ? null : name };
    data.sessions = data.sessions.filter((s) => ids.includes(s.id));
    const fake = JSON.parse(localStorage.getItem("test.fake") || "{}");
    data.sessions.forEach((s) => { if (fake[s.id]) Object.assign(s, fake[s.id]); });
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  };
})();""" % json.dumps(OTHERS)


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:500]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE if body is not None else OWNER)
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def waited(test, seconds=15):
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
                self.errors.append(message["params"]["exceptionDetails"].get("text", "") + " " + str(message["params"]["exceptionDetails"].get("exception", {}).get("description", ""))[:300])

    def js(self, expression):
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True, userGesture=True).get("result", {}).get("value")

    def shot(self, name):
        (OUT / f"{name}.png").write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def at(self, selector):
        return waited(lambda: self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e || !e.offsetParent) return null; e.scrollIntoView({{ block: 'nearest' }}); const r = e.getBoundingClientRect(); return {{x: r.left + r.width / 2, y: r.top + r.height / 2, l: r.left, r: r.right, t: r.top, b: r.bottom}}; }})()"), 10)

    def click(self, selector):
        b = self.at(selector)
        if not b:
            raise AssertionError(f"nothing to click at {selector}")
        for kind in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", type=kind, x=b["x"], y=b["y"], button="left", buttons=1 if kind == "mousePressed" else 0, clickCount=1)
        time.sleep(0.3)

    def key(self, key, code=None, modifiers=0, kind="both", vk=0):
        vk = vk or {"Escape": 27, "Enter": 13, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40, "F2": 113, "Alt": 18}.get(key, 0)
        params = {"key": key, "code": code or key, "modifiers": modifiers, "windowsVirtualKeyCode": vk}
        if kind in ("both", "down"):
            text = {"Enter": "\r", " ": " "}.get(key, key if len(key) == 1 and not modifiers else "")
            self.call("Input.dispatchKeyEvent", type="keyDown" if text else "rawKeyDown", **({**params, "text": text} if text else params))
        if kind in ("both", "up"):
            self.call("Input.dispatchKeyEvent", type="keyUp", **params)
        time.sleep(0.15)

    def poll(self, times=1):
        for _ in range(times):
            self.js("window.manualPoll = true; tick().finally(() => { window.manualPoll = false; })")
        time.sleep(0.25)

    def settle(self):
        """The page has taken the server's settings, as it does after any change."""
        self.js("loadSettings()")
        time.sleep(0.4)
        self.poll()


def page_of(width, height, mobile, ids):
    target = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")))
    c = CDP(target["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2 if mobile else 1, mobile=mobile)
    if mobile:
        c.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    c.call("Page.addScriptToEvaluateOnNewDocument", source=FAKE)
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    waited(lambda: c.js("typeof hub !== 'undefined'"), 20)
    c.js(f"localStorage.setItem('test.project', {json.dumps(NAME)}); localStorage.setItem('test.ids', {json.dumps(json.dumps(ids))}); localStorage.removeItem('test.fake'); localStorage.removeItem('test.nohome')")
    c.call("Page.reload")
    waited(lambda: c.js("typeof hub !== 'undefined' && hub.ready && S.projects.length === 3"), 30)
    c.poll()
    return c


def fake(c, sid, fields):
    c.js(f"(() => {{ const f = JSON.parse(localStorage.getItem('test.fake') || '{{}}'); f[{json.dumps(sid)}] = {{ ...(f[{json.dumps(sid)}] || {{}}), ...{json.dumps(fields)} }}; localStorage.setItem('test.fake', JSON.stringify(f)); }})()")
    c.poll(2)


def go(c, route, wait=1.0):
    c.js(f"location.hash = {json.dumps(route)}")
    time.sleep(wait)


def open_side(c, mobile):
    if mobile and not c.js("document.body.classList.contains('side-open')"):
        c.js("document.body.classList.add('side-open')")
        time.sleep(0.4)


def close_side(c, mobile):
    if mobile:
        c.js("document.body.classList.remove('side-open')")
        time.sleep(0.3)


def artifacts_tab(c, tag, mobile):
    """The home project's Artifacts tab: the hub-wide session's rows carry the hub mark, the project's own don't."""
    c.js(f"localStorage.setItem('test.arthome', {json.dumps(home)})")
    go(c, f"#/p/{NAME}/artifacts")
    rows = "[...document.querySelectorAll('.art-row')].filter((r) => !r.title.startsWith('http'))"
    loaded = waited(lambda: c.js(f"{rows}.length >= 20"), 20)
    check(f"{tag}: the home project's Artifacts tab lists the hub-wide session's artifacts beside its own", loaded and c.js(f"{rows}.some((r) => r.title.includes('/wide/')) && {rows}.some((r) => r.title.includes('/own/'))"),
          c.js(f"{rows}.map((r) => r.title).slice(0, 6)"))
    check(f"{tag}: each of the hub-wide session's rows has the hub mark", c.js(f"{rows}.filter((r) => r.title.includes('/wide/')).every((r) => !!r.querySelector('small .hubwide-tag'))"))
    check(f"{tag}: and the project's own rows have none", c.js(f"{rows}.filter((r) => r.title.includes('/own/')).every((r) => !r.querySelector('.hubwide-tag'))"))
    check(f"{tag}: typing hub-wide filters to them", c.js("(() => { const s = document.querySelector('.art-search'); s.value = 'hub-wide'; s.dispatchEvent(new Event('input')); return true; })()") and
          c.js(f"{rows}.length > 0 && {rows}.every((r) => !!r.querySelector('.hubwide-tag') && !r.title.includes('/own/'))"))
    c.js("(() => { const s = document.querySelector('.art-search'); s.value = ''; s.dispatchEvent(new Event('input')); })()")
    c.js(f"{rows}.find((r) => r.title.includes('/wide/') && r.querySelector('b').textContent === 'notes.md').click()")
    check(f"{tag}: the viewer says it is from a hub-wide session", waited(lambda: c.js("(() => { const m = document.querySelector('.art-meta'); return !!m && m.offsetParent !== null && m.textContent.includes('Hub-wide · Hub · Tidy notes'); })()"), 8),
          c.js("document.querySelector('.art-meta') && document.querySelector('.art-meta').textContent"))
    c.shot(f"{tag}-artifacts")
    c.js("localStorage.removeItem('test.arthome')")


sweep()
launchd_before = launchd_jobs()
top = Path(tempfile.mkdtemp(prefix="hubwide-check.", dir=f"/private/tmp/claude-{os.getuid()}"))
work = top / "made" / "here"  # the page shortens a scratch path by two folders; the rows are told apart by the third
wide_art, own_art, home, art_before = os.urandom(4).hex(), os.urandom(4).hex(), None, None
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
own = hubwide = None
try:
    status, made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    own = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "kind": "shell"})[1]["ids"][0]
    hubwide = api("POST", "/api/sessions", {"project": "@hub", "tasks": [], "kind": "shell"})[1]["ids"][0]
    state = api("GET", "/api/state")[1]
    check("the state names the home project, or none", "home" in state["hubwide"], state["hubwide"])
    meta = next((s for s in state["sessions"] if s["id"] == hubwide), {})
    check("a hub-wide session still belongs to no project and runs in the home folder", meta.get("project") == "@hub" and meta.get("repo") == str(Path.home()), {k: meta.get(k) for k in ("project", "repo")})
    home = state["hubwide"].get("home")
    if home:  # two made-up sessions with artifacts: one hub-wide, one of the real home project (only in this instance's state)
        art_before = api("GET", "/api/settings")[1].get("values", {}).get("feature_artifacts", True)
        api("PUT", "/api/settings", {"feature_artifacts": True})
        fx.make(work / "wide", wide_art, base.HUB_PROJECT, "Hub · Tidy notes", work / "wide-out")
        fx.make(work / "own", own_art, home, "Home's own session", work / "own-out")
    else:
        print("note  this instance has no home project, so the home project's Artifacts tab is not checked here", flush=True)
    waited(lambda: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version"), 20)
    for mobile, (width, height) in ((False, (1440, 900)), (True, (390, 844))):
        tag = "phone" if mobile else "desk"
        c = page_of(width, height, mobile, [own, hubwide])
        fake(c, hubwide, {"kind": "claude", "state": "working", "now": "Reading ORG.md in every store", "title": "Hub · Tidy every store", "model": "claude-opus-4-7", "mode": ""})
        fake(c, own, {"kind": "claude", "state": "finished", "said": "Done", "title": f"{NAME} · Fix the importer", "mode": "default"})
        go(c, "#/")
        open_side(c, mobile)
        check(f"{tag}: no Hub sessions row in the sidebar", c.js("!document.querySelector('#side .side-group[data-project=\"@hub\"]')"))
        check(f"{tag}: the hub-wide session sits under the home project", c.js(f"!!document.querySelector('#side .side-group[data-project={json.dumps(NAME)}] [data-sid={json.dumps(hubwide)}]')"))
        check(f"{tag}: with the hub mark before its name", c.js(f"(() => {{ const t = document.querySelector('#side [data-sid={json.dumps(hubwide)}] .hubwide-tag'); return !!t && t.nextElementSibling.classList.contains('label') && t.nextElementSibling.textContent === 'Tidy every store'; }})()"))
        check(f"{tag}: and the project's own session has none", c.js(f"!document.querySelector('#side [data-sid={json.dumps(own)}] .hubwide-tag')"))
        c.shot(f"{tag}-sidebar")
        close_side(c, mobile)
        check(f"{tag}: Home's Working queue says it is the home project's", waited(lambda: c.js(f"(() => {{ const r = document.querySelector('.qrow[data-nav={json.dumps(hubwide)}] .q-p'); return r && r.textContent; }})()") == "Context Hub", 5),
              c.js("document.querySelector('.triage') && document.querySelector('.triage').innerText"))
        c.shot(f"{tag}-home")
        fake(c, hubwide, {"state": "needs", "asking": "Which store first?"})
        check(f"{tag}: and so does Needs you", waited(lambda: c.js(f"(() => {{ const r = document.querySelector('.qrow[data-nav={json.dumps(hubwide)}] .q-p'); return r && r.textContent; }})()") == "Context Hub", 5))
        fake(c, hubwide, {"state": "working", "asking": None})
        go(c, f"#/p/{NAME}")
        panel = waited(lambda: c.js("!!document.querySelector('.hub-panel')"), 5)
        check(f"{tag}: the home project's Overview has a Hub-wide sessions panel", panel)
        check(f"{tag}: listing the hub-wide session, not the project's own", c.js(f"!!document.querySelector('.hub-panel .strip[data-nav={json.dumps(hubwide)}]') && !document.querySelector('.hub-panel .strip[data-nav={json.dumps(own)}]')"))
        check(f"{tag}: whose strip says No prompts, not a mode", c.js(f"document.querySelector('.hub-panel .strip[data-nav={json.dumps(hubwide)}] .strip-facts').textContent.includes('No prompts')"))
        check(f"{tag}: and the project's own Sessions panel keeps its own", c.js(f"!!document.querySelector('.board-box .strip[data-nav={json.dumps(own)}]') && !document.querySelector('.board-box .strip[data-nav={json.dumps(hubwide)}]')"))
        check(f"{tag}: the project's composer is still there", c.js("!!document.querySelector('.compose-panel')"))
        c.js("document.querySelector('.hub-panel').scrollIntoView({ block: 'center' })")
        time.sleep(0.3)
        c.shot(f"{tag}-overview")
        c.js("document.querySelector('[data-key=project-more]').click()")
        time.sleep(0.4)
        check(f"{tag}: its ⋯ menu offers a new hub-wide session", c.js("[...document.querySelectorAll('.menu button, [role=menu] button, [role=menuitem]')].some((b) => b.textContent.includes('New hub-wide session'))"),
              c.js("[...document.querySelectorAll('[role=menuitem], .menu button')].map((b) => b.textContent).join(' | ')"))
        c.key("Escape")
        time.sleep(0.3)
        c.js("document.querySelector('[data-key=hub-new]').click()")
        time.sleep(1)
        check(f"{tag}: New hub-wide session opens the start page", c.js("location.hash") == "#/p/%40hub/new" or c.js("location.hash") == "#/p/@hub/new", c.js("location.hash"))
        check(f"{tag}: which leads back to the home project and offers no mode", c.js(f"!!document.querySelector('#top a[href=\"#/p/{NAME}\"]') && !document.querySelector('.tiles.modes') && !!document.querySelector('.hub-lead')"))
        check(f"{tag}: and doesn't list the running ones again", c.js("!document.querySelector('.hub-live')"))
        c.shot(f"{tag}-start")
        go(c, "#/p/@hub")
        check(f"{tag}: an old #/p/@hub link lands on the home project's Overview", waited(lambda: c.js("location.hash") == f"#/p/{NAME}", 5), c.js("location.hash"))
        if not mobile:
            c.js("document.querySelector('#side [data-key=side-order]').click()")  # sorted by what needs you; clicked again below
            time.sleep(0.6)
            check(f"{tag}: sorted by what needs you, the projects list has no Hub sessions row", c.js("!document.querySelector('#side .side-group[data-project=\"@hub\"]')"))
            check(f"{tag}: and the hub-wide row names the home project", c.js(f"document.querySelector('#side [data-sid={json.dumps(hubwide)}] .proj').textContent") == "Context Hub")
            c.js("document.querySelector('#side [data-key=side-order]').click()")
            time.sleep(0.6)
            c.js("setRail(true)")
            time.sleep(0.5)
            check(f"{tag}: the rail has no Hub entry, and the session sits under the home project", c.js("!document.querySelector('#side [data-key=\"p:@hub\"]')") and c.js(f"!!document.querySelector('#side .rail-group [data-sid={json.dumps(hubwide)}]')"))
            c.js("setRail(false)")
            time.sleep(0.4)
        if home:
            artifacts_tab(c, tag, mobile)
        # A hub with no home project: still no row of their own. The session sits under Home, with the hub mark.
        c.js("localStorage.setItem('test.nohome', '1')")
        c.poll(2)
        go(c, "#/")
        open_side(c, mobile)
        check(f"{tag}: with no home project the session sits under Home", waited(lambda: c.js(f"!!document.querySelector('#side .home-hubwide [data-sid={json.dumps(hubwide)}]')"), 5))
        check(f"{tag}: and there is no Hub sessions row", c.js("!document.querySelector('#side .side-group[data-project=\"@hub\"]') && !/Hub sessions/.test(document.querySelector('#side').textContent)"))
        check(f"{tag}: with the hub mark on its row", c.js("!!document.querySelector('#side .home-hubwide .hubwide-tag')"))
        c.shot(f"{tag}-fallback-sidebar")
        close_side(c, mobile)
        go(c, "#/p/@hub")
        check(f"{tag}: and #/p/@hub lands on Home", waited(lambda: c.js("location.hash") == "#/", 5))
        go(c, "#/p/@hub/new")
        check(f"{tag}: while #/p/@hub/new is still the start page, headed by Home", waited(lambda: c.js("!!document.querySelector('.hub-lead') && /New hub-wide session/.test(document.querySelector('#top').textContent) && !/Hub sessions/.test(document.body.textContent)"), 5))
        go(c, f"#/p/{NAME}")
        check(f"{tag}: and the project's Overview has no hub panel", waited(lambda: c.js("!!document.querySelector('.compose-panel') && !document.querySelector('.hub-panel')"), 5))
        check(f"{tag}: no script errors", not c.errors, c.errors)
        c.js("localStorage.removeItem('test.nohome')")
finally:
    for sid in (hubwide, own):
        if sid:
            api("POST", f"/api/sessions/{sid}/stop", {})
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    for sid in (wide_art, own_art):
        fx.remove(sid)
    if art_before is not None:
        api("PUT", "/api/settings", {"feature_artifacts": art_before})
    shutil.rmtree(top, ignore_errors=True)
    chrome.terminate()
    shutil.rmtree(profile, ignore_errors=True)
    left = remove_project(NAME)
    check("the throwaway project is gone", not left, left)
    check("nothing was written to launchd's folder", launchd_jobs() == launchd_before)
    print(f"screenshots in {OUT}")
    print("ALL PASS" if not failures else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
