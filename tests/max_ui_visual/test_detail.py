import ast
import importlib.util
from pathlib import Path
import types
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui'
UI=ROOT/'resources/lib/ui'
spec=importlib.util.spec_from_file_location('detail_layout',UI/'detail_layout.py')
layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)


class DetailTests(unittest.TestCase):
    def test_metadata_formats_service_values_without_inventing_capability_badges(self):
        self.assertEqual(layout.metadata({'mpaa':'16+','duration':9180,'year':2008}),'16+  2h 33m  2008')
        self.assertEqual(layout.metadata({'duration':'bad','year':2026}),'2026')
        self.assertEqual(layout.metadata({'duration':-90}),'')
        self.assertNotIn('4K',layout.metadata({'duration':9180,'year':2008}))

    def methods(self):
        tree=ast.parse((UI/'detail_window.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DetailWindow')
        nodes=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_activate_click','onAction')]
        env={'xbmc':types.SimpleNamespace(log=lambda *args:None,LOGINFO=1),
             'C':types.SimpleNamespace(ACTION_BACK=(9,10,92))}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'detail','exec'),env)
        return env

    def test_more_and_back_reuse_existing_text_panel_without_closing_entity(self):
        methods=self.methods();events=[]
        control=types.SimpleNamespace(controlUp=lambda target:events.append('up-bound'))
        obj=types.SimpleNamespace(_sidebar=[],getProperty=lambda key:'0',getControl=lambda cid:control,
             _select_tab=lambda index:events.append(('tab',index)),setFocusId=lambda cid:events.append(('focus',cid)),
             getFocusId=lambda:6101,_restore_episode_information=lambda:None,_close_current_window=lambda:events.append('closed'))
        methods['_activate_click'](obj,1004)
        methods['_activate_click'](obj,1004)
        self.assertEqual(obj._summary_previous_tab,0)
        self.assertTrue(obj._expanded_summary)
        methods['onAction'](obj,types.SimpleNamespace(getId=lambda:92))
        self.assertFalse(obj._expanded_summary)
        self.assertEqual(events[-2:],[('tab',0),('focus',1004)])
        self.assertNotIn('closed',events)

    def test_header_actions_fit_below_plot_and_genres(self):
        root=ET.parse(ROOT/'resources/skins/Default/1080i/ui_detail.xml').getroot()
        hero=root.find(".//control[@id='5100']")
        meta=hero.find("control[@id='2003']");plot=hero.find("control[@id='2004']");genre=hero.find("control[@id='2007']")
        bottom=lambda n:int(n.findtext('top'))+int(n.findtext('height'))
        self.assertLess(bottom(meta),int(plot.findtext('top')))
        self.assertLess(bottom(plot),int(genre.findtext('top')))
        self.assertLess(bottom(genre),int(hero.find("control[@id='1000']/top").text))
        ids=[int(n.get('id')) for n in root.iter('control') if n.get('id')]
        self.assertEqual(len(ids),len(set(ids)))


if __name__=='__main__':unittest.main()
