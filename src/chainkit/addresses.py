"""Address parsing and associated token account (ATA) derivation."""
from solders.pubkey import Pubkey

from .constants import ATA_PROGRAM, TOKEN_PROGRAM

_TOKEN_PROGRAM = Pubkey.from_string(TOKEN_PROGRAM)
_ATA_PROGRAM = Pubkey.from_string(ATA_PROGRAM)


class AddressError(ValueError):
    """The value is not a valid Solana address."""


def parse_pubkey(value: object) -> Pubkey:
    """Parse a base58 Solana address strictly: surrounding spaces are trimmed, everything else must round-trip."""
    if not isinstance(value, str):
        raise AddressError('That is not a valid Solana address.')
    text = value.strip()
    if not 32 <= len(text) <= 44:
        raise AddressError('That is not a valid Solana address.')
    try:
        key = Pubkey.from_string(text)
    except ValueError:
        raise AddressError('That is not a valid Solana address.') from None
    if str(key) != text:  # pragma: no cover - defensive: base58 decoding is canonical in solders today
        raise AddressError('That is not a valid Solana address.')
    return key


def _key(value: str | Pubkey) -> Pubkey:
    return value if isinstance(value, Pubkey) else parse_pubkey(value)


def derive_ata(owner: str | Pubkey, mint: str | Pubkey) -> Pubkey:
    """The associated token account of `owner` for `mint` under the classic SPL Token program."""
    ata, _bump = Pubkey.find_program_address([bytes(_key(owner)), bytes(_TOKEN_PROGRAM), bytes(_key(mint))],
                                             _ATA_PROGRAM)
    return ata


def is_on_curve(address: str | Pubkey) -> bool:
    """True for addresses that can sign (wallets); False for program-derived addresses such as token accounts."""
    return _key(address).is_on_curve()
