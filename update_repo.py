#!/usr/bin/env python3
"""Prepare a Kodi repository update locally; inspect and commit the result.

Usage: python update_repo.py package.zip
       python update_repo.py --only-generate
No implicit git add -A, pushes or unrelated commits.
"""
from pathlib import Path
import shutil
import sys
from generate_repo import generate, package_info, REPO_DIR


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python update_repo.py package.zip | --only-generate')
    if sys.argv[1] != '--only-generate':
        source = Path(sys.argv[1]).resolve()
        addon_id, version, _ = package_info(source)
        folder = REPO_DIR / addon_id
        folder.mkdir(exist_ok=True)
        target = folder / (addon_id + '-' + version + '.zip')
        if source != target.resolve():
            shutil.copy2(source, target)
    print('Repository prepared; index checksum:', generate())
    print('Review the package and index changes before committing and pushing.')


if __name__ == '__main__':
    main()
