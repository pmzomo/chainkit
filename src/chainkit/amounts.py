"""USDC amounts as integer atomic units (6 decimals). Never floats.

`to_atomic('150.25') == 150_250_000`. Integers in atomic units are the only safe representation for ledger and
on-chain amounts; decimal strings are for people.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

from .constants import ATOMIC_PER_USDC, U64_MAX, USDC_DECIMALS

# ASCII digits only: \d would also match other scripts (for example Arabic-Indic digits), which Decimal accepts.
_PLAIN = re.compile(r'[0-9]+(\.[0-9]+)?')
_GROUPED = re.compile(r'[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?')


class AmountError(ValueError):
    """The value is not a valid positive USDC amount."""


def to_atomic(value: str | Decimal) -> int:
    """Parse a positive USDC amount into atomic units.

    Accepts a decimal string ('150.25', '1,250.50') or a Decimal. Rejects floats (binary rounding), plain
    integers (ambiguous: dollars or atomic units?), scientific notation, malformed thousands separators, zero,
    negatives, more than 6 decimal places and anything above the u64 limit of an SPL token amount.
    """
    raw: object = value  # callers may pass anything at runtime; validate it all
    if isinstance(raw, (bool, float)):
        raise AmountError('Floats are not accepted for money; pass a string or Decimal.')
    if isinstance(raw, int):
        raise AmountError('Pass USDC as a decimal string; integers are ambiguous here.')
    if isinstance(raw, Decimal):
        amount = raw
    elif isinstance(raw, str):
        text = raw.strip()
        if not (_PLAIN.fullmatch(text) or _GROUPED.fullmatch(text)):
            raise AmountError('Enter a valid amount, for example 150.25.')
        amount = Decimal(text.replace(',', ''))
    else:
        raise AmountError('Pass USDC as a decimal string or Decimal.')
    if not amount.is_finite() or amount <= 0:
        raise AmountError('Amount must be greater than zero.')
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > USDC_DECIMALS:
        raise AmountError('USDC supports at most 6 decimal places.')
    atomic = int(amount.scaleb(USDC_DECIMALS))
    if atomic > U64_MAX:
        raise AmountError('Amount is too large.')
    return atomic


def from_atomic(atomic: int) -> Decimal:
    """Atomic units to an exact Decimal with 6 places: 150250000 -> Decimal('150.250000')."""
    raw: object = atomic
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError('atomic must be an int')
    value: Decimal = Decimal(raw) / ATOMIC_PER_USDC
    return value.quantize(Decimal('0.000001'))


def format_usdc(atomic: int, places: int = 2) -> str:
    """Human display, rounded half up to `places` with thousands separators. Display only, never for posting."""
    if not 0 <= places <= USDC_DECIMALS:
        raise ValueError('places must be between 0 and 6')
    value = from_atomic(atomic).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f'{value:,.{places}f}'
