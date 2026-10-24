#!/usr/bin/env python3
"""Validate the recovered Max source and build an unpublished, repeatable ZIP.

This tool never calls the repository generator, edits a source file, or writes
inside the publishing checkout. Its protected baseline is the shipped 0.3.2 ZIP.
"""
import argparse
import ast
import hashlib
import io
import json
import platform
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib


REPO = Path(__file__).resolve().parents[1]
ADDON_ID = 'slyguy.max.cleanui'
BASELINE_VERSION = '0.3.2'
BASELINE_SHA256 = '6f636e7504d183fed3341e9c38888082ed465488860d09025c287d28f5f537b8'
BASELINE_PACKAGE = REPO / ADDON_ID / (ADDON_ID + '-' + BASELINE_VERSION + '.zip')
SOURCE = REPO / 'source' / ADDON_ID
PROTECTION = REPO / 'source' / (ADDON_ID + '.protected.json')
CONTROLLER = 'resources/lib/ui/controller.py'
EDITABLE_ROOTS = ('resources/lib/ui/', 'resources/skins/')
PROTECTED_UI = (
    'resources/lib/ui/entry.py',
    'resources/lib/ui/intro.py',
    'resources/lib/ui/playback.py',
    'resources/lib/ui/session.py',
    'resources/lib/ui/diagnostics.py',
    'resources/skins/Default/1080i/ui_intro.xml',
)
# These existing methods own playback, navigation restoration, cleanup and Back.
# Presentation methods may change; preservation here is AST-based so formatting
# and comments do not require changing a protected baseline.
PROTECTED_METHODS = (
    '_initialize_session_state', '_finish_exit_if_ready', 'close_child_window',
    '_show_window', '_navigation_screens', '_restore_screen', 'play',
    '_close_all_windows', 'open_plugin_directory', 'run_plugin_after_close',
    'exit_clean_ui', '_player_is_playing', '_player_has_media',
    '_close_busy_dialogs', '_busy_dialog_visible', '_stop_player_safely',
    '_log_resource_counts', '_run_player', '_wait_before_restore',
    '_drain_pending_playback', '_refresh_after_playback', 'close_navigation',
)
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class IntegrityError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _archive_files(package):
    data = Path(package).read_bytes()
    if sha256(data) != BASELINE_SHA256:
        raise IntegrityError('Baseline ZIP SHA-256 differs from the published 0.3.2 package')
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None:
            raise IntegrityError('Baseline ZIP has a corrupt member')
        prefix = ADDON_ID + '/'
        for member in archive.infolist():
            if member.is_dir():
                continue
            if not member.filename.startswith(prefix):
                raise IntegrityError('Unexpected baseline root')
            name = member.filename[len(prefix):]
            if not name or '..' in Path(name).parts or '\\' in name or name in files:
                raise IntegrityError('Unsafe or duplicate baseline member: ' + name)
            files[name] = archive.read(member)
    return files


def _metadata_fingerprint(data):
    root = ET.fromstring(data)
    root.attrib.pop('version', None)
    for extension in root.findall('extension'):
        if extension.get('point') == 'xbmc.addon.metadata':
            for news in list(extension.findall('news')):
                extension.remove(news)

    def normalize(node):
        return [node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
                [normalize(child) for child in node]]

    return sha256(json.dumps(normalize(root), ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def _normalized_ast(node):
    """Canonicalize the Python 3.8 AST across supported builder runtimes."""
    if isinstance(node, ast.AST):
        kind = type(node).__name__
        if kind == 'Index':  # Removed as a wrapper starting with Python 3.9.
            return _normalized_ast(node.value)
        if kind == 'ExtSlice':
            return {'type': 'Tuple', 'fields': {'elts': _normalized_ast(node.dims),
                                              'ctx': {'type': 'Load', 'fields': {}}}}
        fields = {}
        for name, value in ast.iter_fields(node):
            if name == 'type_params' and not value:  # Added in Python 3.12.
                continue
            fields[name] = _normalized_ast(value)
        return {'type': kind, 'fields': fields}
    if isinstance(node, (list, tuple)):
        return [_normalized_ast(value) for value in node]
    if isinstance(node, bytes):
        return {'bytes_hex': node.hex()}
    if node is Ellipsis:
        return {'literal': 'Ellipsis'}
    if isinstance(node, complex):
        return {'complex': [node.real, node.imag]}
    return node


def _controller_fingerprints(data):
    tree = ast.parse(data.decode('utf-8-sig'), filename=CONTROLLER, feature_version=(3, 8))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'UIController']
    if len(classes) != 1:
        raise IntegrityError('Expected one UIController class')
    result = {}
    for name in PROTECTED_METHODS:
        methods = [node for node in classes[0].body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
        if len(methods) != 1:
            raise IntegrityError('Expected one protected UIController.' + name)
        representation = json.dumps(_normalized_ast(methods[0]), ensure_ascii=False,
                                    sort_keys=True, separators=(',', ':'))
        result['UIController.' + name] = sha256(representation.encode('utf-8'))
    return result


def _protected(name):
    return name in PROTECTED_UI or (name != 'addon.xml' and not name.startswith(EDITABLE_ROOTS))


def make_protection_manifest(package=BASELINE_PACKAGE):
    files = _archive_files(package)
    return {
        'schema': 1,
        'addon_id': ADDON_ID,
        'baseline': {'version': BASELINE_VERSION, 'package': str(BASELINE_PACKAGE.relative_to(REPO)),
                     'sha256': BASELINE_SHA256, 'files': len(files)},
        'editable_presentation_roots': list(EDITABLE_ROOTS),
        'protected_ui_files': list(PROTECTED_UI),
        'addon_xml_allowed_changes': ['version', 'xbmc.addon.metadata/news'],
        'addon_xml_metadata_sha256': _metadata_fingerprint(files['addon.xml']),
        'protected_files': {name: sha256(data) for name, data in sorted(files.items()) if _protected(name)},
        'controller_ast': {'path': CONTROLLER, 'algorithm': 'python38-normalized-ast-json-v1',
                           'methods': _controller_fingerprints(files[CONTROLLER])},
        'baseline_files': {name: sha256(data) for name, data in sorted(files.items())},
    }


def _source_files(source):
    source = Path(source)
    if not source.is_dir() or source.is_symlink():
        raise IntegrityError('Source must be a real directory')
    files = {}
    folded = set()
    for path in sorted(source.rglob('*')):
        name = path.relative_to(source).as_posix()
        if path.is_symlink():
            raise IntegrityError('Symlinks are not allowed: ' + name)
        if '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo') or path.name in ('.DS_Store', 'Thumbs.db'):
            continue
        if not path.is_file():
            continue
        if '\\' in name or name.casefold() in folded:
            raise IntegrityError('Unsafe or case-colliding source path: ' + name)
        folded.add(name.casefold())
        files[name] = path.read_bytes()
    return files


def validate_source(source=SOURCE, protection=PROTECTION, baseline=BASELINE_PACKAGE):
    expected = make_protection_manifest(baseline)
    policy = json.loads(Path(protection).read_text(encoding='utf-8'))
    if policy != expected:
        raise IntegrityError('Protection manifest does not match the pinned published baseline')
    files = _source_files(source)
    for name, digest in expected['protected_files'].items():
        if name not in files or sha256(files[name]) != digest:
            raise IntegrityError('Protected file changed or missing: ' + name)
    for name in files:
        if name not in expected['baseline_files'] and not name.startswith(EDITABLE_ROOTS):
            raise IntegrityError('New files are allowed only inside presentation roots: ' + name)
    if 'addon.xml' not in files or _metadata_fingerprint(files['addon.xml']) != expected['addon_xml_metadata_sha256']:
        raise IntegrityError('addon.xml changed outside version/news')
    if CONTROLLER not in files:
        raise IntegrityError('Controller is missing')
    actual_methods = _controller_fingerprints(files[CONTROLLER])
    for name, digest in expected['controller_ast']['methods'].items():
        if actual_methods[name] != digest:
            raise IntegrityError('Protected controller method changed: ' + name)
    for name, data in files.items():
        if name.endswith('.py'):
            try:
                text = data.decode('utf-8-sig')
                tree = ast.parse(text, filename=name, feature_version=(3, 8))
                compile(tree, name, 'exec')
            except (SyntaxError, UnicodeError) as error:
                raise IntegrityError('Python 3.8 syntax check failed: ' + name) from error
        elif name.endswith(('.xml', '.svg')):
            try:
                ET.fromstring(data)
            except ET.ParseError as error:
                raise IntegrityError('XML check failed: ' + name) from error
    changed = sorted(name for name, data in files.items()
                     if sha256(data) != expected['baseline_files'].get(name))
    deleted = sorted(set(expected['baseline_files']) - set(files))
    return files, {'protected_files_verified': len(expected['protected_files']),
                   'protected_controller_methods_verified': len(actual_methods),
                   'source_files': len(files), 'changed_from_0_3_2': changed,
                   'deleted_presentation_files': deleted}


def candidate_bytes(files, version):
    if not re.fullmatch(r'\d+(?:\.\d+)*', version or ''):
        raise IntegrityError('Candidate version must be numeric')
    if tuple(map(int, version.split('.'))) <= tuple(map(int, BASELINE_VERSION.split('.'))):
        raise IntegrityError('Candidate version must be newer than the protected baseline')
    packaged = dict(files)
    root = ET.fromstring(packaged['addon.xml'])
    root.set('version', version)
    packaged['addon.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(packaged.items()):
            info = zipfile.ZipInfo(ADDON_ID + '/' + name, date_time=ZIP_DATE)
            info.create_system = 0
            info.external_attr = 0x20
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    result = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(result)) as archive:
        if archive.testzip() is not None:
            raise IntegrityError('Candidate ZIP CRC failure')
    return result


def build_candidate(source=SOURCE, output_dir=None, version='0.4.0', protection=PROTECTION, baseline=BASELINE_PACKAGE):
    directory = Path(output_dir or REPO.parent / 'max-candidates').resolve()
    if directory == REPO or REPO in directory.parents:
        raise IntegrityError('Candidate output must be outside the publishing checkout')
    files, report = validate_source(source, protection, baseline)
    data = candidate_bytes(files, version)
    digest = sha256(data)
    name = '{}-{}-candidate-{}.zip'.format(ADDON_ID, version, digest[:12])
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.exists() and target.read_bytes() != data:
        raise IntegrityError('Refusing to overwrite a different candidate with the same name')
    target.write_bytes(data)
    target.with_suffix('.zip.sha256').write_text(digest + '  ' + name + '\n', encoding='ascii')
    report.update({'addon_id': ADDON_ID, 'version': version, 'zip': name, 'sha256': digest,
                   'bytes': len(data), 'candidate': True, 'published': False,
                   'validation_state': 'not_runtime_validated',
                   'baseline_sha256': BASELINE_SHA256, 'fixed_zip_timestamp': list(ZIP_DATE),
                   'build_runtime': {'python': platform.python_version(), 'zlib': zlib.ZLIB_RUNTIME_VERSION}})
    target.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--version', default='0.4.0')
    parser.add_argument('--output-dir', type=Path, default=REPO.parent / 'max-candidates')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        _, report = validate_source(args.source)
    else:
        target, report = build_candidate(args.source, args.output_dir, args.version)
        report = dict(report, output=str(target))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
