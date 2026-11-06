"""External writable locations; no data or environments belong in the checkout."""
import os
from pathlib import Path

def data_dir():
    return Path(os.environ.get('KANJI_DATA_DIR', str(Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'kanji-translator'))).expanduser().resolve()

def cache_dir():
    return Path(os.environ.get('KANJI_CACHE_DIR', str(data_dir()/'cache'))).expanduser().resolve()

def external(path):
    path=Path(path).expanduser().resolve()
    package=Path(__file__).resolve().parent
    # Also works in an installed wheel, where the package itself is protected.
    release=package.parent if package.name=='kanji_translator' and (package.parent/'pyproject.toml').is_file() else package
    if path==release or path.is_relative_to(release):
        raise ValueError('Writable data must be outside the installed package and checkout')
    return path
