#!/usr/bin/env python3
"""The sidebar's features from herdr's most-voted asks, each behind its switch in Settings › Features, end to end:
- the project order kept in settings (drag, ⌥↑ ⌥↓, the ⋯ menu), in both sidebar orders;
- hidden projects: out of the sidebar, in Go to and the Hidden row, still telling you when they need you;
- the sidebar on the right: the shell, its edge, the rail, the phone's drawer and Peek, and body[data-sidebar];
- a colour per project, from a curated set, on its mark, its rows and in Go to, in both themes;
- jump numbers while ⌥ is held, and ⌥1–9 in Go to;
- notices: how long they stay, Clear all, Recent (the last 50 on this device), a toast that waits under the pointer,
  and a swipe on the phone;
- where new worktrees go (worktree_path), checked and previewed, and a checkout placed there listed and removed;
- names kept in step with Claude both ways (sync_title), and a session's subagents nested under its row;
- and for every switch: off, the hub looks and behaves as it did before.

A throwaway project, hub-test-throwaway-<n>, made here and removed at the end, with three plain terminals. The page
sees only that project and three made-up ones (laid over /api/state), so nothing private is on screen, and what each
session is doing is laid over the real state too. Settings go to the real server, and are put back at the end.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/sidebar_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, secrets, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, OWNER, STATE, TMUX, WRITE, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT
import hub_base as base

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-sidebar.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
CONFIG = Path(os.path.realpath(base.CONFIG))
OTHERS = ["atlas", "harbor", "juniper"]  # made-up projects the page shows beside the throwaway one
MINE = ["project_order", "hidden_projects", "sidebar_side", "project_colours", "notice_time", "worktree_path", "feature_project_order", "feature_hide_projects",
        "feature_project_colours", "feature_jump_numbers", "feature_notice_tools", "feature_title_sync", "feature_subagents"]
failures = 0

FAKE = """(() => {
  window.EventSource = undefined;  // the stream would bring the real state past this overlay: the page polls instead
  const real = window.fetch.bind(window);
  window.fetch = async (url, options) => {
    const answer = await real(url, options);
    if (typeof url !== "string" || !url.startsWith("/api/state") || !answer.ok) return answer;
    const data = await answer.clone().json();
    const name = localStorage.getItem("test.project");
    const mine = data.projects.find((p) => p.name === name);
    data.projects = mine ? [mine, ...%s.map((n) => ({ ...mine, name: n, display: n, needs: 0, latest: null, dreaming: false }))] : [];
    data.sessions = data.sessions.filter((s) => s.project === name);
    const fake = JSON.parse(localStorage.getItem("test.fake") || "{}");
    data.sessions.forEach((s) => { if (fake[s.id]) Object.assign(s, fake[s.id]); });
    if (window.manualPoll || !window.lastAt) window.lastAt = Date.now() / 1000;
    data.at = window.lastAt;
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  window.told = [];
  window.Notification = function (title, options) { window.told.push({ title, ...(options || {}) }); return { close() {}, set onclick(f) {} }; };
  window.Notification.permission = "granted";
  window.Notification.requestPermission = async () => "granted";
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


def put(body):
    return api("PUT", "/api/settings", body)


def values():
    return api("GET", "/api/settings")[1]["values"]


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


def page_of(width, height, mobile):
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
    c.js(f"localStorage.setItem('test.project', {json.dumps(NAME)}); localStorage.removeItem('test.fake'); localStorage.removeItem('hub.noticeLog')")
    c.call("Page.reload")
    waited(lambda: c.js("typeof hub !== 'undefined' && hub.ready && !!document.querySelector('#side .nav.session')"), 30)
    c.settle()
    return c


def fake(c, sid, fields):
    c.js(f"(() => {{ const f = JSON.parse(localStorage.getItem('test.fake') || '{{}}'); f[{json.dumps(sid)}] = {json.dumps(fields)}; localStorage.setItem('test.fake', JSON.stringify(f)); }})()")


# What the sidebar shows, in order: each row's kind and words, its colour edge, the Hidden row, subagents, numbers.
SIG = """[...document.querySelectorAll('#side .side-list .side-row, #side .side-list .side-fold, #side .side-crew, #side .side-hidden')].map((el) =>
  [el.className.replace(/\\b(on|two|done-read|done-unread|menu-open|drop-before|drop-after)\\b/g, '').replace(/\\s+/g, ' ').trim(), (el.querySelector('.label') || el).textContent.trim().slice(0, 40),
   el.getAttribute('style') || '', el.dataset.jump || '', (el.closest('.side-group') || {}).getAttribute ? (el.closest('.side-group').getAttribute('style') || '') : '']).concat([[document.body.dataset.sidebar, document.body.dataset.jumpKeys || '', getComputedStyle(document.querySelector('#side')).order]])"""
LOOSE = "[...document.querySelectorAll('#side .side-list > .side-group[data-project]:not(.hub-group)')].map((g) => g.dataset.project)"


sweep()
launchd_before = launchd_jobs()
as_found = CONFIG.read_bytes()
held = json.loads(as_found).get("settings", {})
if any(k in held for k in MINE):  # start from none of this check's settings, as a hub that never used them
    put({k: v for k, v in api("GET", "/api/settings")[1]["defaults"].items() if k in MINE})
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
placed_root = HOME / "projects" / f"{NAME}-worktrees"
try:
    status, made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    REPO = HOME / "projects" / NAME

    # ── The settings, on the server ──
    status, page = api("GET", "/api/settings")
    schema = {i["name"]: i for i in page["schema"]}
    check("every switch is in Features, on by default", all(schema[f"feature_{n}"]["section"] == "features" and page["defaults"][f"feature_{n}"] is True
                                                           for n in ("project_order", "hide_projects", "project_colours", "jump_numbers", "notice_tools", "title_sync", "subagents")))
    check("the defaults are today's behaviour", page["defaults"]["sidebar_side"] == "left" and page["defaults"]["notice_time"] == "auto" and page["defaults"]["worktree_path"] == ""
          and page["defaults"]["project_order"] == [] and page["defaults"]["hidden_projects"] == [] and page["defaults"]["project_colours"] == {})
    check("the order and the colours are kept off the Settings page; hidden projects are on it", schema["project_order"].get("hidden") and schema["project_colours"].get("hidden") and not schema["hidden_projects"].get("hidden"))
    status, said = put({"project_order": ["juniper", "atlas", NAME, "juniper"]})
    check("an order is kept as given, once each", status == 200 and said["values"]["project_order"] == ["juniper", "atlas", NAME], said)
    for setting, bad, why in (("project_order", ["Not A Name"], "project names"), ("project_colours", {NAME: "#ff0000"}, "one of"), ("project_colours", {"../x": "jade"}, "name projects"),
                              ("sidebar_side", "top", "one of"), ("notice_time", "7", "one of"), ("worktree_path", "../{repo}-wt/{name}", "no .."), ("worktree_path", "/etc/{name}", "inside the repo"),
                              ("worktree_path", "~/Desktop/{name}", "inside the repo"), ("worktree_path", "{nope}/{name}", "isn't a placeholder"), ("worktree_path", ".git/x/{name}", ".git"),
                              ("worktree_path", "{parent}/wt", "End with"), ("worktree_path", "{parent}/{name}/x", "last folder"), ("worktree_path", "~/projects/{name}", "loose")):
        status, said = put({setting: bad})
        check(f"{setting} refuses {bad!r}", status == 400 and why in said.get("error", ""), said)
    status, said = put({"project_colours": {NAME: "jade"}, "worktree_path": "{parent}/{repo}-worktrees/{name}"})
    check("a colour from the set and a sibling-folder template are kept", status == 200 and said["values"]["project_colours"] == {NAME: "jade"} and said["values"]["worktree_path"] == "{parent}/{repo}-worktrees/{name}", said)
    status, seen = api("GET", f"/api/settings/worktree-preview?template={urllib.request.quote('{parent}/{repo}-worktrees/{name}')}&project={NAME}")
    check("the preview says where a new worktree would go, for a real project", seen.get("ok") and seen.get("path") == f"~/projects/{NAME}-worktrees/fix-login-a1b2" and seen.get("outside") is True, seen)
    status, seen = api("GET", f"/api/settings/worktree-preview?template={urllib.request.quote('../x/{name}')}")
    check("and why not, for a template that climbs out", seen.get("ok") is False and ".." in seen.get("why", ""), seen)
    status, seen = api("GET", f"/api/settings/worktree-preview?template=&project={NAME}")
    check("empty is today's place", seen.get("path") == f"~/projects/{NAME}/.claude/worktrees/fix-login-a1b2" and seen.get("outside") is False, seen)

    # ── A worktree placed by the setting, made, listed and removed ──
    import hub_data as hub, hub_worktrees as wts
    time.sleep(1.1)  # this process reads the config again when it changes
    folder = Path(hub.make_worktree(str(REPO), "placed-a1b2", NAME))
    check("a new worktree goes where the setting says", folder == placed_root / "placed-a1b2" and (folder / ".git").exists(), folder)
    sid = secrets.token_hex(4)
    (hub.META / f"{sid}.json").write_text(json.dumps({"id": sid, "project": NAME, "repo": str(REPO), "title": f"{NAME} · Placed", "kind": "claude", "isolate": True, "created": time.time(),
                                                      "folder": str(folder), "tree": {"base": "main", "start": "", "branch": "hub/placed-a1b2", "placed": True}}))
    status, listed = api("GET", f"/api/p/{NAME}/worktrees")
    rows = [r for e in listed.get("repos", []) for r in e["rows"]]
    check("the project's worktrees list the placed checkout", any(r["path"] == f"~/projects/{NAME}-worktrees/placed-a1b2" for r in rows), rows)
    check("and the session's row carries its facts", (hub.worktrees.session_tree(json.loads((hub.META / f"{sid}.json").read_text())) or {}).get("branch") == "hub/placed-a1b2")
    stray = placed_root / "stray"; stray.mkdir(parents=True, exist_ok=True)
    status, said = api("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": f"~/projects/{NAME}", "path": str(stray)})
    check("a folder beside it that no session placed is refused", status != 200 and "error" in said, said)
    status, said = api("POST", f"/api/p/{NAME}/worktrees/remove", {"repo": f"~/projects/{NAME}", "path": str(folder)})
    check("the placed checkout is removed like any other", status == 200 and not folder.exists(), said)
    (hub.META / f"{sid}.json").unlink()
    put({"worktree_path": ""})
    time.sleep(1.1)
    again = Path(hub.make_worktree(str(REPO), "home-c3d4", NAME))
    check("with the setting empty, a worktree goes in .claude/worktrees as before", again == REPO / ".claude" / "worktrees" / "home-c3d4", again)
    subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(again)], capture_output=True)

    # ── Names in step with Claude, and subagents, on the server ──
    sid = secrets.token_hex(4)
    meta = {"id": sid, "project": NAME, "repo": str(REPO), "title": f"{NAME} · First", "kind": "claude", "isolate": False, "created": time.time(), "folder": str(REPO)}
    (hub.META / f"{sid}.json").write_text(json.dumps(meta))
    row = {"title": meta["title"], "alive": False, "state": "ended"}
    hub.sync_title(meta, f"{NAME} · First", row)
    check("the name Claude shows first is noted, and nothing changes", meta.get("claudeTitle") == f"{NAME} · First" and row["title"] == f"{NAME} · First")
    hub.sync_title(meta, "Renamed in Claude", row)
    kept = json.loads((hub.META / f"{sid}.json").read_text())
    check("a /rename in Claude reaches the hub", row["title"] == "Renamed in Claude" and kept["title"] == "Renamed in Claude", kept)
    sent = []
    was = hub.rename_live
    hub.rename_live = lambda m: sent.append(m["title"]) or True
    kept = hub._update_meta(sid, title=f"{NAME} · From the hub", renamePending=True)
    hub.sync_title(kept, "Renamed in Claude", {"title": kept["title"], "alive": True, "state": "needs"})
    time.sleep(0.3)
    check("a waiting rename isn't sent while a dialog is open", not sent, sent)
    hub.sync_title(kept, "Renamed in Claude", {"title": kept["title"], "alive": True, "state": "finished"})
    waited(lambda: sent, 3)
    check("it is sent once Claude can take it", sent == [f"{NAME} · From the hub"], sent)
    check("and stops waiting", waited(lambda: json.loads((hub.META / f"{sid}.json").read_text()).get("renamePending") is False, 3))
    hub.rename_live = was
    kept = json.loads((hub.META / f"{sid}.json").read_text())
    put({"feature_title_sync": False})
    time.sleep(1.1)
    check("off, the poll leaves names alone (sync_title is called only while the switch is on)", hub.hub_setting("feature_title_sync", True) is False)
    put({"feature_title_sync": True})
    (hub.META / f"{sid}.json").unlink()
    import hub_agents
    script = Path(tempfile.mkdtemp(prefix="hub-crew.")) / "t.jsonl"
    lines = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": "Agent", "input": {"description": f"Job {i}", "subagent_type": "Explore"}}]}} for i in range(3)]
    lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t0", "content": "done"}]}})
    lines.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "no", "is_error": True}]}})
    lines.append({"type": "custom-title", "customTitle": "Name from the transcript", "sessionId": "x"})
    script.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    got = hub_agents.counts("crew-test", script, True)
    check("each subagent comes with its state, running first", [(a["what"], a["state"]) for a in got["list"]] == [("Job 2", "running"), ("Job 1", "failed"), ("Job 0", "done")] and got["running"] == 1, got)
    check("the transcript's custom title is read", hub_agents.digest_of("crew-test", script)["title"] == "Name from the transcript")
    check("a session that isn't running has no running subagent", [a["state"] for a in hub_agents.counts("crew-test2", script, False)["list"]] == ["stopped", "failed", "done"])
    hub_agents.forget("crew-test"); hub_agents.forget("crew-test2")

    # ── The page ──
    ids = []
    for word in ("Fix the login", "Write the docs", "Ship it"):
        s = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})[1]["ids"][0]
        api("POST", f"/api/sessions/{s}/rename", {"title": word})
        ids.append(s)
    A, B, C = ids
    time.sleep(1)
    for s in ids:  # a plain prompt, so a screenshot names no user or machine
        subprocess.run(TMUX + ["send-keys", "-t", f"hub-{s}", "PS1='% '; clear", "Enter"], capture_output=True)
    put({k: page["defaults"][k] for k in MINE})
    desk = page_of(1440, 900, False)
    base_sig = desk.js(SIG)
    check("with none of these set, the projects are in the server's order", desk.js(LOOSE) == [NAME, *OTHERS], desk.js(LOOSE))
    check("the sidebar is on the left, and says so on the body", desk.js("document.body.dataset.sidebar") == "left" and desk.js("document.querySelector('#side').getBoundingClientRect().left") == 0)

    # Order
    put({"project_order": ["juniper", NAME, "atlas", "harbor"]})
    desk.settle()
    check("the sidebar follows the order kept in settings", desk.js(LOOSE) == ["juniper", NAME, "atlas", "harbor"], desk.js(LOOSE))
    check("j and k with the prefix walk the same order", desk.js("sideSessions().map((s) => s.project).every((p) => p === '%s')" % NAME))
    desk.js(f"""(() => {{ const dt = new DataTransfer(); dt.setData('text/x-hub-project', 'harbor');
      const row = document.querySelector('#side .side-group[data-project="juniper"] > .side-row.project'), r = row.getBoundingClientRect();
      row.dispatchEvent(new DragEvent('dragover', {{ dataTransfer: dt, bubbles: true, cancelable: true, clientY: r.top + 2 }}));
      window.lineShown = row.classList.contains('drop-before');
      row.dispatchEvent(new DragEvent('drop', {{ dataTransfer: dt, bubbles: true, cancelable: true, clientY: r.top + 2 }})); }})()""")
    check("dragging a project over another shows where it lands", desk.js("window.lineShown") is True)
    check("dropping it there moves it", waited(lambda: desk.js(LOOSE) == ["harbor", "juniper", NAME, "atlas"], 5), desk.js(LOOSE))
    check("and every device gets the order from the server", waited(lambda: values()["project_order"] == ["harbor", "juniper", NAME, "atlas"], 5), values()["project_order"])
    desk.js(f"document.querySelector('#side [data-key=\"p:{NAME}\"]').focus()")
    desk.key("ArrowUp", "ArrowUp", modifiers=1, vk=38)
    check("⌥↑ on a focused project moves it up", waited(lambda: desk.js(LOOSE) == ["harbor", NAME, "juniper", "atlas"], 5), desk.js(LOOSE))
    check("and focus stays on it", desk.js("document.activeElement && document.activeElement.dataset.key") == f"p:{NAME}")
    desk.key("ArrowDown", "ArrowDown", modifiers=1, vk=40)
    check("⌥↓ moves it back down", waited(lambda: desk.js(LOOSE) == ["harbor", "juniper", NAME, "atlas"], 5), desk.js(LOOSE))
    desk.js(f"document.querySelector('#side [data-key=\"p:{NAME}\"]').focus()"); desk.click(f'#side [data-key="pmore:{NAME}"]')
    items = desk.js("[...document.querySelectorAll('.popup.menu button')].map((b) => b.textContent)")
    check("the ⋯ menu offers Move up, Move down, Colour and Hide", any(t.startswith("Move up") for t in items) and any(t.startswith("Move down") for t in items) and any("olour" in t for t in items) and "Hide from the sidebar" in items, items)
    desk.key("Escape")
    desk.click('#side [data-key="side-order"]')
    check("sorted by what needs you, the project list keeps the order", desk.js("[...document.querySelectorAll('#side .side-list > .side-group[data-project]:not(.hub-group)')].map((g) => g.dataset.project)") == ["harbor", "juniper", NAME, "atlas"])
    desk.click('#side [data-key="side-order"]')

    # Colours
    put({"project_colours": {NAME: "jade", "atlas": "orange"}})
    desk.settle()
    group = f'#side .side-group[data-project="{NAME}"]'
    check("a coloured project runs its colour down its rows", desk.js(f"document.querySelector('{group}').classList.contains('tinted') && document.querySelector('{group}').style.getPropertyValue('--pc') === 'var(--pc-jade)'"))
    check("its mark takes the colour", desk.js(f"document.querySelector('{group} .mark').style.getPropertyValue('--c')") == "var(--pc-jade)")
    check("the dark tone is the dark theme's", desk.js(f"getComputedStyle(document.querySelector('{group}')).boxShadow").startswith("rgb(45, 212, 160)"), desk.js(f"getComputedStyle(document.querySelector('{group}')).boxShadow"))
    desk.shot("sidebar-desk-colours")
    desk.js("document.documentElement.dataset.theme = 'light'")
    check("the light theme has its own, deeper tone", desk.js(f"getComputedStyle(document.querySelector('{group}')).boxShadow").startswith("rgb(12, 138, 102)"))
    desk.js("document.documentElement.dataset.theme = 'dark'; applyAppearance && applyAppearance()")
    check("projectColour() says it for other parts, such as the tabs", desk.js(f"projectColour('{NAME}')") == "var(--pc-jade)" and desk.js("projectColour('harbor')") == "")
    desk.js(f"document.querySelector('#side [data-key=\"p:{NAME}\"]').focus()"); desk.click(f'#side [data-key="pmore:{NAME}"]')
    desk.js("[...document.querySelectorAll('.popup.menu button')].find((b) => /olour/.test(b.textContent)).click()")
    check("Colour… opens the set, as a radio group with None", waited(lambda: desk.js("document.querySelectorAll('dialog.colour-sheet [role=radio]').length") == 10) and desk.js("document.querySelector('dialog.colour-sheet [aria-checked=true]').dataset.colour") == "jade")
    desk.shot("sidebar-desk-colour-sheet")
    desk.key("ArrowRight", "ArrowRight", vk=39)
    check("the arrows walk the colours", desk.js("document.activeElement.dataset.colour") == "pink", desk.js("document.activeElement.dataset.colour"))
    desk.key("Enter", "Enter", vk=13)
    check("choosing one keeps it on the server", waited(lambda: values()["project_colours"].get(NAME) == "pink", 5), values()["project_colours"])
    put({"project_colours": {NAME: "jade", "atlas": "orange"}})
    desk.settle()

    # Hidden projects
    fake(desk, A, {"state": "needs", "asking": "May I push?"})
    desk.poll(2)
    put({"hidden_projects": [NAME]})
    desk.settle()
    check("a hidden project leaves the sidebar", desk.js(f"!document.querySelector('#side .side-list > .side-group[data-project=\"{NAME}\"]')"))
    check("a Hidden row at the foot counts it, and shows that it needs you", desk.js("!!document.querySelector('#side [data-key=\"hidden-projects\"] .orb-needs, #side [data-key=\"hidden-projects\"] .s-needs, #side [data-key=\"hidden-projects\"] .state')"), desk.js("document.querySelector('#side [data-key=\"hidden-projects\"]') && document.querySelector('#side [data-key=\"hidden-projects\"]').outerHTML.slice(0, 300)"))
    desk.js("location.hash = '#/settings'")
    check("its session that needs you still has its card", waited(lambda: desk.js(f"!!document.querySelector('#alerts [data-key=\"alert:{A}\"]')"), 5))
    desk.js("location.hash = '#/'")
    time.sleep(0.3)
    check("j and k skip it", desk.js(f"!sideSessions().some((s) => s.project === '{NAME}')"))
    desk.click('#side [data-key="hidden-projects"]')
    check("the Hidden row opens to list it", desk.js(f"!!document.querySelector('#side .side-hidden .side-group[data-project=\"{NAME}\"]')"))
    desk.shot("sidebar-desk-hidden")
    desk.click('#side [data-key="hidden-projects"]')
    desk.js("openPalette()")
    time.sleep(0.3)
    desk.js(f"document.querySelector('dialog.palette input').value = '{NAME}'; document.querySelector('dialog.palette input').dispatchEvent(new Event('input'))")
    found = desk.js("[...document.querySelectorAll('dialog.palette .opt')].map((o) => o.textContent)")
    check("Go to still finds the project, marked Hidden, and its sessions", any("Hidden" in t for t in found) and any("Fix the login" in t for t in found), found)
    desk.key("Escape")
    put({"hidden_projects": []})
    desk.settle()
    fake(desk, A, {"state": "shell"})
    desk.poll()

    # Subagents
    crew = {"running": 1, "total": 3, "doing": ["Read the docs"], "list": [{"id": "t3", "what": "Read the docs", "type": "Explore", "state": "running"},
                                                                          {"id": "t2", "what": "Check the tests", "type": "general-purpose", "state": "done"}, {"id": "t1", "what": "Look for leaks", "type": "Explore", "state": "failed"}]}
    fake(desk, B, {"agents": crew})
    desk.poll()
    check("a session's subagents nest under its row, open while one runs", desk.js(f"document.querySelectorAll('#side [data-crew=\"{B}\"] .crew-row').length") == 3)
    check("each says its state", desk.js(f"[...document.querySelectorAll('#side [data-crew=\"{B}\"] .crew-row')].map((r) => r.className.split(' c-')[1])") == ["running", "done", "failed"])
    desk.shot("sidebar-desk-subagents")
    desk.click(f'#side [data-key="crew:{B}"]')
    folded = desk.js(f"[document.querySelectorAll('#side [data-crew=\"{B}\"] .crew-row').length, (document.querySelector('#side [data-crew=\"{B}\"] .crew-word') || {{}}).textContent, localStorage.getItem('crewOpen')]")
    check("the line folds them away and says how many", folded[:2] == [0, "3 subagents, 1 running"], folded)
    desk.click(f'#side [data-key="crew:{B}"]')

    # Jump numbers
    desk.js(f"location.hash = '#/s/{A},{B}'")
    waited(lambda: desk.js(f"!!document.querySelector('.pane[data-sid=\"{B}\"]')"), 10)
    time.sleep(0.5)
    desk.js("document.querySelector('#side .brand').click()")
    desk.key("Alt", "AltLeft", modifiers=1, kind="down", vk=18)
    time.sleep(0.5)
    check("holding ⌥ numbers the panes of the split", desk.js(f"[document.querySelector('.pane[data-sid=\"{A}\"]').dataset.jump, document.querySelector('.pane[data-sid=\"{B}\"]').dataset.jump]") == ["1", "2"])
    check("and their rows in the sidebar", desk.js(f"document.querySelector('#side .side-row[data-sid=\"{B}\"]').dataset.jump") == "2" and desk.js("document.body.dataset.jumpKeys") == "alt")
    desk.shot("sidebar-desk-jump")
    desk.key("Alt", "AltLeft", kind="up", vk=18)
    check("letting go takes them away", desk.js("!document.querySelector('[data-jump]') && !document.body.dataset.jumpKeys"))
    put({"feature_tabs": False})  # with tabs, a session already in a split's tab opens that split: this check is about Go to's numbers
    desk.settle()
    desk.js("location.hash = '#/'")
    time.sleep(0.4)
    desk.js("openPalette()")
    time.sleep(0.3)
    nums = desk.js("[...document.querySelectorAll('dialog.palette kbd.jump-n')].map((k) => k.textContent)")
    check("Go to numbers its sessions ⌥1, ⌥2, ⌥3", nums[:3] == ["⌥1", "⌥2", "⌥3"], nums)
    third = desk.js("[...document.querySelectorAll('dialog.palette .opt')].find((o) => (o.querySelector('kbd.jump-n') || {}).textContent === '⌥3').querySelector('.t').firstChild.textContent")
    desk.js("document.querySelector('dialog.palette input').focus()")
    desk.key("3", "Digit3", modifiers=1, vk=51)
    check("⌥3 opens the third", waited(lambda: not desk.js("!!document.querySelector('dialog.palette[open]')") and (desk.js("titleNow(), document.title") or "").find(third) >= 0, 5), [third, desk.js("document.title")])
    desk.js("location.hash = '#/'")
    desk.js("location.hash = '#/'")
    put({"feature_tabs": True})
    time.sleep(0.4)

    # Notices
    put({"notice_time": "10"})
    desk.settle()
    desk.js("showNotice({ key: 'x1', kind: 'done', title: 'One', line: 'First' })")
    check("notice_time sets how long a notice stays", desk.js("document.querySelector('[data-notice=\"x1\"]').dataset.left") == "10000")
    check("one notice shows Recent, not Clear all", desk.js("!!document.querySelector('.notice-tools-bar') && document.querySelector('[data-key=\"notice-clear\"]').hidden"))
    desk.js("tell('banner', { native: {}, banner: { key: 's:%s', kind: 'done', title: 'Write the docs', line: 'Two' } })" % B)
    check("two show Clear all too", desk.js("!document.querySelector('[data-key=\"notice-clear\"]').hidden"))
    desk.shot("sidebar-desk-notices")
    desk.click('[data-key="notice-clear"]')
    check("Clear all takes them all away", waited(lambda: desk.js("!document.querySelector('#notices .notice') && !document.querySelector('.notice-tools-bar')"), 3))
    put({"notice_time": "stay"})
    desk.settle()
    desk.js("showNotice({ key: 'x2', kind: 'needs', title: 'Stays', line: 'Until you say' })")
    time.sleep(1.2)
    check("'Until dismissed' keeps a notice", desk.js("!!document.querySelector('[data-notice=\"x2\"]') && document.querySelector('[data-notice=\"x2\"]').dataset.left === 'Infinity'"))
    desk.js("dropNoticeOf('x2')")
    log = desk.js("JSON.parse(localStorage.getItem('hub.noticeLog') || '[]')")
    check("what was told is kept in this browser's history", len(log) >= 1 and log[0]["title"] == "Write the docs" and log[0]["go"] == f"#/s/{B}", log)
    desk.js("openNoticeLog()")
    check("Recent lists it, newest first", waited(lambda: desk.js("document.querySelectorAll('dialog.notice-log .log-row').length") == len(log)))
    desk.shot("sidebar-desk-recent")
    desk.click("dialog.notice-log .log-row")
    check("and opens what it was about", waited(lambda: desk.js("location.hash") == f"#/s/{B}", 5), desk.js("location.hash"))
    desk.js("location.hash = '#/'")
    put({"notice_time": "auto"})
    desk.settle()
    desk.js("toast('Passing')")
    check("a toast takes the pointer, so it can wait under it", desk.js("getComputedStyle(document.getElementById('toast')).pointerEvents") == "auto")
    b = desk.js("(() => { const r = document.getElementById('toast').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()")
    desk.call("Input.dispatchMouseEvent", type="mouseMoved", x=b["x"], y=b["y"])
    time.sleep(5.6)
    check("and it does: it stays while pointed at", desk.js("document.getElementById('toast').classList.contains('show')"))
    desk.call("Input.dispatchMouseEvent", type="mouseMoved", x=700, y=300)
    check("then goes once the pointer leaves", waited(lambda: not desk.js("document.getElementById('toast').classList.contains('show')"), 4))

    # Rename with F2
    desk.js(f"document.querySelector('#side [data-key=\"s:{C}\"]').focus()")
    desk.key("F2", "F2", vk=113)
    check("F2 renames the session in hand", desk.js("!!document.querySelector('#side .side-input')"))
    desk.key("Escape", "Escape", vk=27)
    check("Esc leaves the name as it was", desk.js("!document.querySelector('#side .side-input')") and api("GET", "/api/state")[1]["sessions"] and next(s for s in api("GET", "/api/state")[1]["sessions"] if s["id"] == C)["title"].endswith("Ship it"))

    # Worktree setting on the Settings page
    desk.js("location.hash = '#/settings/sessions'")
    waited(lambda: desk.js("!!document.querySelector('.wt-input')"), 10)
    desk.js("(() => { const i = document.querySelector('.wt-input'); i.focus(); i.value = '{parent}/{repo}-worktrees/{name}'; i.dispatchEvent(new Event('input')); })()")
    check("the field previews where a worktree would go", waited(lambda: (desk.js("document.querySelector('.wt-preview').textContent") or "").find("-worktrees/fix-login-a1b2") >= 0, 5), desk.js("document.querySelector('.wt-preview').textContent"))
    desk.shot("sidebar-desk-worktree-setting")
    desk.js("(() => { const i = document.querySelector('.wt-input'); i.value = '../{name}'; i.dispatchEvent(new Event('input')); })()")
    check("and says why a bad one can't be used", waited(lambda: desk.js("document.querySelector('.wt-preview').classList.contains('bad')"), 5), desk.js("[document.querySelector('.wt-input').value, document.querySelector('.wt-preview').outerHTML]"))
    desk.js("(() => { const i = document.querySelector('.wt-input'); i.value = '.worktrees/{branch}'; i.dispatchEvent(new Event('input')); i.dispatchEvent(new Event('change')); })()")
    check("a good one is kept", waited(lambda: values()["worktree_path"] == ".worktrees/{branch}", 5), values()["worktree_path"])
    put({"worktree_path": ""})
    desk.js("location.hash = '#/'")
    time.sleep(0.4)

    # The sidebar on the right
    put({"sidebar_side": "right"})
    desk.settle()
    right = desk.js("[document.body.dataset.sidebar, Math.round(document.querySelector('#side').getBoundingClientRect().right), Math.round(document.querySelector('#content').getBoundingClientRect().left)]")
    check("on the right: the sidebar takes the right edge and the content the left", right == ["right", 1440, 0], right)
    w0 = desk.js("document.querySelector('#side').getBoundingClientRect().width")
    edge = desk.at(".side-edge")
    for kind, x in (("mousePressed", edge["x"]), ("mouseMoved", edge["x"] - 60), ("mouseReleased", edge["x"] - 60)):
        desk.call("Input.dispatchMouseEvent", type=kind, x=x, y=400, button="left", buttons=1 if kind != "mouseReleased" else 0, clickCount=1)
        time.sleep(0.1)
    w1 = desk.js("document.querySelector('#side').getBoundingClientRect().width")
    check("dragging its edge left makes it wider", abs(w1 - w0 - 60) <= 2, [w0, w1])
    desk.js("document.querySelector('.side-edge').focus()")
    desk.key("ArrowRight", "ArrowRight", vk=39)
    check("the arrow toward it narrows it", desk.js("document.querySelector('#side').getBoundingClientRect().width") < w1)
    desk.js("shell.w = SIDE.start; keepShell(); applyShell()")
    desk.key("b", "KeyB", modifiers=4, vk=66)
    check("⌘B folds it to the rail, still on the right", desk.js("document.body.classList.contains('rail') && Math.round(document.querySelector('#side').getBoundingClientRect().right) === 1440"))
    desk.shot("sidebar-desk-right-rail")
    desk.key("b", "KeyB", modifiers=4, vk=66)
    desk.js(f"location.hash = '#/s/{A}'")
    waited(lambda: desk.js(f"!!document.querySelector('.pane[data-sid=\"{A}\"]')"), 10)
    desk.shot("sidebar-desk-right")
    desk.js(f"document.querySelector('#side [data-key=\"s:{B}\"]').focus(); peekSession('{B}')")
    pk = waited(lambda: desk.js("document.querySelector('.peek-pop') && !document.querySelector('.peek-pop').classList.contains('sheet') ? [document.querySelector('.peek-pop').getBoundingClientRect().right, document.querySelector('#side').getBoundingClientRect().left] : null"), 5)
    check("Peek opens beside the sidebar, on its left", pk and pk[0] <= pk[1], pk)
    desk.js("closePeek && closePeek(false)")
    desk.js("location.hash = '#/'")

    # ── Every switch off: the hub as it was ──
    fake(desk, B, {"agents": crew})
    put({"project_order": ["harbor", "juniper", NAME, "atlas"], "hidden_projects": ["atlas"], "project_colours": {NAME: "jade"}, "sidebar_side": "left"})
    desk.settle()
    for name in ("project_order", "hide_projects", "project_colours", "subagents"):
        put({f"feature_{name}": False})
    desk.settle()
    off_sig = desk.js(SIG)
    put({k: page["defaults"][k] for k in ("project_order", "hidden_projects", "project_colours")})
    fake(desk, B, {"agents": {"running": 0, "total": 0, "doing": [], "list": []}})
    desk.settle()
    check("off, the sidebar is exactly what it is with none of them used", off_sig == desk.js(SIG) == base_sig, [off_sig, base_sig])
    put({"project_order": ["harbor", "juniper", NAME, "atlas"], "hidden_projects": ["atlas"], "project_colours": {NAME: "jade"}})
    desk.settle()
    check("off: the order is the server's", desk.js(LOOSE) == [NAME, *OTHERS], desk.js(LOOSE))
    check("off: nothing is hidden, and there's no Hidden row", desk.js("!document.querySelector('#side [data-key=\"hidden-projects\"]')") and "atlas" in desk.js(LOOSE))
    check("off: no colours, the mark keeps its own", desk.js(f"!document.querySelector('{group}').classList.contains('tinted') && !document.querySelector('{group} .mark').style.getPropertyValue('--c').includes('pc-')"))
    desk.js(f"document.querySelector('#side [data-key=\"p:{NAME}\"]').focus()"); desk.click(f'#side [data-key="pmore:{NAME}"]')
    items = desk.js("[...document.querySelectorAll('.popup.menu button')].map((b) => b.textContent)")
    check("off: the ⋯ menu is as it was", not any(t.startswith(("Move up", "Move down", "Hide", "Show in", "Colour", "Change colour")) for t in items), items)
    desk.key("Escape")
    desk.js(f"document.querySelector('#side [data-key=\"p:{NAME}\"]').focus()")
    desk.key("ArrowDown", "ArrowDown", modifiers=1, vk=40)
    check("off: ⌥↓ doesn't move a project", desk.js(LOOSE) == [NAME, *OTHERS] and values()["project_order"] == ["harbor", "juniper", NAME, "atlas"])
    put({"feature_jump_numbers": False, "feature_notice_tools": False, "notice_time": "30"})
    desk.settle()
    desk.js(f"location.hash = '#/s/{A},{B}'")
    waited(lambda: desk.js(f"!!document.querySelector('.pane[data-sid=\"{B}\"]')"), 10)
    desk.key("Alt", "AltLeft", modifiers=1, kind="down", vk=18)
    time.sleep(0.5)
    check("off: holding ⌥ shows no numbers", desk.js("!document.querySelector('[data-jump]') && !document.body.dataset.jumpKeys"))
    desk.key("Alt", "AltLeft", kind="up", vk=18)
    desk.js("openPalette()")
    time.sleep(0.3)
    check("off: Go to has no numbers and no Recent notices", desk.js("!document.querySelector('dialog.palette kbd.jump-n') && ![...document.querySelectorAll('dialog.palette .opt')].some((o) => /Recent notices/.test(o.textContent))"))
    desk.key("Escape")
    desk.js("location.hash = '#/'")
    desk.js("localStorage.removeItem('hub.noticeLog'); showNotice({ key: 'y1', kind: 'done', title: 'A', line: 'a' }); showNotice({ key: 'y2', kind: 'done', title: 'B', line: 'b' }); tell('banner', { native: {}, banner: { key: 'y3', kind: 'done', title: 'C' } })")
    check("off: no Clear all, no history kept", desk.js("!document.querySelector('.notice-tools-bar') && !localStorage.getItem('hub.noticeLog')"))
    check("off: a notice stays its old time", desk.js("document.querySelector('[data-notice=\"y1\"]').dataset.left") == "5000")
    desk.js("toast('Passing')")
    check("off: a toast lets the pointer through, as before", desk.js("getComputedStyle(document.getElementById('toast')).pointerEvents") == "none")
    desk.js("document.querySelectorAll('#notices .notice').forEach(dropNotice)")
    put({"notice_time": "auto"})
    put({f"feature_{n}": True for n in ("project_order", "hide_projects", "project_colours", "subagents", "jump_numbers", "notice_tools")})
    desk.settle()
    check("on again, it all comes back at once, with no reload", desk.js(LOOSE) == ["harbor", "juniper", NAME] and desk.js(f"document.querySelector('{group}').classList.contains('tinted')"))

    # ── The phone ──
    put({"hidden_projects": [], "sidebar_side": "right", "notice_time": "auto"})
    phone = page_of(390, 844, True)
    phone.js("setSide(true)")
    time.sleep(0.5)
    rect = phone.js("[Math.round(document.querySelector('#side').getBoundingClientRect().left), Math.round(document.querySelector('#side').getBoundingClientRect().right)]")
    check("on the phone, the drawer comes from the right", rect[1] == 390 and rect[0] > 0, rect)
    phone.shot("sidebar-phone-right-drawer")
    phone.js("setSide(false)")
    put({"sidebar_side": "left"})
    phone.settle()
    phone.js("showNotice({ key: 'p1', kind: 'done', title: 'Swipe me', line: 'Away it goes' }); showNotice({ key: 'p2', kind: 'needs', title: 'Second', line: 'Still here' })")
    time.sleep(0.4)
    phone.shot("sidebar-phone-notices")
    b = phone.at('[data-notice="p1"]')
    phone.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": b["x"], "y": b["y"]}])
    for dx in (20, 60, 110, 160):
        phone.call("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": b["x"] + dx, "y": b["y"] + 2}])
        time.sleep(0.03)
    phone.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    check("a notice swipes away on the phone", waited(lambda: phone.js("!document.querySelector('[data-notice=\"p1\"]')"), 3))
    check("and the swipe opened nothing", phone.js("location.hash") in ("#/", ""), phone.js("location.hash"))
    b = phone.at('[data-notice="p2"]')
    phone.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": b["x"], "y": b["y"]}])
    phone.call("Input.dispatchTouchEvent", type="touchMove", touchPoints=[{"x": b["x"] + 30, "y": b["y"]}])
    phone.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    time.sleep(0.4)
    check("a short swipe puts it back", phone.js("!!document.querySelector('[data-notice=\"p2\"]') && document.querySelector('[data-notice=\"p2\"]').style.transform === ''"))
    phone.js("openNoticeLog()")
    time.sleep(0.4)
    check("Recent fills the phone's screen", phone.js("Math.round(document.querySelector('dialog.notice-log').getBoundingClientRect().width)") == 390)
    phone.shot("sidebar-phone-recent")
    phone.js("document.querySelector('dialog.notice-log').close()")
    fake(phone, B, {"agents": crew})
    phone.poll()
    phone.js("setSide(true)")
    time.sleep(0.4)
    check("the phone's sidebar nests subagents too", phone.js(f"document.querySelectorAll('#side [data-crew=\"{B}\"] .crew-row').length") == 3)
    phone.shot("sidebar-phone-drawer")
    phone.js(f"projectMenu(document.querySelector('#side [data-key=\"pmore:{NAME}\"]'), project('{NAME}'))")
    items = phone.js("[...document.querySelectorAll('.popup.menu button')].map((b) => b.textContent)")
    check("on the phone, where nothing drags, the ⋯ menu moves a project", any(t.startswith("Move") for t in items), items)

    check("no script errors on the desk", not desk.errors, desk.errors)
    check("no script errors on the phone", not phone.errors, phone.errors)
finally:
    chrome.terminate()
    try:
        put({k: v for k, v in api("GET", "/api/settings")[1]["defaults"].items() if k in MINE})
    except Exception:
        pass
    shutil.rmtree(placed_root, ignore_errors=True)
    left = remove_project(NAME)
    check("the throwaway project is gone", not left and not placed_root.exists(), left)
    check("no launchd job was made", launchd_jobs() == launchd_before)
print(f"\n{'All passed' if not failures else f'{failures} failed'}. Screenshots in {OUT}")
sys.exit(1 if failures else 0)
