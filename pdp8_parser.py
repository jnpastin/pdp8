"""
PDP-8 Programmer's Calculator — Layer 2: Command Parsing & Dispatch

Tokenizes user input, dispatches to Layer 1 operations, and manages session
state.  This layer has no UI or I/O dependencies.

Session state (SessionState):
  machine  — MachineState (ac, link) from Layer 1
  base     — input base: "DEC", "OCT", "BIN"
  mode     — decimal interpretation: "SIGNED", "UNSIGNED"
  last     — string for status bar: last machine-state-changing operation

dispatch(line, session) returns (new_session, None) on success or
(original_session, error_string) on any parse or validation failure.
Session state (including 'last') is never mutated on error.

Numeric argument parsing:
  BIN  — unsigned binary, no sign prefix, masked to 12 bits
  OCT  — unsigned octal, no sign prefix, masked to 12 bits
  DEC/SIGNED   — any integer (negatives allowed), masked to 12 bits
  DEC/UNSIGNED — non-negative integer only, masked to 12 bits
"""

from typing import NamedTuple, Optional, Tuple
import re
import pdp8_core as core
from pdp8_core import MachineState


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

class SessionState(NamedTuple):
    """Immutable Layer 2 session state."""
    machine: MachineState = MachineState()
    base: str = "OCT"       # "DEC", "OCT", "BIN"
    mode: str = "SIGNED"    # "SIGNED", "UNSIGNED"
    last: str = ""          # last machine-state-changing operation, or ""


# ---------------------------------------------------------------------------
# Alias map and command sets
# ---------------------------------------------------------------------------

_ALIASES = {"+": "ADD", "-": "SUB", "&": "AND", "|": "OR", "^": "XOR", "I": "IAC", "L": "LOAD"}

_NOARG_COMMANDS = frozenset(
    {"IAC", "CIA", "CLA", "CMA", "SET", "CLL", "CML", "STL", "RAL", "RAR"}
)
_ARG_COMMANDS = frozenset({"LOAD", "ADD", "SUB", "AND", "OR", "XOR"})

_NOARG_OPS = {
    "IAC": core.op_i,
    "CIA": core.op_cia,
    "CLA": core.op_cla,
    "CMA": core.op_cma,
    "SET": core.op_set,
    "CLL": core.op_cll,
    "CML": core.op_cml,
    "STL": core.op_stl,
    "RAL": core.op_ral,
    "RAR": core.op_rar,
}

_ARG_OPS = {
    "LOAD": core.op_load,
    "ADD":  core.op_add,
    "SUB":  core.op_sub,
    "AND":  core.op_and,
    "OR":   core.op_or,
    "XOR":  core.op_xor,
}


# Tokenizer: splits a command line so that the space between a command and its
# numeric operand is optional (e.g. "+1234" == "+ 1234", "LOAD-7" == "LOAD -7").
# Pattern: one token is a word (letters/digits) or a single symbolic alias;
# an optional second token is a sign-prefixed-or-plain run of word characters.
_TOKENIZE_RE = re.compile(
    r'^\s*([A-Za-z]+|[+\-&|^])\s*([+\-]?[A-Za-z0-9]+)?\s*$'
)


def _tokenize(line: str) -> Optional[list]:
    """Return [cmd] or [cmd, arg] from line, or None if the format is unrecognised.

    Accepts optional whitespace between command and operand, e.g. '+42' or '+ 42'.
    """
    m = _TOKENIZE_RE.match(line)
    if not m:
        return None
    cmd = m.group(1)
    arg = m.group(2)
    return [cmd] if arg is None else [cmd, arg]



def parse_number(token: str, base: str, mode: str) -> Tuple[int, Optional[str]]:
    """Parse a numeric token according to the active base and mode.

    Returns (value, None) on success, where value is masked to 12 bits.
    Returns (0, error_message) on failure.

    BIN and OCT do not accept a sign prefix.
    DEC/SIGNED accepts negatives (they wrap naturally into 12 bits).
    DEC/UNSIGNED rejects negatives.
    """
    if base in ("BIN", "OCT"):
        if token and token[0] in ("+", "-"):
            label = "binary" if base == "BIN" else "octal"
            return 0, f"Sign prefix not allowed for {label} input: {token}"
        try:
            radix = 2 if base == "BIN" else 8
            value = int(token, radix)
        except ValueError:
            label = "binary" if base == "BIN" else "octal"
            return 0, f"Invalid {label} number: {token}"
        return value & core.AC_MASK, None

    # DEC
    try:
        value = int(token, 10)
    except ValueError:
        return 0, f"Invalid decimal number: {token}"

    if mode == "UNSIGNED" and value < 0:
        return 0, f"Negative values not allowed in UNSIGNED mode: {token}"

    return value & core.AC_MASK, None


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------

def dispatch(line: str, session: SessionState) -> Tuple[SessionState, Optional[str]]:
    """Parse and execute one input line against the given session.

    Returns (new_session, None) on success.
    Returns (original_session, error_string) on any failure; session is unchanged.

    Mode commands (BASE, MODE) update base/mode but do not update 'last'.
    All other valid commands update 'last' on success.

    Input is uppercased before parsing; callers need not pre-normalize.
    """
    normalized = line.strip().upper()
    if not normalized:
        return session, None

    # --- Multi-op micro-instruction (all no-arg commands on one line) ---
    # e.g. "CLA CLL IAC" — each token must be a known no-arg command/alias.
    words = normalized.split()
    if len(words) > 1:
        canonicals = [_ALIASES.get(w, w) for w in words]
        if all(c in _NOARG_COMMANDS for c in canonicals):
            machine = session.machine
            for c in canonicals:
                machine = _NOARG_OPS[c](machine)
            last = " ".join(words)   # preserve user's original tokens (e.g. IAC not I)
            return session._replace(machine=machine, last=last), None
        # More than one word but not all no-arg — fall through to normal parse
        # (will likely fail tokenization and return a clear error)

    tokens = _tokenize(normalized)
    if tokens is None:
        return session, f"Unrecognised input: {line.strip()!r}"

    cmd = tokens[0]
    rest = tokens[1:]
    canonical = _ALIASES.get(cmd, cmd)

    # --- BASE ---
    if canonical == "BASE":
        if not rest:
            return session, "BASE requires an argument: DEC, OCT, or BIN"
        if len(rest) > 1:
            return session, "BASE takes exactly one argument"
        arg = rest[0]
        if arg not in ("DEC", "OCT", "BIN"):
            return session, f"Unknown base '{arg}': use DEC, OCT, or BIN"
        return session._replace(base=arg), None

    # --- MODE ---
    if canonical == "MODE":
        if not rest:
            return session, "MODE requires an argument: SIGNED or UNSIGNED"
        if len(rest) > 1:
            return session, "MODE takes exactly one argument"
        arg = rest[0]
        if arg not in ("SIGNED", "UNSIGNED"):
            return session, f"Unknown mode '{arg}': use SIGNED or UNSIGNED"
        return session._replace(mode=arg), None

    # --- No-argument machine ops ---
    if canonical in _NOARG_COMMANDS:
        if rest:
            return session, f"{canonical} takes no argument"
        new_machine = _NOARG_OPS[canonical](session.machine)
        return session._replace(machine=new_machine, last=canonical), None

    # --- Argument machine ops ---
    if canonical in _ARG_COMMANDS:
        if not rest:
            return session, f"{canonical} requires a numeric argument"
        if len(rest) > 1:
            return session, f"{canonical} takes exactly one argument"
        value, err = parse_number(rest[0], session.base, session.mode)
        if err:
            return session, err
        new_machine = _ARG_OPS[canonical](session.machine, value)
        last = f"{canonical} {rest[0]}"
        return session._replace(machine=new_machine, last=last), None

    return session, f"Unknown command: {cmd}"
