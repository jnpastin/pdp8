# PDP‑8 Programmer’s Calculator

## Design & Command Specification (MVP)

This document consolidates **all agreed design, UI, and command‑syntax decisions** for the PDP‑8 Programmer’s Calculator. It is authoritative for the MVP and intended to be dropped directly into the project repository.

---

## 1. Purpose and Scope

The PDP‑8 Programmer’s Calculator is a **thinking aid** for writing and reasoning about PDP‑8 assembly programs.

It exists to:
- Explore accumulator (AC) and link (L) behavior
- Convert between decimal, octal, and binary representations
- Reason about PDP‑8 arithmetic and microinstruction effects

It is **not**:
- A simulator or emulator
- A timing‑accurate model
- A memory or control‑flow interpreter

Correctness is judged solely by:

> **Whether AC and Link match real PDP‑8 behavior.**

---

## 2. Global UI Constraints

- Terminal UI is **rigidly 80×24 characters**
- Outer border is invariant and never changes
- No scrolling in main or help screens
- Interior content is exactly 22×78
- Status bar occupies exactly one row

---

## 3. Main Screen Layout (Canonical)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ PDP‑8 Programmer’s Calculator                                               │
│──────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│                         L     Accumulator                                   │
│                         --- ---------------                                 │
│                          1   111 111 111 111                                │
│                    Octal:   7   7   7   7                                   │
│                                                                              │
│          Decimal:  signed:     -1    unsigned: 4095                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Command> _                                                                  │
│                                                                              │
│                                                                              │
│                                                                              │
│  Commands:                                                                   │
│        LOAD <n> · + <n> · - <n> · IAC · CIA · & <n> · | <n> · ^ <n>       │
│          CLA    ·  CMA  ·  SET  · CLL · CML ·  STL  ·  RAL  ·  RAR        │
│           BASE <dec|oct|bin>    ·       MODE <signed|unsigned>              │
│                                 (H for help)                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ BASE: DEC | DECIMAL: SIGNED | LAST: CIA                          Q : quit   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Register Display Semantics

- Link is visually attached to the accumulator, front‑panel style
- Accumulator bits are shown as **four binary triads**
- Octal digit appears **directly beneath each triad**
- No "Binary:" label is used

Semantic hierarchy:
1. Machine state (Link + bits)
2. Octal encoding
3. Decimal interpretations

---

## 5. Decimal Interpretation

Decimal values are *interpretations* only.
They do **not** affect arithmetic behavior.

```
Decimal:
    signed:   -1
    unsigned: 4095
```

- Signed: 12‑bit two’s‑complement (−2048…+2047)
- Unsigned: 12‑bit magnitude (0…4095)

---

## 6. Input Normalization

### 6.1 Uppercase Normalization

All alphabetic input is converted to uppercase **as it is typed**.

Example keystrokes:
```
a → A → AD → ADD
```

Rules:
- Only `a–z` are transformed
- Numbers, operators, and punctuation are untouched
- Cursor position and editing behavior are preserved
- Normalization occurs **before parsing**

---

## 7. Status Bar Rules

The status bar shows **only dynamically relevant context**, right-padded to the full
content width with a fixed `Q : quit` hint at the far right.

Possible fields:
- `BASE` – input base (always shown)
- `DECIMAL` – signed/unsigned (only when BASE = DEC)
- `LAST` – most recent operation (only when non‑empty)

Examples:
```
BASE: DEC | DECIMAL: SIGNED | LAST: CIA                          Q : quit
BASE: OCT | LAST: RAL                                            Q : quit
BASE: BIN                                                        Q : quit
```

---

## 8. Supported Operations and Syntax

All commands are case‑insensitive (visually uppercased on entry).

### 8.1 Data Movement

```
load <n>   | l <n>
```
Loads AC with `<n>`. Link unchanged.

---

### 8.2 Arithmetic

```
add <n>     | + <n>
sub <n>     | - <n>
iac
cia
```

- `iac` increments AC by 1; carry toggles Link. (`i` is accepted as an alias.)
- Arithmetic wraps unconditionally
- Carry toggles Link

---

### 8.3 Accumulator / Link Micro‑operations

```
cla    clear AC
cma    complement AC (ones complement)
set    set AC = 7777
cll    clear Link
cml    complement Link
stl    set Link = 1
iac    increment AC  (alias: i)
cia    complement and increment AC
ral    rotate ⟨L,AC⟩ left one bit
rar    rotate ⟨L,AC⟩ right one bit
```

All correspond directly to PDP‑8 Group‑1 OPR semantics.

Multiple no‑argument micro‑ops can be combined on one line, as an assembler would:
```
cla cll iac
cla cma
```
They are executed in left‑to‑right order; any single unrecognised token in the
combination is an error and the session is left unchanged.

---

### 8.4 Logical Operations

```
and <n>   | & <n>
or  <n>   | | <n>
xor <n>   | ^ <n>
```

- Operate on AC only
- Link unchanged

---

### 8.5 Rotate Operations

```
ral
rar
```

- Rotate operates on **⟨L,AC⟩ as a 13‑bit value**

---

## 9. Mode Commands

```
base dec | oct | bin
mode signed | unsigned
```

- Mode commands never alter AC or Link
- Signed/unsigned only applies when base = DEC

---

## 10. Help Screen

- Toggled with `H` (key press, no Enter needed) or by submitting `H` at the prompt
- Same 80×24 border as main screen; pane separator row shows plain `│` verticals instead of `├`/`┤`
- No scrolling
- `H` (hotkey), `Enter`, or `Q` returns to the main screen

Help content:

```
 Commands
 ───────────────────────────────────────────────────────────────────────────
  LOAD <n>  (L <n>)  Load n into AC
  ADD  <n>  (+ <n>)  Add n to AC  (carry into Link)
  SUB  <n>  (- <n>)  Subtract n from AC
  AND  <n>  (& <n>)  Bitwise AND  AC with n
  OR   <n>  (| <n>)  Bitwise OR   AC with n
  XOR  <n>  (^ <n>)  Bitwise XOR  AC with n
  IAC       (I)      Increment AC by 1  (carry into Link)
  CIA                Complement and Increment AC  (two’s-complement negate)
  CLA  CMA  SET      Clear AC   /   Complement AC   /  Set AC to 7777
  CLL  CML  STL      Clear Link  /  Complement Link  /   Set Link to 1
  RAL  RAR           Rotate ⟨L, AC⟩ left / right one bit

  BASE <dec|oct|bin>       Set input number base  (default: OCT)
  MODE <signed|unsigned>   Decimal display mode   (default: SIGNED)
```

Help status bar: `H : return` on the left, `Q : quit` on the right.

---

## 11. Explicit Non‑Features (MVP)

- Memory operations
- Skip instructions
- Program counter
- GLK (get link into AC)
- Scripting or macros

---

## 12. Design Principles

- Machine representation precedes human interpretation
- Signedness is a view, not state
- Controls live near the state they affect
- If it never changes, it does not belong on screen
- The calculator exists to support **thinking**, not execution

---

## Summary

This specification defines a **minimal, complete, and disciplined** PDP‑8 programmer’s calculator.
Every feature directly supports PDP‑8 arithmetic reasoning without drifting into simulator territory.
