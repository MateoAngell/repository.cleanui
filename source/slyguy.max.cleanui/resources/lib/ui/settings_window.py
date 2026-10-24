"""TV presentation of existing SlyGuy categories and setting handlers.

Values, confirmations, restrictions and persistence remain owned by SlyGuy.
"""
import xbmcgui
from . import constants as C

CATEGORY_LIST = 6100
SETTING_LIST = 6200


class SettingsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.root_category = kwargs.pop('root_category')
        self.categories = []
        self.rows = []
        self.history = []
        self.category_index = 0
        self._selecting = False
        super(SettingsWindow, self).__init__(*args, **kwargs)

    def onInit(self):
        self.setProperty('cleanui.settings.account_notice',
                         'Para gestionar tu cuenta o suscripción, usa la app oficial de Max.')
        self._load_categories()
        self.setFocus(self.getControl(CATEGORY_LIST))

    def _load_categories(self):
        # Root-level actions/settings remain reachable instead of being dropped.
        self.categories = ([self.root_category] if list(self.root_category.settings) else [])
        self.categories += list(self.root_category.categories)
        control = self.getControl(CATEGORY_LIST)
        control.reset()
        items = [xbmcgui.ListItem(label=('General' if category is self.root_category else str(category.label)),
                                  offscreen=True) for category in self.categories]
        control.addItems(items)
        self.category_index = min(self.category_index, max(0, len(items) - 1))
        if items:
            control.selectItem(self.category_index)
            self.history = [self.categories[self.category_index]]
        else:
            self.history = []
        self._load_rows()

    def _load_rows(self, selection=0):
        control = self.getControl(SETTING_LIST)
        control.reset()
        self.rows = []
        if self.history:
            category = self.history[-1]
            self.setProperty('cleanui.settings.section', str(category.label))
            self.rows = [('category', child) for child in category.categories] if category is not self.root_category else []
            self.rows += [('setting', setting) for setting in category.settings]
        else:
            self.setProperty('cleanui.settings.section', 'Ajustes')
        items = []
        for kind, obj in self.rows:
            if kind == 'category':
                label, description = str(obj.label), 'Abrir opciones'
            elif getattr(obj, '_private_value', False):
                # SlyGuy's generic label can include its value; never expose secrets.
                label, description = str(getattr(obj, '_label', 'Opción privada')), 'Valor privado'
            else:
                label = str(obj.label)
                description = str(obj.description or '')
            item = xbmcgui.ListItem(label=label, offscreen=True)
            item.setProperty('cleanui.settings.description', description)
            item.setProperty('cleanui.settings.arrow', '›' if kind == 'category' else '')
            item.setProperty('cleanui.settings.enabled',
                             'true' if kind == 'category' or obj.is_enabled else 'false')
            items.append(item)
        control.addItems(items)
        if items:
            control.selectItem(min(max(0, selection), len(items) - 1))
        self.setProperty('cleanui.settings.empty', 'false' if items else 'true')
        self.setProperty('cleanui.settings.path', ' / '.join(str(c.label) for c in self.history[1:]))

    def _select_category(self, focus_rows=True):
        index = self.getControl(CATEGORY_LIST).getSelectedPosition()
        if not 0 <= index < len(self.categories):
            return
        self.category_index = index
        self.history = [self.categories[index]]
        self._load_rows()
        if focus_rows and self.rows:
            self.setFocus(self.getControl(SETTING_LIST))

    def onClick(self, control_id):
        if control_id == CATEGORY_LIST:
            self._select_category()
        elif control_id == SETTING_LIST and not self._selecting:
            index = self.getControl(SETTING_LIST).getSelectedPosition()
            if not 0 <= index < len(self.rows):
                return
            kind, obj = self.rows[index]
            if kind == 'category':
                self.history.append(obj)
                self._load_rows()
                return
            # Dynamic visibility and enabled checks, confirmations and typed input
            # are performed by the original on_select method, without copying save logic.
            if not obj.is_visible:
                self._load_rows(index)
                return
            self._selecting = True
            try:
                obj.on_select()
            except Exception:
                xbmcgui.Dialog().ok('Ajustes', 'No se pudo completar esta opción. Inténtalo de nuevo.')
            finally:
                self._selecting = False
                self._load_rows(index)

    def onAction(self, action):
        action_id = action.getId()
        focus = self.getFocusId()
        if action_id in C.ACTION_BACK:
            if focus == SETTING_LIST:
                if len(self.history) > 1:
                    self.history.pop()
                    self._load_rows()
                else:
                    self.setFocus(self.getControl(CATEGORY_LIST))
            else:
                self.close()
        elif action_id in C.ACTION_RIGHT and focus == CATEGORY_LIST:
            self._select_category()
        elif action_id in C.ACTION_LEFT and focus == SETTING_LIST:
            self.setFocus(self.getControl(CATEGORY_LIST))
        elif action_id in (1, 2, 3, 4) and focus == CATEGORY_LIST:
            index = self.getControl(CATEGORY_LIST).getSelectedPosition()
            if index != self.category_index:
                self._select_category(focus_rows=False)


def show_settings(addon_path, root_category=None):
    if root_category is None:
        from slyguy.settings.types import Category
        root_category = Category.get(0)
    window = SettingsWindow('ui_settings.xml', addon_path, 'Default', '1080i', root_category=root_category)
    window.doModal()
    del window
