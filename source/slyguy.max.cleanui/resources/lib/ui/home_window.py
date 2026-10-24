"""Catalogue windows; session and playback remain owned by the existing controller."""
import traceback
import uuid
import xbmc
import xbmcgui
from slyguy import userdata
from . import constants as C, effects
from .adapter import UIAdapter
from .models import Card, Screen

class HomeWindow(xbmcgui.WindowXMLDialog):
    PLATFORM = 'max'

    def __init__(self, *args, **kwargs):
        self.controller = kwargs.pop('controller', None)
        self.screen = kwargs.pop('screen', None)
        self.screen_kind = kwargs.pop('screen_kind', 'home')
        self._initial_loader = kwargs.pop('initial_loader', None)
        super(HomeWindow, self).__init__(*args, **kwargs)
        self._cards, self._body = {}, []
        self._navigation_owner = uuid.uuid4().hex
        self._pending_visual_navigation = None
        self._activating = False
        self._last_focus_key = self._last_activation = None
        self._gallery_alarm = 'cleanui_max_gallery'
        self._content_focus = 4600
        self._sidebar = [3003,3012,3011,3015]
        self._menu_cards = []
        self._history=list(getattr(self.screen,'_cleanui_history',[]))
        if self.screen is not None and hasattr(self.screen,'_cleanui_history'):
            del self.screen._cleanui_history
        if not self.controller._windows:
            self.controller._home_stack=self._history

    def onInit(self):
        self._window_id = xbmcgui.getCurrentWindowDialogId()
        try:
            effects.prepare(self)
            initial = self.screen is None and self._initial_loader
            if initial:
                self.screen = Screen(Screen.HOME,title='', rails=[])
            self._populate()
            if not self._restore_state():
                self._focus_first()
            if initial:
                self.controller.load_navigation(self, self._initial_loader,
                    lambda screen: self.replace_screen(screen, 'home'))
        except Exception:
            self._log_error('onInit')
            self.controller.end_transition()
            self.close()

    def _log_error(self, context):
        xbmc.log('[CLEANUI] {}: {}'.format(context, traceback.format_exc()), xbmc.LOGERROR)

    def _control_ids(self):
        return [3100, 4500, 4510, 4520, 4600] + [base+i for base in (4000,4200,4400) for i in range(8)]

    def _rail_control_id(self, index):
        style = UIAdapter._effective_rail_style(self.screen.rails[index], self.screen_kind)
        return (4400 if style == C.STYLE_BRAND else 4200 if style in
                (C.STYLE_LANDSCAPE,C.STYLE_EPISODE) else 4000) + index

    def _items(self, cid, cards, style):
        control = self.getControl(cid)
        control.reset()
        items, accepted = [], []
        for card in cards:
            try:
                items.append(UIAdapter.to_list_item(card, style))
                accepted.append(card)
            except Exception:
                self._log_error('card')
        control.addItems(items)
        self._cards[cid] = accepted

    def _populate(self):
        self._binding=True
        self.getControl(5000).setVisibleCondition('false')
        self.getControl(5000).setAnimations([])
        try:
            self._bind_content()
        finally:
            self.getControl(5000).setVisibleCondition('false' if self.screen_kind in ('search','watchlist','continue_watching') else 'true')
            self._binding=False

    def _bind_content(self):
        self._cards.clear()
        for cid in self._control_ids():
            self.getControl(cid).reset()
        self.getControl(5800).setVisibleCondition('true' if self.screen_kind == 'search' else 'false')
        self.getControl(5810).setVisibleCondition('true' if self.screen_kind in ('watchlist','continue_watching') else 'false')
        profile = userdata.get('profile') or {}
        avatar = userdata.get('avatar','') if self.PLATFORM == 'disney' else profile.get('avatar','')
        name = profile if self.PLATFORM == 'disney' else profile.get('name','')
        values = {'screen.kind':self.screen_kind,'screen.title':self.screen.title,
                  'profile.avatar':avatar or '', 'profile.name':str(name or '')}
        if self.screen_kind == 'search':
            for key, value in values.items():
                self.setProperty('cleanui.' + key, value)
            from .search_view import SearchView
            self._search_view = SearchView(self)
            self._search_view.present()
            self._prepare_sidebar()
            self._configure_navigation()
            return
        if self.screen_kind in ('watchlist','continue_watching'):
            for key, value in values.items():
                self.setProperty('cleanui.' + key, value)
            from .stuff_view import StuffView
            self._stuff_view = StuffView(self)
            self._stuff_view.present()
            self._prepare_sidebar()
            self._configure_navigation()
            self._row_offsets = {4520:0,7600:0,7601:0}
            self._scroll_offset = 0
            return
        layout = getattr(self.screen,'layout','rails')
        if self.screen_kind in ('watchlist','search','episodes'):
            layout = 'grid'
        featured, filters = self.screen.featured, self.screen.filters
        self.setProperty('cleanui.featured.count',str(len(featured)))
        for i in range(20):
            x=960-(len(featured)-1)*20-6+i*40
            self.getControl(4800+i).setPosition(x,908)
            self.getControl(4850+i).setPosition(x,908)
        values.update({'catalogue.layout':layout,'featured.visible':'true' if featured else 'false',
                       'filters.visible':'true' if filters else 'false',
                       'page.more':'true' if self.screen.continuation else 'false',
                       'catalogue.empty':'true' if not self.screen.rails and not featured else 'false'})
        for key,value in values.items():
            self.setProperty('cleanui.'+key,value)
        self._items(4600,featured,C.STYLE_LANDSCAPE)
        self._items(3100,filters,C.STYLE_BUTTON)
        for i in range(8):
            for key,value in (('visible','false'),('style',''),('title','')):
                self.setProperty('cleanui.home.rail{}.{}'.format(i,key),value)
        if layout == 'grid':
            self._items(4500,[c for r in self.screen.rails for c in r.items],
                        C.STYLE_EPISODE if self.screen_kind == 'episodes' else
                        C.STYLE_POSTER if self.PLATFORM=='max' else C.STYLE_LANDSCAPE)
        else:
            for i,rail in enumerate(self.screen.rails[:8]):
                cards = list(rail.items)
                cid = self._rail_control_id(i)
                self._items(cid,cards,UIAdapter._effective_rail_style(rail,self.screen_kind))
                self.setProperty('cleanui.home.rail{}.visible'.format(i),'true' if cards else 'false')
                self.setProperty('cleanui.home.rail{}.style'.format(i),
                                 'brand' if cid>=4400 else 'landscape' if cid>=4200 else 'poster')
                self.setProperty('cleanui.home.rail{}.title'.format(i),rail.title)
        self._prepare_sidebar()
        self._configure_navigation()
        self._layout_content()
        self._featured_actions()

    def _prepare_sidebar(self):
        self._menu_cards=list(getattr(self.screen,'menu_entries',None)
                              or getattr(self,'_menu_cards',[]))[:8]
        self._sidebar=[3003,3012,3011]+[3300+i for i in range(len(self._menu_cards))]+[3015]
        self.setProperty('cleanui.nav.count',str(len(self._menu_cards)))
        for i,card in enumerate(self._menu_cards):
            route=str((card.navigation or {}).get('id','')).lower()
            icon=('home' if route=='home' else 'series' if 'series' in route else
                  'movies' if 'movie' in route else 'hbo' if 'hbo' in card.label.lower()
                  else 'kids' if any(s in card.label.lower() for s in ('niños','kids','familia')) else 'categories')
            self.setProperty('cleanui.nav.{}.title'.format(i),card.label)
            self.setProperty('cleanui.nav.{}.icon_key'.format(i),icon)
            self.setProperty('cleanui.nav.{}.icon'.format(i),
                self.controller.addon_path.rstrip('/\\')+'/resources/skins/Default/media/max-nav-'+icon+'.png')
        self.getControl(3012).setPosition(26,114)
        active = 3011 if self.screen_kind == 'search' else 3012 if self.screen_kind in ('watchlist','continue_watching') else 0
        for i, card in enumerate(self._menu_cards):
            if (card.navigation or {}).get('id') == self.screen_kind or card.label == self.screen.title:
                active = 3300 + i
                break
        self.setProperty('cleanui.nav.active', str(active))
        self.setProperty('cleanui.nav.open','false')

    def _layout_content(self):
        y=934 if self.screen.featured else 0
        self._row_offsets={4600:0,7300:0,7301:0,3100:0}
        if self.screen_kind!='home':
            self.getControl(5102).setPosition(0,y)
            y+=190
        if self.screen.filters:
            self.getControl(5103).setPosition(0,y)
            y+=90
        if self.getProperty('cleanui.catalogue.layout')=='grid':
            self.getControl(4500).setPosition(119,y)
            self._row_offsets[4500]=0
        else:
            for i,rail in enumerate(self.screen.rails[:8]):
                cid=self._rail_control_id(i)
                parent,height=((5400+i,169) if cid>=4400 else (5300+i,217) if cid>=4200 else (5200+i,450))
                self.getControl(parent).setPosition(0,y)
                self._row_offsets[cid]=max(0,y-180)
                y+=height+112
        self.getControl(5105).setPosition(0,y)
        self._scroll_offset=0
        self.getControl(5000).setPosition(0,0)

    def _scroll_content(self,cid):
        target=getattr(self,'_row_offsets',{}).get(cid)
        if target is None or target==self._scroll_offset:
            return
        previous=self._scroll_offset
        self._scroll_offset=target
        body=self.getControl(5000)
        body.setPosition(0,-target)
        body.setAnimations([('Conditional','effect=slide start=0,{} end=0,0 time=300 '
            'tween=cubic easing=out condition=true'.format(target-previous))]
            if self.getProperty('cleanui.motion')=='true' else [])

    def _featured_actions(self):
        card=self._selected_card(4600)
        self.setProperty('cleanui.featured.details_label',
            'Ir a Serie' if card and card.kind==Card.SHOW else 'Ir a Película')
        self.setProperty('cleanui.featured.play_path',card.play_path if card else '')

    def _continue_at_edge(self,edge):
        if edge==4969:
            previous=getattr(self.screen,'_previous_rows',None)
            if previous:
                self.replace_screen(previous,self.screen_kind)
                cid=self._rail_control_id(len(previous.rails)-1)
                self.setFocusId(cid)
            return
        row=edge-4970
        rail=self.screen.rails[row] if 0<=row<min(8,len(self.screen.rails)) else None
        cid=self._rail_control_id(row) if rail else self._body[-1]
        self.setFocusId(cid)
        if getattr(self,'_loading_request',None):
            return
        target=rail.continuation if rail else self.screen.continuation
        if not target:
            return
        owner=self.screen
        position=self.getControl(cid).getSelectedPosition()
        self.controller.load_navigation(self,
            lambda:self.controller.repository.build_navigation(target),
            lambda result:self._apply_continuation(owner,cid,position,rail,result))

    def _apply_continuation(self,owner,cid,position,rail,result):
        if self.screen is not owner:
            return
        if rail:
            additions=[card for part in result.rails for card in part.items]
            rail.items.extend(additions)
            rail.continuation=result.continuation
            if additions:
                self._items(cid,rail.items,UIAdapter._effective_rail_style(rail,self.screen_kind))
                self.getControl(cid).selectItem(min(position+1,len(rail.items)-1))
            self.setFocusId(cid)
        else:
            result.featured=[]
            result._previous_rows=owner
            self.replace_screen(result,self.screen_kind)
            if self._body:
                self.setFocusId(self._body[0])

    def _configure_navigation(self):
        if self.screen_kind in ('watchlist','continue_watching'):
            current_tab = 7601 if self.screen_kind == 'continue_watching' and self.getProperty('cleanui.stuff.continue_available') == 'true' else 7600
            target = self.getControl(current_tab)
            for i, cid in enumerate(self._sidebar):
                control = self.getControl(cid)
                control.controlLeft(control)
                control.controlRight(target)
                control.controlUp(self.getControl(self._sidebar[max(0, i - 1)]))
                control.controlDown(self.getControl(self._sidebar[min(len(self._sidebar) - 1, i + 1)]))
            self._body = [4520] if self._cards.get(4520) else []
            results = self.getControl(4520)
            results.controlUp(target)
            results.controlLeft(self.getControl(3012))
            for cid in (7600,7601):
                tab = self.getControl(cid)
                tab.controlUp(tab)
                tab.controlDown(results if self._body else tab)
            self.getControl(7600).controlLeft(self.getControl(3012))
            self.getControl(7600).controlRight(self.getControl(7601) if self.getProperty('cleanui.stuff.continue_available') == 'true' else self.getControl(7600))
            self.getControl(7601).controlLeft(self.getControl(7600))
            self.getControl(7601).controlRight(self.getControl(7601))
            return
        if self.screen_kind == 'search':
            keyboard = self.getControl(getattr(self, '_search_key_focus', 8000))
            for i, cid in enumerate(self._sidebar):
                control = self.getControl(cid)
                control.controlLeft(control)
                control.controlRight(keyboard)
                control.controlUp(self.getControl(self._sidebar[max(0, i - 1)]))
                control.controlDown(self.getControl(self._sidebar[min(len(self._sidebar) - 1, i + 1)]))
            self._body = [4510] if self._cards.get(4510) else []
            self.getControl(4510).controlLeft(keyboard)
            return
        header = getattr(self,'_sidebar',[3003,3011,3012])
        body = [cid for cid in (4600,3100) if self._cards.get(cid)]
        if self.getProperty('cleanui.catalogue.layout') == 'grid':
            body += [4500] if self._cards.get(4500) else []
        else:
            body += [self._rail_control_id(i) for i in range(min(len(self.screen.rails),8))
                     if self._cards.get(self._rail_control_id(i))]
        if 4600 in body:
            body[1:1]=[7300]
            if any(c.play_path for c in self.screen.featured):
                body[2:2]=[7301]
        for i,cid in enumerate(header):
            control = self.getControl(cid)
            control.controlLeft(control)
            control.controlRight(self.getControl(self._content_focus if self._content_focus in body else body[0] if body else cid))
            control.controlUp(self.getControl(header[max(0,i-1)]))
            control.controlDown(self.getControl(header[min(len(header)-1,i+1)]))
        for i,cid in enumerate(body):
            control = self.getControl(cid)
            control.controlUp(self.getControl(body[i-1] if i else cid))
            control.controlDown(self.getControl(body[i+1] if i+1<len(body) else cid))
            if cid!=4600:
                control.controlLeft(self.getControl(header[1]))
            if 4000<=cid<4500:
                index=next(i for i in range(min(8,len(self.screen.rails))) if self._rail_control_id(i)==cid)
                control.controlRight(self.getControl(4970+index))
        if body and self.screen.continuation:
            self.getControl(body[-1]).controlDown(self.getControl(4979))
        rows=[cid for cid in body if 4000<=cid<4500]
        if rows and getattr(self.screen,'_previous_rows',None):
            self.getControl(rows[0]).controlUp(self.getControl(4969))
        self._body = body

    def _focus_first(self):
        if self.screen_kind in ('watchlist','continue_watching'):
            self.setFocusId(7601 if self.screen_kind == 'continue_watching' and self.getProperty('cleanui.stuff.continue_available') == 'true' else 7600)
            return
        if self.screen_kind == 'search':
            self.setFocusId(getattr(self, '_search_key_focus', 8000))
            return
        self.setFocusId(self._body[0] if self._body else 3000)

    def capture_state(self):
        self.screen._cleanui_window_state = dict(focus_id=self.getFocusId(),
            positions={cid:self.getControl(cid).getSelectedPosition() for cid,cards in self._cards.items() if cards})

    def _restore_state(self):
        state = getattr(self.screen,'_cleanui_window_state',None)
        if not state:
            return False
        for cid,position in state.get('positions',{}).items():
            if self._cards.get(cid):
                self.getControl(cid).selectItem(min(max(0,position),len(self._cards[cid])-1))
        cid = state.get('focus_id',3000)
        if cid in self._control_ids() and not self._cards.get(cid):
            return False
        self.setFocusId(cid)
        return True

    def reset_navigation(self):
        if self.screen_kind == 'home':
            self.screen._cleanui_window_state = None
            for cid,cards in self._cards.items():
                if cards:
                    self.getControl(cid).selectItem(0)
            self._focus_first()

    def replace_screen(self,screen,screen_kind=None):
        if not screen:
            return False
        self._gallery_clock(False)
        target_kind = screen_kind or screen.screen_kind
        if target_kind == 'search' and self.screen_kind == 'search':
            screen._cleanui_search_query = getattr(screen, '_cleanui_search_query',
                getattr(self.screen, '_cleanui_search_query', ''))
        self.screen,self.screen_kind = screen,target_kind
        if self.controller._windows and self.controller._windows[0] is self:
            self.controller._home_stack=self._history
        self._populate()
        if not self._restore_state():
            self._focus_first()
        effects.animate(self,(4500,4600))
        return True

    def _selected_card(self,control_id=None,position=None):
        cid = self.getFocusId() if control_id is None else control_id
        cards = self._cards.get(cid) or []
        index = self.getControl(cid).getSelectedPosition() if position is None else position
        return cards[index] if 0 <= index < len(cards) else None

    def _refresh_hero_from_focus(self):
        # Featured content never follows focus in lower rows.
        return

    def onFocus(self,cid):
        if getattr(self,'_binding',False) or self.getFocusId()!=cid:
            return
        if cid==4969 or 4970<=cid<=4979:
            self._continue_at_edge(cid)
            return
        if self.screen_kind == 'search' and (8000 <= cid < 8037 or 8100 <= cid <= 8102):
            self._search_key_focus = cid
            self._content_focus = cid
            self._configure_navigation()
        if hasattr(self,'_row_offsets'):
            self._scroll_content(cid)
        sidebar=getattr(self,'_sidebar',[])
        self.setProperty('cleanui.nav.open','true' if cid in sidebar else 'false')
        for nav_id in sidebar:
            self.getControl(nav_id).setWidth(420 if cid in sidebar else 104)
        if cid in self._body:
            self._content_focus=cid
            for nav_id in sidebar:
                self.getControl(nav_id).controlRight(self.getControl(cid))
        self._gallery_clock(cid == 4600)
        self.controller.notify_window_focused(self)

    def _gallery_clock(self, enabled=False):
        xbmc.executebuiltin('CancelAlarm({},true)'.format(self._gallery_alarm))
        if enabled and self.screen and len(self.screen.featured) > 1 and not effects.reduced():
            xbmc.executebuiltin('AlarmClock({},Control.Move(4600,1),00:08,true,loop)'.format(self._gallery_alarm))

    def onAction(self,action):
        aid = action.getId()
        if aid in (1,2) and self.getFocusId()==4600:
            self._featured_actions()
        if aid in (1,2) and self.getFocusId() == 4600:
            self._gallery_clock(True)
        if aid in C.ACTION_BACK:
            self._gallery_clock(False)
            if self.getFocusId() in getattr(self,'_sidebar',[]):
                self.setFocusId(self._content_focus)
                return
            if getattr(self,'_loading_request',None) or self.getProperty('cleanui.load_error')=='true':
                self.controller.cancel_navigation(self)
                self._focus_first()
                return
            if self._history:
                screen,kind = self._history.pop()
                self.replace_screen(screen,kind)
            elif self.screen_kind == 'home':
                self.controller.exit_clean_ui()
            else:
                self.controller.close_child_window(self)
        elif aid in C.ACTION_MENU:
            self._gallery_clock(False)
            self._open_menu()
        # Confirmation belongs only to onClick, never to directional actions.

    def onClick(self,cid):
        if cid == 4998:
            from .navigation_relay import consume
            consume(self)
            return
        if cid==4999:
            self.controller.complete_navigation(self)
            return
        if cid==4980:
            self.controller.retry_navigation(self)
            return
        if cid==4981:
            self.controller.cancel_navigation(self)
            self._focus_first()
            return
        if self.screen_kind == 'search' and getattr(self, '_search_view', None):
            if self._search_view.activate(cid):
                return
        if self.screen_kind in ('watchlist','continue_watching') and getattr(self, '_stuff_view', None):
            if self._stuff_view.activate(cid):
                return
        if getattr(self,'_loading_request',None):
            return
        if self._activating:
            return
        self._activating = True
        self._gallery_clock(False)
        try:
            self._activate_control(cid)
        except Exception:
            self._log_error('activate')
            xbmcgui.Dialog().ok('Clean UI','No se pudo abrir. Puedes volver e intentarlo de nuevo.')
        finally:
            self._activating = False

    def _activate_control(self,cid,card=None):
        if cid in (7300,7301):
            selected=self._selected_card(4600)
            if selected:
                if cid==7301 and selected.play_path:
                    self.controller.play(selected.play_path)
                else:
                    self._open_card(selected)
            return
        if 3300<=cid<3300+len(getattr(self,'_menu_cards',[])):
            self._navigate(self._menu_cards[cid-3300].navigation,root=True)
            return
        if 4800 <= cid < 4820:
            position = cid - 4800
            if position < len(self.screen.featured):
                self.getControl(4600).selectItem(position)
                self.setFocusId(4600)
            return
        if cid in (4700,4701):
            xbmc.executebuiltin('Control.Move(4600,{})'.format(-1 if cid == 4700 else 1))
            self.setFocusId(4600)
            return
        if cid == 3003:
            self._open_profile_menu()
        elif cid == 3015:
            self._open_settings()
        elif cid == 3000 and self.PLATFORM == 'max':
            self._open_menu()
        elif cid in (3000,3010):
            self.controller._open_home_like(self.controller.repository.build_home,'home','home',self)
        elif cid in (3005,3011):
            self.controller.open_search(self)
        elif cid in (3004,3012):
            self.controller.open_watchlist(self)
        elif cid == 3001:
            self.controller.open_movies(self)
        elif cid == 3002:
            self.controller.open_series(self)
        elif cid == 3006 and self.PLATFORM == 'disney':
            self.controller._open_home_like(
                lambda:self.controller.repository._build_browse_home('originals','Originales','collection'),
                'originals','originals',self)
        elif cid == 4900:
            self._navigate(self.screen.continuation)
        else:
            card = card or self._selected_card(cid)
            if card:
                if cid == 3100:
                    self._filter(card)
                else:
                    self._open_card(card)

    def _filter(self,card):
        filters = self.screen.filters
        self.controller.load_navigation(self,
            lambda:self.controller.repository.build_navigation(card.navigation),
            lambda screen:self._apply_filter(screen,filters,card))

    def _apply_filter(self,screen,filters,card):
        screen.filters,screen.title = filters,self.screen.title
        self.replace_screen(screen,self.screen_kind)
        self.setFocusId(3100)
        self.getControl(3100).selectItem(filters.index(card))

    def _navigate(self,target,root=False):
        return self.controller._open_home_like(lambda:self.controller.repository.build_navigation(target),
                    'home' if root and target.get('screen_kind')=='home' else 'catalogue',
                    target.get('screen_kind','collection'),self)

    def _open_card(self,card):
        if card.navigation:
            self._navigate(card.navigation)
        elif card.kind == 'page':
            self.controller.open_next_page(card,self)
        elif card.action_role == 'play' or card.kind in (C.KIND_EPISODE,C.KIND_VIDEO):
            if card.show_id and not card.season_id and card.kind == C.KIND_VIDEO and not card.action_role:
                self.controller.open_show(card.show_id)
            elif card.play_path:
                self.controller.play(card.play_path)
        elif card.kind == C.KIND_MOVIE and card.deeplink_id:
            if self.PLATFORM == 'max':
                self.controller.open_movie(card.deeplink_id,card)
            else:
                self.controller.open_movie(card.deeplink_id)
        elif card.kind == C.KIND_SHOW and card.show_id:
            self.controller.open_show(card.show_id)
        elif card.kind == C.KIND_SEASON and card.show_id and card.season_id:
            self.controller.open_season(card.show_id,card.season_id)
        elif card.browse_id:
            self.controller.open_collection(card.browse_id,card.label,self)
        else:
            raise ValueError('El servicio no entregó una acción compatible')

    def _play(self,path):
        if path:
            self.controller.play(path)

    def release_resources(self):
        from .navigation_relay import cancel
        cancel(self)
        self.controller.cancel_navigation(self)
        self._last_load=None
        self._gallery_clock(False)
        for cid in self._control_ids():
            try:
                self.getControl(cid).reset()
            except RuntimeError:
                pass
        self._cards.clear()
        self.setProperty('cleanui.profile.avatar','')


    def _open_settings(self):
        """Use SlyGuy's existing categories/actions over the current window."""
        from slyguy.settings.types import Category
        history = [Category.get(0)]
        while history:
            category = history[-1]
            children = list(category.categories)
            options = children + list(category.settings)
            from .choice_window import choose
            choice = choose(self.controller.addon_path, category.label, [item.label for item in options])
            if choice < 0:
                history.pop()
            elif choice < len(children):
                history.append(children[choice])
            elif choice < len(options):
                options[choice].on_select()


    def _open_profile_menu(self):
        """Mirror Max's avatar menu using only SlyGuy-backed actions."""
        if not self.controller:
            return
        loader=getattr(self.controller,'_navigation_loader',None)
        if loader and loader.active:
            return
        from .profile_window import available_profiles
        from .choice_window import choose
        profiles = available_profiles()
        if not profiles:
            return
        options = [profile.get('profileName') or '' for profile in profiles]
        options += ['Ajustes', 'Cerrar sesión', effects.label()]
        choice = choose(self.controller.addon_path, 'Perfil', options)
        if choice < 0:
            return
        if choice == len(profiles) + 2:
            effects.toggle(self)
            return
        if choice < len(profiles):
            self.controller.select_profile(self, profiles[choice])
            return
        if choice == len(profiles):
            self._open_settings()
            return
        import resources.lib.plugin as core
        self.controller.run_plugin_after_close(core.plugin.url_for(core.logout))

    def _open_menu(self):
        loader=getattr(self.controller,'_navigation_loader',None)
        if loader and loader.active:
            return
        from .choice_window import choose
        entries = self.controller.repository.menu_entries()
        choice = choose(self.controller.addon_path,'Explorar',[entry.label for entry in entries],sidebar=True)
        if 0 <= choice < len(entries):
            self._navigate(entries[choice].navigation,root=True)
