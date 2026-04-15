# PDP‑8 Programmer's Calculator

A terminal-based programmer's calculator for working with PDP‑8 assembly code.

---

## What it is

When you're writing PDP‑8 assembly, you frequently need to know: *what does the AC and Link look like after this sequence of instructions?* You could run a full emulator, but that's heavyweight and puts you in execution mode rather than reasoning mode. You could do it on paper, but 12‑bit arithmetic in your head invites mistakes.

This calculator is the middle ground. You type the instructions — `CLA CLL IAC`, `+ 177`, `CIA` — and it shows the AC and Link immediately, in binary, octal, and decimal simultaneously, calculated as a real PDP‑8 would produce them.

It is a **thinking tool**: something you keep open in a terminal pane while you write assembly, to validate your reasoning instruction by instruction.

---

## What it is not

- **Not a simulator or emulator.** There is no memory, no program counter, no instruction fetch, no timing. It does not run PDP‑8 programs.
- **Not a debugger.** There is no way to load a binary and step through it.
- **Not a reference implementation.** It covers only the arithmetic and logical behavior of Group‑1 OPR microinstructions and TAD‑equivalent arithmetic. Skip instructions (Groups 2 and 3), IOT, and memory‑reference instructions are out of scope.
- **Not a replacement for documentation.** It assumes you know what `CMA`, `RAL`, and `CIA` mean; it will not teach you PDP‑8.

The sole correctness criterion is:

> *The AC and Link values produced must match what a real PDP‑8 would produce.*

---

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ PDP‑8 Programmer's Calculator                                                │
│──────────────────────────────────────────────────────────────────────────────│
│                                                                              │
│                         L     Accumulator                                    │
│                         --- ---------------                                  │
│                          1   111 111 111 111                                 │
│                   Octal:   7   7   7   7                                     │
│                                                                              │
│           Decimal:  signed:     -1    unsigned: 4095                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Command > _                                                                 │
│                                                                              │
│                                                                              │
│                                                                              │
│  Commands:                                                                   │
│        LOAD <n> · + <n> · - <n> · IAC · CIA · & <n> · | <n> · ^ <n>          │
│          CLA    ·  CMA  ·  SET  · CLL · CML ·  STL  ·  RAL  ·  RAR           │
│           BASE <dec|oct|bin>    ·       MODE <signed|unsigned>               │
│                                 (H for help)                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ BASE: OCT                                                         Q : quit   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Download

Pre-built single-file binaries are attached to each [GitHub Release](https://github.com/jnpastin/pdp8-programmers-calculator/releases). No installation or elevated privileges required — just download and run.

| Platform | File |
|----------|------|
| Linux (x86-64) | `pdp8calc-linux` |
| macOS | `pdp8calc-macos` |
| Windows | `pdp8calc-windows.exe` |

**Linux / macOS:** make executable once, then run directly.
```sh
chmod +x pdp8calc-linux   # or pdp8calc-macos
./pdp8calc-linux
```

**Windows:** double-click in Explorer, or run from a Command Prompt or PowerShell window. A console window is required — the TUI will not display in a window-less context.

**macOS Gatekeeper note:** the binary is unsigned. On first run, macOS will block it with a security warning. Right-click (or Control-click) the binary → *Open* → *Open* to allow it once. Subsequent runs proceed normally.

---

## Building from source

Requires Python 3.10 or later. No runtime dependencies.

```sh
pip install -r build-requirements.txt             # installs PyInstaller
# Windows only: pip install windows-curses
cd Calculator
pyinstaller --onefile pdp8_tui.py                 # output: dist/pdp8_tui[.exe]
```

The GitHub Actions workflow (`.github/workflows/build.yml`) automates this for all three platforms and attaches the binaries to a release when you push a `v*` tag.

---

## Requirements

*To run from source:*

- Python 3.10 or later
- A terminal at least **80 columns × 24 rows**
- No dependencies outside the standard library

---

## Running

```
python3 pdp8_tui.py
```

Type commands at the `Command>` prompt and press Enter.  
Press `H` for the built-in command reference. Press `Q` to quit.

---

## Commands

All commands are case-insensitive. The space between a command and its operand is optional (`+42` and `+ 42` are identical).

### Data

| Command | Alias | Effect |
|---------|-------|--------|
| `LOAD <n>` | `L <n>` | Load AC with n; Link unchanged |

### Arithmetic

| Command | Aliases | Effect |
|---------|---------|--------|
| `ADD <n>` | `+ <n>` | AC ← AC + n (carry into Link) |
| `SUB <n>` | `- <n>` | AC ← AC − n (via complement-and-add) |
| `IAC` | `I` | Increment AC (carry into Link) |
| `CIA` | | Complement and increment AC (two’s-complement negate) |

### Accumulator / Link micro-operations

| Command | Effect |  |  Command | Effect |
|---------|--------|--|---------|--------|
| `CLA` | Clear AC | | `CLL` | Clear Link |
| `CMA` | Complement AC | | `CML` | Complement Link |
| `SET` | Set AC = 7777 | | `STL` | Set Link = 1 |
| `RAL` | Rotate ⟨L,AC⟩ left | | `RAR` | Rotate ⟨L,AC⟩ right |

Multiple no-argument micro-ops can be combined on one line, like an assembler:
```
CLA CLL IAC
```

### Logical

| Command | Aliases | Effect |
|---------|---------|--------|
| `AND <n>` | `& <n>` | AC ← AC AND n |
| `OR <n>` | `\| <n>` | AC ← AC OR n |
| `XOR <n>` | `^ <n>` | AC ← AC XOR n |

### Mode

| Command | Effect |
|---------|--------|
| `BASE dec\|oct\|bin` | Set input number base (default: OCT) |
| `MODE signed\|unsigned` | Set decimal display interpretation (default: SIGNED) |

---

## Numeric Input

The active base applies to all numeric operands.

| Base | Example | Notes |
|------|---------|-------|
| OCT (default) | `LOAD 7777` | No sign prefix allowed |
| BIN | `BASE BIN`, then `LOAD 111111111111` | No sign prefix allowed |
| DEC | `BASE DEC`, then `LOAD 4095` | Negative values allowed in SIGNED mode |

---

## Project Structure

```
pdp8_tui.py       — TUI entry point (curses, Layer 3)
pdp8_parser.py    — Command parsing and dispatch (Layer 2)
pdp8_core.py      — AC/Link arithmetic engine (Layer 1, pure functions)
tests/
  test_pdp8_core.py
  test_pdp8_parser.py
  test_pdp8_tui.py
  conftest.py
docs/
  DESIGN.md       — Full design and command specification
  UI.md           — Terminal UI layout and design rationale
```

The three-layer architecture keeps logic, parsing, and presentation strictly separated:

- **Layer 1** (`pdp8_core.py`) — pure functions, no I/O, no state. All operations return a new `MachineState`.
- **Layer 2** (`pdp8_parser.py`) — tokenizes input, dispatches to Layer 1, owns session state (base, mode, last).
- **Layer 3** (`pdp8_tui.py`) — curses TUI, calls Layer 2, renders results.

---

## Testing

```sh
python3 -m unittest discover tests
```

The test suite covers all three layers: 69 core arithmetic tests, 142+ parser tests, and 36 TUI unit/smoke tests — 247 tests total, all without a real terminal.

---

## Design Reference

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full command specification and [`docs/UI.md`](docs/UI.md) for the screen layout and UI rationale.

---

## Correctness Criterion

> **The AC and Link values produced must match what a real PDP‑8 would produce.**

This tool supports *thinking*, not simulation. Memory, skip instructions, and program counter are intentionally out of scope.
