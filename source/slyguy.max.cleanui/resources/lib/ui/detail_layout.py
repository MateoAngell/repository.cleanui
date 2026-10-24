"""Display-only formatting for the TV entity header."""


def metadata(info):
    pieces = [str(info['mpaa'])] if info.get('mpaa') else []
    try:
        minutes = max(0, int(info.get('duration') or 0) // 60)
    except (ValueError, TypeError):
        minutes = 0
    if minutes:
        hours, remainder = divmod(minutes, 60)
        pieces.append('{}h {}m'.format(hours, remainder) if hours else '{}m'.format(minutes))
    if info.get('year'):
        pieces.append(str(info['year']))
    return '  '.join(pieces)
