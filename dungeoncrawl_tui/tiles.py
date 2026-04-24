"""Tile IDs for dungeon floors + per-tile behaviour hints.

Wizardry's tile grid is cells-and-walls: each cell has a floor tile plus
optional walls on N/E/S/W edges, doors on those edges, etc. For
simplicity v1 uses a denser encoding where the tile id tells you the
passability of the cell AND whether a door exists on a side.

Since Wizardry has **orthogonal walls-between-cells** and we want to
represent doors, we use the classic dungeon-crawler trick:
   each cell has a 4-bit wall mask (N=1 E=2 S=4 W=8)
   each cell has a 4-bit door mask (N=16 E=32 S=64 W=128)
   plus 8 bits of feature (floor type / stairs / chute / ...).

So one cell = 16 bits. Stored as a simple int in the grid.
"""
from __future__ import annotations

# --- wall mask bits ----
WALL_N = 1
WALL_E = 2
WALL_S = 4
WALL_W = 8
WALL_MASK = 15

# --- door mask bits (same directions, shifted up 4) ----
DOOR_N = 16
DOOR_E = 32
DOOR_S = 64
DOOR_W = 128
DOOR_MASK = 240

# --- cell validity bit ----
# Any passable cell (floor / door / stairs / etc.) has PASS_BIT set.
# Void cells (outside-map rock) have value 0.  This lets us distinguish
# "floor with no walls, no doors, no feature" from "void" — both would
# otherwise collapse to 0.
PASS_BIT = 1 << 16

# --- feature codes (top byte) ----
FEAT_SHIFT = 8
FEAT_NONE = 0
FEAT_STAIRS_UP = 1
FEAT_STAIRS_DOWN = 2
FEAT_CHUTE = 3
FEAT_SPINNER = 4
FEAT_TELEPORT = 5
FEAT_DARK = 6          # dim rendering on this tile
FEAT_PIT = 7           # damage trap
FEAT_BOSS = 8          # scripted encounter
FEAT_EXIT = 9          # back to castle (on floor 1 only)
FEAT_ENCOUNTER = 10    # fixed encounter marker

_FEAT_NAMES = {
    FEAT_NONE: "floor",
    FEAT_STAIRS_UP: "stairs up",
    FEAT_STAIRS_DOWN: "stairs down",
    FEAT_CHUTE: "chute",
    FEAT_SPINNER: "spinner",
    FEAT_TELEPORT: "teleport",
    FEAT_DARK: "dark",
    FEAT_PIT: "pit",
    FEAT_BOSS: "boss chamber",
    FEAT_EXIT: "stairs to castle",
    FEAT_ENCOUNTER: "encounter",
}


# --- helpers --------------------------------------------------------------

def walls(cell: int) -> int:
    return cell & WALL_MASK


def doors(cell: int) -> int:
    return cell & DOOR_MASK


def feature(cell: int) -> int:
    return (cell >> FEAT_SHIFT) & 0xFF


def has_wall(cell: int, dir_bit: int) -> bool:
    return bool(cell & dir_bit)


def has_door(cell: int, dir_bit: int) -> bool:
    door_bit = dir_bit << 4
    return bool(cell & door_bit)


def is_open(cell: int, dir_bit: int) -> bool:
    """No wall in this direction (OR door — doors are walkable)."""
    # Doors can coexist with walls in our encoding (door implies passable).
    if cell & (dir_bit << 4):
        return True
    return not (cell & dir_bit)


def feature_name(cell: int) -> str:
    return _FEAT_NAMES.get(feature(cell), "floor")


# --- direction constants & helpers ----------------------------------------

DIR_N = 0
DIR_E = 1
DIR_S = 2
DIR_W = 3

# (dx, dy) — y increases southward.
DIR_DELTA = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# Bit for the wall on that side of the cell.
DIR_BIT = [WALL_N, WALL_E, WALL_S, WALL_W]

DIR_NAME = ["N", "E", "S", "W"]


def dir_left(d: int) -> int:
    return (d + 3) % 4


def dir_right(d: int) -> int:
    return (d + 1) % 4


def dir_back(d: int) -> int:
    return (d + 2) % 4


# --- cell packing ---------------------------------------------------------

def cell(walls_mask: int = 0, doors_mask: int = 0, feat: int = 0) -> int:
    return (PASS_BIT
            | (walls_mask & WALL_MASK)
            | (doors_mask & DOOR_MASK)
            | ((feat & 0xFF) << FEAT_SHIFT))


def is_void(cell: int) -> bool:
    return (cell & PASS_BIT) == 0
