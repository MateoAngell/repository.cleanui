"""Small control panel for the automatic private recorder."""
import json
import xbmcaddon
import xbmcgui
from core import ADDON, snapshot, export
from protocol import snapshot_input


def main():
    addon = xbmcaddon.Addon(ADDON)
    enabled = addon.getSetting('capture_enabled') != 'false'
    dialog = xbmcgui.Dialog()
    choice = dialog.select('Clean UI Diagnóstico', [
        'Estado actual', 'Desactivar registro automático' if enabled else 'Activar registro automático',
        'Exportar informe privado (opcional)'])
    if choice == 0:
        dialog.textviewer('Estado actual (null = no disponible)',
                          json.dumps(snapshot_input(snapshot(True)), indent=2, ensure_ascii=False))
    elif choice == 1:
        addon.setSetting('capture_enabled', 'false' if enabled else 'true')
        dialog.ok('Diagnóstico', 'Registro automático desactivado.' if enabled else
                  'Registro automático activado. Solo datos técnicos locales, sin envío a Internet.')
    elif choice == 2:
        export()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        xbmcgui.Dialog().ok('Diagnóstico', 'No se pudo completar. Audio y búferes no se han cambiado.')
