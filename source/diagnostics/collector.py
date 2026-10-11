"""Private laptop collector. Device-scoped ADB reads; no Kodi imports/server."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time

from protocol import FILES, SCHEMA, clean_record, safe_log

REMOTE = '/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/script.cleanui.diagnostics'
CHUNK = 256 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_AGE = 14 * 86400


def atomic(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')
    os.replace(str(temporary), str(path))


def android_metrics(text):
    """Only counters from Kodi's meminfo and system memory; no full dumps."""
    result = {}
    for key, pattern in (
        ('pss_kib', r'TOTAL PSS:\s*(\d+)'),
        ('rss_kib', r'TOTAL RSS:\s*(\d+)'),
        ('swap_pss_kib', r'TOTAL SWAP PSS:\s*(\d+)'),
        ('available_kib', r'MemAvailable:\s*(\d+)'),
        ('total_kib', r'MemTotal:\s*(\d+)'),
        ('free_kib', r'MemFree:\s*(\d+)')):
        match = re.search(pattern, text)
        if match:
            result[key] = int(match.group(1))
    # Android versions before the App Summary RSS fields.
    if 'pss_kib' not in result:
        match = re.search(r'^\s*TOTAL\s+(\d+)\s+\d+', text, re.M)
        if match:
            result['pss_kib'] = int(match.group(1))
    return result


def exit_metrics(text):
    """ApplicationExitInfo numeric reasons only; descriptions contain PII."""
    results = []
    for block in re.split(r'ApplicationExitInfo #', text)[1:33]:
        item = {}
        for key in ('pid', 'reason', 'status', 'importance', 'pss', 'rss'):
            match = re.search(r'\b' + key + r'=\s*(\d+)', block)
            if match:
                item[key] = int(match.group(1))
        stamp = re.search(r'\btimestamp=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)', block)
        if stamp:
            item['timestamp'] = stamp.group(1)
        if item:
            results.append(item)
    return results


class Adb:
    def __init__(self, executable, guid):
        self.executable = str(Path(executable).resolve(strict=True))
        if not re.fullmatch(r'adb-[A-Za-z0-9_-]{8,100}', guid):
            raise ValueError('Invalid paired device')
        self.guid, self.serial = guid, None

    def command(self, args, maximum=CHUNK, device=True):
        if device and not self.serial:
            raise ConnectionError('Offline')
        command = [self.executable]
        if device:
            command += ['-s', self.serial]
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(command + args, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=15, creationflags=flags, check=False)
        if result.returncode or len(result.stdout) > maximum:
            raise ConnectionError('ADB read unavailable')
        return result.stdout

    def connect(self):
        # Never pick the first attached device, scan a subnet, or trust a new GUID.
        devices = self.command(['devices'], device=False).decode('utf-8', 'replace')
        for line in devices.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == 'device' and parts[0] == self.guid + '._adb-tls-connect._tcp':
                self.serial = parts[0]
                return
        services = self.command(['mdns', 'services'], device=False).decode('utf-8', 'replace')
        for line in services.splitlines():
            parts = line.split()
            if len(parts) != 3 or parts[:2] != [self.guid, '_adb-tls-connect._tcp']:
                continue
            match = re.fullmatch(r'([0-9.]+):(\d{1,5})', parts[2])
            if not match or not ipaddress.ip_address(match[1]).is_private or not 1 <= int(match[2]) <= 65535:
                continue
            self.command(['connect', parts[2]], device=False)
            self.serial = parts[2]
            self.command(['get-state'], maximum=64)
            return
        self.serial = None
        raise ConnectionError('Paired Chromecast offline')

    def read(self, name, offset=0):
        if name not in FILES + ('transfer.json',):
            raise ValueError('Unapproved file')
        if not isinstance(offset, int) or not 0 <= offset <= 4 * 1024 * 1024:
            raise ValueError('Invalid offset')
        path = REMOTE + '/' + name
        return self.command(['exec-out', 'sh', '-c',
            'tail -c +{} {} | head -c {}'.format(offset + 1, path, CHUNK)])

    def generation(self, name):
        if name not in FILES:
            raise ValueError('Unapproved file')
        raw = self.command(['exec-out', 'sh', '-c',
            'head -n 1 {} | head -c 16384'.format(REMOTE + '/' + name)], maximum=16384)
        return hashlib.sha256(raw).hexdigest()


class Collector:
    def __init__(self, config, output):
        self.config = Path(config)
        self.root = Path(output).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / 'collector-state.json'
        try:
            self.state = json.loads(self.state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault('offsets', {})
        self.last_exit = 0
        self.android_cursor = time.strftime('%m-%d %H:%M:%S.000')
        self.status = None

    def append(self, value, category='kodi'):
        path = self.root / ('{}-{}.jsonl'.format(category, time.strftime('%Y%m%d')))
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + '\n')

    def transition(self, status):
        if status != self.status:
            self.append(dict(time=time.time(), event=status), 'collector')
            self.status = status
        self.state.update(status=status, heartbeat=time.time())

    def ingest(self, name, generation, raw):
        key = generation
        offset = self.state['offsets'].get(key, 0)
        consumed = 0
        for line in raw.splitlines(keepends=True):
            if not line.endswith(b'\n'):
                break
            consumed += len(line)
            if len(line) > 16384:
                continue
            try:
                value = clean_record(json.loads(line))
                if value:
                    self.append(value)
            except (ValueError, TypeError, OverflowError):
                continue
        self.state['offsets'][key] = offset + consumed
        return consumed

    def sync(self, adb, transfer):
        if not isinstance(transfer, dict) or transfer.get('schema') != SCHEMA:
            raise ValueError('Unsupported recorder')
        if not isinstance(transfer.get('capture_enabled'), bool):
            raise ValueError('Missing capture consent')
        if not transfer['capture_enabled']:
            self.transition('disabled')
            return False
        files = transfer.get('files', [])
        if not isinstance(files, list) or len(files) > 4:
            raise ValueError('Invalid files')
        generations = set()
        for item in files:
            if not isinstance(item, dict):
                continue
            name, generation, size = item.get('name'), item.get('generation'), item.get('size')
            if name not in FILES or not isinstance(generation, str) or not re.fullmatch('[a-f0-9]{64}', generation):
                continue
            if not isinstance(size, int) or not 0 <= size <= 4 * 1024 * 1024:
                continue
            generations.add(generation)
            offset = self.state['offsets'].get(generation, 0)
            if offset >= size:
                continue
            # Rotation during transfer must never attach bytes to the wrong offset.
            if adb.generation(name) != generation:
                continue
            raw = adb.read(name, offset)
            if adb.generation(name) == generation:
                self.ingest(name, generation, raw)
        self.state['offsets'] = {k: v for k, v in self.state['offsets'].items() if k in generations}
        self.transition('collecting')
        return True

    def prune(self):
        # Only our dated journals. Never recurse or follow links into other files.
        files = [p for p in self.root.iterdir() if p.is_file() and not p.is_symlink() and
                 re.fullmatch(r'(?:kodi|android|collector)-\d{8}\.jsonl', p.name)]
        files.sort(key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        now = time.time()
        for path in files:
            size = path.stat()
            if now - size.st_mtime > MAX_AGE or total > MAX_TOTAL:
                total -= size.st_size
                path.unlink()

    def android(self, adb):
        try:
            pid = adb.command(['shell', 'pidof', 'org.xbmc.kodi'], maximum=128).decode().strip()
        except ConnectionError:
            pid = ''
        pids = pid.split()
        valid = bool(pids) and all(re.fullmatch(r'\d{1,8}', x) for x in pids)
        result = dict(time=time.time(), event='android_sample', kodi_running=valid)
        memory = adb.command(['exec-out', 'sh', '-c',
            'cat /proc/meminfo | head -n 8; dumpsys meminfo org.xbmc.kodi | head -c 32768'], maximum=65536)
        result['memory'] = android_metrics(memory.decode('utf-8', 'replace'))
        if valid:
            # Numeric proc counters only. No cmdlines or environment/credentials.
            try:
                text = adb.command(['shell', 'cat', '/proc/' + pids[0] + '/stat'], maximum=8192).decode('utf-8', 'replace')
            except ConnectionError:
                text = ''
            fields = text[text.rfind(')') + 2:].split()
            if len(fields) >= 22:
                result['process'] = {k: int(fields[i]) for k, i in
                    (('user_ticks', 11), ('system_ticks', 12), ('threads', 17), ('rss_pages', 21), ('virtual_bytes', 20))
                    if fields[i].isdigit()}
        self.append(result, 'android')
        if valid:
            try:
                raw = adb.command(['logcat', '-d', '-v', 'threadtime', '--pid=' + pids[0],
                                   '-T', self.android_cursor, '-t', '1000'], maximum=CHUNK)
            except ConnectionError:
                raw = b''
            for line in raw.decode('utf-8', 'replace').splitlines():
                safe = safe_log(line)
                if safe:
                    self.append(dict(time=time.time(), event='android_log', log=safe.strip()), 'android')
        self.android_cursor = time.strftime('%m-%d %H:%M:%S.000')
        if time.monotonic() - self.last_exit >= 300:
            raw = adb.command(['shell', 'dumpsys', 'activity', 'exit-info', 'org.xbmc.kodi'], maximum=CHUNK)
            exits = exit_metrics(raw.decode('utf-8', 'replace'))
            digest = hashlib.sha256(json.dumps(exits, sort_keys=True).encode()).hexdigest()
            if exits and self.state.get('exit_digest') != digest:
                self.append(dict(time=time.time(), event='exit_info', exits=exits), 'android')
                self.state['exit_digest'] = digest
            self.last_exit = time.monotonic()

    def once(self):
        try:
            config = json.loads(self.config.read_text(encoding='utf-8'))
            if not config.get('enabled', False):
                self.transition('disabled')
                return
            adb = Adb(config['adb'], config['paired_guid'])
            adb.connect()
            # Pin hardware identity privately on first available authorized connection.
            serial = adb.command(['shell', 'getprop', 'ro.serialno'], maximum=256).strip()
            if not serial:
                raise ConnectionError('Identity unavailable')
            identity = hashlib.sha256(serial).hexdigest()
            if config.get('identity') and config['identity'] != identity:
                self.transition('identity_mismatch')
                return
            if not config.get('identity'):
                config['identity'] = identity
                atomic(self.config, config)
            try:
                transfer = json.loads(adb.read('transfer.json'))
            except ValueError:
                self.transition('recorder_not_installed')
                return
            if self.sync(adb, transfer):
                try:
                    self.android(adb)
                except (OSError, ValueError, ConnectionError, subprocess.TimeoutExpired):
                    self.append(dict(time=time.time(), event='android_read_unavailable'), 'collector')
        except (OSError, ValueError, KeyError, ConnectionError, subprocess.TimeoutExpired):
            self.transition('offline')
        finally:
            self.prune()
            atomic(self.state_path, self.state)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    collector = Collector(args.config, args.output)
    lock = collector.root / 'collector.lock'
    # Kernel-held file lock: released even after power loss, without stale PID guesses.
    with lock.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if lock.stat().st_size == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return
        while True:
            try:
                collector.once()
            except OSError:
                # Disk unavailable/full: never loop tightly or retain raw output.
                pass
            if args.once:
                break
            time.sleep(60)


if __name__ == '__main__':
    main()
