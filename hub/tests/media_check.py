#!/usr/bin/env python3
"""Offline checks of what a chat shows besides its words: every way a picture, video, recording or PDF reaches a
conversation lands in `media` on the turn where it was shared, and nothing the hub never serves does.

No Claude session and no server: a made-up session (its record in the instance's state folder, its files in a
temporary folder in the Claude scratch space) and a transcript written line by line in Claude Code's own shapes.
Run: /usr/bin/python3 tests/media_check.py (with the six HUB_* variables of a second instance, as for the other tests)
"""
import base64, json, os, shutil, struct, sys, tempfile, time, zlib
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hub_data as hub
import hub_preview as preview

fails = 0


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{extra}]"), flush=True)
    fails += 0 if ok else 1


def png(w, h):
    raw = b"".join(b"\x00" + bytes([200, 80, 40]) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


PDF = (b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 400]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
       b"4 0 obj<</Length 44>>stream\nBT /F1 24 Tf 50 300 Td (Hello PDF) Tj ET\nendstream endobj\n"
       b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
now = datetime.now(timezone.utc)
stamp = lambda seconds_ago=0: datetime.fromtimestamp(now.timestamp() - seconds_ago, timezone.utc).isoformat().replace("+00:00", "Z")
b64 = lambda data: base64.b64encode(data).decode()
image_block = lambda w, h: {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64(png(w, h))}}

folder = Path(tempfile.mkdtemp(prefix="media-check.", dir=f"/private/tmp/claude-{os.getuid()}"))
outside = Path(tempfile.mkdtemp(prefix="media-check-outside.", dir="/private/tmp"))
sid = os.urandom(4).hex()
hub.still_running = lambda _folder: []  # the record asks what still runs in the folder; nothing does here
try:
    (folder / "shot.png").write_bytes(png(40, 30))
    (folder / "My Shot 1.png").write_bytes(png(30, 60))
    (folder / "bare.png").write_bytes(png(10, 10))
    (folder / "sent.png").write_bytes(png(12, 12))
    (folder / "sub.png").write_bytes(png(14, 14))
    (folder / "made.png").write_bytes(png(16, 16))
    (folder / "old.png").write_bytes(png(16, 16))
    os.utime(folder / "old.png", (now.timestamp() - 86400, now.timestamp() - 86400))
    (folder / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    (folder / "voice.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVE")
    (folder / "doc.pdf").write_bytes(PDF)
    (folder / ".git").mkdir()
    (folder / ".git" / "secret.png").write_bytes(png(8, 8))
    (outside / "far.png").write_bytes(png(20, 20))

    meta = {"id": sid, "project": "hub-test-media", "repo": str(folder), "folder": str(folder), "title": "Media check", "kind": "claude", "created": time.time()}
    hub.META.mkdir(parents=True, exist_ok=True)
    (hub.META / f"{sid}.json").write_text(json.dumps(meta))
    record = hub.RECORDS / sid
    (record / "transcript" / "subagents").mkdir(parents=True, exist_ok=True)

    def use(id_, name, given):
        return {"type": "tool_use", "id": id_, "name": name, "input": given}

    def result(id_, content, **extra):
        return {"type": "tool_result", "tool_use_id": id_, "content": content, **extra}

    lines = [
        # 0: you paste a picture with a few words
        {"type": "user", "timestamp": stamp(60), "message": {"role": "user", "content": [{"type": "text", "text": "look at this [Image #1]"}, image_block(64, 48)]}},
        # 1: a picture pasted alone
        {"type": "user", "timestamp": stamp(59), "message": {"role": "user", "content": [image_block(20, 10)]}},
        # 2-3: Claude reads a picture in the folder: the file is shown, its pixels in the result are not shown twice
        {"type": "assistant", "timestamp": stamp(58), "message": {"role": "assistant", "content": [use("r1", "Read", {"file_path": str(folder / "shot.png")})]}},
        {"type": "user", "timestamp": stamp(58), "message": {"role": "user", "content": [result("r1", [image_block(40, 30)])]}},
        # 4: and a PDF
        {"type": "assistant", "timestamp": stamp(57), "message": {"role": "assistant", "content": [use("r2", "Read", {"file_path": str(folder / "doc.pdf")})]}},
        # 5-6: a screenshot an MCP tool returns
        {"type": "assistant", "timestamp": stamp(56), "message": {"role": "assistant", "content": [use("s1", "mcp__claude-in-chrome__computer", {"action": "screenshot"})]}},
        {"type": "user", "timestamp": stamp(56), "message": {"role": "user", "content": [result("s1", [{"type": "text", "text": "ok"}, image_block(80, 50)])]}},
        # 7-8: a Read of a picture outside the session's folders: its pixels are shown, under the file's name
        {"type": "assistant", "timestamp": stamp(55), "message": {"role": "assistant", "content": [use("r3", "Read", {"file_path": str(outside / "far.png")})]}},
        {"type": "user", "timestamp": stamp(55), "message": {"role": "user", "content": [result("r3", [image_block(20, 20)])]}},
        # 9: SendUserFile
        {"type": "assistant", "timestamp": stamp(54), "message": {"role": "assistant", "content": [use("u1", "SendUserFile", {"files": [str(folder / "sent.png"), str(folder / ".git" / "secret.png")], "caption": "here"})]}},
        # 10: a command that makes a picture from an older one
        {"type": "assistant", "timestamp": stamp(30), "message": {"role": "assistant", "content": [use("b1", "Bash", {"command": f"sips -s format png old.png --out {folder / 'made.png'}"})]}},
        # 11-12: a subagent, whose own steps are in its file beside the transcript
        {"type": "assistant", "timestamp": stamp(20), "message": {"role": "assistant", "content": [use("a1", "Agent", {"description": "draw", "prompt": "draw"})]}},
        {"type": "user", "timestamp": stamp(10), "toolUseResult": {"agentId": "abc123def", "status": "completed"}, "message": {"role": "user", "content": [result("a1", [{"type": "text", "text": "drew it"}])]}},
        # 13: Claude's reply names files every way it does
        {"type": "assistant", "timestamp": stamp(5), "message": {"role": "assistant", "content": [{"type": "text", "text":
            "Done. The tall one is `My Shot 1.png`, the clip is clip.mp4 and the recording ./voice.wav.\n"
            f"![chart](bare.png) and again as file://{folder}/My%20Shot%201.png. Not this: .git/secret.png nor {outside}/far.png.\n"
            "Also https://example.com/x.png and https://example.com/page."}]}},
        # 14: a picture you sent through the hub's paperclip goes in as its path under uploads/
        {"type": "user", "timestamp": stamp(3), "message": {"role": "user", "content": f"and this one {hub.UPLOADS / sid / 'ab12-photo.png'}"}},
        # 15: a sidechain line in the main file is never a turn
        {"type": "assistant", "isSidechain": True, "timestamp": stamp(4), "message": {"role": "assistant", "content": [{"type": "text", "text": "side: bare.png"}]}},
    ]
    (hub.UPLOADS / sid).mkdir(parents=True, exist_ok=True)
    (hub.UPLOADS / sid / "ab12-photo.png").write_bytes(png(50, 25))
    (record / "transcript.jsonl").write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    sub = record / "transcript" / "subagents"
    (sub / "agent-abc123def.meta.json").write_text(json.dumps({"toolUseId": "a1"}))
    (sub / "agent-abc123def.jsonl").write_text("\n".join(json.dumps(line) for line in [
        {"type": "user", "isSidechain": True, "message": {"role": "user", "content": "draw something and save it as clip.mp4"}},
        {"type": "assistant", "isSidechain": True, "timestamp": stamp(15), "message": {"role": "assistant", "content": [use("w1", "Write", {"file_path": str(folder / "sub.png"), "content": "x"})]}},
        {"type": "assistant", "isSidechain": True, "timestamp": stamp(14), "message": {"role": "assistant", "content": [use("s2", "mcp__computer-use__screenshot", {})]}},
        {"type": "user", "isSidechain": True, "timestamp": stamp(14), "message": {"role": "user", "content": [result("s2", [image_block(33, 22)])]}},
    ]) + "\n")

    rec = hub.session_record(sid)
    items = rec["items"]
    by_text = lambda word: next((i for i in items if word in i.get("text", "")), None)
    media_of = lambda item: (item or {}).get("media", [])
    names = lambda item: sorted(m.get("name") or m.get("url") for m in media_of(item))

    first = items[0]
    check("a pasted picture shows inside what you said, with its pixel size", first["kind"] == "you" and media_of(first) == [{"kind": "image", "blob": "0.1", "name": "Pasted image", "w": 64, "h": 48}], first)
    check("the [Image #1] mark leaves the words when the picture is shown", first["text"] == "look at this", first["text"])
    check("a picture pasted alone is a turn of yours holding it", items[1]["kind"] == "you" and items[1]["text"] == "" and media_of(items[1])[0]["blob"] == "1.0", items[1])
    steps = [i for i in items if i["kind"] == "tools"]
    check("the steps are one run, before the reply", len(steps) == 1 and items.index(steps[0]) == 2, [i["kind"] for i in items])
    run = steps[0]
    got = {m.get("name"): m for m in media_of(run)}
    check("a Read picture is shown as its file, with its pixel size", got.get("shot.png", {}).get("path") == str(folder / "shot.png") and got["shot.png"].get("w") == 40, got.get("shot.png"))
    check("its pixels in the tool result are not shown a second time", not any(m.get("blob", "").startswith("3.") for m in media_of(run)), names(run))
    check("a Read PDF is shown", got.get("doc.pdf", {}).get("kind") == "pdf", names(run))
    check("a screenshot an MCP tool returned is shown, with its pixel size", any(m.get("blob") == "6.0.1" and m.get("name") == "Screenshot" and m.get("w") == 80 for m in media_of(run)), names(run))
    check("a Read picture outside the session's folders shows its pixels under its name, never its path", got.get("far.png", {}).get("blob") == "8.0.0" and "path" not in got["far.png"], got.get("far.png"))
    check("a file sent with SendUserFile is shown", got.get("sent.png", {}).get("path") == str(folder / "sent.png"), names(run))
    check("a file a command made is shown; one it only read is not", "made.png" in got and "old.png" not in got, names(run))
    check("what a subagent wrote is shown under the step that started it", "sub.png" in got, names(run))
    check("a screenshot a subagent's tool returned is shown, by its subagent blob", any(m.get("blob") == "abc123def:3.0.0" and m.get("w") == 33 for m in media_of(run)), [m.get("blob") for m in media_of(run)])
    check("a subagent's prompt naming a file doesn't show it", "clip.mp4" not in got, names(run))
    reply = by_text("Done.")
    shown = {m.get("name") or m.get("url"): m for m in media_of(reply)}
    check("a path with spaces in `code` is found", shown.get("My Shot 1.png", {}).get("w") == 30, list(shown))
    check("a bare file name in the session's folder is found", "clip.mp4" in shown and shown["clip.mp4"]["kind"] == "video", list(shown))
    check("a relative ./ path is found", shown.get("voice.wav", {}).get("kind") == "audio", list(shown))
    check("a markdown picture's target is found", "bare.png" in shown, list(shown))
    check("a file:// address with %20 is the same file, shown once", sum(1 for m in media_of(reply) if m.get("name") == "My Shot 1.png") == 1, names(reply))
    check("nothing in a folder never served is shown, however it's named", not any(".git" in (m.get("path") or "") for i in items for m in media_of(i)), [m for i in items for m in media_of(i) if ".git" in (m.get("path") or "")])
    check("a file outside the session's folders is never shown by path", not any(str(outside) in (m.get("path") or "") for i in items for m in media_of(i)))
    check("links in the reply are links", "https://example.com/x.png" in shown and "https://example.com/page" in shown, list(shown))
    check("a sidechain line in the main transcript is not a turn", by_text("side:") is None)
    upload = by_text("and this one")
    check("a picture you sent through the hub shows under its own name, with its size", media_of(upload) and media_of(upload)[0]["name"] == "photo.png" and media_of(upload)[0]["w"] == 50, media_of(upload))

    # the record is read once per change, and a subagent's file changing is a change
    again = hub.session_record(sid)
    check("asking again gives the same turns", again["items"] == items)
    time.sleep(0.01)
    with open(sub / "agent-abc123def.jsonl", "a") as f:
        f.write(json.dumps({"type": "assistant", "isSidechain": True, "timestamp": stamp(1), "message": {"role": "assistant", "content": [{"type": "text", "text": "Saved later.png too, and bare.png."}]}}) + "\n")
    (folder / "later.png").write_bytes(png(9, 9))
    later = hub.session_record(sid)
    check("a subagent's new file shows without the main transcript changing", "later.png" in names(next(i for i in later["items"] if i["kind"] == "tools")), names(next(i for i in later["items"] if i["kind"] == "tools")))

    check("a file Claude's reply names isn't shown again under the steps of that exchange", "bare.png" not in names(next(i for i in later["items"] if i["kind"] == "tools")) and any(m.get("name") == "bare.png" for i in later["items"] if i["kind"] == "claude" for m in media_of(i)), names(next(i for i in later["items"] if i["kind"] == "tools")))

    # serving: what the chat asks for is served, and only that
    data, mime = hub.blob_of(sid, "abc123def:3.0.0")
    check("a subagent's screenshot is served", mime == "image/png" and data.startswith(b"\x89PNG"))
    data, mime = preview.thumbnail(sid, str(folder / "doc.pdf"), "", "320")
    check("a PDF's first page is drawn as a picture", mime == "image/png" and data.startswith(b"\x89PNG") and hub.pixel_size(data)[1] > hub.pixel_size(data)[0], (mime, hub.pixel_size(data) if data.startswith(b"\x89PNG") else data[:8]))
    for px in ("960", "9999", "x"):
        data, mime = preview.thumbnail(sid, str(folder / "shot.png"), "", px)
        check(f"a thumbnail asked at {px!r} is served", mime.startswith("image/"), mime)
    for bad, why in ((str(folder / ".git" / "secret.png"), "never served"), (str(outside / "far.png"), "outside"), (str(folder / "clip.mp4"), "not a picture")):
        try:
            preview.thumbnail(sid, bad, "", "960")
            check(f"a thumbnail of a file {why} is refused", False)
        except hub.Refused:
            check(f"a thumbnail of a file {why} is refused", True)
    card = preview.link_card("https://example.com/media-check-%d.png" % os.getpid())
    check("a link to a picture is its own card, fetched later through the picture guards", card.get("kind") == "image" and len(card.get("image") or "") == 32 and card["title"].endswith(".png"), card)
    check("only addresses that name a PNG, JPEG, GIF or WebP are picture cards", not preview.PICTURE_LINK.search("/a.svg") and preview.PICTURE_LINK.search("/a.JPG"))
finally:
    shutil.rmtree(folder, ignore_errors=True)
    shutil.rmtree(outside, ignore_errors=True)
    shutil.rmtree(hub.RECORDS / sid, ignore_errors=True)
    shutil.rmtree(hub.UPLOADS / sid, ignore_errors=True)
    (hub.META / f"{sid}.json").unlink(missing_ok=True)
    for kept in (preview.CACHE / f"{preview._key('https://example.com/media-check-%d.png' % os.getpid())}.json",):
        kept.unlink(missing_ok=True)

print(f"\n{'All passed' if not fails else f'{fails} failed'}")
sys.exit(1 if fails else 0)
