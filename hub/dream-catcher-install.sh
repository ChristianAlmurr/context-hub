#!/bin/sh
# Gives the Dream Catcher a memory of its own: a folder its sessions run in, and a store for that folder, made by the
# kit's own installer like any project's. Its sessions are then archived and dreamed on like any other project's, so it
# learns across runs (what you overrode, and what kind of item that was), and its own dreams are among what it catches.
#   sh hub/dream-catcher-install.sh [folder]      default folder: ~/projects/dream-catcher
# The store is named dream-catcher unless DREAM_CATCHER_STORE says otherwise; then set "dream_catcher_store" to the same
# name in the hub's config.json. Safe to run again: an existing folder and store are kept.
set -eu
hub=$(cd "$(dirname "$0")" && pwd)
kit=${HUB_KIT:-}
if [ -z "$kit" ]; then
  if [ -f "$hub/../agent-memory-kit/install-store.sh" ]; then kit=$(cd "$hub/../agent-memory-kit" && pwd); else kit=$HOME/tools/agent-memory-kit; fi
fi
[ -f "$kit/install-store.sh" ] || { echo "No memory kit at $kit. Set HUB_KIT to the kit's folder." >&2; exit 1; }
name=${DREAM_CATCHER_STORE:-dream-catcher}
folder=${1:-$HOME/projects/dream-catcher}
mkdir -p "$folder"
folder=$(cd "$folder" && pwd)
if ! git -C "$folder" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$folder" init -q -b main
fi
if [ ! -e "$folder/README.md" ]; then
  cat >"$folder/README.md" <<'EOF'
# Dream Catcher

The folder Context Hub's Dream Catcher runs in. It holds nothing but this file and the memory kit's files: the Dream
Catcher reads every project's memory store and repositories, and writes its verdicts into the hub's state folder.
Its own memory is the store linked here as memory/.
EOF
  git -C "$folder" add README.md
  git -C "$folder" -c user.name="Context Hub" -c user.email="context-hub@localhost" commit -q -m "Dream Catcher's folder" || true
fi
sh "$kit/install-store.sh" "$name" "$folder"
cat <<EOF

The Dream Catcher's memory is $HOME/agent-memory/$name, and its sessions run in $folder.
Start Claude there once and accept the trust dialog (cd $folder && claude), so a run never stops on it.
EOF
