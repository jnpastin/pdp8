"""
PDP-8 Programmer's Calculator — Layer 3: TUI Shell

Curses-based fixed 80×24 terminal UI.

Entry point: main()
"""

import curses
import sys

import pdp8_core as core
from pdp8_parser import SessionState, dispatch

# ── Layout constants ──────────────────────────────────────────────────────────

REQUIRED_COLS = 80
REQUIRED_ROWS = 24

# Outer border occupies row 0, row 23, col 0, col 79.
# Interior content region: rows 1–22, cols 1–78 (22 rows × 78 cols).
BORDER_TOP    = 0
BORDER_BOTTOM = 23
BORDER_LEFT   = 0
BORDER_RIGHT  = 79

CONTENT_TOP   = 1
CONTENT_ROWS  = 22
CONTENT_LEFT  = 1
CONTENT_COLS  = 78

SEPARATOR_ROW = 21   # ├...┤ divider between content and status bar
STATUS_ROW    = 22   # │ status text │ — own row between ├───┤ and └───┘
PANE1_ROW     = 10   # ├...┤ divider between register pane and commands pane

# Register display rows (absolute, 0-indexed)
_ROW_REG_LABELS = 4
_ROW_REG_SEP    = 5
_ROW_REG_BITS   = 6
_ROW_REG_OCTAL  = 7
_ROW_DEC        = 9   # signed + unsigned on one line
_ROW_CMD_HDR    = 11
_ROW_PROMPT     = 12
_ROW_ERROR      = 13
_ROW_CHEAT_HDR  = 16
_ROW_CHEAT1     = 17
_ROW_CHEAT2     = 18
_ROW_CHEAT3     = 19
_ROW_CHEAT4     = 20

PROMPT_TEXT = " Command> "

# Cheat-strip — per-column widths derived from data so dots align between rows.
_CHEAT_SEP    = " · "
_CHEAT_INDENT = "        "   # 8-space tab (PDP-8 convention)
_CHEAT_CMDS_R1 = ["LOAD <n>", "+ <n>", "- <n>", "IAC",  "CIA", "& <n>", "| <n>", "^ <n>"]
_CHEAT_CMDS_R2 = ["CLA",      "CMA",   "SET",   "CLL", "CML", "STL",   "RAL",   "RAR"  ]
_CHEAT_COL_W   = [max(len(a), len(b))
                  for a, b in zip(_CHEAT_CMDS_R1, _CHEAT_CMDS_R2)]
_CHEAT_LINE_1  = _CHEAT_INDENT + _CHEAT_SEP.join(
                     c.center(w) for c, w in zip(_CHEAT_CMDS_R1, _CHEAT_COL_W))
_CHEAT_LINE_2  = _CHEAT_INDENT + _CHEAT_SEP.join(
                     c.center(w) for c, w in zip(_CHEAT_CMDS_R2, _CHEAT_COL_W))
# Line 3: BASE spans cols 0-2, MODE spans cols 3-7 — both centred in their merged widths
_BASE_SPAN     = sum(_CHEAT_COL_W[0:3]) + len(_CHEAT_SEP) * 2   # = 24
_MODE_SPAN     = sum(_CHEAT_COL_W[3:8]) + len(_CHEAT_SEP) * 4   # = 33
_CHEAT_LINE_3  = (_CHEAT_INDENT
                  + "BASE <dec|oct|bin>".center(_BASE_SPAN)
                  + _CHEAT_SEP
                  + "MODE <signed|unsigned>".center(_MODE_SPAN))
_CHEAT_LINE_4  = "(H for help)".center(CONTENT_COLS)

# ── Static border characters ──────────────────────────────────────────────────

_TL = "┌"
_TR = "┐"
_BL = "└"
_BR = "┘"
_ML = "├"
_MR = "┤"
_H  = "─"
_V  = "│"

TITLE_TEXT = "PDP‑8 Programmer's Calculator"


# ── Screen initialization ─────────────────────────────────────────────────────

def _assert_terminal_size(stdscr: "curses.window") -> None:
    """Abort with a clear error if the terminal is smaller than required."""
    rows, cols = stdscr.getmaxyx()
    if rows < REQUIRED_ROWS or cols < REQUIRED_COLS:
        try:
            curses.endwin()
        except Exception:
            pass
        print(
            f"Terminal too small: {cols}×{rows}. "
            f"At least {REQUIRED_COLS}×{REQUIRED_ROWS} is required.",
            file=sys.stderr,
        )
        sys.exit(1)


def _draw_static_border(stdscr: "curses.window") -> None:
    """Draw the outer border and title once; never redrawn during the session."""
    # Top edge
    stdscr.addstr(0, 0, _TL + _H * (REQUIRED_COLS - 2) + _TR)

    # Side verticals (rows 1–20; rows 10 and 21 are separator rows, not plain sides)
    for row in range(1, SEPARATOR_ROW):
        if row == PANE1_ROW:
            continue
        stdscr.addch(row, BORDER_LEFT,  _V)
        stdscr.addch(row, BORDER_RIGHT, _V)

    # Pane separator between register display and commands
    stdscr.addstr(PANE1_ROW, 0, _ML + _H * (REQUIRED_COLS - 2) + _MR)

    # Middle separator before status bar
    stdscr.addstr(SEPARATOR_ROW, 0, _ML + _H * (REQUIRED_COLS - 2) + _MR)

    # Status bar row gets its own │ sides (sits between ├───┤ and └───┘)
    stdscr.addch(STATUS_ROW, BORDER_LEFT,  _V)
    stdscr.addch(STATUS_ROW, BORDER_RIGHT, _V)

    # Bottom edge — use addstr up to col 78, then addch at col 79 to avoid
    # the curses "write at last cell" exception on some terminals.
    bottom = _BL + _H * (REQUIRED_COLS - 2) + _BR
    stdscr.addstr(BORDER_BOTTOM, 0, bottom[:-1])
    stdscr.addch(BORDER_BOTTOM, BORDER_RIGHT, _BR)

    # Title row (row 1) and horizontal rule (row 2)
    stdscr.addstr(CONTENT_TOP, CONTENT_LEFT, TITLE_TEXT)
    stdscr.addstr(CONTENT_TOP + 1, CONTENT_LEFT, _H * CONTENT_COLS)


# ── Pure rendering helpers (no curses; fully unit-testable) ─────────────────

# Register block is horizontally centred.
# Block: L-col (3) + gap (1) + AC-col (15) = 19 chars; CONTENT_COLS = 78.
_REG_PAD   = (CONTENT_COLS - 19) // 2   # = 29
_TRIAD_COL = _REG_PAD + 3 + 1           # = 33  (first bit of AC triads)
_OCTAL_COL = _TRIAD_COL + 1             # = 34  (first octal digit, under triad centre)


def _fmt_reg_labels() -> str:
    """Centred:  '(pad) L    Accumulator (pad)' padded to CONTENT_COLS."""
    # "Accumulator" (11 chars) centred in the 15-char AC column.
    acc_start = _TRIAD_COL + (15 - 11) // 2   # = 35
    return (
        " " * (_REG_PAD + 1) + "L"
        + " " * (acc_start - _REG_PAD - 2) + "Accumulator"
    ).ljust(CONTENT_COLS)


def _fmt_reg_sep() -> str:
    """Centred:  '(pad) ---  --------------- (pad)' padded to CONTENT_COLS."""
    return (" " * _REG_PAD + "---" + " " + "-" * 15).ljust(CONTENT_COLS)


def _fmt_bits_row(link: int, ac: int) -> str:
    """Centred:  '(pad)  1   111 111 111 111 (pad)' padded to CONTENT_COLS.

    Link bit at content offset _REG_PAD+1 (centre of L-col).
    Triads start at content offset _TRIAD_COL.
    """
    return (
        " " * (_REG_PAD + 1) + str(link) + "  " + core.to_binary_triads(ac)
    ).ljust(CONTENT_COLS)


def _fmt_octal_row(ac: int) -> str:
    """Centred:  '(pad) Octal:  7   7   7   7 (pad)' padded to CONTENT_COLS.

    Each octal digit lands at _OCTAL_COL + n*4, directly under the centre
    of its binary triad.
    """
    digits = "   ".join(core.to_octal(ac))   # "7   7   7   7" (13 chars)
    label_start = _OCTAL_COL - 7             # = 27  ("Octal: " is 7 chars)
    return (" " * label_start + "Octal: " + digits).ljust(CONTENT_COLS)


def _fmt_decimal_row(ac: int) -> str:
    """Single centred line: signed and unsigned decimal on the same row."""
    s = core.to_signed(ac)
    u = core.to_unsigned(ac)
    content = f"Decimal:  signed: {s:6d}    unsigned: {u:4d}"  # 42 chars
    pad = (CONTENT_COLS - len(content)) // 2
    return (" " * pad + content).ljust(CONTENT_COLS)


def _fmt_cheat(line: str) -> str:
    """Pad a cheat line to CONTENT_COLS (left-aligned, indented as given)."""
    return line.ljust(CONTENT_COLS)


# ── Register display ─────────────────────────────────────────────────────────

def _draw_register_display(
    stdscr: "curses.window",
    session: SessionState,
    input_buf: str = "",
) -> None:
    """Render the full content area from the register rows down to the prompt."""
    ac   = session.machine.ac
    link = session.machine.link
    L    = CONTENT_LEFT
    blank = " " * CONTENT_COLS

    stdscr.addstr(_ROW_REG_LABELS - 1, L, blank)                # row 3 blank
    stdscr.addstr(_ROW_REG_LABELS,     L, _fmt_reg_labels())
    stdscr.addstr(_ROW_REG_SEP,        L, _fmt_reg_sep())
    stdscr.addstr(_ROW_REG_BITS,       L, _fmt_bits_row(link, ac))
    stdscr.addstr(_ROW_REG_OCTAL,      L, _fmt_octal_row(ac))
    stdscr.addstr(_ROW_DEC - 1,        L, blank)                # row 8 blank
    stdscr.addstr(_ROW_DEC,            L, _fmt_decimal_row(ac))
    # row 10 (PANE1_ROW) is a static ├───┤ drawn by _draw_static_border; do not overwrite
    # Commands pane: prompt near top, cheat strip near bottom
    stdscr.addstr(_ROW_CMD_HDR,        L, blank)                # row 11: subtle — no header needed with prompt adjacent
    prompt_content = PROMPT_TEXT + input_buf
    stdscr.addstr(_ROW_PROMPT,         L, prompt_content.ljust(CONTENT_COLS))
    stdscr.addstr(_ROW_ERROR,          L, blank)                # row 13 error line (clear)
    for r in range(_ROW_ERROR + 1, _ROW_CHEAT_HDR):            # rows 14-16 blank
        stdscr.addstr(r, L, blank)
    stdscr.addstr(_ROW_CHEAT_HDR,      L, " Commands:".ljust(CONTENT_COLS))
    stdscr.addstr(_ROW_CHEAT1,         L, _fmt_cheat(_CHEAT_LINE_1))
    stdscr.addstr(_ROW_CHEAT2,         L, _fmt_cheat(_CHEAT_LINE_2))
    stdscr.addstr(_ROW_CHEAT3,         L, _fmt_cheat(_CHEAT_LINE_3))
    stdscr.addstr(_ROW_CHEAT4,         L, _fmt_cheat(_CHEAT_LINE_4))
    # Position cursor at end of prompt input
    stdscr.move(_ROW_PROMPT, L + len(prompt_content))


# ── Status bar ───────────────────────────────────────────────────────────────

def _compose_status(session: SessionState) -> str:
    """Compose the status bar string from session state (no curses dependency).

    Rules:
      BASE      — always shown
      DECIMAL   — only when BASE = DEC
      LAST      — only when last operation is non-empty
    Right side always shows Q : quit.
    """
    parts = [f"BASE: {session.base}"]
    if session.base == "DEC":
        parts.append(f"DECIMAL: {session.mode}")
    if session.last:
        parts.append(f"LAST: {session.last}")
    left  = " | ".join(parts)
    right = "Q : quit"
    gap   = CONTENT_COLS - len(left) - len(right)
    if gap < 1:
        return left[:CONTENT_COLS]
    return left + " " * gap + right


def _draw_status_bar(stdscr: "curses.window", session: SessionState) -> None:
    """Render the status bar at STATUS_ROW, left-aligned, padded to clear stale text."""
    text = _compose_status(session)
    # Status bar sits inside the bottom border (cols 1-78)
    stdscr.addstr(STATUS_ROW, CONTENT_LEFT, text.ljust(CONTENT_COLS))


# ── Prompt & error line helpers ───────────────────────────────────────────────

def _draw_prompt(stdscr: "curses.window", input_buf: str) -> None:
    """Redraw just the prompt line and position the cursor."""
    content = PROMPT_TEXT + input_buf
    stdscr.addstr(_ROW_PROMPT, CONTENT_LEFT, content.ljust(CONTENT_COLS))
    stdscr.move(_ROW_PROMPT, CONTENT_LEFT + len(content))


def _draw_error(stdscr: "curses.window", msg: str) -> None:
    """Render or clear the error line.  msg is truncated to fit."""
    stdscr.addstr(_ROW_ERROR, CONTENT_LEFT, msg[:CONTENT_COLS].ljust(CONTENT_COLS))


# ── Help screen ───────────────────────────────────────────────────────────────

_HELP_STATUS = "H : return" + "Q : quit".rjust(CONTENT_COLS - len("H : return"))

_HELP_LINES = [
    "",
    " Commands",
    " " + "\u2500" * 75,
    "  LOAD <n>  (L <n>)  Load n into AC",
    "  ADD  <n>  (+ <n>)  Add n to AC  (carry into Link)",
    "  SUB  <n>  (- <n>)  Subtract n from AC",
    "  AND  <n>  (& <n>)  Bitwise AND  AC with n",
    "  OR   <n>  (| <n>)  Bitwise OR   AC with n",
    "  XOR  <n>  (^ <n>)  Bitwise XOR  AC with n",
    "  IAC       (I)      Increment AC by 1  (carry into Link)",
    "  CIA                Complement and Increment AC  (two\u2019s-complement negate)",
    "  CLA  CMA  SET      Clear AC   /   Complement AC   /  Set AC to 7777",
    "  CLL  CML  STL      Clear Link  /  Complement Link  /   Set Link to 1",
    "  RAL  RAR           Rotate \u27e8L, AC\u27e9 left / right one bit",
    "",
    "  BASE <dec|oct|bin>       Set input number base  (default: OCT)",
    "  MODE <signed|unsigned>   Decimal display mode   (default: SIGNED)",
    "",
]


def _redraw_pane_separator(stdscr: "curses.window") -> None:
    """Redraw the \u251c\u2500\u2500\u2500\u2524 between the register pane and the commands pane (PANE1_ROW)."""
    stdscr.addstr(PANE1_ROW, 0, _ML + _H * (REQUIRED_COLS - 2) + _MR)


def _draw_help(stdscr: "curses.window") -> None:
    """Render the help screen; help content replaces the interior content area."""
    L = CONTENT_LEFT
    start = CONTENT_TOP + 2   # row 3, below title + rule
    for i, line in enumerate(_HELP_LINES):
        stdscr.addstr(start + i, L, line.ljust(CONTENT_COLS))
    # PANE1_ROW (row 10) is inside the help area — its ├/┤ border chars
    # would look like T-shapes; replace with plain │ side verticals.
    stdscr.addch(PANE1_ROW, BORDER_LEFT,  _V)
    stdscr.addch(PANE1_ROW, BORDER_RIGHT, _V)
    # Fixed status bar while in help mode
    stdscr.addstr(STATUS_ROW, L, _HELP_STATUS.ljust(CONTENT_COLS))


# ── Input loop ────────────────────────────────────────────────────────────────

_BACKSPACE_KEYS = frozenset({curses.KEY_BACKSPACE, 0x7F, 0x08})
_ENTER_KEYS     = frozenset({ord("\n"), ord("\r"), curses.KEY_ENTER})
_EXIT_KEYS      = frozenset({0x03, curses.KEY_F0 + 10, ord('Q'), ord('q')})  # Ctrl+C, F10, Q


def _input_loop(stdscr: "curses.window", session: SessionState) -> None:
    """Main input loop.  Returns when the user exits."""
    buf: list[str] = []
    in_help = False

    while True:
        ch = stdscr.getch()

        # ── Exit ──────────────────────────────────────────────────────────────
        if ch in _EXIT_KEYS:
            break

        # ── Backspace ─────────────────────────────────────────────────────────
        if ch in _BACKSPACE_KEYS:
            if buf:
                buf.pop()
                _draw_prompt(stdscr, "".join(buf))
                stdscr.refresh()
            continue

        # ── Enter — submit ────────────────────────────────────────────────────
        if ch in _ENTER_KEYS:
            command = "".join(buf).strip()
            buf.clear()
            _draw_error(stdscr, "")          # clear any previous error

            # In help mode, Enter returns to main screen regardless of buffer
            if in_help:
                in_help = False
                _redraw_pane_separator(stdscr)
                _draw_register_display(stdscr, session)
                _draw_status_bar(stdscr, session)
                _draw_prompt(stdscr, "")
                stdscr.refresh()
                continue

            if command:
                if command == "H":
                    in_help = True
                    _draw_help(stdscr)
                    stdscr.refresh()
                    continue          # don't fall through to _draw_prompt
                else:
                    new_session, err = dispatch(command, session)
                    if err:
                        _draw_error(stdscr, err)
                    else:
                        session = new_session
                        _draw_register_display(stdscr, session)
                        _draw_status_bar(stdscr, session)

            _draw_prompt(stdscr, "")
            stdscr.refresh()
            continue

        # ── Printable characters (with live uppercase normalization) ──────────
        if 0x20 <= ch <= 0x7E:
            c = chr(ch)
            if "a" <= c <= "z":
                c = c.upper()
            # H hotkey: if in help mode, exit immediately without buffering
            if c == "H" and in_help:
                in_help = False
                _redraw_pane_separator(stdscr)
                _draw_register_display(stdscr, session)
                _draw_status_bar(stdscr, session)
                _draw_prompt(stdscr, "")
                stdscr.refresh()
                continue
            buf.append(c)
            if not in_help:
                _draw_prompt(stdscr, "".join(buf))
                stdscr.refresh()
            continue

        # Ignore all other characters (function keys, arrows, etc.)


# ── curses setup ─────────────────────────────────────────────────────────────

def _init_curses(stdscr: "curses.window") -> None:
    """Configure curses options."""
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.curs_set(1)   # visible cursor
    # Inherit the terminal's own foreground/background instead of
    # curses defaulting to black/white.
    curses.start_color()
    curses.use_default_colors()


# ── Main ─────────────────────────────────────────────────────────────────────

def _run(stdscr: "curses.window") -> None:
    _assert_terminal_size(stdscr)
    _init_curses(stdscr)
    _draw_static_border(stdscr)
    session = SessionState()
    _draw_register_display(stdscr, session)
    _draw_status_bar(stdscr, session)
    stdscr.refresh()
    _input_loop(stdscr, session)


def main() -> None:
    try:
        curses.wrapper(_run)
    except KeyboardInterrupt:
        pass   # Ctrl+C outside the input loop (e.g. during startup); exit cleanly


if __name__ == "__main__":
    main()
