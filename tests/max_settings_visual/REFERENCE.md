# Settings TV frontend

Reference: `work/max040/runtime/official-settings.png` (1920×1080).
Measured layout: title x130/top~100, categories x130/y232/width385,
80-high category fill with88 step; content x604, width1187, first card y288.
Dark191919 cards, white focus. There is no decorative inert sidebar.

Integration (presentation method only):

```python
def _open_settings(self):
    from .settings_window import show_settings
    show_settings(self.controller.addon_path)
```

The actual Category/Setting interfaces were read from backed-up installed
`script.module.slyguy/resources/modules/slyguy/settings/types.py` inside
`outputs/recovery-2026-10-24/kodi-current.tar`, not guessed. Category.settings
and .categories already filter visibility/order; Setting.on_select owns enabled
reasons, typed editors, confirmations and persistence. This frontend does not
call value setters or storage. Root-level actions remain under General.
Unsupported account/subscription controls are an informational notice only.
Private-value settings render their title alone without reading their generic
label/value/description. No sensitive details are logged on handler errors.

Six mock tests exercise real category object identity/handler delegation,
hierarchy and Back, disabled explanation delegation, late-hidden option guard,
private-value non-read, exception latch release, empty categories and measured
XML/focus links. These do not establish real Kodi rendering or input latency.
Run local Kodi checks: scroll every category/row, nested Back, Bool update,
Enum/text cancellation, disabled reason, handler confirmation and long labels.
No screenshot of this new window in Kodi has been asserted by these tests.
