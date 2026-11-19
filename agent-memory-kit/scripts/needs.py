#!/usr/bin/env python3
"""What dreams said needs the person and is not memory: a job that is broken, a login that ran out, a credential to rotate.

A proposal's section "Needs you" holds such things as plain lines with no tick box. Nothing applies
them and no dream proposes them as items. They are kept here, in dreams/needs.json in the store,
which this module alone reads and writes: a file of its own, so a kit copy from before it existed,
which rewrites dreams/proposals.json whole, can't erase them.

  {"needs": [{"text", "key", "from", "at", "last", "seen", "said", and the keys of OPTIONAL when they are known}]}, oldest first

`text` is the line as it was last said, `key` its sentence in a normal form (key()), `from` and `at`
the proposal that first said it and when, `last` and `seen` the one that last said it and when,
`said` how many proposals have said it.

Who can put it right. Each line ends, after its evidence, with who can: ` · fix: <repo> — <what to change>`
when an agent can, a small file change in a repository that is only the owner's (fixable()), or
` · yours: <why, in a few words>` when only the person can (a credential, a login, a decision, a shared
repository, money, system settings, a live service). owner() reads it into `who` ("agent" or "you"),
with `repo` and `change`, or `why`. A need written before lines said it has no `who`: it is unsorted.
key() reads only the sentence, so a dream that sorts a need differently says the same need.

Its life. dream_finish.py records what a proposal says (record()) in the commit that makes the
proposal the store's open one, whatever becomes of that proposal afterwards. The next dream is
handed the open ones (handover(), in _left-open.md) and says one again, in the same words, only if
its sessions still show it: that is the same entry, said once more. When its sessions show the
thing put right, it writes `- resolved: <the same words> · evidence: <where it shows>` and the
entry is closed with that proposal: the person reads the line there and does nothing. One
that no dream has said for KEPT_DAYS is dropped when the next proposal is written. The daily
check says how many wait for the person once the oldest has waited WAIT_DAYS (dream_due.py).

What the person decides, its `state` (STATES; an entry with none is open):
- `python3 scripts/dream_proposal.py approve "<words>"`: open, or stopped, becomes approved. The fixer
  (run-fix.sh, scripts/fix.py) takes it: fixing, then fixed (with what it changed and whether it was
  merged) or stopped (with its reason). An unsorted need can be approved too; the fixer then works out
  the repository from the text, or stops and says it couldn't. A need that is yours can't be approved.
- `reject "<words>"`: the person doesn't want it. It stays on record as rejected, and each later dream is
  told never to say it again, as with a declined item; proposal_check.py refuses one that does.
- `done "<words>"`: it is dealt with, or not wanted said again until it shows again. Off the record.
All three are the person's: refused inside an unattended run, and stopped by the Bash guard (verbs.PERSONS).
A fixed need goes to the next dream with the rule: check it is really put right, and resolve it if so;
say it again if not, and it is open again.

Whether two lines are the same need is decided by key(): the sentence before its evidence, with
case, punctuation and spacing folded. A dream that says the same thing in other words is not
caught by this; the list it is handed is what stops that, as for declined items.
"""
import json, os, re
from pathlib import Path

import memcheck

FILE = Path("dreams") / "needs.json"
HEADING = "Needs you"  # the section of a proposal
EVIDENCE = " · evidence: "  # what ends the sentence of a line there
FIX = " · fix: "  # after the evidence: an agent can put it right, `<repo> — <what to change>`
YOURS = " · yours: "  # after the evidence: only the person can, and why in a few words
DASH = " — "  # between the repo and what to change
RESOLVED = "resolved: "  # how a line starts that says an earlier need has been put right
KEPT_DAYS = 180  # one no dream has said for this long is dropped
WAIT_DAYS = 3  # one that has been open this long is said in the daily check's reminder
ENTRY = ("text", "key", "from", "at", "last", "seen", "said")
STATES = ("open", "approved", "fixing", "fixed", "stopped", "rejected")
WAITS_FOR_PERSON = ("open", "stopped")  # the states in which the person has something to decide
RESULT = {"at": "number", "summary": str, "branch": str, "merged": str, "kept": str}  # what the fixer's run said, in an entry that is fixed or stopped
NO_FIX = Path.home() / ".config" / "agent-memory" / "no-fix.txt"  # the person's own list of repositories the fixer never works in, one path a line
KIT_FILES = re.compile(r"^/scripts/(memwrite|guard_memory|verbs|store|needs)\.py$")  # a line of a repository's info/exclude that keeps the kit's files out of its history


def number(value) -> bool:
    return type(value) in (int, float) and value == value and abs(value) != float("inf")


def text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


OPTIONAL = {"who": lambda v: v in ("agent", "you"), "repo": text, "change": text, "why": text, "state": lambda v: v in STATES, "decided": number,
            "result": lambda v: isinstance(v, dict) and set(v) == set(RESULT) and all(number(v[k]) if kind == "number" else isinstance(v[k], kind) for k, kind in RESULT.items())}


def key(line: str) -> str:
    """The sentence of a line, without its evidence and its `resolved:`, in a normal form: letters and digits, one space between words."""
    sentence = line.split(EVIDENCE)[0]
    sentence = sentence[len(RESOLVED):] if sentence.startswith(RESOLVED) else sentence
    return " ".join(re.sub(r"[^\w]+", " ", sentence.casefold()).split())


def owner(line: str) -> dict:
    """Who can put a need right, from what its line says after its evidence: {"who": "agent", "repo", "change"},
    {"who": "you", "why"}, or {} when the line doesn't say, or says it in a shape that can't be read (proposal_check.py names that)."""
    tail = line.split(EVIDENCE, 1)[1] if EVIDENCE in line else ""
    if (FIX in tail) == (YOURS in tail):
        return {}
    if YOURS in tail:
        why = tail.rsplit(YOURS, 1)[1].strip()
        return {"who": "you", "why": why} if why else {}
    repo, dash, change = tail.rsplit(FIX, 1)[1].partition(DASH)
    return {"who": "agent", "repo": repo.strip(), "change": change.strip()} if dash and repo.strip() and change.strip() else {}


def state(entry: dict) -> str:
    return entry.get("state", "open")


def parse(lines: list) -> tuple:
    """(said, resolved) from the lines of a proposal's "Needs you" section: each a list of {"text", "key"}.

    Only plain list lines count. A tick line there is not one of these: proposal_check.py refuses it and dream_apply.py never applies it.
    """
    said, resolved = [], []
    for line in lines:
        if not line.startswith("- ") or re.match(r"^- \[[ xX]\] ", line):
            continue
        text = line[2:].strip()
        if text:
            (resolved if text.startswith(RESOLVED) else said).append({"text": text, "key": key(text)})
    return said, resolved


def good(e) -> bool:
    """One entry as this version writes it, or as an earlier one did (no `who`, no `state`)."""
    if not (isinstance(e, dict) and set(ENTRY) <= set(e) <= set(ENTRY) | set(OPTIONAL)):
        return False
    if not (all(isinstance(e[k], str) and e[k] for k in ("text", "key", "from", "last")) and number(e["at"]) and number(e["seen"]) and type(e["said"]) is int and e["said"] >= 1):
        return False
    if not all(check(e[k]) for k, check in OPTIONAL.items() if k in e):
        return False
    who = e.get("who")
    sorted_right = ({"repo", "change"} <= set(e) and "why" not in e) if who == "agent" else ("why" in e and not {"repo", "change"} & set(e)) if who == "you" \
        else not {"repo", "change", "why"} & set(e)
    decided = state(e) == "open" or "decided" in e
    finished = ("result" in e) == (state(e) in ("fixed", "stopped"))
    return sorted_right and decided and finished and not (who == "you" and state(e) in ("approved", "fixing", "fixed"))


def load(mem: Path) -> list:
    """Every need on record, whatever its state, oldest first. A store that has no file yet has none."""
    path = mem / FILE
    try:
        found = json.loads(path.read_text())
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        found = None
    entries = found.get("needs") if isinstance(found, dict) else None
    if not (isinstance(entries, list) and all(good(e) for e in entries)):
        raise SystemExit(f"{path} is not a record of what needs the person that this version can read. "
                         "Correct it, or restore it from the store's history (git -C memory log -- dreams/needs.json).")
    return entries


def for_person(mem: Path) -> list:
    """The needs the person has something to decide about, oldest first: open, and stopped by the fixer."""
    return sorted((e for e in load(mem) if state(e) in WAITS_FOR_PERSON), key=lambda e: e["at"])


def write(mem: Path, entries: list):
    """Write the file whole. Called under the store's lock, by whoever commits it next."""
    path = mem / FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"needs": entries}, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def sort(entry: dict, line: str):
    """Who can put it right, as the line says, in place of what the entry said. A line that doesn't say leaves the entry as it was."""
    said = owner(line)
    if said:
        for k in ("who", "repo", "change", "why"):
            entry.pop(k, None)
        entry.update(said)


def record(mem: Path, proposal: str, at: float, lines: list) -> dict:
    """dream_finish.py, under the store's lock, as it commits a proposal: what its "Needs you" lines say goes on record.

    Returns {"new", "again", "resolved", "aged"}: how many were said for the first time, said again,
    closed because the dream showed them put right, and dropped for age. Writes the file only when
    there is something to hold or the file is there already; the dream's own commit takes it.
    A need the person rejected is never said again here (proposal_check.py refuses the line). One the
    fixer fixed and that is said again was not put right: it is open again. One that waits for the
    fixer, or that the fixer stopped on, keeps its state and who it was given to.
    """
    said, resolved = parse(lines)
    entries = load(mem)
    known = {entry["key"]: entry for entry in entries}
    counts = dict(new=0, again=0, resolved=0, aged=0)
    for line in said:
        if line["key"] in known:
            entry = known[line["key"]]
            if entry["last"] != proposal and state(entry) != "rejected":
                entry.update(text=line["text"], last=proposal, seen=int(at), said=entry["said"] + 1)
                if state(entry) == "fixed":
                    for k in ("state", "decided", "result"):
                        entry.pop(k, None)
                if state(entry) == "open":
                    sort(entry, line["text"])
                counts["again"] += 1
        else:
            known[line["key"]] = {"text": line["text"], "key": line["key"], "from": proposal, "at": int(at), "last": proposal, "seen": int(at), "said": 1, **owner(line["text"])}
            counts["new"] += 1
    for line in resolved:
        if known.pop(line["key"], None):
            counts["resolved"] += 1
    kept = [entry for entry in known.values() if at - entry["seen"] <= KEPT_DAYS * 86400 or state(entry) in ("approved", "fixing")]
    counts["aged"] = len(known) - len(kept)
    if kept or (mem / FILE).exists():
        write(mem, kept)
    return counts


def read_only(what: str):
    if os.environ.get("AGENT_MEMORY_PROPOSE_ONLY"):
        raise SystemExit(f"READ-ONLY: this run only proposes. {what} is the person's step. Nothing was recorded.")


def one(entries: list, words: str, what: str) -> dict:
    """The one entry whose text holds these words, or a stop that lists them."""
    match = [e for e in entries if words.casefold() in e["text"].casefold()]
    if len(match) != 1:
        listed = "".join(f"\n  {e['text']}" for e in match)
        raise SystemExit(f"{len(match)} things that need you hold \"{words}\", and one is {what} at a time. Nothing was changed." + listed
                         + ("" if match else " `python3 scripts/dream_proposal.py` lists them."))
    return match[0]


def done(mem: Path, words: str) -> str:
    """The person closes one need: it is dealt with, or they don't want it. Returns its text. Takes the store's lock and commits."""
    read_only("Closing what needs the person")
    with memcheck.locked(mem):
        entries = load(mem)
        match = one(entries, words, "closed")
        write(mem, [e for e in entries if e is not match])
        error = memcheck.commit(mem, f"needs: what {match['from']} said needs the person is closed", [str(FILE)])
        if error:
            raise SystemExit(f"{mem / FILE} was written, but the commit failed: {error}")
    return match["text"]


def decide(mem: Path, words: str, verdict: str, at: float) -> dict:
    """The person approves a need for the fixer, or rejects it. Returns the entry. Takes the store's lock and commits.

    Approve: an open or stopped need that an agent can fix, or that is unsorted. Reject: one that is open,
    approved and not yet started, or stopped. Anything else is refused with what it is.
    """
    read_only("Approving or rejecting what needs the person")
    with memcheck.locked(mem):
        entries = load(mem)
        match = one(entries, words, "approved" if verdict == "approve" else "rejected")
        now_in = state(match)
        if verdict == "approve" and match.get("who") == "you":
            raise SystemExit(f"Only you can put this right ({match['why']}), so there is nothing to approve for the fixer. "
                             "When it is dealt with: python3 scripts/dream_proposal.py done \"<words only it holds>\". Nothing was changed.")
        allowed = ("open", "stopped") if verdict == "approve" else ("open", "approved", "stopped")
        if now_in not in allowed:
            raise SystemExit(f"This one is {now_in}, so it can't be {'approved' if verdict == 'approve' else 'rejected'} now. Nothing was changed.")
        match.pop("result", None)
        match.update(state="approved" if verdict == "approve" else "rejected", decided=int(at))
        write(mem, entries)
        error = memcheck.commit(mem, f"needs: what {match['from']} said needs the person is {match['state']}"
                                     + (" for the fixer" if verdict == "approve" else ""), [str(FILE)])
        if error:
            raise SystemExit(f"{mem / FILE} was written, but the commit failed: {error}")
    return match


def approved(mem: Path) -> list:
    """The needs the person approved and the fixer has not taken yet, in the order they were approved."""
    return sorted((e for e in load(mem) if state(e) == "approved"), key=lambda e: e["decided"])


def move(mem: Path, which: str, was: tuple, to: str, result=None, message: str = "") -> bool:
    """For the fixer's runner (scripts/fix.py): one need, by its key, from one of the states in `was` to `to`, with what
    the run said. Takes the store's lock and commits. False, with nothing changed, when the need is gone (the person closed
    it meanwhile) or is no longer in one of those states. Only the fixer's own states: what the person decides is decide()'s."""
    if to not in ("fixing", "fixed", "stopped") or not set(was) <= {"approved", "fixing", "fixed"}:
        raise ValueError(f"needs.move: {was} to {to} is not a step of the fixer's")
    read_only("The fixer's record")
    with memcheck.locked(mem):
        entries = load(mem)
        match = next((e for e in entries if e["key"] == which), None)
        if match is None or state(match) not in was:
            return False
        match["state"] = to
        match.pop("result", None)
        if result is not None:
            match["result"] = result
        write(mem, entries)
        error = memcheck.commit(mem, message or f"needs: what {match['from']} said needs the person is {to}", [str(FILE)])
        if error:
            raise SystemExit(f"{mem / FILE} was written, but the commit failed: {error}")
    return True


# ── which repositories the fixer may work in ──
def roots(mem: Path) -> list:
    path = mem / "roots.txt"
    return [Path(line.strip()) for line in (path.read_text().splitlines() if path.exists() else []) if line.strip()]


def common_dir(repo: Path):
    """The folder git keeps a repository in, read from the files alone (no git is run): <repo>/.git, or for a worktree the one its .git file names."""
    dot = repo / ".git"
    if dot.is_dir():
        return dot
    try:
        said = dot.read_text().strip()
    except OSError:
        return None
    if not said.startswith("gitdir: "):
        return None
    gitdir = (repo / said[len("gitdir: "):]).resolve()
    try:
        return (gitdir / (gitdir / "commondir").read_text().strip()).resolve()
    except OSError:
        return gitdir


def off_limits(repo: Path) -> str:
    """Why the fixer may not work in this repository, or empty when it may. Read from files only, before any git is run there:
    a repository on the person's list (NO_FIX), a jj repository, one that is not git, and one whose kit files are kept out of
    its history (its info/exclude names them: a repository shared with others, where the kit is a guest)."""
    if not repo.is_dir():
        return "is not there"
    try:
        listed = [Path(line.strip()).expanduser().resolve() for line in NO_FIX.read_text().splitlines() if line.strip() and not line.startswith("#")]
    except OSError:
        listed = []
    real = repo.resolve()
    if any(real == other or other in real.parents for other in listed):
        return f"is on the list of repositories the fixer never works in ({str(NO_FIX).replace(str(Path.home()), '~', 1)})"
    if (repo / ".jj").exists():
        return "is a jj repository, which the fixer doesn't work in"
    common = common_dir(repo)
    if common is None:
        return "is not a git repository"
    try:
        excluded = (common / "info" / "exclude").read_text(errors="ignore").splitlines()
    except OSError:
        excluded = []
    if any(KIT_FILES.match(line.strip()) for line in excluded):
        return "keeps the kit's files out of its history: it is shared with others"
    return ""


def fixable(mem: Path) -> dict:
    """{name of the repository's folder: (its path, why the fixer may not work there, or empty)} for every repository of the store."""
    return {path.name: (path, off_limits(path)) for path in roots(mem)}


def repo_named(mem: Path, name: str):
    """The repository of the store a need names, by its folder's name or its whole path; None when no one repository is that."""
    found = [path for path in roots(mem) if name in (path.name, str(path))]
    return found[0] if len(found) == 1 else None


# ── what is said about them ──
def fixer_hour(mem: Path):
    """The hour the store's fixer runs every day (its launchd job, which schedule-dream.sh writes), or None when it has none."""
    import plistlib
    try:
        with open(Path.home() / "Library" / "LaunchAgents" / f"ai.agent-memory.fix.{mem.name}.plist", "rb") as f:
            hour = plistlib.load(f)["StartCalendarInterval"]["Hour"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return hour if type(hour) is int and 0 <= hour <= 23 else None


def status_words(e: dict, fixer_hour=None) -> str:
    """What has become of a need, in a few words, for the person."""
    now_in, result = state(e), e.get("result") or {}
    if now_in == "approved":
        return "Approved. The fixer runs " + (f"at {fixer_hour:02d}:00" if fixer_hour is not None else "when it is started by hand: sh agent-memory-kit/run-fix.sh <repo>")
    if now_in == "fixing":
        return "Being fixed"
    if now_in == "fixed":
        return (f"Fixed: {result['summary']}, merged into {result['merged']}" if result["merged"]
                else f"Fixed on branch {result['branch']}, not merged: {result['kept']}. {result['summary']}")
    if now_in == "stopped":
        return f"Stopped: {result['summary']}"
    if now_in == "rejected":
        return "Rejected. No dream says it again"
    return ""


def who_words(e: dict) -> str:
    if e.get("who") == "agent":
        return f"an agent can fix it, in {e['repo']}: {e['change']}"
    if e.get("who") == "you":
        return f"only you can: {e['why']}"
    return "not sorted: approve it and the fixer works out where, or stops and says so"


def lines(mem: Path, at: float) -> list:
    """For the person: every need on record but the rejected, oldest first, with the proposal that said it, how often it was
    said, who can put it right, what has become of it, and the commands that decide it."""
    found, hour = sorted((e for e in load(mem) if state(e) != "rejected"), key=lambda e: e["at"]), fixer_hour(mem)
    out = [f"  {e['text']}\n      said in {e['from']}, {max(0, int((at - e['at']) // 86400))} days ago"
           + (f", and {e['said'] - 1} more time{'' if e['said'] == 2 else 's'}, last in {e['last']}" if e["said"] > 1 else "")
           + f"\n      {who_words(e)}" + (f"\n      {status_words(e, hour)}" if state(e) != "open" else "") for e in found]
    return out and [f"{HEADING} (not memory; no dream applies these):"] + out + [
        "When one is dealt with: python3 scripts/dream_proposal.py done \"<words only it holds>\"",
        "To have the fixer do one an agent can fix: python3 scripts/dream_proposal.py approve \"<words>\"; to never hear of one again: … reject \"<words>\""]


def handover(mem: Path) -> list:
    """The lines of _left-open.md that hand the needs on record to the next dream, with the rule for each kind."""
    found = load(mem)
    out = ["", f"## {HEADING}: said by an earlier dream and not closed. Not memory: never propose one as an item"]
    said = lambda e: [f"- {e['text']}", f"      said in {e['from']}" + (f", {e['said']} times, last in {e['last']}" if e["said"] > 1 else "")]
    waiting = [e for e in found if state(e) not in ("fixed", "rejected")]
    for e in waiting:
        out += said(e) + ([f"      {status_words(e)}"] if state(e) != "open" else [])
    if not waiting:
        out.append("None.")
    else:
        out.append(f"A session of this batch still shows one: put it under \"{HEADING}\" again, in the same words. "
                   f"A session shows one put right: write `- {RESOLVED}<the same words>{EVIDENCE}<where it shows>` there, and it is closed with this proposal. "
                   "Neither: leave it out. It stays on record until the person closes it.")
    fixed = [e for e in found if state(e) == "fixed"]
    if fixed:
        out += ["", f"## {HEADING}: the fixer says it put these right. Check each one"]
        for e in fixed:
            out += said(e) + [f"      {status_words(e)}"]
        out.append(f"Check each against the code and the sessions. Really put right: write `- {RESOLVED}<the same words>{EVIDENCE}<where it shows>`. "
                   "Not put right: say it again, in the same words, and it is open again.")
    rejected = [e for e in found if state(e) == "rejected"]
    if rejected:
        out += ["", f"## {HEADING}: the person rejected these. Never say them again, in any words"]
        out += [f"- {e['text'].split(EVIDENCE)[0]}" for e in rejected]
    places = fixable(mem)
    may = [name for name, (_, why) in places.items() if not why]
    out += ["", "## Who can put a need right",
            f"Each line under \"{HEADING}\" ends, after its evidence, with who can. `{FIX.strip()} <repo>{DASH}<what to change>` when an agent can: "
            "a small change to files, described, in one of these repositories: " + (", ".join(may) if may else "none") + ". "
            f"`{YOURS.strip()} <why, in a few words>` for everything else: a credential, a login, a decision, a shared repository, money, system settings, a live service."]
    out += [f"- {name} {why}: its needs are the person's" for name, (_, why) in places.items() if why]
    return out
