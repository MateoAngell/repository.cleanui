#!/usr/bin/env python3
"""Build the Kodi index, choosing one numeric release per add-on.

Packages are kept for rollback; active releases are copied into the canonical
addon-id directory. Hash the exact UTF-8 bytes written, including on Windows.
"""
import hashlib
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile

REPO_DIR = Path(__file__).resolve().parent


def package_info(path):
    with zipfile.ZipFile(path) as archive:
        candidates = [n for n in archive.namelist() if n.count('/') == 1 and n.endswith('/addon.xml')]
        if len(candidates) != 1:
            raise ValueError('Expected one root addon.xml: ' + str(path))
        data = archive.read(candidates[0])
        manifest = ET.fromstring(data)
        addon_id, version = manifest.get('id'), manifest.get('version')
        if not addon_id or not re.fullmatch(r'[A-Za-z0-9_.-]+', addon_id):
            raise ValueError('Invalid addon ID')
        if not version or not re.fullmatch(r'\d+(?:\.\d+)*', version):
            raise ValueError('Expected numeric release version: ' + str(version))
        return addon_id, version, manifest


def generate(directory=REPO_DIR):
    directory = Path(directory)
    latest = {}
    for path in sorted(directory.rglob('*.zip')):
        if '.git' in path.parts or path.name.startswith(('repository.', 'script.module.')):
            continue
        addon_id, version, manifest = package_info(path)
        key = tuple(map(int, version.split('.')))
        if addon_id not in latest or key > latest[addon_id][0]:
            latest[addon_id] = (key, path, manifest, version)
    if not latest:
        raise ValueError('No add-on packages found')
    index = ET.Element('addons')
    for addon_id, (_, source, manifest, version) in sorted(latest.items()):
        target_dir = directory / addon_id
        target_dir.mkdir(exist_ok=True)
        target = target_dir / (addon_id + '-' + version + '.zip')
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        (target_dir / 'addon.xml').write_bytes(ET.tostring(manifest, encoding='utf-8'))
        index.append(manifest)
    ET.indent(index, space='  ')
    data = ET.tostring(index, encoding='utf-8', xml_declaration=True) + b'\n'
    (directory / 'addons.xml').write_bytes(data)
    digest = hashlib.md5(data).hexdigest()
    (directory / 'addons.xml.md5').write_text(digest, encoding='ascii')
    return digest


if __name__ == '__main__':
    print(generate())
