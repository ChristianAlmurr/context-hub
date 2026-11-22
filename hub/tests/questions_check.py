#!/usr/bin/env python3
"""Every way Claude asks for input, answered from the hub's own page, end to end, in headless Chrome.

Real Claude sessions (Haiku, low effort) in a throwaway project, hub-test-throwaway-<n>, made here and removed at the end:
- AskUserQuestion with three questions, at a desk in the chat view with the keyboard: a single choice by its digit, a
  multiple choice ticked and with words of its own, moving between the questions, the review, and Submit.
- The same on a phone (390 wide, touch): taps only, every target at least 44 px.
- A permission prompt answered from a peek: No, with words for Claude, then Yes.
- A plan to approve on a phone: words for Claude first, then approved.
Each answer is checked against what Claude received, not only against the page.

Runs against a second instance (the six HUB_* variables, see tests/instance.py), at the origin its config gives.
Run: /usr/bin/python3 tests/questions_check.py <folder-for-screenshots>
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE, answer_first_run, launchd_jobs, quiet_alert, remove_project, screen, sweep, tell
from instance import PORT as HUB_PORT

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="hub-questions.")); OUT.mkdir(parents=True, exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))
failures = 0

ASK_DESK = ('Use the AskUserQuestion tool ONCE with exactly these 3 questions: (1) header "Color", question "Pick a color for the new '
            'dashboard theme?", single select, options Red (description "Warm and loud, good for alerts"), Blue (description "Calm and '
            'readable on dark backgrounds"), Green (description "Fresh"). (2) header "Toppings", question "Which toppings?", multiSelect '
            'true, options Cheese (description "Mozzarella"), Ham (description "Smoked"), Olives (description "Black"). (3) header "Size", '
            'question "What size?", options Small (description "25 cm"), Large (description "35 cm"). Then reply with my three answers '
            'exactly as you received them, and nothing else.')
ASK_PHONE = ('Use the AskUserQuestion tool ONCE with exactly these 3 questions: (1) header "Drink", question "What to drink?", options '
             'Tea (description "Green or black"), Coffee (description "Espresso"). (2) header "Snacks", question "Which snacks?", '
             'multiSelect true, options Nuts (description "Salted"), Fruit (description "Seasonal"), Cake (description "Lemon"). '
             '(3) header "Seat", question "Where to sit?", options Window, Aisle. Then reply with my three answers exactly as you '
             'received them, and nothing else.')
PLAN = "Plan how to add a README.md with one line describing this folder. Keep the plan to 3 short bullets, then present it for approval with ExitPlanMode."


def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{str(extra)[:400]}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, WRITE)
    return json.loads(c.getresponse().read() or b"{}")


def said(sid):
    """What Claude has said in this session: the record the chat reads, newest last."""
    record = api("GET", f"/api/sessions/{sid}/record")
    return "\n".join(str(item.get("text", "")) for item in record.get("items", []) if item.get("kind") == "claude")


def waited(test, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        value = test()
        if value:
            return value
        time.sleep(0.3)
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
        """One key, as the keyboard sends it: a digit, Enter or an arrow."""
        codes = {"Enter": (13, "Enter", "\r"), "ArrowLeft": (37, "ArrowLeft", ""), "ArrowRight": (39, "ArrowRight", ""), "ArrowUp": (38, "ArrowUp", ""), "ArrowDown": (40, "ArrowDown", ""), "Escape": (27, "Escape", "")}
        vk, code, text = codes[key] if key in codes else (ord(key), f"Digit{key}", key)
        self.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=code, windowsVirtualKeyCode=vk, text=text)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk)
        time.sleep(0.15)

    def type(self, text):
        self.call("Input.insertText", text=text)
        time.sleep(0.1)

    def tap(self, selector):
        """A finger on the middle of what the selector finds, as a phone sends it."""
        box = self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null; e.scrollIntoView({{block: 'nearest'}}); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
        if not box:
            raise AssertionError(f"nothing to tap at {selector}")
        x, y = box
        self.call("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
        self.call("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
        time.sleep(0.2)


def panel(c, where=".chat-ask"):
    """What the question panel shows, read off the page."""
    return c.js(f"""(() => {{
      const qa = document.querySelector({json.dumps(where)} + ' .qa');
      if (!qa) return null;
      const all = (s) => [...qa.querySelectorAll(s)];
      return {{
        kind: qa.dataset.kind, busy: qa.hasAttribute('aria-busy'),
        question: (qa.querySelector('.qa-q') || {{}}).textContent || '',
        count: (qa.querySelector('.qa-count') || {{}}).textContent || '',
        steps: all('.qa-step').map(s => [s.textContent, s.getAttribute('aria-current') === 'step', !!s.querySelector('.qa-done')]),
        role: (qa.querySelector('.qa-list') || {{}}).getAttribute?.('role') || '',
        options: all('.qa-list > .qa-opt').map(o => ({{ role: o.getAttribute('role'), checked: o.getAttribute('aria-checked'), label: (o.querySelector('.qa-label') || {{}}).textContent || '',
          desc: (o.querySelector('.qa-desc') || {{}}).textContent || '', words: !!o.querySelector('input'), placeholder: (o.querySelector('input') || {{}}).placeholder || '' }})),
        apart: all('.qa-apart button').map(b => b.textContent),
        next: (qa.querySelector('.qa-next') || {{}}).textContent || '',
        review: all('.qa-review dd').map(d => d.textContent),
        detail: (qa.querySelector('.qa-detail') || {{}}).textContent || '',
        amend: (qa.querySelector('.qa-amend input') || {{}}).placeholder || '',
      }};
    }})()""")


def shown(c, test, where=".chat-ask", seconds=60):
    """Wait until the panel shows what `test` looks for, and isn't busy with an answer."""
    return waited(lambda: (lambda p: p if p and not p["busy"] and test(p) else None)(panel(c, where)), seconds)


def small_targets(c, where):
    """Everything to press in the panel that is shorter than a thumb."""
    return c.js(f"[...document.querySelectorAll({json.dumps(where)} + ' .qa button, ' + {json.dumps(where)} + ' .qa input')].filter(e => e.offsetParent && e.getBoundingClientRect().height < 44).map(e => e.className + ':' + Math.round(e.getBoundingClientRect().height))")


sweep()
launchd_before = launchd_jobs()
profile = tempfile.mkdtemp(prefix="hub-chrome.")
chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", f"--remote-debugging-port={PORT}", "--window-size=1440,900", "about:blank"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ids = []
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    task = {"project": NAME, "isolate": False, "model": "haiku", "effort": "low"}
    ids += api("POST", "/api/sessions", {**task, "mode": "manual", "tasks": [""]})["ids"]
    sid = ids[0]
    answer_first_run(sid)
    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.call("Page.navigate", url=CFG["origin"] + "/#/")
    time.sleep(3)
    c.js("localStorage.setItem('deskView', JSON.stringify('chat'))")

    # ── a desk: three questions in the chat view, answered with the keyboard ──
    c.js(f"location.hash = '#/s/{sid}'")
    tell(sid, ASK_DESK)
    first = shown(c, lambda p: p["question"].startswith("Pick a color"), seconds=90)
    check("a question of several shows in the chat, with its steps and where it stands", first and [s[0] for s in first["steps"]] == ["Color", "Toppings", "Size", "Review"] and first["steps"][0][1] and first["count"] == "Question 1 of 3", first)
    if first:
        check("a single choice is a radio group, each label clean with its description apart", first["role"] == "radiogroup" and [o["label"] for o in first["options"][:3]] == ["Red", "Blue", "Green"]
              and first["options"][0]["desc"] == "Warm and loud, good for alerts" and all(o["role"] == "radio" for o in first["options"][:3]), first["options"])
        check("its own answer is a text field, and Chat about this is still offered", first["options"][3]["words"] and first["apart"] == ["Chat about this"], first)
    check("on a desk the panel takes the keyboard when it appears", waited(lambda: c.js("document.activeElement && !!document.activeElement.closest('.qa')"), 5))
    c.shot("desk-1-single")
    c.key("2")
    multi = shown(c, lambda p: p["question"] == "Which toppings?")
    check("a digit picks and moves on to the next question", multi and multi["steps"][0][2] and multi["steps"][1][1] and multi["count"] == "Question 2 of 3", multi)
    if multi:
        check("a multiple choice is a group of checkboxes, with its own answer and Next", multi["role"] == "group" and [o["role"] for o in multi["options"][:3]] == ["checkbox"] * 3 and multi["options"][3]["words"] and multi["next"].startswith("Next"), multi)
    c.js("document.querySelector('.chat-ask .qa-opt[role=checkbox]').focus()")
    c.key("1"); c.key("3")
    ticked = panel(c)
    check("digits tick and untick here, before anything is sent", ticked and [o["checked"] for o in ticked["options"][:3]] == ["true", "false", "true"], ticked and ticked["options"])
    c.js("document.querySelector('.chat-ask .qa-words input').focus()")
    c.type("Pineapple")
    c.shot("desk-2-multi")
    c.key("Enter")
    size = shown(c, lambda p: p["question"] == "What size?")
    check("Enter in its own answer sends the ticks and the words, and moves on", size and size["steps"][1][2] and size["count"] == "Question 3 of 3", size)
    c.js("document.querySelector('.chat-ask .qa-step[data-qa=\"s1\"]').click()")
    back = shown(c, lambda p: p["question"] == "Which toppings?")
    check("a step opens that question again, with what the terminal holds for it", back and [o["checked"] for o in back["options"][:4]] == ["true", "false", "true", None] and c.js("document.querySelector('.chat-ask .qa-words input').value") == "Pineapple", back and back["options"])
    c.js("document.querySelector('.chat-ask .qa-opt[role=checkbox]').focus()")
    c.key("ArrowRight")
    again = shown(c, lambda p: p["question"] == "What size?")
    check("→ opens the next question", bool(again))
    c.js("document.querySelector('.chat-ask .qa-words input').focus()")
    c.type("Medium, cut in 8")
    c.key("Enter")
    review = shown(c, lambda p: p["kind"] == "review")
    check("the last answer leads to the review, every answer as Claude has it", review and review["review"] == ["Blue", "Cheese, Olives, Pineapple", "Medium, cut in 8"] and review["steps"][3][1], review)
    c.shot("desk-3-review")
    c.key("1")
    gone = waited(lambda: not c.js("!!document.querySelector('.chat-ask .qa')"), 20)
    check("Submit answers sends them, and the choice leaves the page", bool(gone))
    told = waited(lambda: (lambda t: t if "Pineapple" in t and "Medium, cut in 8" in t and "Blue" in t else None)(said(sid)), 90)
    check("Claude received all three answers, the typed ones word for word", bool(told), said(sid)[-600:])
    c.shot("desk-4-answered")

    # ── a phone: the same kind of question, with taps ──
    waited(lambda: api("GET", f"/api/sessions/{sid}/peek").get("state") == "finished", 60)
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    c.js("localStorage.setItem('shared', 'false'); localStorage.removeItem('panelBy')")  # the desk's side panel stays at the desk
    c.call("Page.reload")
    time.sleep(4)
    tell(sid, ASK_PHONE)
    drink = shown(c, lambda p: p["question"] == "What to drink?", seconds=90)
    check("a phone opens the question in the chat", bool(drink), drink)
    check("every target in the panel is at least 44 px on a phone", drink and not small_targets(c, ".chat-ask"), small_targets(c, ".chat-ask"))
    fits = c.js("[...document.querySelectorAll('.chat-ask .qa *')].every(e => e.getBoundingClientRect().right <= innerWidth + 1) && document.documentElement.scrollWidth <= innerWidth")
    check("the panel fits a phone's width", fits)
    c.shot("phone-1-single")
    c.tap(".chat-ask .qa-opt[role=radio]")
    snacks = shown(c, lambda p: p["question"] == "Which snacks?")
    check("a tap picks and moves on", bool(snacks), snacks)
    c.tap(".chat-ask .qa-opt[data-qa=o1]")
    c.tap(".chat-ask .qa-opt[data-qa=o3]")
    c.tap(".chat-ask .qa-words input")
    c.type("Extra napkins")
    c.shot("phone-2-multi")
    c.tap(".chat-ask .qa-next")
    seat = shown(c, lambda p: p["question"] == "Where to sit?")
    check("Next sends the ticks and the words", bool(seat), seat)
    c.tap(".chat-ask .qa-opt[data-qa=o2]")
    review = shown(c, lambda p: p["kind"] == "review")
    check("the review lists the answers on a phone", review and review["review"] == ["Tea", "Nuts, Cake, Extra napkins", "Aisle"], review)
    c.shot("phone-3-review")
    c.tap(".chat-ask .qa-actions .btn.primary")
    told = waited(lambda: (lambda t: t if "Extra napkins" in t and "Aisle" in t else None)(said(sid)), 90)
    check("Claude received the phone's answers", bool(told), said(sid)[-600:])
    c.shot("phone-4-answered")

    # ── a permission prompt, answered from a peek at a desk: No with words, then Yes ──
    waited(lambda: api("GET", f"/api/sessions/{sid}/peek").get("state") == "finished", 60)
    c.call("Emulation.setTouchEmulationEnabled", enabled=False)
    c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
    c.js("location.hash = '#/'")
    c.call("Page.reload")
    time.sleep(4)
    tell(sid, "Run this bash command: ls -la / | head -2 . Then stop.")
    waited(lambda: (api("GET", f"/api/sessions/{sid}/peek").get("dialog") or {}).get("kind") == "permission", 90)
    time.sleep(3.5)  # the next poll has the session as needing you
    c.js(f"window.hubPeek('{sid}')")
    asked = shown(c, lambda p: p["kind"] == "permission", where=".peek-pop")
    check("a permission prompt shows in the peek with what it would run, and a field for words", asked and "ls -la /" in asked["detail"] and asked["amend"] == "Or tell Claude what to do instead", asked)
    c.shot("desk-5-peek-permission")
    c.js("document.querySelector('.peek-pop .qa-amend input').focus()")
    c.type("Use ls -1 / | head -2 instead")
    c.key("Enter")
    retold = waited(lambda: (lambda d: d if d and d.get("kind") == "permission" and "ls -1" in d.get("detail", "") else None)((api("GET", f"/api/sessions/{sid}/peek").get("dialog"))), 90)
    check("No with words reaches Claude, and it asks again for what it was told", bool(retold), screen(sid)[-800:])
    if retold:
        shown(c, lambda p: "ls -1" in p["detail"], where=".peek-pop", seconds=20)
        c.js("document.querySelector('.peek-pop .qa-opt').focus()")
        c.key("1")
        done = waited(lambda: api("GET", f"/api/sessions/{sid}/peek").get("state") == "finished", 90)
        check("Yes by its digit lets it run", bool(done))
    c.js("document.activeElement && document.activeElement.blur(); document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")

    # ── a plan to approve, on a phone: words first, then approved ──
    ids += api("POST", "/api/sessions", {**task, "mode": "plan", "tasks": [""]})["ids"]
    plan = ids[-1]
    answer_first_run(plan)
    c.call("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
    c.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
    c.js(f"localStorage.setItem('shared', 'false'); localStorage.removeItem('panelBy'); location.hash = '#/s/{plan}'")
    c.call("Page.reload")
    time.sleep(4)
    tell(plan, PLAN)
    # How long the model takes to plan is its own (it may read the folder first), so the plan is waited for where the
    # hub reads it, from the session's screen; the page then has a few seconds to show it, which is what is checked here.
    planned = waited(lambda: (api("GET", f"/api/sessions/{plan}/peek").get("dialog") or {}).get("kind") == "plan", 240)
    check("Claude presents a plan to approve", bool(planned), screen(plan)[-800:])
    asked = shown(c, lambda p: p["kind"] == "plan", seconds=30) if planned else None
    check("a plan to approve shows its plan, its options and a field for what to change", asked and "README" in asked["detail"] and any(o["words"] and o["placeholder"] == "Tell Claude what to change" for o in asked["options"]), asked or screen(plan)[-800:])
    c.shot("phone-5-plan")
    replanned = None
    if asked:
        before = asked["detail"]
        c.tap(".chat-ask .qa-words input")
        c.type("Make it a single sentence with no title line")
        c.tap(".chat-ask .qa-words .qa-go")
        replanned = shown(c, lambda p: p["kind"] == "plan" and p["detail"] != before, seconds=240)
        check("words for the plan reach Claude, and it plans again", bool(replanned), screen(plan)[-800:])
    if replanned:
        c.tap(".chat-ask .qa-opt[data-qa=o2]")
        nextq = shown(c, lambda p: p["kind"] == "permission", seconds=120)
        check("approving it moves Claude on to its first edit, asked as a permission", bool(nextq), nextq)
        c.shot("phone-6-permission")
        if nextq:
            c.tap(".chat-ask .qa-opt[data-qa=o1]")
            check("Yes is sent with a tap, and the file is written", bool(waited(lambda: (HOME / "projects" / NAME / "README.md").exists(), 60)))
    check("no script errors", not c.errors, c.errors[:5])
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
