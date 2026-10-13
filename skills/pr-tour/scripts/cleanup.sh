#!/usr/bin/env bash
# Usage: cleanup.sh <rundir>   Removes the run's checkout (git worktree) and the run dir.
set -euo pipefail
run="${1:?usage: cleanup.sh <rundir>}"
gitdir="$(jq -r .gitdir "$run/meta.json")"
git --git-dir="$gitdir" worktree remove --force "$run/src" 2>/dev/null || true
git --git-dir="$gitdir" worktree prune
rm -rf "$run"
echo "pr-tour: removed $run"
