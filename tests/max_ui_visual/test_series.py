import ast
from pathlib import Path
import types
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui'


class SeriesTests(unittest.TestCase):
    def fixture(self):
        class Item:
            def __init__(self,label):self.label=label;self.properties={}
            def setProperty(self,key,value):self.properties[key]=value
        class Control:
            position=0
            def reset(self):self.items=[]
            def addItems(self,items):self.items=items
            def selectItem(self,index):self.position=index
            def getSelectedPosition(self):return self.position
            def setLabel(self,label):self.label=label
            def controlUp(self,target):pass
            def controlDown(self,target):pass
            def size(self):return 2
            def setVisibleCondition(self,value):self.visible=value
        controls={cid:Control() for cid in [7000,7001,7002,7200,6101,*range(4000,4004),*range(6000,6004)]}
        calls=[];properties={}
        season1=types.SimpleNamespace(label='Temporada 1',season_id='1',show_id='actual-show')
        season2=types.SimpleNamespace(label='Temporada 2',season_id='2',show_id='actual-show')
        screen=types.SimpleNamespace(season_choices=[season1,season2],selected_season=season2)
        repo=types.SimpleNamespace(build_show_episodes=lambda show,season:(show,season))
        controller=types.SimpleNamespace(repository=repo,load_navigation=lambda owner,build,apply:calls.append(build()))
        obj=types.SimpleNamespace(screen=screen,PLATFORM='max',controller=controller,
             _sidebar=[],getControl=controls.__getitem__,setProperty=properties.__setitem__,
             getProperty=lambda key:properties.get(key,''),_panel_id=lambda i:4000+i,
             _set_season_picker=lambda opened:None,setFocusId=lambda cid:None,
             _apply_season=lambda result,index:None)
        tree=ast.parse((ROOT/'resources/lib/ui/detail_window.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DetailWindow')
        selected={'_seasons','_season_index','_populate_seasons','_change_season','_select_tab'}
        env={'xbmcgui':types.SimpleNamespace(ListItem=Item)}
        exec(compile(ast.Module(body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in selected],type_ignores=[]),'detail_seasons','exec'),env)
        for name in selected:setattr(obj,name,types.MethodType(env[name],obj))
        return obj,controls,calls

    def test_chips_keep_service_order_and_current_season_without_new_actions(self):
        view,controls,calls=self.fixture();view._populate_seasons()
        self.assertEqual([n.label for n in controls[7002].items],['1','2'])
        self.assertEqual(controls[7002].position,1)
        self.assertEqual([n.properties['cleanui.selected'] for n in controls[7002].items],['false','true'])
        self.assertEqual(calls,[])

    def test_switch_delegates_exact_service_ids_and_same_choice_is_noop(self):
        view,controls,calls=self.fixture();view._populate_seasons()
        controls[7001].selectItem(1);view._change_season();self.assertEqual(calls,[])
        controls[7001].selectItem(0);view._change_season();self.assertEqual(calls,[('actual-show','1')])
        controls[7001].selectItem(99);view._change_season();self.assertEqual(len(calls),1)

    def test_episode_row_and_text_viewport_fit_the_observed_lower_view(self):
        root=ET.parse(ROOT/'resources/skins/Default/1080i/ui_detail.xml').getroot()
        body=root.find(".//control[@id='5300']");panel=body.find(".//control[@id='4000']")
        texture=next(n for n in panel.find('itemlayout').findall('control') if n.findtext('texture')=='$INFO[ListItem.Property(cleanui.display_art)]')
        self.assertEqual(int(body.findtext('top'))+int(panel.findtext('top'))+int(texture.findtext('top'))-643,507)
        self.assertEqual((texture.findtext('width'),texture.findtext('height')),('385','217'))
        self.assertEqual(panel.find('itemlayout').get('width'),'460')
        fulltext=body.find("control[@id='6100']")
        self.assertLessEqual(int(body.findtext('top'))-643+int(fulltext.findtext('top'))+int(fulltext.findtext('height')),1080)
        nav=root.find(".//control[@id='5900']")
        self.assertIn('cleanui.detail.scrolled',nav.findtext('visible'))
        self.assertIsNotNone(nav.find("control[@id='3011']"))


if __name__=='__main__':unittest.main()
