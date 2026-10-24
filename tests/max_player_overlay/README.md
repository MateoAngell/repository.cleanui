# Max playback presentation prototype — disabled until runtime validation

The new `player_overlay.py` and `ui_player.xml` are not imported by production code. They never open/resolve media and do not modify SlyGuy, DRM, manifests, audio settings, `observe_playback`, controller playback methods, the global skin or keymaps.

## Integration snippets for the parent, after local MP4 validation

In `UIController.__init__`, beside other presentation state:

```python
from .player_overlay import MaxPlayerOverlay
self._max_player_overlay = MaxPlayerOverlay(self)
```

In the existing UI-facing `_play(path)` methods of HomeWindow and DetailWindow, directly before their existing `controller.play(path)` call:

```python
presenter = getattr(self.controller, '_max_player_overlay', None)
if presenter is not None:
    presenter.arm(path)  # Existing plugin route only, exact Max netloc; no URL is executed.
# Keep the original controller.play(path) call unchanged.
```

When the controller's entire presentation session is finished, explicitly call:

```python
presenter = getattr(controller, '_max_player_overlay', None)
if presenter is not None:
    presenter.close()
    controller._max_player_overlay = None
```

The parent must choose an existing **presentation cleanup** point that runs after the complete session, rather than when a child window closes before playback. Do not edit a protected lifecycle method to force this integration through its integrity checks. Dropping the weak controller reference also closes the active presentation worker; explicit cleanup remains required for repeatable native callback disposal.

## Isolation and behavior

- Unarmed observer: no thread, window, media action or player RPC.
- Explicit arm: requires `plugin://slyguy.max.cleanui/...`, exact netloc, no userinfo/port/control characters. It records only a bounded intent, not the path or its parameters.
- Activation: onAVStarted, controller belongs to Max and is processing its playback, live video exists, external session owner is Max or absent for a local launch, and the media is not an addon intro.
- One current generation, observer and worker. Old dialog actions and late stream selections are rejected. A new foreign playback without another Max arm cannot inherit the overlay.
- The transparent dialog stays active while its HUD auto-hides, preserving reception of the next remote action without a keymap. First Back hides visible HUD; Back from the hidden HUD stops through Kodi's public player API, leaving the existing controller to restore navigation.
- Pause/resume and ±10-second seek use public Kodi player methods. Seek is clamped to available duration. Time/progress/title use Kodi GUI info labels; no catalogue polling.
- Audio/subtitle options are queried only on user request. Actual non-sequential stream indices are preserved and revalidated before Player.SetAudioStream/Player.SetSubtitle. No track or service capability is invented.
- EOF, Stop, Error, monitor abort or loss of the controlling session closes the main and child dialogs and releases the worker. Buffering alone hides the HUD but does not terminate media or the observation lifetime.

## Visual evidence and declared differences

The official player could not be traversed in Waydroid because playback did not open; its appearance is **not visually validated**. Static references are `Player_Playback-Controls.layout` (1920×1080), `Player_Player-Scrubber.layout` (1760×12 centered at960,981: top975), quick-actions row (height68), and JSON colors `#f5f5f7/#282828/#191919`.

This prototype uses the existing addon gradient and fonts and text buttons for an explicit, testable control set. Button positions, stream dialog presentation and four-second auto-hide are prototype defaults. They are not claimed identical to the official app. No unsupported Up Next, Skip Intro, preview thumbnails, server progress synchronization or profile actions are added.

## Validation

Run `python -m unittest discover -s tests/max_player_overlay -p 'test_*.py' -q` from the repository root.

The contracts verify isolation, route validation, generations, callback cleanup, weak references, buffering, scope changes, actual stream selection, no recursive builtins, user Back semantics and public player delegation. They do not verify Android surface rendering, focus capture or audible output.

Before activation, the parent must run a local non-DRM video in Kodi and verify: visible video beneath the transparent HUD; controls/seek/pause; both Back steps; hidden-HUD remote reveal; stream selection/cancellation; EOF and errors; repeated activation/disposal; Home and foreign-service transitions. The test apparatus may synthesize a scoped Max intent, but production integration must always arm the actual existing Max plugin path before its unchanged play call. Do not publish as enabled before that validation.
