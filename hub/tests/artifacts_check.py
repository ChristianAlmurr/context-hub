#!/usr/bin/env python3
"""The artifact server: what a session made is found in its transcript, each file once at its latest version and only
while it is still there; a file's bytes are served only from the session's own folders or as the transcript wrote
them, never through `..`, never a secret, never too big, always with its own type; an HTML page comes with a sandbox
and a CSP that keep it out of the hub's origin; and the hub's API refuses every request such a page could make.

No Claude session: two made-up sessions (artifacts_fixture.py) in a throwaway project, hub-test-throwaway-<n>, made
here and removed at the end, against a second instance (the six HUB_* variables, see tests/instance.py). The switch
is turned off and on again through PUT /api/settings, and put back as it was found.
Run: /usr/bin/python3 tests/artifacts_check.py
"""
import http.client, json, os, shutil, sys, tempfile, time
from pathlib import Path
from urllib.parse import quote

from instance import CFG, HOME, NAME, OWNER, PORT, WRITE, base, launchd_jobs, quiet_alert, remove_project, sweep
import hub_artifacts as artifacts
import artifacts_fixture as fx

fails = 0


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{str(extra)[:400]}]"), flush=True)
    fails += 0 if ok else 1


def call(method, path, body=None, headers=None, raw=False):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    c.request(method, path, json.dumps(body) if body is not None else None, {**(WRITE if method != "GET" else OWNER), **(headers or {})})
    r = c.getresponse()
    data = r.read()
    if raw:
        return r.status, {k.lower(): v for k, v in r.getheaders()}, data
    try:
        return r.status, json.loads(data or b"{}")
    except ValueError:
        return r.status, {}


def raw_url(sid, path, extra=""):
    return f"/api/sessions/{sid}/raw" + "/".join(quote(part) for part in str(path).split("/")) + extra


sweep()
launchd_before = launchd_jobs()
REPO = HOME / "projects" / NAME
elsewhere = Path(tempfile.mkdtemp(prefix="artifacts-check-elsewhere.", dir=f"/private/tmp/claude-{os.getuid()}"))
sid, other, stranger = os.urandom(4).hex(), os.urandom(4).hex(), os.urandom(4).hex()
config_before = base.CONFIG.read_bytes()  # put back exactly as found, however it was laid out
settings_before = None
try:
    made = call("POST", "/api/projects", {"name": NAME})[1]
    check("a throwaway project is created", made.get("name") == NAME, made)
    quiet_alert(NAME)
    settings_before = call("GET", "/api/settings")[1].get("values", {}).get("feature_artifacts", True)
    call("PUT", "/api/settings", {"feature_artifacts": True})
    fx.make(REPO, sid, NAME, "Made one of everything", elsewhere)
    fx.make(REPO / "second", other, NAME, "A second session", elsewhere / "two")
    fx.make(elsewhere / "three", stranger, "hub-test-no-such-project", "Another project's session", elsewhere / "four")

    # ── discovery ──
    status, listed = call("GET", f"/api/sessions/{sid}/artifacts")
    items = listed.get("items", [])
    by_name = {i.get("name") or i.get("url"): i for i in items}
    check("the list answers", status == 200 and items, (status, listed))
    for name, kind in (("report.html", "html"), ("notes.md", "markdown"), ("chart.png", "image"), ("logo.svg", "image"), ("data.csv", "data"),
                       ("data.json", "data"), ("greet.py", "code"), ("brief.pdf", "pdf"), ("clip.mp4", "video"), ("voice.wav", "audio"),
                       ("sub.md", "markdown"), ("outside.md", "markdown")):
        check(f"{name} is found as {kind}", by_name.get(name, {}).get("kind") == kind, by_name.get(name))
    check("a file written then edited is one row with two versions", [i["name"] for i in items if i.get("name") == "notes.md"] == ["notes.md"] and by_name["notes.md"]["versions"] == 2
          and by_name["notes.md"]["ops"] == ["write", "edit"], by_name.get("notes.md"))
    check("a file a command wrote is found by its redirect", "bash" in by_name.get("data.csv", {}).get("ops", []), by_name.get("data.csv"))
    check("and by -o after a cd", by_name.get("chart.png", {}).get("rel") == "img/chart.png" and "bash" in by_name["chart.png"]["ops"], by_name.get("chart.png"))
    check("a file handed over with SendUserFile is found", by_name.get("brief.pdf", {}).get("ops") == ["shared"], by_name.get("brief.pdf"))
    check("a subagent's file says so", by_name.get("sub.md", {}).get("by") == "abc123def", by_name.get("sub.md"))
    check("a file deleted since is left out", "gone.md" not in by_name)
    check("a secret-looking file the session wrote is never listed", ".env" not in by_name)
    check("a file only named, never made, is left out", "untouched.py" not in by_name and "untouched.html" not in by_name)
    links = sorted(i["url"] for i in items if i["kind"] == "link")
    check("published pages are found: a deploy host, a claude.ai artifact, a deploy tool's answer",
          links == ["https://claude.ai/public/artifacts/0000-demo", "https://demo-build.example.org/", "https://demo-report.vercel.app/"], links)
    whens = [i["when"] for i in items]
    check("newest first", whens == sorted(whens, reverse=True), whens)
    (REPO / "notes.md").write_text(fx.NOTES_V2 + "\nOne more line.\n")
    os.utime(REPO / "notes.md", (time.time() + 5, time.time() + 5))
    again = call("GET", f"/api/sessions/{sid}/artifacts")[1]["items"]
    check("a file written again rises to the top", again[0].get("name") == "notes.md", [i.get("name") for i in again[:3]])

    status, project = call("GET", f"/api/p/{NAME}/artifacts")
    rows = project.get("items", [])
    titles = {i.get("title") for i in rows}
    check("the project's list has both sessions' artifacts, each with its session", status == 200 and titles == {"Made one of everything", "A second session"}, (status, titles))
    shared = [i for i in rows if i.get("path") == str(elsewhere / "outside.md")]
    check("a project's list has each file once", len(shared) == 1 and len({i.get("path") or i.get("url") for i in rows}) == len(rows), len(rows))

    # ── serving: content types and policies ──
    types = {}
    for name in ("report.html", "notes.md", "img/chart.png", "logo.svg", "data.csv", "data.json", "greet.py", "brief.pdf", "clip.mp4", "voice.wav"):
        status, head, body = call("GET", raw_url(sid, REPO / name), raw=True)
        types[name] = (status, head.get("content-type"), head.get("content-security-policy", ""), head.get("x-content-type-options"))
    want = {"report.html": "text/html; charset=utf-8", "notes.md": "text/plain; charset=utf-8", "img/chart.png": "image/png", "logo.svg": "image/svg+xml",
            "data.csv": "text/csv; charset=utf-8", "data.json": "application/json; charset=utf-8", "greet.py": "text/plain; charset=utf-8",
            "brief.pdf": "application/pdf", "clip.mp4": "video/mp4", "voice.wav": "audio/wav"}
    for name, mime in want.items():
        check(f"{name} is served as {mime}, nosniff", types[name][0] == 200 and types[name][1] == mime and types[name][3] == "nosniff", types[name])
    html_policy = types["report.html"][2]
    check("an HTML page is sandboxed with scripts but never allow-same-origin", html_policy.startswith("sandbox allow-scripts") and "allow-same-origin" not in html_policy, html_policy)
    check("it can't fetch, post a form, frame or be framed by anyone but the hub",
          all(part in html_policy for part in ("connect-src 'none'", "form-action 'none'", "frame-src 'none'", "frame-ancestors 'self'", "default-src 'none'")), html_policy)
    check("its own folder's files are named by the hub's origin, since its own origin is opaque", f"img-src 'self' {CFG['origin']}" in html_policy, html_policy)
    for name in ("logo.svg", "notes.md", "img/chart.png", "data.json"):
        check(f"{name} is sandboxed with no script at all", types[name][2].startswith("sandbox;") and "script" not in types[name][2], types[name][2])
    status, head, body = call("GET", raw_url(sid, REPO / "clip.mp4"), headers={"Range": "bytes=0-9"}, raw=True)
    check("video is read in ranges", status == 206 and len(body) == 10 and head.get("content-range", "").startswith("bytes 0-9/"), (status, head))
    status, head, _ = call("GET", raw_url(sid, REPO / "report.html", "?download=1"), raw=True)
    check("download asks the browser to save it, by its name", status == 200 and head.get("content-disposition") == 'attachment; filename="report.html"', head)
    status, text = call("GET", f"/api/sessions/{sid}/artifact-text?path={quote(str(REPO / 'notes.md'))}")
    check("a document's text is read for the viewer", status == 200 and "Release notes" in text.get("text", "") and text.get("truncated") is False, (status, text))
    big = REPO / "big.csv"
    big.write_text("n\n" + "1234567\n" * 300_000)
    status, text = call("GET", f"/api/sessions/{sid}/artifact-text?path={quote(str(big))}")
    check("a text over 2 MB is cut, and says so", status == 200 and text.get("truncated") is True and len(text.get("text", "")) == artifacts.MAX_TEXT, (status, text.get("size")))
    status, _ = call("GET", f"/api/sessions/{sid}/artifact-text?path={quote(str(REPO / 'img' / 'chart.png'))}")
    check("a picture has no text to read", status == 403, status)

    # ── serving: what is refused ──
    status, _, _ = call("GET", raw_url(sid, REPO / "untouched.html"), raw=True)
    check("a file in the project's folder, never named, may still be read (a page's own pictures)", status == 200, status)
    status, _, _ = call("GET", raw_url(sid, elsewhere / "outside.md"), raw=True)
    check("a file the session wrote outside its folders is served", status == 200, status)
    status, err = call("GET", raw_url(sid, elsewhere / "never.md"))
    check("a file outside its folders it never wrote is refused", status == 403 and "outside" in err.get("error", ""), (status, err))
    status, err = call("GET", raw_url(sid, REPO / ".env"))
    check("a secret-looking file is refused, though the session wrote it", status == 403, (status, err))
    status, err = call("GET", raw_url(sid, REPO / ".git" / "config"))
    check("nothing in .git is served", status == 403, (status, err))
    for label, path in (("..", f"/api/sessions/{sid}/raw{REPO}/../../../../etc/hosts"), ("encoded ..", f"/api/sessions/{sid}/raw{REPO}/%2e%2e/%2e%2e/%2e%2e/etc/hosts"),
                        ("an encoded slash with ..", f"/api/sessions/{sid}/raw{REPO}/img%2f..%2f..%2fnotes.md"), ("a dot segment", f"/api/sessions/{sid}/raw{REPO}/./notes.md")):
        status, err = call("GET", path)
        check(f"a path with {label} is refused", status == 403 and err.get("error") == "That path isn't allowed.", (status, err))
    os.symlink("/etc/hosts", REPO / "link.md")
    status, err = call("GET", raw_url(sid, REPO / "link.md"))
    check("a link out of the folder is followed to where it really is, and refused there", status == 403, (status, err))
    status, err = call("GET", raw_url(sid, REPO / "gone.md"))
    check("a file that has gone says so", status == 404, (status, err))
    status, _, _ = call("GET", raw_url(other, REPO / "notes.md"), raw=True)
    check("another session of the project may read the project's files", status == 200, status)
    status, err = call("GET", raw_url(stranger, REPO / "notes.md"))
    check("a session of another project can't", status == 403, (status, err))
    status, err = call("GET", f"/api/sessions/zzzz/raw{REPO}/notes.md")
    check("a session that isn't one is refused", status in (403, 409), (status, err))
    held, artifacts.MAX_RAW = artifacts.MAX_RAW, 10
    try:
        artifacts.resolve(sid, str(REPO / "report.html"))
        check("a file over the size cap is refused", False)
    except artifacts.TooBig:
        check("a file over the size cap is refused", True)
    finally:
        artifacts.MAX_RAW = held

    # ── the API refuses what a sandboxed page could send ──
    sandboxed = {"Origin": "null", "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors"}
    status, err = call("GET", "/api/state", headers=sandboxed)
    check("GET /api/state from a sandboxed page is refused", status == 403 and err.get("error") == "Wrong origin.", (status, err))
    status, err = call("GET", "/api/state", headers={"Sec-Fetch-Site": "cross-site"})
    check("so is any cross-site read of the API", status == 403, (status, err))
    status, err = call("GET", "/api/state", headers={"Sec-Fetch-Site": "same-site"})
    check("and a read from another port on the same host", status == 403, (status, err))
    status, err = call("GET", f"/api/sessions/{sid}/artifacts", headers=sandboxed)
    check("even the artifact list", status == 403, (status, err))
    status, err = call("POST", "/api/sessions", {"project": NAME, "tasks": []}, headers=sandboxed)
    check("a write from a sandboxed page is refused", status == 403, (status, err))
    status, err = call("POST", f"/api/sessions/{sid}/key", {"key": "enter"}, headers={"Origin": "null"})
    check("a key typed into a terminal from a sandboxed page is refused", status == 403, (status, err))
    status, err = call("GET", "/api/stream", headers=sandboxed)
    check("the state stream is refused to it", status == 403, (status, err))
    status, _, _ = call("GET", raw_url(sid, REPO / "img" / "chart.png"), headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Dest": "image"}, raw=True)
    check("but the page's own picture loads from the raw route", status == 200, status)
    status, err = call("GET", "/api/state")
    check("the hub's own page still reads the API", status == 200 and "sessions" in err, status)
    status, err = call("GET", "/api/state", headers={"Sec-Fetch-Site": "same-origin"})
    check("as a same-origin fetch too", status == 200, status)

    # ── the switch ──
    status, err = call("PUT", "/api/settings", {"feature_artifacts": False})
    check("the switch turns off", status == 200, (status, err))
    for path in (f"/api/sessions/{sid}/artifacts", f"/api/p/{NAME}/artifacts", raw_url(sid, REPO / "notes.md"), f"/api/sessions/{sid}/artifact-text?path={quote(str(REPO / 'notes.md'))}"):
        status, err = call("GET", path)
        check(f"off, {path.split('?')[0].replace(str(REPO), '<repo>')[:60]} is not there", status == 404 and "switched off" in err.get("error", ""), (status, err))
    status, shared = call("GET", f"/api/sessions/{sid}/shared")
    check("off, the chat's shared list works as before", status == 200 and isinstance(shared, list), status)
    call("PUT", "/api/settings", {"feature_artifacts": True})
    status, _ = call("GET", f"/api/sessions/{sid}/artifacts")
    check("on again, the list is back", status == 200, status)
finally:
    if settings_before is not None:
        call("PUT", "/api/settings", {"feature_artifacts": settings_before})
        base.CONFIG.write_bytes(config_before)
    for one in (sid, other, stranger):
        fx.remove(one)
    shutil.rmtree(elsewhere, ignore_errors=True)
    left = remove_project(NAME)
    check("the throwaway project is gone", not left, left)
    check("no launchd job was made", launchd_jobs() == launchd_before)

print(f"\n{'all passed' if not fails else f'{fails} failed'}")
sys.exit(1 if fails else 0)
