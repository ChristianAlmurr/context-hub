"""The Dream Catcher: a Claude session that goes through everything dreams left waiting on the person, decides what it
can, and leaves the rest for them, with a reason each.

The session only reads and writes verdicts. Everything a verdict does is done here, by the hub, afterwards, as the
person's configured delegate and through the functions the hub's own buttons call: a tick is hub_data.tick, a need is
hub_data.decide_need (the kit's `approve` or `reject`), applying a proposal is hub_data.apply_dream. The kit's guard still
stops every person command in the session itself, as it does in every other session.

A run is a folder in the hub's state (dream-catcher/runs/<id>/):
  manifest.json   the hub's list of what waits, store by store, written before the session starts
  verdicts.jsonl  the session's: one verdict per item (catcher_verdicts.py says the shape and checks it)
  report.md       the session's: what it did, for the person
  finished.json   written by the check once both are right: the run is over and its verdicts can be carried out
  results.jsonl   the hub's: what became of each item, one line per item as it is done, so a crash halfway leaves
                  every line it wrote true, and the next pass carries on from there
  settled.json    the hub's: the pass is over, with its counts

Whether verdicts are carried out by themselves is the person's switch (`auto`): the config's "dream_catcher_auto",
false unless set, and the switch on the page after that. Off, approve and reject are only recommended, and "Accept all
recommended" carries them out.
"""
import json, os, re, secrets, shlex, subprocess, threading, time
from pathlib import Path

import catcher_verdicts as verdicts
import hub_data as hub
import hub_kit as kit
from hub_base import APP, ENV, HUB_PROJECT, SETTINGS, STATE, Malformed, Refused

ROOT = STATE / "dream-catcher"
RUNS = ROOT / "runs"
CHOICE = ROOT / "settings.json"  # the switch on the page, once the person has used it
RUN_ID = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
ACTED = ("done", "gone")  # results that close an item; the others leave it waiting on the person
WAITING = ("left", "recommended", "skipped", "failed")
lock = threading.RLock()  # one pass at a time over any run: carrying out, accepting, deciding
_settling = set()


# ── what the person configured ──
def own_name() -> str:
    name = SETTINGS.get("dream_catcher_store")
    return name if isinstance(name, str) and hub.NAME.match(name) else "dream-catcher"


def own_store():
    """The catcher's own store, when it has been made (dream-catcher-install.sh) and has a folder; else None, and its
    sessions run as hub sessions in the home folder, with no memory of their own."""
    store = hub.STORES / own_name()
    return store if (store / "ORG.md").exists() and hub.repos_of(store) else None


def scope() -> list:
    """The stores it goes through: the config's "dream_catcher_stores" when that is a list, every store otherwise."""
    named = SETTINGS.get("dream_catcher_stores")
    every = hub.stores()
    if isinstance(named, list):
        return [s for s in every if s.name in named]
    return every


def auto() -> bool:
    try:
        chosen = json.loads(CHOICE.read_text()).get("auto")
        if isinstance(chosen, bool):
            return chosen
    except (OSError, ValueError, AttributeError):
        pass
    return SETTINGS.get("dream_catcher_auto") is True


def set_auto(body: dict):
    if not isinstance(body.get("auto"), bool):
        raise Malformed("Say whether the Dream Catcher's verdicts are carried out by themselves.")
    hub.the_person("let the Dream Catcher act for you" if body["auto"] else "stop the Dream Catcher acting for you")
    ROOT.mkdir(parents=True, exist_ok=True)
    spare = CHOICE.with_suffix(".tmp")
    spare.write_text(json.dumps({"auto": body["auto"], "at": int(time.time())}))
    os.replace(spare, CHOICE)
    return {"auto": body["auto"]}


def default_model() -> str:
    model = SETTINGS.get("dream_catcher_model")
    return model if model in hub.MODELS else ""


# ── what waits ──
def under(text: str, line: int) -> list:
    """The indented lines under a tick line, as written."""
    lines, out = text.split("\n"), []
    for row in lines[line + 1:]:
        if not row.startswith("      "):
            break
        out.append(row.strip())
    return out


def busy(store: Path, live: set) -> str:
    """Why a store is left alone this time, or empty: a dream holds it or runs, or its fixer runs."""
    try:
        held = kit.dreamer(store)
    except Refused as quiet:
        return str(quiet)
    if held:
        return held
    if hub.dream_running(store.name, live):
        return "It is dreaming now."
    if hub.fix_running(store.name, live):
        return "Its fixer is running now."
    return ""


def proposal_items(store: Path, record: dict) -> list:
    path = store / "dreams" / record["name"]
    text = path.read_text(errors="ignore")
    items = []
    for section in hub.parse_proposal(text)["sections"]:
        for it in section["items"]:
            if it["checked"]:  # the person ticked it already: theirs, decided
                continue
            items.append({"key": f"p:{store.name}:{record['name']}:{it['id']}", "kind": "proposal", "store": store.name, "proposal": record["name"], "id": it["id"],
                          "section": section["name"], "section_kind": section["kind"], "n": it["n"], "file": it["file"], "action": it["action"],
                          "text": it["text"], "quote": it["quote"], "details": under(text, it["line"])})
    return items


def need_items(store: Path) -> list:
    found = hub.needs_of(store)
    return [{"key": f"n:{store.name}:{hub.sha(e['text'])}", "kind": "need", "store": store.name, "text": e["text"], "who": e["who"], "repo": e["repo"],
             "change": e["change"], "why": e["why"], "state": e["state"], "from": e["from"], "details": []}
            for e in found["open"] if e["state"] in ("open", "stopped")]


def inbox_items(store: Path) -> list:
    return [{"key": f"i:{store.name}:{path.name}", "kind": "inbox", "store": store.name, "file": f"inbox/{path.name}",
             "text": path.read_text(errors="ignore")[:4000], "details": []}
            for path in sorted((store / "inbox").glob("*.md")) if path.is_file()]


def gather() -> dict:
    """Everything that waits on the person in the stores in scope, as the manifest lists it. A store a dream or the fixer
    holds is skipped, with why, and so is an open proposal that is being applied."""
    live, own = hub.tmux_sessions(), own_store()
    stores, items, skipped = [], [], []
    for store in scope():
        why = busy(store, live)
        if why:
            skipped.append({"store": store.name, "why": why})
            continue
        record = kit.record_of(store)
        if record["problem"]:
            skipped.append({"store": store.name, "why": record["problem"]})
            continue
        held = next((p for p in record["proposals"] if p["state"] == "open"), None)
        found = []
        if held and (store / "dreams" / held["name"]).is_file():
            if kit.apply_record(store, held["name"]) is not None:
                skipped.append({"store": store.name, "why": f"Its proposal {held['name']} is being applied, so its items are left alone."})
            else:
                found += proposal_items(store, held)
        found += need_items(store) + inbox_items(store)
        for item in found:
            item["held"] = verdicts.held_back(item)
        items += found
        stores.append({"name": store.name, "path": str(store), "repos": hub.repos_of(store), "proposal": held["name"] if held else None,
                       "own": own is not None and store == own, "items": len(found)})
    return {"stores": stores, "items": items, "skipped": skipped}


# ── runs ──
def folder_of(run: str) -> Path:
    if not RUN_ID.match(run or ""):
        raise Refused("That isn't a Dream Catcher run.")
    folder = RUNS / run
    if not (folder / "run.json").is_file():
        raise Refused("That Dream Catcher run doesn't exist.")
    return folder


def runs() -> list:
    return sorted((p.name for p in RUNS.iterdir() if RUN_ID.match(p.name) and (p / "run.json").is_file()), reverse=True) if RUNS.is_dir() else []


def read_json(path: Path, otherwise=None):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return otherwise


def results(folder: Path) -> dict:
    """What became of each item, the last line for a key winning: a later pass, or the person, can change it."""
    out = {}
    path = folder / "results.jsonl"
    for line in (path.read_text(errors="ignore").splitlines() if path.is_file() else []):
        try:
            row = json.loads(line)
        except ValueError:
            continue  # a line cut off by a crash: the item it was about is done again, or found done
        if isinstance(row, dict) and isinstance(row.get("key"), str):
            out[row["key"]] = row
    return out


def note(folder: Path, key: str, verdict: str, result: str, said: str, by: str = hub.CATCHER, **more):
    row = {"key": key, "verdict": verdict, "result": result, "said": said[:400], "by": by, "at": int(time.time()), **more}
    path = folder / "results.jsonl"
    with open(path, "ab+") as out:
        out.seek(0, os.SEEK_END)
        if out.tell():
            out.seek(-1, os.SEEK_END)
            cut = out.read(1) != b"\n"  # a line a crash cut off ends here: start on a line of our own
        else:
            cut = False
        out.write((("\n" if cut else "") + json.dumps(row) + "\n").encode())
        out.flush()
        os.fsync(out.fileno())
    return row


def phase(folder: Path, live=None) -> str:
    """running, finished (verdicts written, not yet carried out), settled, or stopped (the session ended without finishing)."""
    if (folder / "settled.json").is_file():
        return "settled"
    if (folder / "finished.json").is_file():
        return "finished"
    meta = read_json(folder / "run.json", {})
    live = hub.tmux_sessions() if live is None else live
    return "running" if f"hub-{meta.get('sid')}" in live else "stopped"


def history(limit: int = 3) -> list:
    """What became of earlier verdicts, for the next run to learn from: each item it approved, rejected or left, and
    whether it still waits. An item it ticked that waits again was unticked by the person."""
    out = []
    for run in runs()[:limit]:
        for key, row in results(RUNS / run).items():
            if row.get("verdict") in verdicts.VERDICTS:
                out.append({"run": run, "key": key, "verdict": row["verdict"], "result": row.get("result"), "by": row.get("by"), "reason": row.get("reason", "")})
    return out


def start(body: dict):
    """Start a run: write what waits, then a Claude session to judge it. One run at a time."""
    hub.the_person("run the Dream Catcher")
    model = str(body.get("model") or default_model())
    if model and model not in hub.MODELS:
        raise Refused("That isn't a model.")
    with lock:
        live = hub.tmux_sessions()
        latest = runs()[:1]
        if latest and phase(RUNS / latest[0], live) == "running":
            raise Refused("The Dream Catcher is already running.")
        found = gather()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        run = stamp if not (RUNS / stamp).exists() else f"{stamp}-{secrets.randbelow(1000)}"
        folder = RUNS / run
        folder.mkdir(parents=True)
        manifest = {**found, "run": run, "history": history(), "made": int(time.time())}
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=1))
        if not found["items"]:
            (folder / "run.json").write_text(json.dumps({"id": run, "started": time.time(), "sid": None, "model": model}))
            (folder / "report.md").write_text("Nothing waited on you" + (f", and {len(found['skipped'])} projects were busy, so they were left alone." if found["skipped"] else ".") + "\n")
            (folder / "finished.json").write_text(json.dumps({"at": int(time.time()), "verdicts": 0}))
            settle(run)
            return {"run": run, "ids": []}
        own = own_store()
        project = own.name if own else HUB_PROJECT
        where = hub.repos_of(own)[0] if own else str(hub.HUB_HOME)
        sid = secrets.token_hex(4)
        title = hub.claude_name(project, f"Dream Catcher {time.strftime('%d %b %H:%M')}")
        check = f"/usr/bin/python3 {shlex.quote(str(APP / 'catcher_verdicts.py'))} check {shlex.quote(str(folder))}"
        task = (f"Catch the dreams in {folder}. Start by reading {folder / 'manifest.json'}: {len(found['items'])} items in "
                f"{len(found['stores'])} projects. When verdicts.jsonl and report.md are written, run: {check}")
        cmd = [hub.CLAUDE, task, "--settings", str(hub.HUB_SETTINGS), "--name", title, "--remote-control", title, *hub.catcher_flags()]
        cmd += ["--model", model] if model else []
        result = hub.tmux("new-session", "-d", "-s", f"hub-{sid}", "-x", "120", "-y", "36", "-c", where, *hub.session_env(sid), f"{shlex.join(cmd)}; exec /bin/zsh -l")
        if result.returncode != 0:
            raise Refused("The Dream Catcher didn't start: " + result.stderr.strip()[:200])
        (hub.META / f"{sid}.json").write_text(json.dumps({"id": sid, "project": project, "repo": where, "title": title, "kind": "claude", "isolate": False,
                                                          "created": time.time(), "task": task[:400], "folder": where, "mode": "", "model": model,
                                                          "effort": "", "agent": "", "code": False, "catcher": run}))
        (folder / "run.json").write_text(json.dumps({"id": run, "started": time.time(), "sid": sid, "model": model, "project": project}))
        return {"run": run, "ids": [sid]}


# ── carrying out a verdict ──
def current_proposal(store: Path, item: dict):
    """(path, text, the item as the file holds it now) for a proposal item, or a reason it can't be acted on."""
    try:
        record = hub.known_proposal(store, item["proposal"])
    except Refused as gone:
        return str(gone)
    if record["state"] != "open":
        return f"Its proposal is {record['state']} now."
    path = store / "dreams" / item["proposal"]
    if not path.is_file():
        return "Its proposal's file is gone."
    if kit.apply_record(store, item["proposal"]) is not None:
        return "Its proposal is being applied."
    text = path.read_text(errors="ignore")
    now = next((it for s in hub.parse_proposal(text)["sections"] for it in s["items"] if it["id"] == item["id"]), None)
    return (path, text, now) if now else "The proposal changed, and this item isn't in it any more."


def carry_out(item: dict, verdict: str, by: str, why: str):
    """Do what a verdict says, through the hub's own functions. Returns (result, what was said)."""
    store = hub.STORES / item["store"]
    if not (store / "ORG.md").exists():
        return "gone", "The project isn't there any more."
    held = busy(store, hub.tmux_sessions())
    if held:
        return "skipped", f"Not done now: {held}"
    if item["kind"] == "proposal":
        found = current_proposal(store, item)
        if isinstance(found, str):
            return "gone", found
        path, text, now = found
        if verdict == "approve":
            if not now["checked"]:
                hub.tick(item["store"], {"file": item["proposal"], "line": now["line"], "checked": True, "expect": hub.sha(text)})
                hub.record_action(item["store"], "tick", f"{item['proposal']} item {now['n'] or ''}: {now['text']}"[:300], by, why)
            return "done", "Ticked. It is applied with the proposal."
        if verdict == "reject":
            if now["checked"]:
                if by:  # someone ticked it since the run read it; the catcher doesn't take a tick back
                    return "skipped", "It was ticked since, so it is left as it is."
                hub.tick(item["store"], {"file": item["proposal"], "line": now["line"], "checked": False, "expect": hub.sha(text)})
            return "done", "Left unticked: it counts as a no when the proposal is applied."
    if item["kind"] == "need":
        if verdict in ("approve", "reject"):
            said = hub.decide_need(item["store"], {"words": item["text"]}, verdict, by, why)["said"]
            return "done", said
        if verdict == "done" and not by:
            return "done", hub.close_need(item["store"], {"words": item["text"]})["said"]
    if item["kind"] == "inbox":
        if verdict == "approve":
            return "done", "Left for the next dream to weigh."
        return "left", "For you to read."
    raise Refused("That can't be done to this item.")


def try_carry(item: dict, verdict: str, by: str, why: str):
    try:
        return carry_out(item, verdict, by, why)
    except Refused as refused:  # the kit's words, or the hub's: the item stays for the person, with them
        return "failed", str(refused)


def apply_ready(folder: Path, manifest: dict, by: str):
    """Apply each open proposal whose every unticked item has been decided no, with at least one tick: the same as the
    person pressing Apply. Anything still waiting on the person in it holds it back, because applying would count
    that item as a no."""
    rows = results(folder)
    for proposal in {(i["store"], i["proposal"]) for i in manifest["items"] if i["kind"] == "proposal"}:
        key = f"apply:{proposal[0]}:{proposal[1]}"
        if key in rows:
            continue
        store = hub.STORES / proposal[0]
        mine = [i for i in manifest["items"] if (i["kind"], i.get("store"), i.get("proposal")) == ("proposal", *proposal)]
        if any(rows.get(i["key"], {}).get("result") in WAITING for i in mine):
            continue
        path = store / "dreams" / proposal[1]
        if busy(store, hub.tmux_sessions()) or not path.is_file():
            continue
        parsed = [it for s in hub.parse_proposal(path.read_text(errors="ignore"))["sections"] for it in s["items"]]
        decided_no = {i["id"] for i in mine if rows.get(i["key"], {}).get("verdict") == "reject" and rows[i["key"]].get("result") == "done"}
        if not any(it["checked"] for it in parsed) or any(not it["checked"] and it["id"] not in decided_no for it in parsed):
            continue
        try:
            started = hub.apply_dream(proposal[0], {"file": proposal[1]})
        except Refused as refused:
            note(folder, key, "apply", "failed", str(refused), by)
            continue
        hub.record_action(proposal[0], "apply", f"Started /dream apply for {proposal[1]}", by, "every item was decided")
        note(folder, key, "apply", "done", "Every item was decided, so a session is applying it.", by, sid=(started.get("ids") or [""])[0])


def notify(waiting: int):
    """The catcher's own store's alert, as the kit's dreams use theirs: a title, and the count only."""
    own = own_store()
    script = own / "notify.sh" if own else None
    if script and os.access(script, os.X_OK):
        body = f"{waiting} {'thing waits' if waiting == 1 else 'things wait'} for you" if waiting else "Nothing waits for you"
        try:
            subprocess.run([str(script), "Dream Catcher", body], env=kit.kit_env(own), capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            pass


def waiting_in(folder: Path) -> int:
    manifest = read_json(folder / "manifest.json", {"items": []})
    rows = results(folder)
    return sum(1 for i in manifest["items"] if rows.get(i["key"], {}).get("result", "left") in WAITING)


def settle(run: str):
    """Carry out a finished run's verdicts, item by item, each written down as it is done. Safe to run again: an item
    with a result is not done twice. With the switch off, approve and reject are recommended and wait."""
    with lock:
        folder = folder_of(run)
        if phase(folder) != "finished":
            return
        manifest = read_json(folder / "manifest.json", {"items": []})
        verdicts_text = (folder / "verdicts.jsonl").read_text(errors="ignore") if (folder / "verdicts.jsonl").is_file() else ""
        found, problems = verdicts.parse(manifest, verdicts_text)
        acting, done = auto(), results(folder)
        for item in manifest["items"]:
            if item["key"] in done:
                continue
            v = found.get(item["key"])
            if problems or not v:
                note(folder, item["key"], "leave", "left", "The run's verdicts couldn't be read, so this is yours.")
                continue
            extra = {"reason": v["reason"], "evidence": v["evidence"]}
            if v["verdict"] == "leave":
                note(folder, item["key"], "leave", "left", item.get("held") or "Left for you.", **extra)
            elif not acting:
                note(folder, item["key"], v["verdict"], "recommended", "Recommended. It waits for you to accept it.", **extra)
            else:
                result, said = try_carry(item, v["verdict"], hub.CATCHER, v["reason"])
                note(folder, item["key"], v["verdict"], result, said, **extra)
        if acting and not problems:
            apply_ready(folder, manifest, hub.CATCHER)
        waiting = waiting_in(folder)
        spare = folder / "settled.json.tmp"
        spare.write_text(json.dumps({"at": int(time.time()), "auto": acting, "waiting": waiting, "problems": problems}))
        os.replace(spare, folder / "settled.json")
    notify(waiting)


def settle_later(run: str):
    """Carry out a run that has just finished, off the request that noticed it."""
    if run in _settling:
        return
    _settling.add(run)

    def work():
        try:
            settle(run)
        except Exception as error:  # written down, so the page says it; the next look tries again
            hub.damaged(RUNS / run, f"the Dream Catcher's verdicts could not be carried out: {error}")
        finally:
            _settling.discard(run)
    threading.Thread(target=work, daemon=True).start()


def watch(every: float = 10):
    """In the background for as long as the server runs: a run that has finished is carried out, even with no page open
    to poll (the summary does the same on every poll, sooner)."""
    def loop():
        while True:
            time.sleep(every)
            try:
                latest = runs()[:1]
                if latest and (RUNS / latest[0] / "finished.json").is_file() and not (RUNS / latest[0] / "settled.json").is_file():
                    settle_later(latest[0])
            except Exception:  # never let the watcher die on one bad folder; the page says what is wrong
                pass
    threading.Thread(target=loop, daemon=True, name="dream-catcher").start()


def item_of(folder: Path, key: str) -> dict:
    manifest = read_json(folder / "manifest.json", {"items": []})
    item = next((i for i in manifest["items"] if i["key"] == key), None)
    if item is None:
        raise Refused("That item isn't in this run.")
    return item


def accept(body: dict):
    """The person accepts every verdict the catcher only recommended, in one go, and they are carried out as the person's."""
    run = str(body.get("run") or "")
    hub.the_person("accept the Dream Catcher's recommendations")
    with lock:
        folder = folder_of(run)
        if phase(folder) != "settled":
            raise Refused("This run's verdicts aren't ready yet.")
        manifest = read_json(folder / "manifest.json", {"items": []})
        did = 0
        for key, row in results(folder).items():
            if row.get("result") != "recommended":
                continue
            item = next((i for i in manifest["items"] if i["key"] == key), None)
            if item is None:
                continue
            result, said = try_carry(item, row["verdict"], "", "")
            note(folder, key, row["verdict"], result, said, by="", reason=row.get("reason", ""), evidence=row.get("evidence", ""), accepted=True)
            did += result == "done"
        apply_ready(folder, manifest, "")
        refresh(folder)
    return {"said": f"{did} recommended {'verdict was' if did == 1 else 'verdicts were'} carried out."}


def decide(body: dict):
    """The person decides one item from the catcher's page: approve, reject, or done (a need only they could put right)."""
    run, key, verdict = str(body.get("run") or ""), str(body.get("key") or ""), body.get("verdict")
    if verdict not in ("approve", "reject", "done"):
        raise Malformed("Say approve, reject or done.")
    hub.the_person("decide what the Dream Catcher left for you")
    with lock:
        folder = folder_of(run)
        item = item_of(folder, key)
        if item["kind"] != "need" and verdict == "done":
            raise Refused("Only something that needs you can be marked done.")
        if item["kind"] == "need" and item.get("who") == "you" and verdict == "approve":
            raise Refused("Only you can put this right, so there is no fix to approve. Mark it done once it is dealt with.")
        result, said = carry_out(item, verdict, "", "")
        before = results(folder).get(key, {})
        note(folder, key, verdict, result, said, by="", reason=before.get("reason", ""), evidence=before.get("evidence", ""))
        refresh(folder)
    return {"said": said, "result": result}


def refresh(folder: Path):
    """Keep the count the sidebar shows in step after the person acts."""
    settled = read_json(folder / "settled.json")
    if isinstance(settled, dict):
        settled["waiting"] = waiting_in(folder)
        spare = folder / "settled.json.tmp"
        spare.write_text(json.dumps(settled))
        os.replace(spare, folder / "settled.json")


# ── what the hub shows ──
def summary() -> dict:
    """For the sidebar on every poll, from files only: the latest run, its phase and how many items wait on the person.
    A run that has just finished is carried out from here, in the background."""
    latest = runs()[:1]
    if not latest:
        return {"run": None, "phase": "", "waiting": 0, "auto": auto()}
    folder = RUNS / latest[0]
    now = phase(folder)
    if now == "finished":
        settle_later(latest[0])
    settled = read_json(folder / "settled.json", {}) or {}
    meta = read_json(folder / "run.json", {}) or {}
    return {"run": latest[0], "phase": now, "waiting": settled.get("waiting", 0) if now == "settled" else 0, "settled": settled.get("at"),
            "sid": meta.get("sid"), "auto": auto()}


def recent(limit: int = 6) -> list:
    """The last few runs, newest first, as one line each: when, how it ended, and what it decided."""
    out = []
    for run in runs()[:limit]:
        folder = RUNS / run
        meta, settled, rows = read_json(folder / "run.json", {}) or {}, read_json(folder / "settled.json", {}) or {}, results(folder)
        count = lambda verdict: sum(1 for k, r in rows.items() if not k.startswith("apply:") and r.get("verdict") == verdict and r.get("result") != "left")
        out.append({"id": run, "started": meta.get("started"), "phase": phase(folder), "approved": count("approve"), "rejected": count("reject"),
                    "left": settled.get("waiting", 0), "acted": settled.get("auto")})
    return out


def page() -> dict:
    """The Dream Catcher's page: the latest run's report and every item with its verdict and what became of it. Each
    item says whether it still waits: one decided elsewhere (on Dreams, by a dream) is no longer listed as waiting."""
    own = own_store()
    out = {"auto": auto(), "model": default_model(), "own": {"name": own_name(), "ready": own is not None, "install": f"sh {shlex.quote(str(APP / 'dream-catcher-install.sh'))}"},
           "scope": [s.name for s in scope()], "run": None, "runs": runs()[:8], "recent": recent()}
    latest = runs()[:1]
    if not latest:
        return out
    folder = RUNS / latest[0]
    now = phase(folder)
    manifest = read_json(folder / "manifest.json", {"items": [], "stores": [], "skipped": []}) or {}
    rows = results(folder)
    report = (folder / "report.md").read_text(errors="ignore")[:verdicts.REPORT_MAX] if (folder / "report.md").is_file() else ""
    still = set()
    if now == "settled":
        try:
            still = {i["key"] for i in gather()["items"]}
        except Refused:
            still = {i["key"] for i in manifest["items"]}
    items = []
    for item in manifest["items"]:
        row = rows.get(item["key"], {})
        waits = row.get("result", "left") in WAITING
        items.append({**{k: item.get(k) for k in ("key", "kind", "store", "proposal", "section", "section_kind", "n", "file", "action", "text", "quote", "who", "repo", "change", "why", "state", "held")},
                      "verdict": row.get("verdict"), "result": row.get("result"), "said": row.get("said", ""), "reason": row.get("reason", ""), "evidence": row.get("evidence", ""),
                      "by": row.get("by"), "open": item["key"] in still if now == "settled" else True, "waits": waits})
    settled = read_json(folder / "settled.json", {}) or {}
    shown = sum(1 for i in items if i["waits"] and i["open"])
    if now == "settled" and settled.get("waiting") != shown:  # decided elsewhere since: the sidebar's count follows
        with lock:
            spare = folder / "settled.json.tmp"
            spare.write_text(json.dumps({**settled, "waiting": shown}))
            os.replace(spare, folder / "settled.json")
    meta = read_json(folder / "run.json", {}) or {}
    applying = [{"store": k.split(":")[1], "proposal": k.split(":", 2)[2], **{x: r.get(x) for x in ("result", "said", "sid")}} for k, r in rows.items() if k.startswith("apply:")]
    out["run"] = {"id": latest[0], "phase": now, "started": meta.get("started"), "model": meta.get("model", ""), "sid": meta.get("sid"), "report": report,
                  "stores": manifest.get("stores", []), "skipped": manifest.get("skipped", []), "items": items, "applying": applying,
                  "settled": settled.get("at"), "acted": settled.get("auto"), "problems": settled.get("problems", [])}
    return out
