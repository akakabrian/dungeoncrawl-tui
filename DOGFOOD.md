# DOGFOOD — wizardry

_Session: 2026-04-23T13:15:38, driver: pty, duration: 3.0 min_

**PASS** — ran for 1.9m, captured 12 snap(s), 1 milestone(s), 0 blocker(s), 0 major(s).

## Summary

Ran a rule-based exploratory session via `pty` driver. Found no findings worth flagging. Game reached 39 unique state snapshots. Captured 1 milestone shot(s); top candidates promoted to `screenshots/candidates/`. 1 coverage note(s) — see Coverage section.

## Findings

### Blockers

_None._

### Majors

_None._

### Minors

_None._

### Nits

_None._

### UX (feel-better-ifs)

_None._

## Coverage

- Driver backend: `pty`
- Keys pressed: 930 (unique: 37)
- State samples: 58 (unique: 39)
- Score samples: 0
- Milestones captured: 1
- Phase durations (s): A=82.8, B=11.2, C=18.0
- Snapshots: `/home/brian/AI/projects/tui-dogfood/reports/snaps/wizardry-20260423-131344`

Unique keys exercised: /, 1, 2, 3, 4, 5, 6, :, ?, H, R, ], a, c, d, down, enter, escape, f2, h, k, left, m, n, p, q, question_mark, r, right, s, shift+slash, shift+tab, space, up, v, w, z

### Coverage notes

- **[CN1] Phase B exited early due to saturation**
  - State hash unchanged for 10 consecutive samples during the stress probe; remaining keys skipped.

## Milestones

| Event | t (s) | Interest | File | Note |
|---|---|---|---|---|
| first_input | 0.3 | 0.0 | `wizardry-20260423-131344/milestones/first_input.txt` | key=enter |
