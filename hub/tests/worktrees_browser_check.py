#!/usr/bin/env python3
"""The worktree UI in headless Chrome, at desk and phone sizes, in a throwaway project, hub-test-throwaway-<n>, made
here and removed at the end: the chip in a session's pane header and its sheet, the close dialog's "Remove the checkout"
after a real commit, the second ask when files are still uncommitted after the close, and the project page's
Worktrees list with "Clean up merged" and its preview, removing a checkout and deleting an unmerged branch only after
its box is ticked.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives, with
Chrome's debugging port HUB_CDP_PORT. Screenshots go to the folder given as the first argument, else a temporary one.
Run: /usr/bin/python3 tests/worktrees_browser_check.py [screenshot folder]
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, STATE, WRITE, answer_first_run, launchd_jobs, quiet_alert, remove_project, sweep
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-worktrees.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
REPO = HOME / "projects" / NAME
failures = 0
NOTE = "tree-note.txt"
TASK = f"Create a file named {NOTE} in this folder containing the single line: hello from the worktree check. Then reply with the single word done."


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read() or b"{}")


def row(sid):
    return next((s for s in api("GET", "/api/state").get("sessions", []) if s["id"] == sid), None)


def waited(test, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.3)
    return None


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args], capture_output=True, text=True)


def tree(name, base="HEAD"):
    path = REPO / ".claude" / "worktrees" / name
    git(REPO, "worktree", "add", "-q", "-b", f"hub/{name}", str(path), base)
    return path


def commit(folder, file, text):
    (Path(folder) / file).write_text(text)
    git(folder, "add", file)
    git(folder, "commit", "-qm", f"Add {file}")


def has_branch(branch):
    return git(REPO, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").returncode == 0


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
        time.sleep(0.15)

    def click(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (e) e.click(); return !!e; }})()")

    def click_text(self, selector, words):
        """The first element matching the selector whose text starts with these words, clicked."""
        return self.js(f"(() => {{ const b = [...document.querySelectorAll({json.dumps(selector)})].find(b => b.textContent.trim().startsWith({json.dumps(words)})); if (b) b.click(); return !!b; }})()")

    def text(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); return e ? e.innerText : null; }})()")

    def go(self, route, ready):
        self.js(f"location.hash = {json.dumps(route)}")
        return waited(lambda: self.js(ready), 30)



sweep()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ids = []
desk = dict(width=1440, height=900, deviceScaleFactor=1, mobile=False)
handset = dict(width=390, height=844, deviceScaleFactor=2, mobile=True)
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    exclude = Path(git(REPO, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()) / "info" / "exclude"
    if "/.claude/worktrees/" not in exclude.read_text():
        exclude.write_text(exclude.read_text() + "\n/.claude/worktrees/\n")
    merged = tree("merged-aaaa"); commit(merged, "done.txt", "done\n"); git(REPO, "merge", "-q", "--no-ff", "-m", "Merge", "hub/merged-aaaa")
    unmerged = tree("unmerged-bbbb"); commit(unmerged, "half.txt", "half\n"); git(REPO, "worktree", "remove", str(unmerged))
    dirty = tree("dirty-cccc"); (dirty / "scratch.txt").write_text("unsaved\n"); (dirty / "notes.txt").write_text("unsaved\n")

    # a session that commits its work, then closes taking its checkout with it
    committer = api("POST", "/api/sessions", {"project": NAME, "tasks": [TASK], "isolate": True, "mode": "bypassPermissions", "model": "haiku", "effort": "low"})["ids"][0]
    ids.append(committer)
    answer_first_run(committer)
    # a session in plan mode, which can't commit: its file is left behind
    planner = api("POST", "/api/sessions", {"project": NAME, "tasks": ["Reply with the single word ready and nothing else"], "isolate": True, "mode": "plan", "model": "haiku", "effort": "low"})["ids"][0]
    ids.append(planner)
    answer_first_run(planner)
    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setDeviceMetricsOverride", **desk)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)
    c.js("localStorage.clear()")

    # ── the chip in a pane header ──
    done = waited(lambda: (lambda r: r if r and r["state"] == "finished" and (REPO / ".claude" / "worktrees").exists() else None)(row(committer)), 150)
    folder = Path(json.loads((STATE / "sessions" / f"{committer}.json").read_text())["folder"])
    check("the committer made its file in its own checkout", (folder / NOTE).exists(), list(folder.iterdir()) if folder.exists() else folder)
    waited(lambda: (row(committer).get("tree") or {}).get("changed") == 1, 30)
    c.go(f"#/s/{committer}", "!!document.querySelector('.pane-top .tree-chip')")
    chip = c.text(".pane-top .tree-chip")
    check("the pane header shows the branch, without the project's name, and what is uncommitted", chip and "1 changed" in chip and folder.name[len(NAME) + 1:] in chip and NAME not in chip, chip)
    check("the chip says it all to a screen reader", "Worktree hub/" in (c.js("document.querySelector('.pane-top .tree-chip').getAttribute('aria-label')") or ""))
    c.shot("01-desk-pane-chip")
    c.click(".pane-top .tree-chip")
    sheet = waited(lambda: c.text("dialog.tree-sheet"), 10)
    check("tapping it shows the branch, its base and the uncommitted file", sheet and "hub/" in sheet and "from main" in sheet and NOTE in sheet, sheet)
    check("a running session's checkout can't be removed from there", sheet and "Remove checkout" not in sheet and "still running" in sheet, sheet)
    c.shot("02-desk-tree-sheet")
    c.key("Escape")

    # ── close: commit first, then remove the checkout ──
    c.click(".pane-top [data-key=more]"); time.sleep(0.2)  # Close session lives in the pane's ⋯
    c.click_text(".popup.menu button", "Close session")
    dialog = waited(lambda: c.text("dialog.close-sheet"), 10)
    check("the close dialog offers to remove the checkout, keeping the branch", dialog and "Remove the checkout" in dialog and "(keeps the branch)" in dialog, dialog)
    boxes = c.js("[...document.querySelectorAll('dialog.close-sheet label.check')].map(l => [l.innerText, l.querySelector('input').checked, l.querySelector('input').disabled])")
    tree_box = next((b for b in boxes or [] if b[0].startswith("Remove the checkout")), None)
    check("with an uncommitted file it isn't ticked to start with", tree_box and tree_box[1] is False and tree_box[2] is False, boxes)
    check("commit-first is still offered and ticked", any(b[0].startswith("Commit them first") and b[1] for b in boxes or []), boxes)
    c.click_text("dialog.close-sheet label.check", "Remove the checkout")
    hint = c.text("dialog.close-sheet")
    check("ticking it says what happens if files are left", "asked before anything is lost" in (hint or ""), hint)
    c.shot("03-desk-close-dialog")
    c.click_text("dialog.close-sheet .btn.primary", "Close session")
    closed = waited(lambda: (lambda r: r if r and r["state"] == "closed" else None)(row(committer)), 400)
    result = (closed or {}).get("closeResult") or {}
    check("Claude committed its file first", bool(result.get("commits")), result)
    check("then the clean checkout was removed and the branch kept", (result.get("tree") or {}).get("removed") and not folder.exists() and has_branch(f"hub/{folder.name}"), result)
    notice = waited(lambda: (lambda t: t if t and "checkout is removed" in t else None)(c.js("document.getElementById('toast').innerText")), 20)
    check("the closed notice says the checkout went and the branch stays", bool(notice), c.js("document.getElementById('toast').innerText"))
    check("no dialog asks anything more", not c.js("!!document.querySelector('dialog[open]')"))
    check("the main checkout is untouched", (REPO / ".git").is_dir() and not (REPO / NOTE).exists())

    # ── close with a file left: the second ask ──
    waited(lambda: (row(planner) or {}).get("state") == "finished", 150)
    pfolder = Path(json.loads((STATE / "sessions" / f"{planner}.json").read_text())["folder"])
    (pfolder / "left.txt").write_text("never committed\n")
    c.go(f"#/s/{planner}", "!!document.querySelector('.pane-top [data-key=more]')")
    c.click(".pane-top [data-key=more]"); time.sleep(0.2)
    c.click_text(".popup.menu button", "Close session")
    waited(lambda: c.text("dialog.close-sheet"), 10)
    c.click_text("dialog.close-sheet label.check", "Tidy up")  # no handoff: closes at once
    c.click_text("dialog.close-sheet label.check", "Remove the checkout")
    c.click_text("dialog.close-sheet .btn.primary", "Close session")
    ask = waited(lambda: (lambda t: t if t and "Lose 1 uncommitted file" in t else None)(c.text("dialog[open]")), 30)
    check("after the close, files still uncommitted are asked about again, by name", ask and "left.txt" in ask and "for good" in ask, c.text("dialog[open]"))
    check("the checkout is still there while it asks", pfolder.is_dir())
    c.shot("04-desk-second-ask")
    c.click_text("dialog[open] .btn.danger", "Remove and lose 1 file")
    check("saying yes removes it, and the branch stays", waited(lambda: not pfolder.exists(), 15) and has_branch(f"hub/{pfolder.name}"))

    # ── the project page ──
    c.go(f"#/p/{NAME}", "!!document.querySelector('.trees-box .tree-row')")
    rows = waited(lambda: (lambda t: t if t and "dirty-cccc" in t and "merged-aaaa" in t else None)(c.text(".trees-box")), 30)
    check("the project page lists its worktrees", rows and "Worktrees" in rows and "unmerged-bbbb" in rows, rows)
    check("each row says what it holds", rows and "2 changed" in rows and "merged" in rows and "1 ahead" in rows, rows)
    check("Clean up merged counts the merged ones", "Clean up merged (1)" in (rows or ""), rows)
    c.shot("05-desk-project-trees")
    c.click_text(".trees-box button", "Clean up merged")
    preview = waited(lambda: c.text("dialog.tree-clean"), 10)
    check("the preview names what goes, and changes nothing yet", preview and "hub/merged-aaaa" in preview and "checkout and branch" in preview and merged.exists(), preview)
    c.shot("06-desk-clean-preview")
    c.click_text("dialog.tree-clean .btn.primary", "Clean up 1")
    check("clean up removes the merged checkout and branch", waited(lambda: not merged.exists() and not has_branch("hub/merged-aaaa"), 15))
    check("and leaves the dirty one", (dirty / "scratch.txt").exists())
    waited(lambda: "merged-aaaa" not in (c.text(".trees-box") or "merged-aaaa"), 15)
    row_of = lambda branch: f"[...document.querySelectorAll('.tree-row')].find(r => r.innerText.includes({json.dumps(branch)}))"
    c.js(f"{row_of('unmerged-bbbb')}.querySelector('.tree-acts button').click()")
    strong = waited(lambda: c.text("dialog[open]"), 10)
    check("deleting an unmerged branch says how many commits are lost", strong and "1 commit isn't merged" in strong, strong)
    check("its button stays off until the box is ticked", c.js("document.querySelector('dialog[open] .btn.danger').disabled") is True)
    c.shot("07-desk-strong-confirm")
    c.click("dialog[open] label.check input")
    check("ticking the box turns it on", c.js("document.querySelector('dialog[open] .btn.danger').disabled") is False)
    c.click("dialog[open] .btn.danger")
    check("then the branch is deleted", waited(lambda: not has_branch("hub/unmerged-bbbb"), 15))
    c.js(f"{row_of('dirty-cccc')}.querySelector('.tree-acts button').click()")
    ask = waited(lambda: c.text("dialog[open]"), 10)
    check("removing a dirty checkout from the list asks first, naming the files", ask and "Lose 2 uncommitted files" in ask and "scratch.txt" in ask and "notes.txt" in ask, ask)
    c.key("Escape")
    check("saying no keeps it", dirty.is_dir() and (dirty / "scratch.txt").exists())

    # ── phone ──
    c.call("Emulation.setDeviceMetricsOverride", **handset)
    time.sleep(1)
    c.js(f"location.hash = '#/p/{NAME}'")
    time.sleep(2)
    c.js("document.querySelector('.trees-box') && document.querySelector('.trees-box').scrollIntoView()")
    time.sleep(0.5)
    widths = c.js("(() => { const r = document.querySelector('.trees-box .tree-row'); return r ? [r.scrollWidth, r.clientWidth, Math.round(r.getBoundingClientRect().height)] : null; })()")
    check("on a phone the list fits its width", widths and widths[0] <= widths[1] + 1, widths)
    check("on a phone each action is a 44px target", c.js("[...document.querySelectorAll('.trees-box .tree-acts .retry')].every(b => b.getBoundingClientRect().height >= 44)") is True)
    c.shot("08-phone-project-trees")
    keep = api("POST", "/api/sessions", {"project": NAME, "tasks": [], "isolate": False, "kind": "shell"})["ids"][0]; ids.append(keep)
    meta = STATE / "sessions" / f"{keep}.json"
    data = json.loads(meta.read_text()); data.update(isolate=True, folder=str(dirty), tree={"branch": "hub/dirty-cccc", "base": "main", "start": ""}); meta.write_text(json.dumps(data))
    c.go(f"#/s/{keep}", "!!document.querySelector('.pane-top .tree-chip')")
    time.sleep(1)
    chip = c.js("(() => { const e = document.querySelector('.pane-top .tree-chip'); const r = e.getBoundingClientRect(); return [e.innerText, Math.round(r.right), innerWidth]; })()")
    check("on a phone the chip says one fact and fits", chip and chip[0].strip() == "2 changed" and chip[1] <= chip[2], chip)
    c.shot("09-phone-pane-chip")
    c.click(".pane-top .tree-chip")
    waited(lambda: c.text("dialog.tree-sheet"), 10)
    fits = c.js("(() => { const d = document.querySelector('dialog.tree-sheet'); return d.scrollWidth <= d.clientWidth + 1; })()")
    check("its sheet fits a phone", fits is True)
    c.shot("10-phone-tree-sheet")
    c.key("Escape")
    check("no script errors", not c.errors, c.errors[:5])
except Exception as error:  # a step that couldn't run is a failure, and the rest still cleans up
    check("the run went to its end", False, repr(error))
finally:
    try:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        for sid in ids:
            api("POST", f"/api/sessions/{sid}/dismiss", {})
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, left)
        check("launchd's folder holds what it held before", launchd_jobs() == launchd_before)
print(f"--- failures: {failures}")
sys.exit(1 if failures else 0)
