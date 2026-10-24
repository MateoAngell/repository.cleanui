# Max TV presentation reference and boundaries

Reference: installed Android TV Max **7.14.0.69**, base APK SHA-256
`55e0456e7bca669e118beb89e5090793c195f1d0121bf23bb0e3b8b5fecf5a15`.
REA package evidence: `ev_29be6f4c3d7ba9e18a394cad6a029a73f269c9a66d6202e151b331670799a9f9`.

The private research archive retains the original APKs, decoded You.i layouts,
tokens, and timestamped 1920×1080 runtime captures. Those private artifacts are
not part of the addon or repository sources. Static scene/anchor values alone
were not treated as observed Android runtime positions.

## Implemented presentation

- Profiles: observed title/row placement, 260px idle and304px focused avatars,
  neutral circular background behind transparent avatars, native selection halo,
  and320px cell spacing. Counts come from the existing service profile list.
- Home: the existing server-provided synopsis is now visible, with separated
  logo, metadata, summary and actions. No fabricated release or quality badges.
- Navigation: profile and Mis cosas appear above search only when expanded;
  section icons match the measured24px visible glyph scale (HBO wordmark retains
  its wider scale). Settings calls the existing SlyGuy setting actions.
- Search: observed Spanish6-column keyboard including ñ and all digits, delete,
  space and clear; actual query results use385×217 landscape cards in3columns.
  Search uses only the existing `build_search` and session metadata worker.
  The latest query supersedes an earlier pending result. Query and selected
  result position live in the existing Screen/window state used after playback.
- My Stuff: the existing saved-list cards use the observed4-column385×217
  landscape grid, title and tab placement. Continue watching is shown only when
  an actual nonempty Screen model is available; the current backend explicitly
  returns an empty model, so no synchronization or progress is fabricated.
- Entity: display-only duration formatting, existing play/watchlist/trailer
  actions, full synopsis via Más, and real navigation relayed to the live parent
  catalogue with owner/request validation and a bounded native GUI queue.
- Series: horizontal season chips invoke the existing season switch;385×217
  episode cards use a460px step, two-line titles and genuine metadata. The
  background remains fixed while a compact logo anchors the lower episode view.
  The header uses an episode only when its existing play path already matches
  the repository-selected header action. No remote resume/progress is invented.

## Deliberate boundaries and remaining comparison work

The existing backend cannot create/edit/delete profiles or manage account PINs,
plan or billing. Inert copies of those official controls are not included.

A blank search displays an instruction instead of fabricating the official
personalized recommendations, since the existing search builder exposes query
results rather than that recommendation layout.

The fonts remain the installed Kodi Estuary fonts. `WindowXML` loads its fallback
texture path but does not independently load an addon Font.xml. No global skin
or font file is changed. Type and procedural ambient textures are approximations
that require comparison in the actual renderer, not a claim of pixel identity.

The existing full-text detail panel is reused for expanded synopsis and episode
information; it is not claimed to duplicate an unobserved official modal.

Static/mock tests verify data routing, stale-result rejection, scope protection,
geometry boundaries and handoff contracts. They do not prove DRM playback,
audible audio, Android Surface behavior or Chromecast performance. The separate
runtime QA record must identify which screens and transitions were actually
observed before publication.

## Developer regeneration

The `build_*` files in this test directory regenerate our geometric textures or
native XML controls using Python/Pillow. Pillow is a build-time dependency only;
the Kodi addon has no new runtime dependencies. The published source guard
continues to verify the backend, intro, session and playback files unchanged.
