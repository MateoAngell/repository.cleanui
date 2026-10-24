from . import constants as C


class Card(object):
    """A visual card representing content in the UI."""

    MOVIE = C.KIND_MOVIE
    SHOW = C.KIND_SHOW
    SEASON = C.KIND_SEASON
    EPISODE = C.KIND_EPISODE
    COLLECTION = C.KIND_COLLECTION
    VIDEO = C.KIND_VIDEO

    def __init__(
        self,
        label='',
        kind=C.KIND_VIDEO,
        art=None,
        info=None,
        open_path='',
        play_path='',
        trailer_path='',
        context=None,
        source_item=None,
        deeplink_id='',
        show_id='',
        season_id='',
        browse_id='',
        browse_ref='',
        navigation=None,
        action_role='',
    ):
        self.label = label or ''
        self.kind = kind
        self.art = art or {}
        self.info = info or {}
        self.open_path = open_path or ''
        self.play_path = play_path or ''
        self.trailer_path = trailer_path or ''
        self.context = context or []
        self.source_item = source_item
        # Direct IDs for navigation (no URL re-parsing needed)
        self.deeplink_id = (deeplink_id or '').replace('entity-', '')
        self.show_id = show_id or ''
        self.season_id = season_id or ''
        self.browse_id = browse_id or ''
        self.browse_ref = browse_ref or ''
        self.navigation = navigation
        self.action_role = action_role

    def __repr__(self):
        return '<Card kind={} label={!r}>'.format(self.kind, self.label)


class Rail(object):
    """A horizontal rail of cards shown on a screen."""

    POSTER = C.STYLE_POSTER
    LANDSCAPE = C.STYLE_LANDSCAPE
    EPISODE = C.STYLE_EPISODE
    SEASON = C.STYLE_SEASON
    BUTTON = C.STYLE_BUTTON
    BRAND = C.STYLE_BRAND

    def __init__(self, title='', items=None, style=C.STYLE_POSTER, rail_id='', continuation=None):
        self.title = title or ''
        self.items = items or []
        self.style = style
        self.rail_id = rail_id
        self.continuation = continuation

    def __repr__(self):
        return '<Rail title={!r} items={}>'.format(self.title, len(self.items))


class Screen(object):
    """A full screen layout with hero element and rails."""

    HOME = C.SCREEN_HOME
    MOVIE = C.SCREEN_MOVIE
    SHOW = C.SCREEN_SHOW
    SEASON = C.SCREEN_SEASON
    COLLECTION = C.SCREEN_COLLECTION
    SEARCH = C.SCREEN_SEARCH

    def __init__(self, screen_type, title='', hero=None, rails=None, screen_kind='',
                 layout='rails', featured=None, filters=None, continuation=None):
        self.screen_type = screen_type
        self.screen_kind = screen_kind or screen_type
        self.title = title or ''
        self.hero = hero
        self.rails = rails or []
        self.layout = layout
        self.featured = featured or []
        self.filters = filters or []
        self.continuation = continuation

    def __repr__(self):
        return '<Screen type={} rails={}>'.format(self.screen_type, len(self.rails))

