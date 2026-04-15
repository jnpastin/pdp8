# PDP‑8 Programmer’s Calculator

## Terminal UI Design (80×24 Fixed Layout)

This document defines the **user interface design** for the PDP‑8 Programmer’s Calculator.
The UI is a **rigid 80×24 character TUI**, inspired by classic front panels and Nano‑style interfaces.
The outer border never changes; only interior content swaps.

---

## Global Constraints

- Screen size is **exactly 80 columns × 24 rows**
- Outer border is static and never redraws differently
- No scrolling in main or help views
- Status bar is always exactly **1 line**
- Content area is **22 × 78**

---

## Main Screen Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ PDP‑8 Programmer’s Calculator                                                │
│──────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│                         L     Accumulator                                    │
│                         --- ---------------                                  │
│                          1   111 111 111 111                                 │
│                    Octal:   7   7   7   7                                    │
│                                                                              │
│          Decimal:  signed:     -1    unsigned: 4095                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Command> _                                                                  │
│                                                                              │
│                                                                              │
│                                                                              │
│  Commands:                                                                   │
│        LOAD <n> · + <n> · - <n> · IAC · CIA · & <n> · | <n> · ^ <n>          │
│          CLA    ·  CMA  ·  SET  · CLL · CML ·  STL  ·  RAL  ·  RAR           │
│           BASE <dec|oct|bin>    ·       MODE <signed|unsigned>               │
│                                 (H for help)                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ BASE: DEC | DECIMAL: SIGNED | LAST: CIA                           Q : quit   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Register Display Semantics

- **Link (L)** is visually attached to the accumulator, front‑panel style
- Accumulator bits are shown as **four binary triads**
- Each triad has its **octal digit directly beneath it**
- No explicit "Binary" label is used

Hierarchy:
1. Machine truth (Link + bits)
2. Octal encoding
3. Decimal interpretations

---

## Decimal Interpretation

Decimal values are *interpretations* layered beneath the machine view.
They never affect arithmetic semantics.

```
Decimal:
    signed:   -1
    unsigned: 4095
```

- Signed = 12‑bit two’s‑complement
- Unsigned = pure magnitude

---

## Command Entry

- Single‑line prompt (`Command> `)
- Located in the commands pane, below the pane separator
- One command executes immediately on Enter
- Multiple no‑argument micro‑ops can be given on one line (`CLA CLL IAC`)
- Errors display on the line below the prompt and are cleared on the next entry
- Layout does not change when an error occurs

---

## Inline Command Reference

The main screen includes a **terse, always‑visible command cheat strip** for common operations.
Shown commands are reminders only, not documentation; press `H` for the full help screen.

Two rows of dot‑separated columns, plus a mode and help‑hint row:

```
        LOAD <n> · + <n> · - <n> · IAC · CIA · & <n> · | <n> · ^ <n>
          CLA    ·  CMA  ·  SET  · CLL · CML ·  STL  ·  RAL  ·  RAR
           BASE <dec|oct|bin>    ·       MODE <signed|unsigned>
                                 (H for help)
```

Columns are aligned so dots line up between rows.

---

## Status Bar Rules

The status bar always occupies **the bottom line** of the content area.
It is left‑padded with dynamic context and right‑padded with the fixed `Q : quit` hint.

Possible fields:

- `BASE` – input base (always shown)
- `DECIMAL` – signed/unsigned (only when base = DEC)
- `LAST` – last operation (only when non‑empty)

Examples:

```
BASE: DEC | DECIMAL: SIGNED | LAST: CIA                          Q : quit
BASE: OCT | LAST: RAL                                            Q : quit
BASE: BIN                                                        Q : quit
```

---

## Help Screen (Toggle with `H`)

- Help replaces the interior content area only; outer border is identical
- The pane‑separator row shows plain `│` verticals in place of `├`/`┤` T‑shapes
- No scrolling
- Exit help with `H` (hotkey, no Enter needed), `Enter`, or `Q`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ PDP‑8 Programmer’s Calculator                                                │
│──────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│ Commands                                                                     │
│ ─────────────────────────────────────────────────────────────────────────────│
│  LOAD <n>  (L <n>)  Load n into AC                                           │
│  ADD  <n>  (+ <n>)  Add n to AC  (carry into Link)                           │
│  SUB  <n>  (- <n>)  Subtract n from AC                                       │
│  AND  <n>  (& <n>)  Bitwise AND  AC with n                                   │
│  OR   <n>  (| <n>)  Bitwise OR   AC with n                                   │
│  XOR  <n>  (^ <n>)  Bitwise XOR  AC with n                                   │
│  IAC       (I)      Increment AC by 1  (carry into Link)                     │
│  CIA                Complement and Increment AC  (two’s-complement negate)   │
│  CLA  CMA  SET      Clear AC   /   Complement AC   /  Set AC to 7777         │
│  CLL  CML  STL      Clear Link  /  Complement Link  /   Set Link to 1        │
│  RAL  RAR           Rotate ⟨L, AC⟩ left / right one bit                      │
│                                                                              │
│  BASE <dec|oct|bin>       Set input number base  (default: OCT)              │
│  MODE <signed|unsigned>   Decimal display mode   (default: SIGNED)           │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ H : return                                                         Q : quit  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Design Principles

- Machine representation comes before human interpretation
- Signedness is an interpretive lens, not state
- Controls are adjacent to the state they modify
- The calculator supports thinking, not simulation

---

## Summary

This UI is:
- Deterministic
- Non‑modal
- PDP‑8‑centric
- Friendly to sustained program‑writing sessions

It is intentionally quiet and minimal, trading decoration for clarity.
