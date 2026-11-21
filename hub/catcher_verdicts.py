#!/usr/bin/env python3
"""The Dream Catcher's verdicts: what it may say about each item, what it may never decide, and the check its session
runs before it is done. Standard library only, and nothing of the hub is loaded, so a Claude session can run it:

  /usr/bin/python3 <hub>/catcher_verdicts.py check <run folder>

A run folder holds manifest.json (written by the hub: every item that waits on the person, across the stores it was
given), and what the session writes: verdicts.jsonl, one verdict per line, and report.md. The check names each problem
on its own line and exits 1; when there are none it writes finished.json, which is how the hub knows the run is over.
The hub reads the same verdicts with the same function (parse), so the two can't disagree.

A verdict line: {"key": "<an item's key>", "verdict": "approve" | "reject" | "leave", "reason": "<one line>",
"evidence": "<what was checked>"}. Every item of the manifest gets exactly one. What the catcher may never decide
(held_back) is decided here, before the session sees the item: such an item allows "leave" alone.
"""
import json, os, re, sys, time
from pathlib import Path

VERDICTS = ("approve", "reject", "leave")
REASON_MAX, EVIDENCE_MAX, REPORT_MAX = 240, 400, 40_000
# What the owner said always goes to them: credentials and money, deleting memory, the principles and Steering, a
# person's own decisions and preferences. Words, not a classifier: when in doubt it is the person's.
SENSITIVE = re.compile(r"(credential|password|passphrase|secret|\btoken|api[ _-]?key|private key|ssh|keychain|\bmoney|payment|\bbank|invoice|billing|salary|\bprice|budget|financ|[$€£])", re.I)
PREFERENCE = re.compile(r"(\bDecision:|\bprefer|\(by [^)]+\))", re.I)
TOP_FILES = re.compile(r"^(ORG\.md|STEERING\.md|Steering\b)", re.I)


def held_back(item: dict) -> str:
    """Why the catcher may only leave this item for the person, or empty when it may decide it. Read from the item as the
    hub lists it in the manifest: its kind, section, file, action and words."""
    words = " ".join([item.get("text", ""), *item.get("details", [])])
    if item["kind"] == "proposal":
        if item.get("section_kind") == "yours" or TOP_FILES.match(item.get("file", "")):
            return "ORG.md and Steering are yours to change"
        if item.get("section_kind") == "unchecked":
            return "nothing could check this fact: your tick is the check"
        if item.get("action", "").startswith("delete"):
            return "it deletes a memory line"
        if item.get("file", "").endswith("decisions.md") or PREFERENCE.search(words):
            return "it records a decision or preference of a person"
    if item["kind"] == "need" and item.get("who") == "you":
        return "only you can put it right"
    if item["kind"] == "inbox" and re.search(r"ORG\.md|STEERING|Steering|principle", words):
        return "it proposes a change to ORG.md or Steering"
    if SENSITIVE.search(words):
        return "it touches credentials or money"
    return ""


def allowed(item: dict) -> list:
    return ["leave"] if item.get("held") else list(VERDICTS)


def one_line(value, most: int) -> bool:
    return isinstance(value, str) and value.strip() != "" and "\n" not in value and len(value) <= most


def parse(manifest: dict, text: str):
    """(verdicts by key, problems): every line of verdicts.jsonl read against the manifest. A problem is one sentence
    the session can act on. An item with no verdict, or a line that is wrong, is a problem; the hub never applies a
    run with problems, and leaves every item of such a run for the person."""
    items = {item["key"]: item for item in manifest.get("items", [])}
    found, problems = {}, []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            problems.append(f"line {number} isn't JSON")
            continue
        if not isinstance(row, dict):
            problems.append(f"line {number} isn't a JSON object")
            continue
        key = row.get("key")
        if key not in items:
            problems.append(f"line {number}: {key!r} isn't the key of an item in manifest.json")
            continue
        if key in found:
            problems.append(f"line {number}: {key} has a verdict already, on an earlier line. Give each item one")
            continue
        if row.get("verdict") not in allowed(items[key]):
            why = f" ({items[key]['held']}, so it can only be left for the person)" if items[key].get("held") else ""
            problems.append(f"line {number}: {key}: the verdict must be one of {', '.join(allowed(items[key]))}{why}")
            continue
        if not one_line(row.get("reason"), REASON_MAX):
            problems.append(f"line {number}: {key}: reason must be one line of at most {REASON_MAX} characters")
            continue
        if not one_line(row.get("evidence"), EVIDENCE_MAX):
            problems.append(f"line {number}: {key}: evidence must be one line of at most {EVIDENCE_MAX} characters, saying what you checked")
            continue
        found[key] = {"verdict": row["verdict"], "reason": row["reason"].strip(), "evidence": row["evidence"].strip()}
    missing = [key for key in items if key not in found]
    if missing:
        problems.append(f"{len(missing)} items have no verdict yet: {', '.join(missing[:12])}{' …' if len(missing) > 12 else ''}")
    return found, problems


def check(folder: Path) -> list:
    """The problems with a run folder's verdicts and report, or none. With none, finished.json is written."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text())
    except (OSError, ValueError) as error:
        return [f"manifest.json can't be read ({error}). It is the hub's: don't write it"]
    verdicts = folder / "verdicts.jsonl"
    found, problems = parse(manifest, verdicts.read_text(errors="replace") if verdicts.is_file() else "")
    report = folder / "report.md"
    text = report.read_text(errors="replace").strip() if report.is_file() else ""
    if not text:
        problems.append("report.md is missing or empty")
    elif len(text) > REPORT_MAX:
        problems.append(f"report.md is longer than {REPORT_MAX} characters; say less")
    if not problems:
        done = folder / "finished.json"
        spare = folder / "finished.json.tmp"
        spare.write_text(json.dumps({"at": int(time.time()), "verdicts": len(found)}))
        os.replace(spare, done)
    return problems


def main(argv: list) -> int:
    if len(argv) != 3 or argv[1] != "check":
        print("usage: catcher_verdicts.py check <run folder>", file=sys.stderr)
        return 2
    problems = check(Path(argv[2]))
    for problem in problems:
        print(f"- {problem}")
    if problems:
        print("Put each right in verdicts.jsonl or report.md and run the check again.")
        return 1
    print("finished: the hub will apply the verdicts now.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
