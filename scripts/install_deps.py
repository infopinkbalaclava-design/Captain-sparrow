"""Interactive dependency installer for the Vision Trainer project.

This script helps install the optional dependencies used by the project. It
is intentionally conservative: it asks for confirmation before installing and
recommends using a virtual environment.

Usage:
  python scripts\install_deps.py        # interactive: choose which groups to install
  python scripts\install_deps.py --all --yes   # non-interactive install all

Groups:
- core: pillow, numpy, opencv-python
- vision: pytesseract (requires system tesseract)
- ui: keyboard, pyautogui
- web: fastapi, uvicorn

Note: Installing Tesseract OCR binary is not handled by this script — visit:
https://github.com/tesseract-ocr/tesseract for platform-specific installation.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

GROUPS = {
    'core': ['pillow', 'numpy', 'opencv-python'],
    'vision': ['pytesseract'],
    'ui': ['keyboard', 'pyautogui'],
    'web': ['fastapi', 'uvicorn[standard]']
}
ALL_PACKAGES = [pkg for packages in GROUPS.values() for pkg in packages]


def _confirm(prompt: str) -> bool:
    resp = input(f"{prompt} [y/N]: ").strip().lower()
    return resp in ('y', 'yes')


def _pip_install(packages: list[str]) -> int:
    cmd = [sys.executable, '-m', 'pip', 'install'] + packages
    print('Running:', ' '.join(cmd))
    return subprocess.call(cmd)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Install optional dependencies for Vision Trainer')
    parser.add_argument('--all', action='store_true', help='Install all groups')
    parser.add_argument('--yes', action='store_true', help='Assume yes for all prompts')
    parser.add_argument('--groups', nargs='*', choices=GROUPS.keys(), help='Install only these groups')
    args = parser.parse_args(argv)

    to_install: list[str] = []

    if args.all:
        to_install = ALL_PACKAGES
    elif args.groups:
        for g in args.groups:
            to_install.extend(GROUPS[g])
    else:
        print('Available groups:')
        for name, pkgs in GROUPS.items():
            print(f" - {name}: {', '.join(pkgs)}")
        sel = input('Comma-separated groups to install (or "all"): ').strip()
        if sel.lower() == 'all':
            to_install = ALL_PACKAGES
        else:
            for part in [p.strip() for p in sel.split(',') if p.strip()]:
                if part in GROUPS:
                    to_install.extend(GROUPS[part])

    if not to_install:
        print('Nothing to install. Exiting.')
        return 0

    print('\nPackages selected:')
    for p in to_install:
        print(' -', p)

    if not args.yes and not _confirm('Proceed to install these packages?'):
        print('Aborted by user')
        return 0

    ret = _pip_install(list(dict.fromkeys(to_install)))
    if ret == 0:
        print('\nInstallation finished. If you installed pytesseract, remember to install the Tesseract binary (system package).')
    else:
        print('\nInstallation did not complete successfully; check output above.')
    return ret


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))