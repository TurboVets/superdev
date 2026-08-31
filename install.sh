#!/usr/bin/env bash
# Install SuperDev as a personal Cursor skill.
# Run from the clone root:
#   ./install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="${SUPERDEV_DEST:-$HOME/.cursor/skills/superdev}"
RULES="${HOME}/.cursor/rules"

echo "Installing SuperDev → ${DEST}"
mkdir -p "${DEST}" "${RULES}" "${DEST}/state/user-intentions" "${DEST}/state/work-history"

# Copy skill files; never clobber an existing operator.yaml or state/.
rsync -a \
  --exclude '.git/' \
  --exclude 'state/' \
  --exclude 'operator.yaml' \
  --exclude '.DS_Store' \
  "${ROOT}/" "${DEST}/"

if [[ ! -f "${DEST}/operator.yaml" ]]; then
  cp "${ROOT}/operator.example.yaml" "${DEST}/operator.yaml"
  echo "Wrote ${DEST}/operator.yaml — fill github.login and github.default_repo"
fi

cp "${ROOT}/rules/superdev-sticky.mdc" "${RULES}/superdev-sticky.mdc"
chmod +x "${DEST}/install.sh" "${DEST}/scripts/"*.py "${DEST}/scripts/"*.sh 2>/dev/null || true

# Best-effort: prefill github.login from gh.
if command -v gh >/dev/null 2>&1; then
  LOGIN="$(gh api user --jq .login 2>/dev/null || true)"
  if [[ -n "${LOGIN}" ]] && grep -q 'login: ""' "${DEST}/operator.yaml"; then
    python3 - "${DEST}/operator.yaml" "${LOGIN}" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
login = sys.argv[2]
text = p.read_text()
text = text.replace('login: ""', f'login: "{login}"', 1)
p.write_text(text)
print(f"Prefill github.login = {login}")
PY
  fi
else
  echo "warn: gh CLI not found. Install GitHub CLI and run: gh auth login"
fi

echo
echo "Next:"
echo "  1. Edit ${DEST}/operator.yaml  (default_repo, workspace.path, skills.*)"
echo "  2. Cursor Settings → MCP → enable Browser Tab (required for Path 6 smoke)"
echo "  3. In a new Agent chat, attach the superdev skill or type /superdev"
echo "  4. Do NOT copy someone else's state/ directory — intentions are personal"
echo
echo "Sticky rule installed: ${RULES}/superdev-sticky.mdc"
echo "Done."
