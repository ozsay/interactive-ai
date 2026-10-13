#!/usr/bin/env bash
# Usage: prepare.sh <pr-number|pr-url> [--repo owner/repo]
# Creates a run dir with the PR's metadata, diff, hunk index, discussion, and a read-only
# checkout of the PR head at <rundir>/src. Prints the run dir on the last line.
set -euo pipefail

ref="${1:?usage: prepare.sh <pr-number|pr-url> [--repo owner/repo]}"
shift
repo=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    *) echo "pr-tour: unknown argument $1" >&2; exit 2 ;;
  esac
done

here="$(cd "$(dirname "$0")" && pwd)"
for c in gh git jq python3; do
  command -v "$c" >/dev/null || { echo "pr-tour: missing dependency: $c" >&2; exit 1; }
done

if [[ "$ref" =~ github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
  repo="${BASH_REMATCH[1]}"; num="${BASH_REMATCH[2]}"
else
  num="${ref#\#}"
fi
[ -n "$repo" ] || repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

home="${PR_TOUR_HOME:-$HOME/.cache/pr-tour}"
meta_tmp="$(mktemp)"
gh pr view "$num" --repo "$repo" --json \
  number,title,body,url,author,state,isDraft,baseRefName,headRefName,baseRefOid,headRefOid,additions,deletions,changedFiles,labels,commits \
  > "$meta_tmp"
head_sha="$(jq -r .headRefOid "$meta_tmp")"
base_ref="$(jq -r .baseRefName "$meta_tmp")"

run="$home/runs/${repo//\//-}-$num-${head_sha:0:7}"
mkdir -p "$run"
mv "$meta_tmp" "$run/pr.json"

gh pr diff "$num" --repo "$repo" > "$run/diff.patch"
gh api "repos/$repo/pulls/$num/comments" --paginate | jq -s 'add // []' > "$run/review-comments.json"
gh api "repos/$repo/issues/$num/comments" --paginate | jq -s 'add // []' > "$run/issue-comments.json"
gh api "repos/$repo/pulls/$num/reviews" --paginate | jq -s 'add // []' > "$run/reviews.json"

# Reuse the current checkout when it is this repo; otherwise keep a partial clone in the cache.
gitdir=""
if git rev-parse --git-dir >/dev/null 2>&1 && git remote -v | grep -qiE "github\.com[:/]${repo}(\.git)?[[:space:]]"; then
  gitdir="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
  remote="$(git remote -v | grep -iE "github\.com[:/]${repo}(\.git)?[[:space:]]" | head -1 | cut -f1)"
else
  clone="$home/repos/$repo"
  if [ ! -d "$clone" ]; then
    mkdir -p "$(dirname "$clone")"
    gh repo clone "$repo" "$clone" -- --filter=blob:none --no-checkout -q
  fi
  gitdir="$clone/.git"
  remote=origin
fi
g() { git --git-dir="$gitdir" "$@"; }
g fetch -q "$remote" "+refs/pull/$num/head:refs/pr-tour/$num"
# A stacked PR's base branch is often deleted once the PR below merges; fall back to the recorded base commit.
g fetch -q "$remote" "+refs/heads/$base_ref:refs/pr-tour/base-$num" 2>/dev/null \
  || { g fetch -q "$remote" "$(jq -r .baseRefOid "$run/pr.json")" && g update-ref "refs/pr-tour/base-$num" FETCH_HEAD; }
merge_base="$(g merge-base "refs/pr-tour/base-$num" "$head_sha")"
if [ ! -d "$run/src" ]; then
  g worktree add -q --detach "$run/src" "$head_sha"
fi

python3 "$here/hunks.py" "$run/diff.patch" "$run/hunks.json" > "$run/hunks.txt"
python3 "$here/stack.py" "$repo" "$num" "$run" | tee "$run/stack.txt"

jq -n --arg repo "$repo" --argjson number "$num" --arg head "$head_sha" --arg mb "$merge_base" \
  --arg src "$run/src" --arg gitdir "$gitdir" --arg run "$run" \
  '{repo:$repo, number:$number, headSha:$head, mergeBase:$mb, src:$src, gitdir:$gitdir, run:$run}' > "$run/meta.json"

files="$(jq '.files | length' "$run/hunks.json")"
hunks="$(jq '[.files[].hunks[]] | length' "$run/hunks.json")"
echo "pr-tour: $repo#$num  $(jq -r .title "$run/pr.json")"
echo "pr-tour: $files files, $hunks hunks, +$(jq .additions "$run/pr.json") -$(jq .deletions "$run/pr.json")"
[ -f "$run/tour.json" ] && echo "pr-tour: a tour.json already exists for this head commit"
echo "$run"
