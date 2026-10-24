"""Candidate integrity/publication tests; never import Kodi or account code."""
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_max_candidate', REPO / 'tools' / 'build_max_candidate.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class MaxReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='max-release-', dir=REPO.parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / builder.ADDON_ID
        self.source.mkdir()
        self.baseline = builder._archive_files(builder.BASELINE_PACKAGE)
        for name, data in self.baseline.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def validate(self):
        return builder.validate_source(self.source)

    def build(self, directory='candidates', version='0.4.0'):
        return builder.build_candidate(self.source, self.root / directory, version)

    def test_published_baseline_hash_and_recorded_protection_match(self):
        self.assertEqual(builder.sha256(builder.BASELINE_PACKAGE.read_bytes()), builder.BASELINE_SHA256)
        self.assertEqual(json.loads(builder.PROTECTION.read_text()), builder.make_protection_manifest())
        files, report = self.validate()
        self.assertEqual(files, self.baseline)
        self.assertEqual(report['changed_from_0_3_2'], [])
        self.assertEqual(report['source_files'], 66)

    def test_current_versioned_source_keeps_protected_baseline(self):
        _, report = builder.validate_source()
        self.assertEqual(report['protected_files_verified'], 21)
        self.assertEqual(report['protected_controller_methods_verified'], 22)

    def test_candidate_rebuild_is_byte_identical_despite_mtime_changes(self):
        first, report = self.build('first')
        for path in self.source.rglob('*'):
            if path.is_file():
                os.utime(path, (1700000000, 1700000000))
        second, repeated = self.build('second')
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(report['sha256'], repeated['sha256'])
        with zipfile.ZipFile(first) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            self.assertTrue(all(info.date_time == builder.ZIP_DATE for info in archive.infolist()))

    def test_candidate_version_changes_only_packaged_manifest(self):
        original = (self.source / 'addon.xml').read_bytes()
        target, report = self.build()
        self.assertEqual((self.source / 'addon.xml').read_bytes(), original)
        with zipfile.ZipFile(target) as archive:
            data = archive.read(builder.ADDON_ID + '/addon.xml')
            self.assertEqual(ET.fromstring(data).get('version'), '0.4.0')
            self.assertEqual(builder._metadata_fingerprint(data), builder._metadata_fingerprint(original))
            for name, expected in builder.make_protection_manifest()['protected_files'].items():
                self.assertEqual(builder.sha256(archive.read(builder.ADDON_ID + '/' + name)), expected)
        self.assertTrue(report['candidate'])
        self.assertFalse(report['published'])
        self.assertEqual(report['validation_state'], 'not_runtime_validated')

    def test_build_preserves_repository_index_historical_packages_and_source(self):
        paths = [REPO / 'addons.xml', REPO / 'addons.xml.md5', builder.BASELINE_PACKAGE,
                 builder.BASELINE_PACKAGE.with_suffix('.zip.sha256'),
                 REPO / 'slyguy.disney.plus.cleanui' / 'slyguy.disney.plus.cleanui-0.2.6.zip',
                 REPO / 'slyguy.disney.plus.cleanui' / 'addon.xml', REPO / builder.ADDON_ID / 'addon.xml']
        before = {str(path): builder.sha256(path.read_bytes()) for path in paths}
        source_before = {str(path): builder.sha256(path.read_bytes())
                         for path in self.source.rglob('*') if path.is_file()}
        self.build()
        self.assertEqual(before, {str(path): builder.sha256(path.read_bytes()) for path in paths})
        self.assertEqual(source_before, {str(path): builder.sha256(path.read_bytes())
                                         for path in self.source.rglob('*') if path.is_file()})

    def test_api_plugin_intro_and_entry_tampering_is_rejected(self):
        for name in ['resources/lib/api.py', 'resources/lib/plugin.py',
                     'resources/lib/ui/entry.py', 'resources/lib/ui/intro.py',
                     'resources/lib/ui/playback.py', 'resources/lib/ui/session.py',
                     'resources/lib/ui/diagnostics.py', 'resources/media/intro.mp4',
                     'resources/skins/Default/1080i/ui_intro.xml']:
            with self.subTest(name=name):
                path = self.source / name
                path.write_bytes(self.baseline[name] + b'\n')
                with self.assertRaisesRegex(builder.IntegrityError, 'Protected file'):
                    self.validate()
                path.write_bytes(self.baseline[name])

    def test_protected_file_removal_is_rejected(self):
        (self.source / 'resources/lib/ui/entry.py').unlink()
        with self.assertRaisesRegex(builder.IntegrityError, 'Protected file'):
            self.validate()

    def test_presentation_source_and_skin_changes_are_allowed(self):
        path = self.source / 'resources/lib/ui/new_renderer.py'
        path.write_text('def render_title(value):\n    return value.upper()\n')
        skin = self.source / 'resources/skins/Default/1080i/ui_choice.xml'
        root = ET.fromstring(skin.read_bytes())
        width = root.find('.//width')
        self.assertIsNotNone(width)
        width.text = str(int(width.text) + 1)
        skin.write_bytes(ET.tostring(root, encoding='utf-8'))
        _, report = self.validate()
        self.assertIn('resources/lib/ui/new_renderer.py', report['changed_from_0_3_2'])
        self.assertIn('resources/skins/Default/1080i/ui_choice.xml', report['changed_from_0_3_2'])

    def test_new_files_outside_presentation_roots_are_rejected(self):
        (self.source / 'new_settings.xml').write_text('<settings/>')
        with self.assertRaisesRegex(builder.IntegrityError, 'New files are allowed only'):
            self.validate()

    def replace_method(self, method_name, body):
        path = self.source / builder.CONTROLLER
        source = path.read_text()
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'UIController')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
        lines = source.splitlines(keepends=True)
        lines[method.body[0].lineno - 1:method.end_lineno] = ['        ' + body + '\n']
        path.write_text(''.join(lines))

    def test_protected_controller_playback_body_change_is_rejected(self):
        self.replace_method('_run_player', 'return False')
        with self.assertRaisesRegex(builder.IntegrityError, 'Protected controller method changed'):
            self.validate()

    def test_controller_presentation_method_can_change(self):
        self.replace_method('_present_detail', 'return True')
        self.validate()

    def test_controller_comment_does_not_change_protected_ast(self):
        path = self.source / builder.CONTROLLER
        source = path.read_text().replace(
            '    def _run_player(self, path, screens=None):\n',
            '    def _run_player(self, path, screens=None):\n        # Documentation only.\n')
        path.write_text(source)
        self.validate()

    def test_ast_fingerprint_ignores_old_index_wrapper(self):
        legacy_type = type('Index', (ast.AST,), {'_fields': ('value',)})
        literal = ast.Constant(value=0)
        legacy = legacy_type(value=literal)
        self.assertEqual(builder._normalized_ast(legacy), builder._normalized_ast(literal))

    def test_duplicate_protected_controller_method_is_rejected(self):
        path = self.source / builder.CONTROLLER
        path.write_bytes(path.read_bytes() + b'\n    def _run_player(self, path, screens=None):\n        return False\n')
        with self.assertRaisesRegex(builder.IntegrityError, 'Expected one protected'):
            self.validate()

    def test_addon_xml_version_and_news_are_allowed(self):
        path = self.source / 'addon.xml'
        root = ET.fromstring(path.read_bytes())
        root.set('version', '0.4.0')
        metadata = next(node for node in root.findall('extension') if node.get('point') == 'xbmc.addon.metadata')
        news = metadata.find('news')
        if news is None:
            news = ET.SubElement(metadata, 'news')
        news.text = 'Presentation candidate; validation pending.'
        path.write_bytes(ET.tostring(root, encoding='utf-8'))
        self.validate()

    def test_addon_xml_identity_and_dependencies_are_protected(self):
        path = self.source / 'addon.xml'
        for change in ['id', 'name', 'requires']:
            with self.subTest(change=change):
                root = ET.fromstring(self.baseline['addon.xml'])
                if change == 'requires':
                    root.find('./requires/import').set('version', '99.0.0')
                else:
                    root.set(change, 'changed')
                path.write_bytes(ET.tostring(root, encoding='utf-8'))
                with self.assertRaisesRegex(builder.IntegrityError, 'addon.xml changed'):
                    self.validate()

    def test_manifest_edit_cannot_bypass_protected_file_checks(self):
        policy = builder.make_protection_manifest()
        policy['protected_files']['resources/lib/api.py'] = '0' * 64
        altered = self.root / 'changed-protection.json'
        altered.write_text(json.dumps(policy))
        with self.assertRaisesRegex(builder.IntegrityError, 'Protection manifest does not match'):
            builder.validate_source(self.source, protection=altered)

    def test_wrong_baseline_package_is_rejected(self):
        package = self.root / 'wrong-baseline.zip'
        package.write_bytes(builder.BASELINE_PACKAGE.read_bytes() + b'changed')
        with self.assertRaisesRegex(builder.IntegrityError, 'Baseline ZIP SHA-256'):
            builder.validate_source(self.source, baseline=package)

    def test_output_inside_publishing_checkout_is_rejected(self):
        with self.assertRaisesRegex(builder.IntegrityError, 'outside the publishing checkout'):
            builder.build_candidate(self.source, REPO / builder.ADDON_ID)

    def test_candidate_collision_does_not_overwrite_other_bytes(self):
        target, _ = self.build()
        target.write_bytes(b'other candidate content')
        with self.assertRaisesRegex(builder.IntegrityError, 'Refusing to overwrite'):
            self.build()
        self.assertEqual(target.read_bytes(), b'other candidate content')

    def test_historical_or_non_numeric_version_is_rejected(self):
        for version in ['0.3.2', '0.3.1', '0.4.0-rc1', '']:
            with self.subTest(version=version):
                with self.assertRaises(builder.IntegrityError):
                    self.build(version=version)

    def test_invalid_python_and_xml_are_rejected(self):
        path = self.source / 'resources/lib/ui/new_renderer.py'
        path.write_text('def invalid(:\n')
        with self.assertRaisesRegex(builder.IntegrityError, 'Python 3.8 syntax'):
            self.validate()
        path.unlink()
        (self.source / 'resources/skins/Default/1080i/new.xml').write_text('<broken>')
        with self.assertRaisesRegex(builder.IntegrityError, 'XML check failed'):
            self.validate()

    def test_generated_bytecode_is_not_packaged(self):
        cache = self.source / 'resources/lib/ui/__pycache__'
        cache.mkdir()
        (cache / 'new.cpython-311.pyc').write_bytes(b'generated')
        target, _ = self.build()
        with zipfile.ZipFile(target) as archive:
            self.assertFalse(any('__pycache__' in name or name.endswith('.pyc') for name in archive.namelist()))

    @unittest.skipUnless(hasattr(os, 'symlink'), 'Host has no symlink support')
    def test_symlinked_source_is_rejected(self):
        link = self.source / 'resources/lib/ui/linked.py'
        try:
            link.symlink_to(self.source / 'resources/lib/api.py')
        except OSError:
            self.skipTest('Host does not permit creating test symlinks')
        with self.assertRaisesRegex(builder.IntegrityError, 'Symlinks are not allowed'):
            self.validate()


class PublishedRepositoryTests(unittest.TestCase):
    def test_index_has_unique_addon_ids(self):
        root = ET.fromstring((REPO / 'addons.xml').read_bytes())
        ids = [addon.get('id') for addon in root]
        self.assertEqual(root.tag, 'addons')
        self.assertEqual(len(ids), len(set(ids)))

    def test_index_md5_matches_exact_published_bytes(self):
        actual = hashlib.md5((REPO / 'addons.xml').read_bytes()).hexdigest()
        self.assertEqual(actual, (REPO / 'addons.xml.md5').read_text().strip())

    def test_active_index_manifests_match_canonical_package_and_mirror(self):
        def semantic(node):
            return [node.tag, sorted(node.attrib.items()), (node.text or '').strip(),
                    [semantic(child) for child in node]]

        for addon in ET.fromstring((REPO / 'addons.xml').read_bytes()):
            aid, version = addon.get('id'), addon.get('version')
            with self.subTest(addon=aid, version=version):
                package = REPO / aid / '{}-{}.zip'.format(aid, version)
                with zipfile.ZipFile(package) as archive:
                    self.assertIsNone(archive.testzip())
                    manifest = archive.read(aid + '/addon.xml')
                self.assertEqual(semantic(ET.fromstring(manifest)), semantic(addon))
                self.assertEqual(semantic(ET.fromstring((REPO / aid / 'addon.xml').read_bytes())), semantic(addon))

    def test_all_published_sha256_sidecars_match_their_exact_archives(self):
        sidecars = list(REPO.rglob('*.zip.sha256'))
        self.assertTrue(sidecars)
        for sidecar in sidecars:
            with self.subTest(sidecar=sidecar.name):
                actual = builder.sha256(sidecar.with_suffix('').read_bytes())
                self.assertEqual(actual, sidecar.read_text().split()[0])

    def test_recovered_source_checkout_keeps_original_byte_endings(self):
        attributes = (REPO / 'source' / '.gitattributes').read_text()
        self.assertIn('slyguy.max.cleanui/** -text', attributes)


if __name__ == '__main__':
    unittest.main()
