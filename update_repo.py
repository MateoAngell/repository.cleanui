#!/usr/bin/env python3
"""
Update script for CleanUI Repository.
Usage: python3 update_repo.py <addon_zip_path>

Example: python3 update_repo.py /path/to/slyguy.disney.plus.cleanui.zip
This will:
  1. Copy and rename the ZIP to <addon_id>-<version>.zip
  2. Re-generate addons.xml + addons.xml.md5
  3. Commit and push to GitHub
  4. Create a new GitHub Release
"""
import hashlib
import os
import sys
import shutil
import subprocess
import zipfile
import xml.etree.ElementTree as ET
import tempfile

REPO_DIR = os.path.dirname(os.path.abspath(__file__))


def find_zip_files(directory):
    """Recursively find all addon ZIP files, excluding repo/module zips."""
    zips = []
    for root, dirs, files in os.walk(directory):
        if '.git' in root:
            continue
        for fname in files:
            if not fname.endswith('.zip'):
                continue
            if fname.startswith('repository.'):
                continue
            if fname.startswith('script.module.'):
                continue
            zips.append(os.path.join(root, fname))
    return sorted(zips)


def get_addon_info(zip_path):
    """Extract addon id and version from an addon ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith('/addon.xml'):
                content = zf.read(name).decode('utf-8')
                root = ET.fromstring(content)
                addon_id = root.get('id', '')
                version = root.get('version', '')
                return addon_id, version, content
    return None, None, None


def generate_repo_files():
    """Regenerate addons.xml and addons.xml.md5."""
    entries = []
    for zip_path in find_zip_files(REPO_DIR):
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.endswith('/addon.xml'):
                    content = zf.read(name).decode('utf-8')
                    # Strip XML declaration to avoid duplicates
                    lines = content.split('\n')
                    cleaned = [l for l in lines if not l.strip().startswith('<?xml')]
                    entries.append('\n'.join(cleaned).strip())
                    break
    
    xml_header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    content = xml_header + '<addons>\n' + '\n'.join(entries) + '\n</addons>\n'
    
    with open(os.path.join(REPO_DIR, 'addons.xml'), 'w', encoding='utf-8') as f:
        f.write(content)
    
    md5 = hashlib.md5(content.encode('utf-8')).hexdigest()
    with open(os.path.join(REPO_DIR, 'addons.xml.md5'), 'w') as f:
        f.write(md5)
    
    return md5

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 update_repo.py <addon_zip_path>")
        print("   Or: python3 update_repo.py --only-generate")
        return 1
    
    if sys.argv[1] == '--only-generate':
        md5 = generate_repo_files()
        print(f"addons.xml regenerated (md5: {md5})")
        return 0
    
    zip_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(zip_path):
        print(f"File not found: {zip_path}")
        return 1
    
    addon_id, version, xml_content = get_addon_info(zip_path)
    if not addon_id or not version:
        print(f"Could not extract addon info from {zip_path}")
        return 1
    
    print(f"Addon: {addon_id} v{version}")
    
    # Copy and rename
    dest_name = f"{addon_id}-{version}.zip"
    dest_path = os.path.join(REPO_DIR, dest_name)
    shutil.copy2(zip_path, dest_path)
    print(f"Copied to: {dest_name}")
    
    # Regenerate repo files
    md5 = generate_repo_files()
    print(f"Repo files regenerated (md5: {md5})")
    
    # Git commit
    try:
        subprocess.run(['git', '-C', REPO_DIR, 'add', '-A'], check=True)
        subprocess.run(['git', '-C', REPO_DIR, 'commit', '-m', f'Update {addon_id} to v{version}'], check=True)
        subprocess.run(['git', '-C', REPO_DIR, 'push'], check=True)
        print("Pushed to GitHub")
        
        # Create GitHub release
        tag = f"{addon_id}-v{version}"
        subprocess.run(['gh', '-R', 'MateoAngell/repository.cleanui', 'release', 'create', tag, '--title', f'{addon_id} v{version}', '--notes', f'Actualización {addon_id} a versión {version}', dest_path], check=True)
        print(f"GitHub Release created: {tag}")
    except subprocess.CalledProcessError as e:
        print(f"Git/GH error: {e}")
        return 1
    
    print("\nDone! Chromecast users can now update via repo.")
    return 0

if __name__ == '__main__':
    exit(main())
