#!/bin/sh
# A daily check through launchd, at the hour you choose: run-dream.sh --if-due starts a /dream only when
# scripts/dream_due.py says enough has happened since the last one. A dream only proposes; each one costs money.
#   sh agent-memory-kit/schedule-dream.sh <repo> [--hour 18]   turn it on (once per store); without --hour,
#     the store keeps its hour, and a new one gets an hour no other store's dream or fixer has
#   sh agent-memory-kit/schedule-dream.sh <repo> --remove      turn it off
# Running it again replaces the job, also the weekly one an older kit set up. The new job is written
# and checked before the old one is taken out, so a mistake never leaves a store with no schedule.
# A store shared by several repos needs one schedule: the run covers every repo in roots.txt.
# With it comes the fixer's job, ai.agent-memory.fix.<store>, two hours before the dream's hour: run-fix.sh --if-approved
# does what the person approved under "Needs you", and nothing when nothing is. --remove removes both; both are
# written and checked before either old one is taken out.
set -eu
repo=$(cd "$1" && pwd); shift
hour=auto; remove=
while [ $# -gt 0 ]; do
  case $1 in
    --hour) [ $# -ge 2 ] || { echo "--hour needs a number from 0 to 23" >&2; exit 2; }; hour=$2; shift 2 ;;
    --remove) remove=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
store=$(basename "$(cd "$repo/memory" && pwd -P)")
# auto (the default): the store keeps the hour its dream job has; a store without one gets the first hour where
# neither its dream nor its fixer (two hours before) starts beside another store's dream or fixer. Evenings first.
if [ "$hour" = auto ] && [ -z "$remove" ]; then
  hour=$(/usr/bin/python3 - "$HOME/Library/LaunchAgents" "$store" <<'EOF_PY'
import glob, os, plistlib, sys
jobs, store = sys.argv[1], sys.argv[2]
def hour_of(path):
    try:
        with open(path, "rb") as f:
            h = plistlib.load(f)["StartCalendarInterval"]["Hour"]
        return h if isinstance(h, int) and 0 <= h <= 23 else None
    except Exception:
        return None
own = hour_of(os.path.join(jobs, f"ai.agent-memory.dream.{store}.plist"))
if own is not None:
    print(own); sys.exit()
busy = []
for kind in ("dream", "fix"):
    for path in glob.glob(os.path.join(jobs, f"ai.agent-memory.{kind}.*.plist")):
        if os.path.basename(path) != f"ai.agent-memory.{kind}.{store}.plist" and hour_of(path) is not None:
            busy.append(hour_of(path))
order = [18, 20, 22, 16, 14, 12, 10, 19, 21, 23, 17, 15, 13, 11] + [h for h in range(24) if not 10 <= h <= 23]
# the first free pair; when none is, the hour whose pair is least taken
print(min(order, key=lambda h: (busy.count(h) + busy.count((h + 22) % 24), order.index(h))))
EOF_PY
) || { echo "couldn't read the other stores' jobs to choose an hour; say one with --hour" >&2; exit 1; }
elif [ "$hour" = auto ]; then
  hour=0  # --remove has no hour
fi
case $hour in ''|*[!0-9]*|???*) echo "--hour is '$hour'; it has to be a whole number from 0 to 23" >&2; exit 2 ;; esac
hour=$(expr "$hour" + 0) || true  # 08 is 8; expr exits 1 when the answer is 0
[ "$hour" -le 23 ] || { echo "--hour is $hour; it has to be a whole number from 0 to 23" >&2; exit 2; }
label=ai.agent-memory.dream.$store
plist=$HOME/Library/LaunchAgents/$label.plist
fix_label=ai.agent-memory.fix.$store
fix_plist=$HOME/Library/LaunchAgents/$fix_label.plist
if [ -n "$remove" ]; then
  for one in "$label" "$fix_label"; do
    launchctl bootout "gui/$(id -u)/$one" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/$one.plist"
  done
  echo "removed $label and $fix_label"; exit 0
fi
fix_hour=$(( (hour + 22) % 24 ))
# launchd has almost no PATH, so find claude now and pass its folder on.
claude=$(command -v claude)
kit=$(cd "$(dirname "$0")" && pwd)
state=$HOME/.local/state/agent-memory
mkdir -p "$(dirname "$plist")" "$state"
# A path may hold & or <, which would end the value or break the file.
xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
# job <file> <label> <hour> <script> <option> <log>: one job's plist
job() {
cat >"$1" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$(xml "$2")</string>
  <key>WorkingDirectory</key><string>$(xml "$repo")</string>
  <key>ProgramArguments</key><array>
    <string>/bin/sh</string><string>$(xml "$kit/$4")</string><string>$(xml "$repo")</string><string>$5</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$(xml "$(dirname "$claude"):/usr/bin:/bin:/usr/sbin:/sbin")</string>
    <key>HOME</key><string>$(xml "$HOME")</string>
  </dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$3</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$(xml "$state/$6")</string>
  <key>StandardErrorPath</key><string>$(xml "$state/$6")</string>
</dict></plist>
EOF_PLIST
}
new=$(mktemp "$state/$store.plist.XXXXXX")
fix_new=$(mktemp "$state/$store.fix-plist.XXXXXX")
job "$new" "$label" "$hour" run-dream.sh --if-due "launchd-$store.log"
job "$fix_new" "$fix_label" "$fix_hour" run-fix.sh --if-approved "launchd-fix-$store.log"
for one in "$new" "$fix_new"; do
  if ! problem=$(plutil -lint "$one" 2>&1); then
    rm -f "$new" "$fix_new"
    echo "The new jobs for $store are not valid plists, so nothing was changed: $problem" >&2
    exit 1
  fi
done
chmod 644 "$new" "$fix_new"
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/$fix_label" 2>/dev/null || true
mv "$new" "$plist"
mv "$fix_new" "$fix_plist"
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl bootstrap "gui/$(id -u)" "$fix_plist"
echo "on: $label, checks every day at $hour:00 and dreams when one is due; the daily check logs to ~/.local/state/agent-memory/launchd-$store.log, a dream to ~/.local/state/agent-memory/dream-$store.log"
echo "on: $fix_label, every day at $fix_hour:00 does what you approved for the fixer, and nothing when nothing is; it logs to ~/.local/state/agent-memory/fix-$store.log"
