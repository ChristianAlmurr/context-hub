"""The checkouts the hub makes for a session of its own (<repo>/.claude/worktrees/<name>, on a branch hub/<name>), and
their lifecycle: what each holds (its branch, how far it is ahead of the branch it came from, what is uncommitted,
whether it is merged), and removing a checkout or a merged branch once the work is done.

Rules it keeps, whatever the request says:
- It only ever touches checkouts directly inside a project folder's .claude/worktrees, that git lists as worktrees of
  that folder. The main checkout is never one of them.
- A checkout with uncommitted files is removed only when the request says so and names how many files it expects to
  lose; if that number changed since the person looked, nothing happens.
- A branch is deleted only when it is not checked out anywhere, is one the hub or Claude made for a worktree, and is
  merged, unless the request confirms how many unmerged commits it is giving up.
- Nothing runs git in a no_vcs folder: run() refuses it, and every entry point says so before trying.
"""
import json, os, re, shutil, threading, time
from pathlib import Path

from hub_base import HOME, Refused, Malformed, off_limits, run

TREES = Path(".claude") / "worktrees"
OURS = re.compile(r"^(hub/|worktree-)[\w./-]+$")  # branches made for a worktree: the hub's hub/<name>, Claude's own worktree-<name>
FACTS_TTL = 15  # seconds; the sidebar polls every few, and git is asked at most this often per running session's checkout
IDLE_TTL = 120  # and this often for a session that isn't running, whose branch rarely changes
_cache, _cache_lock = {}, threading.Lock()


def git(folder, *args, timeout=15):
    return run("git", "-C", folder, *args, timeout=timeout)


def tilde(path) -> str:
    return str(path).replace(str(HOME), "~", 1)


def real(path) -> Path:
    return Path(os.path.realpath(str(path)))


def forget():
    """Drop what is cached, after anything is removed: the next look asks git again."""
    with _cache_lock:
        _cache.clear()


# ── reading ──
def origin_of(repo: str) -> dict:
    """Where a new worktree comes from, kept with its session: the branch the folder is on, and the commit."""
    base = git(repo, "symbolic-ref", "-q", "--short", "HEAD").stdout.strip()
    start = git(repo, "rev-parse", "-q", "--verify", "HEAD").stdout.strip()
    return {"base": base, "start": start}


def listing(repo: str) -> list:
    """`git worktree list --porcelain`, as one dict per checkout. The first is always the main checkout."""
    result = git(repo, "worktree", "list", "--porcelain")
    if result.returncode != 0:
        return []
    out, entry = [], {}
    for line in result.stdout.splitlines() + [""]:
        if not line.strip():
            if entry.get("path"):
                out.append(entry)
            entry = {}
        elif line.startswith("worktree "):
            entry = {"path": line[9:], "branch": "", "head": "", "detached": False, "locked": False, "prunable": False}
        elif line.startswith("branch "):
            entry["branch"] = line[7:].removeprefix("refs/heads/")
        elif line.startswith("HEAD "):
            entry["head"] = line[5:]
        elif line == "detached":
            entry["detached"] = True
        elif line.startswith("locked"):
            entry["locked"] = True
        elif line.startswith("prunable"):
            entry["prunable"] = True
    return out


def inside_trees(repo: str, path) -> bool:
    """A checkout directly inside the repo's .claude/worktrees, or one the hub placed elsewhere by the worktree_path
    setting for one of its sessions (kept with that session), and never the repo itself."""
    root = real(Path(repo) / TREES)
    where = real(path)
    if where == real(repo):
        return False
    return where.parent == root or str(where) in placed_folders(repo)


# ── where new worktrees go: the worktree_path setting ──
# A template such as "{parent}/{repo}-worktrees/{name}" or ".worktrees/{name}". Relative to the repo; {parent} is the
# folder the repo is in, ~ is home. {name} and {branch} only in its last part, so each checkout has a folder of its own.
# Wherever it points, the checkout must land inside the repo (never in .git) or inside the projects folder: no "..",
# and every placeholder is filled with a plain name, so nothing can climb out.
PLACEHOLDERS = ("repo", "project", "name", "branch", "parent")
TEMPLATE_PART = re.compile(r"\{([^{}]*)\}")


def _plain(text: str) -> str:
    """A placeholder's value as one safe folder name."""
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip(".-")[:80]
    return out or "x"


def check_template(text: str) -> str:
    """The template as it is kept, or raise Malformed saying what is wrong with it. Tried on an example repo in the
    projects folder, so a template that can only land outside it is refused here, not when a session starts."""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) > 200 or any(ord(c) < 32 for c in text) or "\\" in text:
        raise Malformed("Keep it to one line of folder names, up to 200 characters.", name="worktree_path")
    parts = [part for part in text.rstrip("/").split("/")]
    lead = 1 if text.startswith("/") else 0
    for i, part in enumerate(parts[lead:], lead):
        if part in ("", ".", ".."):
            raise Malformed("Name each folder plainly: no empty parts, no . and no .. (use {parent} for the repo's folder).", name="worktree_path")
        for found in TEMPLATE_PART.findall(part):
            if found not in PLACEHOLDERS:
                raise Malformed(f"{{{found}}} isn't a placeholder. Use {{repo}}, {{project}}, {{name}}, {{branch}} or {{parent}}.", name="worktree_path")
        if ("{" in TEMPLATE_PART.sub("", part)) or ("}" in TEMPLATE_PART.sub("", part)):
            raise Malformed("A { or } that isn't part of a placeholder.", name="worktree_path")
        if "{parent}" in part and (i != 0 or part != "{parent}"):
            raise Malformed("{parent} can only be the first folder, on its own.", name="worktree_path")
        if part == "~" and i != 0:
            raise Malformed("~ can only start it.", name="worktree_path")
        if i < len(parts) - 1 and ("{name}" in part or "{branch}" in part):
            raise Malformed("{name} and {branch} go in the last folder only.", name="worktree_path")
        if part.lower() == ".git":
            raise Malformed("Never inside .git.", name="worktree_path")
    if "{name}" not in parts[-1] and "{branch}" not in parts[-1]:
        raise Malformed("End with {name} or {branch}, so each session gets a folder of its own.", name="worktree_path")
    from hub_base import PROJECTS
    where, why = placement(str(PROJECTS / "example-repo"), "example", "example-name", text)
    if why:
        raise Malformed(why, name="worktree_path")
    return text


def placement(repo: str, project: str, name: str, template=None):
    """(the folder a new worktree goes in, "") or (None, why not). With no template, the setting's."""
    from hub_base import PROJECTS
    if template is None:
        import hub_settings
        template = hub_settings.value("worktree_path") if "worktree_path" in hub_settings.BY_NAME else ""
    if not template:
        return Path(repo) / TREES / name, ""
    values = {"repo": _plain(Path(repo).name), "project": _plain(project), "name": _plain(name), "branch": _plain(f"hub/{name}")}
    parts = template.rstrip("/").split("/")
    if parts[0] == "{parent}":
        base, parts = Path(repo).parent, parts[1:]
    elif parts[0] == "~":
        base, parts = HOME, parts[1:]
    elif parts[0] == "":
        base, parts = Path("/"), parts[1:]
    else:
        base = Path(repo)
    filled = [TEMPLATE_PART.sub(lambda m: values[m[1]], part) for part in parts]
    if any(part in ("", ".", "..") or part.lower() == ".git" for part in filled):
        return None, "That template doesn't make a plain folder."
    path = base.joinpath(*filled)
    # Compared as the folders really are: the nearest part that exists is resolved, links and all.
    known = path
    while not known.exists() and known != known.parent:
        known = known.parent
    resolved = real(known) / path.relative_to(known)
    inside = lambda root: resolved != real(root) and str(resolved).startswith(str(real(root)).rstrip("/") + "/")
    if inside(repo):
        if inside(Path(repo) / ".git"):
            return None, "Never inside .git."
        return path, ""
    if inside(PROJECTS):
        if resolved.parent == real(PROJECTS):
            return None, f"Put them in a folder of their own inside {tilde(PROJECTS)}, not loose in it, where they'd pass for projects."
        return path, ""
    return None, f"It must stay inside the repo or inside {tilde(PROJECTS)}."


def preview(template: str, project: str = "") -> dict:
    """GET /api/settings/worktree-preview: where a new worktree would go for a real project, or why the template can't."""
    import hub_data as hub
    try:
        kept = check_template(template)
    except Malformed as bad:
        return {"ok": False, "why": str(bad)}
    repo, name = "", project
    for p in ([project] if project else []) + [m.get("project") for m in _metas()]:
        try:
            found = [r for r in hub.repos_of(hub.store_of(p)) if (Path(r) / ".git").exists() and not off_limits(r)] if p else []
        except Exception:
            found = []
        if found:
            repo, name = found[0], p
            break
    repo = repo or str(__import__("hub_base").PROJECTS / "my-app")
    path, why = placement(repo, name or "my-app", "fix-login-a1b2", kept)
    if why:
        return {"ok": False, "why": why, "repo": tilde(repo)}
    outside = not str(real(path)).startswith(str(real(repo)).rstrip("/") + "/")
    return {"ok": True, "path": tilde(path), "repo": tilde(repo), "outside": outside, "template": kept}


def placed_folders(repo: str) -> set:
    """Checkouts the hub placed by the setting, for this repo: the folders its sessions recorded, wherever they went."""
    out = set()
    for meta in _metas():
        tree = meta.get("tree") if isinstance(meta.get("tree"), dict) else {}
        if meta.get("isolate") and tree.get("placed") and meta.get("folder") and meta.get("repo") and real(meta["repo"]) == real(repo):
            out.add(str(real(meta["folder"])))
    return out


def exists(repo: str, ref: str) -> bool:
    return bool(ref) and git(repo, "rev-parse", "-q", "--verify", f"refs/heads/{ref}").returncode == 0


def base_of(repo: str, wanted: str = "") -> str:
    """The branch a worktree's work goes back into: the one it was made from when that is known and still there, else
    the branch the main checkout is on, else main or master."""
    if exists(repo, wanted):
        return wanted
    main = git(repo, "symbolic-ref", "-q", "--short", "HEAD").stdout.strip()
    if main:
        return main
    return next((b for b in ("main", "master") if exists(repo, b)), "")


def uncommitted(folder) -> list:
    """The files git would lose with the checkout: changed, staged or untracked (ignored ones are rebuilt or linked)."""
    if off_limits(folder) or not Path(folder).is_dir():
        return []
    result = git(folder, "status", "--porcelain", "--untracked-files=all")
    if result.returncode != 0:
        return []
    return [line[3:].split(" -> ")[-1].strip('"') for line in result.stdout.splitlines() if len(line) > 3]


def _start_of(repo: str, branch: str, known: str) -> str:
    """The commit a branch was made at: kept with the session, else the oldest entry of the branch's reflog."""
    if known:
        return known
    log = git(repo, "reflog", "show", "--format=%H", f"refs/heads/{branch}").stdout.split()
    return log[-1] if log else ""


def facts(repo: str, branch: str, base: str = "", start: str = "", folder: str = "", cached: bool = False, ttl: float = FACTS_TTL) -> dict:
    """What a worktree's branch holds against its base, and what its checkout has uncommitted. The sidebar's poll takes
    it cached briefly; anything a person acts on asks git again."""
    key = (repo, branch, base, start, folder)
    with _cache_lock:
        hit = _cache.get(key)
        if cached and hit and time.time() - hit[0] < ttl:
            return dict(hit[1])
    out = {"branch": branch, "base": "", "ahead": 0, "behind": 0, "merged": False, "fresh": False, "changed": 0, "files": [],
           "checkout": bool(folder) and Path(folder).is_dir()}
    if branch and exists(repo, branch):
        out["base"] = base = base_of(repo, base)
        tip = git(repo, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").stdout.strip()
        if base and base != branch:
            counts = git(repo, "rev-list", "--left-right", "--count", f"{base}...{branch}").stdout.split()
            if len(counts) == 2 and all(c.isdigit() for c in counts):
                out["behind"], out["ahead"] = int(counts[0]), int(counts[1])
            first = _start_of(repo, branch, start)
            out["fresh"] = out["ahead"] == 0 and bool(first) and tip == first
            if out["ahead"] == 0:
                out["merged"] = not out["fresh"]
            else:
                # Rebased or cherry-picked onto the base: every commit has an equal one there.
                cherry = git(repo, "cherry", base, branch).stdout.split("\n")
                lines = [c for c in cherry if c.strip()]
                out["merged"] = bool(lines) and all(c.startswith("-") for c in lines)
    elif branch:
        out["branch"], out["missing"] = branch, True
    if out["checkout"]:
        files = uncommitted(folder)
        out["changed"], out["files"] = len(files), files[:20]
    with _cache_lock:
        _cache[key] = (time.time(), dict(out))
    return out


def _metas() -> list:
    import hub_data as hub
    out = []
    for path in hub.META.glob("*.json"):
        try:
            out.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    return out


def session_tree(meta: dict, cached: bool = False, alive: bool = True):
    """The worktree facts a session's row carries, or None for a session in its project's own folder."""
    folder = meta.get("folder") or ""
    repo = meta.get("repo") or ""
    if not meta.get("isolate") or not folder or not repo or off_limits(repo) or not Path(repo).is_dir():
        return None
    made = meta.get("tree") if isinstance(meta.get("tree"), dict) else {}
    if not (real(folder).parent == real(Path(repo) / TREES) or Path(folder).parent == Path(repo) / TREES or made.get("placed")):
        return None
    branch = made.get("branch") or ""
    if not branch and Path(folder).is_dir():
        branch = git(folder, "symbolic-ref", "-q", "--short", "HEAD").stdout.strip()
    branch = branch or f"hub/{Path(folder).name}"
    out = facts(repo, branch, made.get("base", ""), made.get("start", ""), folder if Path(folder).is_dir() else "", cached, FACTS_TTL if alive else IDLE_TTL)
    out["files"] = out["files"][:12]
    out["path"] = tilde(folder)
    return out


def project_trees(name: str) -> dict:
    """Every worktree checkout of a project's folders, and every branch made for one whose checkout is gone, with the
    session that used it."""
    import hub_data as hub
    store = hub.store_of(name)
    metas = [m for m in _metas() if m.get("project") == name]
    alive = hub.tmux_sessions()
    by_folder = {str(real(m["folder"])): m for m in metas if m.get("isolate") and m.get("folder")}
    by_branch = {(m.get("tree") or {}).get("branch") or f"hub/{Path(m['folder']).name}": m for m in metas if m.get("isolate") and m.get("folder")}

    def who(meta):
        if not meta:
            return None
        live = f"hub-{meta['id']}" in alive
        return {"id": meta["id"], "title": meta.get("title", ""), "alive": live, "closing": bool(meta.get("closing")),
                "closed": bool(meta.get("closed"))}

    repos = []
    for repo in hub.repos_of(store):
        entry = {"repo": tilde(repo), "name": Path(repo).name, "rows": []}
        if off_limits(repo):
            entry["noVcs"] = True
            repos.append(entry)
            continue
        if not (Path(repo) / ".git").exists():
            continue
        checked_out = set()
        for wt in listing(repo)[1:]:
            checked_out.add(wt["branch"])
            if not inside_trees(repo, wt["path"]):
                continue
            meta = by_folder.get(str(real(wt["path"])))
            made = (meta or {}).get("tree") or {}
            row = facts(repo, wt["branch"], made.get("base", ""), made.get("start", ""), "" if wt["prunable"] else wt["path"])
            row.update(path=tilde(wt["path"]), folder=Path(wt["path"]).name, detached=wt["detached"], locked=wt["locked"],
                       stale=wt["prunable"], session=who(meta))
            entry["rows"].append(row)
        for main in listing(repo)[:1]:
            checked_out.add(main["branch"])
        branches = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/hub/", "refs/heads/worktree-*").stdout.split()
        for branch in [b for b in branches if b not in checked_out][:60]:
            meta = by_branch.get(branch)
            made = (meta or {}).get("tree") or {}
            row = facts(repo, branch, made.get("base", ""), made.get("start", ""))
            row.update(path=None, folder="", detached=False, locked=False, stale=False, session=who(meta))
            entry["rows"].append(row)
        entry["rows"].sort(key=lambda r: (r["path"] is None, not (r["session"] or {}).get("alive"), r["branch"]))
        repos.append(entry)
    return {"repos": repos}


# ── changing ──
def _repo_in(name: str, body: dict) -> str:
    import hub_data as hub
    wanted = body.get("repo") if isinstance(body, dict) else None
    if not isinstance(wanted, str) or not wanted.strip():
        raise Malformed("Say which folder.")
    wanted = os.path.expanduser(wanted)
    for repo in hub.repos_of(hub.store_of(name)):
        if real(repo) == real(wanted):
            if off_limits(repo):
                raise Refused(f"The hub never runs git in {Path(repo).name} (no_vcs in its settings).")
            return repo
    raise Refused("That folder isn't part of this project.")


def _checkout(repo: str, path) -> dict:
    """The worktree at a path, checked: listed by git for this repo, inside its .claude/worktrees, never the main one."""
    if not isinstance(path, str) or not path.strip():
        raise Malformed("Say which checkout.")
    path = os.path.expanduser(path)
    if not inside_trees(repo, path):
        raise Refused("The hub only removes checkouts in the project's .claude/worktrees folder.")
    listed = listing(repo)
    if listed and real(listed[0]["path"]) == real(path):
        raise Refused("That is the project's main checkout, which the hub never removes.")
    for wt in listed[1:]:
        if real(wt["path"]) == real(path) or (wt["prunable"] and Path(wt["path"]) == Path(path)):
            return wt
    raise Refused("Git doesn't list that folder as a worktree of this project.")


def _in_use(path, but: str = "") -> dict:
    """A hub session that still runs, or is closing, in this checkout. `but`: the session whose close is removing it."""
    import hub_data as hub
    alive = hub.tmux_sessions()
    for meta in _metas():
        folder = meta.get("folder")
        if meta.get("id") != but and folder and real(folder) == real(path) and (f"hub-{meta['id']}" in alive or meta.get("closing")):
            return meta
    return {}


def remove_checkout(repo: str, path: str, force: bool = False, expect=None, but: str = "") -> dict:
    """`git worktree remove` for one checkout. The branch stays. With uncommitted files it needs force, and expect: the
    number of files the person was shown, so a change since then stops it."""
    wt = _checkout(repo, path)
    using = _in_use(wt["path"], but)
    if using:
        raise Refused(f"“{using.get('title', 'A session')}” is still running in this checkout. Close it first.")
    if wt["locked"]:
        raise Refused("Git has this checkout locked, so the hub leaves it alone.")
    if wt["prunable"] or not Path(wt["path"]).is_dir():
        git(repo, "worktree", "prune")
        forget()
        return {"removed": tilde(wt["path"]), "branch": wt["branch"], "lost": 0}
    files = uncommitted(wt["path"])
    if files and not force:
        raise Refused(f"This checkout has {len(files)} uncommitted {'file' if len(files) == 1 else 'files'}. Removing it loses {'it' if len(files) == 1 else 'them'}.",
                      dirty=len(files), files=files[:20])
    if files and expect != len(files):
        raise Refused("The uncommitted files changed since you looked. Look again before you remove it.", dirty=len(files), files=files[:20])
    result = git(repo, "worktree", "remove", *(["--force"] if files else []), wt["path"], timeout=60)
    if result.returncode != 0:
        raise Refused("Git didn't remove it: " + (result.stderr.strip() or result.stdout.strip())[:200])
    forget()
    return {"removed": tilde(wt["path"]), "branch": wt["branch"], "lost": len(files)}


def delete_branch(repo: str, branch: str, force: bool = False, expect=None) -> dict:
    """Delete a worktree's branch. Merged ones go; one with unmerged commits only with force and expect, the number of
    commits the person agreed to give up."""
    if not isinstance(branch, str) or not OURS.match(branch):
        raise Refused("The hub only deletes branches it or Claude made for a worktree (hub/… or worktree-…).")
    if not exists(repo, branch):
        raise Refused("That branch isn't there any more.")
    listed = listing(repo)
    if any(wt["branch"] == branch for wt in listed):
        raise Refused("That branch is checked out. Remove its checkout first.")
    row = facts(repo, branch)
    if branch == row["base"]:
        raise Refused("That is the branch its work goes back into.")
    if not row["merged"] and not row["fresh"]:
        if not force:
            raise Refused(f"{branch} has {row['ahead']} {'commit' if row['ahead'] == 1 else 'commits'} that aren't in {row['base'] or 'its base'}.", ahead=row["ahead"])
        if expect != row["ahead"]:
            raise Refused("The branch changed since you looked. Look again before you delete it.", ahead=row["ahead"])
    tip = git(repo, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").stdout.strip()
    result = git(repo, "branch", "-D", branch)  # OURS: it starts hub/ or worktree-, never with a dash
    if result.returncode != 0:
        raise Refused("Git didn't delete it: " + (result.stderr.strip() or result.stdout.strip())[:200])
    forget()
    return {"deleted": branch, "tip": tip[:12], "lost": 0 if row["merged"] or row["fresh"] else row["ahead"]}


def after_close(meta: dict) -> dict:
    """At the end of a close that was asked to remove its checkout: remove it when nothing is uncommitted, and say what
    is left when something is. Never forced: losing files is asked of the person, again, after the close."""
    folder, repo = meta.get("folder") or "", meta.get("repo") or ""
    if not meta.get("isolate") or not folder or not repo or off_limits(repo) or off_limits(folder):
        return {}
    branch = ((meta.get("tree") or {}).get("branch")) or (git(folder, "symbolic-ref", "-q", "--short", "HEAD").stdout.strip() if Path(folder).is_dir() else "")
    try:
        _checkout(repo, folder)
    except Refused as why:
        return {"kept": True, "why": str(why), "branch": branch}
    files = uncommitted(folder)
    if files:
        return {"kept": True, "changed": len(files), "files": files[:12], "branch": branch, "path": tilde(folder)}
    try:
        done = remove_checkout(repo, folder, but=meta.get("id", ""))
    except Refused as why:
        return {"kept": True, "why": str(why), "branch": branch, "path": tilde(folder)}
    return {"removed": True, "branch": done["branch"] or branch, "path": done["removed"]}


# ── the routes: owner-only like every route, by server.py's check ──
def route_list(name: str) -> dict:
    return project_trees(name)


def route_remove(name: str, body: dict) -> dict:
    repo = _repo_in(name, body)
    force = body.get("force") is True
    expect = body.get("expect")
    return remove_checkout(repo, body.get("path"), force, expect if isinstance(expect, int) and not isinstance(expect, bool) else None)


def route_branch(name: str, body: dict) -> dict:
    repo = _repo_in(name, body)
    force = body.get("force") is True
    expect = body.get("expect")
    return delete_branch(repo, body.get("branch"), force, expect if isinstance(expect, int) and not isinstance(expect, bool) else None)


def clean_plan(name: str) -> dict:
    """What "Clean up merged" would do: for each merged branch, remove its checkout (when clean and not in use) and
    delete the branch. What it leaves, and why."""
    plan, skip = [], []
    for entry in project_trees(name)["repos"]:
        if entry.get("noVcs"):
            continue
        for row in entry["rows"]:
            if not row.get("merged"):
                continue
            item = {"repo": entry["repo"], "branch": row["branch"], "path": row["path"], "key": f"{entry['repo']}|{row['path'] or ''}|{row['branch']}"}
            session = row.get("session") or {}
            if session.get("alive") or session.get("closing"):
                skip.append({**item, "why": "Its session is still running."})
            elif row["path"] and row["changed"]:
                skip.append({**item, "why": f"{row['changed']} uncommitted {'file' if row['changed'] == 1 else 'files'}."})
            elif row.get("locked"):
                skip.append({**item, "why": "Git has it locked."})
            elif not OURS.match(row["branch"] or ""):
                skip.append({**item, "why": "Its branch wasn't made for a worktree."})
            else:
                plan.append(item)
    return {"plan": plan, "skip": skip}


def route_clean(name: str, body: dict) -> dict:
    """Without "keys", the preview. With the keys the person saw, each one is checked again and done."""
    keys = body.get("keys")
    if keys is None:
        return clean_plan(name)
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise Malformed("Say which ones.")
    fresh = {item["key"]: item for item in clean_plan(name)["plan"]}
    done, left = [], []
    for key in keys[:100]:
        item = fresh.get(key)
        if not item:
            left.append({"key": key, "why": "It changed since the preview."})
            continue
        try:
            repo = _repo_in(name, {"repo": item["repo"]})
            if item["path"]:
                remove_checkout(repo, item["path"])
            delete_branch(repo, item["branch"])
            done.append(item)
        except Refused as why:
            left.append({**item, "why": str(why)})
    return {"done": done, "left": left}
