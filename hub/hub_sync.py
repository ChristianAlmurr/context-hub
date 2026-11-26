"""End-to-end encrypted sync of memory stores between one person's devices. Standard library plus `age` and `ssh-keygen`.

Nothing here invents a cipher. Confidentiality is `age` (X25519 + ChaCha20-Poly1305). Who may change the keyring is
decided by ed25519 signatures made and checked with the stock `ssh-keygen -Y sign/verify`. Bundles are authenticated
with HMAC-SHA256, codes stretched with PBKDF2-HMAC-SHA256. The design and what it does not protect against are in
docs/sync-security.md; read that before changing anything below.

The remote only ever holds:
  remote.json            plaintext: format, version and a random id (the salt for pairing and recovery codes)
  keyring.json           the newest keyring: members, wraps of the data key, the recovery wraps, a signature
  k/<rev>                every keyring since the last rotation, so a device that was away can check each step
  p/<hmac>               a pairing request or reply, for ten minutes at most; neither holds a key
  o/<hmac>               bundles and per-device heads: MAGIC || age ciphertext || MAC, names derived from the data key
"""
from __future__ import annotations

import base64, fcntl, hashlib, hmac, json, os, re, secrets, shutil, socket, stat, subprocess, tempfile, threading, time
from pathlib import Path

import hub_kit as kit
from hub_base import ENV, Malformed, Refused

FORMAT = "context-hub-sync"
VERSION = 1
MAGIC = b"CHS1"
TAG = 32
THROWAWAY = "hub-test-throwaway-"
PAIR_SECONDS = 600
EVERY = 120  # seconds between background syncs
KDF_ROUNDS = 600_000  # PBKDF2-HMAC-SHA256; /usr/bin/python3 has no hashlib.scrypt (LibreSSL)
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # 31 symbols: no 0 O 1 I L
PAIR_GROUPS, RECOVERY_GROUPS = 6, 8  # 24 symbols = 118.9 bits; 32 symbols = 158.5 bits
REPO, TEST_REPO = "context-hub-sync", "context-hub-sync-test"  # a second instance never finds the installed hub's repo
STORE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")  # always fullmatch
DEVICE_ID = re.compile(r"[0-9a-f]{16}")
RECIPIENT = re.compile(r"age1[02-9ac-hj-np-z]{58}")
SIGNER = re.compile(r"ssh-ed25519 [A-Za-z0-9+/]{68}")
HEX64 = re.compile(r"[0-9a-f]{64}")
REMOTE_NAME = re.compile(r"(?:remote\.json|keyring\.json|[op]/[0-9a-f]{40}|k/[0-9]{8}\.json)")
WALK = 2000  # the most keyring steps a device checks to reach the newest one
SMALL, RING_CAP, BUNDLE_CAP = 64 * 1024, 1024 * 1024, 64 * 1024 * 1024  # the most sync reads of any one file
NAMESPACE = "context-hub-sync"
GIT_ID = {"GIT_AUTHOR_NAME": "Context Hub sync", "GIT_AUTHOR_EMAIL": "sync@context-hub.invalid",
          "GIT_COMMITTER_NAME": "Context Hub sync", "GIT_COMMITTER_EMAIL": "sync@context-hub.invalid"}
LOCKED_FILES = ("ORG.md", "STEERING.md")  # the kit marks these as the person's with the kernel's immutable flag
ALERT = "notify.sh"  # a command the kit runs: never one another device wrote, unless it is the kit's own
ATTRIBUTES = b"*.md merge=union\n/roots.txt merge=union\n"  # roots.txt is a list of repo paths; the hub uses those that exist here
REVOKE = {"github": "Sign the removed device out of GitHub too: on it run gh auth logout, or revoke GitHub CLI under GitHub Settings > Applications, "
                    "because a device that can still push to the repo can hold back the change from devices that haven't synced yet.",
          "folder": "Take the removed device's access to the sync folder away too (sign it out of that iCloud account, or keep the drive from it), "
                    "because a device that can still write there can hold back the change from devices that haven't synced yet."}


def tool(name: str) -> str | None:
    return shutil.which(name, path=ENV["PATH"])


class Rejected(Exception):
    """A file on the remote failed a check. Its text is one sentence, and it never holds a key or plaintext."""


class Unverifiable(Rejected):
    """A step of the keyring's history is missing: the newest keyring may be genuine, it just can't be checked."""


class Removed(Rejected):
    """A keyring that checked out no longer lists this device."""


class Deferred(Exception):
    """A bundle can't be taken yet (it needs commits from another bundle, or the store is busy). Tried again later."""


# ── encoding: bech32 for age identities, codes people type ──
_B32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _polymod(values) -> int:
    generator = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    check = 1
    for value in values:
        top = check >> 25
        check = (check & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            check ^= generator[i] if (top >> i) & 1 else 0
    return check


def bech32(hrp: str, data: bytes) -> str:
    acc = bits = 0
    five = []
    for byte in data:
        acc, bits = (acc << 8) | byte, bits + 8
        while bits >= 5:
            bits -= 5
            five.append((acc >> bits) & 31)
    if bits:
        five.append((acc << (5 - bits)) & 31)
    expanded = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]
    mod = _polymod(expanded + five + [0] * 6) ^ 1
    return hrp + "1" + "".join(_B32[c] for c in five + [(mod >> 5 * (5 - i)) & 31 for i in range(6)])


def identity_of(raw: bytes) -> str:
    """An age X25519 identity from 32 bytes: it is only the bytes, bech32-encoded."""
    assert len(raw) == 32
    return bech32("age-secret-key-", raw).upper()


def make_code(groups: int) -> str:
    return "-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(groups))


def read_code(text, groups: int, what: str) -> str:
    if not isinstance(text, str):
        raise Malformed(f"Say the {what}.")
    plain = re.sub(r"[\s-]", "", text.upper())
    if len(plain) != 4 * groups or any(c not in ALPHABET for c in plain):
        raise Refused(f"That isn't a {what}: it has {4 * groups} letters and digits, in groups of four.", reason="bad_code")
    return plain


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def unb64(text) -> bytes:
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except (AttributeError, ValueError, UnicodeError) as bad:
        raise Rejected("A field on the remote isn't readable.") from bad


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def digest(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def subkey(key: bytes, label: str) -> bytes:
    """HKDF-Expand with one block: HMAC(key, label || 0x01). Each use of a key gets its own label."""
    return hmac.new(key, f"{FORMAT}/v{VERSION}/{label}".encode() + b"\x01", hashlib.sha256).digest()


def mac(key: bytes, *parts: bytes) -> bytes:
    return hmac.new(key, b"\x00".join(parts), hashlib.sha256).digest()


def same_hex(given, expected: bytes) -> bool:
    """A MAC from the remote against the one computed here, as bytes, so text of any shape is just a mismatch."""
    try:
        return isinstance(given, str) and hmac.compare_digest(bytes.fromhex(given), expected)
    except ValueError:
        return False


def code_keys(code: str, remote_id: str, purpose: str) -> dict:
    """What a pairing code or the recovery key stands for: an age identity, a MAC key and a name key."""
    seed = hashlib.pbkdf2_hmac("sha256", code.encode(), f"{FORMAT}/v{VERSION}/{purpose}/{remote_id}".encode(), KDF_ROUNDS)
    return {"identity": identity_of(subkey(seed, "age")), "mac": subkey(seed, "mac"), "name": subkey(seed, "name")}


def six(recipient: str, signer: str) -> str:
    """The six digits both screens show: the joining device's two public keys, so the person sees it is the one in their hand."""
    return f"{int.from_bytes(hashlib.sha256(f'{FORMAT}/check/{recipient}/{signer}'.encode()).digest()[:8], 'big') % 1_000_000:06d}"


def kid_of(key: bytes) -> str:
    return subkey(key, "id").hex()


# ── age ──
_recipients = {}


def recipient_of(identity: str) -> str:
    if identity in _recipients:
        return _recipients[identity]
    result = subprocess.run([tool("age-keygen") or "age-keygen", "-y"], input=identity + "\n", capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise Refused("age-keygen could not read a key.")
    _recipients[identity] = result.stdout.strip()
    return _recipients[identity]


def encrypt(plaintext: bytes, recipients: list) -> bytes:
    command = [tool("age") or "age"]
    for recipient in recipients:
        command += ["-r", recipient]
    result = subprocess.run(command, input=plaintext, capture_output=True, timeout=120)
    if result.returncode != 0:
        raise Refused("age could not encrypt.")
    return result.stdout


def decrypt(ciphertext: bytes, identity: str) -> bytes:
    """The identity goes to age through a pipe, never a file, so no key is written anywhere to decrypt."""
    read, write = os.pipe()
    try:
        os.write(write, (identity + "\n").encode())
        os.close(write)
        write = None
        result = subprocess.run([tool("age") or "age", "-d", "-i", f"/dev/fd/{read}"], input=ciphertext, capture_output=True, pass_fds=(read,), timeout=120)
    finally:
        os.close(read)
        if write is not None:
            os.close(write)
    if result.returncode != 0:
        raise Rejected("A file on the remote could not be decrypted.")
    return result.stdout


# ── ed25519 signatures, through the stock ssh-keygen ──
def _ssh_keygen() -> str:
    return tool("ssh-keygen") or "/usr/bin/ssh-keygen"


def new_signing_key(path: Path) -> str:
    """An ed25519 key at path (0600) and path.pub. Returns the public key line."""
    for old in (path, path.with_name(path.name + ".pub")):
        if old.exists():
            old.unlink()
    result = subprocess.run([_ssh_keygen(), "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(path)], capture_output=True, timeout=30)
    if result.returncode != 0:
        raise Refused("ssh-keygen could not make a signing key.")
    os.chmod(path, 0o600)
    return " ".join(path.with_name(path.name + ".pub").read_text().split()[:2])


def sign(data: bytes, key_file: Path) -> str:
    result = subprocess.run([_ssh_keygen(), "-Y", "sign", "-f", str(key_file), "-n", NAMESPACE], input=data, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise Refused("ssh-keygen could not sign.")
    return result.stdout.decode()


def verified(data: bytes, signature, public: str) -> bool:
    if not isinstance(signature, str) or len(signature) > 4096 or not SIGNER.fullmatch(public or ""):
        return False
    with tempfile.TemporaryDirectory() as folder:
        allowed, sig = Path(folder) / "allowed", Path(folder) / "sig"
        allowed.write_text(f'signer namespaces="{NAMESPACE}" {public}\n')
        sig.write_text(signature)
        result = subprocess.run([_ssh_keygen(), "-Y", "verify", "-f", str(allowed), "-I", "signer", "-n", NAMESPACE, "-s", str(sig)],
                                input=data, capture_output=True, timeout=30)
    return result.returncode == 0


ROOT_TMP = "hub-sync-root-"


def new_root(base: Path) -> tuple:
    """A new root signing key, made in a 0700 folder under the device's keys and removed at once: (public, private)."""
    base.mkdir(parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    folder = tempfile.mkdtemp(prefix=ROOT_TMP, dir=base)
    try:
        public = new_signing_key(Path(folder) / "root")
        return public, (Path(folder) / "root").read_bytes()
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def sweep_roots(*bases):
    """Root-key folders a crash left behind, here and in the temporary folder older versions used."""
    for base in bases:
        try:
            for leftover in Path(base).glob(ROOT_TMP + "*"):
                if leftover.is_dir() and not leftover.is_symlink() and leftover.stat().st_uid == os.getuid():
                    shutil.rmtree(leftover, ignore_errors=True)
        except OSError:
            pass


class RootKey:
    """The person's root signing key, opened from the recovery key for as long as one action takes. It is written to a
    0600 file in a 0700 folder only because ssh-keygen signs from a file, and removed right after."""

    def __init__(self, private: bytes, base: Path):
        self.private, self.base = private, Path(base)

    def __enter__(self):
        self.base.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base, 0o700)
        self.folder = tempfile.mkdtemp(prefix=ROOT_TMP, dir=self.base)
        os.chmod(self.folder, 0o700)
        self.path = Path(self.folder) / "root"
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(self.private)
        result = subprocess.run([_ssh_keygen(), "-y", "-f", str(self.path)], capture_output=True, timeout=30)
        if result.returncode != 0:
            self.__exit__()
            raise Refused("That recovery key doesn't open this sync.", reason="wrong_recovery_key")
        self.public = " ".join(result.stdout.decode().split()[:2])
        self.path.with_name("root.pub").write_text(self.public + "\n")
        return self

    def sign(self, data: bytes) -> str:
        return sign(data, self.path)

    def __exit__(self, *exc):
        shutil.rmtree(self.folder, ignore_errors=True)


class Keys:
    """What one data key stands for. Each use gets its own subkey."""

    def __init__(self, key: bytes, epoch: int):
        self.key, self.epoch = key, epoch
        self.mac, self.names = subkey(key, "mac"), subkey(key, "name")
        self.identity = identity_of(subkey(key, "age"))
        self.recipient = recipient_of(self.identity)
        self.kid = kid_of(key)

    def name(self, *parts: str) -> str:
        return "o/" + hmac.new(self.names, "\x00".join([str(self.epoch), *parts]).encode(), hashlib.sha256).hexdigest()[:40]

    def pack(self, name: str, plaintext: bytes) -> bytes:
        """Encrypt, then MAC the whole file and its name, so a file can't be moved to another name or changed."""
        body = encrypt(plaintext, [self.recipient])
        return MAGIC + body + mac(self.mac, MAGIC, name.encode(), body)

    def unpack(self, name: str, blob: bytes) -> bytes:
        """The MAC is checked before anything is decrypted."""
        if len(blob) < len(MAGIC) + TAG or not blob.startswith(MAGIC):
            raise Rejected("A file on the remote isn't one of ours.")
        body, tag = blob[len(MAGIC):-TAG], blob[-TAG:]
        if not hmac.compare_digest(tag, mac(self.mac, MAGIC, name.encode(), body)):
            raise Rejected("A file on the remote failed its check: it was changed, moved or not made by your devices.")
        return decrypt(body, self.identity)


# ── backends: a place that holds files ──
class Folder:
    """Any folder: iCloud Drive, a USB drive, a share. Whoever else can write there is an attacker: a link is never
    followed, only names sync makes are read, written or deleted, and no read is longer than its cap."""
    kind = "folder"
    FOLDERS = ("o", "p", "k")

    def __init__(self, path):
        if not isinstance(path, str) or not os.path.isabs(os.path.expanduser(path)):
            raise Malformed("Say the folder as a full path.")
        self.root = Path(os.path.expanduser(path))

    @property
    def label(self) -> str:
        return str(self.root)

    def settings(self) -> dict:
        return {"backend": "folder", "path": str(self.root)}

    def make(self):
        if not self.root.parent.is_dir():
            raise Refused(f"{self.root.parent} isn't a folder on this Mac.", reason="unreachable")
        if not os.path.lexists(self.root):
            self.root.mkdir()
        self.reach()

    def _real_dir(self, path: Path, missing_ok: bool):
        try:
            seen = os.lstat(path)
        except FileNotFoundError:
            if missing_ok:
                return False
            raise Refused(f"{path} isn't reachable right now.", reason="unreachable")
        if stat.S_ISLNK(seen.st_mode) or not stat.S_ISDIR(seen.st_mode):
            raise Refused(f"{path} is a link or not a folder, which sync refuses: something other than your devices changed the remote.", reason="tampered")
        return True

    def reach(self):
        self._real_dir(self.root, missing_ok=False)
        for folder in self.FOLDERS:
            self._real_dir(self.root / folder, missing_ok=True)

    def begin(self):
        self.reach()

    def finish(self):
        pass

    def _path(self, name: str) -> Path:
        if not isinstance(name, str) or not REMOTE_NAME.fullmatch(name):
            raise Rejected("Sync was asked for a remote name it never makes.")
        if "/" in name:
            self._real_dir(self.root / name.split("/")[0], missing_ok=True)
        return self.root / name

    def read(self, name: str, cap: int = SMALL):
        path = self._path(name)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
        except FileNotFoundError:
            return None
        except OSError:
            raise Rejected(f"{name} on the remote is a link or can't be opened, so it is refused.")
        with os.fdopen(fd, "rb") as handle:
            seen = os.fstat(handle.fileno())
            if not stat.S_ISREG(seen.st_mode):
                raise Rejected(f"{name} on the remote isn't a plain file, so it is refused.")
            if seen.st_size > cap:
                raise Rejected(f"{name} on the remote is bigger than sync ever makes it, so it is refused.")
            data = handle.read(cap + 1)
        if len(data) > cap:
            raise Rejected(f"{name} on the remote is bigger than sync ever makes it, so it is refused.")
        return data

    def _dir_for(self, name: str) -> Path:
        path = self._path(name)
        if not self._real_dir(path.parent, missing_ok=True):
            path.parent.mkdir()
            self._real_dir(path.parent, missing_ok=False)
        return path

    def write(self, name: str, data: bytes):
        path = self._dir_for(name)
        spare = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
        fd = os.open(spare, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(spare, path)  # replacing a link replaces the link itself, never what it points to

    def write_new(self, name: str, data: bytes) -> bool:
        """Write a file that must not exist yet. False when it does: another device got there first."""
        path = self._dir_for(name)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        return True

    def delete(self, name: str):
        path = self._path(name)
        try:
            os.unlink(path)  # a link is removed as a link
        except FileNotFoundError:
            pass

    def names(self, folder: str) -> list:
        if folder not in self.FOLDERS or not self._real_dir(self.root / folder, missing_ok=True):
            return []
        with os.scandir(self.root / folder) as entries:
            found = [f"{folder}/{e.name}" for e in entries if e.is_file(follow_symlinks=False) and REMOTE_NAME.fullmatch(f"{folder}/{e.name}")]
        return sorted(found)

    def empty(self) -> bool:
        with os.scandir(self.root) as entries:
            return not any(e.name not in (".DS_Store", ".git") for e in entries)

    def forget(self):
        for name in ("remote.json", "keyring.json"):
            self.delete(name)
        for folder in self.FOLDERS:
            for name in self.names(folder):
                self.delete(name)


class GitHub(Folder):
    """A private GitHub repo holding only the encrypted files, worked on through a local clone with plain git and
    core.symlinks off, so a link someone commits arrives as a small plain file. `url` is given only by tests (a local
    bare repo); otherwise it is found or made with gh."""
    kind = "github"

    def __init__(self, clone: Path, url: str | None = None, repo: str | None = None, name: str = REPO):
        self.clone, self.url, self.repo, self.repo_name = Path(clone), url, repo, name
        super().__init__(str(self.clone))

    @property
    def label(self) -> str:
        return f"github.com/{self.repo} · private" if self.repo else (self.url or "github")

    def settings(self) -> dict:
        return {"backend": "github", "url": self.url, "repo": self.repo}

    def _gh(self, *args, timeout=60):
        if not tool("gh"):
            raise Refused("The GitHub backend needs gh: brew install gh, then gh auth login.", reason="needs_gh")
        return subprocess.run([tool("gh"), *args], capture_output=True, text=True, timeout=timeout, env=ENV)

    def _git(self, *args, timeout=120, check=True):
        helper = ["-c", "credential.helper=", "-c", f"credential.helper=!{tool('gh')} auth git-credential"] if tool("gh") and self.url and self.url.startswith("https://") else []
        result = subprocess.run(["git", "-c", "core.symlinks=false", *helper, "-C", str(self.clone), *args], capture_output=True, text=True, timeout=timeout,
                                env={**ENV, **GIT_ID, "GIT_TERMINAL_PROMPT": "0"})
        if check and result.returncode != 0:
            raise Refused("git could not reach the sync repo: " + " ".join(result.stderr.split())[:160], reason="unreachable")
        return result

    def find(self, create: bool):
        if self.url:
            return
        who = self._gh("api", "user", "--jq", ".login")
        if who.returncode != 0 or not who.stdout.strip():
            raise Refused("gh isn't signed in: run gh auth login, then try again.", reason="gh_login")
        self.repo = f"{who.stdout.strip()}/{self.repo_name}"
        seen = self._gh("repo", "view", self.repo, "--json", "visibility", "--jq", ".visibility")
        if seen.returncode != 0:
            if not create:
                raise Refused(f"There's no {self.repo} repo on GitHub: set up sync on your first device, or pick the folder it uses.", reason="no_sync_here")
            made = self._gh("repo", "create", self.repo, "--private", "--description", "Context Hub sync: encrypted files only")
            if made.returncode != 0:
                raise Refused("gh could not make the private sync repo: " + " ".join(made.stderr.split())[:160], reason="unreachable")
        elif seen.stdout.strip() != "PRIVATE":
            raise Refused(f"{self.repo} on GitHub isn't private, so sync won't use it.", reason="not_private")
        self.url = f"https://github.com/{self.repo}.git"

    def make(self):
        self.find(create=True)
        self.reach()

    def reach(self):
        if self.url is None:
            self.find(create=False)
        if not (self.clone / ".git").is_dir():
            self.clone.parent.mkdir(parents=True, exist_ok=True)
            if self.clone.exists():
                shutil.rmtree(self.clone)
            self.clone.mkdir()
            self._git("init", "-q", "-b", "main")
            self._git("config", "core.symlinks", "false")
            self._git("remote", "add", "origin", self.url)
        super().reach()

    def begin(self):
        if self.url is None:
            self.find(create=False)
        if not (self.clone / ".git").is_dir():
            self.reach()
        self._git("fetch", "-q", "origin")
        if self._git("rev-parse", "-q", "--verify", "origin/main", check=False).returncode == 0:
            self._git("reset", "-q", "--hard", "origin/main")
            self._git("clean", "-q", "-fdx")
        super().reach()

    def finish(self):
        self._git("add", "-A")
        if self._git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return
        self._git("commit", "-q", "-m", "sync")
        for _ in range(3):
            if self._git("push", "-q", "origin", "HEAD:main", check=False).returncode == 0:
                return
            self._git("fetch", "-q", "origin")
            if self._git("rebase", "-q", "origin/main", check=False).returncode != 0:
                self._git("rebase", "--abort", check=False)
                self._git("reset", "-q", "--hard", "origin/main")
                raise Refused("The sync repo changed while this device was writing; it will try again.", reason="retry")
        raise Refused("git could not push to the sync repo.", reason="unreachable")

    def write_new(self, name: str, data: bytes) -> bool:
        # In the clone the check is local; two devices adding the same name meet as a conflict when they push.
        return super().write_new(name, data)


# ── the keyring: its shape, and the rule for each step ──
RING_KEYS = {"format", "v", "epoch", "rev", "prev", "root", "handover", "kid", "members", "wraps", "recovery", "body", "signer", "sig"}
MEMBER_KEYS = {"id", "recipient", "signer", "added_by", "name_hash"}
ROOT_ADDED = ("setup", "recovery")  # a member the root key added; any other added_by is the id of the member that added it


def name_hash(name: str) -> str:
    return hashlib.sha256(f"{FORMAT}/name/{name}".encode()).hexdigest()


def ring_shape(ring) -> dict:
    """Refuse a keyring of any other shape before anything is looked up in it."""
    def bad(what="isn't in the shape sync makes"):
        raise Rejected(f"The keyring on the remote {what}, so it is refused.")
    if not isinstance(ring, dict) or set(ring) != RING_KEYS:
        bad()
    if ring["format"] != FORMAT or ring["v"] != VERSION:
        bad("was made by something else")
    for field in ("epoch", "rev"):
        if not isinstance(ring[field], int) or isinstance(ring[field], bool) or not 1 <= ring[field] < 10 ** 8:
            bad()
    if not (ring["prev"] == "" or (isinstance(ring["prev"], str) and HEX64.fullmatch(ring["prev"]))) or not isinstance(ring["root"], str) or not SIGNER.fullmatch(ring["root"]):
        bad()
    if not isinstance(ring["kid"], str) or not HEX64.fullmatch(ring["kid"]) or not isinstance(ring["sig"], str) or not isinstance(ring["body"], str) \
            or not isinstance(ring["handover"], str):
        bad()
    members = ring["members"]
    if not isinstance(members, list) or not 0 < len(members) <= 64:
        bad()
    for member in members:
        if not isinstance(member, dict) or set(member) != MEMBER_KEYS or not all(isinstance(member[k], str) for k in member):
            bad()
        if not DEVICE_ID.fullmatch(member["id"]) or not RECIPIENT.fullmatch(member["recipient"]) or not SIGNER.fullmatch(member["signer"]) \
                or not HEX64.fullmatch(member["name_hash"]) or not (member["added_by"] in ROOT_ADDED or DEVICE_ID.fullmatch(member["added_by"])):
            bad()
    ids = [m["id"] for m in members]
    if len(set(ids)) != len(ids) or ids != sorted(ids):
        bad()
    if not isinstance(ring["wraps"], dict) or set(ring["wraps"]) != set(ids) or not all(isinstance(v, str) for v in ring["wraps"].values()):
        bad()
    recovery = ring["recovery"]
    if not isinstance(recovery, dict) or set(recovery) != {"wrap", "root"} or not all(isinstance(v, str) for v in recovery.values()):
        bad()
    if ring["signer"] != "root" and not (isinstance(ring["signer"], str) and DEVICE_ID.fullmatch(ring["signer"])):
        bad()
    if ring["handover"] and ring["signer"] != "root":
        bad()
    return ring


def ring_order(ring: dict) -> tuple:
    return (ring["epoch"], ring["rev"])


def unsigned(ring: dict) -> bytes:
    """What the signatures cover: everything but the two signatures themselves."""
    return canonical({k: v for k, v in ring.items() if k not in ("sig", "handover")})


def root_signed_by(ring: dict, root: str) -> bool:
    """A root-signed keyring that `root` vouches for: signed by `root` itself, or a rotation to a new root that `root`
    handed over (the new root signs it, the old one signs the handover)."""
    if ring["signer"] != "root":
        return False
    if ring["root"] == root:
        return verified(unsigned(ring), ring["sig"], root)  # its handover, if any, is the earlier root's business
    return bool(ring["handover"]) and verified(unsigned(ring), ring["handover"], root) and verified(unsigned(ring), ring["sig"], ring["root"])


def check_step(prev: dict, ring: dict):
    """One step of the keyring's history.
    The root key may add devices (added_by "setup" or "recovery") within the same epoch and key, or rotate: the next
    epoch, a new data key, and a new root key that the old one hands over. A member device may only add devices it
    vouches for (added_by: its own id), or take itself out, within the same epoch, key, root and recovery wraps. No
    step changes what an existing member's entry or wrap says, except the root's rotation, which may only drop members."""
    if ring["prev"] != digest(prev) or ring["rev"] != prev["rev"] + 1:
        raise Rejected("The keyring on the remote doesn't follow the one before it, so it is refused.")
    members = {m["id"]: m for m in prev["members"]}
    now = {m["id"]: m for m in ring["members"]}
    added = set(now) - set(members)
    kept = set(members) & set(now)
    if any(now[i] != members[i] for i in kept):
        raise Rejected("A step of the keyring changes what another device's entry says, so it is refused.")
    if ring["signer"] == "root":
        if not root_signed_by(ring, prev["root"]):
            raise Rejected("The keyring on the remote has a root signature that doesn't check out, so it is refused.")
        rotation = ring["epoch"] == prev["epoch"] + 1
        if rotation:
            if ring["kid"] == prev["kid"] or ring["root"] == prev["root"] or added:
                raise Rejected("A rotation on the remote doesn't bring a new key and a new root, or adds a device, so it is refused.")
        elif ring["epoch"] != prev["epoch"] or ring["kid"] != prev["kid"] or ring["root"] != prev["root"] or set(members) - set(now) \
                or any(now[i]["added_by"] not in ROOT_ADDED for i in added) or any(ring["wraps"][i] != prev["wraps"][i] for i in kept):
            raise Rejected("A step the root key signed changes more than it may without a rotation, so it is refused.")
        return
    signer = members.get(ring["signer"])
    if not signer or not verified(unsigned(ring), ring["sig"], signer["signer"]):
        raise Rejected("The keyring on the remote isn't signed by one of your devices, so it is refused.")
    if ring["epoch"] != prev["epoch"] or ring["kid"] != prev["kid"] or ring["recovery"] != prev["recovery"] or ring["root"] != prev["root"]:
        raise Rejected("A device tried to change the key or the recovery key without the recovery key, so it is refused.")
    gone = set(members) - set(now)
    if gone and (gone != {ring["signer"]} or added):
        raise Rejected("A device tried to take another device out without the recovery key, so it is refused.")
    if any(now[i]["added_by"] != ring["signer"] for i in added):
        raise Rejected("A device added another and said someone else added it, so it is refused.")
    if any(ring["wraps"][i] != prev["wraps"][i] for i in kept):
        raise Rejected("A device tried to change another device's keys, so it is refused.")


IGNORABLE = dict.fromkeys([0x200C, 0x200D, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x206A, 0x2070), 0xFEFF])  # what HFS+ ignores in names, as git's is_hfs_dotgit


def fold(part: str) -> str:
    """A path part as a Mac or Windows file system sees it: case folded, HFS-ignorable code points dropped, NTFS's
    trailing dots and spaces dropped."""
    return part.translate(IGNORABLE).casefold().rstrip(". ")


def git_special(folded: str) -> bool:
    """.git, .gitattributes or .gitmodules in any spelling a file system takes for them, NTFS 8.3 short names included
    (git's is_ntfs_dotgit, is_ntfs_dotgitattributes, is_ntfs_dotgitmodules)."""
    return folded in (".git", ".gitattributes", ".gitmodules") or re.fullmatch(r"git~\d+|gitatt~\d+|gitmod~\d+|gi7d29~\d+|gi7d32~\d+|gi250a~\d+", folded) is not None


def beacon_name(device_id: str) -> str:
    return "o/" + hashlib.sha256(f"{FORMAT}/beacon/{device_id}".encode()).hexdigest()[:40]


def added_by_removed(members: list, gone: str) -> list:
    """Every member that the removed one added, and every member those added, and so on."""
    out, frontier = [], {gone}
    while frontier:
        found = [m for m in members if m["added_by"] in frontier and m["id"] not in out and m["id"] != gone]
        out += [m["id"] for m in found]
        frontier = {m["id"] for m in found}
    return out


# ── one device's sync ──
class Sync:
    """Everything sync does on one device. `config` holds the keys and settings (the instance's config folder), `state`
    what was accepted and sent (its state folder), `stores` the folder of memory stores. `second` is a second instance:
    it may touch only stores named hub-test-throwaway-*, and it never re-keys or wipes a remote it didn't set up."""

    def __init__(self, config: Path, state: Path, stores: Path, second: bool, now=time.time, clones: Path | None = None, github_url: str | None = None):
        self.dir, self.state_dir, self.stores = Path(config), Path(state), Path(stores)
        self.second, self.now = second, now
        self.keys_dir = self.dir / "keys"
        self.clones = Path(clones) if clones else self.state_dir / "github"
        self.lock = threading.RLock()
        self.busy = False
        self.pairing = None  # in memory only: the code is never written down
        self.wake = threading.Event()
        self.thread = None
        self.attributes = self.state_dir / "merge-attributes"
        self.github_url = github_url  # tests only: a local bare repo in place of GitHub
        self.problems = []
        self.hold = self.paused = False
        self._needs = (-1e9, [])
        sweep_roots(self.dir, tempfile.gettempdir())

    # ── files of our own ──
    def _private(self, folder: Path):
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(folder, 0o700)

    def _write(self, path: Path, data: bytes):
        self._private(path.parent)
        spare = path.with_name(f".{path.name}.tmp")
        fd = os.open(spare, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(spare, path)

    def _json(self, path: Path, default):
        try:
            return json.loads(path.read_text())
        except FileNotFoundError:
            return default

    @property
    def settings(self) -> dict:
        return self._json(self.dir / "sync.json", {})

    def _save_settings(self, settings: dict):
        self._write(self.dir / "sync.json", json.dumps(settings, indent=1).encode())

    @property
    def st(self) -> dict:
        return self._json(self.state_dir / "sync-state.json", {})

    def _save_state(self, state: dict):
        self._write(self.state_dir / "sync-state.json", json.dumps(state, indent=1).encode())

    def _update(self, change):
        state = self.st
        change(state)
        self._save_state(state)

    def _device_identity(self) -> str:
        return (self.keys_dir / "device.key").read_text().strip()

    def _data(self) -> Keys:
        held = json.loads((self.keys_dir / "data.key").read_text())
        return Keys(bytes.fromhex(held["key"]), held["epoch"])

    def _save_data(self, keys: Keys):
        self._write(self.keys_dir / "data.key", json.dumps({"key": keys.key.hex(), "epoch": keys.epoch}).encode())

    def _pinned(self):
        """The newest keyring this device has checked and accepted."""
        try:
            return json.loads((self.state_dir / "keyring.json").read_text())
        except FileNotFoundError:
            return None

    def _pin(self, ring: dict):
        self._write(self.state_dir / "keyring.json", json.dumps(ring).encode())

    # ── the second-instance rule ──
    def allowed(self, name: str) -> bool:
        return isinstance(name, str) and bool(STORE_NAME.fullmatch(name)) and (not self.second or name.startswith(THROWAWAY))

    def guard(self, name: str):
        if not isinstance(name, str) or not STORE_NAME.fullmatch(name):
            raise Refused("That isn't a store name.")
        if self.second and not name.startswith(THROWAWAY):
            raise Refused(f"A second instance syncs only hub-test-throwaway-* stores, and {name} isn't one.", reason="second_instance")

    def _own_remote(self, settings: dict, what: str):
        if self.second and not settings.get("created"):
            raise Refused(f"A second instance can {what} only on a sync it set up itself.", reason="second_instance")

    # ── the backend ──
    def _backend(self, settings: dict):
        if settings.get("backend") == "folder":
            return Folder(settings.get("path"))
        if settings.get("backend") == "github":
            return GitHub(self.clones / REPO, self.github_url or settings.get("url"), settings.get("repo"), TEST_REPO if self.second else REPO)
        raise Malformed("Say which backend: github or folder.")

    def _remote_id(self, remote) -> str:
        raw = remote.read("remote.json")
        try:
            info = json.loads(raw) if raw else None
        except ValueError:
            info = None
        if not isinstance(info, dict) or info.get("format") != FORMAT or not isinstance(info.get("id"), str) or not re.fullmatch(r"[0-9a-f]{32}", info["id"]):
            raise Refused("There's no Context Hub sync in that place yet: set it up on your first device.", reason="no_sync_here")
        if info.get("v") != VERSION:
            raise Refused("That sync was made by a different version of Context Hub.", reason="version")
        if self.second and info.get("second") is not True:
            raise Refused("A second instance joins only a sync a second instance set up, never the installed hub's.", reason="second_instance")
        return info["id"]

    # ── reading, checking and writing the keyring ──
    def _read_ring(self, remote, name="keyring.json"):
        raw = remote.read(name, RING_CAP)
        if raw is None:
            return None
        try:
            return ring_shape(json.loads(raw))
        except (ValueError, UnicodeError):
            raise Rejected("The keyring on the remote isn't readable, so it is refused.")

    def _resolve(self, remote, latest: dict, pinned, root: str) -> dict:
        """Accept `latest` only if every step from what this device trusts checks out: the keyring it pinned, or for a
        device with none yet, the newest keyring that the root key it was given (joining) or opened (recovering)
        signed or handed over to. The walk back is no longer than the gap to the pin, and never longer than WALK."""
        if pinned and digest(latest) == digest(pinned):
            return latest
        if pinned and ring_order(latest) <= ring_order(pinned):
            raise Rejected("The remote offers an older or different keyring than this device already accepted: a rollback, refused.")
        limit = min(WALK, latest["rev"] - pinned["rev"] + 1) if pinned else min(WALK, latest["rev"])
        chain, current = [latest], latest
        for _ in range(max(limit, 1)):
            if pinned and ring_order(current) <= ring_order(pinned):
                if digest(current) != digest(pinned):
                    raise Rejected("The keyring's history on the remote doesn't lead back to the one this device trusts, so it is refused.")
                chain.pop()
                base = pinned
                break
            if current["signer"] == "root" and root_signed_by(current, root):
                chain.pop()
                base = current
                break
            if current["signer"] == "root" and current["root"] == root:
                raise Rejected("The keyring on the remote has a root signature that doesn't check out, so it is refused.")
            earlier = self._read_ring(remote, f"k/{current['rev'] - 1:08d}.json") if current["rev"] > 1 else None
            if earlier is None:
                raise Unverifiable("A step of the keyring's history is missing from the remote, so the newest keyring can't be checked.")
            chain.append(earlier)
            current = earlier
        else:
            raise Unverifiable("The keyring's history on the remote doesn't reach a keyring this device can check.")
        for ring in reversed(chain):
            check_step(base, ring)
            base = ring
        return base

    def _open_wrap(self, ring: dict, device_id: str) -> Keys:
        """This device's wrap, opened only after the keyring it is in was checked."""
        wrap = ring["wraps"].get(device_id)
        if wrap is None:
            raise Removed("This device was removed from sync on another device.")
        key = decrypt(unb64(wrap), self._device_identity())
        if len(key) != 32 or not hmac.compare_digest(kid_of(key), ring["kid"]):
            raise Rejected("The key this device was given doesn't match the keyring, so it is refused.")
        return Keys(key, ring["epoch"])

    def _body(self, ring: dict, keys: Keys) -> dict:
        try:
            body = json.loads(decrypt(unb64(ring["body"]), keys.identity))
        except ValueError:
            raise Rejected("The keyring's device list isn't readable.")
        if not isinstance(body, dict) or not isinstance(body.get("devices"), dict) or not isinstance(body.get("removed", []), list):
            raise Rejected("The keyring's device list isn't in the shape sync makes.")
        return body

    def _accept(self, remote, settings: dict):
        """The keyring this sync works under. A remote keyring that is missing, unreadable or older than the pinned one
        is put back from the pin and reported; one that checks out is pinned. "Removed" is concluded only from a
        keyring that checked out."""
        pinned = self._pinned()
        if pinned is None:
            raise Refused("This device has no keyring it trusts; turn sync off and join again.", reason="no_keyring")
        try:
            latest = self._read_ring(remote)
            problem = None if latest is not None else "The keyring was missing from the remote; this device put its own back."
        except Rejected as bad:
            latest, problem = None, f"{bad} This device put its own back."
        if latest is not None and ring_order(latest) < ring_order(pinned):
            latest, problem = None, "The remote offered an older keyring than this device already accepted: a rollback, refused; this device put its own back."
        ring = None
        if latest is not None:
            try:
                ring = self._resolve(remote, latest, pinned, pinned["root"])
            except Unverifiable as bad:
                if latest["epoch"] <= pinned["epoch"]:
                    raise
                self.hold = True  # perhaps a rotation this device can't check yet: receive under the old key, send nothing
                self.paused = True
                self.problems.append(f"{bad} This device holds back what it would send until it can check the new key.")
                ring = pinned
            except Rejected as bad:
                problem = f"{bad} This device put its own back."
        if ring is None:
            if latest is not None and latest["epoch"] > pinned["epoch"]:
                self.hold = True  # a rotation may have happened that this device can't see yet: send nothing under the old key
                self.paused = True
                problem = problem[:-1] + ", and holds back what it would send until it sees the new key."
            self._republish(remote, pinned)
            self.problems.append(problem)
            ring = pinned
        me = settings["device"]["id"]
        if me not in {m["id"] for m in ring["members"]}:
            self._pin(ring)
            self._update(lambda s: s.update(removed=True))
            raise Removed("This device was removed from sync on another device.")
        keys = self._open_wrap(ring, me)
        body = self._body(ring, keys)
        self._pin(ring)
        old = self._data()
        if keys.epoch != old.epoch or keys.key != old.key:
            self._save_data(keys)
            self._new_epoch(keys.epoch)
        self._update(lambda s: s.update(devices=self._devices(ring, body, s)))
        return ring, keys, body

    def _republish(self, remote, ring: dict):
        """Put back the keyring this device checked: over a missing, junk, older or forged one."""
        remote.write("keyring.json", json.dumps(ring).encode())
        remote.write(f"k/{ring['rev']:08d}.json", json.dumps(ring).encode())

    def _publish(self, remote, base: dict, ring: dict, signer, handover=None) -> dict:
        """Write the next keyring, only over the one it was made from: compare-and-swap through its history file,
        which can be made once. A device that loses the race is told to try again."""
        ring = {**ring, "rev": base["rev"] + 1, "prev": digest(base), "sig": "", "handover": ""}
        ring["members"] = sorted(ring["members"], key=lambda m: m["id"])
        ring["sig"] = signer(unsigned(ring))
        if handover:
            ring["handover"] = handover(unsigned(ring))
        ring_shape(ring)
        current = self._read_ring(remote)
        if current is not None and digest(current) != digest(base):
            raise Refused("The keyring changed on another device meanwhile; try again.", reason="retry")
        name = f"k/{ring['rev']:08d}.json"
        if not remote.write_new(name, json.dumps(ring).encode()):
            try:  # a real change by another device is a race lost; anything else in that place is junk, written over
                there = self._read_ring(remote, name)
                if there is None:
                    raise Rejected("gone")
                check_step(base, there)
                raise Refused("The keyring changed on another device meanwhile; try again.", reason="retry")
            except Rejected:
                remote.write(name, json.dumps(ring).encode())
        remote.write("keyring.json", json.dumps(ring).encode())
        return ring

    def _sign_as_device(self, data: bytes) -> str:
        return sign(data, self.keys_dir / "sign.key")

    def _seal_body(self, body: dict, keys: Keys) -> str:
        return b64(encrypt(canonical(body), [keys.recipient]))

    def _devices(self, ring: dict, body: dict, state: dict) -> list:
        """The device list, from the signed member entries: a name is shown only if it matches the hash the entry
        holds, and who added a device comes from the entry, never from the encrypted body a member can rewrite."""
        before = {d["id"]: d for d in state.get("devices", [])}

        def name_of(member):
            info = body["devices"].get(member["id"]) if isinstance(body["devices"].get(member["id"]), dict) else {}
            name = info.get("name")
            return (name[:60], info) if isinstance(name, str) and name_hash(name) == member["name_hash"] else ("A device whose name doesn't check out", info)
        names = {m["id"]: name_of(m)[0] for m in ring["members"]}
        out = []
        for member in ring["members"]:
            name, info = name_of(member)
            by = member["added_by"]
            out.append({"id": member["id"], "name": name, "added": info.get("added") if isinstance(info.get("added"), str) else None,
                        "added_by": by if by in ROOT_ADDED else names.get(by, "a device no longer in sync"),
                        "last_seen": before.get(member["id"], {}).get("last_seen")})
        return out

    # ── what the person sees ──
    def needs(self) -> list:
        if time.monotonic() - self._needs[0] < 300:
            return self._needs[1]
        need = []
        if not tool("age") or not tool("age-keygen"):
            need.append("age")
        if not tool("gh") or subprocess.run([tool("gh"), "auth", "token"], capture_output=True, timeout=15, env=ENV).returncode != 0:
            need.append("gh_login")  # `gh auth token` reads the local login only; its output is thrown away unread
        self._needs = (time.monotonic(), need)
        return need

    def local_stores(self) -> list:
        if not self.stores.is_dir():
            return []
        return sorted(p.name for p in self.stores.iterdir() if STORE_NAME.fullmatch(p.name) and (p / "ORG.md").exists() and (p / ".git").exists())

    def status(self, recheck: bool = False) -> dict:
        if recheck:
            self._needs = (-1e9, [])
        settings, state = self.settings, self.st
        enabled = bool(settings.get("enabled"))
        backend = None
        if enabled:
            try:
                backend = self._backend(settings)
            except Refused:
                backend = None
        names = sorted(set(self.local_stores()) | set(state.get("stores", {})))
        off = set(settings.get("off", []))
        stores = []
        for name in names:
            seen = state.get("stores", {}).get(name, {})
            if not self.allowed(name):
                stores.append({"name": name, "synced": False, "state": "off", "detail": f"A second instance syncs only hub-test-throwaway-* stores, and {name} isn't one.",
                               "last_sent": None, "last_received": None})
                continue
            synced = enabled and name not in off
            stores.append({"name": name, "synced": synced, "state": seen.get("state", "pending") if synced else "off",
                           "detail": seen.get("detail") if synced else None, "last_sent": seen.get("last_sent"), "last_received": seen.get("last_received")})
        me = settings.get("device")
        devices = [{**d, "this": bool(me and d["id"] == me["id"])} for d in state.get("devices", [])]
        pairing = None
        if self.pairing and self.pairing["expires"] > self.now():
            pairing = {"code": self.pairing["code"], "expires_at": iso(self.pairing["expires"]), "check": self.pairing.get("check", ""), "state": self.pairing["state"]}
        joining = settings.get("joining")
        return {"enabled": enabled, "backend": settings.get("backend") if enabled else None, "remote_label": backend.label if backend else None,
                "device": {"id": me["id"], "name": me["name"]} if me and enabled else None, "devices": devices if enabled else [],
                "stores": stores, "last_sync": iso(state.get("last_sync")), "next_sync": iso(state.get("next_sync")) if enabled else None,
                "busy": self.busy, "error": state.get("error"), "error_kind": state.get("error_kind") if state.get("error") else None,
                "removed": bool(state.get("removed")), "needs": self.needs(), "pairing": pairing,
                "joining": {"check": joining["check"], "expires_at": iso(joining["expires"])} if joining else None}

    # ── setting up ──
    def _require_tools(self):
        if not tool("age") or not tool("age-keygen"):
            raise Refused("Sync needs age: brew install age, then try again.", reason="needs_age")
        if not os.path.exists(_ssh_keygen()):
            raise Refused("Sync needs ssh-keygen, which macOS ships in /usr/bin.", reason="needs_ssh_keygen")

    def _new_device(self, name: str) -> dict:
        """This device's two keys: an age identity to receive the data key, an ed25519 key to sign keyrings."""
        shutil.rmtree(self.keys_dir, ignore_errors=True)
        self._private(self.keys_dir)
        identity = identity_of(secrets.token_bytes(32))
        self._write(self.keys_dir / "device.key", (identity + "\n").encode())
        signer = new_signing_key(self.keys_dir / "sign.key")
        return {"id": secrets.token_hex(8), "name": name, "recipient": recipient_of(identity), "signer": signer, "added": iso(self.now())}

    def _device_name(self, name) -> str:
        if name is None:
            name = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True, text=True).stdout.strip() or socket.gethostname()
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise Malformed("Give this device a name of up to 60 characters.")
        return " ".join(name.split())

    def _not_set_up(self):
        settings = self.settings
        if settings.get("enabled") or settings.get("joining"):
            raise Refused("Sync is already on for this device, or joining; turn it off first.", reason="already_on")

    @staticmethod
    def _member(device: dict, added_by: str) -> dict:
        """A device's entry: its public keys, who vouched for it and a hash of its name, all covered by the signatures
        and never changed by a later step, so a device can't be relabelled or made to look added by setup."""
        return {"id": device["id"], "recipient": device["recipient"], "signer": device["signer"], "added_by": added_by, "name_hash": name_hash(device["name"])}

    def _start(self, remote, keys: Keys, ring: dict, device: dict, created: bool):
        self._save_data(keys)
        self._pin(ring)
        self._save_settings({**remote.settings(), "enabled": True, "created": created, "device": {"id": device["id"], "name": device["name"]}, "off": []})
        self._save_state({"epoch": keys.epoch, "seq": 0, "hash": "", "peers": {}, "stores": {}, "devices": []})

    def setup(self, body: dict) -> dict:
        with self.lock:
            self._not_set_up()
            self._require_tools()
            remote = self._backend(body)
            remote.make()
            remote.begin()
            if remote.read("keyring.json", RING_CAP) is not None or not remote.empty():
                raise Refused("That place already holds something: join the sync there with a code from one of your devices, or use the recovery key.", reason="remote_not_empty")
            remote_id = secrets.token_hex(16)
            device = self._new_device(self._device_name(body.get("name")))
            keys = Keys(secrets.token_bytes(32), 1)
            recovery = make_code(RECOVERY_GROUPS)
            derived = code_keys(read_code(recovery, RECOVERY_GROUPS, "recovery key"), remote_id, "recovery")
            root_public, root_private = new_root(self.dir)
            to_recovery = recipient_of(derived["identity"])
            ring = {"format": FORMAT, "v": VERSION, "epoch": 1, "rev": 1, "prev": "", "root": root_public, "handover": "", "kid": keys.kid,
                    "members": [self._member(device, "setup")], "wraps": {device["id"]: b64(encrypt(keys.key, [device["recipient"]]))},
                    "recovery": {"wrap": b64(encrypt(keys.key, [to_recovery])), "root": b64(encrypt(root_private, [to_recovery]))},
                    "body": self._seal_body({"devices": {device["id"]: {"name": device["name"], "added": device["added"], "added_by": "setup"}}, "removed": []}, keys),
                    "signer": "root", "sig": ""}
            with RootKey(root_private, self.dir) as root:
                ring["sig"] = root.sign(unsigned(ring))
            del root_private
            ring_shape(ring)
            remote.write("remote.json", json.dumps({"format": FORMAT, "v": VERSION, "id": remote_id, **({"second": True} if self.second else {})}).encode())
            remote.write_new("k/00000001.json", json.dumps(ring).encode())
            remote.write("keyring.json", json.dumps(ring).encode())
            remote.finish()
            self._start(remote, keys, ring, device, created=True)
            self.wake.set()
            return {"ok": True, "recovery_key": recovery}

    # ── pairing: the new device asks, the device already in shows six digits, the person confirms there ──
    @staticmethod
    def _pair_names(derived: dict) -> tuple:
        name = lambda what: "p/" + hmac.new(derived["name"], what, hashlib.sha256).hexdigest()[:40]
        return name(b"request"), name(b"reply")

    def _enabled(self) -> dict:
        settings = self.settings
        if not settings.get("enabled"):
            raise Refused("Sync isn't on for this device.", reason="not_on")
        return settings

    def pair(self) -> dict:
        """A code for a new device. While one is open (waiting or waiting for the confirm) the same one is answered again,
        so a page that asks twice never shows a code this device no longer holds; Cancel ends it."""
        with self.lock:
            settings = self._enabled()
            if self.pairing and self.pairing["state"] in ("waiting", "confirm") and self.pairing["expires"] > self.now():
                return {"code": self.pairing["code"], "expires_at": iso(self.pairing["expires"]), "check": self.pairing["check"], "state": self.pairing["state"]}
            remote = self._backend(settings)
            remote.begin()
            self._drop_pairing(remote)
            code = make_code(PAIR_GROUPS)
            derived = code_keys(read_code(code, PAIR_GROUPS, "pairing code"), self._remote_id(remote), "pair")
            request, reply = self._pair_names(derived)
            for name in (request, reply):
                remote.delete(name)
            remote.finish()
            expires = self.now() + PAIR_SECONDS
            self.pairing = {"code": code, "expires": expires, "derived": derived, "request": request, "reply": reply, "state": "waiting", "check": "", "joiner": None}
            self._update(lambda s: s.update(pair_files=[request, reply], pair_expires=expires))
            self.wake.set()
            return {"code": code, "expires_at": iso(expires), "check": "", "state": "waiting"}

    def _drop_pairing(self, remote):
        """What a pairing left on the remote. The names are kept on disk (never the code), so this works after a restart too."""
        for name in self.st.get("pair_files", []) + ([self.pairing["request"], self.pairing["reply"]] if self.pairing else []):
            try:
                remote.delete(name)
            except Rejected:
                pass
        self._update(lambda s: (s.pop("pair_files", None), s.pop("pair_expires", None)))
        self.pairing = None

    def cancel_pair(self) -> dict:
        with self.lock:
            settings = self._enabled()
            remote = self._backend(settings)
            remote.begin()
            self._drop_pairing(remote)
            remote.finish()
            return {"ok": True}

    def _pairing_tick(self, remote):
        """Look for the new device's request; drop the pairing when it expires, and leftovers from before a restart."""
        if not self.pairing:
            if self.st.get("pair_files"):
                self._drop_pairing(remote)
            return
        if self.pairing["expires"] <= self.now():
            self._drop_pairing(remote)
            return
        if self.pairing["state"] != "waiting":
            return
        raw = remote.read(self.pairing["request"])
        if raw is None:
            return
        try:
            request = json.loads(raw)
            if not isinstance(request, dict) or not same_hex(request.get("mac"), mac(self.pairing["derived"]["mac"], b"request", str(request.get("ct", "")).encode())):
                raise Rejected("A pairing request on the remote failed its check, so it was ignored.")
            asked = json.loads(decrypt(unb64(request["ct"]), self.pairing["derived"]["identity"]))
            if not (isinstance(asked, dict) and isinstance(asked.get("id"), str) and DEVICE_ID.fullmatch(asked["id"])
                    and isinstance(asked.get("recipient"), str) and RECIPIENT.fullmatch(asked["recipient"])
                    and isinstance(asked.get("signer"), str) and SIGNER.fullmatch(asked["signer"])
                    and isinstance(asked.get("name"), str) and 0 < len(asked["name"]) <= 60):
                raise Rejected("A pairing request on the remote isn't in the shape sync makes, so it was ignored.")
        except (Rejected, ValueError, KeyError) as problem:
            remote.delete(self.pairing["request"])
            self.problems.append(str(problem) if isinstance(problem, Rejected) else "A pairing request on the remote isn't readable, so it was ignored.")
            return
        self.pairing.update(state="confirm", check=six(asked["recipient"], asked["signer"]), joiner=asked)

    def confirm_pair(self, body: dict) -> dict:
        """The person saw the same six digits on both screens and sends them back: only now is the data key wrapped to
        the new device. Digits that differ from the waiting device's are refused, so a confirm can't land on another."""
        typed = re.sub(r"\s", "", body.get("check", "")) if isinstance(body, dict) and isinstance(body.get("check"), str) else None
        if not typed or not re.fullmatch(r"[0-9]{6}", typed):
            raise Malformed("Send the six digits you saw on both screens.", reason="bad_input")
        with self.lock:
            settings = self._enabled()
            self._own_remote(settings, "add devices")
            if not self.pairing or self.pairing["state"] != "confirm" or self.pairing["expires"] <= self.now():
                raise Refused("No device is waiting to be confirmed.", reason="nothing_to_confirm")
            if not hmac.compare_digest(typed.encode(), self.pairing["check"].encode()):
                raise Refused("Those digits aren't the ones the waiting device shows, so nothing was handed over.", reason="wrong_check")
            remote = self._backend(settings)
            remote.begin()
            ring, keys, body = self._accept(remote, settings)
            joiner = self.pairing["joiner"]
            if joiner["id"] in {m["id"] for m in ring["members"]}:
                raise Refused("That device is already in this sync.", reason="already_member")
            body["devices"][joiner["id"]] = {"name": joiner["name"], "added": iso(self.now())}
            new = {**ring, "members": ring["members"] + [self._member(joiner, settings["device"]["id"])], "wraps": {**ring["wraps"], joiner["id"]: b64(encrypt(keys.key, [joiner["recipient"]]))},
                   "body": self._seal_body(body, keys), "signer": settings["device"]["id"]}
            new = self._publish(remote, ring, new, self._sign_as_device)
            signed = {"v": VERSION, "root": ring["root"], "rev": new["rev"], "hash": digest(new), "id": joiner["id"]}
            remote.write(self.pairing["reply"], json.dumps({**signed, "mac": mac(self.pairing["derived"]["mac"], b"reply", canonical(signed)).hex()}).encode())
            remote.delete(self.pairing["request"])
            remote.finish()
            self._pin(new)
            self.pairing["state"] = "done"
            self._update(lambda s: s.update(devices=self._devices(new, body, s)))
            self.wake.set()
            return {"ok": True}

    def join(self, body: dict) -> dict:
        """The new device posts its public keys, MACed with the code. It holds no key until the other device confirms."""
        with self.lock:
            self._not_set_up()
            self._require_tools()
            code = read_code(body.get("code"), PAIR_GROUPS, "pairing code")
            remote = self._backend(body)
            remote.begin()
            derived = code_keys(code, self._remote_id(remote), "pair")
            request, reply = self._pair_names(derived)
            device = self._new_device(self._device_name(body.get("name")))
            asked = {"id": device["id"], "recipient": device["recipient"], "signer": device["signer"], "name": device["name"]}
            ct = b64(encrypt(canonical(asked), [recipient_of(derived["identity"])]))
            if not remote.write_new(request, json.dumps({"ct": ct, "mac": mac(derived["mac"], b"request", ct.encode()).hex()}).encode()):
                raise Refused("Another device is already answering that code: make a new one on your other device.", reason="code_in_use")
            remote.finish()
            check = six(device["recipient"], device["signer"])
            self._write(self.keys_dir / "joining.json", json.dumps({"mac": derived["mac"].hex(), "reply": reply, "request": request}).encode())
            self._save_settings({**remote.settings(), "enabled": False, "created": False, "device": {"id": device["id"], "name": device["name"]},
                                 "off": [], "joining": {"check": check, "expires": self.now() + PAIR_SECONDS}})
            self._save_state({})
            self.wake.set()
            return {"ok": True, "check": check}

    def _joining_tick(self, settings: dict):
        """On the new device: wait for the reply that the person confirmed. The reply names the root key and the keyring
        that added this device, MACed with the code; everything else is checked from that root."""
        joining = settings["joining"]
        held = json.loads((self.keys_dir / "joining.json").read_text())
        remote = self._backend(settings)
        remote.begin()
        if joining["expires"] <= self.now():
            remote.delete(held["request"])
            remote.finish()
            shutil.rmtree(self.keys_dir, ignore_errors=True)
            self._save_settings({})
            self._save_state({"error": "The pairing wasn't confirmed on your other device within ten minutes: make a new code and try again.", "error_kind": "expired"})
            return
        raw = remote.read(held["reply"])
        if raw is None:
            return
        try:
            reply = json.loads(raw)
            signed = {k: v for k, v in reply.items() if k != "mac"} if isinstance(reply, dict) else None
            if not signed or not same_hex(reply.get("mac"), mac(bytes.fromhex(held["mac"]), b"reply", canonical(signed))) or signed.get("id") != settings["device"]["id"]:
                raise Rejected("The pairing reply on the remote failed its check, so it was ignored.")
            if not isinstance(signed.get("root"), str) or not SIGNER.fullmatch(signed["root"]):
                raise Rejected("The pairing reply on the remote isn't in the shape sync makes.")
            latest = self._read_ring(remote)
            if latest is None:
                raise Rejected("The keyring is missing from the remote.")
            if not isinstance(signed.get("rev"), int) or isinstance(signed["rev"], bool) or not isinstance(signed.get("hash"), str):
                raise Rejected("The pairing reply on the remote isn't in the shape sync makes.")
            added = self._read_ring(remote, f"k/{signed['rev']:08d}.json")
            if added is None or digest(added) != signed["hash"] or signed["id"] not in {m["id"] for m in added["members"]}:
                raise Rejected("The keyring that added this device isn't on the remote as the other device confirmed it, so nothing was taken; make a new code and try again.")
            if digest(self._resolve(remote, added, None, signed["root"])) != digest(added):
                raise Rejected("The keyring that added this device doesn't check out, so it is refused.")
            ring = self._resolve(remote, latest, added, signed["root"])  # nothing older than it, and only through it
            keys = self._open_wrap(ring, settings["device"]["id"])
        except (Rejected, ValueError, KeyError) as problem:
            self._update(lambda s: s.update(error=str(problem) if isinstance(problem, Rejected) else "The pairing reply on the remote isn't readable.", error_kind="remote_refused"))
            return
        remote.delete(held["reply"])
        remote.finish()
        (self.keys_dir / "joining.json").unlink()
        device = {"id": settings["device"]["id"], "name": settings["device"]["name"]}
        self._start(remote, keys, ring, device, created=False)

    def recover(self, body: dict) -> dict:
        """Every device lost: the recovery key opens the root key and the data key, and the root key adds this device."""
        with self.lock:
            self._not_set_up()
            self._require_tools()
            code = read_code(body.get("recovery_key"), RECOVERY_GROUPS, "recovery key")
            remote = self._backend(body)
            remote.begin()
            remote_id = self._remote_id(remote)
            latest = self._read_ring(remote)
            if latest is None:
                raise Refused("The keyring is missing from the remote.", reason="tampered")
            name = self._device_name(body.get("name"))
            try:
                root_private, key = self._open_recovery(code, remote_id, latest)
                device = self._new_device(name)
                with RootKey(root_private, self.dir) as root:
                    if root.public != latest["root"]:  # only the newest root, which this recovery key opens; an old chain replayed doesn't open with it
                        raise Refused("That recovery key doesn't open this sync.", reason="wrong_recovery_key")
                    ring = self._resolve(remote, latest, None, root.public)
                    keys = Keys(key, ring["epoch"])
                    if keys.kid != ring["kid"] or ring["root"] != root.public:
                        raise Refused("That recovery key doesn't open this sync.", reason="wrong_recovery_key")
                    ring_body = self._body(ring, keys)
                    ring_body["devices"][device["id"]] = {"name": device["name"], "added": device["added"]}
                    new = {**ring, "members": ring["members"] + [self._member(device, "recovery")], "wraps": {**ring["wraps"], device["id"]: b64(encrypt(keys.key, [device["recipient"]]))},
                           "body": self._seal_body(ring_body, keys), "signer": "root"}
                    new = self._publish(remote, ring, new, root.sign)
            except Rejected as problem:
                raise Refused(str(problem), reason=kind_of(problem))
            remote.finish()
            self._start(remote, keys, new, device, created=False)
            self.wake.set()
            return {"ok": True}

    def _open_recovery(self, code: str, remote_id: str, ring: dict) -> tuple:
        derived = code_keys(code, remote_id, "recovery")
        try:
            root_private = decrypt(unb64(ring["recovery"]["root"]), derived["identity"])
            key = decrypt(unb64(ring["recovery"]["wrap"]), derived["identity"])
        except Rejected:
            raise Refused("That recovery key doesn't open this sync.", reason="wrong_recovery_key")
        return root_private, key

    # ── per-store switch ──
    def set_store(self, body: dict) -> dict:
        name = body.get("name") if isinstance(body, dict) else None
        if not isinstance(name, str) or not isinstance(body.get("synced"), bool):
            raise Malformed("Say the store and whether it syncs.")
        self.guard(name)
        with self.lock:
            settings = self._enabled()
            off = set(settings.get("off", []))
            (off.discard if body["synced"] else off.add)(name)
            self._save_settings({**settings, "off": sorted(off)})
        self.wake.set()
        return {"ok": True}

    # ── removing a device: only the recovery key can, and it brings a new data key ──
    def remove_device(self, body: dict) -> dict:
        """Only the recovery key removes a device. The removal rotates everything the removed device could know or
        sign with: a new data key, a new root key (the old root signs the handover) and a new recovery key, shown once.
        Every device the removed one added goes too, and so on down, since a device it vouched for is its own."""
        gone = body.get("id") if isinstance(body, dict) else None
        if not isinstance(gone, str):
            raise Malformed("Say which device.")
        code = read_code(body.get("recovery_key"), RECOVERY_GROUPS, "recovery key")
        with self.lock:
            settings = self._enabled()
            self._own_remote(settings, "remove devices")
            me = settings["device"]["id"]
            if gone == me:
                raise Refused("To take this device out, turn sync off here.", reason="this_device")
            remote = self._backend(settings)
            remote.begin()
            try:
                ring, keys, body_ = self._accept(remote, settings)
                if gone not in {m["id"] for m in ring["members"]}:
                    raise Refused("That device isn't in this sync.", reason="not_member")
                also = added_by_removed(ring["members"], gone)
                if me in also:
                    raise Refused("This device was added by the one you are removing, so it would go too: remove it from another device.", reason="this_device")
                remote_id = self._remote_id(remote)
                root_private, _ = self._open_recovery(code, remote_id, ring)
                names = {d["id"]: d["name"] for d in self._devices(ring, body_, self.st)}
                with RootKey(root_private, self.dir) as root:
                    if root.public != ring["root"]:
                        raise Refused("That recovery key doesn't open this sync.", reason="wrong_recovery_key")
                    new_keys = Keys(secrets.token_bytes(32), ring["epoch"] + 1)
                    new_code = make_code(RECOVERY_GROUPS)
                    to_recovery = recipient_of(code_keys(read_code(new_code, RECOVERY_GROUPS, "recovery key"), remote_id, "recovery")["identity"])
                    new_public, new_private = new_root(self.dir)
                    leaving = {gone, *also}
                    staying = [m for m in ring["members"] if m["id"] not in leaving]
                    for device_id in leaving:
                        body_["devices"].pop(device_id, None)
                    body_["removed"] = body_.get("removed", []) + [{"id": i, "name": names.get(i, "A device"), "at": iso(self.now()), "by": me} for i in sorted(leaving)]
                    new = {**ring, "epoch": new_keys.epoch, "kid": new_keys.kid, "root": new_public, "members": staying,
                           "wraps": {m["id"]: b64(encrypt(new_keys.key, [m["recipient"]])) for m in staying},
                           "recovery": {"wrap": b64(encrypt(new_keys.key, [to_recovery])), "root": b64(encrypt(new_private, [to_recovery]))},
                           "body": self._seal_body(body_, new_keys), "signer": "root"}
                    with RootKey(new_private, self.dir) as fresh:
                        new = self._publish(remote, ring, new, fresh.sign, handover=root.sign)
                    del new_private
            except Rejected as problem:
                raise Refused(str(problem), reason=kind_of(problem))
            keep = {beacon_name(m["id"]) for m in staying}
            for name in remote.names("o") + remote.names("p") + [n for n in remote.names("k") if n != f"k/{new['rev']:08d}.json"]:
                if name not in keep:
                    remote.delete(name)  # every file under the old key and every older keyring; the new one is signed by the new root
            remote.finish()
            self._pin(new)
            self._save_data(new_keys)
            self._new_epoch(new_keys.epoch)
            self.pairing = None
            by = {m["id"]: m["added_by"] for m in ring["members"]}
            also_removed = [{"id": i, "name": names.get(i, "A device"), "added_by": names.get(by[i], "a removed device")} for i in also]
        self.sync()
        return {"ok": True, "recovery_key": new_code, "advice": REVOKE.get(settings.get("backend"), REVOKE["folder"]), "also_removed": also_removed}

    def _new_epoch(self, epoch: int):
        def change(s):
            s.update(epoch=epoch, seq=0, hash="", peers={})
            for seen in s.get("stores", {}).values():
                seen["tips"] = []
        self._update(change)

    # ── off ──
    def off(self, body: dict) -> dict:
        forget = body.get("forget_remote", False) if isinstance(body, dict) else False
        if not isinstance(forget, bool):
            raise Malformed("Say whether to forget the remote.")
        with self.lock:
            settings = self.settings
            if not settings.get("enabled") and not settings.get("joining"):
                raise Refused("Sync isn't on for this device.", reason="not_on")
            problem = None
            if forget:
                self._own_remote(settings, "forget the remote")
                code = read_code(body.get("recovery_key"), RECOVERY_GROUPS, "recovery key")
            try:
                remote = self._backend(settings)
                remote.begin()
                if forget:
                    ring, _, _ = self._accept(remote, settings)
                    self._open_recovery(code, self._remote_id(remote), ring)  # only the person, with the recovery key, wipes a remote every device uses
                    remote.forget()
                elif settings.get("enabled"):
                    ring, keys, body_ = self._accept(remote, settings)
                    me = settings["device"]["id"]
                    body_["devices"].pop(me, None)
                    new = {**ring, "members": [m for m in ring["members"] if m["id"] != me], "wraps": {k: v for k, v in ring["wraps"].items() if k != me},
                           "body": self._seal_body(body_, keys), "signer": me}
                    if new["members"]:
                        self._publish(remote, ring, new, self._sign_as_device)
                    remote.delete(keys.name("head", me))
                elif settings.get("joining"):
                    held = self._json(self.keys_dir / "joining.json", {})
                    for name in (held.get("request"), held.get("reply")):
                        if name:
                            remote.delete(name)
                remote.finish()
            except Rejected as failure:
                problem = str(failure)
            except Refused as failure:
                if forget:
                    raise
                problem = str(failure)
            shutil.rmtree(self.keys_dir, ignore_errors=True)
            for path in (self.dir / "sync.json", self.state_dir / "sync-state.json", self.state_dir / "keyring.json"):
                path.unlink(missing_ok=True)
            shutil.rmtree(self.state_dir / "held", ignore_errors=True)
            shutil.rmtree(self.clones, ignore_errors=True)
            self.pairing = None
            if problem:
                raise Refused(f"Sync is off on this device, but the remote wasn't updated: {problem}", reason="off_remote_not_updated")
            return {"ok": True}

    # ── a sync ──
    def now_sync(self) -> dict:
        self._enabled()
        self.wake.set()
        return {"ok": True}

    def sync(self) -> dict:
        """Send what changed here, take what the other devices sent, merge it. Every failure is one sentence in `error`."""
        with self.lock:
            settings = self.settings
            if settings.get("joining"):
                try:
                    self._joining_tick(settings)
                except (Refused, Rejected) as problem:
                    self._update(lambda s: s.update(error=str(problem), error_kind=kind_of(problem)))
                return {"ok": True}
            if not settings.get("enabled"):
                return {"ok": False}
            self.busy = True
            self.problems = []
            self.hold = self.paused = False
            try:
                self._sync(settings)
                kind = "paused" if self.paused else "remote_refused" if self.problems else None
                self._update(lambda s: s.update(error=self.problems[0] if self.problems else None, error_kind=kind))
            except (Refused, Rejected) as problem:
                self._update(lambda s: s.update(error=str(problem), error_kind=kind_of(problem)))
            except Exception as problem:  # a remote can be anything: nothing it holds may stop sync for good
                print(f"error: sync: {type(problem).__name__}", flush=True)  # never the details: they could hold a path or more
                self._update(lambda s: s.update(error="Sync stopped on an unexpected problem; it will try again.", error_kind="unexpected"))
            finally:
                self.busy = False
                now = self.now()
                self._update(lambda s: s.update(last_sync=now, next_sync=now + EVERY))
            return {"ok": True}

    def _sync(self, settings: dict):
        remote = self._backend(settings)
        remote.begin()
        ring, keys, body = self._accept(remote, settings)
        self._pairing_tick(remote)
        me = settings["device"]["id"]
        peers = [{"id": m["id"], "name": next((d["name"] for d in self.st.get("devices", []) if d["id"] == m["id"]), "A device")} for m in ring["members"] if m["id"] != me]
        self._release_held(settings)
        seen = self._receive(remote, keys, peers, settings)
        self._beacons(remote, ring, me)
        self._merge_all(settings)
        if not self.hold:
            self._send(remote, keys, me, settings)

        def change(s):
            for device in s.get("devices", []):
                device["last_seen"] = iso(self.now()) if device["id"] == me else seen.get(device["id"]) or device.get("last_seen")
        self._update(change)
        remote.finish()

    # beacons: each device says, signed with its own key, the newest keyring it accepted
    def _beacons(self, remote, ring: dict, me: str):
        """Freshness that a removed device can't fake. Each device writes a beacon signed with its ed25519 key, naming
        the newest keyring it has accepted. A device holds back what it would send when any member's beacon names a
        newer keyring than its own, goes back to an older one, or disappears after it was seen: a removed device that
        hides a rotation from this device can delete beacons, but deleting one is itself the alarm."""
        state = self.st
        seen = {k: v for k, v in state.get("beacons", {}).items() if k in {m["id"] for m in ring["members"]}}
        mine = [ring["epoch"], ring["rev"]]
        name = beacon_name(me)
        current = None
        try:
            raw = remote.read(name)
            current = json.loads(raw) if raw else None
        except (Rejected, ValueError):
            current = None
        if not isinstance(current, dict) or current.get("ring") != mine:
            signed = {"device": me, "ring": mine, "at": self.now()}
            remote.write(name, json.dumps({**signed, "sig": self._sign_as_device(canonical(signed))}).encode())
        for member in ring["members"]:
            if member["id"] == me:
                continue
            who = next((d["name"] for d in state.get("devices", []) if d["id"] == member["id"]), "A device")
            try:
                raw = remote.read(beacon_name(member["id"]))
                beacon = json.loads(raw) if raw else None
            except (Rejected, ValueError):
                beacon = "junk"
            if beacon is None:
                if member["id"] in seen:
                    self._pause(f"The signed record of what {who} has seen is gone from the remote, so this device holds back what it would send.")
                continue
            signed = {k: v for k, v in beacon.items() if k != "sig"} if isinstance(beacon, dict) else None
            ok = signed is not None and signed.get("device") == member["id"] and isinstance(signed.get("ring"), list) and len(signed["ring"]) == 2 \
                and all(isinstance(x, int) and not isinstance(x, bool) for x in signed["ring"]) and verified(canonical(signed), beacon.get("sig"), member["signer"])
            if not ok:
                self._pause(f"The signed record of what {who} has seen doesn't check out, so this device holds back what it would send.")
                continue
            if member["id"] in seen and signed["ring"] < seen[member["id"]]:
                self._pause(f"The remote shows an older record of what {who} has seen: a rollback, so this device holds back what it would send.")
                continue
            seen[member["id"]] = signed["ring"]
            if signed["ring"] > mine:
                self._pause(f"{who} has accepted a newer keyring than the remote shows this device, so it holds back what it would send until it sees it.")
        self._update(lambda s: s.update(beacons=seen))

    def _pause(self, sentence: str):
        self.hold = self.paused = True
        self.problems.insert(0, sentence)

    # receiving
    def _receive(self, remote, keys: Keys, peers: list, settings: dict) -> dict:
        """Each other device's chain, in order, from the last bundle this device accepted. Returns when each was last seen."""
        accepted = dict(self.st.get("peers", {}))
        heads, seen = {}, {}
        for device in peers:
            name = keys.name("head", device["id"])
            mine = accepted.get(device["id"], {"seq": 0, "hash": ""})
            try:
                raw = remote.read(name)
                if raw is None:
                    if mine["seq"]:
                        raise Rejected(f"The record of what {device['name']} sent is missing from the remote, so nothing more is taken from it.")
                    continue
                head = json.loads(keys.unpack(name, raw))
                if not isinstance(head, dict) or head.get("device") != device["id"] or head.get("epoch") != keys.epoch or not isinstance(head.get("seq"), int) or not isinstance(head.get("hash"), str):
                    raise Rejected(f"The record of what {device['name']} sent doesn't belong where it was found, so it is refused.")
                if head["seq"] < mine["seq"] or (head["seq"] == mine["seq"] and not hmac.compare_digest(head["hash"].encode(), mine["hash"].encode())):
                    raise Rejected(f"The remote shows an older state of {device['name']} than this device already took: a rollback, refused.")
            except (Rejected, ValueError) as problem:
                self.problems.append(str(problem) if isinstance(problem, Rejected) else f"The record of what {device['name']} sent isn't readable.")
                continue
            heads[device["id"]] = (device, head)
            seen[device["id"]] = iso(head.get("at"))
        progress = True
        while progress:
            progress = False
            for device_id, (device, head) in list(heads.items()):
                try:
                    progress = self._chain(remote, keys, device, head, accepted, settings) or progress
                except (Rejected, ValueError) as problem:
                    self.problems.append(str(problem) if isinstance(problem, Rejected) else f"A bundle from {device['name']} isn't readable, so it is refused.")
                    del heads[device_id]  # nothing more from this device until the problem is gone
        waiting = [device["name"] for device_id, (device, head) in heads.items() if accepted.get(device_id, {"seq": 0})["seq"] < head["seq"]]
        self._update(lambda s: s.update(waiting=waiting))
        return seen

    def _chain(self, remote, keys: Keys, device: dict, head: dict, accepted: dict, settings: dict) -> bool:
        """Take one device's bundles in order, from the one after the last this device accepted. Each must pass its
        MAC, be the bundle its name says (device, sequence number, epoch) and follow the one before by hash."""
        moved = False
        mine = accepted.get(device["id"], {"seq": 0, "hash": ""})
        while mine["seq"] < head["seq"]:
            seq = mine["seq"] + 1
            name = keys.name("bundle", device["id"], str(seq))
            raw = remote.read(name, BUNDLE_CAP)
            if raw is None:
                raise Rejected(f"Bundle {seq} from {device['name']} is missing from the remote, so its later changes can't be taken.")
            plain = keys.unpack(name, raw)
            header_line, _, bundle = plain.partition(b"\n")
            header = json.loads(header_line)
            if not isinstance(header, dict) or header.get("device") != device["id"] or header.get("seq") != seq or header.get("epoch") != keys.epoch:
                raise Rejected(f"A bundle from {device['name']} isn't the one its name says: replayed or moved, refused.")
            if not hmac.compare_digest(str(header.get("prev", "")).encode(), mine["hash"].encode()):
                raise Rejected(f"A bundle from {device['name']} doesn't follow the one before it, so it is refused.")
            seal = hashlib.sha256(plain).hexdigest()
            if seq == head["seq"] and not hmac.compare_digest(seal.encode(), head["hash"].encode()):
                raise Rejected(f"The newest bundle from {device['name']} isn't the one its record names, so it is refused.")
            try:
                self._take(header, bundle, settings, device)
            except Deferred:
                return moved
            mine = {"seq": seq, "hash": seal}
            accepted[device["id"]] = mine
            self._update(lambda s: s.setdefault("peers", {}).__setitem__(device["id"], mine))
            moved = True
        return moved

    def _take(self, header: dict, bundle: bytes, settings: dict, device: dict):
        """One bundle into its store: fetched into refs/sync/<device>, merged afterwards. A store that is off keeps it in
        the held folder for later; one a second instance may not touch is passed over and never kept."""
        store = header.get("store")
        if not isinstance(store, str) or not STORE_NAME.fullmatch(store) or not DEVICE_ID.fullmatch(device["id"]) or not isinstance(header.get("seq"), int):
            raise Rejected("A bundle names a store or device that can't exist.")
        if not self.allowed(store):
            return
        if store in settings.get("off", []):
            self._write(self.state_dir / "held" / store / f"{header['epoch']:04d}-{device['id']}-{header['seq']:08d}.bundle", canonical(header) + b"\n" + bundle)
            self._mark(store, "pending", None)
            return
        self._fetch(store, header, bundle, device["id"])
        self._update(lambda s: self._store_state(s, store).update(last_received=iso(self.now()),
                                                                  branch=header["branch"] if isinstance(header.get("branch"), str) and re.fullmatch(r"[A-Za-z0-9._/-]{1,64}", header["branch"]) else "main"))

    def _store_state(self, state: dict, store: str) -> dict:
        return state.setdefault("stores", {}).setdefault(store, {"tips": [], "state": "pending", "detail": None, "last_sent": None, "last_received": None})

    def _mark(self, store: str, kind: str, detail):
        self._update(lambda s: self._store_state(s, store).update(state=kind, detail=detail))

    def _git(self, store: Path, *args, check=True, timeout=120):
        result = subprocess.run(["git", "-C", str(store), "-c", f"core.attributesFile={self.attributes}", "-c", "core.symlinks=false",
 *args],
                                capture_output=True, timeout=timeout, env={**ENV, **GIT_ID, "GIT_TERMINAL_PROMPT": "0"})
        if check and result.returncode != 0:
            raise Refused(f"git failed in {store.name}: " + " ".join(result.stderr.decode(errors="replace").split())[:160])
        return result

    def _tree_problem(self, store: Path, ref: str):
        """Memory is plain files. Refuse a bundle whose commits hold a link, a submodule, an executable (but the store's
        own notify.sh) or a .gitattributes or .gitmodules, which could change how git treats the store."""
        commits = self._git(store, "rev-list", "--max-count=2000", ref, "--not", "--exclude=" + ref, "--all").stdout.decode().split()
        for commit in commits:
            listing = self._git(store, "ls-tree", "-r", "-z", "--full-tree", commit).stdout.decode(errors="replace")
            folded = {}
            for entry in filter(None, listing.split("\0")):
                meta, _, path = entry.partition("\t")
                mode = meta.split(" ")[0]
                parts = [fold(part) for part in path.split("/")]
                if mode != "100644" and not (mode == "100755" and path == ALERT):
                    return f"A bundle for {store.name} holds {path} as a link, a submodule or an executable, which memory never is, so it is refused."
                if any(git_special(part) for part in parts):
                    return f"A bundle for {store.name} holds {path}, which could change how git treats the store, so it is refused."
                if parts == [ALERT] and path != ALERT:
                    return f"A bundle for {store.name} holds {path}, a second spelling of {ALERT}, so it is refused."
                key = "/".join(parts)
                if key in folded and folded[key] != path:
                    return f"A bundle for {store.name} holds {folded[key]} and {path}, which are one file on a Mac, so it is refused."
                folded[key] = path
        return None

    def _fetch(self, name: str, header: dict, bundle: bytes, device_id: str):
        self.guard(name)
        if not DEVICE_ID.fullmatch(device_id):
            raise Rejected("A bundle names a device that can't exist.")
        store = self.stores / name
        fresh = not store.exists()
        if fresh:
            store.mkdir(parents=True)
            self._git(store, "init", "-q", "-b", "main")
        with tempfile.NamedTemporaryFile(dir=self.state_dir, suffix=".bundle") as handle:
            os.chmod(handle.name, 0o600)
            handle.write(bundle)
            handle.flush()
            with self._store_lock(store):
                if self._git(store, "bundle", "verify", "-q", handle.name, check=False).returncode != 0:
                    if fresh:
                        shutil.rmtree(store)
                    raise Deferred()
                incoming = "refs/sync-incoming/" + device_id
                self._git(store, "fetch", "-q", "--no-tags", handle.name, f"+HEAD:{incoming}")
                problem = self._tree_problem(store, incoming)
                if problem:
                    self._git(store, "update-ref", "-d", incoming)
                    if fresh:
                        shutil.rmtree(store)
                    raise Rejected(problem)
                self._git(store, "update-ref", f"refs/sync/{device_id}", incoming)
                self._git(store, "update-ref", "-d", incoming)
        tip = self._git(store, "rev-parse", f"refs/sync/{device_id}").stdout.decode().strip()
        self._update(lambda s: self._add_tip(self._store_state(s, name), store, tip))

    def _add_tip(self, seen: dict, store: Path, tip: str):
        tips = [t for t in seen.get("tips", []) if t != tip]
        seen["tips"] = [t for t in tips if self._git(store, "merge-base", "--is-ancestor", t, tip, check=False).returncode != 0] + [tip]

    def _store_lock(self, store: Path, wait: float = 20.0):
        """The kit's own lock (flock on .memwrite.lock), so nothing is merged while the kit is mid-write."""
        class Lock:
            def __enter__(self_):
                path = store / ".memwrite.lock"
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)
                self_.handle = os.fdopen(fd, "a")
                deadline = time.monotonic() + wait
                while True:
                    try:
                        fcntl.flock(self_.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return self_
                    except BlockingIOError:
                        if time.monotonic() > deadline:
                            self_.handle.close()
                            raise Deferred()
                        time.sleep(0.2)

            def __exit__(self_, *exc):
                self_.handle.close()
        return Lock()

    # merging
    def _merge_all(self, settings: dict):
        self._write(self.attributes, ATTRIBUTES)
        local = self.local_stores()
        names = local + [n for n in self.st.get("stores", {}) if n not in local and (self.stores / n / ".git").exists()]
        for name in names:
            if not self.allowed(name) or name in settings.get("off", []):
                continue
            try:
                self._merge(name)
            except Deferred:
                self._mark(name, "pending", "Waiting for the memory kit to finish writing.")
            except Refused as problem:
                self._mark(name, "error", str(problem))

    def _merge(self, name: str):
        """Every refs/sync/* the store doesn't have yet goes into its branch. Markdown is merged as a union, so no line
        is lost; INDEX.md is rebuilt by the kit afterwards; notify.sh and roots.txt stay this device's own. A file the
        person locked, or a conflict outside markdown, stops the merge and says so."""
        self.guard(name)
        store = self.stores / name
        if not (store / ".git").exists():
            return
        refs = self._git(store, "for-each-ref", "--format=%(refname)", "refs/sync/").stdout.decode().split()
        has_head = self._git(store, "rev-parse", "-q", "--verify", "HEAD", check=False).returncode == 0
        todo = [r for r in refs if not has_head or self._git(store, "merge-base", "--is-ancestor", r, "HEAD", check=False).returncode != 0]
        if not todo:
            if self.st.get("stores", {}).get(name, {}).get("state") in (None, "pending", "error", "conflict"):
                self._mark(name, "ok", None)
            return
        if has_head and kit.dreamer(store):
            raise Deferred()
        with self._store_lock(store):
            if has_head and self._git(store, "status", "--porcelain", "--untracked-files=no").stdout.strip():
                self._mark(name, "pending", "This store has changes that aren't committed, so incoming changes wait.")
                return
            before = self._git(store, "rev-parse", "HEAD").stdout.decode().strip() if has_head else None
            for ref in todo:
                if not has_head:
                    branch = self.st.get("stores", {}).get(name, {}).get("branch") or "main"
                    self._git(store, "checkout", "-q", "-B", branch, ref)
                    has_head = True
                    continue
                if self._git(store, "merge-base", "--is-ancestor", ref, "HEAD", check=False).returncode == 0:
                    continue
                touched = self._git(store, "diff", "--name-only", "HEAD..." + ref).stdout.decode().split()
                if ALERT in touched and self._blob(store, ref, ALERT) != self._blob(store, "HEAD", ALERT):
                    self._mark(name, "pending", f"{ALERT} is different on another device, and sync never takes a command another device wrote: make {store / ALERT} the same on both devices to go on.")
                    return
                held = [f for f in touched if f in LOCKED_FILES and locked(store / f)]
                if held:
                    self._mark(name, "pending", f"{held[0]} changed on another device and is locked here: lift its lock (chflags nouchg {store / held[0]}), press Sync now, then lock it again.")
                    return
                if self._git(store, "merge-base", "--is-ancestor", "HEAD", ref, check=False).returncode == 0:
                    self._git(store, "merge", "-q", "--ff-only", ref)
                else:
                    result = self._git(store, "merge", "-q", "--no-edit", "-m", "Merge memory from another device", ref, check=False)
                    if result.returncode != 0:
                        conflicted = self._git(store, "diff", "--name-only", "--diff-filter=U").stdout.decode().split()
                        self._git(store, "merge", "--abort", check=False)
                        self._mark(name, "conflict", f"{conflicted[0] if conflicted else 'A file'} changed on two devices in ways that can't be joined; merge it by hand in {store}.")
                        return
            detail = self._alert_off(store) if before is None else None
            kit.rebuild_index(store)
            if self._git(store, "status", "--porcelain", "--", "INDEX.md").stdout.strip():
                self._git(store, "add", "--", "INDEX.md")
                self._git(store, "commit", "-q", "-m", "Rebuild the index after a sync", "--", "INDEX.md")
        self._mark(name, "ok", detail)

    def _blob(self, store: Path, ref: str, path: str):
        found = self._git(store, "rev-parse", "-q", "--verify", f"{ref}:{path}", check=False)
        return found.stdout.decode().strip() if found.returncode == 0 else None

    def _alert_off(self, store: Path):
        """A store made here from a bundle keeps the notify.sh it came with only when that is the kit's own; any other
        is left in place but not executable (core.fileMode off, so git doesn't count that as a change)."""
        alert = store / ALERT
        if not alert.is_file() or alert.is_symlink():
            return None
        if alert.read_text(errors="replace") == (kit.notify_template() or "\0"):
            return None
        self._git(store, "config", "core.fileMode", "false")
        os.chmod(alert, 0o644)
        return f"{ALERT} came from another device and was left switched off: read {alert}, then chmod +x it if it is yours."

    # sending
    def _send(self, remote, keys: Keys, me: str, settings: dict):
        state = self.st
        for name in self.local_stores():
            if not self.allowed(name) or name in settings.get("off", []):
                continue
            self.guard(name)
            store = self.stores / name
            head = self._git(store, "rev-parse", "-q", "--verify", "HEAD", check=False).stdout.decode().strip()
            if not head:
                continue
            seen = state.get("stores", {}).get(name, {})
            tips = [t for t in seen.get("tips", []) if self._git(store, "cat-file", "-e", t + "^{commit}", check=False).returncode == 0]
            if any(self._git(store, "merge-base", "--is-ancestor", head, t, check=False).returncode == 0 for t in tips):
                continue  # its state is the merge's to say
            branch = self._git(store, "symbolic-ref", "-q", "--short", "HEAD", check=False).stdout.decode().strip() or "main"
            with tempfile.TemporaryDirectory(dir=self.state_dir) as folder:
                os.chmod(folder, 0o700)
                path = Path(folder) / "out.bundle"
                self._git(store, "bundle", "create", "-q", str(path), "HEAD", *(["--not", *tips] if tips else []))
                bundle = path.read_bytes()
            if len(bundle) > BUNDLE_CAP - 4096:
                self._mark(name, "error", f"{name} changed by more than sync sends at once (64 MB).")
                continue
            state = self.st
            seq = state.get("seq", 0) + 1
            header = {"v": VERSION, "epoch": keys.epoch, "store": name, "device": me, "seq": seq, "prev": state.get("hash", ""),
                      "at": self.now(), "branch": branch, "head": head, "full": not tips}
            plain = canonical(header) + b"\n" + bundle
            seal = hashlib.sha256(plain).hexdigest()
            remote.write(keys.name("bundle", me, str(seq)), keys.pack(keys.name("bundle", me, str(seq)), plain))
            head_name = keys.name("head", me)
            remote.write(head_name, keys.pack(head_name, canonical({"device": me, "epoch": keys.epoch, "seq": seq, "hash": seal, "at": self.now()})))

            def change(s):
                s.update(seq=seq, hash=seal)
                entry = self._store_state(s, name)
                self._add_tip(entry, store, head)
                entry["last_sent"] = iso(self.now())
            self._update(change)
            state = self.st

    # held bundles for a store turned back on
    def _release_held(self, settings: dict):
        held = self.state_dir / "held"
        if not held.is_dir():
            return
        for folder in sorted(held.iterdir()):
            if folder.name in settings.get("off", []) or not self.allowed(folder.name):
                continue
            pending = sorted(folder.iterdir())
            progress = True
            while pending and progress:
                progress = False
                for path in list(pending):
                    header_line, _, bundle = path.read_bytes().partition(b"\n")
                    header = json.loads(header_line)
                    try:
                        self._fetch(folder.name, header, bundle, header["device"])
                    except Deferred:
                        continue
                    except Rejected as problem:
                        self.problems.append(str(problem))
                    path.unlink()
                    pending.remove(path)
                    progress = True
            if not pending:
                folder.rmdir()

    # ── in the background ──
    def start(self):
        if self.thread:
            return
        self.thread = threading.Thread(target=self._loop, daemon=True, name="sync")
        self.thread.start()

    def _loop(self):
        while True:
            try:
                self.wake.wait(5 if self.pairing or self.settings.get("joining") else 30)
                asked = self.wake.is_set()
                self.wake.clear()
                settings = self.settings
                if settings.get("joining"):
                    self.sync()
                    continue
                if not settings.get("enabled"):
                    continue
                due = self.st.get("next_sync") or 0
                if asked or self.pairing or self.now() >= due or self._changed():
                    self.sync()
            except Exception as problem:  # the loop must outlive anything a remote or a store can do to one round
                print(f"error: sync loop: {type(problem).__name__}", flush=True)
                try:
                    self._update(lambda s: s.update(error="Sync stopped on an unexpected problem; it will try again."))
                except Exception:
                    pass
                time.sleep(5)

    def _changed(self) -> bool:
        state = self.st
        for name in self.local_stores():
            if not self.allowed(name) or name in self.settings.get("off", []):
                continue
            head = self._git(self.stores / name, "rev-parse", "-q", "--verify", "HEAD", check=False).stdout.decode().strip()
            if head and head not in state.get("stores", {}).get(name, {}).get("tips", []):
                return True
        return False


def kind_of(problem) -> str:
    """The machine word for a refusal, so a page never has to match the words of a sentence."""
    if isinstance(problem, Removed):
        return "removed"
    if isinstance(problem, Rejected):
        return "remote_refused"
    return getattr(problem, "more", {}).get("reason") or ("bad_input" if isinstance(problem, Malformed) else "refused")


def locked(path: Path) -> bool:
    try:
        return bool(getattr(os.lstat(path), "st_flags", 0) & stat.UF_IMMUTABLE)
    except FileNotFoundError:
        return False


def iso(when):
    if not isinstance(when, (int, float)) or isinstance(when, bool):
        return when if isinstance(when, str) else None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))
