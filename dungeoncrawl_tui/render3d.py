"""ASCII wireframe first-person renderer.

This is Wizardry's signature look: a 3-depth corridor wireframe with
doors, walls, and openings ahead.  We use Unicode box-drawing chars
composed into a fixed 40x15 frame.

Rendering algorithm:

1. Compute `cells[d]` for depth d in {0, 1, 2} = cell ahead, 2 ahead,
   3 ahead (if passable in a straight line).
2. For each depth d, figure out what's on left, right, front of that
   cell: wall / door / open.
3. Composite layers back-to-front: depth 2 first (smallest box), then
   depth 1, then depth 0 (largest box closest).

Instead of a per-feature layer system, we precompute a base frame of
nested boxes and then stamp on door/opening overlays.  The base frame
gives the classic "tunnel receding into the distance" look.
"""
from __future__ import annotations

from typing import List

from . import tiles as T


# Frame dimensions — tuned to fit in the map panel.
FRAME_W = 40
FRAME_H = 15


# --- base frame: three nested boxes centred in the viewport ---

# Outer box (depth-0, closest).  Corners + walls drawn at the frame edge.
#
# The "receding" effect is faked by nesting boxes whose walls are
# drawn with diagonal lines connecting their corners to the corners of
# the next box inside.
#
# Layout (depths are 0 = nearest, increasing into the distance):
#
#   (0,0)                              (W-1, 0)
#     ╔══════════════════════════════╗
#     ║╲                            ╱║
#     ║ ╲ ╔════════════════════╗ ╱ ║        <- depth-1 box
#     ║  ╲║╲                  ╱║╱  ║
#     ║   ║ ╔═══════════════╗ ║   ║        <- depth-2 box
#     ║   ║ ║               ║ ║   ║
#     ║   ║ ╚═══════════════╝ ║   ║
#     ║  ╱║╱                  ╲║╲  ║
#     ║ ╱ ╚════════════════════╝ ╲ ║
#     ║╱                            ╲║
#     ╚══════════════════════════════╝

# Box rects: (left, top, right, bottom) inclusive, per depth.
BOX_RECTS = [
    (0, 0, FRAME_W - 1, FRAME_H - 1),         # depth 0 — full frame
    (4, 2, FRAME_W - 5, FRAME_H - 3),         # depth 1
    (9, 4, FRAME_W - 10, FRAME_H - 5),        # depth 2
    (13, 6, FRAME_W - 14, FRAME_H - 7),       # depth 3 (end-of-corridor / dead-end)
]


# --- character drawing primitives ---------------------------------------

def _blank_frame() -> list[list[str]]:
    return [[" "] * FRAME_W for _ in range(FRAME_H)]


def _draw_box(frame: list[list[str]], rect: tuple[int, int, int, int],
              style: str = "solid") -> None:
    """Draw a rectangle using box-drawing chars."""
    l, t, r, b = rect
    if style == "solid":
        tl, tr, bl, br = "╔", "╗", "╚", "╝"
        hz, vt = "═", "║"
    else:
        tl, tr, bl, br = "┌", "┐", "└", "┘"
        hz, vt = "─", "│"
    for x in range(l + 1, r):
        frame[t][x] = hz
        frame[b][x] = hz
    for y in range(t + 1, b):
        frame[y][l] = vt
        frame[y][r] = vt
    frame[t][l] = tl
    frame[t][r] = tr
    frame[b][l] = bl
    frame[b][r] = br


def _draw_line(frame: list[list[str]], x0: int, y0: int,
               x1: int, y1: int, ch: str) -> None:
    """Draw a simple line (used for the receding diagonals)."""
    dx = x1 - x0
    dy = y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return
    for i in range(1, steps):
        xi = round(x0 + dx * i / steps)
        yi = round(y0 + dy * i / steps)
        if 0 <= xi < FRAME_W and 0 <= yi < FRAME_H:
            if frame[yi][xi] == " ":
                frame[yi][xi] = ch


def _draw_diagonals(frame: list[list[str]], near: tuple[int, int, int, int],
                    far: tuple[int, int, int, int]) -> None:
    """Connect the 4 corners of `far` to `near` with / and \\ lines."""
    nl, nt, nr, nb = near
    fl, ft, fr, fb = far
    _draw_line(frame, nl, nt, fl, ft, "╲")   # top-left diagonal
    _draw_line(frame, nr, nt, fr, ft, "╱")   # top-right diagonal
    _draw_line(frame, nl, nb, fl, fb, "╱")   # bottom-left diagonal
    _draw_line(frame, nr, nb, fr, fb, "╲")   # bottom-right diagonal


# --- features overlaid on the base frame -------------------------------

def _draw_door_front(frame: list[list[str]], rect: tuple[int, int, int, int]) -> None:
    """Stamp a door shape on the front wall of a box (the back wall from
    the player's view — depth N sees depth N+1 as the far wall)."""
    l, t, r, b = rect
    mid_x = (l + r) // 2
    door_h = max(2, (b - t) - 2)
    door_top = t + 1
    door_bottom = t + door_h
    door_left = mid_x - 1
    door_right = mid_x + 1
    # Draw door frame.
    for y in range(door_top, door_bottom + 1):
        if 0 <= y < FRAME_H:
            if 0 <= door_left < FRAME_W:
                frame[y][door_left] = "│"
            if 0 <= door_right < FRAME_W:
                frame[y][door_right] = "│"
    if 0 <= door_top < FRAME_H:
        frame[door_top][door_left] = "┌"
        frame[door_top][door_right] = "┐"
        for x in range(door_left + 1, door_right):
            frame[door_top][x] = "─"


def _draw_door_side(frame: list[list[str]], rect: tuple[int, int, int, int],
                    side: str) -> None:
    """Stamp a door shape on the left or right side wall of a depth box.

    Drawn as two vertical-door-frame chars inside the angled wall.
    """
    l, t, r, b = rect
    if side == "left":
        wall_x = l
    else:
        wall_x = r
    mid_y = (t + b) // 2
    # Door slot: 3-4 rows around mid_y.
    height = max(2, (b - t) // 2)
    top_y = mid_y - height // 2
    bot_y = top_y + height
    if 0 <= wall_x < FRAME_W:
        for y in range(top_y, bot_y + 1):
            if 0 <= y < FRAME_H:
                frame[y][wall_x] = "│"


def _draw_opening_front(frame: list[list[str]], rect: tuple[int, int, int, int]) -> None:
    """Remove the front wall of a box — corridor continues."""
    l, t, r, b = rect
    # Leave corners so the frame doesn't look broken; clear the top wall
    # between corners.
    for x in range(l + 1, r):
        if 0 <= x < FRAME_W and 0 <= t < FRAME_H:
            frame[t][x] = " "


def _draw_opening_side(frame: list[list[str]], rect: tuple[int, int, int, int],
                       side: str) -> None:
    """Remove the side wall of a box — branching corridor on that side."""
    l, t, r, b = rect
    wall_x = l if side == "left" else r
    if 0 <= wall_x < FRAME_W:
        for y in range(t + 1, b):
            if 0 <= y < FRAME_H:
                frame[y][wall_x] = " "


# --- main render entry point -------------------------------------------

def _cell_open_sides(grid: list[list[int]], x: int, y: int,
                     facing: int) -> tuple[str, str, str]:
    """Given a cell and the party's facing, classify (left, front, right).

    Returns one of 'wall' / 'door' / 'open' per side.
    """
    W = len(grid[0])
    H = len(grid)
    if not (0 <= x < W and 0 <= y < H):
        return ("wall", "wall", "wall")
    c = grid[y][x]
    if T.is_void(c):   # void — outside map
        return ("wall", "wall", "wall")

    left_dir = T.dir_left(facing)
    right_dir = T.dir_right(facing)
    front_dir = facing

    def side_state(dir_idx: int) -> str:
        bit = T.DIR_BIT[dir_idx]
        if T.has_door(c, bit):
            return "door"
        if T.has_wall(c, bit):
            return "wall"
        return "open"

    return side_state(left_dir), side_state(front_dir), side_state(right_dir)


def _step_forward(x: int, y: int, facing: int) -> tuple[int, int]:
    dx, dy = T.DIR_DELTA[facing]
    return x + dx, y + dy


def _blocked_forward(grid: list[list[int]], x: int, y: int, facing: int) -> bool:
    """Return True if the party can *see* past (x, y) in `facing` direction.

    We use the front side-state: wall blocks; door partial-blocks (we
    still treat door as stopping visibility — classic corridor rule).
    """
    _, front, _ = _cell_open_sides(grid, x, y, facing)
    return front != "open"


def render_wireframe(grid: list[list[int]], px: int, py: int,
                     facing: int, dark: bool = False) -> list[str]:
    """Return a list of FRAME_H strings of exactly FRAME_W cells each."""
    frame = _blank_frame()

    # Draw outermost box always (the walls immediately to the player's
    # left / right / ahead).
    rect0 = BOX_RECTS[0]
    _draw_box(frame, rect0, "solid")

    # Walk forward up to 3 cells for depth 1, 2, 3 boxes.
    cell_x, cell_y = px, py
    facing_here = facing
    visible_depth = 0
    for depth in range(3):
        # Check if we can see past the current cell into the next.
        if _blocked_forward(grid, cell_x, cell_y, facing_here):
            break
        cell_x, cell_y = _step_forward(cell_x, cell_y, facing_here)
        if not (0 <= cell_x < len(grid[0]) and 0 <= cell_y < len(grid)):
            break
        if T.is_void(grid[cell_y][cell_x]):
            break
        visible_depth = depth + 1
        rect = BOX_RECTS[depth + 1]
        _draw_box(frame, rect, "solid")
        # Diagonals connecting near box to this far box.
        _draw_diagonals(frame, BOX_RECTS[depth], rect)

    # Now draw features:
    # - For the current cell, left/right walls are in BOX_RECTS[0]; doors on
    #   left/right of BOX_RECTS[0] indicate nearby doors.
    # - For each visible_depth d>=1, the left/right walls of box d-1 show
    #   doors to those sides of the cell we stepped into.
    #
    # Conceptually: after stepping d times, we're examining cell_d.  The
    # side states of cell_d at (facing) tell us whether box-d's left/right
    # walls should look like doors.  For d=0 (current cell), that's
    # BOX_RECTS[0].

    def apply_sides(cell_x_d: int, cell_y_d: int, facing_d: int,
                    box_idx: int) -> None:
        left, _, right = _cell_open_sides(grid, cell_x_d, cell_y_d, facing_d)
        rect = BOX_RECTS[box_idx]
        if left == "door":
            _draw_door_side(frame, rect, "left")
        elif left == "open":
            _draw_opening_side(frame, rect, "left")
        if right == "door":
            _draw_door_side(frame, rect, "right")
        elif right == "open":
            _draw_opening_side(frame, rect, "right")

    # Current cell (player standing) — sides visible at depth 0 box.
    apply_sides(px, py, facing, 0)

    # Walk again to annotate deeper cells.
    cell_x, cell_y = px, py
    for depth in range(visible_depth):
        cell_x, cell_y = _step_forward(cell_x, cell_y, facing)
        apply_sides(cell_x, cell_y, facing, depth + 1)

    # Determine the "front" feature of the deepest visible cell: if that
    # cell's front is a door, draw a door on the back wall of the deepest
    # box; if wall, it's just the box back wall (already drawn).
    # If visible_depth == 3, there's no deeper box — we treat the inmost
    # box's back wall as the end.
    cell_x, cell_y = px, py
    for _ in range(visible_depth):
        cell_x, cell_y = _step_forward(cell_x, cell_y, facing)
    # front-state of the last-visible cell
    _, front_state, _ = _cell_open_sides(grid, cell_x, cell_y, facing)
    # The "back wall" is the far wall of BOX_RECTS[visible_depth].
    far_box_idx = visible_depth
    far_rect = BOX_RECTS[far_box_idx] if far_box_idx < len(BOX_RECTS) \
        else BOX_RECTS[-1]
    if front_state == "door":
        _draw_door_front(frame, far_rect)
    # (opening at the far end means we should have stepped further, which
    # our loop did; so this means there's a wall or door.  Default wall is
    # already drawn.)

    # Feature overlay: if the *current cell* has a stairs-down feature,
    # draw a down-arrow.  Similarly stairs-up, boss, etc.
    cur_cell = grid[py][px] if 0 <= py < len(grid) and 0 <= px < len(grid[0]) else 0
    feat = T.feature(cur_cell)
    _feature_overlay(frame, feat)

    if dark:
        # Dim the frame by substituting walls with dimmer variants and
        # erasing far depths.
        frame = _dim_frame(frame, visible_depth)

    # Assemble into list[str].
    return ["".join(row) for row in frame]


# --- overlays ----------------------------------------------------------

def _feature_overlay(frame: list[list[str]], feat: int) -> None:
    """Draw a small icon near the bottom-middle of the frame when the
    current tile has a notable feature."""
    if feat == T.FEAT_NONE:
        return
    label = {
        T.FEAT_STAIRS_DOWN: " ↓ STAIRS DOWN ",
        T.FEAT_STAIRS_UP:   " ↑ STAIRS UP ",
        T.FEAT_EXIT:        " ↑ TO CASTLE ",
        T.FEAT_CHUTE:       " ! CHUTE ! ",
        T.FEAT_SPINNER:     " ↻ SPINNER ",
        T.FEAT_TELEPORT:    " ? TELEPORT ",
        T.FEAT_PIT:         " × PIT × ",
        T.FEAT_BOSS:        " ★ OMINOUS ★ ",
        T.FEAT_ENCOUNTER:   " ⚔ ENCOUNTER ",
    }.get(feat)
    if not label:
        return
    y = FRAME_H - 2
    x = (FRAME_W - len(label)) // 2
    for i, ch in enumerate(label):
        if 0 <= x + i < FRAME_W and 0 <= y < FRAME_H:
            frame[y][x + i] = ch


def _dim_frame(frame: list[list[str]], visible_depth: int) -> list[list[str]]:
    """Simulate darkness by removing detail from depth 2+ boxes."""
    if visible_depth <= 0:
        return frame
    # Clear inside depth-1 box.
    if len(BOX_RECTS) > 1:
        l, t, r, b = BOX_RECTS[1]
        for y in range(t, b + 1):
            for x in range(l, r + 1):
                if 0 <= y < FRAME_H and 0 <= x < FRAME_W:
                    frame[y][x] = " "
    # Overlay the word "DARK" in the middle.
    label = " DARK "
    y = FRAME_H // 2
    x = (FRAME_W - len(label)) // 2
    for i, ch in enumerate(label):
        if 0 <= x + i < FRAME_W:
            frame[y][x + i] = ch
    return frame


# --- minimap (bottom-left overlay on the map view) -------------------

def render_minimap(grid: list[list[int]], px: int, py: int,
                   facing: int, radius: int = 3) -> list[str]:
    """Small ASCII minimap showing a square around the party."""
    size = radius * 2 + 1
    out: list[str] = []
    for oy in range(-radius, radius + 1):
        row_chars: list[str] = []
        for ox in range(-radius, radius + 1):
            x, y = px + ox, py + oy
            if not (0 <= x < len(grid[0]) and 0 <= y < len(grid)):
                row_chars.append(" ")
                continue
            c = grid[y][x]
            if T.is_void(c):
                row_chars.append("█")   # solid
                continue
            if ox == 0 and oy == 0:
                row_chars.append("@NESW"[1 + facing] if 0 <= facing < 4 else "@")
            else:
                feat = T.feature(c)
                if feat == T.FEAT_STAIRS_DOWN:
                    row_chars.append("v")
                elif feat == T.FEAT_STAIRS_UP:
                    row_chars.append("^")
                elif feat == T.FEAT_EXIT:
                    row_chars.append(">")
                else:
                    row_chars.append("·")
        out.append("".join(row_chars))
    return out
