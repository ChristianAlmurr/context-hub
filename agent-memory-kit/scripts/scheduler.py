#!/usr/bin/env python3
"""The one scheduler: every hour it looks at every store that is on it, and starts at most one store's work.

  amk schedule run                      one hourly check (the launchd job ai.agent-memory.scheduler runs this)
  amk schedule enroll <store> <repo>    put a store on the scheduler (schedule-dream.sh does this)
  amk schedule drop <store>             take it off; prints how many stores are left on it
  amk schedule list                     the stores on it, one a line: name and repository

A dream is worth most right after a burst of work ends, and it must never compete with the owner's live
sessions or with another store's dream. So each hour this:

1. Takes the machine's slot, a lock in the kit's state folder, without waiting. While another check holds
   it, or a run is going anywhere (any store's run lock: an unattended dream or the fixer, started by this or
   by hand; or the run an earlier check started, which holds scheduler-run.lock until it ends), nothing
   starts: every store waits for the next hourly check. So one run at a time, for the machine.
2. Leaves out every store with a Claude Code session at work in one of its repositories or their worktrees
   (scripts/live.py: a Claude process working there, by lsof, as the fixer asks; or a transcript Claude Code
   kept for one of those folders that changed in the last IDLE_MINUTES).
3. Asks each other store's own check (dream_due.py, the same check run-dream.sh --if-due makes, with its
   reminders) whether a dream is due, and how many needs the person approved wait for the fixer. A store
   whose last dream started less than MIN_GAP_HOURS ago doesn't dream, whatever the counts. Every dream start
   counts, whoever made it: run-dream.sh records each one before it starts claude (note_start(), in
   dream-starts.json), by hand or from an app too. A start by hand is never held back by that; the scheduler's
   own decisions count it. A record of starts that can't be read starts nothing that hour, and the log says why.
4. Of the stores that may dream, starts the one with the most learning waiting (dream_due.priority(), from
   counts()), after its fixer when it has approved needs. When none may dream, a store with approved needs
   gets its fixer alone, at most once in MIN_GAP_HOURS. At most MAX_DREAMS_PER_DAY dreams start on one
   calendar day, for all stores together, counted the same way. Right before the start the chosen store is
   asked once more whether its owner is at work (the checks before can take minutes); if so, nothing starts.
   The start is on record (`started`) before anything runs. The run itself is a process of its own
   (`launch`, started detached, its output in scheduler-<store>.log): the fixer first, then the dream, one
   after the other. It holds scheduler-run.lock from its start to its end, so the check that started it ends
   at once and the next hourly checks see the run and wait.

5. Brings the error ledger of every store it did not ask in step 3 up to date (`refresh`: the store's session archive,
   then errors.update(), as the check does for the stores it asks), so the failure hook (error_context.py) is at most an
   hour behind, also for a store whose owner is at work. Mechanical, a process of its own per store, before anything
   starts: a dream started this hour can run for a long time.

A dream that hangs would hold every store back. run-dream.sh stops its claude after DREAM_MAX_MINUTES (120), and
that is a failed try with an alert. For what that can't reach, each hourly check that finds a store's run lock held
by a dream asks dream_try.py held for it, as run-dream.sh --if-due does: that starts nothing and alerts once a day
when the dream is the scheduler's own and a day old.

The check is mechanical: no model is asked anything until run-fix.sh or run-dream.sh starts one. Those keep
every rule of their own (the store's run lock, a person's dream that is alive, an open proposal, the back-off
after a failed try, the fixer's worktrees and repositories it may not work in), so the scheduler only decides
when to ask them.

What each store was told is kept in ~/.local/state/agent-memory/scheduler.json for `amk status`, with the
dreams and fixer runs it started (`started`, the newest KEPT), the last run it started (`launched`) and what came of
a store's last run (`run`, which the run writes when it ends). It logs to scheduler.log in the same folder.
The stores on it are in ~/.config/agent-memory/schedule.json: {"stores": {"<store>": {"repo": "<path>"}}}.

It binds no store as it loads: one process asks one store (`probe`, with AGENT_MEMORY_DIR), because every
reader of the kit serves the store it was started for.
"""
import contextlib, datetime, fcntl, json, math, os, subprocess, sys, time
from pathlib import Path

import live
import store

KIT = Path(__file__).resolve().parent.parent
LABEL = "ai.agent-memory.scheduler"
IDLE_MINUTES = 45  # a store dreams only when no Claude session has been at work in its repositories for this long
MIN_GAP_HOURS = 20  # at most one dream per store in this many hours, whatever the counts
MAX_DREAMS_PER_DAY = 4  # dreams started on one calendar day, all stores together; the rest wait
KEPT = 50  # starts remembered in scheduler.json
STARTS_KEPT_DAYS = 7  # every dream start run-dream.sh records (dream-starts.json) is kept this long: the gap and the day's count look back a day
PROBE_SECONDS = 600
REFRESH_SECONDS = 120  # one store's archive and ledger; a first archive run that takes longer goes on from where it stopped next hour
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def now() -> float:
    """AGENT_MEMORY_NOW replaces the clock, as for the rest of the kit (archive.now)."""
    text = os.environ.get("AGENT_MEMORY_NOW")
    if not text:
        return time.time()
    try:
        at = float(text)
    except ValueError:
        at = math.nan
    if not math.isfinite(at):
        raise SystemExit(f"AGENT_MEMORY_NOW is {text!r}, which is not a time in epoch seconds. It is only for tests: unset it.")
    return at


def state() -> Path:
    return Path.home() / ".local" / "state" / "agent-memory"


def config_file() -> Path:
    return Path.home() / ".config" / "agent-memory" / "schedule.json"


def record_file() -> Path:
    return state() / "scheduler.json"


def job_file() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def clock(at: float) -> str:
    d = datetime.datetime.fromtimestamp(at)
    return f"{d.day} {MONTHS[d.month - 1]} {d:%H:%M}"


def write_json(path: Path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.writing")
    with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as handle:
        handle.write(json.dumps(value, indent=1) + "\n")
    os.replace(tmp, path)


def config() -> dict:
    """The stores on the scheduler, {name: {"repo": path}}. No file: none. One that can't be read stops, in words."""
    path = config_file()
    try:
        found = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise SystemExit(f"{path} can't be read ({type(error).__name__}). Correct it, or move it away and put each store on again with schedule-dream.sh.")
    stores = found.get("stores") if isinstance(found, dict) else None
    if not (isinstance(stores, dict) and all(isinstance(v, dict) and isinstance(v.get("repo"), str) for v in stores.values())):
        raise SystemExit(f"{path} is not a schedule this version can read. Correct it, or move it away and put each store on again with schedule-dream.sh.")
    return stores


def enroll(name: str, repo: str):
    stores = config()
    if stores.get(name) != {"repo": repo}:
        stores[name] = {"repo": repo}
        write_json(config_file(), {"stores": stores})


def drop(name: str) -> int:
    stores = config()
    if name in stores:
        del stores[name]
        write_json(config_file(), {"stores": stores})
    return len(stores)


def record() -> dict:
    try:
        found = json.loads(record_file().read_text())
    except (OSError, ValueError):
        found = {}
    found = found if isinstance(found, dict) else {}
    started = [s for s in found.get("started") or [] if isinstance(s, dict) and isinstance(s.get("at"), (int, float)) and isinstance(s.get("store"), str)]
    stores = found.get("stores") if isinstance(found.get("stores"), dict) else {}
    launched = found.get("launched") if isinstance(found.get("launched"), dict) else None
    return {"at": found.get("at"), "line": found.get("line"), "stores": stores, "started": started, "launched": launched}


def lock_held(path: Path) -> bool:
    """Does a live process hold this lock? As dream_owner.lock_held(), for a store this process is not bound to."""
    try:
        handle = open(path)
    except FileNotFoundError:
        return False
    with handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def running_elsewhere() -> tuple:
    """(the store, words for it) of a run that is going: an unattended dream or the fixer, started by this or by hand (a store's run
    lock), or the run an earlier check started (run_lock(), held from its start to its end, the moment between its fixer and its
    dream included). ("", "") when none is: then, and only then, the machine's slot is free for a start."""
    for mem in store.stores():
        path = state() / f"{mem.name}.run.lock"
        if lock_held(path):
            try:
                fixer = path.read_text().split()[1:2] == ["fixer"]
            except OSError:
                fixer = False
            return mem.name, (f"the fixer is at work on {mem.name}" if fixer else f"a dream is running on {mem.name}")
    if lock_held(run_lock()):
        try:
            name = (run_lock().read_text().split() or [""])[0]
        except OSError:
            name = ""
        return name, f"the run the scheduler started on {name or 'a store'} is still going"
    return "", ""


def repos_of(mem: Path, repo: Path) -> list:
    path = mem / "roots.txt"
    found = [Path(line.strip()) for line in (path.read_text().splitlines() if path.exists() else []) if line.strip()]
    return found or [repo]


def worktrees(repo: Path) -> list:
    try:
        said = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"], capture_output=True, text=True, timeout=30,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [Path(line[len("worktree "):]) for line in said.stdout.splitlines() if line.startswith("worktree ")]


def busy(repos: list, folders, at: float) -> str:
    """Why a store must not dream now because its owner is at work, or empty."""
    places = []
    for repo in repos:
        if repo.is_dir():
            places += [repo] + [w for w in worktrees(repo) if w not in places]
    if not places:
        return ""
    alive = live.live(places, folders)
    if alive is None:
        return "it can't be told whether a Claude session is at work in its repositories"
    if alive:
        return "a Claude session is at work in its repositories"
    newest = live.newest_transcript(places)
    if newest is not None and at - newest < IDLE_MINUTES * 60:
        return (f"a session was at work {max(0, int((at - newest) // 60))} minutes ago; it dreams after {IDLE_MINUTES} quiet minutes")
    return ""


def probe() -> dict:
    """For one store, in a process of its own (AGENT_MEMORY_DIR): its check, with reminders, and what the scheduler needs beside it."""
    import dream_due
    import dream_try
    import needs
    found = dream_try.checked()
    kept = dream_due.load()
    starts = [t["at"] for t in kept["tries"]] + ([kept["last_dream"]] if kept["last_dream"] is not None else [])
    fix = len(needs.approved(dream_due.MEM)) + sum(needs.state(e) == "fixing" for e in needs.load(dream_due.MEM))
    # `last`: when its state says its last dream started (its tries, and up to when its last dream read); the check adds the starts on record (last_start()).
    return {"due": found["due"], "line": found["line"], "priority": found.get("priority", 0), "last": max(starts) if starts else None, "fix": fix}


def ask(name: str, mem: Path, repo: Path):
    """probe() for one store, in a process of its own. (answer, None) or (None, why it could not be asked)."""
    env = {k: v for k, v in os.environ.items() if k != "AGENT_MEMORY_FROM_KIT"}
    env.update(AGENT_MEMORY_DIR=str(mem))
    try:
        said = subprocess.run([sys.executable, str(Path(__file__).resolve()), "probe"], cwd=str(repo), env=env,
                              capture_output=True, text=True, timeout=PROBE_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, f"{type(error).__name__}"
    if said.returncode != 0:
        return None, " ".join((said.stderr.strip().splitlines() or ["it stopped with no word"])[-1:])[:300]
    try:
        return json.loads(said.stdout), None
    except ValueError:
        return None, "its answer could not be read"


def refresh():
    """For one store, in a process of its own (AGENT_MEMORY_DIR): its session archive and then its error ledger brought up to date.
    No check, no reminder, no state of the dream's written: only what the failure hook reads."""
    import archive
    import errors
    archive.update()
    errors.update()


def keep_up(mem: Path, repo: Path) -> str:
    """refresh() for one store, in a process of its own. Empty when done, else why not, for the log only: a ledger an hour
    older than it could be holds nothing back."""
    env = {k: v for k, v in os.environ.items() if k != "AGENT_MEMORY_FROM_KIT"}
    env.update(AGENT_MEMORY_DIR=str(mem))
    try:
        said = subprocess.run([sys.executable, str(Path(__file__).resolve()), "refresh"], cwd=str(repo), env=env,
                              capture_output=True, text=True, timeout=REFRESH_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        return type(error).__name__
    return "" if said.returncode == 0 else " ".join((said.stderr.strip().splitlines() or ["it stopped with no word"])[-1:])[:300]


def keep_all_up(stores: dict, asked: set):
    """The error ledger of every store on the scheduler that the check did not ask (its check already did it), said in the log when one can't be."""
    for name, entry in sorted(stores.items()):
        mem, repo = store.home() / name, Path(entry["repo"])
        if name in asked or not mem.is_dir() or not repo.is_dir():
            continue
        problem = keep_up(mem, repo)
        if problem:
            print(f"  {name}: its error ledger could not be brought up to date: {problem}", file=sys.stderr)


def run_script(script: str, repo: Path, option: str) -> tuple:
    """run-fix.sh or run-dream.sh for a store, as launchd would start it, and waits for it: for launch(). (exit code, its last line).
    AGENT_MEMORY_SCHEDULED tells run-dream.sh the start is the scheduler's, which it records as such (note_start())."""
    env = {k: v for k, v in os.environ.items() if k not in ("AGENT_MEMORY_DIR", "AGENT_MEMORY_FROM_KIT")}
    env.update(AGENT_MEMORY_SCHEDULED="1")
    said = subprocess.run(["/bin/sh", str(KIT / script), str(repo), option], cwd=str(repo), env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL)
    lines = [line for line in (said.stdout + said.stderr).splitlines() if line.strip()]
    return said.returncode, (lines[-1] if lines else "")


def tried_since(name: str, at: float) -> bool:
    """Whether run-dream.sh recorded a try of the store's at or after `at`: the dream started."""
    try:
        tries = json.loads((state() / f"{name}.json").read_text()).get("tries") or []
    except (OSError, ValueError, AttributeError):
        return False
    return bool(tries) and isinstance(tries[-1], dict) and isinstance(tries[-1].get("at"), (int, float)) and tries[-1]["at"] >= int(at)


def alert(mem: Path, title: str, body: str):
    notify = mem / "notify.sh"
    if os.access(notify, os.X_OK):
        subprocess.run([str(notify), f"{title}: {mem.name}", body], capture_output=True, text=True)


# ── every unattended dream's start, whoever started it ──

def starts_file() -> Path:
    return state() / "dream-starts.json"


def read_starts() -> list:
    """Every unattended dream start on record, [{store, at, by}], oldest first. None yet: []. A file that can't be read, or is not
    what this version writes, stops in words (SystemExit): the scheduler then starts nothing, as it can't tell what has run."""
    path = starts_file()
    try:
        found = json.loads(path.read_text())
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as error:
        raise SystemExit(f"{path} can't be read ({type(error).__name__}), so there is no telling which dreams have started")
    starts = found.get("starts") if isinstance(found, dict) else None
    if not (isinstance(starts, list) and all(isinstance(one, dict) and isinstance(one.get("store"), str) and type(one.get("at")) in (int, float)
                                             and math.isfinite(one["at"]) and isinstance(one.get("by"), str) for one in starts)):
        raise SystemExit(f"{path} is not a record of dream starts this version can read, so there is no telling which dreams have started")
    return starts


def note_start(name: str, by: str):
    """For run-dream.sh, by way of dream_try.py, right before it starts claude: a dream of this store starts now, `by` the scheduler,
    a daily job of the store's own (`due`), or a person or an app (`hand`). The scheduler counts every one toward MIN_GAP_HOURS and
    MAX_DREAMS_PER_DAY. One that can't be recorded stops the start (SystemExit, in words)."""
    at = int(now())
    folder = state()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(folder / ".dream-starts.lock", os.O_WRONLY | os.O_CREAT, 0o600), "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        starts = [one for one in read_starts() if one["at"] > at - STARTS_KEPT_DAYS * 86400]
        try:
            write_json(starts_file(), {"starts": starts + [{"store": name, "at": at, "by": by}]})
        except OSError as error:
            raise SystemExit(f"{starts_file()} can't be written ({type(error).__name__}: {error.strerror})")


def last_start(name: str, rec: dict, starts: list, probed=None):
    """When the store's last dream started, as far as anything says: the scheduler's own starts, every start run-dream.sh recorded
    (by hand too), and the store's own state (probe(): its tries, and up to when its last dream read). None when nothing does."""
    found = [s["at"] for s in rec["started"] if s["store"] == name and s.get("what") == "dream"]
    found += [s["at"] for s in starts if s["store"] == name]
    found += [probed] if probed is not None else []
    return max(found) if found else None


def dreams_on(day: datetime.date, rec: dict, starts: list) -> int:
    """Dreams started on that calendar day, all stores together: the scheduler's own, and every other start run-dream.sh recorded.
    A start of the scheduler's is in both, so run-dream.sh's record of it (`by` scheduler) is not counted twice."""
    return (sum(s.get("what") == "dream" and datetime.date.fromtimestamp(s["at"]) == day for s in rec["started"])
            + sum(s["by"] != "scheduler" and datetime.date.fromtimestamp(s["at"]) == day for s in starts))


# ── the run a check starts, which goes on after the check has ended ──

def run_lock() -> Path:
    """Held by the run the scheduler started (launch()) for as long as it runs: the fixer, the dream after it, and the moment between."""
    return state() / "scheduler-run.lock"


def run_log(name: str) -> Path:
    return state() / f"scheduler-{name}.log"


def launch(name: str, repo: Path, what: str, at: float) -> int:
    """The run one hourly check started for a store, in a process of its own that outlives the check: the fixer first when `what` has
    it, then the dream. It holds run_lock() the whole time (the check handed it its open file), so no later check starts anything
    beside it. What came of it goes to its log and into scheduler.json, beside what the last check said of the store (`run`)."""
    done = []
    if "fix" in what.split("+"):
        code, last = run_script("run-fix.sh", repo, "--if-approved")
        done.append(f"the fixer: {last or 'exit ' + str(code)}")
    if "dream" in what.split("+"):
        code, last = run_script("run-dream.sh", repo, "--if-due")
        if tried_since(name, at):
            done.append("dreamed" + ("" if code == 0 else ", and it failed: the store's alert says why"))
        else:
            done.append(f"no dream started: {last or 'exit ' + str(code)}")
    line = "; ".join(done)
    print(f"{clock(now())} {name}: {line}", flush=True)
    with record_locked():
        rec = record()
        rec["stores"].setdefault(name, {})["run"] = {"at": int(at), "line": line}
        write_json(record_file(), {k: rec.get(k) for k in ("at", "line", "stores", "started", "launched")})
    return 0


def start_run(name: str, repo: Path, what: str, at: float) -> str:
    """launch() for a store, detached: a session of its own, stdin closed, its output in the store's scheduler log, and run_lock()
    taken here and handed to it as an open file, so no later check can come between this one and the run. Empty, or why it did not start."""
    held = os.open(run_lock(), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return "a run the scheduler started is still going"
        os.ftruncate(held, 0)
        os.pwrite(held, f"{name} {what} {int(at)}\n".encode(), 0)
        env = {k: v for k, v in os.environ.items() if k not in ("AGENT_MEMORY_DIR", "AGENT_MEMORY_FROM_KIT")}
        try:
            with os.fdopen(os.open(run_log(name), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a") as log:
                subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "launch", name, str(repo), what, str(int(at))],
                                 cwd=str(repo), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                 start_new_session=True, pass_fds=(held,))
        except OSError as error:
            return f"{type(error).__name__}: {error}"
        return ""
    finally:
        os.close(held)  # the run holds the lock now, through its own copy of this open file


def still_running(mem: Path):
    """A dream holds the store's run lock. dream_try.py held, which run-dream.sh --if-due asks when it finds the lock held, says so when
    it is the scheduler's own try and has run for a day, once a day; that goes out as the store's alert. Nothing is started."""
    env = {k: v for k, v in os.environ.items() if k != "AGENT_MEMORY_FROM_KIT"}
    env.update(AGENT_MEMORY_DIR=str(mem))
    try:
        said = subprocess.run([sys.executable, str(KIT / "scripts" / "dream_try.py"), "held"], env=env, capture_output=True, text=True,
                              timeout=PROBE_SECONDS, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return
    if said.returncode == 0 and said.stdout.strip():
        alert(mem, "Dream still running", said.stdout.strip())


def tick() -> int:
    at = now()
    folder = state()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    slot = os.open(folder / "scheduler.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"{clock(at)} the slot is taken by another check: every store waits for the next hourly check")
        return 0
    os.ftruncate(slot, 0)
    os.pwrite(slot, f"{os.getpid()} {int(at)}\n".encode(), 0)
    stores = config()
    rec = record()
    said = {}
    held, other = running_elsewhere()
    if other:
        for name in stores:
            said[name] = f"waits: {other}"
        if held in stores and (store.home() / held).is_dir() and other.startswith("a dream"):
            # A dream holds the store's run lock. If it is the scheduler's own and has run for a day, the store's alert says so, once a
            # day. run-dream.sh stops its claude after DREAM_MAX_MINUTES, so this is for a run that hangs where that can't reach.
            still_running(store.home() / held)
        keep_all_up(stores, set())
        return finish(rec, at, said, f"{other}: every store waits for the next hourly check")
    try:
        starts = read_starts()
    except SystemExit as stop:
        for name in stores:
            said[name] = f"waits: {stop}"
        keep_all_up(stores, set())
        return finish(rec, at, said, f"nothing starts: {stop}. Correct it, or move it away, and the next check goes by what the stores' own files say")
    folders = live.claude_folders()
    ready, asked = [], set()
    for name, entry in sorted(stores.items()):
        mem, repo = store.home() / name, Path(entry["repo"])
        if not mem.is_dir() or not repo.is_dir():
            said[name] = f"its {'store ' + str(mem) if not mem.is_dir() else 'repository ' + str(repo)} is gone: run schedule-dream.sh <repo> --remove, or once more from a repository it has"
            continue
        why = busy(repos_of(mem, repo), folders, at)
        if why:
            said[name] = f"waits: {why}"
            continue
        answer, problem = ask(name, mem, repo)
        asked.add(name)
        if problem:
            said[name] = f"the check could not be made: {problem}"
            if (rec["stores"].get(name) or {}).get("line") != said[name]:  # said once, not every hour
                alert(mem, "Dream check failed", f"The hourly check could not tell whether a dream is due, so none was started: {problem}")
            continue
        last = last_start(name, rec, starts, answer.get("last"))
        gap = ""
        if last is not None and at - last < MIN_GAP_HOURS * 3600:
            gap = f"its last dream started {clock(last)}, and the next can start from {clock(last + MIN_GAP_HOURS * 3600)}"
        dream = answer["due"] and not gap
        said[name] = answer["line"] if not answer["due"] else f"waits: {answer['line'][len('due: '):]}, but {gap}" if gap else answer["line"]
        if dream or answer["fix"]:
            ready.append({"name": name, "mem": mem, "repo": repo, "dream": dream, **answer})
    if dreams_on(datetime.date.fromtimestamp(at), rec, starts) >= MAX_DREAMS_PER_DAY:
        for one in ready:
            if one["dream"]:
                one["dream"] = False
                said[one["name"]] = f"waits: {one['line'][len('due: '):]}, but {MAX_DREAMS_PER_DAY} dreams have started today, the most for one day"
    for one in ready:
        fixed = [s["at"] for s in rec["started"] if s["store"] == one["name"] and s.get("what") == "fix"]
        if one["fix"] and not one["dream"] and fixed and at - max(fixed) < MIN_GAP_HOURS * 3600:
            one["fix"] = 0  # the fixer alone runs once in MIN_GAP_HOURS: what it could not do waits for the store's next dream, or the next day
    keep_all_up(stores, asked)  # before anything starts, so no ledger is read while a run writes its store
    ready = [one for one in ready if one["dream"] or one["fix"]]
    ready.sort(key=lambda one: (not one["dream"], -one["priority"] if one["dream"] else 0, one["name"]))
    if not ready:
        return finish(rec, at, said, "nothing to start")
    chosen = ready[0]
    for one in ready[1:]:
        what = "a dream" if one["dream"] else "the fixer"
        said[one["name"]] = f"waits: {what} is due, after {chosen['name']}" + (" (more to learn there)" if one["dream"] and chosen["dream"] else "")
    name = chosen["name"]
    # Asked again right before the start: the checks above can take minutes, and the owner may have sat down since.
    why = busy(repos_of(chosen["mem"], chosen["repo"]), live.claude_folders(), now())
    if why:
        said[name] = f"waits: {why}"
        return finish(rec, at, said, f"nothing started: {name} was idle when it was checked, and is not now")
    what = "+".join((["fix"] if chosen["fix"] else []) + (["dream"] if chosen["dream"] else []))
    # On record before it starts, so it counts toward the gap and the day's dreams even if it never gets as far as run-dream.sh.
    rec["started"] += ([{"store": name, "at": int(at), "what": "fix"}] if chosen["fix"] else []) \
        + ([{"store": name, "at": int(at), "what": "dream"}] if chosen["dream"] else [])
    said[name] = ("started " + ", then ".join((["the fixer"] if chosen["fix"] else []) + ([f"a dream ({chosen['line']})"] if chosen["dream"] else []))
                  + f"; it says what came of it in {run_log(name)}")
    finish(rec, at, said, f"{name}: {said[name]}", quiet=True)
    problem = start_run(name, chosen["repo"], what, at)
    if problem:
        said[name] = f"could not be started: {problem}"
    else:
        rec["launched"] = {"store": name, "what": what, "at": int(at)}
    return finish(rec, at, said, f"{name}: {said[name]}")


@contextlib.contextmanager
def record_locked():
    """One writer of scheduler.json at a time: a check, and the run an earlier check started, which says there what came of it."""
    folder = state()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(folder / ".scheduler.json.lock", os.O_WRONLY | os.O_CREAT, 0o600), "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def finish(rec: dict, at: float, said: dict, line: str, quiet: bool = False) -> int:
    with record_locked():
        runs = record()["stores"]  # what a run said of itself since this check read the file is kept
        rec.update(at=int(at), line=line, started=rec["started"][-KEPT:],
                   stores={name: {"at": int(at), "line": words, **({"run": runs[name]["run"]} if isinstance((runs.get(name) or {}).get("run"), dict) else {})}
                           for name, words in said.items()})
        write_json(record_file(), {k: rec.get(k) for k in ("at", "line", "stores", "started", "launched")})
    if quiet:
        return 0
    print(f"{clock(at)} {line}")
    for name, words in sorted(said.items()):
        print(f"  {name}: {words}")
    return 0


def main():
    args = sys.argv[1:]
    if args == ["run"]:
        sys.exit(tick())
    elif args == ["probe"]:
        print(json.dumps(probe()))
    elif args == ["refresh"]:
        refresh()
    elif args[:1] == ["launch"] and len(args) == 5:
        sys.exit(launch(args[1], Path(args[2]), args[3], float(args[4])))
    elif args[:1] == ["enroll"] and len(args) == 3:
        enroll(args[1], args[2])
    elif args[:1] == ["drop"] and len(args) == 2:
        print(drop(args[1]))
    elif args == ["list"]:
        for name, entry in sorted(config().items()):
            print(f"{name}\t{entry['repo']}")
    else:
        sys.exit("usage: amk schedule run | enroll <store> <repo> | drop <store> | list")


if __name__ == "__main__":
    main()
