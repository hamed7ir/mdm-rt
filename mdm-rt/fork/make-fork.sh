#!/bin/sh
# MDM RT: builds the fork branch in a clone of anefzaoui/misterdownloadmanager - upstream's commit the series was
# made on (<series>/base.txt; for 1.1 its main at 1f241ae4), one commit per patch of the series (with its message
# from series.txt), then the mdm-rt/ project folder and the README. The branch (BRANCH, default mdm-rt) must not
# exist yet. Run it in Git Bash inside the clone, for example:
#   cd /d/repo/mdm-rt && sh /f/mdm-rt/src/mdm-rt/fork/make-fork.sh /f/mdm-rt/series-1126 /f/mdm-rt/src/mdm-rt
# The commits get your own git name and e-mail. Nothing is pushed; push the branch yourself.
set -e
SERIES=${1:?series folder (the .patch files and series.txt)}
PROJECT=${2:?the mdm-rt project folder}
# upstream's commit the series was made on (split-series.py writes it), else BASE as given
BASE=${BASE:-$(cat "$SERIES/base.txt" 2>/dev/null)}
: "${BASE:?no BASE and no $SERIES/base.txt}"
BRANCH=${BRANCH:-mdm-rt}
TAB=$(printf '\t')

git rev-parse --verify -q "$BASE^{commit}" >/dev/null || { echo "no $BASE in this clone"; exit 1; }
if [ -n "$(git status --porcelain)" ]; then echo "the clone has changes; commit or stash them first"; exit 1; fi
git checkout -q -b "$BRANCH" "$BASE"

while IFS="$TAB" read -r patch subject body; do
  [ -n "$patch" ] || continue
  git -c core.autocrlf=false apply --index --whitespace=nowarn "$SERIES/$patch"
  if [ -z "$body" ] || [ "$body" = '""' ]; then
    git commit -q -m "$subject"
  else
    git commit -q -m "$subject" -m "$body"
  fi
  echo "$(git log -1 --format=%h) $subject"
done < "$SERIES/series.txt"

# the project folder (no Python caches), and the fork's README; upstream's stays beside it as README-MDM.md (the
# same folder, so its relative links still work)
mkdir -p mdm-rt
(cd "$PROJECT" && tar --exclude='__pycache__' --exclude='*.pyc' -cf - .) | (cd mdm-rt && tar -xf -)
git mv README.md README-MDM.md
cp mdm-rt/fork/README.md README.md
git add -A mdm-rt README.md README-MDM.md
git commit -q -m "mdm-rt: build scripts, patches, helpers, installer, device kits, branding and docs" \
  -m "the mdm-rt folder: build.py (cargo with llvm-rt's rustc for arm32 thumb-2, x64 and an x86 test build, thinlto and pgo; the arm32 release's profile is in pgo/), the patched dependencies for arm32, the helpers (yt-dlp with kodi rt's arm32 python, quickjs, ffmpeg), the installer, the device kits, the theme and icon scripts and the recipe. the readme says what mdm rt is; upstream's readme is README-MDM.md."
echo "$(git log -1 --format=%h) mdm-rt folder + README"
echo
echo "branch $BRANCH is ready. to publish it (you do this):"
echo "  git remote add fork https://github.com/hamed7ir/mdm-rt.git   # once"
echo "  git push fork $BRANCH"
