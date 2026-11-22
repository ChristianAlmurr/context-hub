#!/usr/bin/env python3
"""The hub-wide settings: the store behind GET and PUT /api/settings, server.py --check, and the Settings page.

Run: /usr/bin/python3 tests/settings_check.py <output-folder>
Runs against a second instance (the six HUB_* variables, see tests/instance.py) and changes its config.json, which it
puts back as it was at the end. Makes a throwaway project for the choice a project keeps, and removes it.
Then drives the page in headless Chrome (HUB_CDP_PORT) at a desk's size and a phone's, and saves screenshots.
"""
import base64, http.client, json, os, shutil, socket, stat, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, NAME, PORT as HUB_PORT, OWNER, WRITE, quiet_alert, remove_project, sweep
import hub_base as base

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="settings-check.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
SERVER = Path(__file__).resolve().parent.parent / "server.py"
CONFIG = Path(os.path.realpath(base.CONFIG))
failures = 0


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:600]}]"), flush=True)
    failures += 0 if ok else 1


def call(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, headers or (WRITE if method != "GET" else OWNER))
    r = c.getresponse()
    data = r.read()
    try:
        return r.status, json.loads(data)
    except ValueError:
        return r.status, {}


def put(body, headers=None):
    return call("PUT", "/api/settings", body, headers)


def on_disk():
    return json.loads(CONFIG.read_text())


as_found = CONFIG.read_bytes()  # put back at the end, whatever an earlier run left in it
original_mode = stat.S_IMODE(os.stat(CONFIG).st_mode)
# This check starts from a config with no settings yet, as a new hub's is: anything an earlier run saved is set aside.
if "settings" in json.loads(as_found):
    CONFIG.write_text(json.dumps({k: v for k, v in json.loads(as_found).items() if k != "settings"}, indent=2) + "\n")
    time.sleep(1.2)  # the server reads the file again when it changes
original = CONFIG.read_bytes()
sweep()
try:
    # ── the store ──
    status, page = call("GET", "/api/settings")
    names = [item["name"] for item in page.get("schema", [])]
    agreed = ["theme", "accent", "term_font_size", "density", "reduce_motion", "notify_needs", "notify_done", "notify_closed", "notify_catcher", "sound_needs", "sound_done", "sound_volume",
              "muted_projects", "sidebar_order", "asks_as_needs", "default_mode", "default_model", "default_effort", "default_worktree", "models", "prefix_key", "max_panes"]
    check("GET /api/settings gives values, the schema and the defaults, for every agreed name", status == 200 and all(n in names and n in page["values"] and n in page["defaults"] for n in agreed), [n for n in agreed if n not in names])
    check("its defaults are today's behaviour", page["defaults"]["theme"] == "dark" and page["defaults"]["notify_needs"] == "system" and page["defaults"]["notify_done"] == "off" and page["defaults"]["notify_closed"] == "system" and page["defaults"]["notify_catcher"] == "system" and page["defaults"]["sound_volume"] == 0.6
          and page["defaults"]["prefix_key"] == "Control+`" and page["defaults"]["max_panes"] == 4 and page["defaults"]["models"] == [] and page["defaults"]["default_mode"] == "", page["defaults"])
    text = json.dumps(page)
    check("the key is never sent, and access is only shown", "\"key\"" not in json.dumps(page["access"]) and (not CFG.get("key") or CFG["key"] not in text) and page["access"]["origin"] == CFG["origin"], page["access"])
    check("a request without the owner's login is turned away", call("GET", "/api/settings", headers={"Host": OWNER["Host"]})[0] == 403)
    check("a write without the app's origin is turned away", put({"theme": "light"}, {**OWNER, "Content-Type": "application/json"})[0] == 403)
    status, said = put({"thme": "light"})
    check("an unknown name is refused, with a did-you-mean", status == 400 and "Did you mean theme?" in said.get("error", "") and said.get("name") == "thme", said)
    for name, value in (("port", 1), ("login", "x"), ("origin", "http://x"), ("key", "y" * 40)):
        status, said = put({name: value})
        check(f"{name} is never written here", status == 409 and "install.sh" in said.get("error", ""), said)
    for name, value, why in (("theme", "blue", "one of"), ("sound_volume", 2, "from 0 to 1"), ("max_panes", 4.5, "whole number"), ("asks_as_needs", "yes", "on or off"), ("accent", "url(x)", "colour"),
                             ("prefix_key", "j", "Hold Control"), ("muted_projects", ["Not A Name"], "project names"), ("default_model", "gpt", "models in the list"), ("models", [{"id": "-x"}], "id")):
        status, said = put({name: value})
        check(f"a bad {name} is refused, saying what it must be", status == 400 and why in said.get("error", ""), said)
    check("nothing refused was written", on_disk() == json.loads(original), on_disk())

    before = on_disk()
    status, said = put({"theme": "light", "sound_volume": 0.35, "muted_projects": ["b-proj", "a-proj"]})
    after = on_disk()
    check("a good write answers with the new values", status == 200 and said["values"]["theme"] == "light" and said["values"]["sound_volume"] == 0.35 and said["values"]["muted_projects"] == ["a-proj", "b-proj"], said.get("values"))
    check("it changes the settings key and nothing else", {k: v for k, v in after.items() if k != "settings"} == before and list(after)[:len(before)] == list(before), after)
    check("the file keeps its indentation and stays at mode 600", stat.S_IMODE(os.stat(CONFIG).st_mode) == 0o600 and CONFIG.read_text().startswith("{\n" + " " * (len(original.decode().split("\n")[1]) - len(original.decode().split("\n")[1].lstrip()))))
    put({"theme": "dark"})
    check("a value set back to its default leaves the file", "theme" not in on_disk()["settings"], on_disk()["settings"])

    held = on_disk()
    held["settings"]["density"] = "compact"
    CONFIG.write_text(json.dumps(held, indent=1) + "\n")
    check("a change made by hand applies at once, without a restart", call("GET", "/api/settings")[1]["values"]["density"] == "compact")
    held["settings"]["densty"] = "x"
    held["settings"]["theme"] = "neon"
    held["no_vsc"] = []
    CONFIG.write_text(json.dumps(held, indent=1) + "\n")
    problems = [p["text"] for p in call("GET", "/api/settings")[1]["problems"]]
    check("diagnostics name an unknown setting, a bad value and an unknown key, with hints", any("densty" in p and "density" in p for p in problems) and any("theme is ignored" in p for p in problems) and any("no_vsc" in p and "no_vcs" in p for p in problems), problems)
    check("a bad value falls back to its default meanwhile", call("GET", "/api/settings")[1]["values"]["theme"] == "dark")
    check("a write keeps the settings it doesn't know", put({"density": "comfortable"})[0] == 200 and on_disk()["settings"].get("densty") == "x" and "no_vsc" in on_disk())
    ran = subprocess.run(["/usr/bin/python3", str(SERVER), "--check"], capture_output=True, text=True, timeout=60, env={k: v for k, v in os.environ.items() if k != "HUB_SESSION"})
    check("server.py --check prints them, with fixes, and fails", ran.returncode == 1 and "no_vsc" in ran.stdout and "Fix:" in ran.stdout and "tmux" in ran.stdout, ran.stdout + ran.stderr)
    CONFIG.write_text(CONFIG.read_text()[:-5])
    status, page = call("GET", "/api/settings")
    check("a config that won't parse is said, and every setting has its default", status == 200 and page["problems"][0]["level"] == "error" and "isn't valid JSON" in page["problems"][0]["text"] and page["values"]["density"] == "comfortable", page.get("problems"))
    broken = CONFIG.read_text()
    status, said = put({"theme": "light"})
    check("and nothing is written over it", status == 409 and CONFIG.read_text() == broken, said)
    CONFIG.write_bytes(original)

    status, health = call("GET", "/api/settings/health?fresh=1")
    parts = {p["name"]: p for p in health.get("parts", [])}
    check("health names claude, tmux, the hooks, the kit and launchd, each with a fix when wrong", status == 200 and set(parts) >= {"Claude Code", "tmux", "Hooks", "Memory kit", "launchd"}
          and all(p["fix"] for p in parts.values() if p["ok"] is False) and parts["Hooks"]["ok"] and parts["launchd"]["ok"] is None, health)
    status, about = call("GET", "/api/settings/about")
    check("about gives the version and what's new", status == 200 and about.get("version") and "news" in about and "branch" in about, about)

    # The Dream Catcher's switch: one place, whichever page sets it.
    was = call("GET", "/api/catcher")[1].get("auto")
    put({"dream_catcher_auto": not was})
    check("Settings and the Dream Catcher page share one switch", call("GET", "/api/catcher")[1].get("auto") is (not was) and call("GET", "/api/settings")[1]["values"]["dream_catcher_auto"] is (not was) and "dream_catcher_auto" not in on_disk().get("settings", {}))
    call("POST", "/api/catcher/auto", {"auto": was})
    check("and the page's switch shows in Settings", call("GET", "/api/settings")[1]["values"]["dream_catcher_auto"] is was)

    # Models and new-session defaults
    status, said = put({"models": [{"id": "claude-opus-5-5[1m]", "name": "Opus, long context", "say": "A million tokens"}, {"id": "haiku", "name": "Haiku"}], "default_model": "claude-opus-5-5[1m]"})
    check("an own model list and a default from it are kept", status == 200 and said["values"]["default_model"] == "claude-opus-5-5[1m]" and said["values"]["models"][0]["say"] == "A million tokens", said)
    status, said = put({"models": [{"id": "haiku"}]})
    check("a list without the default model is refused until the default changes", status == 400 and "default model" in said.get("error", ""), said)
    made = call("POST", "/api/projects", {"name": NAME})[1]
    quiet_alert(NAME)
    status, kept = call("POST", f"/api/p/{NAME}/start", {"mode": "plan", "model": "claude-opus-5-5[1m]", "effort": "high", "code": False})
    project = next((p for p in call("GET", "/api/state")[1]["projects"] if p["name"] == NAME), {})
    check("a project keeps the choice its last session started with, on the server", status == 200 and project.get("start") == {"mode": "plan", "effort": "high", "model": "claude-opus-5-5[1m]", "code": False}, (kept, project.get("start")))
    check("a project's choice must be a real mode", call("POST", f"/api/p/{NAME}/start", {"mode": "fast"})[0] == 400)
    status, forgot = call("POST", "/api/settings/forget-starts", {})
    project = next((p for p in call("GET", "/api/state")[1]["projects"] if p["name"] == NAME), {})
    check("Use these everywhere makes every project forget its choice", status == 200 and forgot["forgot"] >= 1 and project.get("start") is None, forgot)
    put({"default_model": "", "models": []})

    # ── the page ──
    CONFIG.write_bytes(original)
    notes = base.STATE / "settings-notes.json"
    kept_notes = notes.read_bytes() if notes.exists() else None
    notes.unlink(missing_ok=True)
    profile = tempfile.mkdtemp(prefix="hub-chrome.")
    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={CDP_PORT}", "--window-size=1440,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                target = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json")) if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.25)

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

        c = CDP(target["webSocketDebuggerUrl"])
        c.call("Page.enable"); c.call("Runtime.enable")
        c.call("Network.enable")
        c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
        c.size(1440, 900)
        c.call("Page.navigate", url=CFG["origin"] + "/#/")
        wait = lambda what, seconds=15: next((True for _ in range(seconds * 4) if c.js(what) or time.sleep(0.25)), False)
        check("Home shows the first-run card while the config has no settings", wait("!!document.querySelector('.panel.welcome')") and c.js("document.querySelectorAll('.welcome-list li').length") == 4, c.js("document.body.innerText.slice(0, 300)"))
        check("and the queue still leads Home", c.js("!document.querySelector('.qtabs') || document.querySelector('.dash > .panel').classList.contains('triage')"))
        check("SETTINGS is filled when the page loads", c.js("typeof SETTINGS === 'object' && SETTINGS.theme === 'dark' && pref('max_panes', 0) === 4"))
        check("saveSettings is there for other features to call", c.js("typeof window.saveSettings === 'function'"))
        check("the sidebar's foot has a gear to Settings", c.js("document.querySelector('#side [data-key=settings]').getAttribute('href')") == "#/settings")
        c.js("document.querySelector('#side [data-key=settings]').click()")
        check("it opens Settings, on Appearance", wait("!!document.querySelector('.set-body .set-title')") and c.js("document.querySelector('.set-title').textContent") == "Appearance" and c.js("document.title").startswith("Settings"))
        check("the page is built from the schema: a row for each Appearance setting", c.js("[...document.querySelectorAll('.set-row')].map(r => r.dataset.setting).join()") == "theme,accent,term_font_size,density,reduce_motion,term_renderer,term_park_after")
        c.js("window.heard = 0; window.addEventListener('hub:settings', () => window.heard++)")
        c.js("(() => { const b = document.querySelector('[data-key=\"set-theme:light\"]'); b.focus(); b.click(); })()")
        check("a choice saves at once, quietly, and fires hub:settings", wait("document.querySelector('[data-said=theme]').textContent === 'Saved'") and c.js("SETTINGS.theme") == "light" and c.js("window.heard") >= 1 and on_disk().get("settings", {}).get("theme") == "light")
        check("focus stays on the choice made", c.js("document.activeElement.dataset.key") == "set-theme:light", c.js("document.activeElement.outerHTML.slice(0, 120)"))
        c.js("(() => { const r = document.querySelector('#set-term_font_size'); r.value = 16; r.dispatchEvent(new Event('input')); })()")
        check("a slider previews while it moves, without saving", c.js("SETTINGS.term_font_size") == 16 and "term_font_size" not in on_disk().get("settings", {}))
        c.js("document.querySelector('#set-term_font_size').dispatchEvent(new Event('change'))")
        wait("document.querySelector('[data-said=term_font_size]').textContent === 'Saved'")
        check("and saves when let go", on_disk().get("settings", {}).get("term_font_size") == 16)
        check("Cancel changes is offered after a change", wait("!!document.querySelector('[data-key=appearance-cancel]')"))
        c.shot("settings-desk")
        c.js("document.querySelector('[data-key=appearance-cancel]').click()")
        check("Cancel puts back the values from before", wait("SETTINGS.theme === 'dark' && SETTINGS.term_font_size === 13") and not {"theme", "term_font_size"} & set(on_disk().get("settings", {})), on_disk().get("settings"))
        c.js("location.hash = '#/settings/notifications'")
        wait("document.querySelector('.set-title').textContent.startsWith('Notifications')")
        check("the hub's own sounds are offered", c.js("typeof window.hubPlaySound === 'function' && window.hubSounds.join() === 'chime,knock,bell'"))
        c.js("window.hubSounds = ['chime', 'knock', 'bell']; window.hubPlaySound = (s, v) => { window.played = [s, v]; }; dispatchEvent(new Event('hub:settings'))")
        c.js("document.querySelector('[data-key=\"set-sound_needs:bell\"]').click()")
        wait("!!document.querySelector('[data-key=\"set-sound_needs:play\"]:not([disabled])')")
        c.js("document.querySelector('[data-key=\"set-sound_needs:play\"]').click()")
        check("with hubPlaySound, Play plays the chosen sound at the chosen volume", c.js("JSON.stringify(window.played)") == json.dumps(["bell", 0.6]).replace(" ", ""), c.js("JSON.stringify(window.played)"))
        c.js("location.hash = '#/settings/sessions'")
        wait("document.querySelector('.set-title').textContent === 'New sessions'")
        c.js("document.querySelector('[data-key=\"set-default_mode:plan\"]').click()")
        wait("SETTINGS.default_mode === 'plan'")
        c.shot("settings-sessions")
        c.js("location.hash = '#/settings/sidebar'")
        wait("document.querySelector('.set-title').textContent.startsWith('Sidebar')")
        c.js("document.querySelector('[data-key=\"set-prefix_key\"]').click()")
        c.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
        time.sleep(0.4)
        check("Esc while recording a key only stops recording", c.js("location.hash") == "#/settings/sidebar" and c.js("SETTINGS.prefix_key") == "Control+`")
        c.js("document.querySelector('[data-key=\"set-prefix_key\"]').click()")
        c.call("Input.dispatchKeyEvent", type="keyDown", key="j", code="KeyJ", windowsVirtualKeyCode=74, modifiers=1)
        check("the leave-the-terminal key is recorded from the keys pressed", wait("SETTINGS.prefix_key === 'Alt+j'"), c.js("SETTINGS.prefix_key"))
        c.js("location.hash = '#/settings/keyboard'")
        check("Keyboard shows the live key sheet", wait("document.querySelectorAll('.set-keys').length === KEYS.length") and "Show or hide this sheet" in c.js("document.querySelector('.set-body').innerText"))
        c.js("location.hash = '#/settings/health'")
        check("Health lists the hub's parts", wait("document.querySelectorAll('.health-row').length >= 5") and "tmux" in c.js("document.querySelector('.set-body').innerText"))
        c.js("location.hash = '#/settings/access'")
        wait("document.querySelector('.set-title').textContent === 'Access'")
        check("Access is shown read only, without the key", c.js("document.querySelectorAll('.set-body input, .set-body [role=radio]').length") == 0 and CFG["origin"] in c.js("document.querySelector('.set-body').innerText") and (not CFG.get("key") or CFG["key"] not in c.js("document.body.innerHTML")))
        c.js("location.hash = '#/settings/about'")
        check("About gives the version, a check for updates and what changed", wait("!!document.querySelector('[data-key=update-check]')") and c.js("!!document.querySelector('.about-news li, .set-body .empty-line')"))
        c.js("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))")
        wait("!!document.querySelector('dialog.palette')")
        c.js("(() => { const i = document.querySelector('dialog.palette input'); i.value = 'appearance'; i.dispatchEvent(new Event('input')); })()")
        check("⌘K reaches Settings and each of its sections", c.js("[...document.querySelectorAll('dialog.palette .opt')].some(o => o.textContent.includes('Appearance') && o.textContent.includes('Settings'))"))
        c.js("document.querySelector('dialog.palette').close()")
        c.js("location.hash = '#/'")
        wait("!!document.querySelector('.panel.welcome')")
        check("the card ticks what was set", c.js("document.querySelectorAll('.welcome-list li.done').length") >= 3, c.js("document.querySelector('.panel.welcome').innerText"))
        c.shot("home-welcome")
        c.js("document.querySelector('[data-key=welcome-dismiss]').click()")
        gone = wait("!document.querySelector('.panel.welcome')")
        stored = next((True for _ in range(40) if (notes.exists() and json.loads(notes.read_text()).get("welcome") == "done") or time.sleep(0.25)), False)
        check("dismissing the card hides it for good", gone and stored, notes.read_text() if notes.exists() else "no notes")
        c.call("Page.reload")
        time.sleep(3)
        check("and it stays gone after a reload", c.js("!!document.querySelector('.dash')") and not c.js("!!document.querySelector('.panel.welcome')"))
        c.size(390, 844, mobile=True)
        c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
        c.js("location.hash = '#/settings/notifications'")
        wait("!!document.querySelector('.set-title')")
        time.sleep(0.6)
        check("on a phone a section is a page of its own under Settings, and rows stack", c.js("document.querySelector('.set-nav').offsetParent === null") and c.js("!!document.querySelector('#top [data-key=settings-back]')") and c.js("document.querySelector('.set-body').getBoundingClientRect().left") < 40
              and c.js("document.documentElement.scrollWidth <= innerWidth"))
        c.shot("settings-phone")
        c.js("location.hash = '#/settings/sessions'")
        time.sleep(0.8)
        c.shot("settings-phone-sessions")
        c.size(1440, 900)
        c.js("location.hash = '#/settings/health'")
        time.sleep(1.2)
        c.shot("settings-health")
        check("no script errors on the way", not c.errors, c.errors)
    finally:
        chrome.terminate()
        shutil.rmtree(profile, ignore_errors=True)
        if kept_notes is not None:
            notes.write_bytes(kept_notes)
finally:
    CONFIG.write_bytes(as_found)
    os.chmod(CONFIG, original_mode)
    left = remove_project(NAME)
    check("the throwaway project is gone", not left, left)

print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
