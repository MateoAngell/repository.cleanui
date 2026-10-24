"""My Stuff presentation using only existing service Screen/Card models."""
from .adapter import UIAdapter
from . import constants as C

RESULTS = 4520
MY_LIST, CONTINUE = 7600, 7601
KINDS = ('watchlist', 'continue_watching')


def has_cards(screen):
    return bool(screen is not None and any(getattr(card, 'kind', '') != 'page'
        for rail in getattr(screen, 'rails', []) for card in rail.items))


class StuffView:
    def __init__(self, window):
        self.window = window

    def continuation(self):
        screen = self.window.screen
        if self.window.screen_kind == 'continue_watching' and has_cards(screen):
            return screen
        candidate = getattr(screen, '_cleanui_continue_screen', None)
        return candidate if has_cards(candidate) else None

    def present(self):
        window = self.window
        continuing = window.screen_kind == 'continue_watching'
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
            item.setProperty('cleanui.stuff_meta', str(info['year']) if info.get('year') else '')
            items.append(item)
        control.addItems(items)
        window._cards[RESULTS] = cards
        available = self.continuation() is not None
        window.setProperty('cleanui.stuff.continue_available', 'true' if available else 'false')
        window.getControl(CONTINUE).setVisibleCondition('true' if available else 'false')
        window.setProperty('cleanui.stuff.tab', 'continue_watching' if continuing else 'watchlist')
        window.setProperty('cleanui.stuff.empty', 'true' if not cards else 'false')
        window.setProperty('cleanui.stuff.empty_message',
            'Continuar viendo no está disponible en este complemento.' if continuing and not cards else
            'No hay títulos disponibles en Mi lista.' if not cards else '')

    def activate(self, cid):
        if cid not in (MY_LIST, CONTINUE):
            return False
        window = self.window
        if cid == MY_LIST:
            if window.screen_kind == 'watchlist':
                return True
            window.controller.cancel_navigation(window)
            saved = getattr(window.screen, '_cleanui_watchlist_screen', None)
            if saved is not None:
                window.replace_screen(saved, 'watchlist')
            else:
                window.controller.open_watchlist(window)
            return True
        continuation = self.continuation()
        if continuation is not None and window.screen_kind != 'continue_watching':
            window.controller.cancel_navigation(window)
            previous = window.screen
            continuation._cleanui_watchlist_screen = previous
            window.replace_screen(continuation, 'continue_watching')
        return True
