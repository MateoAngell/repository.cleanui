#!/usr/bin/env python3
"""Generate addons.xml and addons.xml.md5 for Kodi repository."""
import hashlib
import os
import zipfile
import xml.etree.ElementTree as ET

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ADDONS_XML = os.path.join(REPO_DIR, 'addons.xml')
ADDONS_MD5 = os.path.join(REPO_DIR, 'addons.xml.md5')


def find_zip_files(directory):
    """Recursively find all addon ZIP files, excluding repo/module zips."""
    zips = []
    for root, dirs, files in os.walk(directory):
        # Skip .git directory
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

def strip_xml_declaration(content):
    """Remove <?xml ...?> declaration from content."""
    lines = content.split('\n')
    cleaned = [l for l in lines if not l.strip().startswith('<?xml')]
    return '\n'.join(cleaned)

def get_addon_xml_from_zip(zip_path):
    """Extract addon.xml content from an addon ZIP."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if name.endswith('/addon.xml'):
                    content = zf.read(name).decode('utf-8')
                    return strip_xml_declaration(content)
    except Exception as e:
        print(f"  ERROR reading {zip_path}: {e}")
    return None

def main():
    entries = []

    for zip_path in find_zip_files(REPO_DIR):
        rel_path = os.path.relpath(zip_path, REPO_DIR)
        print(f"  Processing: {rel_path}")

        content = get_addon_xml_from_zip(zip_path)
        if content:
            # Strip any leading/trailing whitespace
            content = content.strip()
            entries.append(content)
            # Verify it's valid XML
            try:
                ET.fromstring(content)
                print(f"    -> addon.xml OK")
            except ET.ParseError as e:
                print(f"    -> INVALID addon.xml: {e}")
        else:
            print(f"    -> NO addon.xml found")
    
    if not entries:
        print("\nNo addon entries found!")
        return 1
    
    xml_header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    addons_xml_content = xml_header + '<addons>\n' + '\n'.join(entries) + '\n</addons>\n'
    
    with open(ADDONS_XML, 'w', encoding='utf-8') as f:
        f.write(addons_xml_content)
    
    md5_hash = hashlib.md5(addons_xml_content.encode('utf-8')).hexdigest()
    with open(ADDONS_MD5, 'w') as f:
        f.write(md5_hash)
    
    print(f"\nDone!")
    print(f"  {ADDONS_XML}")
    print(f"  {ADDONS_MD5} = {md5_hash}")
    return 0

if __name__ == '__main__':
    exit(main())
