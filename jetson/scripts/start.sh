#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/../app"
PYTHON="python3"
export PYTHONPATH="${APP_DIR}/..:${PYTHONPATH:-}"
${PYTHON} -m app.main "$@"
