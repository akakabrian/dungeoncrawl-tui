# wizardry-tui

Terminal-native clean-room reinterpretation of the 1981 Sir-Tech
dungeon crawler **Wizardry: Proving Grounds of the Mad Overlord**.
Six-character party, 8 classes, Mage + Priest spell schools, and the
game's signature ASCII-wireframe first-person dungeon view.

**Clean-room.** No Sir-Tech assets, no decompiled data. All strings,
names, monster tables, and level layouts are original prose inspired
by public mechanical documentation. See `DECISIONS.md`.

## Quick start

```
make venv     # set up .venv, install textual, install package
make run      # play
make qa       # run headless QA harness
```

## Controls

**Castle (default home):**

- `1` Training Grounds (create/review characters)
- `2` Tavern (form party)
- `3` Inn (rest)
- `4` Temple (raise dead)
- `5` Shop
- `6` Descend into the Deep
- `F2`/`F3` save / load
- `?` help

**Dungeon:**

- `W`/`↑` step forward, `S`/`↓` step back
- `A`/`←` turn left, `D`/`→` turn right
- `space`/`enter` interact (stairs, door)
- `M` party status
- `escape` retreat to castle

## Scope

Vertical slice of the original 10-floor dungeon — 3 floors (B1/B2/B3).
Enough to demonstrate doors, stairs, chutes, spinners, teleports, pits,
and a scripted boss encounter.

## License

MIT.  The original Wizardry series is owned by Drinian (formerly
Sir-Tech, then 1259190 Ontario Inc., then Aeria).  This project is not
affiliated with any of them.
