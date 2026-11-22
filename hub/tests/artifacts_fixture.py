"""A made-up session that made one of everything, for the artifact checks: its files in a folder the test gives, its
record in the instance's state folder, and its transcript written line by line in Claude Code's own shapes.
Nothing here is anyone's: every name, page and address is invented, and the links are on example hosts.
"""
import json, struct, time, zlib
from datetime import datetime, timezone
from pathlib import Path

import hub_data as hub

now = datetime.now(timezone.utc)


def stamp(seconds_ago=0):
    return datetime.fromtimestamp(now.timestamp() - seconds_ago, timezone.utc).isoformat().replace("+00:00", "Z")


def png(w, h, rgb=(47, 98, 245)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 400]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
       b"4 0 obj<</Length 44>>stream\nBT /F1 24 Tf 50 300 Td (Hello PDF) Tj ET\nendstream endobj\n"
       b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")

# The page an HTML artifact is: it shows a picture beside it, then tries everything a page must never manage from the
# hub's viewer, and tells the page that holds it what happened (postMessage is the one way out of its sandbox).
REPORT = """<!doctype html>
<html><head><meta charset="utf-8"><title>Quarterly report</title>
<style>body{font:15px system-ui;margin:24px;color:#223} h1{font-size:22px} .bar{height:14px;background:#2f62f5;margin:6px 0}</style></head>
<body><h1>Quarterly report</h1><p id="p">Made by a test session.</p>
<img id="pic" src="img/chart.png" alt="chart" width="64" height="32">
<div class="bar" style="width:60%"></div><div class="bar" style="width:35%"></div>
<script>
(async () => {
  const out = { origin: String(self.origin), scripts: true };
  try { out.cookie = document.cookie; } catch (e) { out.cookie = "blocked"; }
  try { out.parent = String(parent.document.title); } catch (e) { out.parent = "blocked"; }
  try { out.storage = typeof localStorage.getItem("x"); } catch (e) { out.storage = "blocked"; }
  try { const r = await fetch("/api/state"); out.state = r.status; } catch (e) { out.state = "blocked"; }
  try { const r = await fetch("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); out.write = r.status; } catch (e) { out.write = "blocked"; }
  out.pic = await new Promise((done) => { const img = document.getElementById("pic"); if (img.complete) done(img.naturalWidth > 0); else { img.onload = () => done(true); img.onerror = () => done(false); } });
  parent.postMessage({ artifactProbe: out }, "*");
})();
</script></body></html>
"""
NOTES_V1 = "# Release notes\n\nA first draft.\n"
NOTES_V2 = """# Release notes

The **second** version, with a list:

- Faster start
- A table below

| Part | State |
|---|---|
| Server | done |
| Viewer | done |

```python
print("hello")
```
"""
CSV = "city,visits,share\nLisbon,120,0.4\nOslo,95,0.31\nKyoto,88,0.29\n"
JSON = {"name": "demo", "items": [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": []}], "ok": True, "nested": {"deep": {"deeper": 3}}}
CODE = "def greet(name):\n    # say hello\n    return f\"Hello, {name}!\"\n\n\nif __name__ == \"__main__\":\n    print(greet(\"world\"))\n"
SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" fill="#2dd4a0"/>
<script>parent.postMessage({ svgRan: true }, "*")</script></svg>
"""


def use(id_, name, given):
    return {"type": "tool_use", "id": id_, "name": name, "input": given}


def result(id_, content):
    return {"type": "tool_result", "tool_use_id": id_, "content": content}


def say(seconds_ago, blocks, role="assistant", **extra):
    return {"type": role, "timestamp": stamp(seconds_ago), "message": {"role": role, "content": blocks}, **extra}


def make(folder: Path, sid: str, project: str, title: str, elsewhere: Path):
    """Writes the files and the record. `elsewhere` is a folder outside the session's own, for a file it wrote there."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "img").mkdir(exist_ok=True)
    (folder / "report.html").write_text(REPORT)
    (folder / "img" / "chart.png").write_bytes(png(64, 32))
    (folder / "notes.md").write_text(NOTES_V2)
    (folder / "data.csv").write_text(CSV)
    (folder / "data.json").write_text(json.dumps(JSON, indent=2))
    (folder / "greet.py").write_text(CODE)
    (folder / "logo.svg").write_text(SVG)
    (folder / "brief.pdf").write_bytes(PDF)
    (folder / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    (folder / "voice.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVE" + b"\x00" * 32)
    (folder / ".env").write_text("TOKEN=never-shown\n")
    (folder / "sub.md").write_text("# From a subagent\n")
    (folder / "untouched.html").write_text("<p>never named by the session</p>")
    elsewhere.mkdir(parents=True, exist_ok=True)
    (elsewhere / "outside.md").write_text("# Written outside the project\n")
    (elsewhere / "never.md").write_text("# Never named\n")
    meta = {"id": sid, "project": project, "repo": str(folder), "folder": str(folder), "title": title, "kind": "claude", "created": time.time() - 600}
    hub.META.mkdir(parents=True, exist_ok=True)
    (hub.META / f"{sid}.json").write_text(json.dumps(meta))
    record = hub.RECORDS / sid
    (record / "transcript" / "subagents").mkdir(parents=True, exist_ok=True)
    lines = [
        say(300, "Make a small report, notes and a chart.", role="user"),
        say(290, [use("w1", "Write", {"file_path": str(folder / "notes.md"), "content": NOTES_V1})]),
        say(280, [use("w2", "Write", {"file_path": str(folder / "report.html"), "content": REPORT})]),
        say(270, [use("b1", "Bash", {"command": f"cd {folder} && python3 plot.py -o img/chart.png && echo done"})]),
        say(265, [use("b2", "Bash", {"command": "python3 export.py > data.csv"})]),
        say(260, [use("w3", "Write", {"file_path": str(folder / "data.json"), "content": "{}"})]),
        say(255, [use("w4", "Write", {"file_path": str(folder / "greet.py"), "content": CODE})]),
        say(250, [use("w5", "Write", {"file_path": str(folder / "logo.svg"), "content": SVG})]),
        say(245, [use("w6", "Write", {"file_path": str(folder / ".env"), "content": "TOKEN=x"})]),
        say(240, [use("w7", "Write", {"file_path": str(folder / "gone.md"), "content": "# deleted later"})]),
        say(235, [use("w8", "Write", {"file_path": str(elsewhere / "outside.md"), "content": "# outside"})]),
        say(230, [use("u1", "SendUserFile", {"files": [str(folder / "brief.pdf")]})]),
        say(225, [use("d1", "mcp__hosting__deploy", {"project": "demo"})]),
        say(224, [result("d1", [{"type": "text", "text": "Deployed to https://demo-build.example.org/ in 12s"}])], role="user"),
        say(220, [use("a1", "Agent", {"description": "write a note", "prompt": "write sub.md"})]),
        say(200, [use("e1", "Edit", {"file_path": str(folder / "notes.md"), "old_string": "A first draft.", "new_string": "The second version"})]),
        say(190, [{"type": "text", "text": "Done. The page is report.html; the clip is ./clip.mp4 and the recording ./voice.wav.\n"
                                           "It's live at https://demo-report.vercel.app/ and as https://claude.ai/public/artifacts/0000-demo .\n"
                                           "See https://example.com/docs for the background, and ignore ./untouched.py."}]),
    ]
    (record / "transcript.jsonl").write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    sub = record / "transcript" / "subagents"
    (sub / "agent-abc123def.jsonl").write_text(json.dumps(
        {"type": "assistant", "isSidechain": True, "timestamp": stamp(215), "message": {"role": "assistant", "content": [use("s1", "Write", {"file_path": str(folder / "sub.md"), "content": "# sub"})]}}) + "\n")
    return meta


def remove(sid: str):
    import shutil
    for path in (hub.META / f"{sid}.json",):
        if path.exists():
            path.unlink()
    shutil.rmtree(hub.RECORDS / sid, ignore_errors=True)
