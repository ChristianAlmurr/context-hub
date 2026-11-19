#!/usr/bin/env python3
"""The fixer's runner: the needs the person approved, put right one at a time by Claude in a worktree of their own.

  python3 scripts/fix.py count   how many needs are approved and wait for the fixer (run-fix.sh asks before it takes the lock)
  python3 scripts/fix.py run     the run itself; run-fix.sh starts it, holding the store's run lock on fd 9, with AGENT_MEMORY_DIR set

The kit's own, run from the kit and never from a repository's copy: run-fix.sh is the one way in, so a failure always alerts.

What the script does and what Claude does. Claude only judges and edits: for each approved need it is started in a
fresh git worktree of the target repository, on a new branch fix/<date>-<words>, with fixer.md as its instructions,
the narrowest permissions that let it work (claude_args(), settings()) and a time limit. Everything around it is
code here: which repository (the need's own, or the one its words name, or none), whether the fixer may work there
at all (needs.off_limits(), read from files before any git runs there), the worktree, the state in needs.json
(approved, fixing, then fixed or stopped, each committed under the store's lock), the checks of what it left
(check()), the merge, and cleaning up.

The merge. The branch is fast-forwarded into the repository's checked-out branch only when nothing could be lost or
disturbed by it: no other branch or tag of the repository changed while the fixer worked (refs(); if one did, the
person is alerted), and (unmerged()) the repository is still on the branch the fix was made from, that branch has not moved,
its tracked files have no changes and no untracked file stands where the fix writes, and no Claude Code process is
working in the repository or one of its worktrees (live(): the processes' working folders, from lsof). When the
answer can't be known it is no. A branch that is not merged is kept and named; a merged one is deleted. The worktree
is always removed.

What the person hears. Each need ends fixed (merged, or on a branch with why not) or stopped (with the fixer's
paragraph, or the runner's reason). A run in which a need could not be dealt with as it should (no result, a run
over its time, a check that refused the branch, a merge or cleanup that failed) sends one alert through the store's
notify.sh. The run's last line goes into <store>.fix.json in the kit's state folder, for `amk status`.
"""
import datetime, json, os, re, shutil, signal, subprocess, sys
from pathlib import Path

import archive
import memcheck
import needs
import redact

MEM = memcheck.MEM
KIT = Path(__file__).resolve().parent.parent
CAP = 5  # needs one run takes at most; the rest wait for the next run
MINUTES = float(os.environ.get("AGENT_MEMORY_FIX_MINUTES") or 30)  # one need's time limit; a fraction is for tests
MODEL = os.environ.get("AGENT_MEMORY_FIX_MODEL") or "opus"
TURNS = 200
MAX_FILES, MAX_LINES = 8, 300  # what a small fix changes at most; a branch bigger than this is not merged
OLDEST = (2, 1, 259)  # the first Claude Code with --restricted (2.1.248) and --permission-prompts (2.1.259)
TOOLS = "Bash,Read,Edit,Write,Glob,Grep"
GIT_SECONDS = 60
SECRET_FILE = re.compile(r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx|keystore)|id_(rsa|ed25519|ecdsa)(\.pub)?|\.netrc|\.npmrc|\.pypirc|credentials(\.\w+)?|secrets?(\.\w+)?)$", re.I)
GIT_FILE = re.compile(r"(^|/)\.git(attributes|modules)$")
ATTRIBUTION = re.compile(r"co-authored-by:.*(claude|anthropic)|claude-session:|generated with \[?claude", re.I)
DENY = ["WebFetch", "WebSearch", "Agent", "Task", "NotebookEdit",
        "Bash(git push *)", "Bash(git push)", "Bash(git fetch *)", "Bash(git fetch)", "Bash(git pull *)", "Bash(git pull)", "Bash(git clone *)",
        "Bash(git remote *)", "Bash(git config *)", "Bash(git worktree *)", "Bash(git switch *)", "Bash(git checkout -b *)", "Bash(git branch *)",
        "Bash(git -C *)", "Bash(git submodule *)", "Bash(sudo *)", "Bash(launchctl *)", "Bash(curl *)", "Bash(wget *)", "Bash(ssh *)", "Bash(scp *)",
        "Bash(rsync *)", "Bash(open *)", "Bash(osascript *)", "Bash(security *)", "Bash(chflags *)", "Bash(amk *)", "Bash(npm install *)", "Bash(npm i *)",
        "Bash(pip install *)", "Bash(pip3 install *)", "Bash(brew *)", "Bash(python3 scripts/memwrite.py *)", "Bash(python3 scripts/dream_proposal.py *)",
        "Bash(vercel *)", "Bash(gh *)", "Bash(supabase *)", "Bash(docker *)", "Bash(kubectl *)", "Bash(terraform *)", "Bash(fly *)", "Bash(netlify *)"]
PRIVATE = ["~/.ssh", "~/.aws", "~/.gnupg", "~/.config", "~/agent-memory", "~/.netrc", "~/Library/Keychains", "~/.claude", "~/.local/state"]

now = archive.now


def git(where, *args, check=False):
    """git in one folder, with nothing from the caller's environment pointing it elsewhere, no hooks of its own and no
    fsmonitor: nothing a repository's config names is run by the runner, which is not in the fixer's sandbox."""
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    found = subprocess.run(["git", "-C", str(where), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *args],
                           capture_output=True, text=True, env=environment, timeout=GIT_SECONDS)
    if check and found.returncode != 0:
        raise Stop(f"git {args[0]} failed: {' '.join(found.stderr.split())[:200]}", alert=True)
    return found


class Stop(Exception):
    """A need the runner stops on, with the reason the person reads. `alert`: it went wrong, rather than being a judgement."""

    def __init__(self, why: str, alert=False):
        super().__init__(why)
        self.alert = alert


def plain(text: str, limit: int = 600) -> str:
    """Words from the fixer, fit for needs.json and a terminal: one line, no control characters, nothing this store never keeps."""
    text = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", str(text)).split())[:limit]
    if redact.credential(text) or redact.refused(text, redact.rules(MEM)):
        return "[the fixer's words held what this store never keeps, so they are not shown]"
    return text


def repo_for(entry: dict):
    """The repository a need is about: the one it names; for a need that names none, the store's only repository, or the
    one whose folder its words name. None when that can't be told."""
    if entry.get("repo"):
        return needs.repo_named(MEM, entry["repo"])
    roots = needs.roots(MEM)
    if len(roots) == 1:
        return roots[0]
    words = set(re.findall(r"[\w.-]+", entry["text"].casefold()))
    named = [path for path in roots if path.name.casefold() in words]
    return named[0] if len(named) == 1 else None


def slug(entry: dict) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", entry["key"])[:4])[:40] or "need"


def claude_path() -> str:
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")


def version_ok(claude: str) -> str:
    """Why this Claude Code can't run the fixer as it must, or empty."""
    try:
        said = subprocess.run([claude, "--version"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"Claude Code could not be started ({type(error).__name__})"
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", said)
    if not found or tuple(map(int, found.groups())) < OLDEST:
        return f"Claude Code {found[0] if found else '(version unknown)'} is older than {'.'.join(map(str, OLDEST))}, which the fixer needs for its restricted, sandboxed run"
    return ""


def settings(tree: Path, out: Path, guarded=()) -> dict:
    """What the fixer's Claude is allowed, beside --restricted (no user, project or local settings; file tools only in the working folders).

    Bash runs in the sandbox (Seatbelt on macOS): it writes only in the worktree, its result folder and the temporary folder,
    has no network (no domain is allowed, and dontAsk refuses one that is not), can't run a command outside the sandbox
    (allowUnsandboxedCommands false), and the run ends rather than goes on unsandboxed if the sandbox can't start
    (failIfUnavailable). It reads none of the private folders, but its own two (allowRead: the worktree lives under
    ~/.local/state). A worktree's sandbox may also write the repository's shared git folder, all but its hooks and config
    (Claude Code's own rule), so it can commit: `guarded` (protected()) are the paths there it may not write, so the owner's
    branches, tags and HEAD stay as they are. File edits are allowed in the worktree and the result file only. No MCP server
    and no claude.ai connector is loaded (--strict-mcp-config, disableClaudeAiConnectors).
    """
    return {"permissions": {"allow": [f"Edit(/{tree}/**)", f"Edit(/{out}/result.json)"], "deny": DENY, "defaultMode": "dontAsk"},
            "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True, "allowUnsandboxedCommands": False, "failIfUnavailable": True,
                        "network": {"allowedDomains": []},
                        "filesystem": {"denyRead": PRIVATE, "allowRead": [str(tree), str(out)], "denyWrite": [str(p) for p in guarded]}},
            "disableClaudeAiConnectors": True, "includeCoAuthoredBy": False, "attribution": {"commit": "", "pr": ""}}


def protected(repo: Path, tree: Path, name: str) -> list:
    """The paths of the repository's shared git folder the fixer's commands may not write: HEAD, packed-refs, info/, the
    tags, every branch's ref but its own, and the folders of the other worktrees. Its own branch and worktree it needs."""
    common = needs.common_dir(repo)
    if common is None:
        raise Stop(f"{repo}'s git folder could not be found", alert=True)
    try:
        said = (tree / ".git").read_text().strip()  # "gitdir: <common>/worktrees/<its folder>"
        own = (tree / said[len("gitdir: "):]).resolve()
    except OSError:
        raise Stop("its worktree has no .git file to read", alert=True)
    heads = [common / ref for ref in git(repo, "for-each-ref", "--format=%(refname)", "refs/heads", check=True).stdout.split() if ref != f"refs/heads/{name}"]
    others = [p for p in (common / "worktrees").iterdir() if p.resolve() != own] if (common / "worktrees").is_dir() else []
    return [common / "HEAD", common / "packed-refs", common / "info", common / "refs" / "tags", common / "modules", *heads, *others]


def refs(repo: Path, name: str) -> dict:
    """The repository's branches and tags but the fix's own, and what its HEAD says: to tell afterwards whether any moved."""
    found = dict(line.split(" ", 1) for line in git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads", "refs/tags").stdout.splitlines() if " " in line)
    found.pop(f"refs/heads/{name}", None)
    found["HEAD"] = git(repo, "symbolic-ref", "-q", "HEAD").stdout.strip() or git(repo, "rev-parse", "HEAD").stdout.strip()
    return found


def claude_args(claude: str, prompt: str, settings_file: Path, out: Path) -> list:
    return [claude, "-p", prompt, "--restricted", "--strict-mcp-config", "--tools", TOOLS, "--settings", str(settings_file), "--permission-mode", "dontAsk",
            "--permission-prompts", "none", "--model", MODEL, "--max-turns", str(TURNS), "--add-dir", str(out), "--no-session-persistence"]


def prompt_for(entry: dict, repo: Path, branch: str, base: str, result: Path) -> str:
    sentence, _, rest = entry["text"].partition(needs.EVIDENCE)
    evidence = re.split(re.escape(needs.FIX) + "|" + re.escape(needs.YOURS), rest)[0]
    change = entry.get("change") or "not said: work it out from the need, and stop if it is not one small, clear change"
    text = (KIT / "fixer.md").read_text()
    for name, value in (("NEED", sentence), ("EVIDENCE", evidence or "none given"), ("CHANGE", change), ("FROM", entry["from"]), ("REPO", str(repo)),
                        ("BRANCH", branch), ("BASE", base), ("RESULT", str(result))):
        text = text.replace(f"<<{name}>>", " ".join(value.replace("```", "'''").split()))
    return text


def run_claude(args: list, tree: Path, result: Path, log) -> str:
    """Start Claude in the worktree and wait for it, MINUTES at most. Returns why it failed, or empty."""
    environment = {k: v for k, v in os.environ.items() if k not in ("AGENT_MEMORY_DIR", "AGENT_MEMORY_FROM_KIT") and not k.startswith("GIT_")}
    environment.update(AGENT_MEMORY_PROPOSE_ONLY="1", CLAUDE_CODE_DISABLE_AUTO_MEMORY="1", ENABLE_CLAUDEAI_MCP_SERVERS="false", AGENT_MEMORY_FIX_RESULT=str(result))
    log.flush()
    process = subprocess.Popen(args, cwd=tree, env=environment, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        code = process.wait(timeout=MINUTES * 60)
    except subprocess.TimeoutExpired:
        for sent in (signal.SIGTERM, signal.SIGKILL):  # its own process group, which it was started in: nothing else is touched
            try:
                os.killpg(process.pid, sent)
                process.wait(timeout=10)
                break
            except (ProcessLookupError, subprocess.TimeoutExpired):
                continue
        return f"it ran past its time limit of {MINUTES:g} minutes and was stopped"
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)  # whatever it left running in its group (a server, a watcher) ends with it
        except (ProcessLookupError, PermissionError):
            pass
    return "" if code == 0 else f"Claude exited with {code}"


def read_result(path: Path):
    """The fixer's result, or None when it is missing or not in its shape."""
    try:
        found = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    good = (isinstance(found, dict) and set(found) == {"result", "summary", "changed", "checked"} and found["result"] in ("fixed", "stopped")
            and isinstance(found["summary"], str) and found["summary"].strip() and isinstance(found["checked"], str)
            and isinstance(found["changed"], list) and all(isinstance(p, str) for p in found["changed"]))
    return found if good else None


def check(repo: Path, tree: Path, base: str, branch: str) -> str:
    """What is wrong with what the fixer left on its branch, or empty: something left uncommitted, no commit, a path that
    is a link or a secret's file, more than a small fix, a line that looks like a credential or that the store refuses,
    a commit message that names Claude."""
    left = git(tree, "status", "--porcelain").stdout.strip()
    if left:
        return "it left changes it did not commit"
    commits = git(repo, "rev-list", f"{base}..{branch}").stdout.split()
    if not commits:
        return "it said it fixed it and committed nothing"
    raw = git(repo, "diff", "--raw", "--no-renames", base, branch).stdout.splitlines()
    paths = [line.split("\t", 1)[1] for line in raw if "\t" in line]
    if any(line.split()[1] == "120000" for line in raw if len(line.split()) > 1):
        return "it committed a symbolic link"
    if any(line.split()[1] == "160000" for line in raw if len(line.split()) > 1):
        return "it committed a submodule"
    if any(SECRET_FILE.search(p) for p in paths):
        return "it changed a file that holds secrets by its name"
    if any(GIT_FILE.search(p) for p in paths):
        return "it changed a file that tells git how to treat others (.gitattributes, .gitmodules)"
    if any(p.startswith("/") or ".." in Path(p).parts for p in paths):
        return "it committed a path outside the repository"
    counted = [line.split("\t") for line in git(repo, "diff", "--no-ext-diff", "--no-textconv", "--numstat", base, branch).stdout.splitlines()]
    lines = sum(int(n) for row in counted for n in row[:2] if n.isdigit())
    if len(paths) > MAX_FILES or lines > MAX_LINES:
        return f"it changed {len(paths)} files and {lines} lines, more than a small fix ({MAX_FILES} files, {MAX_LINES} lines)"
    added = [line[1:] for line in git(repo, "diff", "--no-ext-diff", "--no-textconv", "-U0", base, branch).stdout.splitlines() if line.startswith("+") and not line.startswith("+++")]
    rules = redact.rules(MEM)
    if any(redact.credential(line) for line in added):
        return "a line it added looks like a credential"
    if any(redact.refused(line, rules) for line in added):
        return "a line it added is what this store's reject.txt refuses"
    if ATTRIBUTION.search(git(repo, "log", "--format=%B", f"{base}..{branch}").stdout):
        return "its commit message names Claude, and this repository may be public"
    return ""


def worktrees(repo: Path) -> list:
    return [Path(line[len("worktree "):]) for line in git(repo, "worktree", "list", "--porcelain").stdout.splitlines() if line.startswith("worktree ")]


def live(repo: Path):
    """Whether a Claude Code process is working in the repository or one of its worktrees: True, False, or None when it can't be told.

    From the working folder of each process of this user (lsof, which only reads) and what it was started as (ps). No process
    is matched by a pattern of its command line, and none is touched."""
    places = [p.resolve() for p in [repo] + worktrees(repo)]
    try:
        found = subprocess.run(["lsof", "-a", "-u", str(os.getuid()), "-d", "cwd", "-Fpn", "-w"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if found.returncode not in (0, 1) or found.stderr.strip() or (found.returncode == 1 and found.stdout.strip()):
        return None
    pids, pid = [], None
    for line in found.stdout.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("n") and pid and pid != str(os.getpid()):
            where = Path(line[1:])
            if any(where == p or p in where.parents for p in places):
                pids.append(pid)
    if not pids:
        return False
    try:
        listed = subprocess.run(["ps", "-o", "args=", "-p", ",".join(pids)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for args in listed.stdout.splitlines():
        words = args.split()
        first = words[0] if words else ""
        if os.path.basename(first) == "claude" or "/claude/versions/" in first or (os.path.basename(first) == "node" and "claude-code" in args):
            return True
    return False


def unmerged(repo: Path, start_branch: str, base: str, branch: str) -> str:
    """Why the fix branch is not merged into the repository's checked-out branch, or empty when it can be."""
    if not start_branch:
        return "the repository had no branch checked out when the fix was made"
    now_on = git(repo, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip()
    if now_on != start_branch:
        return f"the repository is now on {now_on or 'no branch'}, not {start_branch}"
    if git(repo, "rev-parse", "HEAD").stdout.strip() != base:
        return f"{start_branch} has moved since the fix was made"
    if git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        return "the repository has changes that are not committed"
    written = git(repo, "diff", "--name-only", base, branch).stdout.splitlines()
    if any((repo / p).exists() and git(repo, "ls-files", "--error-unmatch", "--", p).returncode != 0 for p in written):
        return "an untracked file stands where the fix writes"
    alive = live(repo)
    if alive is None:
        return "it can't be told whether a Claude session is working in it"
    if alive:
        return "a Claude session is working in it"
    return ""


def log_path() -> Path:
    return archive.state() / f"fix-{MEM.name}.log"


def one(entry: dict, claude: str, log) -> dict:
    """Fix one approved need. Returns {"state", "result", "alert"}: what is recorded, and whether the person is alerted.
    Empty when the need is no longer approved by the time the run gets to it (the person changed it)."""
    at, tree, folder, name, base = now(), None, None, "", ""
    result = lambda summary, branch="", merged="", kept="": {"at": int(now()), "summary": summary, "branch": branch, "merged": merged, "kept": kept}
    repo = repo_for(entry)
    if repo is None:
        return {"state": "stopped", "result": result(f"it doesn't say which repository it is about, and its words name none of {', '.join(p.name for p in needs.roots(MEM))} alone. "
                                                     "Deal with it yourself, or have a dream say it again with its repository"), "alert": False}
    why = needs.off_limits(repo)
    if why:
        return {"state": "stopped", "result": result(f"{repo.name} {why}: this one is yours"), "alert": False}
    if not needs.move(MEM, entry["key"], ("approved",), "fixing", message=f"needs: the fixer is at work on what {entry['from']} said needs the person"):
        return {}
    own = lambda: bool(name and base and git(repo, "rev-list", f"{base}..{name}").stdout.strip())  # the fix branch holds commits of its own
    try:
        if Path(git(repo, "rev-parse", "--show-toplevel", check=True).stdout.strip()).resolve() != repo.resolve():
            raise Stop(f"{repo} is inside another repository, not the top of one")
        start_branch = git(repo, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip()
        base = git(repo, "rev-parse", "HEAD", check=True).stdout.strip()
        day, count = datetime.date.fromtimestamp(at).isoformat(), 1
        while True:
            name = f"fix/{day}-{slug(entry)}" + (f"-{count}" if count > 1 else "")
            folder = archive.state() / "fix" / MEM.name / name.replace("/", "-")
            if git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{name}").returncode != 0 and not folder.exists():
                break
            count += 1
        tree, out = folder / "tree", folder / "out"
        out.mkdir(parents=True, mode=0o700)
        made = git(repo, "worktree", "add", "-q", "-b", name, str(tree), base)
        if made.returncode != 0:
            name = ""
            raise Stop(f"its worktree could not be made: {' '.join(made.stderr.split())[:200]}", alert=True)
        before = refs(repo, name)
        (folder / "settings.json").write_text(json.dumps(settings(tree, out, protected(repo, tree, name)), indent=1))
        print(f"{entry['text']}\n  in {repo}, on {name} from {start_branch or base[:12]}", file=log, flush=True)
        failed = run_claude(claude_args(claude, prompt_for(entry, repo, name, start_branch or base[:12], out / "result.json"), folder / "settings.json", out), tree, out / "result.json", log)
        said = read_result(out / "result.json")
        if said is None:
            raise Stop(("The fixer " + failed + ", and left no result" if failed else "The fixer left no result that could be read") + f". Log: {log_path()}", alert=True)
        if said["result"] == "stopped":
            raise Stop(plain(said["summary"]) + (f" (it left commits on {name}, which is kept)" if own() else ""), alert=own())
        wrong = check(repo, tree, base, name)
        if wrong:
            raise Stop(f"The fixer said it fixed it, but {wrong}. Its branch {name} is kept, not merged" if own() else f"The fixer said it fixed it, but {wrong}", alert=True)
        summary = plain(said["summary"], 300)
        remove(repo, tree)
        after = refs(repo, name)  # its branch it may move; the one it was made from the person may, and unmerged() says so
        moved = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k) and k not in ("HEAD", f"refs/heads/{start_branch}"))
        kept = f"other branches or tags changed while it worked ({', '.join(moved[:5])}): look at them first" if moved else unmerged(repo, start_branch, base, name)
        if not kept:
            merged = git(repo, "merge", "--ff-only", "-q", name)
            if merged.returncode == 0:
                git(repo, "branch", "-d", name)
                return {"state": "fixed", "result": result(summary, name, start_branch), "alert": False}
            kept = f"the fast-forward failed: {' '.join(merged.stderr.split())[:150]}"
        return {"state": "fixed", "result": result(summary, name, "", kept), "alert": bool(moved)}
    except Stop as stop:
        return {"state": "stopped", "result": result(str(stop), name if own() else ""), "alert": stop.alert}
    except (OSError, subprocess.SubprocessError) as error:
        return {"state": "stopped", "result": result(f"The runner failed: {type(error).__name__}: {plain(error, 200)}", name if own() else ""), "alert": True}
    finally:
        if tree is not None:
            remove(repo, tree)
        if name and base and not own() and git(repo, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip() != name:
            git(repo, "branch", "-D", name)  # nothing of its own on it, or merged and deleted already: nothing to keep
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)


def remove(repo: Path, tree: Path):
    if tree.exists():
        git(repo, "worktree", "remove", "--force", str(tree))
    git(repo, "worktree", "prune")


def alert(title: str, body: str):
    notify = MEM / "notify.sh"
    if os.access(notify, os.X_OK):
        sent = subprocess.run([str(notify), f"{title}: {MEM.name}", body], capture_output=True, text=True)
        if sent.returncode != 0:
            print(f"WARN: the alert could not be sent: {sent.stderr.strip()[:200]}", file=sys.stderr)


def remember(line: str):
    """The run's last line, for `amk status`: <store>.fix.json in the kit's state folder."""
    path = archive.state() / f"{MEM.name}.fix.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"at": int(now()), "line": line}) + "\n")
    os.replace(tmp, path)


def last_run(name: str):
    """{"at", "line"} of a store's last fixer run, or None."""
    try:
        found = json.loads((archive.state() / f"{name}.fix.json").read_text())
        return found if isinstance(found, dict) and isinstance(found.get("at"), int) and isinstance(found.get("line"), str) else None
    except (OSError, ValueError):
        return None


def run(log) -> int:
    """The whole run. 0 when every need was dealt with as it should be, 1 when the person was alerted."""
    problems = []
    for entry in [e for e in needs.load(MEM) if needs.state(e) == "fixing"]:  # a run that holds the lock is the only one: one left fixing was ended by force
        needs.move(MEM, entry["key"], ("fixing",), "stopped", {"at": int(now()), "summary": "The fixer's run that had it ended before it said how it went. Approve it again to try again",
                                                                "branch": "", "merged": "", "kept": ""})
        problems.append(f"a run ended before it said how \"{entry['text'][:80]}\" went")
    waiting = needs.approved(MEM)
    if not waiting:
        line = "nothing approved for the fixer"
        print(line, file=log)
        remember(line)
        if problems:
            alert("Fixer failed", "; ".join(problems))
        return 1 if problems else 0
    claude = claude_path()
    why = version_ok(claude)
    if why:
        alert("Fixer failed", f"{why}. Nothing was started; {len(waiting)} approved stay approved.")
        remember(f"not started: {why}")
        print(why, file=log)
        return 1
    counts = {"fixed": 0, "merged": 0, "stopped": 0}
    for entry in waiting[:CAP]:
        done = one(entry, claude, log)
        if not done:
            continue  # the person changed it while the run was getting to it
        if not needs.move(MEM, entry["key"], ("approved", "fixing"), done["state"], done["result"], f"needs: the fixer {done['state']} what {entry['from']} said needs the person"):
            print("  it was closed by the person while it was being fixed; what the fixer did is not recorded", file=log)
        counts[done["state"]] += 1
        counts["merged"] += bool(done["result"]["merged"])
        print(f"  {needs.status_words({'state': done['state'], 'result': done['result']})}", file=log, flush=True)
        if done["alert"]:
            problems.append(f"\"{entry['text'][:80]}\": {(done['result']['kept'] or done['result']['summary'])[:200]}")
    rest = max(0, len(waiting) - CAP)
    line = (f"{counts['fixed']} fixed ({counts['merged']} merged), {counts['stopped']} stopped" + (f"; {rest} wait for the next run" if rest else ""))
    print(line, file=log)
    remember(line)
    if problems:
        alert("Fixer failed", "; ".join(problems))
    return 1 if problems else 0


def main():
    if sys.argv[1:] == ["count"]:
        print(len(needs.approved(MEM)) + sum(needs.state(e) == "fixing" for e in needs.load(MEM)))  # one left fixing by a run that was killed is settled by the next
    elif sys.argv[1:] == ["run"]:
        sys.exit(run(sys.stdout))
    else:
        sys.exit("usage: fix.py count | run   (run-fix.sh is the way to run the fixer)")


if __name__ == "__main__":
    main()
