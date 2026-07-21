#!/usr/bin/env python3
"""Generate addons.xml and addons.xml.md5 for Kodi repository."""
import hashlib
import os
import zipfile
import xml.etree.ElementTree as ET

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ADDONS_XML = os.path.join(REPO_DIR, 'addons.xml')
ADDONS_MD5 = os.path.join(REPO_DIR, 'addons.xml.md5')

def get_addon_xml_from_zip(zip_path):
    """Extract addon.xml content from an addon ZIP."""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            # Find addon.xml - could be in root or first dir
            for name in zf.namelist():
                if name.endswith('/addon.xml'):
                    return zf.read(name).decode('utf-8')
    except Exception as e:
        print(f"  ERROR reading {zip_path}: {e}")
    return None

def main():
    entries = []
    
    for fname in sorted(os.listdir(REPO_DIR)):
        if not fname.endswith('.zip'):
            continue
        if fname.startswith('script.module.slyguy'):
            print(f"  SKIP (not for repo): {fname}")
            continue
        
        zip_path = os.path.join(REPO_DIR, fname)
        print(f"  Processing: {fname}")
        
        content = get_addon_xml_from_zip(zip_path)
        if content:
            entries.append(content)
            # Verify it parses
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
    
    # Write addons.xml
    with open(ADDONS_XML, 'w', encoding='utf-8') as f:
        f.write(addons_xml_content)
    
    # Write addons.xml.md5
    md5_hash = hashlib.md5(addons_xml_content.encode('utf-8')).hexdigest()
    with open(ADDONS_MD5, 'w') as f:
        f.write(md5_hash)
    
    print(f"\nDone!")
    print(f"  {ADDONS_XML}  ({len(addons_xml_content)} bytes)")
    print(f"  {ADDONS_MD5}  ({md5_hash})")
    return 0

if __name__ == '__main__':
    exit(main())
