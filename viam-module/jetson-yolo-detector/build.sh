#!/bin/sh
# For Python modules, we just bundle the source files.
# Actual dependency installation happens in setup.sh at deploy time.
set -e
cd "$(dirname "$0")"
mkdir -p dist
tar -czf dist/archive.tar.gz     src/     requirements.txt     setup.sh     meta.json     README.md
echo "Build complete: dist/archive.tar.gz"
