# Encrypted sync: design and threat model

Sync copies memory stores between one person's devices through a place none of them trusts: a folder (iCloud Drive,
a USB drive, a share) or a private GitHub repo. The goal: **only that person's own devices can read the memory, and
only they can put memory into it.** The remote is treated as hostile, and so is whoever runs it or breaks into it. So is
a device after it has been removed.

The code is `hub/hub_sync.py`. The offline tests are in `hub/tests/sync_check.py`, and every attack listed under
"Reviewed attacks" below is one of their cases.

## Building blocks

- **Confidentiality comes from `age`** (1.3.2, `brew install age`): X25519 recipients, ChaCha20-Poly1305. The hub has
  no cipher of its own, and its Python is standard library only.
- **Who may change the keyring is decided by ed25519 signatures**, made and checked with the stock
  `/usr/bin/ssh-keygen -Y sign` / `-Y verify` (namespace `context-hub-sync`).
- **Bundles are authenticated with HMAC-SHA256** (`hmac`). Every MAC is compared as bytes with `hmac.compare_digest`.
- **Subkeys** are derived HKDF-Expand style, `HMAC(key, "context-hub-sync/v1/<label>" || 0x01)`, with one label per
  use (`mac`, `name`, `age`, `id`).
- **Codes people type** (pairing codes, the recovery key) are stretched with PBKDF2-HMAC-SHA256 at 600,000 rounds,
  salted with the remote's random id and the code's purpose. scrypt would be better, but `/usr/bin/python3` (3.9,
  LibreSSL) has no `hashlib.scrypt`. The codes carry enough entropy that the stretching is a second line of defence,
  not the first.
- **Age identities from bytes.** An age X25519 secret key is 32 bytes in bech32 with the prefix `AGE-SECRET-KEY-`, so
  the data key, a pairing code and the recovery key can each become an age identity. Its recipient comes from
  `age-keygen -y`. The bech32 here is only an encoding. An identity reaches `age -d` through a pipe (`-i /dev/fd/N`),
  so no key is written to disk to decrypt something.

## Keys

| Key | Made by | Where it lives |
|---|---|---|
| Device identity (age X25519) | each device, when it sets up, joins or recovers | `<config>/sync/keys/device.key` (folder 0700, files 0600). It never leaves the device. |
| Device signing key (ed25519) | each device, likewise | `<config>/sync/keys/sign.key`. It never leaves the device; its public half is in the keyring. |
| Root signing key (ed25519) | setup | Only on the remote, age-encrypted to the recovery key. The keyring names its public half. |
| Data key K (32 random bytes, one per person, for all their stores) | setup; a new one at every removal | `<config>/sync/keys/data.key`. On the remote only wrapped: to each device, and to the recovery key. |
| Pairing code: 6 groups of 4 from 31 symbols (no 0 O 1 I L), about 119 bits | the device already in | The server's memory, for 10 minutes. |
| Recovery key: 8 groups of 4, about 158 bits | setup | Nowhere: it is shown once. |

`<config>` is the folder of the instance's `config.json` (`~/.config/agent-hub` for the installed hub). What sync has
accepted is in `<state>/sync/`: the last keyring it checked, the chains, the stores' states. A second instance has its
own config and state, so it never sees the installed hub's sync.

The **recovery key** is the person's. It opens the root signing key, and only the root key can take a device out or
make a new data key. No device ever stores the recovery key or the root key: they are opened for the length of one
action, the root key in a 0600 file inside a 0700 temporary folder, because `ssh-keygen` signs from a file, and then
deleted. So a device that is later removed never held what removal needs.

## On the remote

    remote.json      plaintext {"format", "v", "id"}; the id is random and salts the codes
    keyring.json     the newest keyring
    k/<rev>.json     every keyring since the last rotation, so a device that was away can check each step
    p/<40 hex>       a pairing request or its reply, for 10 minutes at most; neither holds a key
    o/<40 hex>       bundles and per-device heads

**Hostile files.** Whoever else can write to the folder, or push to the repo, is an attacker. For that reason:

- the folders `o`, `p` and `k`, and the root itself, must be real folders (checked with `lstat`; a link is refused);
- files are opened with `O_NOFOLLOW | O_NONBLOCK` and must be plain files;
- every read has a cap: 64 KB for small files, 1 MB for a keyring, 64 MB for a bundle;
- listing uses `scandir` with `is_file(follow_symlinks=False)`;
- only names matching `remote.json`, `keyring.json`, `[op]/<40 hex>` or `k/<8 digits>.json` are ever read, written or
  deleted.

The GitHub clone runs with `core.symlinks=false`, so a link someone commits arrives as a small plain file, and then
`o` or `p` isn't a folder and is refused.

**File names are opaque.** They are `HMAC(K_name, epoch, kind, device, seq)`. No store name, device name or count of
stores is in a name. Device ids are 16 random hex digits.

### The keyring

    {format, v, epoch, rev, prev, root, kid, members: [{id, recipient, signer}], wraps: {id: age(K)},
     recovery: {wrap: age(K), root: age(root private key)}, body: age(device names...), signer, sig}

- `rev` goes up by one at every change.
- `prev` is the SHA-256 of the keyring before.
- `kid` is `HMAC(K, "id")`, so a device can check that the key it unwrapped is the keyring's.
- `signer` is a member's device id, or `"root"`.
- `sig` is that key's ed25519 signature over everything else.
- The shape is checked strictly before anything in it is used: every type, regex, member id, recipient and signer key.

Each step from one keyring to the next is checked against the one before (`check_step`):

- **Signed by the root key:** any change, in the same epoch or the next. Only the root key changes the data key, and
  it must do so when the epoch goes up.
- **Signed by a member device:** same epoch, same data key, same recovery wraps. Other members' keys and wraps
  unchanged. It may only add devices, or take out itself.

A device keeps the last keyring it accepted (the pin). On each sync it reads the newest keyring and walks back through
`k/` until it reaches its pin, or a root-signed keyring. Then it checks every step forward. A device with no pin yet
(joining, recovering) walks back to a root-signed keyring and checks it with the root key it was given (joining) or
opened (recovering).

Only after that does it decrypt its own wrap and check `kid`. It concludes "this device was removed" only from a
keyring that passed all of this.

- **Older than the pin:** a rollback. It is refused, and the device puts its pin back on the remote.
- **Junk, missing, too big, or a step that breaks a rule:** refused, and the device puts its pin back.
- **A newer epoch it can't check** (a step is missing from `k/`): it receives under the old key and sends nothing,
  until it can check the new one.

Each step can be written only over the keyring it was made from, which is a compare-and-swap:

1. The writer reads `keyring.json` and compares its hash with its base.
2. It creates `k/<rev>.json` exclusively (`O_EXCL`). If that name is already taken by a valid successor, it lost a race
   and is told to try again. Anything else in that place is junk, and it writes over it.
3. On GitHub, a push that conflicts is rebased. If the rebase fails, the change is undone and retried on the next sync.

### Bundles

A change to a store travels as a `git bundle`. A file holds `MAGIC || age(header JSON "\n" bundle) || HMAC(K_mac,
MAGIC, file name, ciphertext)`: encrypt-then-MAC over the whole file and its name. The header is inside: version,
epoch, store name, device id, sequence number (one chain per device, across all its stores), SHA-256 of that device's
previous bundle, time, branch, head commit.

Each device also has a head file, encrypted and MACed the same way, naming its newest sequence number and that bundle's
hash. A receiver reads the head first, then takes the bundles after the last one it accepted, in order:

1. The MAC is checked before anything is decrypted.
2. The header must name the expected device, sequence number and epoch.
3. `prev` must equal the hash of the bundle accepted before it.
4. A head older than one already accepted is a rollback, refused. So is the same number with another hash.
5. A bundle missing in the middle is a gap: it is named, and nothing after it is taken.
6. A head that disappears after its device has sent something is reported, not passed over.

A refusal holds back only that device's chain; the error is one sentence in `GET /api/sync`, with `error_kind`.

**What a bundle may hold.** After fetching into a side ref, every new commit's tree is checked. A file of any mode
but `100644` (no links, no submodules, no executables) is refused, and so is any `.gitattributes` or `.gitmodules`.
The one exception is the store's `notify.sh`, which may be `100755`.

Then the device-local files:

- **`notify.sh`.** The kit runs this command, so sync never takes it from another device. A merge that would change it
  waits, with a sentence. A store made from another device's bundle keeps its `notify.sh` switched on only when it is
  the kit's own template. Any other is left in place, not executable, under `core.fileMode=false`, with a note.
- **`roots.txt`.** This lists repo paths. It is merged as a union, and the hub uses only the paths that exist on this
  Mac.

## Pairing a device

The remote is the only meeting point, so this works between two devices on different networks. The data key is
**never** encrypted to the code.

1. The device already in makes a code and keeps it in memory. It writes nothing to the remote. It keeps the two file
   names on disk, never the code, so that a restart cleans them up.
2. The new device makes its two keys. It posts a request to `p/HMAC(name key, "request")`: its id, its age recipient,
   its signing key and its name. The request is age-encrypted to the code's identity and MACed with the code's MAC key.
3. The device already in finds the request and checks its MAC. Both screens then show six digits derived from the new
   device's two public keys (`pairing.state = "confirm"`).
4. **The person confirms on the device already in** (`POST /api/sync/pair/confirm`). Only then does it add the new
   device to the keyring, signed with its own device key, and wrap K to the new device's recipient. It then writes a
   reply, MACed with the code, that names the root public key and the hash of that keyring.
5. The new device checks the reply. It walks the keyring back to a root-signed one under that root key, checks that the
   keyring that added it is the one named, then decrypts its wrap and checks `kid`.

A wrong code finds no request: the device already in never sees one made with another code. Neither side holds the key
before the confirm. A request or reply left in GitHub's history holds only public keys. Ten minutes later, or when the
code is cancelled, the device already in deletes both files.

## Recovery

Recovery is for when every device is lost. The recovery key decrypts the root key and K from `keyring.recovery`. The
root key must match the keyring's `root`. The keyring's history is then checked back to a root-signed keyring, and the
new device adds itself with a root-signed step.

## Removing a device

Removing a device needs the **recovery key**. It opens the root key, which signs a keyring of the next epoch with a
new K, wrapped only to the devices that stay and to the recovery key. Every file under `o/`, `p/` and `k/` is then
deleted (the new keyring is signed by the root, so it needs no history), and each device sends its stores again,
encrypted under the new key. The recovery key stays the same, because the removed device never held it.

A removed device still holds the old K, its own signing key and the others' public keys. With those it can still:

- sign a keyring as a member, but no step a member signs may change the key or take another device out, so devices
  refuse it;
- put back an older keyring, which is a rollback: refused, and the devices that already saw the removal put the newer
  one back.

**The removed device keeps what it already had**: the stores on its disk, the old key, and so every file of earlier
epochs. On GitHub those stay in the repo's history. It can't read anything sent after the rotation.

**Take its access to the remote away too.** The removal answer (`advice`) says so. For GitHub: on that device run
`gh auth logout`, or revoke GitHub CLI under GitHub Settings, Applications. For a folder: sign it out of that iCloud
account, or keep the drive from it. Until then it can keep writing to the remote. It can't make another device accept
anything, but it can hold back the change from a device that hasn't synced since the removal (see below).

## What this does not protect against

- **A compromised device.** Malware on one of your devices can read its stores and keys, and can plant memory, as
  Markdown, that the other devices accept as yours. It can also add a device of its own while it is still a member.
  The device list shows who added each device: remove any you don't recognise. Sync guards the path between your
  devices, not the devices themselves.
- **A laggard held back by a removed device that still has write access.** A device that hasn't synced since a
  removal keeps the old key until it sees the new keyring. If the removed device can still write to the remote, it can
  keep putting back what it likes. The laggard refuses every forged step and sends nothing while a newer epoch is on the
  remote that it can't check, but it can be kept from learning of the rotation. That ends once the removed device loses
  write access, because the other devices put the real keyring back.
- **Metadata.** The remote sees when each device syncs, how big each file is, how many devices there are and how many
  bundles each has sent. It never sees store names, device names, file names or content.
- **Freeze and deletion.** A remote can withhold the newest files, or delete everything. Rollback below what a device
  has accepted is caught; what the remote never showed it isn't. After a deletion each device still has its own stores
  and puts its keyring back.
- **Losing every device and the recovery key.** Nothing can be read any more. Set up a new sync to start again.
- **Losing the recovery key alone.** Sync goes on, but no device can be removed. Turn sync off on every device and set
  it up again to get a new one.
- **Someone who sees a pairing code and can write to the remote.** They can post a request, but the six digits differ
  from the ones on your other screen, and nothing happens until someone presses Confirm.

## Who can call the sync routes on this Mac

The hub listens on 127.0.0.1. How far that is a boundary depends on how it is reached (README, Access):

- **This Mac only (`key`).** Every request needs the cookie that holds the key from `config.json` (mode 600). Another
  account on this Mac can't read it, so it can't call sync. A program running as you can, but it can read
  `<config>/sync/keys/` directly anyway: no route of the hub gives it more than your files already do.
- **Behind Tailscale Serve (`login`).** The hub trusts `Tailscale-User-Login`, `Host` and `Origin` on loopback, and
  any local process, of any account, can send them: the login and the address are easy to guess. **This is hub-wide,
  not only sync's problem: such a process can open a terminal as you.** For sync, what the design adds now:
  - removing a device and forgetting the remote need the recovery key, which no device holds;
  - a new device gets the key only after the person presses Confirm, and its request has to be written to the remote
    first, which another account normally can't (your iCloud folder, your GitHub repo).
  - What another account *can* do through the routes: turn sync off on this device (it deletes the local keys), start
    and cancel pairings, see a pairing code, and press Confirm itself for a request it managed to write to the remote.

  **It can't be closed without changing how Tailscale Serve reaches the hub.** The installed Tailscale (1.104.7,
  the standalone macOS app with its network extension) accepts a Unix socket as a target
  (`tailscale serve unix:/path`). The change, not applied to `install.sh` or the live hub:
  1. In `server.py`, when the config has `"login"`, listen with `asyncio.start_unix_server` on
     `~/.local/state/agent-hub/sock/hub.sock`. The folder is 0700 and the socket 0600. Don't open the TCP port at all
     in that mode, and keep the preview listener as it is.
  2. Serve it: `tailscale serve --bg --https=8443 unix:$HOME/.local/state/agent-hub/sock/hub.sock` (after
     `tailscale serve --https=8443 off` for the old target).
  3. First check that the network extension, which is sandboxed, may connect to a socket in the home folder. Try it on
     a spare port with a throwaway server (`--https=8460`), open it from another tailnet device, then
     `tailscale serve --https=8460 off`. If it can't, put the socket's folder where the extension can reach it, still
     0700 and owned by you.

  Only your own processes and root can then connect, so a request that arrives on the socket came through Tailscale or
  from you. That is the same boundary as the key mode.

## Reviewed attacks, each a case in `tests/sync_check.py`

| Attack (review of db0225a) | Now |
|---|---|
| `o/` or `p/` replaced by a link (folder), or committed as a link (GitHub): removal deleted the link's target, sync wrote into it | refused before any read, write or delete; target untouched |
| `keyring.json` a link to `/dev/zero`, or oversized | refused at once by `O_NOFOLLOW`, `O_NONBLOCK` and the size cap |
| A removed device forges an epoch+1 rotation endorsed with the old key; a laggard follows it | only the root key (opened by the recovery key) may rotate; refused; the laggard sends nothing while it can't check a newer epoch |
| A removed device keeps restoring the old keyring | rollback, refused; the devices that know better put the newer one back |
| A member signs another device out | refused: members may only add devices, or take themselves out |
| Keyless junk keyring (`[]`, list wraps, non-ASCII MAC) killed the sync thread | strict shape check; `sync()` and the loop catch everything; the thread lives |
| An epoch+1 keyring with no wraps marked the device removed before any check | "removed" comes only from a checked keyring |
| The pairing envelope held K encrypted to the code, kept in GitHub's history; expiry and single use bound only honest joiners; it outlived a restart | no envelope; request and reply hold only public keys; the key moves only after Confirm; leftovers cleaned after a restart |
| A second instance could forget or re-key a live remote | refused unless that instance set the remote up; it also looks for its own GitHub repo, `context-hub-sync-test` |
| Bundles carrying links, `.gitattributes`, executables | refused before merging; no ref is left |
| A device id like `/../..` built a path outside the state folder | ids must be 16 hex digits, checked before any path is made |
| `STORE_NAME.match` accepted a trailing newline | `fullmatch` everywhere |
| A wrap decrypted before its keyring was checked | decrypted only after the whole chain checks out, then `kid` is compared |
| A join racing a removal could overwrite the rotated keyring | compare-and-swap; the loser is refused with `reason: retry` |
| A deleted head was passed over | reported |
