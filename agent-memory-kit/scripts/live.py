#!/usr/bin/env python3
"""Whether a Claude Code session is at work in some folders: the fixer asks it before it merges, the scheduler before it dreams.

Two signs, both only read:
- claude_folders(): the working folder of every Claude Code process of this user, from lsof (which only reads) and
  what each process was started as (ps). No process is matched by a pattern of its command line, and none is touched.
- newest_transcript(): the newest change to a transcript Claude Code keeps for one of the folders, under
  ~/.claude/projects. A session writes its transcript at every step, so a session that ended a while ago, or one
  whose process lsof can't tell apart, still shows when it last did something.

It binds no store and loads no script of the kit, so the scheduler, which works for every store at once, can use it.
"""
import os, re, subprocess
from pathlib import Path


def inside(where: Path, places: list) -> bool:
    return any(where == p or p in where.parents for p in places)


def claude_folders():
    """The working folders of this user's Claude Code processes, or None when that can't be told."""
    try:
        found = subprocess.run(["lsof", "-a", "-u", str(os.getuid()), "-d", "cwd", "-Fpn", "-w"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if found.returncode not in (0, 1) or found.stderr.strip() or (found.returncode == 1 and found.stdout.strip()):
        return None
    folders, pid = {}, None
    for line in found.stdout.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("n") and pid and pid != str(os.getpid()):
            folders[pid] = Path(line[1:])
    if not folders:
        return []
    try:
        listed = subprocess.run(["ps", "-o", "pid=,args=", "-p", ",".join(folders)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    working = []
    for row in listed.stdout.splitlines():
        pid, _, args = row.strip().partition(" ")
        words = args.split()
        first = words[0] if words else ""
        if pid in folders and (os.path.basename(first) == "claude" or "/claude/versions/" in first
                               or (os.path.basename(first) == "node" and "claude-code" in args)):
            working.append(folders[pid])
    return working


def live(places: list, folders="ask"):
    """Whether a Claude Code process works in one of the folders or below it: True, False, or None when it can't be told.
    `folders` is claude_folders()'s answer when the caller has it already, so one lsof serves many questions."""
    folders = claude_folders() if folders == "ask" else folders
    if folders is None:
        return None
    places = [Path(p).resolve() for p in places]
    return any(inside(Path(f), places) for f in folders)


def project_name(folder) -> str:
    """The folder under ~/.claude/projects that Claude Code keeps a working folder's transcripts in."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(folder))


def newest_transcript(places: list):
    """The newest modification time of a transcript (a session's or one of its subagents') kept for one of the folders
    or a folder below it, or None when there is none. A folder below is kept under the same name with more after a `-`,
    so a folder whose name only starts the same is counted too: that can only make a dream wait, never start."""
    base = Path.home() / ".claude" / "projects"
    names = {project_name(Path(p)) for p in places} | {project_name(Path(p).resolve()) for p in places}
    newest = None
    try:
        kept = list(base.iterdir())
    except OSError:
        return None
    for folder in kept:
        if not any(folder.name == n or folder.name.startswith(n + "-") for n in names):
            continue
        for path in list(folder.glob("*.jsonl")) + list(folder.glob("*/subagents/*.jsonl")):
            try:
                at = path.stat().st_mtime
            except OSError:
                continue
            newest = at if newest is None else max(newest, at)
    return newest
