#!/usr/bin/env python3
"""Audit one immutable candidate and human observations; never publish or deploy.

Optional ADB operation is read-only and restricted to the fixed Waydroid serial.
No credentials, userdata, Kodi APK or other addon directories are read.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import build_max_candidate as builder

WAYDROID_SERIAL = '192.168.240.112:5555'
REMOTE_PARENT = '/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons'
ADDON_ID = builder.ADDON_ID
REQUIRED_CHECKS = ('profiles', 'home_navigation', 'search', 'collections', 'detail',
                   'seasons', 'intro_complete_audio', 'playback_resume',
                   'back_home_reopen', 'service_switch', 'network_recovery',
                   'process_recovery', 'ten_open_exit_cycles', 'performance_memory',
                   'playback_2h')
MAX_BYTES = 128 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if '\\' in name or name.startswith('/') or any(p in ('', '.', '..') for p in name.rstrip('/').split('/')):
        raise ValueError('Unsafe member path: ' + name)
    if not path.parts or path.parts[0] != ADDON_ID:
        raise ValueError('Unexpected addon root: ' + name)
    return path.as_posix().rstrip('/')


def read_candidate(path):
    raw = Path(path).read_bytes()
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for member in archive.infolist():
            name = safe_name(member.filename)
            if name.casefold() in seen:
                raise ValueError('Duplicate/case-colliding member: ' + name)
            seen.add(name.casefold())
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
                raise ValueError('Non-regular member: ' + name)
            total += member.file_size
            if total > MAX_BYTES:
                raise ValueError('Candidate exceeds uncompressed size limit')
            if not member.is_dir():
                if name == ADDON_ID:
                    raise ValueError('Root is a file')
                files[name[len(ADDON_ID) + 1:]] = archive.read(member)
    with tempfile.TemporaryDirectory(prefix='cleanui-candidate-audit-') as tmp:
        root = Path(tmp)
        for name, data in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        checked_files, protection = builder.validate_source(root)
        if set(checked_files) != set(files):
            raise ValueError('Candidate contains generated/ignored files not emitted by constructor')
    addon = ET.fromstring(files['addon.xml'])
    if addon.get('id') != ADDON_ID:
        raise ValueError('Unexpected manifest id')
    return files, dict(sha256=digest(raw), bytes=len(raw), addon_id=ADDON_ID,
                      version=addon.get('version'), files=len(files), integrity=protection)


def compare_installed(expected, tar_bytes):
    actual, ignored, seen = {}, [], set()
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode='r:*') as archive:
        total = 0
        for member in archive:
            name = safe_name(member.name)
            if name in seen:
                raise ValueError('Duplicate installed member: ' + name)
            seen.add(name)
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Non-regular installed member: ' + name)
            relative = name[len(ADDON_ID) + 1:]
            total += member.size
            if total > MAX_BYTES:
                raise ValueError('Installed addon exceeds size limit')
            if '__pycache__' in PurePosixPath(relative).parts or relative.endswith(('.pyc', '.pyo')):
                ignored.append(relative)
                continue
            actual[relative] = archive.extractfile(member).read()
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    return dict(exact_packaged_files=not (missing or extra or changed), missing=missing,
                extra=extra, changed=changed, ignored_generated_bytecode=sorted(ignored),
                installed_file_sha256={name: digest(data) for name, data in sorted(actual.items())})


def read_waydroid(serial, adb='adb'):
    if serial != WAYDROID_SERIAL:
        raise ValueError('Only the fixed Waydroid serial is allowed: ' + WAYDROID_SERIAL)
    # Fixed shell command: no user path, package, environment or device interpolation.
    command = ('if pidof org.xbmc.kodi >/dev/null; then echo Kodi_must_be_stopped >&2; exit 73; fi; '
               + 'cd ' + REMOTE_PARENT + ' && tar -cf - ' + ADDON_ID)
    result = subprocess.run([adb, '-s', WAYDROID_SERIAL, 'exec-out', 'sh', '-c', command],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=True)
    if len(result.stdout) > MAX_BYTES:
        raise ValueError('ADB archive exceeds size limit')
    return result.stdout


def audit_records(records, candidate):
    if not isinstance(records, dict) or records.get('candidate_sha256') != candidate['sha256']:
        raise ValueError('Observation record must identify this exact candidate SHA-256')
    checks = records.get('checks', [])
    if not isinstance(checks, list):
        raise ValueError('checks must be a list')
    by_id = {}
    for item in checks:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in by_id:
            raise ValueError('Invalid or duplicate check record')
        if item.get('status') not in ('passed', 'failed', 'not_run', 'blocked'):
            raise ValueError('Invalid status for ' + item['id'])
        by_id[item['id']] = item
    pending, claimed = [], []
    for name in REQUIRED_CHECKS:
        item = by_id.get(name, {})
        valid = item.get('status') == 'passed' and isinstance(item.get('evidence'), list) and bool(item['evidence'])
        if valid:
            valid = all(isinstance(e, str) and bool(e.strip()) for e in item['evidence'])
        if name == 'playback_2h':
            seconds = item.get('duration_seconds')
            valid = valid and type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 7200
        (claimed if valid else pending).append(name)
    return dict(environment=records.get('environment', {}), observations=checks,
                evidence_status='human_records_not_independently_verified',
                required_checks_with_recorded_evidence=claimed, pending_or_incomplete=pending,
                published=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('records', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--verify-waydroid', action='store_true')
    parser.add_argument('--serial', choices=[WAYDROID_SERIAL])
    args = parser.parse_args()
    if args.verify_waydroid != bool(args.serial):
        parser.error('--verify-waydroid and --serial must be supplied together')
    report_path = args.report.resolve()
    if report_path in (args.candidate.resolve(), args.records.resolve()):
        parser.error('Report cannot overwrite candidate or records')
    if report_path == builder.REPO or builder.REPO in report_path.parents:
        parser.error('Report must be outside the publishing checkout')
    report = dict(published=False,
                  television_contacted=False, installed_bytes={'status': 'not_checked'})
    try:
        files, report['candidate'] = read_candidate(args.candidate)
        records = json.loads(args.records.read_text(encoding='utf-8'))
        report['gates'] = audit_records(records, report['candidate'])
        if args.verify_waydroid:
            report['installed_bytes'] = compare_installed(files, read_waydroid(args.serial))
            report['installed_bytes']['serial'] = WAYDROID_SERIAL
        report['status'] = 'report_complete'
        report['recorded_prerequisites_complete'] = (not report['gates']['pending_or_incomplete']
            and report['installed_bytes'].get('exact_packaged_files') is True)
        report['publication_state'] = ('recorded_checks_complete_no_publication_performed'
            if report['recorded_prerequisites_complete'] else 'not_publishable_checks_missing_or_failed')
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, tarfile.TarError,
            builder.IntegrityError, subprocess.SubprocessError) as error:
        report['status'] = 'validation_error'
        report['error'] = str(error)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(str(report_path))
    failed_bytes = report['installed_bytes'].get('exact_packaged_files') is False
    return 1 if report['status'] == 'validation_error' or failed_bytes else 0


if __name__ == '__main__':
    raise SystemExit(main())
