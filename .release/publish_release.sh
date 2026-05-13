#!/bin/bash
set -euo pipefail

PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PATH
export HOME="${HOME:-/home/ttdinh}"

APP="photo_sonification"
APP_NAME="Photo Sonification"
REPO="trungtin-dinh/photo_sonification"
REPO_DIR="/home/ttdinh/Desktop/Portfolio/photo_sonification"
TAG="v1.0.0"
TITLE="v1.0.0 - Stable Streamlit release"
NOTES_FILE="$REPO_DIR/RELEASE_README.md"
GITHUB_URL="git@github.com:$REPO.git"

log() {
  printf '%s\n' "$1"
}

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

run_git_github() {
  local token
  token="$(gh auth token)"
  git -c "http.https://github.com/.extraheader=AUTHORIZATION: bearer $token" "$@"
}

ensure_git_identity() {
  local current_name current_email login user_id

  current_name="$(git config user.name || true)"
  current_email="$(git config user.email || true)"

  login="$(gh api user --jq '.login' 2>/dev/null || echo 'trungtin-dinh')"
  user_id="$(gh api user --jq '.id' 2>/dev/null || echo '')"

  if [ -z "$current_name" ]; then
    git config user.name "$login"
  fi

  if [ -z "$current_email" ]; then
    if [ -n "$user_id" ]; then
      git config user.email "${user_id}+${login}@users.noreply.github.com"
    else
      git config user.email "${login}@users.noreply.github.com"
    fi
  fi
}

get_default_branch() {
  gh repo view "$REPO" --json defaultBranchRef --jq '.defaultBranchRef.name'
}

commit_release_metadata() {
  local message
  message="Prepare $TAG release"

  git add -f "RELEASE_README.md" ".release/publish_release.sh"

  if git diff --cached --quiet; then
    log "No release metadata changes to commit. Creating an empty release preparation commit so GitHub can count a real contribution."
    git commit --allow-empty -m "$message"
  else
    git commit -m "$message"
  fi
}

ensure_tag_points_to_head_or_existing_remote() {
  local head_commit tag_commit

  if run_git_github ls-remote --exit-code --tags "$GITHUB_URL" "refs/tags/$TAG" >/dev/null 2>&1; then
    log "GitHub tag $TAG already exists. It will be used for the release."
    return 0
  fi

  head_commit="$(git rev-parse HEAD)"

  if git rev-parse "$TAG" >/dev/null 2>&1; then
    tag_commit="$(git rev-list -n 1 "$TAG")"
    if [ "$tag_commit" != "$head_commit" ]; then
      log "Local tag $TAG exists but does not point to HEAD. Recreating local tag before pushing to GitHub."
      git tag -d "$TAG"
      git tag -a "$TAG" -m "$TITLE"
    else
      log "Local tag $TAG already points to HEAD."
    fi
  else
    git tag -a "$TAG" -m "$TITLE"
    log "Created local tag $TAG."
  fi

  run_git_github push "$GITHUB_URL" "$TAG"
  log "Pushed tag $TAG to GitHub."
}

publish_release() {
  gh release create "$TAG" "$NOTES_FILE"     --repo "$REPO"     --title "$TITLE"     --notes-file "$NOTES_FILE"
}

main() {
  cd "$REPO_DIR"

  echo "============================================================"
  echo "Publishing release for $APP_NAME"
  echo "Repository: $REPO"
  echo "Tag: $TAG"
  echo "Date: $(date)"
  echo "============================================================"

  require_command git
  require_command gh

  gh auth status >/dev/null 2>&1 || fail "GitHub CLI is not authenticated. Run: gh auth login"
  [ -f "$NOTES_FILE" ] || fail "Missing release notes file: $NOTES_FILE"

  if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    log "Release $TAG already exists for $REPO. Nothing to do."
    exit 0
  fi

  ensure_git_identity

  DEFAULT_BRANCH="$(get_default_branch)"
  log "GitHub default branch: $DEFAULT_BRANCH"

  run_git_github fetch "$GITHUB_URL" "$DEFAULT_BRANCH" >/dev/null 2>&1 || true

  commit_release_metadata

  run_git_github push "$GITHUB_URL" "HEAD:refs/heads/$DEFAULT_BRANCH"
  log "Pushed release preparation commit to GitHub branch $DEFAULT_BRANCH."

  ensure_tag_points_to_head_or_existing_remote

  publish_release

  echo "Release $TAG published successfully for $REPO."
}

main "$@"
