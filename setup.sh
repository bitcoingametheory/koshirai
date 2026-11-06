#!/bin/sh
# Install into external user directories. POSIX Python 3.12+; no sudo.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python=${PYTHON:-python3}
export PYTHONDONTWRITEBYTECODE=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
export KANJI_DATA_DIR=${KANJI_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/kanji-translator}
export KANJI_CACHE_DIR=${KANJI_CACHE_DIR:-$KANJI_DATA_DIR/cache}
export KANJI_ENV_DIR=${KANJI_ENV_DIR:-$KANJI_DATA_DIR/environment}
"$python" - "$repo" <<'PY'
import os,sys
from pathlib import Path
if sys.version_info < (3,12):raise SystemExit('Python 3.12 or later is required.')
repo=Path(sys.argv[1]).resolve()
for key in ('KANJI_DATA_DIR','KANJI_CACHE_DIR','KANJI_ENV_DIR'):
    p=Path(os.environ[key]).expanduser().resolve()
    if p==repo or p.is_relative_to(repo):raise SystemExit(key+' must be outside the checkout.')
    p.mkdir(parents=True,exist_ok=True)
# --copies does not suppress Python's Linux lib64 symlink; exFAT has no symlinks.
(Path(os.environ['KANJI_ENV_DIR']).expanduser()/'lib64').mkdir(exist_ok=True)
PY
if [ ! -x "$KANJI_ENV_DIR/bin/python" ]; then
    "$python" -m venv --copies "$KANJI_ENV_DIR" || { echo 'Install Python venv support for your platform and retry.' >&2; exit 1; }
fi
stage=$(mktemp -d "$KANJI_CACHE_DIR/install.XXXXXXXX")
trap 'rm -rf -- "$stage"' EXIT HUP INT TERM
cp -R "$repo/kanji_translator" "$stage/kanji_translator"
cp "$repo/pyproject.toml" "$repo/README.md" "$repo/LICENSE" "$stage/"
extras=${SETUP_EXTRAS:-images}
for option in "$@"; do
    if [ "$option" = '--install-bert' ]; then
        if [ -n "$extras" ]; then extras="$extras,bert"; else extras=bert; fi
    fi
done
package=$stage
if [ -n "$extras" ]; then package="$stage[$extras]"; fi
"$KANJI_ENV_DIR/bin/python" -m pip install --no-compile "$package" || { echo 'Dependency install failed. Check network, Python version and disk space.' >&2; exit 1; }
"$KANJI_ENV_DIR/bin/python" -I -B -m kanji_translator.install_dictionaries "$@"
printf 'Lookup installed. Check OCR readiness above. CLI: %s/bin/kanji-translator\n' "$KANJI_ENV_DIR"
