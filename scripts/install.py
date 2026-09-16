#!/usr/bin/env python3
"""Install repository files, preserving existing MPD settings; no root or network."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
helper = runpy.run_path(str(ROOT / 'rose-room-apply.py'))
BEGIN = '# >>> ROSE ROOM REPOSITORY >>>'
END = '# <<< ROSE ROOM REPOSITORY <<<'

def preflight():
    missing = [name for name in ('kitty', 'rmpc', 'cava') if not shutil.which(name)]
    if missing:
        raise ValueError('Missing programs: ' + ', '.join(missing) + '. Install the requirements listed in README.md and retry. No files changed.')
    found = subprocess.run(['kitty', '--version'], capture_output=True, text=True, timeout=10)
    version = re.search(r'kitty (\d+)\.(\d+)\.(\d+)', found.stdout + found.stderr)
    if not version or tuple(map(int, version.groups())) < (0, 47, 1):
        raise ValueError('Kitty 0.47.1 or newer is required. No files changed.')
    if shutil.which('fc-match'):
        font = subprocess.run(['fc-match', '--format=%{family}', 'JetBrains Mono'], capture_output=True, text=True, timeout=10)
        if 'JetBrains' not in font.stdout:
            raise ValueError('JetBrains Mono is missing. Install the font and retry. No files changed.')
    else:
        print('Note: fc-match is unavailable; ensure JetBrains Mono is installed.')

def kitty_text(before, exported):
    if before is None or before == exported:
        return exported
    text = before.decode()
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
            raise ValueError('Malformed repository-managed Kitty block; no files changed.')
        start, end = text.index(BEGIN), text.index(END) + len(END)
        text = text[:start] + text[end:]
    return (text.rstrip() + '\n\n' + BEGIN + '\n' + exported.decode() + END + '\n').encode()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='Validate without changing configuration files')
    modes.add_argument('--restore', action='store_true', help='Undo the last installation made by install.sh')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise ValueError('Run as your normal desktop user, without sudo.')
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config').expanduser().absolute()
    backup_root = base / 'rose-room-github-backups'
    record_path = backup_root / 'last.json'
    if args.restore:
        helper['restore'](record_path)
        return
    preflight()
    sources = {
        'kitty/kitty.conf': (ROOT / 'kitty/kitty.conf').read_bytes(),
        'kitty/themes/sunset-rose.conf': (ROOT / 'kitty/themes/sunset-rose.conf').read_bytes(),
        'rmpc/config.ron': (ROOT / 'rmpc/config.ron').read_bytes(),
        'rmpc/themes/rose-room-sunset-cinema.ron': (ROOT / 'rmpc/themes/rose-room-sunset-cinema.ron').read_bytes(),
    }
    plans = []
    for rel, exported in sources.items():
        path = base / rel
        # Preserve symlink-based dotfile arrangements by stopping instead of replacing links.
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Symlink-based configuration found: ' + str(path) + '. Use the manual installation instructions for your dotfile manager.')
        original, mode = helper['file_state'](path)
        if rel == 'kitty/kitty.conf':
            data = kitty_text(original, exported)
        elif rel == 'rmpc/config.ron' and original is not None:
            text = original.decode()
            for field in ('theme', 'tabs', 'enable_mouse'):
                start, end = helper['value_span'](exported.decode(), field)
                text = helper['replace_field'](text, field, exported.decode()[start:end])
            data = text.encode()
        else:
            data = exported
        plans.append((path, data, original, mode))
    by_name = {p.name: data for p, data, _, _ in plans}
    helper['native_check'](by_name['config.ron'], by_name['rose-room-sunset-cinema.ron'])
    if args.check:
        print('Check complete. No configuration files changed.')
        return
    if all(original == data for _, data, original, _ in plans):
        print('This repository selection is already installed. No changes needed.')
        return
    if record_path.exists():
        import json
        previous = json.loads(record_path.read_text())
        if previous.get('status') in ('prepared', 'applied'):
            raise ValueError('A previous install.sh backup is active. Run bash install.sh --restore before applying a revised selection. Backups: ' + str(backup_root))
    for path, _, original, _ in plans:
        expected = helper['digest'](original) if original is not None else None
        if helper['current_hash'](path) != expected:
            raise ValueError('A configuration changed during validation. Retry: ' + str(path))
    backup_dir = backup_root / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup_dir.mkdir(parents=True, mode=0o700)
    record = {'status': 'prepared', 'files': []}
    for index, (path, data, original, mode) in enumerate(plans):
        backup = backup_dir / (str(index) + '-' + path.name)
        if original is not None:
            helper['atomic_write'](backup, original)
        record['files'].append({'path': str(path), 'backup': str(backup), 'mode': mode,
            'original_sha256': helper['digest'](original) if original is not None else None,
            'applied_sha256': helper['digest'](data)})
    helper['write_record'](record_path, record)
    try:
        for path, data, original, mode in plans:
            expected = helper['digest'](original) if original is not None else None
            if helper['current_hash'](path) != expected:
                raise ValueError('A configuration changed before writing: ' + str(path))
            path.parent.mkdir(parents=True, exist_ok=True)
            helper['atomic_write'](path, data, mode)
        record['status'] = 'applied'
        helper['write_record'](record_path, record)
    except Exception:
        helper['restore'](record_path)
        raise
    print('Installed Sunset Rose. Backup: ' + str(backup_dir))
    print('Close and reopen Kitty, then launch rmpc. Undo: bash install.sh --restore')
    print('Set assets/wallpapers/rose-room-sunset.png as your desktop wallpaper to match the screenshots.')
    print('MPD playback and its CAVA FIFO must already be configured; see README.md.')

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        sys.exit(str(error))
