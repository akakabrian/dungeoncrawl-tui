"""Floor layouts.  Three hand-authored floors, B1 / B2 / B3.

Encoded as a grid of single-char tokens.  Build functions convert the
tokens into the dense wall/door/feature packing from tiles.py.

Token legend:
  '#'  solid rock (impassable void — outside map)
  '.'  floor
  '+'  door (walkable, and renders as a door face)
  '^'  stairs up
  'v'  stairs down
  '>'  exit to castle (only on floor 1 — always paired with stairs up)
  'X'  chute (falls one floor)
  'S'  spinner
  'T'  teleport trap
  'D'  dark area (still floor)
  'P'  pit trap (floor but damages)
  'B'  boss marker (floor)
  '@'  start position (floor, also a player spawn hint)

The grids are 20x20.  Walls are *between* cells — computed by
`cell_has_wall(n, x, y, dir)` helpers.  In our text grid, the convention
is: if tile (x, y) is '#' and tile (x, y-1) is floor, there is a wall on
the north side of (x, y-1).  Doors ('+') are floor tiles that also emit
a door on all adjacent-wall sides.
"""
from __future__ import annotations

from . import tiles as T

MAP_W = 20
MAP_H = 20


# ---- floor B1 -----------------------------------------------------------

B1 = [
    "####################",
    "#..................#",
    "#.######.#####.###.#",
    "#.#....#.#...#.#.#.#",
    "#.#.@..+.+...#.#.#.#",
    "#.#....#.#...#.#.#.#",
    "#.######.#####.#.#.#",
    "#................#.#",
    "######.#######.#.#.#",
    "#....#.#.....#.#.#.#",
    "#..v.#.+..S..#.#.+.#",
    "#....#.#.....#.#...#",
    "######.#.#####.#####",
    "#......#...........#",
    "#.####.###########.#",
    "#.#..#.#.........#.#",
    "#.#..+.+...T.....+.#",
    "#.#..#.#.........#.#",
    "#.####.###########>#",
    "####################",
]


# ---- floor B2 -----------------------------------------------------------

B2 = [
    "####################",
    "#^..#..............#",
    "##.##.#####.########",
    "#..#..#...#........#",
    "#.##.##.#.########.#",
    "#....#..#.#......#.#",
    "####.#.##.#.####.+.#",
    "#....#.#..#.#DDD.#.#",
    "#.##.#.#.##.#DDD.#.#",
    "#.#..#.#..#.#DDD.#.#",
    "#.#.##.##.+.####.#.#",
    "#.#..#..#.#......#.#",
    "#.##.##.#.########.#",
    "#X#..#.P#..........#",
    "#.##.##.############",
    "#....#..............",
    "####.####.##########",
    "#.S..#.v..#........#",
    "#....#....#........#",
    "####################",
]


# ---- floor B3 -----------------------------------------------------------

B3 = [
    "####################",
    "#^........#........#",
    "#.########.########.",
    "#.#......#.#......#.",
    "#.#.####.+.+.####.#.",
    "#.#.#..#.#.#.#..#.#.",
    "#.#.#.##.#.#.##.#.#.",
    "#.#.#..#.#.#.#..#.#.",
    "#.+.####.#.#.####.+.",
    "#.#......#.#......#.",
    "#.########.########.",
    "#..................#",
    "##########.#########",
    "#.................+#",
    "#.###############.##",
    "#.#.............#..#",
    "#.#..B..........+..#",
    "#.#.............#..#",
    "#.###############..#",
    "####################",
]


FLOORS = {"B1": B1, "B2": B2, "B3": B3}


# ---- build -------------------------------------------------------------

_FEATURE_CODES = {
    "v": T.FEAT_STAIRS_DOWN,
    "^": T.FEAT_STAIRS_UP,
    ">": T.FEAT_EXIT,
    "X": T.FEAT_CHUTE,
    "S": T.FEAT_SPINNER,
    "T": T.FEAT_TELEPORT,
    "D": T.FEAT_DARK,
    "P": T.FEAT_PIT,
    "B": T.FEAT_BOSS,
}

_FLOOR_TOKENS = {".", "@", "v", "^", ">", "X", "S", "T", "D", "P", "B", "+"}
_DOOR_TOKENS = {"+"}


def _is_passable_char(c: str) -> bool:
    return c in _FLOOR_TOKENS


def build_floor(floor_key: str) -> tuple[list[list[int]], tuple[int, int], int]:
    """Build floor `floor_key`.

    Returns (grid, start_xy, facing_hint_dir).
    """
    if floor_key not in FLOORS:
        raise KeyError(f"unknown floor {floor_key}")
    raw = FLOORS[floor_key]
    h = len(raw)
    w = max(len(row) for row in raw)
    # Pad rows to w.
    raw = [row.ljust(w, "#") for row in raw]
    grid: list[list[int]] = [[0] * w for _ in range(h)]
    start_xy: tuple[int, int] | None = None

    def passable(x: int, y: int) -> bool:
        if not (0 <= x < w and 0 <= y < h):
            return False
        return _is_passable_char(raw[y][x])

    for y in range(h):
        for x in range(w):
            ch = raw[y][x]
            if not _is_passable_char(ch):
                continue
            walls = 0
            doors = 0
            # Check each direction neighbour.  If neighbour impassable → wall.
            # Exception: if we're a door tile ('+'), all passable sides get a
            # door, solid sides get a wall.
            for dir_idx, (dx, dy) in enumerate(T.DIR_DELTA):
                nx, ny = x + dx, y + dy
                if not passable(nx, ny):
                    walls |= T.DIR_BIT[dir_idx]
            # Door bits: a '+' cell registers doors on passable sides, and
            # also the *neighbour* passable cells should register a door on
            # their opposite side.  We do a second pass to fill neighbour-
            # side doors below.
            if ch == "+":
                for dir_idx, (dx, dy) in enumerate(T.DIR_DELTA):
                    nx, ny = x + dx, y + dy
                    if passable(nx, ny):
                        doors |= (T.DIR_BIT[dir_idx] << 4)
            # Feature.
            feat = _FEATURE_CODES.get(ch, T.FEAT_NONE)
            grid[y][x] = T.cell(walls, doors, feat)
            if ch == "@" and start_xy is None:
                start_xy = (x, y)

    # Second pass: neighbours of door cells gain matching door bit on their
    # side facing the door.
    for y in range(h):
        for x in range(w):
            if raw[y][x] != "+":
                continue
            for dir_idx, (dx, dy) in enumerate(T.DIR_DELTA):
                nx, ny = x + dx, y + dy
                if not passable(nx, ny):
                    continue
                opp_bit = T.DIR_BIT[T.dir_back(dir_idx)]
                grid[ny][nx] |= (opp_bit << 4)   # door on neighbour's side

    # Pick a start if no '@' sentinel in this floor.
    if start_xy is None:
        # Find a floor cell near stairs-up or first passable.
        for y in range(h):
            for x in range(w):
                c = grid[y][x]
                if T.is_void(c):
                    continue
                if T.feature(c) == T.FEAT_STAIRS_UP or T.feature(c) == T.FEAT_EXIT:
                    start_xy = (x, y)
                    break
            if start_xy is not None:
                break
        if start_xy is None:
            for y in range(h):
                for x in range(w):
                    if not T.is_void(grid[y][x]):
                        start_xy = (x, y)
                        break
                if start_xy is not None:
                    break
    assert start_xy is not None, f"no floor cells in {floor_key}"
    return grid, start_xy, T.DIR_N


# Ordered floor list for progression.
FLOOR_KEYS = ["B1", "B2", "B3"]


def next_floor_down(current: str) -> str | None:
    if current not in FLOOR_KEYS:
        return None
    idx = FLOOR_KEYS.index(current)
    if idx + 1 < len(FLOOR_KEYS):
        return FLOOR_KEYS[idx + 1]
    return None


def next_floor_up(current: str) -> str | None:
    if current not in FLOOR_KEYS:
        return None
    idx = FLOOR_KEYS.index(current)
    if idx > 0:
        return FLOOR_KEYS[idx - 1]
    return None
