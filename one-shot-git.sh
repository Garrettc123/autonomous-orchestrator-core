#!/usr/bin/env bash
# one-shot-git.sh
#
# Safeguards:
#   - Shows current directory and asks you to confirm BEFORE any git/gh action.
#   - SIMULATE=1 for dry run (no changes).
#   - Strict Bash options for safety.

set -Eeuo pipefail

REPO_NAME="${1-}"
COMMIT_MSG="${2-}"
VISIBILITY="${3-}"         # private | public | internal
SIMULATE="${SIMULATE:-0}"

############################################
# Argument validation
############################################

if [[ -z "$REPO_NAME" || -z "$COMMIT_MSG" || -z "$VISIBILITY" ]]; then
  echo "Error: Missing required arguments."
  echo "Usage: $0 <repo-name> <commit-message> <private|public|internal>"
  exit 1
fi

if [[ "$VISIBILITY" != "private" && "$VISIBILITY" != "public" && "$VISIBILITY" != "internal" ]]; then
  echo "Error: VISIBILITY must be one of: private, public, internal."
  exit 1
fi

############################################
# Syntax check
############################################

if ! bash -n "$0" 2>/dev/null; then
  echo "Error: Syntax error detected in $0. Aborting."
  exit 1
fi

############################################
# Utility functions
############################################

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

log() {
  echo "[$(timestamp)] $*"
}

run() {
  local cmd=("$@")
  if [[ "$SIMULATE" == "1" ]]; then
    log "SIMULATE: ${cmd[*]}"
  else
    log "EXECUTE:  ${cmd[*]}"
    "${cmd[@]}"
  fi
}

############################################
# Confirm current directory (mandatory)
############################################

CURRENT_DIR="$(pwd)"
echo "------------------------------------------------------------"
echo "Current directory:"
echo "  $CURRENT_DIR"
echo "------------------------------------------------------------"
echo "Repository that will be created on GitHub: $REPO_NAME"
echo "Visibility: $VISIBILITY"
echo "Commit message: $COMMIT_MSG"
echo "SIMULATE mode: $SIMULATE (1=dry run, 0=real)"
echo "------------------------------------------------------------"

read -r -p "Are you sure this is the correct directory? (y/N) " answer
case "$answer" in
  [yY]|[yY][eE][sS])
    echo "Confirmed. Proceeding..."
    ;;
  *)
    echo "Aborted by user. No actions performed."
    exit 1
    ;;
esac

############################################
# Pre-flight checks
############################################

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI (gh) is not installed."
  echo "Install from: https://cli.github.com/ and then run: gh auth login"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed or not in PATH."
  exit 1
fi

if [[ "$SIMULATE" != "1" ]]; then
  if ! gh auth status >/dev/null 2>&1; then
    echo "Error: You are not authenticated with GitHub CLI."
    echo "Run: gh auth login"
    exit 1
  fi
else
  log "SIMULATE: would verify GitHub authentication with 'gh auth status'."
fi

############################################
# Initialize local repository if needed
############################################

if [[ ! -d ".git" ]]; then
  log "No .git directory found. Initializing a new Git repository."
  run git init
  run git branch -M main
else
  log ".git directory detected. Using existing Git repository."
fi

############################################
# Stage and commit changes
############################################

log "Staging all files for commit."
run git add .

if [[ "$SIMULATE" == "1" ]]; then
  log "SIMULATE: git commit -m "$COMMIT_MSG""
else
  log "Committing changes with message: $COMMIT_MSG"
  if ! git commit -m "$COMMIT_MSG"; then
    log "No changes to commit. Continuing."
  fi
fi

############################################
# Create GitHub repository and push
############################################

log "Creating GitHub repository '$REPO_NAME' with visibility '$VISIBILITY' and pushing code."
run gh repo create "$REPO_NAME" "--$VISIBILITY" --source=. --remote=origin --push

############################################
# Show repository information
############################################

log "Operation complete."

if [[ "$SIMULATE" == "1" ]]; then
  log "SIMULATE: would open the GitHub repository in your browser:"
  log "SIMULATE: gh repo view "$REPO_NAME" --web"
else
  log "Opening the GitHub repository in your browser."
  run gh repo view "$REPO_NAME" --web
fi
