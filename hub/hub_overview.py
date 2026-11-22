"""A session's Overview, for the side panel's first tab: where its work lives and what it is.

GET /api/sessions/<id>/overview answers with the folder (to copy, and to open in Finder when the page is on this Mac
itself), the repository's web address (from `git remote get-url origin`, an ssh address turned into https, never a
name or token from it), the branch and whether the folder is a worktree, the open pull request when `gh` is there and
answers, the transcript's id and when the session was last active, the links its chat printed (newest first, once
each) and the files it changed. git runs read only, with short timeouts, and never in a `no_vcs` repo. `gh` runs in
the background with its own longer timeout and is kept for two minutes: the first answer says it is on its way, and
nothing here ever waits on it, so neither does /api/state. The answer is kept for a few seconds per session.

POST /api/sessions/<id>/reveal opens the session's folder in Finder, only when the request comes from this Mac.
"""
import ipaddress, re, shutil, subprocess, threading, time
from pathlib import Path

import hub_data as hub
import hub_diff
from hub_base import ENV, HOME, HUB_PROJECT, Refused, off_limits

TTL = 4.0           # seconds an answer is kept per session
PR_TTL = 120.0      # seconds a pull request answer is kept per folder and branch
GIT_TIMEOUT = 3     # each git call
GH_TIMEOUT = 12     # gh asks GitHub, so it may take a while; it never holds a request
LINKS, FILES = 12, 200
_lock = threading.Lock()
_cache = {}         # sid -> (monotonic, answer)
_prs = {}           # (folder, branch) -> {"at": monotonic, "pr": dict | None, "said": str} | {"pending": True}
_local = {"at": None, "ips": set()}


def tilde(path) -> str:
    text = str(path)
    home = str(HOME)
    return "~" + text[len(home):] if text == home or text.startswith(home + "/") else text


def web_url(remote: str):
    """The repository's address in a browser, from what `git remote get-url origin` printed, or None.

    git@host:owner/repo.git, ssh://git@host[:port]/owner/repo.git and https://[user[:token]@]host/owner/repo(.git) all
    become https://host/owner/repo. A name, password or token in the address is never kept. A path on disk is None."""
    remote = (remote or "").strip()
    if not remote or "\n" in remote:
        return None
    host = path = None
    scp = re.match(r"^(?:[\w.+-]+@)?([\w.-]+\.[A-Za-z]{2,}|[\w-]+):(?!//)([^\s]+)$", remote)
    url = re.match(r"^(?:ssh|git|https?|git\+ssh)://(?:[^@/\s]+@)?([\w.-]+)(?::\d+)?/([^\s]+)$", remote)
    if url:
        host, path = url.group(1), url.group(2)
    elif scp and not remote.startswith(("/", ".", "~")):
        host, path = scp.group(1), scp.group(2)
    if not host or not path:
        return None
    path = re.sub(r"\.git/?$", "", path.strip("/"))
    if not re.match(r"^[\w.-]+(/[\w.-]+)+$", path) or ".." in path.split("/"):
        return None
    return f"https://{host.lower()}/{path}"


def _git(folder: str, *args) -> str:
    try:
        done = hub_diff.git(folder, *args, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def _gh_bin():
    return shutil.which("gh", path=ENV.get("PATH"))


def _ask_gh(key, folder: str, branch: str):
    """Runs in its own thread: the open pull request for this branch, as gh sees it."""
    pr, said = None, ""
    try:
        done = subprocess.run([_gh_bin(), "pr", "view", branch, "--json", "number,title,url,state,isDraft"], cwd=folder, env={**ENV, "GH_PROMPT_DISABLED": "1", "NO_COLOR": "1", "GH_NO_UPDATE_NOTIFIER": "1"},
                              capture_output=True, text=True, timeout=GH_TIMEOUT)
        if done.returncode == 0:
            import json
            data = json.loads(done.stdout or "{}")
            url = str(data.get("url") or "")
            if url.startswith("https://") and isinstance(data.get("number"), int):
                pr = {"number": data["number"], "title": str(data.get("title") or "")[:200], "url": url, "state": str(data.get("state") or "").lower(), "draft": bool(data.get("isDraft"))}
        else:
            said = "none" if "no pull requests found" in (done.stderr or "").lower() else "unknown"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        said = "unknown"
    with _lock:
        _prs[key] = {"at": time.monotonic(), "pr": pr, "said": said}


def pull_request(folder: str, branch: str, host: str):
    """{"pr": {...}} once known, {"pr": None} when there is none or gh can't say, {"pending": True} while gh is asked."""
    if not branch or host != "github.com" or not _gh_bin() or off_limits(folder):
        return {"pr": None, "said": "" if host == "github.com" and _gh_bin() else "no-gh" if host == "github.com" else ""}
    key = (folder, branch)
    with _lock:
        known = _prs.get(key)
        if known and not known.get("pending") and time.monotonic() - known["at"] < PR_TTL:
            return {"pr": known["pr"], "said": known["said"]}
        if not known or not known.get("pending"):
            _prs[key] = {"pending": True, "was": known}
            threading.Thread(target=_ask_gh, args=(key, folder, branch), daemon=True).start()
        was = (_prs[key].get("was") or {})
    if was and "pr" in was:  # an older answer stands while a newer one comes
        return {"pr": was["pr"], "said": was.get("said", "")}
    return {"pending": True}


def local_ips() -> set:
    """This Mac's own addresses, its tailnet one included, read from ifconfig at most once a minute."""
    now = time.monotonic()
    if _local["at"] is None or now - _local["at"] > 60:
        try:
            out = subprocess.run(["/sbin/ifconfig"], capture_output=True, text=True, timeout=2).stdout
            _local["ips"] = {m.split("%")[0] for m in re.findall(r"\binet6? ([0-9a-fA-F:.%]+)", out)}
        except (OSError, subprocess.TimeoutExpired):
            _local["ips"] = set()
        _local["at"] = now
    return _local["ips"]


def at_this_mac(headers) -> bool:
    """Whether the page asking is on this Mac. A loopback Host with nothing forwarded is; behind Tailscale Serve, the
    forwarded client address must be one of this Mac's own. Anything else, or anything unclear, is not."""
    forwarded = [part.strip() for part in (headers.get("x-forwarded-for") or "").split(",") if part.strip()]
    host = (headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
    if not forwarded:
        return host in ("127.0.0.1", "localhost", "::1")
    try:
        client = ipaddress.ip_address(forwarded[-1])
    except ValueError:
        return False
    return client.is_loopback or str(client) in local_ips()


def _folder(meta: dict):
    """The session's folder, when it is still one of its project's folders (or a worktree the hub made in one)."""
    try:
        return hub_diff.folder_of(meta["id"])
    except Refused:
        return None


def _links(sid: str) -> list:
    try:
        items = hub.shared_items(sid)
    except (Refused, OSError):
        return []
    out, seen = [], set()
    for item in items:
        if item.get("kind") != "link" or item.get("by"):
            continue
        url = str(item.get("url") or "")
        if not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "name": str(item.get("name") or url)[:200], "at": item.get("at") or ""})
        if len(out) >= LINKS:
            break
    return out


def _files(folder: str) -> list:
    try:
        if not hub_diff.is_repo(folder):
            return []
        base = hub_diff.base_of(folder)
        rows = [{"path": p, "added": a, "removed": r, "binary": b, "new": False} for p, a, r, b in hub_diff.tracked(folder, base)]
        for rel in hub_diff.untracked(folder)[:FILES]:
            lines = None if hub_diff.hidden(rel) else hub_diff.new_text(folder, rel)
            rows.append({"path": rel, "added": len(lines) if lines else 0, "removed": 0, "binary": lines is None and not hub_diff.hidden(rel), "new": True})
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows.sort(key=lambda row: row["path"])
    return rows[:FILES]


def _transcript(meta: dict):
    live = hub.live_transcript(meta["id"])
    if live is not None:
        return live.stem, live.stat().st_mtime
    kept = hub.RECORDS / meta["id"] / "transcript.jsonl"
    claude = meta.get("claude_session") if re.match(r"^[0-9a-f-]{36}$", str(meta.get("claude_session") or "")) else None
    return claude, (kept.stat().st_mtime if kept.exists() else None)


def _build(sid: str) -> dict:
    meta = hub.session_meta(sid)
    hubwide = meta.get("project") == HUB_PROJECT
    folder = None if hubwide else _folder(meta)
    shown = meta.get("folder") or meta.get("repo") or ""
    out = {"id": sid, "folder": tilde(shown) if shown else "", "path": shown, "exists": bool(shown) and Path(shown).is_dir(),
           "git": False, "no_vcs": bool(shown) and off_limits(shown), "repo_url": None, "host": "", "branch": "", "detached": False,
           "worktree": None, "pr": None, "pr_pending": False, "transcript": None, "active": None, "links": [], "files": [],
           "memory": None if hubwide else meta.get("project")}
    if meta.get("kind") == "claude":
        out["transcript"], out["active"] = _transcript(meta)
        out["links"] = _links(sid)
    events = hub.EVENTS / f"{sid}.json"
    if events.exists():
        out["active"] = max(out["active"] or 0, events.stat().st_mtime)
    if folder and not out["no_vcs"] and _git(folder, "rev-parse", "--is-inside-work-tree") == "true":
        out["git"] = True
        out["repo_url"] = web_url(_git(folder, "remote", "get-url", "origin"))
        out["host"] = out["repo_url"].split("/")[2] if out["repo_url"] else ""
        branch = _git(folder, "symbolic-ref", "-q", "--short", "HEAD")
        out["branch"] = branch or _git(folder, "rev-parse", "--short", "HEAD")
        out["detached"] = not branch
        top, common = _git(folder, "rev-parse", "--show-toplevel"), _git(folder, "rev-parse", "--path-format=absolute", "--git-common-dir")
        if top and common and Path(common).name == ".git" and Path(common).parent.resolve() != Path(top).resolve():
            out["worktree"] = {"main": tilde(Path(common).parent), "path": tilde(top)}
        out["files"] = _files(folder)
        if branch and out["repo_url"]:
            asked = pull_request(folder, branch, out["host"])
            out["pr"], out["pr_pending"] = asked.get("pr"), bool(asked.get("pending"))
            out["pr_said"] = asked.get("said", "")
    return out


def overview(sid: str, headers=None) -> dict:
    now = time.monotonic()
    with _lock:
        kept = _cache.get(sid)
    if kept and now - kept[0] < TTL and not kept[1].get("pr_pending"):
        answer = kept[1]
    else:
        answer = _build(sid)
        with _lock:
            _cache[sid] = (now, answer)
            for old in [k for k, (at, _) in _cache.items() if now - at > 600]:
                _cache.pop(old, None)
    return {**answer, "at_mac": at_this_mac(headers or {})}


def reveal(sid: str, headers) -> dict:
    """Opens the session's own folder in Finder, for a page on this Mac. Nothing from the request names the folder."""
    if not at_this_mac(headers or {}):
        raise Refused("Finder opens only from this Mac. Copy the path instead.")
    meta = hub.session_meta(sid)
    folder = (HOME if meta.get("project") == HUB_PROJECT else None) or _folder(meta)
    if not folder or not Path(folder).is_dir():
        raise Refused("This session's folder isn't there any more.")
    done = subprocess.run(["/usr/bin/open", str(folder)], capture_output=True, text=True, timeout=10)
    if done.returncode != 0:
        raise Refused("Finder didn't open it.")
    return {"ok": True}
