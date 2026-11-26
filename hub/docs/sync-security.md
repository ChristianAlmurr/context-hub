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
| Root signing key (ed25519) | setup; a new one at every removal | Only on the remote, age-encrypted to the recovery key. The keyring names its public half. |
| Data key K (32 random bytes, one per person, for all their stores) | setup; a new one at every removal | `<config>/sync/keys/data.key`. On the remote only wrapped: to each device, and to the recovery key. |
| Pairing code: 6 groups of 4 from 31 symbols (no 0 O 1 I L), about 119 bits | the device already in | The server's memory, for 10 minutes. |
| Recovery key: 8 groups of 4, about 158 bits | setup; a new one at every removal | Nowhere: it is shown once. |

`<config>` is the folder of the instance's `config.json` (`~/.config/agent-hub` for the installed hub). What sync has
accepted is in `<state>/sync/`: the last keyring it checked, the chains, the stores' states. A second instance has its
own config and state, so it never sees the installed hub's sync.

The **recovery key** is the person's. It opens the root signing key, and only the root key can take a device out or
make a new data key. No device ever stores the recovery key or the root key. They are opened for the length of one
action, then deleted. The root key sits in a 0600 file inside a 0700 folder under `<config>/sync/`, because
`ssh-keygen` signs from a file. Folders a crash left behind are swept when sync starts. So a device that is later
removed never held what removal needs.

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

    {format, v, epoch, rev, prev, root, handover, kid,
     members: [{id, recipient, signer, added_by, name_hash}], wraps: {id: age(K)},
     recovery: {wrap: age(K), root: age(root private key)}, body: age(device names...), signer, sig}

- `rev` goes up by one at every change.
- `prev` is the SHA-256 of the keyring before.
- `kid` is `HMAC(K, "id")`, so a device can check that the key it unwrapped is the keyring's.
- `signer` is a member's device id, or `"root"`.
- `sig` is that key's ed25519 signature over everything but `sig` and `handover`.
- `handover`, only on a rotation, is the old root's signature over the same bytes.
- A member entry is covered by the signatures and never changed by a later step. Besides the device's keys it holds
  `added_by` and `name_hash`. `added_by` is `"setup"` or `"recovery"` for a device the root key added, and otherwise
  the id of the member that signed its addition. `name_hash` is a hash of the device's name. The page shows a name only
  if it matches that hash, and shows who added a device only from `added_by`, never from the encrypted body, which any
  member can rewrite.
- The shape is checked strictly before anything in it is used: every type, regex, member id, recipient and signer key.

Each step from one keyring to the next is checked against the one before (`check_step`):

- **Signed by a member device:** same epoch, data key, root and recovery wraps. Every existing entry and wrap is
  unchanged. It may only add devices, each with `added_by` set to its own id. Or it may take itself out, but only while
  no device it added is still a member: otherwise a member could add a device and then leave, so the device it vouched
  for stays without anyone left to answer for it.
- **Every step:** no two members may carry the same name hash, so a planted device can't pass for one of yours by name.
  The hash is of the name after NFKC and case folding. A name is refused outright when it holds invisible, format or
  control characters, a space at either end, letters from more than one of Latin, Cyrillic and Greek, or "This Mac".
- **Signed by the root key, same epoch:** same data key and root. It may only add devices with `added_by` `"setup"`
  or `"recovery"`.
- **A rotation:** the next epoch, a new data key, a new root key and no device added. The new root signs it, and the
  old root signs the handover.

A device keeps the last keyring it accepted (the pin). On each sync it reads the newest keyring and walks back through
`k/` until it reaches its pin, or a root-signed keyring that its trusted root signed or handed over to. Then it checks
every step forward. The walk is never longer than the gap between the pin and the newest keyring, nor than 2,000
steps. A device with no pin yet (joining, recovering) walks back the same way. It trusts the root key it was given
(joining) or opened (recovering), and nothing else.

Only after that does it decrypt its own wrap and check `kid`. It concludes "this device was removed" only from a
keyring that passed all of this.

- **Older than the pin:** a rollback. It is refused, and the device puts its pin back on the remote.
- **A different keyring at the pin's own step**, with the same parent and a step from it that checks out: a **fork**.
  A second rotation can be signed by anyone who held a recovery key of that time. A second member-made step can be
  signed by any device that was in sync then. The device takes neither, sends nothing, never writes over it, and says
  `error_kind: fork`. Anything else at that step that doesn't check out is junk and is put back.
- **Junk, missing, too big, or a step that breaks a rule:** refused, and the device puts its pin back.
- **A newer epoch it can't check** (a step is missing from `k/`): it receives under the old key and sends nothing.
  `error_kind` is `paused`, so the page can say "Sync is paused: the remote has a keyring this Mac can't check". A
  keyless attacker can cause this pause by planting such a keyring, but it holds sending back and leaks nothing.

The walk back checks each link as it reads it, and reads at most 16 MB of keyrings in all.

Each step can be written only over the keyring it was made from, which is a compare-and-swap:

1. The writer reads `keyring.json` and compares its hash with its base.
2. It creates `k/<rev>.json` exclusively (`O_EXCL`). If that name is already taken by a valid successor, it lost a race
   and is told to try again. Anything else in that place is junk, and it writes over it.
3. On GitHub, a push that conflicts is rebased. If the rebase fails, the change is undone and retried on the next sync.

### Beacons: freshness a removed device can't fake

Each device writes a beacon, `o/sha256("beacon", id)`. It names the newest keyring it has accepted, by its step
(epoch, rev) and its **digest**, and the time, all signed with the device's own ed25519 key. It is not encrypted and
holds nothing else. A device refreshes its own beacon at least once a day.

**Before taking any keyring other than its pin**, a device reads the beacons of every device in its pin and in the new
keyring. If one signed for a *different* keyring at the same step, and that keyring is on the remote and checks out
from the same parent, it is a proven fork: the device takes neither, sends nothing and doesn't write over it
(`error_kind: fork`). A beacon that merely names another digest proves nothing, since a removed device can sign
anything for itself. It shows as a plain note ("a removed device, or the remote, may be holding something back"), and
the person's answer below is the gate.

**On every sync**, it also sends nothing (`paused`) when one of these holds:

- a member's beacon names a newer keyring than its own;
- a member names a different digest at its own step;
- a beacon goes back to an older one than already seen;
- a beacon doesn't check out;
- a beacon disappears after it was seen.

When every other device's beacon is over a week old, it says so (`error_kind: stale`), without stopping. That is a
note, not an alarm: a Mac asleep for a week while another is in use doesn't cause it, since the one in use refreshes
its beacon daily.

A removed device can't sign for the others, so hiding a rotation by putting back the keyring a device last accepted
shows in the others' beacons, and deleting them is itself the alarm. Rotation keeps every beacon, the removed
devices' too. Beacons are a signal, not the authority. **Whoever holds the recovery key of an epoch is the authority
for it**, and a removed device may have seen that key: the setup device showed it, or it was typed there. Such a
device can make a second rotation that matches every beacon check, choosing the member list to suit itself. Only the
person can tell "A removed C" from "C removed A". So:

### New keys made on another device: the person decides

When a device takes a rotation it didn't make (a removal or new keys), it **takes the key but merges and sends
nothing** until the person answers on that device (`pending_rotation` in `GET /api/sync`, `error_kind:
pending_rotation`).

**What the question says comes from the signed lists only.** `removed` is whoever the root key took out, read from
the signed member lists of each rotation step since the last keys this device confirmed. `keeps` is every device in
the new signed list, by the names their signed entries vouch for. A forgery therefore can't hide who it keeps: a
removed device that made keys for itself shows under "keeps syncing". `by`, who made the keys, comes from the
encrypted body, which whoever made the keys writes, so it is only a claim. The body must agree with the signed lists:
if it says a device was removed that the signed list still holds, misses one the root key took out, names a maker who
isn't in the new list, or gives different makers, the keys are refused as forged (`fork`) and never asked about. A
hint, `others_agree`, says whether every other remaining device has signed for the same keys. When it is false, the
page shows that as a warning, not small print.

- **Yes** (`POST /api/sync/rotation/ack {"id"}`): it merges what arrived and starts sending.
- **No** (`POST /api/sync/rotation/reject {"id"}`): it goes back to the key, keyring, sync state and fetched refs it
  had before. It refuses that branch from then on (`error_kind: fork`, whatever builds on it) and sends nothing.

What arrives while it waits is fetched into side refs but not merged, so nothing planted under a forged key reaches
memory before the person answers. A bundle for a store that is off is held tagged with the keys it came under. It is
not released while those keys wait for an answer, is thrown away on a No, and goes in after a Yes once the store is
on. If this device makes a removal or new keys itself while a question waits, the question goes: its own keys
supersede it. An answer is bound to the keys it was asked about (`id` is their digest), so a later
different rotation asks again. The device that made the rotation isn't asked, and neither is one that joins or
recovers. **This is the control for a recovery key that leaked to a device later removed.** The others don't need to
fail for it to work: the person's No is enough. Behind Tailscale Serve (the `login` mode), another account on this Mac
can reach the hub on loopback and could answer the question in your place. That is the hub-wide gap described under
"Who can call the sync routes", and the Unix-socket change there closes it. In the default key mode it can't.

To settle a No: take every other device's access to the remote away, then make new keys with the newest recovery key,
or turn sync off on this Mac and join again. Making new keys on a Mac that is itself on keys someone else made fails
with `reason: wrong_branch`, because the newest recovery key doesn't open what it holds. Turn sync off there and join
again.

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

**What a bundle may hold.** After fetching into a side ref, every new commit's tree is checked. Each of these refuses
the bundle:

- a file of any mode but `100644`: no links, no submodules, no executables. The one exception is the store's
  `notify.sh`, spelled exactly so, which may be `100755`.
- `.git`, `.gitattributes` or `.gitmodules` in any spelling a Mac or Windows takes for them: any case, HFS-ignorable
  code points, NTFS trailing dots and spaces, and 8.3 short names, as git's own `is_hfs_dotgit` and `is_ntfs_dotgit`
  check;
- a second spelling of `notify.sh`, such as `Notify.sh`;
- two paths that are one file on a case-insensitive disk.

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
4. **The person confirms on the device already in**, sending back the six digits they saw
   (`POST /api/sync/pair/confirm {"check"}`). Digits that differ from the waiting device's are refused. Only then does
   the device already in add the new device to the keyring, signed with its own device key with `added_by` its own
   id, and wrap K to the new device's recipient. It then writes a reply, MACed with the code, that names the root
   public key, and the rev and hash of that keyring.
5. The new device checks the reply. The keyring the reply names must be on the remote, with that hash, listing this
   device, and its history must check out under the root key from the reply. The newest keyring is then accepted only
   through it, never anything older. If the keyring that added it is missing, the new device takes nothing and says to
   make a new code. Only after all of this does it decrypt its wrap and check `kid`.

A wrong code finds no request: the device already in never sees one made with another code. Neither side holds the key
before the confirm. A request or reply left in GitHub's history holds only public keys. Ten minutes later, or when the
code is cancelled, the device already in deletes both files.

## Recovery

Recovery is for when every device is lost. The newest recovery key decrypts the root key and K from the newest
keyring's `recovery`. That root key must be the keyring's `root`, and the history is checked back only under it. The
new device then adds itself with a root-signed step (`added_by: "recovery"`).

An old keyring put back by a removed device was wrapped to an *earlier* recovery key, so the newest one doesn't open
it. The recovery is refused.

## Removing a device

Removing a device needs the **recovery key**. It rotates everything the removed device knew or could sign with:

- a **new data key**, wrapped only to the devices that stay;
- a **new root key**, which signs the new keyring, while the old root signs the handover;
- a **new recovery key**, shown once like at setup. The old recovery key and every keyring under the old root stop
  being valid.

**Every device the removed one added goes too**, and every device those added, and so on, because a device it vouched
for is its own. A preview without the recovery key (`{"id", "preview": true}`) lists them, and the answer does too
(`also_removed`, with who added each). A device that was itself added by the one being removed can't do the removal;
another device must.

Every bundle and head under `o/` is then deleted, and so is every file under `p/`. Each device then sends its stores
again, encrypted under the new key. **Kept:** every beacon, and the whole keyring history in `k/`, which holds only
public keys and wraps. So a device away for several removals walks every handover and catches up.

**Settling a fork: new keys without removing anyone** (`POST /api/sync/rotate {recovery_key}`). It works like a
removal that takes no one: a new data key, a new root, a new recovery key, written over the fork. Do it only after
every removed device has lost its write access to the remote.

A removed device still holds the old K, its own signing key and the others' public keys. With those it can still:

- sign a keyring as a member, but no step a member signs may change the key, the root or another device's entry, so
  devices refuse it;
- put back an older keyring. That is a rollback for devices that saw the removal. A device that didn't is warned by
  the others' beacons and sends nothing;
- if it ever saw an **old recovery key** (the setup device showed one, for example), open that old root and sign a
  second rotation at the real one's step, with whatever member list it likes. A device that hasn't caught up takes its
  key but asks the person first, and merges and sends nothing until they answer. The person's No refuses that branch.

**The removed device keeps what it already had**: the stores on its disk, the old key, and so every file of earlier
epochs. On GitHub those stay in the repo's history. It can't read anything sent after the rotation.

**Take its access to the remote away too.** The removal answer (`advice`) says so. For GitHub: on that device run
`gh auth logout`, or revoke GitHub CLI under GitHub Settings, Applications. For a folder: sign it out of that iCloud
account, or keep the drive from it. Until then it can keep writing to the remote: it can't make another device accept
anything, but it can delete files and pause sync.

## What this does not protect against

- **A compromised device.** Malware on one of your devices can read its stores and keys, and can plant memory, as
  Markdown, that the other devices accept as yours. It can also add a device of its own while it is still a member.
  The device list shows who added each device: remove any you don't recognise. Sync guards the path between your
  devices, not the devices themselves.
- **A laggard that is shown a whole old snapshot.** A device that hasn't synced since a removal keeps the old key
  until it sees the new keyring. If the removed device can still write to the remote, it can replay a complete
  snapshot of the remote as it was before the removal (keyring, beacons, heads) just before the laggard reads it. The
  laggard then sees a consistent, genuine old world and **sends under the old key**, which the removed device can read.
  This holds even while the other devices are online, if the removed device wins the timing. It can't be told from a
  real quiet week. The partial guard is the `stale` note, once every beacon in that snapshot is over a week old. It
  also works when the laggard never read any beacon from a device that took the rotation. It ends once the removed
  device loses write access, so take it away at once.
- **A device that leaves still has the key.** Turning sync off on a device (without the recovery key) takes it out of
  the keyring but doesn't change the data key: it can still read whatever is sent until the next removal or new keys.
  Turning off is refused while the device has added devices that are still in sync. A device that is simply handed
  the key by a compromised member is the compromised-device case above. If you don't trust a device that left, make
  new keys.
- **An old recovery key used by mistake.** If the removed device puts the old history back on the remote and you then
  recover with an *old* recovery key, the recovery takes that old history, with its old key and the removed device as
  a member. Keep only the newest recovery key. After any recovery, check the device list before writing memory.
- **A recovery key seen by a device later removed.** That device can make keys every check accepts, so the person's
  answer on each other device is the last line. Answer the question only when you made that change yourself. Better
  still, never type or show a recovery key on a device you might remove.
- **Member-made steps.** Any device that is in sync can sign steps that add devices it vouches for: as many as the
  walk allows, so it can grow `k/` up to the walk's limits and slow every other device's check. That is member trust,
  as for the compromised device above. Remove it and every device it added goes too.
- **Metadata.** The remote sees when each device syncs, how big each file is, how many devices there are and how many
  bundles each has sent. It never sees store names, device names, file names or content.
- **Freeze and deletion.** A remote can withhold the newest files, or delete everything. Rollback below what a device
  has accepted is caught; what the remote never showed it isn't. After a deletion each device still has its own stores
  and puts its keyring back.
- **Losing every device and the recovery key.** Nothing can be read any more. Set up a new sync to start again.
- **Losing the recovery key alone.** Sync goes on, but no device can be removed. Turn sync off on every device and set
  it up again to get a new one.
- **A keyless freeze.** Anyone who can write to the remote can pause sending on every device (`error_kind: paused`),
  while receiving goes on. It reads nothing and plants nothing. Ways to do it:
  - plant a keyring of a newer epoch that can't be checked;
  - delete a beacon that was seen before, including an offline device's, which pauses every other device until that
    device syncs again and writes it back;
  - for a device that is catching up on a rotation, delete the beacon of any device it has seen.

  If the pause lasts after every removed device lost its access, turn sync off on the paused Mac and join again.
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
  - a new device gets the key only after Confirm with the six digits it shows, and its request has to be written to the
    remote first, which another account normally can't (your iCloud folder, your GitHub repo).
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
| A removed device forges an epoch+1 rotation endorsed with the old key; a laggard follows it | only the root key (opened by the recovery key) may rotate, and a rotation brings a new root; refused; the laggard sends nothing while it can't check a newer epoch |
| A removed device keeps restoring the old keyring | rollback, refused; the devices that know better put the newer one back |
| A member signs another device out | refused: members may only add devices, or take themselves out |
| Keyless junk keyring (`[]`, list wraps, non-ASCII MAC) killed the sync thread | strict shape check; `sync()` and the loop catch everything; the thread lives |
| An epoch+1 keyring with no wraps marked the device removed before any check | "removed" comes only from a checked keyring |
| The pairing envelope held K encrypted to the code, kept in GitHub's history; expiry and single use bound only honest joiners; it outlived a restart | no envelope; request and reply hold only public keys; the key moves only after Confirm with the right digits; leftovers cleaned after a restart |
| A second instance could forget or re-key a live remote | refused unless that instance set the remote up; it also looks for its own GitHub repo, `context-hub-sync-test`, and never joins a remote the installed hub set up |
| Bundles carrying links, `.gitattributes`, executables | refused before merging; no ref is left |
| A device id like `/../..` built a path outside the state folder | ids must be 16 hex digits, checked before any path is made |
| `STORE_NAME.match` accepted a trailing newline | `fullmatch` everywhere |
| A wrap decrypted before its keyring was checked | decrypted only after the whole chain checks out, then `kid` is compared |
| A join racing a removal could overwrite the rotated keyring | compare-and-swap; the loser is refused with `reason: retry` |
| A deleted head was passed over | reported |
| *Second review (2bef371):* a member adds its own device, named like yours and labelled "added by setup"; it survives the removal of its adder | `added_by` and `name_hash` sit in the signed member entry, and a member can only vouch for itself; removal takes every device the removed one added, transitively, and lists them |
| The root and recovery keys never rotated, so old root-signed keyrings could be replayed to a device that recovers | every removal rotates the root key and the recovery key (new one shown once); recovery trusts only the root the newest recovery key opens; an old recovery key used by mistake is the residual above |
| A joining device accepted a member-signed fork when the keyring that added it was missing | that keyring must exist with the confirmed hash, list the device, check out under the root, and the newest is accepted only through it |
| A laggard sent under the old key when the removed device put back the keyring it last accepted | signed beacons: a newer, older, invalid or vanished beacon pauses sending; residual stated above |
| `.GitAttributes` and other spellings passed the bundle check | case, HFS and NTFS spellings and 8.3 names refused, as git checks them; second spellings of `notify.sh` and paths that are one file on a Mac refused |
| Confirm didn't say which device | `pair/confirm` takes the six digits, compared with the waiting device's |
| Keyless freeze through an unverifiable newer keyring | documented; shown as `error_kind: paused` |
| The keyring history walk wasn't capped | capped at the gap to the pin, and 2,000 steps |
| Root-key folders in `$TMPDIR` could outlive a crash | made under `<config>/sync/` (0700) and swept at start |
| A second instance could join or confirm on a live remote | it joins, recovers into or confirms only on a remote a second instance set up |
| *Third review (af24460):* a removed device that saw an old recovery key signs a second handover at the real rotation's step; beacons held only the step, so a laggard took it | beacons carry the digest; a proven fork is taken by no device and written over by none (`error_kind: fork`); `POST /api/sync/rotate` settles it with the newest recovery key; since the fourth review, the person's Yes is the gate |
| A full old snapshot replayed (beacons too) makes a laggard send under the old key | not closable; `stale` note when every beacon is over a week old; residual stated above |
| A member adds a device and then turns itself off, so the device it vouched for stays unaccounted for | refused, in `check_step` and by `off` (`reason: has_added_devices`); devices it added must go first |
| k/ was wiped at each rotation, so a device away for two removals stayed paused | k/ is kept; the walk follows every handover, still capped |
| Two members could share a name | refused in `check_step`, and at confirm and recovery (`reason: name_taken`); removal can be previewed without the key |
| Deleting an offline device's beacon pauses the others | documented as a freeze |
| *Fourth review (d618d50):* a removed device that saw an old recovery key forges the rotation, chooses the member list and replays the remover's old beacon; no beacon check can tell | the person decides: a rotation made elsewhere is taken but nothing is merged or sent until **Yes** on that device; **No** puts back the earlier keys, keyring, state and refs and refuses the branch (`fork`) |
| A removed device's beacon with a bogus digest at the real step froze every laggard as a fork, which new keys didn't clear | a fork needs the other keyring present and valid from the same parent; otherwise it is a note, and the person decides |
| The history walk read up to 2,000 keyrings of 1 MB each | links checked as read, 16 MB in all |
| Lookalike names (Latin mixed with Cyrillic or Greek; case and width) | NFKC and case folded in the name hash; mixed alphabets refused (`name_lookalike`) |
| Making new keys on a Mac on a forged branch failed with a misleading error | `reason: wrong_branch` with what to do |
| A member could flood `k/` with valid steps | member trust; documented |
| *Fifth review (f77bfec):* the question's "who" and "removed" came from the body the forger writes, so a forgery read like the real removal | `removed` and `keeps` come from the signed lists; a body that disagrees with them is refused as forged and never asked about; `others_agree` false is a warning |
| A bundle held for a store that was off, while the question waited, survived a No and was merged later | held bundles are tagged with their keys: not released while those wait, thrown away on No, released after Yes |
| A stale question outlived this device's own removal or new keys | cleared when this device makes keys itself |
| In Tailscale mode another local account could answer the question | documented; the Unix-socket change closes it |
| *Sixth review (a04e1a1):* names with invisible or format characters (U+200B, U+2060), a space at either end, or the page's own "This Mac" passed for another device | refused at setup, join and recovery, in pairing requests, and shown as "a name that doesn't check out" if one ever reaches a keyring (`name_lookalike`); the page marks this device by id, not by name |
