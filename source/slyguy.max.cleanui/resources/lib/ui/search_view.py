"""TV search presentation over the existing repository and metadata worker.

No extra thread, endpoint, account state or media resolver is introduced.
Pending queries replace each other in NavigationLoader's single queued slot.
"""
from .adapter import UIAdapter
from . import constants as C

KEYS = 'abcdefghijklmnñopqrstuvwxyz1234567890'
KEY_FIRST = 8000
DELETE, SPACE, CLEAR = 8100, 8101, 8102
RESULTS = 4510
MAX_QUERY = 80


class SearchView:
    def __init__(self, window):
        self.window = window

    @property
    def query(self):
        return getattr(self.window.screen, '_cleanui_search_query', '')

    def present(self):
        window = self.window
        query = self.query
        window.setProperty('cleanui.search.query', query)
        window.setProperty('cleanui.search.prompt', query or 'Encuentra películas, series y más')
        cards = [card for rail in window.screen.rails for card in rail.items]
        control = window.getControl(RESULTS)
        control.reset()
        items = []
        for card in cards:
            item = UIAdapter.to_list_item(card, C.STYLE_LANDSCAPE)
            art = card.art or {}
            item.setProperty('cleanui.display_art', art.get('fanart') or art.get('banner') or
                             art.get('thumb') or art.get('poster') or '')
            info = card.info or {}
            item.setProperty('cleanui.search_meta', '  '.join(str(info[key]) for key in
                             ('year', 'mpaa') if info.get(key)))
            items.append(item)
        control.addItems(items)
        window._cards[RESULTS] = cards
        window.setProperty('cleanui.search.empty', 'true' if not cards else 'false')
        window.setProperty('cleanui.search.hint',
            'Escribe el título que quieres encontrar' if not query else
            'No se encontraron resultados' if not cards else '')

    def activate(self, cid):
        old = self.query
        if KEY_FIRST <= cid < KEY_FIRST + len(KEYS):
            query = (old + KEYS[cid - KEY_FIRST])[:MAX_QUERY]
        elif cid == DELETE:
            query = old[:-1]
        elif cid == SPACE:
            query = (old + ' ')[:MAX_QUERY] if old and not old.endswith(' ') else old
        elif cid == CLEAR:
            query = ''
        else:
            return False
        if old == query:
            return True
        window = self.window
        window.controller.cancel_navigation(window)
        window.screen._cleanui_search_query = query
        window.screen.rails = []
        self.present()
        if query.strip():
            window.setProperty('cleanui.search.hint', '')
            window.controller.load_navigation(window,
                lambda: window.controller.repository.build_search(query.strip()),
                lambda result: self.apply(query, result))
        return True

    def apply(self, query, screen):
        window = self.window
        # NavigationLoader already rejects superseded jobs. Keep a local
        # identity check too, so a cancelled search never changes a later page.
        if window.screen_kind != 'search' or self.query != query:
            return False
        if screen is None:
            return False
        screen.screen_kind = 'search'
        screen._cleanui_search_query = query
        window.screen = screen
        self.present()
        window._configure_navigation()
        return True
