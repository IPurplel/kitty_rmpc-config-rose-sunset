#!/usr/bin/env bash
set -euo pipefail
rose_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 is required. Install it, then run bash install.sh again.' >&2
    exit 1
fi
exec python3 "$rose_repo_dir/scripts/install.py" "$@"
