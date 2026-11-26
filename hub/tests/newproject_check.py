#!/usr/bin/env python3
"""The New project page and POST /api/projects (fix/new-project), through the API and in headless Chrome.

- A name is typed as the person likes it, spaces and capitals and all: it is shown as typed, and its id (store, new
  folder, links) is its slug. A name with nothing left for an id is refused, as is one whose id or name is taken.
- With no folder picked a new one is made in the projects folder. One already there is offered, never an error, and
  used only on yes; a projects folder or ~/agent-memory that isn't there yet lists no folders instead of failing.
- A create that fails part way takes back what it made (store, folder, memory link), so a second try starts clean.
- Cancel goes back where you came from (Home after a fresh load); Esc in the empty field cancels; while Create runs,
  Cancel waits. Folders that don't load leave Create on, and a create with no folder then asks first.

Runs against a second instance (the six HUB_* variables, see tests/instance.py). Makes hub-test-throwaway-<pid> and
hub-test-throwaway-<parent pid>, and removes both.
Run: /usr/bin/python3 tests/newproject_check.py [folder-for-screenshots]
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE, hub, launchd_jobs, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-newproject.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9361"))
OTHER = f"hub-test-throwaway-{os.getppid()}"  # a second project: its folder is made by hand first, as a person's would be
DISPLAY, OTHER_DISPLAY = NAME.replace("hub-test-throwaway", "Hub Test Throwaway").replace("-", " "), OTHER.replace("hub-test-throwaway", "Hub  test_Throwaway").replace("-", " ")
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=120)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
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

    def press(self, key, text=None):
        vk = {"Enter": 13, "Escape": 27}[key]
        down = dict(type="keyDown", key=key, code=key, windowsVirtualKeyCode=vk)
        if text:
            down["text"] = text  # Enter submits a form only with its "\r"
        self.call("Input.dispatchKeyEvent", **down)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=key, windowsVirtualKeyCode=vk)
        time.sleep(0.2)

    def type_name(self, text):
        self.js("(() => { const i = document.querySelector('input[name=project-name]'); i.value = ''; i.dispatchEvent(new Event('input')); i.focus(); })()")
        if text:
            self.call("Input.insertText", text=text)
        time.sleep(0.2)

    def fresh(self, route):
        """The page loaded afresh at a route, as when the address is opened or reloaded."""
        self.js(f"location.hash = {json.dumps(route)}; window.oldPage = true")
        self.call("Page.reload")
        waited(lambda: self.js("!window.oldPage && !!document.querySelector('#side')"), 20)
        time.sleep(1)

    def confirm(self):
        return self.js("(() => { const d = document.querySelector('dialog.confirm[open]'); return d ? [d.querySelector('h1').textContent, [...d.querySelectorAll('button')].map(b => b.textContent)] : null; })()")

    def answer(self, word):
        self.js(f"[...document.querySelectorAll('dialog.confirm[open] button')].find(b => b.textContent === {json.dumps(word)}).click()")
        time.sleep(0.3)


sweep()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = None
try:
    # ── the rule for an id, the same on both sides ──
    for typed, want in (("Unreal Estate", "unreal-estate"), ("  My  Big_Idea!! ", "my-big-idea"), ("Café au lait", "cafe-au-lait"), ("../x", "x"), ("日本", ""), ("a" * 60, "a" * 41)):
        check(f"{typed.strip()[:12]!r} has the id {want!r}", hub.slug_of(typed) == want, hub.slug_of(typed))

    # ── the API ──
    for bad in ("", "   ", "../ --", "日本語"):
        status, said = api("POST", "/api/projects", {"name": bad})
        check(f"a name with nothing for an id is refused ({bad!r}), in words", status == 409 and said.get("error") in ("Give the project a name.", "Use at least one letter or number."), said)
    status, said = api("POST", "/api/projects", {"name": "x" * 41})
    check("a name over 40 characters is refused", status == 409 and "40" in said.get("error", ""), said)
    status, listed = api("GET", "/api/folders")
    check("the folder list says where the projects folder is, what can be picked and what else is there", status == 200 and listed.get("root", "").startswith("~") and isinstance(listed.get("folders"), list) and isinstance(listed.get("taken"), list), listed)

    # A projects folder that isn't there yet, and no ~/agent-memory: an empty list, not a failure (it was a 500 before).
    real = (hub.PROJECTS, hub.STORES)
    try:
        hub.PROJECTS, hub.STORES = Path(tempfile.mkdtemp()) / "not-yet", Path(tempfile.mkdtemp()) / "not-yet"
        found = hub.folders()
        check("a projects folder and ~/agent-memory not made yet list no folders instead of failing", found["folders"] == [] and found["taken"] == [], found)
    finally:
        hub.PROJECTS, hub.STORES = real

    # A create that fails part way takes back what it made: run in this process, with the kit's install made to fail after it ran.
    real_install = hub.kit.install
    try:
        def failing(name, repos):
            done = real_install(name, repos)
            return subprocess.CompletedProcess(done.args, 1, done.stdout, "The kit stopped (made to, by this test).")
        hub.kit.install = failing
        try:
            hub.create_project({"name": DISPLAY})
            check("a failed install is refused", False)
        except hub.Refused as refused:
            check("a failed install is refused, in the kit's words", "made to, by this test" in str(refused), str(refused))
        check("and nothing it made is left: no store, no folder, no name", not (HOME / "agent-memory" / NAME).exists() and not (hub.PROJECTS / NAME).exists() and not (hub.PROFILES / f"{NAME}.json").exists())
    finally:
        hub.kit.install = real_install

    # ── the page ──
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
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)

    # Cancel: back where you came from, inside the hub; Home after a fresh load.
    c.js("location.hash = '#/dreams'"); time.sleep(0.8)
    c.js("location.hash = '#/new'"); time.sleep(1.2)
    row = c.js("(() => { const a = document.querySelector('form .actions'); const r = a && a.querySelector('.right'); return r ? [...r.querySelectorAll('button')].map(b => [b.textContent, b.className]) : null; })()")
    check("the actions row has Cancel, a quiet button, left of Create", row == [["Cancel", "btn"], ["Create", "btn primary"]], row)
    check("the keys line says esc cancels", "esc" in (c.js("document.querySelector('#status') ? document.querySelector('#status').innerText : ''") or "") and "cancel" in c.js("document.querySelector('#status').innerText"), c.js("document.querySelector('#status') && document.querySelector('#status').innerText"))
    check("the name field takes words: capitals on, up to 40 characters, a plain placeholder", c.js("(() => { const i = document.querySelector('input[name=project-name]'); return [i.autocapitalize, i.maxLength, i.placeholder]; })()") == ["words", 40, "My project"])
    c.shot("01-new")
    c.js("[...document.querySelectorAll('form .actions button')].find(b => b.textContent === 'Cancel').click()"); time.sleep(0.8)
    check("Cancel goes back to the page you came from", c.js("location.hash") == "#/dreams", c.js("location.hash"))
    c.fresh("#/new")
    c.js("[...document.querySelectorAll('form .actions button')].find(b => b.textContent === 'Cancel').click()"); time.sleep(0.8)
    check("after a fresh load Cancel goes Home", c.js("location.hash") in ("#/", ""), c.js("location.hash"))
    c.js("location.hash = '#/new'"); time.sleep(1.2)
    c.type_name("Some name")
    c.press("Escape")
    check("Esc in a field with text only leaves the field", c.js("location.hash") == "#/new" and c.js("document.querySelector('input[name=project-name]').value") == "Some name" and c.js("document.activeElement.name") != "project-name")
    c.type_name("")
    c.press("Escape")
    check("Esc in the empty field cancels", c.js("location.hash") in ("#/", ""), c.js("location.hash"))

    # The hint: the id and folder a name gives, before Create.
    c.js("location.hash = '#/new'"); time.sleep(1.5)
    c.type_name(DISPLAY)
    hint = c.js("document.getElementById('name-hint').textContent")
    check("with no folder picked, the hint names the folder Create makes", hint == f"Makes the folder ~/projects/{NAME}.", hint)
    c.js("(() => { const b = document.querySelector('.folder input'); if (b) { b.checked = true; b.dispatchEvent(new Event('change', { bubbles: true })); } })()")
    hint = c.js("document.getElementById('name-hint').textContent")
    check("with a folder picked, it names the id", hint == f"Its id: {NAME}.", hint)
    c.js("(() => { const b = document.querySelector('.folder input'); if (b) { b.checked = false; b.dispatchEvent(new Event('change', { bubbles: true })); } })()")
    c.type_name("日本")
    check("a name with nothing for an id says so as you type", c.js("document.getElementById('name-hint').textContent") == "Use at least one letter or number.")

    # While Create runs, Cancel waits: the request is held for two seconds.
    c.js("""(() => { const real = window.fetch; window.fetch = async (url, o) => { if (String(url).includes('/api/projects')) await new Promise(r => setTimeout(r, 2000)); return real(url, o); }; })()""")
    c.type_name(DISPLAY)
    c.press("Enter", "\r")
    time.sleep(0.4)
    check("while Create runs, Cancel is off and Create says so", c.js("(() => { const [x, y] = document.querySelectorAll('form .actions .right button'); return [x.getAttribute('aria-disabled'), y.textContent]; })()") == ["true", "Creating…"])
    c.js("document.querySelector('input[name=project-name]').blur()")
    c.press("Escape")
    c.js("[...document.querySelectorAll('form .actions button')].find(b => b.textContent === 'Cancel').click()")
    check("and neither Esc nor Cancel leaves", c.js("location.hash") == "#/new")
    check("a name with spaces and capitals makes the project and opens it", waited(lambda: c.js("location.hash") == f"#/p/{NAME}"), c.js("location.hash"))
    time.sleep(1.5)
    check("its folder is a new repo with the kit committed", (hub.PROJECTS / NAME / ".git").exists() and "scripts/memwrite.py" in subprocess.run(["git", "-C", str(hub.PROJECTS / NAME), "ls-files"], capture_output=True, text=True).stdout)
    shown = c.js("[document.querySelector('#side').innerText, document.querySelector('#top').innerText]")
    check("the sidebar and the page title show the name as typed", shown and DISPLAY in shown[0] and DISPLAY in shown[1], shown)
    status, state = api("GET", "/api/state")
    mine = next((p for p in state["projects"] if p["name"] == NAME), {})
    check("the state carries it as the project's display name", mine.get("display") == DISPLAY, mine)
    c.shot("02-made")
    status, said = api("POST", "/api/projects", {"name": DISPLAY.lower()})
    check("the same name again, in other capitals, is refused in words", status == 409 and said["error"] == f"There's already a project called {DISPLAY}.", said)

    # A folder already there: offered, and used only on yes. Then folders that don't load.
    folder = hub.PROJECTS / OTHER
    folder.mkdir()
    (folder / "notes.txt").write_text("mine\n")
    c.js("location.hash = '#/new'"); time.sleep(1.5)
    c.type_name(OTHER_DISPLAY)
    hint = c.js("document.getElementById('name-hint').textContent")
    check("the hint says the folder is already there", hint == f"~/projects/{OTHER} is already there. Create asks before using it.", hint)
    c.press("Enter", "\r")
    asked = waited(c.confirm, 5)
    check("Create offers the folder that is already there", asked and asked[0] == f"Use ~/projects/{OTHER}?" and asked[1] == ["Cancel", "Use it"], asked)
    c.shot("03-use-it")
    c.answer("Cancel")
    check("Cancel there makes nothing", not (HOME / "agent-memory" / OTHER).exists() and not (folder / ".git").exists() and c.js("location.hash") == "#/new")
    c.press("Enter", "\r")
    waited(c.confirm, 5)
    c.answer("Use it")
    check("Use it makes the project in that folder", waited(lambda: c.js("location.hash") == f"#/p/{OTHER}"), c.js("location.hash"))
    check("the folder becomes a repo and keeps your files, uncommitted", (folder / ".git").exists() and (folder / "notes.txt").read_text() == "mine\n" and "notes.txt" in subprocess.run(["git", "-C", str(folder), "status", "--short"], capture_output=True, text=True).stdout)
    check("its display name is the words as typed, with the spaces made single", api("GET", "/api/state")[1]["projects"] and next(p for p in api("GET", "/api/state")[1]["projects"] if p["name"] == OTHER)["display"] == " ".join(OTHER_DISPLAY.split()))

    c.fresh("#/")
    c.js("""(() => { const real = window.fetch; window.fetch = (url, o) => String(url).includes('/api/folders') ? Promise.reject(new TypeError('offline')) : real(url, o); })()""")
    c.js("location.hash = '#/new'"); time.sleep(1.5)
    said = c.js("document.querySelector('.retry-line') && document.querySelector('.retry-line').innerText")
    check("folders that don't load say so in plain words, with Retry", said and "didn't load" in said and "Retry" in said, said)
    check("and Create stays on", c.js("document.querySelector('form .actions button.primary').getAttribute('aria-disabled')") is None)
    c.type_name("Hub Test Never Made")
    c.press("Enter", "\r")
    asked = waited(c.confirm, 5)
    check("a create with no folder then asks before making a new one", asked and asked[0] == "Make a new folder?", asked)
    c.shot("04-folders-failed")
    c.answer("Cancel")
    check("and Cancel there makes nothing", not (HOME / "agent-memory" / "hub-test-never-made").exists() and not (hub.PROJECTS / "hub-test-never-made").exists())

    # A phone: the field is 16px so iOS doesn't zoom, and the buttons fit.
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True)
    c.fresh("#/new")
    size = c.js("parseFloat(getComputedStyle(document.querySelector('input[name=project-name]')).fontSize)")
    check("on a phone the name field is 16px", size and size >= 16, size)
    check("on a phone nothing runs off the side", c.js("document.documentElement.scrollWidth <= innerWidth"))
    c.type_name("My Big Idea")
    c.shot("05-phone")
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
        for name in (NAME, OTHER):
            left = remove_project(name)
            check(f"{name} is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
