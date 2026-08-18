#!/usr/bin/env bash
set -Eeuo pipefail

# Configure these in PythonAnywhere Web -> Environment variables.
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
BRANCH="${DEPLOY_BRANCH:-master}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"
WSGI_FILE="${WSGI_FILE:-}"
LOCK_FILE="${DEPLOY_LOCK:-/tmp/monelanal-deploy.lock}"
LOG_FILE="${DEPLOY_LOG:-$PROJECT_DIR/deploy.log}"

exec >>"$LOG_FILE" 2>&1
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Deploy already running"; exit 0; }

echo "===== DEPLOY $(date '+%Y-%m-%d %H:%M:%S') ====="
cd "$PROJECT_DIR"

OLD_COMMIT="$(git rev-parse HEAD)"
git fetch origin "$BRANCH"
NEW_COMMIT="$(git rev-parse "origin/$BRANCH")"

if [[ "$OLD_COMMIT" == "$NEW_COMMIT" ]]; then
  echo "No changes"
  exit 0
fi

git merge --ff-only "origin/$BRANCH"

if [[ -x "$VENV_DIR/bin/pip" ]]; then
  PYTHON="$VENV_DIR/bin/python"
  PIP="$VENV_DIR/bin/pip"
else
  PYTHON="python3"
  PIP=(python3 -m pip)
fi

if [[ -x "$VENV_DIR/bin/pip" ]]; then
  PIP=("$VENV_DIR/bin/pip")
fi

if git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" | grep -qE '(^|/)requirements\.txt$'; then
  "${PIP[@]}" install -r requirements.txt
fi

if git diff --name-only "$OLD_COMMIT" "$NEW_COMMIT" | grep -Eq '(^|/)(migrate.py|db/|services/|bot/|web/|app.py)'; then
  "$PYTHON" migrate.py
fi

if [[ -n "$WSGI_FILE" ]]; then
  touch "$WSGI_FILE"
fi

echo "Deploy complete: $NEW_COMMIT"
