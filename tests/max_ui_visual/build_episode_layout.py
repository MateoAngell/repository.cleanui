"""Measured TV entity/episode geometry; only presentation resources are written."""
from pathlib import Path
import xml.etree.ElementTree as E

ROOT=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui'
PATH=ROOT/'resources/skins/Default/1080i/ui_detail.xml'


def values(node, mapping):
    for key,value in mapping.items():
        element=node.find(key)
        if element is None:element=E.SubElement(node,key)
        element.text=str(value)


def control(parent,kind,ident=None,**mapping):
    node=E.SubElement(parent,'control',dict(type=kind,**({'id':str(ident)} if ident is not None else {})))
    values(node,mapping);return node


def build():
    r=E.parse(PATH).getroot();controls=r.find('controls');body=r.find(".//control[@id='5000']");hero=r.find(".//control[@id='5100']")
    for n in list(hero):
        if n.findtext('texture') in ('$INFO[Window.Property(cleanui.detail.fanart)]','max-hero-shade.png'):
            hero.remove(n);controls.insert(list(controls).index(body),n)
    if controls.find("control[@id='2015']") is None:
        n=control(controls,'image',2015,left=130,top=120,width=414,height=116,
                  texture='$INFO[Window.Property(cleanui.detail.logo)]',aspectratio='keep',
                  visible='String.IsEqual(Window.Property(cleanui.detail.scrolled),true)')
        controls.remove(n);controls.insert(list(controls).index(body)+1,n)
    if hero.find("control[@id='2008']") is None:
        control(hero,'label',2008,left=130,top=582,width=764,height=44,font='font30_title',
                label='$INFO[Window.Property(cleanui.detail.episode_title)]',textcolor='FFF5F5F7',aligny='center',
                visible='String.IsEqual(Window.Property(cleanui.detail.episode_header),true)')
    values(hero.find("control[@id='2007']"),{'visible':'!String.IsEqual(Window.Property(cleanui.detail.episode_header),true)'})
    tabs=r.find(".//control[@id='5200']");values(tabs,{'top':937,'height':98})
    for i in range(5):
        n=tabs.find("control[@id='{}']".format(6000+i));values(n,{'height':76,'font':'font30_title','textcolor':'FFC4C4C4'})
        n.find('texturefocus').set('colordiffuse','FFF5F5F7')
        indicator=tabs.find("control[@id='{}']".format(6500+i));values(indicator,{'top':0,'height':76,'texture':'max-tab-outline.png'})
    for n in tabs.findall('control'):
        if n.get('type')=='image' and not n.get('id'):values(n,{'visible':'false'})
    content=r.find(".//control[@id='5300']");values(content,{'top':1059})
    for i in range(4):
        panel=content.find(".//control[@id='{}']".format(4000+i));panel.set('type','list');values(panel,{'top':80,'height':430,'orientation':'horizontal'})
        for tag in ['itemlayout','focusedlayout']:
            item=panel.find(tag);item.set('width','460');item.set('height','425')
            for n in item.findall('control'):
                if n.findtext('label')=='$INFO[ListItem.Label]' and n.findtext('top')=='245':
                    n.set('type','textbox');values(n,{'height':68})
                if n.findtext('label')=='$INFO[ListItem.Property(cleanui.card_summary)]':
                    n.set('type','label');values(n,{'top':316,'height':40,'font':'font27','label':'$INFO[ListItem.Property(cleanui.episode_meta)]'})
    values(content.find("control[@id='7000']"),{'left':130,'top':0,'width':164,'height':64,'font':'font27','enable':'false'})
    for ident in (6100,6101):values(content.find("control[@id='{}']".format(ident)),{'height':600})
    if content.find("control[@id='7002']") is None:
        chips=control(content,'list',7002,left=304,top=0,width=1350,height=64,orientation='horizontal',scrolltime=150,
            visible='String.IsEqual(Window.Property(cleanui.detail.tab),0) + String.IsEqual(Window.Property(cleanui.detail.has_seasons),true)',
            onup=6000,ondown=4000,onleft=7002,onright=7002)
        for tag,focused in [('itemlayout',False),('focusedlayout',True)]:
            item=E.SubElement(chips,tag,width='78',height='64')
            bg=control(item,'image',left=7,top=0,width=64,height=62,texture='white.png',colordiffuse='FFF5F5F7')
            if not focused:values(bg,{'visible':'String.IsEqual(ListItem.Property(cleanui.selected),true)'})
            for selected,color in [(True,'FF000000'),(False,'FFF5F5F7')]:
                text=control(item,'label',left=7,top=0,width=64,height=62,font='font30_title',label='$INFO[ListItem.Label]',textcolor=color,align='center',aligny='center')
                visible='true' if focused and selected else 'false' if focused else ('' if selected else '!')+'String.IsEqual(ListItem.Property(cleanui.selected),true)'
                values(text,{'visible':visible})
    if content.find("control[@id='7200']") is None:
        n=control(content,'button',7200,left=130,top=450,width=421,height=70,font='font27',label='Información del episodio',align='center',aligny='center',
            textcolor='FFF5F5F7',focusedcolor='FF000000',
            visible='String.IsEqual(Window.Property(cleanui.detail.tab),0) + String.IsEqual(Window.Property(cleanui.detail.has_seasons),true) + [Control.HasFocus(4000) | Control.HasFocus(7200)]')
        E.SubElement(n,'texturefocus',colordiffuse='FFF5F5F7').text='rounded-rect.png';E.SubElement(n,'texturenofocus').text='max-tab-outline.png'
    E.indent(r,space='  ');PATH.write_bytes(E.tostring(r,encoding='utf-8',xml_declaration=True)+b'\n')


if __name__=='__main__':build()
