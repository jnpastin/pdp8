"""
PDP-8 Programmer's Calculator — Layer 1: AC/Link Core Engine

Pure logic layer with no UI or parsing dependencies.

Data model:
  AC  — 12-bit unsigned integer (always masked to 0..4095)
  L   — 1-bit link (0 or 1)

All operations take and return a MachineState; they never mutate state.
Operations that do not mention Link leave it unchanged.
Carry out of bit 11 toggles Link.
"""

from typing import NamedTuple

AC_MASK = 0o7777          # 12 bits: 0–4095
AC_CARRY = 0o10000        # bit 12: carry out of bit 11


class MachineState(NamedTuple):
    """Immutable PDP-8 machine state: 12-bit accumulator and 1-bit link."""
    ac: int = 0
    link: int = 0


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _add(state: MachineState, operand: int) -> MachineState:
    """Binary add operand to AC; toggle Link if carry propagates out of bit 11."""
    result = state.ac + (operand & AC_MASK)
    carry = (result & AC_CARRY) != 0
    new_ac = result & AC_MASK
    new_link = state.link ^ (1 if carry else 0)
    return MachineState(new_ac, new_link)


# ---------------------------------------------------------------------------
# Data Movement
# ---------------------------------------------------------------------------

def op_load(state: MachineState, n: int) -> MachineState:
    """LOAD n — set AC to n (masked to 12 bits); Link unchanged."""
    return MachineState(n & AC_MASK, state.link)


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------

def op_add(state: MachineState, n: int) -> MachineState:
    """ADD n — AC ← AC + n (mod 4096); carry toggles Link."""
    return _add(state, n)


def op_sub(state: MachineState, n: int) -> MachineState:
    """SUB n — AC ← AC + CIA(n); carry toggles Link."""
    cia_n = (~n & AC_MASK) + 1
    return _add(state, cia_n)


def op_i(state: MachineState) -> MachineState:
    """I — Increment AC by 1; carry toggles Link."""
    return _add(state, 1)


def op_cia(state: MachineState) -> MachineState:
    """CIA — Complement and Increment AC (CMA then IAC).

    Carry out of bit 11 during the increment step toggles Link.
    This only occurs when AC = 0: ~0 = 7777, 7777 + 1 = 10000 (carry).
    """
    complemented = (~state.ac) & AC_MASK
    result = complemented + 1
    carry = (result & AC_CARRY) != 0
    new_ac = result & AC_MASK
    new_link = state.link ^ (1 if carry else 0)
    return MachineState(new_ac, new_link)


# ---------------------------------------------------------------------------
# Accumulator micro-operations
# ---------------------------------------------------------------------------

def op_cla(state: MachineState) -> MachineState:
    """CLA — Clear AC to 0; Link unchanged."""
    return MachineState(0, state.link)


def op_cma(state: MachineState) -> MachineState:
    """CMA — Ones-complement AC; Link unchanged."""
    return MachineState((~state.ac) & AC_MASK, state.link)


def op_set(state: MachineState) -> MachineState:
    """SET — Set AC = 7777 octal (all ones); Link unchanged."""
    return MachineState(AC_MASK, state.link)


# ---------------------------------------------------------------------------
# Link micro-operations
# ---------------------------------------------------------------------------

def op_cll(state: MachineState) -> MachineState:
    """CLL — Clear Link to 0; AC unchanged."""
    return MachineState(state.ac, 0)


def op_cml(state: MachineState) -> MachineState:
    """CML — Complement Link; AC unchanged."""
    return MachineState(state.ac, state.link ^ 1)


def op_stl(state: MachineState) -> MachineState:
    """STL — Set Link to 1; AC unchanged."""
    return MachineState(state.ac, 1)


# ---------------------------------------------------------------------------
# Logical operations
# ---------------------------------------------------------------------------

def op_and(state: MachineState, n: int) -> MachineState:
    """AND n — AC ← AC & n; Link unchanged."""
    return MachineState((state.ac & n) & AC_MASK, state.link)


def op_or(state: MachineState, n: int) -> MachineState:
    """OR n — AC ← AC | n; Link unchanged."""
    return MachineState((state.ac | n) & AC_MASK, state.link)


def op_xor(state: MachineState, n: int) -> MachineState:
    """XOR n — AC ← AC ^ n; Link unchanged."""
    return MachineState((state.ac ^ n) & AC_MASK, state.link)


# ---------------------------------------------------------------------------
# Rotate operations  (operate on the 13-bit ⟨L, AC⟩ value)
# ---------------------------------------------------------------------------

def op_ral(state: MachineState) -> MachineState:
    """RAL — Rotate ⟨L, AC⟩ left one bit."""
    # 13-bit value: L is bit 12, AC is bits 11..0
    combined = (state.link << 12) | state.ac
    rotated = ((combined << 1) | (combined >> 12)) & 0o17777  # 13 bits
    new_link = (rotated >> 12) & 1
    new_ac = rotated & AC_MASK
    return MachineState(new_ac, new_link)


def op_rar(state: MachineState) -> MachineState:
    """RAR — Rotate ⟨L, AC⟩ right one bit."""
    combined = (state.link << 12) | state.ac
    rotated = ((combined >> 1) | ((combined & 1) << 12)) & 0o17777  # 13 bits
    new_link = (rotated >> 12) & 1
    new_ac = rotated & AC_MASK
    return MachineState(new_ac, new_link)


# ---------------------------------------------------------------------------
# Numeric interpretation helpers (view only — never affect arithmetic)
# ---------------------------------------------------------------------------

def to_signed(ac: int) -> int:
    """Interpret 12-bit AC as two's-complement signed integer (−2048..+2047)."""
    return ac if ac < 2048 else ac - 4096


def to_unsigned(ac: int) -> int:
    """Interpret 12-bit AC as unsigned magnitude (0..4095)."""
    return ac


def to_octal(ac: int) -> str:
    """Return AC as a 4-digit octal string."""
    return f"{ac:04o}"


def to_binary_triads(ac: int) -> str:
    """Return AC as four space-separated 3-bit groups (e.g. '111 111 111 111')."""
    bits = f"{ac:012b}"
    return " ".join(bits[i:i+3] for i in range(0, 12, 3))
