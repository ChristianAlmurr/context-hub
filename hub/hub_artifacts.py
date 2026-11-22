"""Artifacts: what a session made that is worth looking at, found in its transcript and served to the hub's viewer.

A session's artifacts are the files it wrote (Write, Edit, MultiEdit, NotebookEdit), the files a shell command of
its wrote where the command says so (a redirect, -o, --output, tee, the target of cp or mv) and the file changed
after the command started, the files it handed over (SendUserFile) or named in what it said, and the pages it
published (a claude.ai artifact, a deploy on a known host, a URL a deploy or publish tool returned). Each file is
listed once, at its latest version, and only while it is still there. A project's list is every session's.

Serving is the careful part. The hub serves a file's bytes only when the file is one this session listed, or it lies
inside the session's own folders: the project's folders, the session's folder or worktree, and its uploads. Never a
path with `..` in it, never a secret-looking file, never a folder the hub never serves (`.git`, `.ssh`, the config's
private folders), never more than MAX_RAW bytes. Every answer says its type, and nothing a session made ever runs as
the hub: HTML comes with a CSP `sandbox` (no allow-same-origin), so it runs in an opaque origin of its own, even when
opened in a tab, and can't fetch at all (connect-src 'none'); every other type is sandboxed with no script.
server.py also refuses every other /api request that comes from such a page (Origin "null", or Sec-Fetch-Site
cross-site or same-site).
"""
import json, os, re, time
from pathlib import Path
from urllib.parse import urlsplit

import hub_data as hub
import hub_settings
from hub_base import HOME, HUB_PROJECT, STORES, Refused


class Forbidden(Refused):
    status = "403 Forbidden"


class Missing(Refused):
    status = "404 Not Found"


class TooBig(Refused):
    status = "413 Payload Too Large"


MAX_RAW = 200 * 1024 * 1024  # the largest file served whole (video can be big; it is read in ranges)
MAX_TEXT = 2 * 1024 * 1024  # what the viewer reads of a text file, a table or JSON
MAX_ITEMS = 400

KINDS = {
    "html": {"html", "htm"},
    "markdown": {"md", "markdown", "mdx"},
    "image": {"png", "jpg", "jpeg", "gif", "webp", "avif", "svg", "bmp", "ico"},
    "pdf": {"pdf"},
    "video": {"mp4", "mov", "webm", "m4v"},
    "audio": {"mp3", "m4a", "wav", "ogg", "flac", "aac", "opus"},
    "data": {"csv", "tsv", "json", "jsonl", "ndjson", "geojson", "ipynb"},
    "code": {"py", "js", "mjs", "cjs", "ts", "tsx", "jsx", "swift", "sh", "bash", "zsh", "rb", "go", "rs", "java", "kt", "c", "h", "cc",
             "cpp", "hpp", "cs", "php", "css", "scss", "less", "sql", "yml", "yaml", "toml", "xml", "ini", "lua", "r", "dart", "vue",
             "svelte", "m", "mm", "pl", "ex", "exs", "erl", "hs", "scala", "graphql", "proto", "tf", "dockerfile", "makefile"},
    "text": {"txt", "log", "rst", "tex", "diff", "patch", "env.example"},
}
KIND_OF = {ext: kind for kind, exts in KINDS.items() for ext in exts}
MIME = {
    "html": "text/html; charset=utf-8", "htm": "text/html; charset=utf-8",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "avif": "image/avif",
    "svg": "image/svg+xml", "bmp": "image/bmp", "ico": "image/x-icon", "pdf": "application/pdf",
    "mp4": "video/mp4", "m4v": "video/mp4", "mov": "video/quicktime", "webm": "video/webm",
    "mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav", "ogg": "audio/ogg", "flac": "audio/flac", "aac": "audio/aac", "opus": "audio/ogg",
    "json": "application/json; charset=utf-8", "geojson": "application/json; charset=utf-8", "ipynb": "application/json; charset=utf-8",
    "css": "text/css; charset=utf-8", "js": "text/javascript; charset=utf-8", "mjs": "text/javascript; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}
# Files that look like keys or secrets are never listed or served, wherever they are and whoever wrote them.
SECRETISH = re.compile(r"^\.|^id_(rsa|dsa|ecdsa|ed25519)|(^|[._-])(credentials?|secrets?)([._-]|$)|\.(pem|key|p12|pfx|keychain|kdbx|der|crt)$", re.I)
WRITERS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SENDERS = {"SendUserFile"}
# Where a page Claude published lives: a claude.ai artifact, or a host that serves deploys.
PUBLISHED_HOST = re.compile(r"(^|\.)(vercel\.app|netlify\.app|pages\.dev|workers\.dev|github\.io|fly\.dev|onrender\.com|herokuapp\.com|surge\.sh|"
                            r"web\.app|firebaseapp\.com|railway\.app|deno\.dev|glitch\.me|netlify\.com|claude\.site|gist\.github\.com|"
                            r"streamlit\.app|replit\.app|observablehq\.com|codepen\.io|val\.town|gamma\.app)$", re.I)
PUBLISHING_TOOL = re.compile(r"deploy|publish|artifact|upload|share", re.I)
URL = re.compile(r"https?://[^\s<>\"'`)\]}]+")
EXT_ALT = "|".join(sorted(KIND_OF, key=len, reverse=True))
PATH_IN_TEXT = re.compile(r"(?:~/|/|\.{1,2}/|[\w.-]+/)[\w./@%+-]*\.(?:" + EXT_ALT + r")\b", re.I)
# What a shell command writes, when it says so.
OUT_TARGETS = [
    re.compile(r"(?<![<>&\d])>{1,2}\s*([^\s;&|<>()]+)"),  # > file, >> file (not 2>&1)
    re.compile(r"(?:^|\s)(?:-o|--out|--output|--outfile|--output-file|-O)(?:=|\s+)([^\s;&|<>()]+)"),
    re.compile(r"\btee\s+(?:-a\s+)?([^\s;&|<>()]+)"),
]
CP_MV = re.compile(r"(?:^|[;&|]\s*)(?:cp|mv|rsync)\s+(?:-\w+\s+)*(?:[^\s;&|]+\s+)+([^\s;&|<>()]+)")
CD_LEAD = re.compile(r"^\s*cd\s+([^\s;&|]+)\s*&&")
_cache = {}  # sid -> (stamp, found)


def on() -> bool:
    return hub_settings.value("feature_artifacts") is not False


def _need_on():
    if not on():
        raise Missing("Artifacts are switched off in Settings › Features.")


def kind_of(path: str) -> str:
    name = Path(path).name.lower()
    if name in ("dockerfile", "makefile"):
        return "code"
    return KIND_OF.get(name.rsplit(".", 1)[-1], "") if "." in name else ""


def mime_of(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext in MIME:
        return MIME[ext]
    return "text/plain; charset=utf-8" if kind_of(path.name) in ("markdown", "code", "text", "data") else "application/octet-stream"


def secret_like(path: Path) -> bool:
    return bool(SECRETISH.search(path.name)) or bool(hub.NEVER_SERVED & set(path.parts))


def _own_roots(meta: dict) -> list:
    """The session's own folders: its project's folders, its folder or worktree, and its uploads."""
    if meta.get("project") == HUB_PROJECT:  # a hub session's folder is the home folder: only the stores and projects are its own
        roots = [STORES, hub.HUB_HOME / "projects"]
    else:
        store = STORES / str(meta.get("project", ""))
        roots = [Path(r) for r in (hub.repos_of(store) if store.is_dir() else [])]
        roots += [Path(p) for p in (meta.get("folder"), meta.get("repo")) if p]
    roots.append(hub.UPLOADS / meta["id"])
    out = []
    for root in roots:
        try:
            real = root.resolve()
        except (OSError, RuntimeError):
            continue
        if real.exists() and real != HOME.resolve() and real != Path("/") and real not in out:
            out.append(real)
    return out


def _inside(path: Path, roots) -> bool:
    return any(root == path or root in path.parents for root in roots)


def _resolve(base: Path, text: str):
    text = re.sub(r"^file://(localhost)?", "", str(text or "").strip().strip("'\""))
    if not text or "\n" in text or len(text) > 1000:
        return None
    try:
        path = Path(text).expanduser() if text.startswith(("/", "~")) else base / text
        return path.resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _seconds(stamp: str) -> float:
    return hub._seconds(stamp) if stamp else 0.0


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(p.get("text", "")) for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def _scan(path: Path, by: str, base: Path, mention_roots, found: dict, links: dict):
    """One transcript file: every file it wrote, handed over or named, and every page it published."""
    tools = {}  # tool_use id -> tool name, for reading results

    def note(file, at, how, line, step=""):
        if file is None or not kind_of(file.name):
            return
        kept = found.get(str(file))
        if kept is None:
            kept = found[str(file)] = {"path": str(file), "ops": [], "versions": 0, "first": at, "at": "", "line": line, "by": by, "step": step}
        if how in ("write", "edit", "bash"):
            kept["versions"] += 1
        if how not in kept["ops"]:
            kept["ops"].append(how)
        if at >= kept["at"]:
            kept.update(at=at, line=line, by=by, **({"step": step} if step else {}))
        if not kept["first"] or (at and at < kept["first"]):
            kept["first"] = at

    def link(url, at, line, how):
        url = url.rstrip(".,;:!?*_")
        try:
            parts = urlsplit(url)
        except ValueError:
            return
        host = (parts.hostname or "").lower()
        published = PUBLISHED_HOST.search(host) or (host == "claude.ai" and re.match(r"^/(public/)?artifacts?/", parts.path)) or how == "tool"
        if not published or host in ("localhost", "127.0.0.1", "::1") or url.startswith("https://claude.ai/code/session_"):
            return
        kept = links.get(url)
        if kept is None or at >= kept["at"]:
            links[url] = {"kind": "link", "url": url, "name": host + (parts.path.rstrip("/") or ""), "host": host, "at": at, "line": line, "by": by,
                          "first": (kept or {}).get("first") or at}

    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return
    for number, raw in enumerate(lines):
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isMeta") or (entry.get("isSidechain") and not by) or entry.get("type") not in ("user", "assistant"):
            continue
        at = str(entry.get("timestamp", ""))
        message = entry.get("message") or {}
        content, role = message.get("content"), message.get("role")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content if isinstance(content, list) else []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "tool_use":
                name, given = str(block.get("name", "")), block.get("input") if isinstance(block.get("input"), dict) else {}
                tools[block.get("id")] = name
                if name in WRITERS:
                    target = given.get("file_path") or given.get("notebook_path") or ""
                    note(_resolve(base, target), at, "write" if name == "Write" else "edit", number, f"{'Wrote' if name == 'Write' else 'Edited'} {Path(str(target)).name}")
                elif name in SENDERS:
                    files = given.get("files") or given.get("paths") or [given.get("file") or given.get("path") or ""]
                    for one in (files if isinstance(files, list) else [files])[:24]:
                        note(_resolve(base, one), at, "shared", number, f"Shared {Path(str(one)).name}")
                elif name == "Bash":
                    command = str(given.get("command", ""))[:6000]
                    since = _seconds(at) - 2
                    lead = CD_LEAD.match(command)
                    here = _resolve(base, lead.group(1)) if lead else base
                    here = here if here is not None else base
                    named = [m.group(1) for pattern in OUT_TARGETS for m in pattern.finditer(command)] + [m.group(1) for m in CP_MV.finditer(command)]
                    named += [m.group(0) for m in PATH_IN_TEXT.finditer(URL.sub(" ", command)) if kind_of(m.group(0)) not in ("code", "text", "")]
                    for one in dict.fromkeys(named):
                        file = _resolve(here, one)
                        try:
                            changed = file is not None and since > 0 and file.stat().st_mtime >= since
                        except OSError:
                            changed = False
                        if changed:
                            note(file, at, "bash", number, f"Made {file.name} with a command")
                elif PUBLISHING_TOOL.search(name):
                    for url in URL.findall(json.dumps(given)):
                        link(url, at, number, "said")
            elif kind == "tool_result":
                text = _text_of(block.get("content"))
                how = "tool" if PUBLISHING_TOOL.search(tools.get(block.get("tool_use_id"), "")) else "said"
                for url in URL.findall(text[:20000]):
                    link(url, at, number, how)
            elif kind == "text" and role == "assistant":
                text = str(block.get("text", ""))
                for url in URL.findall(text):
                    link(url, at, number, "said")
                for match in PATH_IN_TEXT.findall(URL.sub(" ", text)):
                    file = _resolve(base, match)
                    if file is not None and kind_of(file.name) not in ("code", "text") and _inside(file, mention_roots):
                        note(file, at, "named", number)


def _find(sid: str, meta: dict) -> list:
    """Every artifact the session's transcript names, newest first, cached until the transcript changes."""
    transcript = hub.transcript_of(sid)
    if transcript is None:
        return []
    subagents = hub._subagents_of(transcript)
    try:
        stamp = (str(transcript), transcript.stat().st_mtime_ns, transcript.stat().st_size, tuple((p.name, p.stat().st_mtime_ns) for p in subagents))
    except OSError:
        return []
    kept = _cache.get(sid)
    if kept and kept[0] == stamp:
        return kept[1]
    base = Path(meta.get("folder") or meta.get("repo") or HOME)
    mention_roots = hub.allowed_roots(meta)
    found, links = {}, {}
    _scan(transcript, "", base, mention_roots, found, links)
    for path in subagents:
        _scan(path, path.stem[len("agent-"):], base, mention_roots, found, links)
    items = [{"kind": kind_of(p), **v} for p, v in found.items() if not secret_like(Path(p))] + list(links.values())
    items.sort(key=lambda i: i["at"], reverse=True)
    _cache[sid] = (stamp, items)
    return items


def _rel(path: Path, meta: dict, roots) -> str:
    for root in [Path(meta["folder"]).resolve()] if meta.get("folder") and meta.get("project") != HUB_PROJECT else []:
        if root in path.parents:
            return str(path.relative_to(root))
    for root in roots:
        if root in path.parents:
            return f"{root.name}/{path.relative_to(root)}"
    text = str(path)
    home = str(HOME.resolve())
    return "~" + text[len(home):] if text.startswith(home + "/") else text


def _present(sid: str, meta: dict) -> list:
    """The list as the page shows it: files that are still there, with their size and when they last changed."""
    roots = _own_roots(meta)
    out = []
    for item in _find(sid, meta):
        if item["kind"] == "link":
            out.append({**item, "sid": sid, "when": _seconds(item["at"])})
            continue
        path = Path(item["path"])
        try:
            st = path.stat()
        except OSError:
            continue
        if not path.is_file():
            continue
        out.append({**item, "sid": sid, "name": path.name, "ext": path.suffix.lower().lstrip("."), "rel": _rel(path, meta, roots),
                    "size": st.st_size, "mtime": st.st_mtime, "when": max(st.st_mtime, _seconds(item["at"]))})
        if len(out) >= MAX_ITEMS:
            break
    out.sort(key=lambda i: i["when"], reverse=True)  # latest version first: a file written again since rises to the top
    return out


def session_list(sid: str) -> dict:
    _need_on()
    meta = hub.session_meta(sid)
    items = _present(sid, meta)
    return {"items": items, "session": {"id": sid, "title": meta.get("title", ""), "project": meta.get("project", "")}}


def project_list(name: str) -> dict:
    """Every session's artifacts in a project, one row per file or page, at its latest version."""
    _need_on()
    if name != HUB_PROJECT:
        hub.store_of(name)
    merged, titles = {}, {}
    for file in sorted(hub.META.glob("*.json")):
        try:
            meta = json.loads(file.read_text())
        except (OSError, ValueError):
            continue
        if meta.get("project") != name or not hub.SESSION_ID.match(str(meta.get("id", ""))):
            continue
        titles[meta["id"]] = meta.get("title", "")
        for item in _present(meta["id"], meta):
            key = item.get("url") or item["path"]
            if key not in merged or item["when"] > merged[key]["when"]:
                merged[key] = {**item, "title": meta.get("title", "")}
    items = sorted(merged.values(), key=lambda i: i["when"], reverse=True)[:MAX_ITEMS]
    return {"items": items, "sessions": titles}


def resolve(sid: str, raw: str, meta: dict = None) -> Path:
    """The one file a request may have: listed by this session, or inside its own folders. Nothing else, ever."""
    _need_on()
    meta = meta or hub.session_meta(sid)
    text = str(raw or "")
    if not text.startswith("/") or "\x00" in text or any(part in ("..", ".") for part in text.split("/")):
        raise Forbidden("That path isn't allowed.")
    try:
        path = Path(text).resolve()
    except (OSError, RuntimeError, ValueError):
        raise Forbidden("That path isn't allowed.")
    if secret_like(path) or not kind_of(path.name):
        raise Forbidden("That file can't be opened here.")
    listed = {i["path"] for i in _find(sid, meta) if i.get("path")}
    if str(path) not in listed and not _inside(path, _own_roots(meta)):
        raise Forbidden("That file is outside this session's folders.")
    if not path.is_file():
        raise Missing("That file isn't there any more.")
    if path.stat().st_size > MAX_RAW:
        raise TooBig("That file is too big to open here.")
    return path


def text_of(sid: str, raw: str) -> dict:
    """A text file's words for the viewer: markdown, code, a table, JSON. At most MAX_TEXT bytes."""
    path = resolve(sid, raw)
    kind = kind_of(path.name)
    if kind not in ("markdown", "code", "text", "data", "html"):
        raise Forbidden("That file has no text to show.")
    size = path.stat().st_size
    with open(path, "rb") as f:
        data = f.read(MAX_TEXT)
    if b"\x00" in data[:8192]:
        raise Forbidden("That file isn't text.")
    return {"name": path.name, "path": str(path), "kind": kind, "text": data.decode("utf-8", errors="replace"),
            "size": size, "truncated": size > MAX_TEXT, "mtime": path.stat().st_mtime}


# What each answer may do. HTML runs in an opaque origin with no network but its own folder's files and web assets;
# everything else runs nothing. A PDF goes without, as /api/sessions/<id>/file sends it: Chrome's viewer won't draw
# a sandboxed PDF, and a PDF runs no script as the hub.
def policy_of(path: Path, origin: str = "") -> str:
    """The page's own files are named by the hub's origin as well as 'self': a sandboxed page's 'self' is its opaque
    origin, which matches nothing, so the folder's pictures and styles would never load."""
    kind = kind_of(path.name)
    if kind == "pdf":
        return ""
    own = f"'self' {origin}" if re.match(r"^https?://[\w.:\[\]-]+$", origin or "") else "'self'"
    if kind == "html":
        return ("sandbox allow-scripts allow-popups allow-downloads allow-modals; default-src 'none'; "
                f"script-src {own} 'unsafe-inline' 'unsafe-eval' https:; style-src {own} 'unsafe-inline' https:; "
                f"img-src {own} data: blob: https:; font-src {own} data: https:; media-src {own} data: blob:; "
                "connect-src 'none'; form-action 'none'; frame-src 'none'; worker-src 'none'; object-src 'none'; base-uri 'self'; "
                "frame-ancestors 'self'")
    return f"sandbox; default-src 'none'; img-src {own} data:; media-src {own}; style-src 'unsafe-inline'; frame-ancestors 'self'"


def raw_route(parts) -> bool:
    """/api/sessions/<id>/raw/<the file's absolute path>: the one /api route a sandboxed page may load from."""
    return len(parts) >= 5 and parts[:2] == ["api", "sessions"] and parts[3] == "raw"
