"""Native My Stuff geometry observed in Max TV at 1920×1080."""
from pathlib import Path
import xml.etree.ElementTree as ET

PATH=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui/resources/skins/Default/1080i/uihome.xml'


def node(parent,kind,ident=None,**values):
    element=ET.SubElement(parent,'control',dict(type=kind,**({'id':str(ident)} if ident is not None else {})))
    for key,value in values.items():ET.SubElement(element,key).text=str(value)
    return element


def image(parent,x,y,width,height,texture,color=None,**values):
    element=node(parent,'image',left=x,top=y,width=width,height=height,aspectratio='stretch',**values)
    ET.SubElement(element,'texture',**({'colordiffuse':color} if color else {})).text=texture
    return element


def build():
    root=ET.parse(PATH).getroot();controls=root.find('controls')
    old=controls.find("control[@id='5810']")
    if old is not None:controls.remove(old)
    group=node(controls,'group',5810,left=0,top=0,width=1920,height=1080,
        visible='[String.IsEqual(Window.Property(cleanui.screen.kind),watchlist) | String.IsEqual(Window.Property(cleanui.screen.kind),continue_watching)]')
    controls.remove(group);controls.insert(2,group)
    image(group,0,0,1920,1080,'white.png','FF000000')
    node(group,'label',left=130,top=58,width=1500,height=100,font='font52_title',textcolor='FFF5F5F7',label='Mis cosas',aligny='center')
    for ident,x,width,label,kind in [(7600,128,180,'Mi lista','watchlist'),(7601,332,320,'Continuar viendo','continue_watching')]:
        image(group,x,173,width,74,'max-tab-outline.png',visible='String.IsEqual(Window.Property(cleanui.stuff.tab),{})'.format(kind)+(' + String.IsEqual(Window.Property(cleanui.stuff.continue_available),true)' if ident==7601 else ''))
        button=node(group,'button',ident,left=x,top=173,width=width,height=74,font='font30_title',label=label,
            align='center',aligny='center',textoffsetx=0,textoffsety=0,textcolor='FFC4C4C4',focusedcolor='FF000000')
        ET.SubElement(button,'texturefocus',colordiffuse='FFF5F5F7').text='rounded-rect.png';ET.SubElement(button,'texturenofocus').text='transparent.png'
        if ident==7601:ET.SubElement(button,'visible').text='String.IsEqual(Window.Property(cleanui.stuff.continue_available),true)'
    node(group,'textbox',left=130,top=300,width=1200,height=120,font='font27',textcolor='FFBDBDBD',
        label='$INFO[Window.Property(cleanui.stuff.empty_message)]',
        visible='String.IsEqual(Window.Property(cleanui.stuff.empty),true) + !String.IsEqual(Window.Property(cleanui.loading),true)')
    panel=node(group,'panel',4520,left=119,top=275,width=1702,height=805,orientation='vertical',scrolltime=180)
    for tag,focused in [('itemlayout',False),('focusedlayout',True)]:
        item=ET.SubElement(panel,tag,width='425',height='397')
        if focused:image(item,0,0,407,239,'rounded-rect.png','FFF5F5F7',visible='Control.HasFocus(4520)')
        image(item,11,11,385,217,'rounded-rect.png','FF282828')
        picture=image(item,11,11,385,217,'$INFO[ListItem.Property(cleanui.display_art)]')
        picture.find('texture').set('background','true');picture.find('aspectratio').text='scale'
        node(item,'textbox',left=11,top=245,width=385,height=68,font='font25_title',textcolor='FFF5F5F7',label='$INFO[ListItem.Label]')
        node(item,'label',left=11,top=316,width=385,height=40,font='font27',textcolor='FFBDBDBD',label='$INFO[ListItem.Property(cleanui.stuff_meta)]',aligny='center')
    for control in controls.findall("control[@type='image']"):
        if control.findtext('texture')=='hbo-max-logo.png':
            visible=control.find('visible')
            if visible is None:visible=ET.SubElement(control,'visible')
            visible.text='!String.IsEqual(Window.Property(cleanui.screen.kind),search) + !String.IsEqual(Window.Property(cleanui.screen.kind),watchlist) + !String.IsEqual(Window.Property(cleanui.screen.kind),continue_watching)'
    ET.indent(root,space='  ');PATH.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n')


if __name__=='__main__':build()
