#!/usr/bin/env python3
"""What a chat shows besides its words, in the real page in headless Chrome, at a desk (1440px) and on a phone (390px, touch).

Run: /usr/bin/python3 tests/media_browser_check.py <folder-for-screenshots>
Runs against a second instance (the six HUB_* variables, see tests/instance.py). Makes a throwaway project and starts
one short real Claude session in it (haiku) that makes a picture, a video, a recording and a PDF with ffmpeg and sips,
reads the picture and names every file in its reply. A second, made-up session beside it holds what a short session
can't be relied on to do: a pasted picture, a tool's screenshot, a subagent's, a file sent with SendUserFile and a
link to a picture. Everything is removed at the end.
"""
import base64, http.client, json, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request, zlib
from datetime import datetime, timezone
from pathlib import Path

from instance import CFG, HOME, NAME, WRITE as HEAD, answer_first_run, quiet_alert, remove_project, sweep, tell
from instance import PORT as HUB_PORT
import hub_data as hub

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
FFMPEG = shutil.which("ffmpeg")
failures = 0
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = int(os.environ.get("HUB_CDP_PORT", "9347"))  # Chrome's debugging port: give each test run beside another its own


def api(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", HUB_PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, HEAD)
    return json.loads(c.getresponse().read())


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
        self.buffer = data.split(b"\r\n\r\n", 1)[1]
        self.n = 0
        self.errors = []

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
            if message.get("method") == "Log.entryAdded" and message["params"]["entry"]["level"] == "error":
                self.errors.append(message["params"]["entry"]["text"][:200])

    def js(self, expression):
        return self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def shot(self, path):
        Path(path).write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))



def check(label, ok, extra=""):
    global failures
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{extra}]" if not ok else ""), flush=True)
    failures += 0 if ok else 1


def png(w, h, rgb=(47, 98, 245)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


TASK = """Do exactly this, using the Bash tool, in the current folder, then reply. Don't ask questions.
1. mkdir -p media
2. ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc=size=480x300 -frames:v 1 media/frame.png
3. ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc=size=320x240:rate=10 -t 2 -c:v libx264 -pix_fmt yuv420p media/clip.mp4
4. ffmpeg -hide_banner -loglevel error -y -f lavfi -i sine=frequency=440:duration=1 media/tone.wav
5. sips -s format pdf media/frame.png --out media/page.pdf
Then use the Read tool on media/frame.png, and reply with one sentence describing it, followed by these four lines exactly as written, each in backticks:
`{folder}/media/frame.png`
`{folder}/media/clip.mp4`
`media/tone.wav`
`media/page.pdf`
End your reply with the word FINISHED."""

sweep()
chrome = None
profile = tempfile.mkdtemp(prefix="hub-chrome.")
fake_sid, scratch = None, None
ids = []
try:
    made = api("POST", "/api/projects", {"name": NAME})
    check("a throwaway project is created", made.get("name") == NAME, str(made))
    quiet_alert(NAME)
    repo = HOME / "projects" / NAME
    if not FFMPEG:
        print("SKIP  ffmpeg isn't installed: the real session makes no video or recording", flush=True)
    task = {"project": NAME, "isolate": False, "mode": "bypassPermissions", "model": "haiku", "effort": "low"}
    ids += api("POST", "/api/sessions", {**task, "tasks": ["Reply with the single word ready"]})["ids"]
    sid = ids[0]
    answer_first_run(sid)
    # wait for the first answer, then give it the real task
    end = time.time() + 120
    while time.time() < end and not any(i["kind"] == "claude" for i in api("GET", f"/api/sessions/{sid}/record").get("items", [])):
        time.sleep(2)
    tell(sid, TASK.replace("{folder}", str(repo)))
    end, rec = time.time() + 300, {}
    while time.time() < end:
        rec = api("GET", f"/api/sessions/{sid}/record")
        if any(i["kind"] == "claude" and "FINISHED" in i.get("text", "") for i in rec.get("items", [])):
            break
        time.sleep(3)
    shown = [m for i in rec.get("items", []) for m in i.get("media", [])]
    kinds = sorted({m["kind"] for m in shown})
    print("real session media:", json.dumps([{k: m.get(k) for k in ("kind", "name", "w", "h")} for m in shown]), flush=True)
    check("the real session's record carries the picture, video, recording and PDF", {"image", "video", "audio", "pdf"} <= set(kinds) if FFMPEG else {"image", "pdf"} <= set(kinds), kinds)

    # The made-up session: what a short real one can't be relied on to show.
    fake_sid = os.urandom(4).hex()
    scratch = Path(tempfile.mkdtemp(prefix="media-browser.", dir=f"/private/tmp/claude-{os.getuid()}"))
    (scratch / "sent.png").write_bytes(png(600, 400, (45, 212, 160)))
    (scratch / "wide shot.png").write_bytes(png(1200, 300, (255, 92, 138)))
    (scratch / "tall.png").write_bytes(png(300, 900, (242, 193, 78)))
    for n, rgb in enumerate(((143, 176, 255), (86, 199, 245), (200, 155, 255))):
        (scratch / f"grid{n}.png").write_bytes(png(400, 300, rgb))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    img = lambda w, h, rgb: {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png(w, h, rgb)).decode()}}
    use = lambda i, name, given: {"type": "tool_use", "id": i, "name": name, "input": given}
    res = lambda i, content: {"type": "tool_result", "tool_use_id": i, "content": content}
    lines = [
        {"type": "user", "timestamp": now, "message": {"role": "user", "content": [{"type": "text", "text": "Here's the bug [Image #1]"}, img(800, 500, (255, 92, 138))]}},
        {"type": "assistant", "timestamp": now, "message": {"role": "assistant", "content": [use("s1", "mcp__claude-in-chrome__computer", {"action": "screenshot"})]}},
        {"type": "user", "timestamp": now, "message": {"role": "user", "content": [res("s1", [img(1280, 800, (17, 24, 43))])]}},
        {"type": "assistant", "timestamp": now, "message": {"role": "assistant", "content": [use("a1", "Agent", {"description": "check"})]}},
        {"type": "user", "timestamp": now, "toolUseResult": {"agentId": "abcdef123"}, "message": {"role": "user", "content": [res("a1", [{"type": "text", "text": "done"}])]}},
        {"type": "assistant", "timestamp": now, "message": {"role": "assistant", "content": [use("u1", "SendUserFile", {"files": [str(scratch / "sent.png")]})]}},
        {"type": "assistant", "timestamp": now, "message": {"role": "assistant", "content": [{"type": "text", "text":
            f"Here they are: `{scratch}/wide shot.png` and ![tall]({scratch}/tall.png).\n\nThree more: {scratch}/grid0.png {scratch}/grid1.png {scratch}/grid2.png\n\n"
            "And a picture on the web: https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"}]}},
    ]
    (hub.UPLOADS / fake_sid).mkdir(parents=True, exist_ok=True)
    (hub.UPLOADS / fake_sid / "ab12-photo.png").write_bytes(png(500, 700, (45, 98, 245)))
    lines.append({"type": "user", "timestamp": now, "message": {"role": "user", "content": f"One more from my phone {hub.UPLOADS / fake_sid / 'ab12-photo.png'}"}})
    meta = {"id": fake_sid, "project": NAME, "repo": str(repo), "folder": str(repo), "title": "Media made up", "kind": "claude", "created": time.time()}
    (hub.META / f"{fake_sid}.json").write_text(json.dumps(meta))
    (hub.RECORDS / fake_sid / "transcript" / "subagents").mkdir(parents=True)
    (hub.RECORDS / fake_sid / "transcript.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    sub = hub.RECORDS / fake_sid / "transcript" / "subagents"
    (sub / "agent-abcdef123.meta.json").write_text(json.dumps({"toolUseId": "a1"}))
    (sub / "agent-abcdef123.jsonl").write_text(json.dumps({"type": "user", "isSidechain": True, "timestamp": now, "message": {"role": "user", "content": [res("x", [img(640, 360, (169, 112, 230))])]}}) + "\n")

    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--autoplay-policy=no-user-gesture-required", f"--user-data-dir={profile}", f"--remote-debugging-port={CDP_PORT}", "--window-size=1440,900", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json")) if t["type"] == "page")
            break
        except (OSError, StopIteration):
            time.sleep(0.25)
    c = CDP(page["webSocketDebuggerUrl"])
    c.call("Page.enable"); c.call("Runtime.enable"); c.call("Log.enable"); c.call("Network.enable")
    c.call("Network.setExtraHTTPHeaders", headers={"Tailscale-User-Login": CFG["login"]})

    def settle(seconds=20):
        """Bring every picture, video and recording near the screen once, as reading the chat would, so the lazy ones load."""
        count = c.js("document.querySelectorAll('.turn-media img, .turn-media video, .turn-media audio').length") or 0
        for n in range(count):
            c.js(f"document.querySelectorAll('.turn-media img, .turn-media video, .turn-media audio')[{n}].scrollIntoView({{ block: 'center' }})")
            time.sleep(0.25)
        end = time.time() + seconds
        while time.time() < end:
            if c.js("[...document.querySelectorAll('.turn-media img')].every(i => i.complete && i.naturalWidth > 0) && [...document.querySelectorAll('.turn-media video, .turn-media audio')].every(v => v.readyState >= 1)"):
                break
            time.sleep(0.4)
        c.js("(() => { const log = document.querySelector('.chat-log') || document.querySelector('.pane .record'); if (log) log.scrollTop = log.scrollHeight; })()")
        time.sleep(0.5)

    def facts():
        return c.js("""(() => {
          const imgs = [...document.querySelectorAll('.turn-media .m-pic img')].map(i => ({ alt: i.alt, nw: i.naturalWidth, w: Math.round(i.getBoundingClientRect().width), h: Math.round(i.getBoundingClientRect().height) }));
          const vids = [...document.querySelectorAll('.turn-media video')].map(v => ({ ready: v.readyState, paused: v.paused, controls: v.controls, w: Math.round(v.getBoundingClientRect().width), h: Math.round(v.getBoundingClientRect().height) }));
          const auds = [...document.querySelectorAll('.turn-media audio')].map(a => ({ ready: a.readyState, controls: a.controls }));
          const pdfs = [...document.querySelectorAll('.turn-media .m-pdf')].map(b => ({ text: b.innerText, page: (b.querySelector('.m-page img') || {}).naturalWidth || 0 }));
          const links = [...document.querySelectorAll('.turn-media .m-link')].map(a => ({ cls: a.className, pic: (a.querySelector('img') || {}).naturalWidth || 0 }));
          const page = document.scrollingElement, log = document.querySelector('.chat-log, .record');
          return { imgs, vids, auds, pdfs, links, sideways: Math.max(page.scrollWidth - page.clientWidth, log ? log.scrollWidth - log.clientWidth : 0) };
        })()""")

    for label, width, height, mobile in (("desk", 1440, 900, False), ("phone", 390, 844, True)):
        c.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2 if mobile else 1, mobile=mobile)
        c.call("Emulation.setTouchEmulationEnabled", enabled=mobile, maxTouchPoints=5 if mobile else 0)
        c.call("Page.navigate", url=CFG["origin"] + "/#/")
        time.sleep(3)
        c.js("localStorage.setItem('deskView', JSON.stringify('chat')); localStorage.setItem('phoneView', JSON.stringify('chat')); localStorage.setItem('panelBy', '{}'); localStorage.setItem('shared', JSON.stringify(!" + ("true" if mobile else "false") + "))")
        c.js(f"location.hash = '#/s/{sid}'")
        time.sleep(4)
        settle()
        f = facts()
        print(f"{label} real:", json.dumps(f), flush=True)
        check(f"{label}: the real session's pictures load inline", f["imgs"] and all(i["nw"] > 0 for i in f["imgs"]), f["imgs"])
        if FFMPEG:
            check(f"{label}: the video loads inline, with controls, not playing", f["vids"] and all(v["ready"] >= 1 and v["controls"] and v["paused"] for v in f["vids"]), f["vids"])
            check(f"{label}: the recording loads inline, with controls", f["auds"] and all(a["ready"] >= 1 and a["controls"] for a in f["auds"]), f["auds"])
        check(f"{label}: the PDF shows its first page", f["pdfs"] and all(p["page"] > 0 for p in f["pdfs"]), f["pdfs"])
        check(f"{label}: nothing scrolls sideways", f["sideways"] <= 1, f["sideways"])
        c.shot(OUT / f"{label}-real.png")
        # the made-up session, read as a record (it isn't running)
        c.js(f"location.hash = '#/s/{fake_sid}'")
        time.sleep(4)
        settle()
        f = facts()
        print(f"{label} made-up:", json.dumps(f), flush=True)
        alts = [i["alt"] for i in f["imgs"]]
        check(f"{label}: every made-up picture loads inline", len(f["imgs"]) >= 10 and all(i["nw"] > 0 for i in f["imgs"]), f["imgs"])
        check(f"{label}: the pasted picture, the screenshots and the sent file are each there", alts.count("Screenshot") == 2 and "Pasted image" in alts and "sent.png" in alts and "wide shot.png" in alts and "tall.png" in alts, alts)
        one = next((i for i in f["imgs"] if i["alt"] == "Pasted image"), {})
        check(f"{label}: a picture sent through the hub shows like a pasted one, under its own name", c.js("(() => { const i = document.querySelector('.turn.you .m-pic img[alt=\"photo.png\"]'); return !!i && i.naturalWidth > 0 && !document.querySelector('.you-shot'); })()"))
        check(f"{label}: a markdown picture of a session file is a button with its label", c.js("[...document.querySelectorAll('button.in-file code')].some(c => c.textContent === 'tall')"))
        check(f"{label}: a picture alone keeps its shape", one and abs(one["w"] / max(1, one["h"]) - 1.6) < 0.05, one)
        check(f"{label}: nothing scrolls sideways", f["sideways"] <= 1, f["sideways"])
        c.shot(OUT / f"{label}-made-up.png")
        c.js("document.querySelector('.turn-media .m-pic').scrollIntoView({ block: 'center' })")
        time.sleep(0.5)
        c.shot(OUT / f"{label}-made-up-top.png")
        c.js("document.querySelector('.turn-media .m-pic').click()")
        time.sleep(1.5)
        check(f"{label}: a tap opens the viewer on that picture", c.js("!!document.querySelector('dialog.viewer[open] .v-img') && document.querySelector('dialog.viewer[open] .v-img').naturalWidth > 0"))
        c.shot(OUT / f"{label}-viewer.png")
        c.js("document.querySelector('dialog.viewer[open]').close()")
        time.sleep(0.5)
    check("no script errors or policy violations", not c.errors, str(c.errors[:5]))
finally:
    try:
        if chrome:
            chrome.terminate()
            chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)
        if fake_sid:
            shutil.rmtree(hub.RECORDS / fake_sid, ignore_errors=True)
            shutil.rmtree(hub.UPLOADS / fake_sid, ignore_errors=True)
            (hub.META / f"{fake_sid}.json").unlink(missing_ok=True)
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
        for one in ids:
            try:
                api("POST", f"/api/sessions/{one}/dismiss", {})
            except Exception:
                pass
    finally:
        left = remove_project(NAME)
        check("the throwaway project is gone", not left, str(left))
print(f"\n{'All passed' if not failures else f'{failures} failed'}")
sys.exit(1 if failures else 0)
