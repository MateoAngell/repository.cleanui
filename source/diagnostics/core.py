"""Private, read-only Kodi diagnostics. No outgoing HTTP or credential files."""
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from protocol import safe_log, snapshot_input, FILES

ADDON = 'script.cleanui.diagnostics'
ACTIVE = 'cleanui.diagnostics.owner'
STOP = 'cleanui.diagnostics.stop'
BEAT = 'cleanui.diagnostics.heartbeat'
LIMIT = 4 * 1024 * 1024  # Per segment: samples/log pairs <=16 MiB total.
SETTING_KEYS = (
    'audiooutput.channels', 'audiooutput.passthrough', 'audiooutput.ac3passthrough',
    'audiooutput.ac3transcode', 'audiooutput.eac3passthrough',
    'videoplayer.usedisplayasclock', 'videoplayer.adjustrefreshrate',
    'videoplayer.usemediacodec', 'videoplayer.usemediacodecsurface',
    'filecache.memorysize', 'filecache.readfactor', 'filecache.buffermode',
)
LABELS = (
    'System.CpuUsage', 'System.Memory(free)', 'System.Memory(used)',
    'System.Memory(total)', 'System.FPS', 'System.ScreenWidth', 'System.ScreenHeight',
    'Player.CacheLevel', 'Player.Progress', 'Player.Time', 'Player.Duration',
    'VideoPlayer.VideoCodec', 'VideoPlayer.VideoResolution', 'VideoPlayer.VideoAspect',
    'VideoPlayer.AudioCodec', 'VideoPlayer.AudioChannels', 'VideoPlayer.AudioLanguage',
    'VideoPlayer.VideoDecoder', 'VideoPlayer.DroppedFrames',
    'Network.LinkState', 'System.InternetState',
)


def folder():
    root = Path(xbmcvfs.translatePath(xbmcaddon.Addon(ADDON).getAddonInfo('profile')))
    root.mkdir(parents=True, exist_ok=True)
    return root


def rpc(method, params=None):
    try:
        result = json.loads(xbmc.executeJSONRPC(json.dumps(
            {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
        return result.get('result')
    except (ValueError, TypeError, RuntimeError):
        return None


def sanitize_line(line):
    """Fail closed: only component diagnostics, never arbitrary addon output."""
    return safe_log(line)




def snapshot(configuration=False):
    start = time.monotonic()
    values = {}
    for label in LABELS:
        raw = xbmc.getInfoLabel(label)
        # Only numeric/codec labels are requested. Reject URLs/unexpected text.
        values[label] = raw if raw and len(raw) < 100 and re.fullmatch(r'[\w .,%:/+()-]+', raw) and '://' not in raw else None
    owner = xbmcgui.Window(10000)
    ui = {}
    for addon in ('slyguy.max.cleanui', 'slyguy.disney.plus.cleanui'):
        raw = owner.getProperty('cleanui.resources.' + addon)
        try:
            data = json.loads(raw)
            stage = data.get('stage')
            ui[addon] = {'stage': stage if stage in ('window_open', 'window_closed', 'before_playback', 'after_playback') else None}
            ui[addon].update({key: data.get(key) if isinstance(data.get(key), (int, float)) else None
                             for key in ('windows', 'screens', 'cards', 'threads', 'cache', 'time')})
        except (ValueError, TypeError):
            ui[addon] = None
    result = {'time': time.time(), 'labels': values, 'cleanui': ui,
              'playing': bool(xbmc.getCondVisibility('Player.HasVideo')),
              'paused': bool(xbmc.getCondVisibility('Player.Paused')),
              'caching': bool(xbmc.getCondVisibility('Player.Caching'))}
    result['process'] = process_state()
    players = rpc('Player.GetActivePlayers') or []
    video = next((p for p in players if p.get('type') == 'video'), None)
    if video:
        result['player'] = rpc('Player.GetProperties', {'playerid': video['playerid'],
            'properties': ['speed', 'time', 'totaltime', 'percentage', 'cachepercentage']})
    if configuration:
        result['application'] = rpc('Application.GetProperties', {'properties': ['version']})
        result['system'] = {'android': xbmc.getCondVisibility('System.Platform.Android'),
                            'windows': xbmc.getCondVisibility('System.Platform.Windows')}
        result['components'] = {}
        for addon in ('slyguy.max.cleanui', 'slyguy.disney.plus.cleanui', 'script.module.slyguy', 'inputstream.adaptive', 'script.module.inputstreamhelper'):
            try:
                result['components'][addon] = xbmcaddon.Addon(addon).getAddonInfo('version')
            except RuntimeError:
                result['components'][addon] = None
        result['settings'] = {}
        for key in SETTING_KEYS:
            value = rpc('Settings.GetSettingValue', {'setting': key})
            result['settings'][key] = value.get('value') if isinstance(value, dict) else None
        result['advanced_cache'] = cache_settings()
        try:
            size = os.statvfs(str(folder()))
            result['storage'] = {'available_bytes': size.f_bavail * size.f_frsize,
                                 'total_bytes': size.f_blocks * size.f_frsize}
        except (OSError, AttributeError):
            result['storage'] = {}
        result['limitations'] = ['null significa no disponible',
            'CPU/memoria pueden ser del sistema, no del proceso Kodi',
            'sin medición de velocidad, señal Wi-Fi, temperatura ni procesos Android',
            'sin credenciales, títulos, direcciones de red ni archivos de cuenta']
    result['sample_ms'] = round((time.monotonic() - start) * 1000, 3)
    return result


def process_state():
    """Process measurements, not Android-wide memory mislabeled as Kodi."""
    result = {'cpu_seconds': time.process_time()}
    try:
        with open('/proc/self/status', 'r') as source:
            keys = {'VmRSS': 'rss_bytes', 'VmHWM': 'peak_rss_bytes',
                    'VmSize': 'virtual_bytes', 'Threads': 'threads'}
            for line in source:
                name, _, value = line.partition(':')
                if name in keys:
                    result[keys[name]] = int(value.strip().split()[0]) * (1 if name == 'Threads' else 1024)
    except (OSError, ValueError):
        if os.name == 'nt':
            try:
                import ctypes
                from ctypes import wintypes
                class Counters(ctypes.Structure):
                    _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [(k, ctypes.c_size_t) for k in
                        ('peak_rss', 'rss', 'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile')]
                counters = Counters()
                counters.cb = ctypes.sizeof(counters)
                kernel = ctypes.WinDLL('kernel32')
                kernel.GetCurrentProcess.restype = wintypes.HANDLE
                get_memory = ctypes.WinDLL('psapi').GetProcessMemoryInfo
                get_memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
                if get_memory(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                    result.update(rss_bytes=counters.rss, peak_rss_bytes=counters.peak_rss)
            except (OSError, AttributeError):
                pass
    return result


def cache_settings():
    result = {}
    path = Path(xbmcvfs.translatePath('special://profile/advancedsettings.xml'))
    if not path.exists() or path.stat().st_size > 1024 * 1024:
        return result
    try:
        root = ET.fromstring(path.read_bytes())
        for key in ('buffermode', 'memorysize', 'readfactor', 'cachemembuffersize'):
            value = root.findtext('./cache/' + key) or root.findtext('./network/' + key)
            if value and re.fullmatch(r'\d+(?:\.\d+)?', value.strip()):
                result[key] = value.strip()
    except (OSError, ET.ParseError):
        result['read_error'] = True
    return result


class Journal:
    def __init__(self, root, limit=LIMIT, name='samples'):
        self.path = root / (name + '.jsonl')
        self.previous = root / (name + '.previous.jsonl')
        self.limit = limit
        self.lock = threading.Lock()

    def metadata(self):
        import hashlib
        result = []
        for path in (self.path, self.previous):
            if path.exists() and path.stat().st_size:
                with path.open('rb') as source:
                    identity = hashlib.sha256(source.readline(16384)).hexdigest()
                result.append({'name': path.name, 'generation': identity, 'size': path.stat().st_size})
        return result

    def write(self, value):
        data = (json.dumps(value, ensure_ascii=True) + '\n').encode('utf-8')
        if len(data) > self.limit:
            return
        with self.lock:
            if self.path.exists() and self.path.stat().st_size + len(data) > self.limit:
                os.replace(str(self.path), str(self.previous))
            with self.path.open('ab') as stream:
                stream.write(data)


def log_extract(name):
    path = Path(xbmcvfs.translatePath('special://logpath/' + name))
    if not path.exists():
        return 'Registro no disponible.\n'
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 512 * 1024))
        tail = stream.read(512 * 1024).decode('utf-8', errors='replace')
    return ''.join(filter(None, (sanitize_line(line) for line in tail.splitlines()[1:])))


def report():
    root = folder()
    (root / 'state.json').write_text(json.dumps(snapshot_input(snapshot(True))), encoding='utf-8')
    result = root / 'latest-report.zip'
    temp = root / 'report.tmp.zip'
    with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES + ('session.json', 'state.json'):
            path = root / name
            if path.exists():
                with path.open('rb') as source:
                    offset = max(0, path.stat().st_size - 256 * 1024)
                    source.seek(offset)
                    if offset:
                        source.readline()
                    archive.writestr(name, source.read(256 * 1024))
        for name in ('kodi.log', 'kodi.old.log'):
            archive.writestr(name, log_extract(name))
        archive.writestr('LEEME.txt', 'Informe privado y saneado. Sin envío automático.\n'
            'Las muestras no disponibles son null. El informe no identifica por sí solo la causa.\n'
            'Sesiones interrumpidas: conservar el informe y anotar la hora del fallo.\n')
    os.replace(str(temp), str(result))
    return result


def recording():
    home = xbmcgui.Window(10000)
    try:
        return bool(home.getProperty(ACTIVE)) and time.time() - float(home.getProperty(BEAT)) < 30
    except ValueError:
        return False


def release(token):
    home = xbmcgui.Window(10000)
    if home.getProperty(ACTIVE) == token:
        for key in (ACTIVE, BEAT, STOP):
            home.clearProperty(key)


def record(token):
    home = xbmcgui.Window(10000)
    if home.getProperty(ACTIVE) != token:
        return
    root = folder()
    writer = Journal(root)
    monitor = xbmc.Monitor()
    session = {'started': time.time(), 'status': 'recording', 'interval_seconds': 5, 'maximum_seconds': 7200}
    (root / 'session.json').write_text(json.dumps(session), encoding='utf-8')
    writer.write({'event': 'start', 'snapshot': snapshot(True)})

    class Events(xbmc.Player):
        def event(self, name):
            writer.write({'time': time.time(), 'event': name})
        def onAVStarted(self): self.event('av_started')
        def onPlayBackStarted(self): self.event('started')
        def onPlayBackPaused(self): self.event('paused')
        def onPlayBackResumed(self): self.event('resumed')
        def onPlayBackStopped(self): self.event('stopped')
        def onPlayBackEnded(self): self.event('ended')
        def onPlayBackError(self): self.event('error')

    observer = Events()
    started = time.monotonic()
    try:
        while not monitor.abortRequested() and time.monotonic() - started < 7200:
            if home.getProperty(ACTIVE) != token or home.getProperty(STOP) == token:
                break
            home.setProperty(BEAT, str(time.time()))
            writer.write({'event': 'sample', 'snapshot': snapshot()})
            if monitor.waitForAbort(5):
                break
        session['status'] = 'interrupted' if monitor.abortRequested() else 'finished'
    except Exception:
        session['status'] = 'capture_error'
    finally:
        del observer
        session['finished'] = time.time()
        (root / 'session.json').write_text(json.dumps(session), encoding='utf-8')
        release(token)
        if not monitor.abortRequested():
            report()


def export():
    root = folder()
    config = root / 'export-target.json'
    try:
        target = json.loads(config.read_text(encoding='utf-8'))['folder']
    except (OSError, ValueError, KeyError):
        target = xbmcgui.Dialog().browse(0, 'Carpeta privada: laptop o USB', 'files')
    if not target:
        target = xbmcgui.Dialog().browse(0, 'Carpeta privada: laptop o USB', 'files')
    if not target:
        return
    if re.match(r'^[a-z]+://', target, re.I) and not target.lower().startswith(('smb://', 'nfs://', 'special://')):
        xbmcgui.Dialog().ok('Diagnóstico', 'Elige una carpeta local, USB o compartida; no un servicio web.')
        return
    source = report()
    name = 'cleanui-diagnostico-' + time.strftime('%Y%m%d-%H%M%S') + '.zip'
    destination = target.rstrip('/\\') + '/' + name
    if xbmcvfs.exists(destination) or not xbmcvfs.copy(str(source), destination):
        config.write_text(json.dumps({'folder': ''}), encoding='utf-8')
        xbmcgui.Dialog().ok('Diagnóstico', 'No se pudo copiar. El informe sigue guardado en Kodi.')
        return
    config.write_text(json.dumps({'folder': target}), encoding='utf-8')
    xbmcgui.Dialog().ok('Diagnóstico', 'Exportado: ' + name + '\nAdjunta ese ZIP en el chat; no lo publiques en GitHub.')
