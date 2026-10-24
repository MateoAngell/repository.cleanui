"""Entity presentation with inline episodes and explicit action routing."""
import textwrap
import traceback
import xbmc
import xbmcgui
from . import constants as C, effects
from .adapter import UIAdapter
from .detail_layout import metadata as display_metadata
from .home_window import HomeWindow

class DetailWindow(xbmcgui.WindowXMLDialog):
    PLATFORM = 'max'

    def __init__(self,*args,**kwargs):
        self.controller=kwargs.pop('controller')
        self.screen=kwargs.pop('screen')
        super(DetailWindow,self).__init__(*args,**kwargs)
        self._activating=False
        self._last_activation=None

    def _log_error(self,context):
        xbmc.log('[CLEANUI] detail.{}: {}'.format(context,traceback.format_exc()),xbmc.LOGERROR)

    def onInit(self):
        try:
            effects.prepare(self)
            self._actions=[]
            self._set_hero()
            self._populate_rails()
            self._populate_seasons()
            self._prepare_navigation()
            self._select_tab(self._tabs[0]-6000)
            if not self._restore_state():
                self._focus_best()
        except Exception:
            self._log_error('onInit')
            self.controller.end_transition()
            self.close()

    def _prepare_navigation(self):
        parent = next((window for window in self.controller._windows
                       if isinstance(window, HomeWindow) and window is not self), None)
        self._catalogue_parent = parent
        self._nav_dispatched = False
        self._content_focus = self._actions[0] if self._actions else self._tabs[0]
        if parent is None:
            self._sidebar = []
            self.setProperty('cleanui.nav.count', '0')
            self.setProperty('cleanui.nav.open', 'false')
            return
        self._menu_cards = list(getattr(parent, '_menu_cards', []))
        self.screen_kind = parent.screen_kind
        for key in ('profile.name', 'profile.avatar'):
            self.setProperty('cleanui.' + key, parent.getProperty('cleanui.' + key))
        HomeWindow._prepare_sidebar(self)
        for i, cid in enumerate(self._sidebar):
            control = self.getControl(cid)
            control.controlLeft(control)
            control.controlRight(self.getControl(self._content_focus))
            control.controlUp(self.getControl(self._sidebar[max(0, i - 1)]))
            control.controlDown(self.getControl(self._sidebar[min(len(self._sidebar) - 1, i + 1)]))
        if self._actions:
            self.getControl(self._actions[0]).controlLeft(self.getControl(3011))
        self.getControl(self._tabs[0]).controlLeft(self.getControl(3011))
        for i in range(min(4, len(self.screen.rails))):
            self.getControl(self._panel_id(i)).controlLeft(self.getControl(3011))

    def _seasons(self):
        return getattr(self.screen,'seasons',getattr(self.screen,'season_choices',[]))

    def _season_index(self):
        selected=getattr(self.screen,'selected_season',0)
        if isinstance(selected,int):
            return min(max(0,selected),max(0,len(self._seasons())-1))
        return next((i for i,s in enumerate(self._seasons()) if s.season_id==selected.season_id),0)

    def _set_hero(self):
        hero=self.screen.hero
        if not hero:
            return
        info,art=hero.info,hero.art
        episode = next((card for rail in self.screen.rails for card in rail.items
                        if card.kind == C.KIND_EPISODE and card.play_path == hero.play_path and card.play_path), None)
        display_info = episode.info if episode is not None else info
        episode_title = ''
        if episode is not None:
            import re
            title = re.sub(r'^\d+\.\s*', '', episode.label)
            season = display_info.get('season') or getattr(self.screen, 'selected_season', '')
            if not isinstance(season, (str, int)):
                season = getattr(season, 'season_id', '')
            number = display_info.get('episode') or ''
            episode_title = 'T{} E{} {}'.format(season, number, title).strip()
        action=''
        if self.PLATFORM=='disney':
            action='add' if getattr(hero,'watchlist_data',None) else ''
        else:
            action=next((a for _,a in hero.context if 'watchlist' in a), '')
        genre=info.get('genre') or ''
        if isinstance(genre,(list,tuple)):
            genre='  '.join(str(g) for g in genre)
        values=dict(title=hero.label,fanart=art.get('fanart') or art.get('banner') or '',
                    logo=art.get('clearlogo') or '',plot=display_info.get('plot') or '',
                    summary=textwrap.shorten(display_info.get('plot') or '',width=105,placeholder='…'),
                    meta=display_metadata(display_info),genre=str(genre),episode_title=episode_title,play_path=hero.play_path or '',
                    trailer_path=hero.trailer_path or '',watchlist_action=action,
                    play_label=getattr(self.screen,'play_label','Ver ahora'))
        if values['play_label'] and not values['play_label'].startswith('▶ '):
            values['play_label'] = '▶ ' + values['play_label']
        if values['play_label'] == '▶ REPRODUCIR':
            values['play_label'] = '▶ Ver ahora'
        self.setProperty('cleanui.detail.episode_header', 'true' if episode_title else 'false')
        self.getControl(2004).setPosition(130, 634 if episode_title else 580)
        self.getControl(1004).setPosition(800, 672 if episode_title else 620)
        for key,value in values.items():
            self.setProperty('cleanui.detail.'+key,value)
        actions=[cid for cid,key in ((1000,'play_path'),(1001,'trailer_path'),(1002,'watchlist_action'))
                 if values[key]]
        self._actions=actions
        x=72 if self.PLATFORM=='disney' else 130
        for i,cid in enumerate(actions):
            control=self.getControl(cid)
            control.setPosition(x,414 if self.PLATFORM=='disney' else 738)
            width=(240 if cid==1000 else 140 if cid==1001 else 64) if self.PLATFORM=='disney' else (265 if cid==1000 else 180 if cid==1001 else 68)
            if self.PLATFORM == 'max' and cid == 1000:
                width = max(width, min(560, len(values['play_label']) * 18 + 60))
            control.setWidth(width)
            if self.PLATFORM == 'max':
                control.setHeight(86)
            control.controlLeft(self.getControl(actions[i-1] if i else cid))
            control.controlRight(self.getControl(actions[i+1] if i+1<len(actions) else cid))
            control.controlUp(control)
            x+=width+20
        if self.PLATFORM == 'max' and values['plot']:
            more = self.getControl(1004)
            more.controlLeft(more)
            more.controlRight(more)
            more.controlDown(self.getControl(actions[0] if actions else 1003))
            if actions:
                self.getControl(actions[0]).controlUp(more)

    def _populate_rails(self):
        tabs=[]
        for i in range(4):
            control=self.getControl(4000+i)
            control.reset()
            rail=self.screen.rails[i] if i<len(self.screen.rails) else None
            self.setProperty('cleanui.detail.rail{}.style'.format(i),rail.style if rail else '')
            cards=rail.items if rail else []
            self.setProperty('cleanui.detail.rail{}.visible'.format(i),'true' if cards else 'false')
            self.setProperty('cleanui.detail.rail{}.title'.format(i),
                {'episodes':'Episodios','seasons':'Temporadas','extras':'Extras',
                 'suggested':'SUGERENCIAS' if self.PLATFORM=='disney' else 'Quizá también te guste'
                 }.get(rail.rail_id,rail.title) if rail else '')
            if cards:
                target=self.getControl(self._panel_id(i))
                target.reset()
                style=(C.STYLE_POSTER if self.PLATFORM=='max' and rail.style==C.STYLE_POSTER else
                       C.STYLE_EPISODE if rail.style==C.STYLE_EPISODE else C.STYLE_LANDSCAPE)
                target.addItems([UIAdapter.to_list_item(card,style) for card in cards])
                tabs.append(6000+i)
        tabs.append(6004)
        self._tabs=tabs
        x=72 if self.PLATFORM=='disney' else 130
        for i,cid in enumerate(tabs):
            control=self.getControl(cid)
            control.setPosition(x,0)
            width=184 if cid==6004 else min(500,max(184,len(self.getProperty(
                'cleanui.detail.rail{}.title'.format(cid-6000)))*15+48))
            control.setWidth(width)
            self.getControl(6500+cid-6000).setPosition(x,0)
            self.getControl(6500+cid-6000).setHeight(76)
            self.getControl(6500+cid-6000).setWidth(width)
            control.controlLeft(self.getControl(tabs[max(0,i-1)]))
            control.controlRight(self.getControl(tabs[min(len(tabs)-1,i+1)]))
            control.controlUp(self.getControl(self._actions[-1] if self._actions else 1003))
            if cid!=6004:
                control.controlDown(self.getControl(
                7002 if cid==6000 and self._seasons() else self._panel_id(cid-6000)))
            x+=width+24
        for cid in self._actions+[1003]:
            self.getControl(cid).controlDown(self.getControl(tabs[0]))

    def _populate_seasons(self):
        seasons=self._seasons()
        self.setProperty('cleanui.detail.has_seasons','true' if seasons else 'false')
        self._set_season_picker(False)
        if seasons:
            index=self._season_index()
            self.getControl(7000).setLabel('Temporada')
            chips = self.getControl(7002)
            chips.reset()
            choices = []
            for i, season in enumerate(seasons):
                item = xbmcgui.ListItem(label=str(season.season_id or i + 1))
                item.setProperty('cleanui.selected', 'true' if i == index else 'false')
                choices.append(item)
            chips.addItems(choices)
            chips.selectItem(index)
            self.getControl(7001).reset()
            self.getControl(7001).addItems([xbmcgui.ListItem(label=s.label) for s in seasons])
            self.getControl(7001).selectItem(index)
        for i in range(4):
            panel=self.getControl(self._panel_id(i))
            panel.controlUp(self.getControl(7002 if i==0 and seasons else 6000+i))
            panel.controlDown(self.getControl(7200) if i == 0 and seasons else panel)
        self.getControl(7200).controlUp(self.getControl(4000))
        self.getControl(7200).controlDown(self.getControl(7200))

    def _panel_id(self,index):
        rail=self.screen.rails[index] if index<len(self.screen.rails) else None
        return (4300 if self.PLATFORM=='max' and rail and rail.style==C.STYLE_POSTER else 4000)+index

    def _select_tab(self,index):
        if index<4 and self.getProperty('cleanui.detail.rail{}.visible'.format(index))!='true':
            return
        self.setProperty('cleanui.detail.tab',str(index))
        self.getControl(7002).setVisibleCondition('true' if index == 0 and self._seasons() else 'false')
        self.getControl(6101).setVisibleCondition('true' if index == 4 else 'false')

    def _change_season(self):
        index=self.getControl(7001).getSelectedPosition()
        seasons=self._seasons()
        self._set_season_picker(False)
        self.setFocusId(7002)
        if not 0<=index<len(seasons):
            self.setFocusId(7002)
            return
        if index!=self._season_index():
            season=seasons[index]
            builder=(lambda:self.controller.repository.build_episode_rail(season.season_id,season.label)
                     if self.PLATFORM=='disney' else
                     self.controller.repository.build_show_episodes(season.show_id,season.season_id))
            self.controller.load_navigation(self,builder,
                lambda result:self._apply_season(result,index))
            return
        self._select_tab(0)
        self.setFocusId(4000 if self.getControl(4000).size() else 7002)

    def _apply_season(self,result,index):
        if self.PLATFORM=='disney':
            self.screen.rails[0]=result
            self.screen.selected_season=index
            first=next((card for card in result.items if card.kind==C.KIND_EPISODE),None)
            self.screen.hero.play_path=first.play_path if first else ''
        else:
            self.screen=result
        self._set_hero()
        self._populate_rails()
        self._populate_seasons()
        self._prepare_navigation()
        self._select_tab(0)
        self.setFocusId(4000 if self.getControl(4000).size() else 7002)

    def _focus_best(self):
        self.setFocusId(self._actions[0] if self._actions else self._tabs[0])

    def _set_season_picker(self,opened):
        value='true' if opened else 'false'
        self.setProperty('cleanui.detail.season_picker',value)
        # Literal visibility is applied before Kodi handles SETFOCUS.
        # A property condition alone is not evaluated until the next frame.
        self.getControl(7001).setVisibleCondition(value)

    def onFocus(self,cid):
        if cid in (1004,7200) and getattr(self, '_expanded_summary', False):
            self._expanded_summary = False
            self._restore_episode_information()
            self._select_tab(getattr(self, '_summary_previous_tab', 0))
        sidebar = getattr(self, '_sidebar', [])
        opened = cid in sidebar
        self.setProperty('cleanui.nav.open', 'true' if opened else 'false')
        for nav_id in sidebar:
            control = self.getControl(nav_id)
            control.setWidth(420 if opened else 104)
            if not opened:
                control.controlRight(self.getControl(cid))
        if not opened:
            self._content_focus = cid
        if self.PLATFORM=='max':
            target=643 if cid>=4000 else 0
            self.setProperty('cleanui.detail.scrolled', 'true' if target else 'false')
            previous=getattr(self,'_scroll_offset',0)
            if target!=previous:
                self._scroll_offset=target
                body=self.getControl(5000)
                body.setPosition(0,-target)
                body.setAnimations([('Conditional','effect=slide start=0,{} end=0,0 time=300 '
                    'tween=cubic easing=out condition=true'.format(target-previous))]
                    if self.getProperty('cleanui.motion')=='true' else [])
        xbmc.log('[CLEANUI][FOCUS] detail={} picker={}'.format(cid,
            self.getProperty('cleanui.detail.season_picker')),xbmc.LOGINFO)
        if 6000<=cid<=6004:
            self._select_tab(cid-6000)
        if cid not in (7000,7001) and self.getFocusId()==cid:
            self._set_season_picker(False)
        self.controller.notify_window_focused(self)

    def capture_state(self):
        self.screen._cleanui_window_state=dict(focus_id=self.getFocusId(),
            tab=self.getProperty('cleanui.detail.tab'),
            positions={self._panel_id(i):self.getControl(self._panel_id(i)).getSelectedPosition()
                       for i in range(4) if self.getControl(self._panel_id(i)).size()})

    def _restore_state(self):
        state=getattr(self.screen,'_cleanui_window_state',None)
        if not state:
            return False
        self._select_tab(int(state.get('tab') or 0))
        for cid,pos in state.get('positions',{}).items():
            control=self.getControl(cid)
            if control.size():
                control.selectItem(min(max(0,pos),control.size()-1))
        cid=state.get('focus_id',self._tabs[0])
        if cid in (7000,7001):
            cid=7002
        allowed=set(self._actions+self._tabs+[1003,1004,6101])
        if self._seasons():
            allowed.update((7002,7200))
        allowed.update(self._panel_id(i) for i in range(min(4,len(self.screen.rails)))
                       if self.getControl(self._panel_id(i)).size())
        if cid not in allowed:
            return False
        self.setFocusId(cid)
        return True

    def _close_current_window(self):
        if getattr(self,'_page_history',None):
            self.screen=self._page_history.pop()
            self.onInit()
        else:
            self.controller.close_child_window(self)

    def onAction(self,action):
        xbmc.log('[CLEANUI][INPUT] detail action={} focus={}'.format(
            action.getId(),self.getFocusId()),xbmc.LOGINFO)
        if action.getId() in C.ACTION_BACK:
            if getattr(self, '_expanded_summary', False):
                self._expanded_summary = False
                self._restore_episode_information()
                self._select_tab(getattr(self, '_summary_previous_tab', 0))
                self.setFocusId(getattr(self, '_summary_return_focus', 1004))
                return
            if self.getFocusId() in getattr(self, '_sidebar', []):
                self.setFocusId(self._content_focus)
                return
            if getattr(self,'_loading_request',None) or self.getProperty('cleanui.load_error')=='true':
                self.controller.cancel_navigation(self)
                self._focus_best()
                return
            if self.getProperty('cleanui.detail.season_picker')=='true':
                self._set_season_picker(False)
                self.setFocusId(7002)
            else:
                self._close_current_window()

    def onClick(self,cid):
        xbmc.log('[CLEANUI][CLICK] detail={}'.format(cid),xbmc.LOGINFO)
        if cid==4999:
            self.controller.complete_navigation(self)
            return
        if cid==4980:
            self.controller.retry_navigation(self)
            return
        if cid==4981:
            self.controller.cancel_navigation(self)
            self._focus_best()
            return
        if getattr(self,'_loading_request',None):
            return
        if self._activating:
            return
        self._activating=True
        try:
            self._activate_click(cid)
        except Exception:
            self._log_error('activation')
            xbmcgui.Dialog().ok('Clean UI','No se pudo abrir este contenido. Puedes volver e intentarlo de nuevo.')
        finally:
            self._activating=False

    def _activate_click(self,cid):
        if cid in getattr(self, '_sidebar', []):
            parent = getattr(self, '_catalogue_parent', None)
            if parent is not None:
                from .navigation_relay import request
                request(parent, self, cid)
            return
        if cid == 7200:
            self._show_episode_information()
        elif cid==1004:
            self._summary_return_focus = 1004
            if not getattr(self, '_expanded_summary', False):
                self._summary_previous_tab = int(self.getProperty('cleanui.detail.tab') or 0)
                self._expanded_summary = True
            self._select_tab(4)
            self.getControl(6101).controlUp(self.getControl(1004))
            self.setFocusId(6101)
        elif cid==1003:
            self._close_current_window()
        elif cid==7000:
            self.setFocusId(7002)
        elif cid==7002:
            self.getControl(7001).selectItem(self.getControl(7002).getSelectedPosition())
            self._change_season()
        elif cid==7001:
            self._change_season()
        elif 6000<=cid<=6004:
            index=cid-6000
            self._select_tab(index)
            self.setFocusId(6101 if index==4 else 7002 if index==0 and self._seasons() else self._panel_id(index))
        elif cid in (1000,1001):
            self._play(self.getProperty('cleanui.detail.'+('play_path' if cid==1000 else 'trailer_path')))
        elif cid==1002:
            if self.PLATFORM=='disney':
                self.controller.repository.add_detail_to_watchlist(self.screen.hero)
                xbmcgui.Dialog().notification('Disney+','Añadido a Mi lista')
            else:
                action=self.getProperty('cleanui.detail.watchlist_action')
                if action:
                    xbmc.executebuiltin(action)
        elif 4000<=cid<4004 or 4300<=cid<4304:
            self._open_selected(cid)

    def _restore_episode_information(self):
        saved = getattr(self, '_episode_information_saved', None)
        if saved:
            for key, value in saved.items():
                self.setProperty('cleanui.detail.' + key, value)
            self._episode_information_saved = None

    def _show_episode_information(self):
        if not self.screen.rails:
            return False
        index = self.getControl(4000).getSelectedPosition()
        cards = self.screen.rails[0].items
        if not 0 <= index < len(cards) or cards[index].kind != C.KIND_EPISODE:
            return False
        card = cards[index]
        self._episode_information_saved = {key:self.getProperty('cleanui.detail.' + key)
                                           for key in ('title','plot','meta','genre')}
        values = dict(title=card.label, plot=(card.info or {}).get('plot') or '',
                      meta=display_metadata(card.info or {}), genre='')
        for key, value in values.items():
            self.setProperty('cleanui.detail.' + key, value)
        self._summary_previous_tab = 0
        self._summary_return_focus = 7200
        self._expanded_summary = True
        self._select_tab(4)
        self.getControl(6101).controlUp(self.getControl(7200))
        self.setFocusId(6101)
        return True

    def _open_selected(self,cid):
        index=self.getControl(cid).getSelectedPosition()
        cards=self.screen.rails[cid-(4300 if cid>=4300 else 4000)].items
        if not 0<=index<len(cards):
            return
        card=cards[index]
        if card.navigation:
            target=card.navigation
            if target.get('kind')=='season':
                self.controller.load_navigation(self,
                    lambda:self.controller.repository.build_episode_rail(target['id'],target['title'],target.get('page',1)),
                    self._apply_episode_page)
                return
            self.controller._open_home_like(lambda:self.controller.repository.build_navigation(target),
                                           'content',target.get('screen_kind','episodes'))
        elif card.kind=='page':
            self.controller.open_next_page(card,self)
        elif card.action_role=='play' or card.kind in (C.KIND_EPISODE,C.KIND_VIDEO):
            self._play(card.play_path)
        elif card.kind==C.KIND_MOVIE and card.deeplink_id:
            self.controller.open_movie(card.deeplink_id)
        elif card.kind==C.KIND_SHOW and card.show_id:
            self.controller.open_show(card.show_id)
        elif card.kind==C.KIND_SEASON:
            self.controller.open_season(card.show_id,card.season_id)
        elif card.browse_id:
            self.controller.open_collection(card.browse_id,card.label)
        else:
            raise ValueError('Contenido sin acción disponible')

    def _play(self,path):
        if not path:
            raise ValueError('El servicio no entregó una reproducción')
        self.controller.play(path)

    def _apply_episode_page(self,rail):
        from copy import copy
        self.capture_state()
        previous=self.screen
        self._page_history=getattr(self,'_page_history',[])+[previous]
        self.screen=copy(previous)
        self.screen.rails=[rail]+previous.rails[1:]
        self.screen._cleanui_window_state=None
        self.onInit()
        self.setFocusId(4000)

    def release_resources(self):
        self.controller.cancel_navigation(self)
        self._last_load=None
        for cid in (4000,4001,4002,4003,7001,7002)+((4300,4301,4302,4303) if self.PLATFORM=='max' else ()):
            self.getControl(cid).reset()
        for key in ('fanart','logo','plot','summary','play_path','trailer_path'):
            self.setProperty('cleanui.detail.'+key,'')
