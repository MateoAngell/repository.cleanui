"""Profile geometry observed in Max TV 7.14.0.69 at 1920 x 1080.

The number of service profiles is authoritative. We never add an inert
"create profile" tile when the existing SlyGuy integration cannot create one.
"""
CANVAS_WIDTH = 1920
PROFILE_CELL = 320
PROFILE_TOP = 386
PROFILE_MAX_VISIBLE = 5
AVATAR_SIZE = 260
FOCUSED_AVATAR_SIZE = 304


def row_geometry(count):
    width = PROFILE_CELL * min(PROFILE_MAX_VISIBLE, max(1, count))
    return (CANVAS_WIDTH - width) // 2, PROFILE_TOP, width
