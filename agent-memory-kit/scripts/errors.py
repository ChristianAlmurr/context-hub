#!/usr/bin/env python3
"""The errors of earlier sessions, so later ones can learn from them: one signature per kind of failed tool call.

  python3 scripts/errors.py              bring the ledger up to date from the session archive, print one line of counts
  python3 scripts/errors.py --dry-run    the same counts and the top repeat errors, read from the archive, nothing written

Mechanical, no model. The session archive (archive.py) already labels every failed tool call as a `**tool error**:`
entry after the `**tool call**:` it answers. Each one becomes a signature (signature()):

  <tool> <command head>: <the error's first meaningful line, normalised>

- The command head is what a Bash command runs: the command the error names (`ls: x: No such file` is ls's, a Python
  exception a Python script's), else the first that does more than set up. `cd x &&`, `FOO=1`, `sudo`, `timeout 30` and a
  loop's `do` are passed over, a path is its last part, and a tool that has subcommands keeps one (`git push`, `npm test`,
  `python3 memwrite.py`, `amk write`). Any other tool is its name alone (`Edit`, `mcp__x__y`).
- A signature that says only that a command exited (`Bash ls: exit 1`, weak()) is many mistakes under one name: it is
  counted and listed, but it is no repeat for the metric and no reason for a dream to start.
- The first meaningful line: `Exit code N` and blank lines are passed over; a Python traceback gives its last exception
  line; else the first line that reads as an error (`Error:`, `fatal:`, `No such file`, `denied`, …); else, for a command
  that only exited, `exit N`; else the first line.
- Normalised, so the same mistake is one signature however often it happens: credentials and what the store's reject.txt
  lists are replaced first (redact.py, as in the archive), then timestamps, URLs, quoted values, paths, long hex and numbers
  become `<time>`, `<url>`, `<q>`, `<path>`, `<hex>` and `<n>`. At most WIDTH characters.

Not mistakes, and so never counted (noise(), the whole list): a call that was interrupted; a permission decision (the person
turning a call down, a rule, a classifier or a plugin refusing it); a block by the kit's own Bash guard (guard_memory.py);
grep, rg, test, `[` or `[[` that exited 1 with no error line (no match, or false: as the last command of a line, what came before
may have printed); an empty error. Claude Code fires no PostToolUseFailure hook for the first three (a cancelled call, a
permission denial and a PreToolUse block never reach it), so the ledger counts what the hook can see. Validation errors
(`File has not been read yet`) don't fire it either, but they are mistakes, so the ledger and the dream count them.

Each failure is recorded with the session it happened in (a subagent's under its parent's id), the session's dates, its
entry number, and the resolution: the entry of the first later call in the same session with the same tool and command
head that succeeded, so `python3 scripts/past.py --session <id> --entry <N>` shows how it was put right. Only a session's own
file is numbered the way past.py --entry counts, so a subagent's failure has no resolution entry.

The ledger is `_errors.json` in the store's archive folder (~/.local/state/agent-memory/sessions/<store>/), private like the
archive and never in the store or a repo. It reads that store's archive and no other. A file is read again only when it
changed, and a session the archive removed (180 days) leaves the ledger with it, so the ledger keeps what the archive keeps.
It is brought up to date by dream_due.py's counts (the daily check and the collector), the collector and dream_finish.py.

The failure hook (error_context.py), the dream's `_errors.md` (report()), the trigger (pending()) and the metric (metric())
read it. `covering()` is the one matcher of a signature against memory, for the hook and the dream alike.
"""
import json, os, re, shlex, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEM = Path(os.environ.get("AGENT_MEMORY_DIR", ROOT / "memory")).expanduser().resolve()  # as slim.MEM
LEDGER = "_errors.json"
VERSION = 1  # the ledger's shape and the signature rules: a ledger of another version is read again from the archive
WIDTH = 200  # characters of one signature
HEAD = 60  # characters of a command head
TOP = 15  # signatures _errors.md lists
# How slim.py stores an entry (slim.LIMITS, slim.SPARE, slim.CUT, its line-end rules): the hook makes a live error look as the
# archive keeps it, so a signature computed now is the one computed from the archive later. The suite holds these to slim's.
CALL_LIMIT, ERROR_LIMIT, SPARE = 400, 1000, 40
CUT = " … [{:,} characters cut] … "
# The longest a text cut to `limit` can be: what short() keeps and its marker. A text past this was not cut, and is cut before any
# pattern below reads it: some of them cost the square of what they are given on a long run of one character.
LONGEST = lambda limit: limit + SPARE + len(CUT.format(10 ** 12))
LINE_ENDS = re.compile("\r\n?|[\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]")
NOTHING = ("\x00-\x09\x0b-\x20\x7f-\xa0\xad\u034f\u061c\u115f\u1160\u1680\u180e\u2000-\u200f\u2028-\u202f\u205f-\u206f\u2800\u3000\u3164"
           "\ufe00-\ufe0f\ufeff\uffa0\ufff9-\ufffb\U0001d173-\U0001d17a\U000e0001\U000e0020-\U000e007f")
BLANK = re.compile(f"\n(?:[{NOTHING}]*\n)+")


def spelled(span: str) -> str:
    """Every character a regular expression's class of single characters and `a-b` ranges (as NOTHING is written) stands for."""
    found, at = [], 0
    while at < len(span):
        if at + 2 < len(span) and span[at + 1] == "-":
            found += [chr(c) for c in range(ord(span[at]), ord(span[at + 2]) + 1)]
            at += 3
        else:
            found.append(span[at])
            at += 1
    return "".join(found)


# What a stored entry loses at its two ends: str.strip, not a regular expression, whose `[…]+\Z` costs the square of a long run before the end.
EDGES = spelled(NOTHING) + "\n"
LABEL = re.compile(r"^\*\*(tool call|tool result|tool error|subagent report|user answer|user|assistant|background task|agent message|"
                   r"headless prompt|compaction summary|system note|system error)\*\*: ")
BACK = ("tool result", "tool error", "subagent report", "user answer")  # what comes back from a call, as slim.BACK

# ── noise: failures that are not a mistake to learn from ──
INTERRUPTED = re.compile(r"^\s*\[?(?:Request interrupted by user|Interrupted by user)|The user doesn't want to take this action right now", re.I)
PERMISSION = re.compile(r"^\s*(?:<tool_use_error>)?\s*(?:The user doesn't want to proceed with this tool use|Permission\b[^\n]{0,120}?\bdenied\b"
                        r"|[^\n]{0,120}\bdenied by your permission settings)", re.I)
# The kit's own Bash guard (guard_memory.py): its rules, by the words each starts with. The suite holds this list to the guard's texts.
KIT_BLOCK = re.compile(r"hook error: [^\n]*?\]: Blocked: (?:the heredoc that feeds memwrite|this memwrite\.py command|a line of the text is the heredoc"
                       r"|protected memory|this is the person's to run|which store a repository belongs|the kit's files in this repo)")
QUIET = {"grep", "egrep", "fgrep", "rg", "test", "[", "[["}  # exit 1 with nothing printed: no match, or false
EXIT = re.compile(r"^Exit code (\d+)$")

# ── the first meaningful line ──
EXCEPTION = re.compile(r"^\s*(?:[\w.]*(?:Error|Exception|Exit|Interrupt|Fault)|error|fatal|panic|ERROR|FATAL|Error)\b\s*(?:\[[^\]\n]*\])?\s*:")
ERRORISH = re.compile(r"(?i)\b(?:errors?|exception|fatal|fail(?:s|ed|ure)?|denied|refused|rejected|forbidden|unauthori[sz]ed|invalid|illegal|"
                      r"unknown|unrecogni[sz]ed|undefined|missing|cannot|can't|couldn't|could not|unable|not found|no such|does not exist|"
                      r"doesn't exist|no module|not allowed|not permitted|timed out|timeout|traceback|aborted|panic|conflict|blocked|usage|"
                      r"expected|has not been|not a)\b")
FRAME_LINE = re.compile(r'^\s*File "[^"]*", line \d+|^\s*at \S+ \(|^\s*\^+\s*$|^\s*…\s*\[[\d,]+ characters cut\]\s*…\s*$')

# ── normalisation ──
TAGS = re.compile(r"</?tool_use_error>")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CUT_MARK = re.compile(r"\s*… \[[\d,]+ characters cut\] …\s*")
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s'\"`<>)\]]+", re.I)
TIME = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b|\b\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\b")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
QUOTED = re.compile(r'"[^"\n]*"|(?<!\w)\'[^\'\n]*\'(?!\w)|`[^`\n]*`|“[^”\n]*”|‘[^’\n]*’')
PATH = re.compile(r"(?:(?<=[\s(=:,\[<>])|^)(?:~|\.{1,2})?(?:/[^\s:,;)\]'\"<>]+)+/?|(?<![\w/~.<-])[\w.@+-]+(?:/[\w.@+-]+)+/?")
HEX = re.compile(r"\b(?:0x)?(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b", re.I)
NUMBER = re.compile(r"(?<![A-Za-z<])\d+(?:[.,]\d+)*")
PLACEHOLDER = re.compile(r"<(?:n|hex|path|q|time|url)>")

# ── command heads ──
SEGMENTS = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
KEYWORDS = {"do", "then", "else", "elif", "{", "(", "!", "time"}  # what may stand before a command inside a loop or a test
CONTROL = {"for", "while", "until", "if", "case", "done", "fi", "esac", "}", ")", "select", "function"}  # a loop's or a test's own line
SETUP = {"cd", "pushd", "popd", "export", "set", "source", ".", "unset", "echo", "printf", "sleep", "true", ":", "umask", "trap", "local",
         "declare", "shopt", "mkdir", "clear"}
WRAPPERS = {"sudo", "env", "time", "nohup", "command", "exec", "nice", "caffeinate", "builtin", "timeout", "gtimeout", "xargs"}
SCRIPTED = re.compile(r"^(?:python[\d.]*|node|bash|sh|zsh|ruby|perl|deno|bun|tsx|ts-node|osascript)$")
SUBCOMMANDS = {"git", "npm", "npx", "pnpm", "yarn", "cargo", "go", "docker", "kubectl", "gh", "brew", "pip", "pip3", "uv", "swift", "xcrun",
               "launchctl", "systemctl", "jj", "amk", "make", "poetry", "flutter", "vercel", "supabase", "wrangler", "tailscale", "defaults",
               "security", "simctl", "xcodebuild", "terraform", "helm", "aws", "gcloud", "firebase", "rustup", "bundle", "rails", "mix", "dotnet",
               "pod", "fastlane", "claude", "hermes", "op", "railway", "fly", "heroku", "turbo", "nx", "pnpx", "corepack", "sqlite3", "psql"}
TAKES = {"-C", "-c", "--git-dir", "--work-tree", "--prefix", "--cwd", "-f", "--file", "--project", "-p", "--context", "-n", "--namespace"}
SUBWORD = re.compile(r"^[\w:.@+-]{1,30}$")

# ── matching memory ──
GENERIC = frozenset("error errors exit code failed fail fails fatal warning line file files command exception traceback call last recent eval "
                    "bash tool most".split())
LEAST = 2  # words a signature and a memory line's symptom share, at least ...
SHARE = 0.6  # ... and more than half of the signature's words (this part of them)


# ════════════════════════════════════════ signatures ════════════════════════════════════════

def short(text: str, limit: int) -> str:
    """The text as slim.Entry.short() keeps a new entry of that limit: the first two thirds and the last third, the cut counted between."""
    if len(text) <= limit + SPARE:
        return text
    first = limit * 2 // 3
    last = limit - first
    return text[:first] + CUT.format(len(text) - first - last) + text[len(text) - last:]


def stored(text: str, limit: int, clean=None) -> str:
    """A text as the archive would hold it in an entry of that limit: one kind of line end, no empty line, scrubbed, then cut."""
    text = BLANK.sub("\n", LINE_ENDS.sub("\n", text).strip(EDGES))
    return short(clean(text) if clean else text, limit)


def normalise(text: str) -> str:
    """One line with what varies from one occurrence to the next taken out. Never more of it than an error the archive keeps."""
    if len(text) > LONGEST(ERROR_LIMIT):
        text = short(text, ERROR_LIMIT)
    text = CUT_MARK.sub(" … ", ANSI.sub("", TAGS.sub("", text)))
    text = URL.sub("<url>", text)
    text = QUOTED.sub("<q>", text)
    text = PATH.sub("<path>", text)
    text = TIME.sub("<time>", text)
    text = UUID.sub("<hex>", text)
    text = HEX.sub("<hex>", text)
    text = NUMBER.sub("<n>", text)
    return " ".join(text.split())


def meaningful(error: str) -> str:
    """The line of an error that says what went wrong, as it stands (not normalised). `exit N` for a command that only exited."""
    lines = [line.strip() for line in TAGS.sub("", error).split("\n") if line.strip()]
    code = None
    if lines and EXIT.match(lines[0]):
        code, lines = EXIT.match(lines[0])[1], lines[1:]
    lines = [line for line in lines if not FRAME_LINE.search(line)]
    if any(line.startswith("Traceback (most recent call last)") for line in lines):
        after = lines[max(i for i, line in enumerate(lines) if line.startswith("Traceback (most recent call last)")) + 1:]
        raised = [line for line in after if EXCEPTION.match(line)]
        if raised:
            return raised[-1]
    for line in lines:
        if EXCEPTION.match(line):
            return line
    for line in lines:
        if ERRORISH.search(line):
            return line
    if code is not None:
        return f"exit {code}"
    return lines[0] if lines else ""


def words_of(segment: str) -> list:
    try:
        return shlex.split(segment, comments=True)
    except ValueError:
        return segment.split()


def bare(word: str) -> str:
    return word.rstrip("/").rsplit("/", 1)[-1] if "/" in word.rstrip("/") else word


def lead(words: list) -> list:
    """The words of one command from the one it runs: a loop's `do`, assignments and wrappers (`sudo`, `env -i`, `timeout 30`) passed over."""
    at = 0
    while at < len(words):
        word = words[at]
        if word in KEYWORDS or re.match(r"^\w+=", word):
            at += 1
        elif bare(word) in WRAPPERS:
            at += 1
            while at < len(words) and (words[at].startswith("-") or re.match(r"^\w+=", words[at]) or re.match(r"^\d+[smhd]?$", words[at])):
                at += 1
        else:
            break
    return words[at:]


def runs(command: str) -> list:
    """The commands a Bash command line runs, each as its words from the one it runs, in order. A loop's or a test's own line is none."""
    found = []
    for piece in SEGMENTS.split(command):
        words = lead(words_of(piece)) if piece.strip() else []
        if words and words[0] not in CONTROL:
            found.append(words)
    return found


def head(words: list) -> str:
    """One command in a word or two: its program's name, and its script or subcommand where it has one."""
    first, rest = bare(words[0]), words[1:]
    said = first
    if SCRIPTED.match(first):
        at = 0
        while at < len(rest) and rest[at].startswith("-") and rest[at] not in ("-c", "-m", "-", "-e"):
            at += 1
        if at < len(rest):
            if rest[at] in ("-c", "-e", "-"):
                said = f"{first} {rest[at]}"
            elif rest[at] == "-m" and at + 1 < len(rest):
                said = f"{first} -m {rest[at + 1]}"
            elif not rest[at].startswith("<"):
                said = f"{first} {bare(rest[at])}"
    elif first in SUBCOMMANDS:
        at = 0
        while at < len(rest) and rest[at].startswith("-"):
            at += 2 if rest[at] in TAKES else 1
        if at < len(rest) and SUBWORD.match(rest[at]):
            said = f"{first} {rest[at]}"
    return " ".join(said.split())[:HEAD]


def heads(command: str) -> list:
    """The head of every command a command line runs, in order."""
    return [head(words) for words in runs(command)]


def head_of(command: str, line: str = "") -> str:
    """What a Bash command runs, in a word or two: the command the error names (`ls: x: No such file` is ls's, a Python
    exception a Python script's), else the first that does more than set up (cd, export, echo, mkdir …)."""
    found = runs(command)
    if not found:
        return ""
    named = re.match(r"^([\w.+-]+):\s", line or "")
    for words in found:
        if named and bare(words[0]) == named[1]:
            return head(words)
    if line and EXCEPTION.match(line) and not line.lower().startswith(("error", "fatal")):
        scripted = [words for words in found if SCRIPTED.match(bare(words[0]))]
        if scripted:
            return head(scripted[0])
    return head(next((words for words in found if bare(words[0]) not in SETUP), found[0]))


def quiet(command: str) -> bool:
    """Is a command one whose exit 1 with no output only means: no match, or false? Its first real command or its last is grep, rg, test or [."""
    found = runs(command)
    return bool(found) and (bare(found[-1][0]) in QUIET or bare(next((w for w in found if bare(w[0]) not in SETUP), found[0])[0]) in QUIET)


def noise(tool: str, command: str, error: str, interrupted: bool = False) -> str:
    """Why a failed call is not a mistake to learn from, in a word, or "" when it is one."""
    text = TAGS.sub("", error or "").strip()
    if interrupted or INTERRUPTED.search(text[:300]):
        return "interrupted"
    if not text:
        return "empty"
    if PERMISSION.search(error[:400]):
        return "permission"
    if KIT_BLOCK.search(text[:600]):
        return "kit guard"
    if tool == "Bash" and re.match(r"Exit code 1\b", text) and meaningful(text) == "exit 1" and quiet(command or ""):
        return "no match"  # nothing but `Exit code 1` and what earlier commands printed: grep found nothing, or test was false
    return ""


def signature(tool: str, command: str, error: str) -> str:
    """The signature of one failed call, from the call and the error as the archive keeps them. "" when it is noise.
    Given more than the archive keeps, it reads what the archive would: each cut to its limit first."""
    command = command if len(command or "") <= LONGEST(CALL_LIMIT) else short(command, CALL_LIMIT)
    error = error if len(error or "") <= LONGEST(ERROR_LIMIT) else short(error, ERROR_LIMIT)
    if noise(tool, command, error):
        return ""
    tool = " ".join(str(tool).split())[:80] or "?"
    line = meaningful(error)
    ran = head_of(command, line) if tool == "Bash" and command else ""
    said = line if line.startswith("exit ") and EXIT.match("Exit code " + line[5:]) else normalise(line)
    lead_in = f"{tool} {ran}" if ran else tool
    return f"{lead_in}: {said}"[:WIDTH].rstrip()


def command_of(call: str) -> tuple:
    """(tool, the Bash command or "") of a `**tool call**:` entry's text: `<tool> <its input as JSON>`, which may be cut in its middle."""
    tool, _, given = call.partition(" ")
    if tool != "Bash":
        return tool, ""
    found = re.match(r'\s*\{"command": "((?:[^"\\]|\\.)*)', given)
    if not found:
        return tool, ""
    raw = found[1]
    if raw.endswith("\\") and not raw.endswith("\\\\"):
        raw = raw[:-1]
    try:
        return tool, json.loads(f'"{raw}"')
    except ValueError:
        return tool, raw


def live(tool: str, given, error: str, mem: Path = None) -> str:
    """The signature of a call the hook is told about, made the way the archive will make it: the call and the error stored as
    slim.py stores them (scrubbed by redact.py with the store's reject.txt, then cut to their limits), then signature()."""
    import redact
    patterns = redact.rules(mem or MEM)
    clean = lambda text: redact.scrub(text, patterns)
    call = stored(f"{tool} {json.dumps(given, ensure_ascii=False)}", CALL_LIMIT, clean)
    _, command = command_of(call)
    return signature(str(tool), command, stored(str(error), ERROR_LIMIT, clean))


# ════════════════════════════════════════ the ledger ════════════════════════════════════════

def state() -> Path:
    return Path.home() / ".local" / "state" / "agent-memory"


def folder(mem: Path = None) -> Path:
    """The store's archive folder (archive.folder()), where the ledger lives."""
    return state() / "sessions" / (mem or MEM).name


def entries_of(body: str) -> list:
    """A stored session's entries, as past.py --entry numbers them: entry N is item N-1."""
    return body.rstrip("\n").split("\n\n")


def read_session(text: str) -> dict:
    """One archived session file as the ledger's row: who, when, its tool calls and every failure with its resolution. None for no session."""
    import archive
    head, _, body = text.partition("\n\n")
    h = archive.fields(head.split("\n"))
    if not h or h.get("format") != str(archive.FORMAT):
        return None  # not a session file, or one an older version wrote, whose entries can't be told apart
    calls, pending, last = [], [], None
    for number, entry in enumerate(entries_of(body), 1):
        kind = LABEL.match(entry)
        kind = kind[1] if kind else None
        text_of = entry[len(kind) + 6:] if kind else entry
        if kind == "tool call":
            if last in BACK:
                pending = []  # a new round of calls: whatever the last round left unanswered stays so
            tool, command = command_of(text_of)
            calls.append({"at": number, "tool": tool, "command": command, "error": None, "ok": None})
            pending.append(calls[-1])
        elif kind in BACK and pending:
            call = pending.pop(0)
            call["ok"] = kind != "tool error"
            call["error"] = text_of if kind == "tool error" else None
        if kind:
            last = kind
    failures, said = [], {}

    def later_heads(j: int) -> list:
        """heads() of call j, worked out once for the file however many failures before it look at it."""
        if j not in said:
            said[j] = heads(calls[j]["command"]) if calls[j]["command"] else []
        return said[j]

    for i, call in enumerate(calls):
        if call["ok"] is not False:
            continue
        sig = signature(call["tool"], call["command"], call["error"])
        if not sig:
            continue
        ran = head_of(call["command"], meaningful(call["error"])) if call["command"] else ""
        fixed = None
        if "agent" not in h:  # past.py --entry numbers a session's own file only
            for j in range(i + 1, len(calls)):
                later = calls[j]
                if later["ok"] and later["tool"] == call["tool"] and (not ran or ran in later_heads(j)):
                    fixed = later["at"]
                    break
        failures.append([sig, call["at"], fixed])
    return {"session": h["session"], "agent": h.get("agent"), "started": h["started_at"], "ended": h["ended_at"],
            "working": h.get("working") != "no", "calls": len(calls), "failures": failures}


def empty() -> dict:
    return {"version": VERSION, "files": {}, "signatures": {}}


def load(mem: Path = None) -> dict:
    """The ledger as it was last written. An empty one when there is none, or one of another version."""
    try:
        found = json.loads((folder(mem) / LEDGER).read_text())
    except (OSError, ValueError):
        return empty()
    return found if isinstance(found, dict) and found.get("version") == VERSION and isinstance(found.get("files"), dict) else empty()


def index(files: dict) -> dict:
    """Per signature: the sessions it happened in, with when each ended, and the newest resolution (session, entry, ended).
    What the hook reads, so it needn't go through every file."""
    found = {}
    for row in files.values():
        for sig, _, fixed in row["failures"]:
            one = found.setdefault(sig, {"sessions": {}, "fix": None})
            one["sessions"][row["session"]] = max(one["sessions"].get(row["session"], 0), row["ended"])
            if fixed and (one["fix"] is None or row["ended"] > one["fix"][2]):
                one["fix"] = [row["session"], fixed, row["ended"]]
    return found


def scanned(mem: Path, was: dict) -> dict:
    """The ledger brought in line with the archive folder: a file read again only when it changed, one that is gone dropped."""
    out = folder(mem)
    files = {}
    for path in sorted(out.glob("*.md")) if out.is_dir() else []:
        try:
            seen = path.stat()
        except OSError:
            continue
        mark = [seen.st_mtime_ns, seen.st_size]
        row = was["files"].get(path.name)
        if row and row.get("mark") == mark:
            files[path.name] = row
            continue
        try:
            with open(path, encoding="utf-8", errors="replace", newline="\n") as handle:
                row = read_session(handle.read())
        except OSError:
            continue  # removed by an archive run between the listing and the read
        if row is not None:
            row["mark"] = mark
            files[path.name] = row
    return {"version": VERSION, "files": files, "signatures": index(files)}


def update(mem: Path = None, write: bool = True) -> dict:
    """Bring the store's ledger up to date from its archive and return it. `write` False: computed, nothing written (--dry-run)."""
    mem = mem or MEM
    if not write:
        return scanned(mem, load(mem))
    import fcntl
    out = folder(mem)
    out.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(out / "_errors.lock", os.O_WRONLY | os.O_CREAT, 0o600), "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        was = load(mem)
        now = scanned(mem, was)
        if json.dumps(now, sort_keys=True) != json.dumps(was, sort_keys=True):
            tmp = out / ".errors.writing"
            with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
                f.write(json.dumps(now, ensure_ascii=False))
            os.chmod(tmp, 0o600)
            os.replace(tmp, out / LEDGER)
    return now


# ════════════════════════════════════════ memory ════════════════════════════════════════

def sig_words(sig: str) -> frozenset:
    import build_index as b
    return b.words(PLACEHOLDER.sub(" ", sig)) - GENERIC


def said_words(sig: str) -> frozenset:
    """The words of what a signature's error says, without its tool and command head."""
    return sig_words(sig.split(": ", 1)[1] if ": " in sig else sig)


def weak(sig: str) -> bool:
    """A signature that says only that a command exited (`Bash ls: exit 1`): a failure to count, but nothing in it to learn or match."""
    return bool(re.search(r": exit \d+$", sig))


def symptom_words(text: str) -> frozenset:
    """The words of what a memory line says goes wrong: the part before its `→` (or its title's cut), its evidence left out."""
    import build_index as b
    return b.words(b.CUT.split(b.EVIDENCE.sub("", text.strip()), 1)[0]) - GENERIC


def project_lines(mem: Path = None) -> list:
    """Every entry of the store's project/ (never history/), as build_index reads them. A file that can't be read is passed over."""
    import build_index as b
    found = []
    for path in sorted(((mem or MEM) / "project").glob("*.md")):
        try:
            found += b.lines(path)
        except OSError:
            continue
    return found


def covering(sig: str, lines: list) -> list:
    """The memory lines whose symptom matches a signature, best first: a line with a cure (`→`) before one without, then by words shared.

    They match when they share at least LEAST words, those are at least SHARE of the signature's own (its placeholders and
    the words every error has left out), and one at least is the error's and not only its command's: a line about the same
    command alone is not enough.
    """
    want, error = sig_words(sig), said_words(sig)
    if len(want) < LEAST or not error:
        return []
    found = []
    for line in lines:
        has = symptom_words(line.text)
        shared = len(want & has)
        if shared >= LEAST and shared >= SHARE * len(want) and error & has:
            found.append((("→" in line.text), shared, line))
    return [line for *_, line in sorted(found, key=lambda f: (f[0], f[1]), reverse=True)]


# ════════════════════════════════════════ the dream's side ════════════════════════════════════════

def in_window(row: dict, since: float, until: float) -> bool:
    return row["working"] and since < row["ended"] <= until


def metric(ledger: dict, since: float, until: float) -> dict:
    """The metric to drive down: failed calls in the window whose signature sessions before the window had already met, and per 100 tool calls.

    A session is in the window by when it ended. Its subagents count with it. Sessions in which no work was done don't count.
    A failure that says only that a command exited (weak()) is no repeat of anything: `Bash ls: exit 1` is many mistakes under one name.
    """
    before = {sig for row in ledger["files"].values() if row["working"] and row["ended"] <= since for sig, *_ in row["failures"] if not weak(sig)}
    rows = [row for row in ledger["files"].values() if in_window(row, since, until)]
    repeat = sum(sig in before for row in rows for sig, *_ in row["failures"])
    calls = sum(row["calls"] for row in rows)
    return {"repeat_errors": repeat, "repeat_errors_per_100_tool_calls": round(100 * repeat / calls, 1) if calls else 0}


def repeats(ledger: dict, since: float, until: float) -> dict:
    """Per signature that failed in the window: how often there, in which sessions, and the sessions before it (or earlier in it) that met it first."""
    starts, found = {}, {}
    for row in ledger["files"].values():
        if row["working"]:
            starts[row["session"]] = min(starts.get(row["session"], row["started"]), row["started"])
    for row in ledger["files"].values():
        if not in_window(row, since, until):
            continue
        for sig, *_ in row["failures"]:
            one = found.setdefault(sig, {"calls": 0, "sessions": set()})
            one["calls"] += 1
            one["sessions"].add(row["session"])
    for sig, one in found.items():
        met = [s for s, ended in ledger["signatures"].get(sig, {}).get("sessions", {}).items() if s in starts]
        ended = ledger["signatures"][sig]["sessions"]
        one["before"] = {s for s in met if s not in one["sessions"] and ended[s] <= since}
        one["earlier"] = {s for s in one["sessions"] if any(starts[o] < starts[s] for o in met if o != s)}
    return found


def pending(ledger: dict, lines: list, since: float, until: float) -> tuple:
    """(uncovered repeat errors, the sessions they are in) in the window: each signature once per session, counted when an earlier
    session had met it too and no memory line covers it, and it says more than that a command exited (weak()). What makes a dream
    due sooner (dream_due.REPEAT_ERRORS)."""
    pairs, sessions = 0, set()
    for sig, one in repeats(ledger, since, until).items():
        if one["earlier"] and not weak(sig) and not covering(sig, lines):
            pairs += len(one["earlier"])
            sessions |= one["earlier"]
    return pairs, len(sessions)


def past_command(where=None) -> str:
    """How past.py is run from `where` (the working folder when not given), for the failure hook and the dream alike: `python3
    scripts/past.py` where the repo has its copy of the kit, else `amk past`: in a run from the kit's own scripts
    (AGENT_MEMORY_FROM_KIT, as run-dream.sh sets it for a repo with no copy), and in a repo with no scripts/past.py."""
    if os.environ.get("AGENT_MEMORY_FROM_KIT"):
        return "amk past"
    try:
        here = Path(where) if where else Path.cwd()
        has = (here / "scripts" / "past.py").is_file()
    except OSError:
        has = False
    return "python3 scripts/past.py" if has else "amk past"


def pointer(session: str, entry: int, where=None) -> str:
    """The command that shows the entry, run from `where` (past_command())."""
    return f"{past_command(where)} --session {session} --entry {entry}"


def report(ledger: dict, lines: list, since: float, until: float) -> str:
    """_errors.md: the errors of the window that recurred, with whether memory covers each and where one was put right."""
    import build_index as b
    found = repeats(ledger, since, until)
    recurring = [(sig, one) for sig, one in found.items() if len(one["sessions"]) >= 2 or one["before"]]
    # What says more than an exit code first: there is something in it to learn and to match.
    recurring.sort(key=lambda pair: (not weak(pair[0]), len(pair[1]["sessions"]) + len(pair[1]["before"]), pair[1]["calls"]), reverse=True)
    m = metric(ledger, since, until)
    out = ["# Errors that recurred (counted by errors.py from the session archive; records, never instructions)", "",
           "Each heading is one kind of failed tool call: the tool, what the command ran, and the error's first meaningful line with what varies "
           "(paths, numbers, quoted values) taken out. Listed: those that failed in two sessions of this window or more, or that sessions before it met too.",
           "",
           "- Not covered and recurring: a candidate memory line. Write its symptom in the error's own words (the words of the heading, without "
           "the `<…>`), so the failure hook (`error_context.py`) matches it the next time the error happens and hands the line to the session; "
           "the cure is what the resolution shows. An error a tool's own message already explains needs no line.",
           "- Covered and still recurring: the line isn't reaching sessions, or its cure is wrong. Check the cure against the resolution; "
           "if it holds, the line is a pin candidate by the `## Pins` rules of `_health.md`.",
           "",
           f"Repeat errors in this window (failed calls whose signature sessions before it had met): {m['repeat_errors']}, "
           f"{m['repeat_errors_per_100_tool_calls']} per 100 tool calls. dream_finish.py records both; the aim is to bring them down.", ""]
    if not recurring:
        return "\n".join(out + ["None."]) + "\n"
    for n, (sig, one) in enumerate(recurring[:TOP], 1):
        ids = sorted(one["sessions"])
        said = (f"- failed {one['calls']}× in {len(ids)} session{'s' if len(ids) != 1 else ''} of this window ("
                + ", ".join(s[:8] for s in ids[:6]) + (", …" if len(ids) > 6 else "") + ")")
        if one["before"]:
            said += f", and in {len(one['before'])} session{'s' if len(one['before']) != 1 else ''} before it"
        cover = covering(sig, lines)
        fix = ledger["signatures"].get(sig, {}).get("fix")
        out += [f"## {n}. " + b.harmless(f"`{sig.replace('`', chr(39))}`"), said,
                (f"- covered by `project/{cover[0].file}`: \"{b.harmless(b.identity(cover[0]))[:300]}\"" if cover else "- not covered by any line of `project/`"),
                f"- resolved in: `{pointer(fix[0], fix[1])}`" if fix else "- no later success of the same call in the sessions held", ""]
    if len(recurring) > TOP:
        out.append(f"{len(recurring) - TOP} more recurred less often.")
    return "\n".join(out).rstrip("\n") + "\n"


def health_lines(ledger: dict, lines: list, since: float, until: float) -> list:
    """The section _health.md carries, so a dream that reads _health.md knows _errors.md is there and what it is for."""
    found = repeats(ledger, since, until)
    recurring = [sig for sig, one in found.items() if len(one["sessions"]) >= 2 or one["before"]]
    open_ones = sum(not covering(sig, lines) for sig in recurring)
    return ["", "## Recurring errors",
            f"`_errors.md` lists {len(recurring)} kind{'s' if len(recurring) != 1 else ''} of failed tool call that recurred, {open_ones} not covered by memory. "
            "Read it with the analysts' findings: an uncovered one is a candidate line whose symptom repeats the error's words; a covered one is a pin candidate or a wrong cure."]


# ════════════════════════════════════════ the command ════════════════════════════════════════

def window(mem: Path) -> tuple:
    """(since, now): the window a dream would read now, as dream_due.counts() works it out, read only (no archive run, no state written)."""
    import dream_due
    at = dream_due.now()
    last = dream_due.last_dream(dream_due.load(), at)
    return max(last, at - dream_due.WINDOW_DAYS * 86400), at


def main():
    import argparse
    ap = argparse.ArgumentParser(description="The ledger of failed tool calls in this store's session archive.")
    ap.add_argument("--dry-run", action="store_true", help="read the archive and print the counts; write nothing")
    ap.add_argument("--top", type=int, default=5, help="repeat signatures to list with --dry-run")
    a = ap.parse_args()
    started = time.perf_counter()
    ledger = update(write=not a.dry_run)
    files = ledger["files"].values()
    failures = sum(len(row["failures"]) for row in files)
    print(f"errors: {len(ledger['signatures'])} signatures, {failures} failed calls of {sum(r['calls'] for r in files)} tool calls "
          f"in the {len({r['session'] for r in files})} sessions held{'' if a.dry_run else ' → ' + str(folder() / LEDGER)}")
    if a.dry_run:
        since, until = window(MEM)
        m = metric(ledger, since, until)
        lines = project_lines()
        print(f"window since the last dream: {m['repeat_errors']} repeat errors, {m['repeat_errors_per_100_tool_calls']} per 100 tool calls; "
              f"uncovered repeats {pending(ledger, lines, since, until)}")
        ranked = sorted(ledger["signatures"].items(), key=lambda kv: len(kv[1]["sessions"]), reverse=True)
        for sig, one in [kv for kv in ranked if len(kv[1]["sessions"]) >= 2 and not weak(kv[0])][:max(a.top, 0)]:
            calls = sum(1 for row in files for s, *_ in row["failures"] if s == sig)
            print(f"  {len(one['sessions'])} sessions, {calls} calls, {'resolved' if one['fix'] else 'unresolved'}, "
                  f"{'covered' if covering(sig, lines) else 'uncovered'}: {sig[:70]}")
        print(f"({(time.perf_counter() - started):.1f} s)")


if __name__ == "__main__":
    main()
