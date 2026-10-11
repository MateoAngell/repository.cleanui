"""Shared, fail-closed wire format. Never accepts arbitrary log messages."""
import math
import re

SCHEMA = 1
ADDONS = ('slyguy.max.cleanui', 'slyguy.disney.plus.cleanui')
EVENTS = frozenset(('start', 'sample', 'configuration', 'recovered', 'finished',
    'capture_error', 'log', 'log_gap', 'queue_gap', 'session_start', 'session_end',
    'launch_rejected', 'origin_restored', 'intro_start', 'intro_end', 'profiles_ready',
    'profile_selected', 'window_open', 'window_closed', 'load_start', 'load_end',
    'load_error', 'ui_error', 'activation', 'click', 'directions', 'playback_request',
    'before_playback', 'after_playback', 'restore', 'started', 'av_started',
    'paused', 'resumed', 'stopped', 'ended', 'error'))
SCREENS = frozenset(('home', 'movies', 'series', 'collection', 'detail', 'movie',
    'show', 'season', 'episodes', 'search', 'watchlist', 'continue', 'hbo', 'kids',
    'profiles', 'unknown'))
NUMBERS = frozenset(('elapsed_ms', 'request_id', 'windows', 'screens', 'cards',
    'threads', 'cache', 'pending', 'count', 'control', 'position', 'rail', 'page', 'time'))
LABELS = frozenset(('System.CpuUsage', 'System.Memory(free)', 'System.Memory(used)',
    'System.Memory(total)', 'System.FPS', 'System.ScreenWidth', 'System.ScreenHeight',
    'Player.CacheLevel', 'Player.Progress', 'Player.Time', 'Player.Duration',
    'VideoPlayer.VideoCodec', 'VideoPlayer.VideoResolution', 'VideoPlayer.VideoAspect',
    'VideoPlayer.AudioCodec', 'VideoPlayer.AudioChannels', 'VideoPlayer.AudioLanguage',
    'VideoPlayer.VideoDecoder', 'VideoPlayer.DroppedFrames', 'Network.LinkState',
    'System.InternetState'))
SETTINGS = frozenset(('audiooutput.channels', 'audiooutput.passthrough',
    'audiooutput.ac3passthrough', 'audiooutput.ac3transcode', 'audiooutput.eac3passthrough',
    'videoplayer.usedisplayasclock', 'videoplayer.adjustrefreshrate',
    'videoplayer.usemediacodec', 'videoplayer.usemediacodecsurface',
    'filecache.memorysize', 'filecache.readfactor', 'filecache.buffermode'))
FILES = ('samples.jsonl', 'samples.previous.jsonl', 'kodi.jsonl', 'kodi.previous.jsonl')
COMPONENT = re.compile(r'\[CLEANUI\](?:\[RESOURCES\])?|CVideoPlayer|VideoPlayer::?|CDVD\w*|ffmpeg|CActiveAE|CMMAL|CCodec|CRender|mediacodec|CPythonInvoker|CServiceAddonManager|CApplication\w*|CWinSystemAndroid|CAndroid\w*', re.I)
SENSITIVE = re.compile(r'authorization|cookie|password|passwd|secret|token|license|licence|pssh|\bdrm\b|profile|userdata|email', re.I)


def safe_log(line):
    if not isinstance(line, str) or len(line) > 2000 or SENSITIVE.search(line):
        return None
    component = COMPONENT.search(line)
    if not component:
        if not re.search(r'\b(?:controller|entry|playback|intro|home_window|detail_window|service|core)\.py\b|^(?:RuntimeError|TypeError|ValueError|NameError|AttributeError|KeyError|MemoryError|ImportError|ModuleNotFoundError|OSError):', line):
            return None
        component = COMPONENT.search('CPythonInvoker')
    stamp = re.match(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?', line)
    prefix = stamp.group(0) + ' ' if stamp else ''
    if '[CLEANUI][RESOURCES]' in line:
        m = re.search(r'(window_open|window_closed|before_playback|after_playback) windows=\d+ screens=\d+ cards=\d+ threads=\d+ cache=\d+', line)
        return prefix + '[CLEANUI][RESOURCES] ' + m.group(0) + '\n' if m else None
    signals = re.findall(r'\b(?:error|warning|buffer|buffering|underrun|timeout|timed out|failed|failure|decoder|dropped|stalled|stopped|paused|resumed|eac3|ac3|aac|h264|hevc|vp9|av1|shutdown|closing|waiting|abort|aborted|killed|unresponsive|Exception|RuntimeError|TypeError|ValueError|NameError|AttributeError|KeyError|MemoryError|ImportError|ModuleNotFoundError|OSError|Traceback)\b', line, re.I)
    codes = re.findall(r'\b(?:errno|status|code)\s*[:=]\s*-?\d{1,6}\b', line, re.I)
    frames = re.findall(r'\b(?:controller|entry|playback|intro|repository|home_window|detail_window|default|service|core|api)\.py\b(?:[\",: ]+line\s+\d{1,6})?', line)
    if not signals and not codes and not frames:
        return None
    return prefix + component.group(0) + ' ' + ' '.join(dict.fromkeys(s.lower() for s in signals)) + ' ' + ' '.join(codes + frames) + '\n'


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and abs(value) < 10**15 and math.isfinite(value) else None


def mapping(value):
    return value if isinstance(value, dict) else {}


def member(value, options):
    return isinstance(value, str) and value in options


def fields(data):
    if not isinstance(data, dict):
        return {}
    clean = {k: number(v) for k, v in data.items() if k in NUMBERS}
    if member(data.get('screen'), SCREENS):
        clean['screen'] = data['screen']
    if isinstance(data.get('cancelled'), bool):
        clean['cancelled'] = data['cancelled']
    return clean


def event_input(data):
    if not isinstance(data, dict) or not member(data.get('addon'), ADDONS) or not member(data.get('event'), EVENTS):
        return None
    result = {'addon': data['addon'], 'event': data['event'], 'data': fields(data.get('data'))}
    if re.fullmatch(r'[a-f0-9]{32}', str(data.get('session', ''))):
        result['session'] = data['session']
    return result


def snapshot_input(data):
    if not isinstance(data, dict):
        return {}
    out = {'time': number(data.get('time')), 'sample_ms': number(data.get('sample_ms'))}
    for key in ('playing', 'paused', 'caching'):
        out[key] = data.get(key) if isinstance(data.get(key), bool) else None
    out['labels'] = {}
    for key, val in mapping(data.get('labels')).items():
        if key not in LABELS:
            continue
        # Numeric labels, ISO language and known codec/decoder families only.
        good = val is None or (isinstance(val, str) and len(val) < 100 and
            re.fullmatch(r'(?:[0-9 .,%:/+()-]+(?:\s*(?:MB|GB|KB|MiB|GiB|KiB|fps|Hz))?|'
                         r'(?:ffmpeg|h264|hevc|vp9|av1|mpeg|aac|eac3|ac3|dca|dts|opus|mediacodec|d3d11|dxva)[\w .+()-]*|'
                         r'[a-z]{2,3}(?:-[A-Z0-9]{2,3})?|Connected|Disconnected|Yes|No)', val, re.I))
        out['labels'][key] = val if good else None
    out['cleanui'] = {}
    for addon, state in mapping(data.get('cleanui')).items():
        if addon in ADDONS:
            out['cleanui'][addon] = fields(state)
            if isinstance(state, dict) and member(state.get('stage'), EVENTS):
                out['cleanui'][addon]['stage'] = state['stage']
    for key in ('process', 'storage', 'settings', 'advanced_cache'):
        values = data.get(key)
        if isinstance(values, dict):
            allowed = SETTINGS if key == 'settings' else {
                'rss_bytes', 'peak_rss_bytes', 'virtual_bytes', 'threads', 'cpu_seconds',
                'cpu_percent', 'available_bytes', 'total_bytes', 'buffermode',
                'memorysize', 'readfactor', 'cachemembuffersize'}
            out[key] = {k: v if isinstance(v, bool) else number(float(v)) if isinstance(v, str) and re.fullmatch(r'\d+(?:\.\d+)?', v) else number(v)
                        for k, v in values.items() if k in allowed}
    if isinstance(data.get('system'), dict):
        out['system'] = {k: v for k, v in data['system'].items() if k in ('android', 'windows') and isinstance(v, bool)}
    if isinstance(data.get('components'), dict):
        out['components'] = {k: v if isinstance(v, str) and re.fullmatch(r'[0-9][0-9A-Za-z.+_-]{0,40}', v) else None
            for k, v in data['components'].items() if k in ADDONS + ('script.cleanui.diagnostics', 'script.module.slyguy', 'inputstream.adaptive', 'script.module.inputstreamhelper')}
    version = (data.get('application') or {}).get('version') if isinstance(data.get('application'), dict) else None
    if isinstance(version, dict):
        out['application'] = {'version': {k: number(v) for k, v in version.items() if k in ('major', 'minor', 'revision')}}
    player = data.get('player')
    if isinstance(player, dict):
        out['player'] = {k: number(v) for k, v in player.items() if k in ('speed', 'percentage', 'cachepercentage')}
        for key in ('time', 'totaltime'):
            if isinstance(player.get(key), dict):
                out['player'][key] = {k: number(v) for k, v in player[key].items() if k in ('hours', 'minutes', 'seconds', 'milliseconds')}
    return out


def clean_record(value):
    if not isinstance(value, dict) or value.get('schema') != SCHEMA or not member(value.get('event'), EVENTS):
        return None
    if not re.fullmatch(r'[a-f0-9]{32}', str(value.get('boot', ''))):
        return None
    out = {k: value[k] for k in ('schema', 'boot', 'event')}
    out.update(time=number(value.get('time')), seq=number(value.get('seq')))
    incoming = event_input(value)
    if incoming:
        out.update(incoming)
    else:
        out['data'] = fields(value.get('data'))
    if 'snapshot' in value:
        out['snapshot'] = snapshot_input(value['snapshot'])
    if value['event'] == 'log':
        # Already structured by the device sanitizer. Validate again on laptop.
        log = value.get('log')
        log = safe_log(log)
        if log:
            out['log'] = log.strip()
    return out
