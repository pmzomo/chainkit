"""The small, fixed set of instructions a USDC transfer needs, encoded by hand and range-checked.

transferChecked (not transfer) is used so the token program itself verifies the mint and decimals.
"""
import struct

from solders.instruction import AccountMeta, Instruction
from solders.pubkey import Pubkey

from .constants import ATA_PROGRAM, COMPUTE_BUDGET_PROGRAM, MEMO_PROGRAM, SYSTEM_PROGRAM, TOKEN_PROGRAM, U64_MAX

TRANSFER_CHECKED = 12
ATA_CREATE_IDEMPOTENT = 1
CU_LIMIT = 2
CU_PRICE = 3
MAX_COMPUTE_UNITS = 1_400_000
MAX_MEMO_BYTES = 120


def _pk(value: str | Pubkey) -> Pubkey:
    return value if isinstance(value, Pubkey) else Pubkey.from_string(str(value))


def _check_int(name: str, value: int, low: int, high: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer from {low} to {high}')


def transfer_checked(source_token_account: str | Pubkey, mint: str | Pubkey,
                     destination_token_account: str | Pubkey, owner: str | Pubkey, amount: int,
                     decimals: int) -> Instruction:
    """SPL Token transferChecked: move `amount` atomic units; fails on-chain if mint or decimals do not match."""
    _check_int('amount', amount, 1, U64_MAX)
    _check_int('decimals', decimals, 0, 255)
    data = bytes([TRANSFER_CHECKED]) + struct.pack('<Q', amount) + bytes([decimals])
    return Instruction(_pk(TOKEN_PROGRAM), data, [
        AccountMeta(_pk(source_token_account), is_signer=False, is_writable=True),
        AccountMeta(_pk(mint), is_signer=False, is_writable=False),
        AccountMeta(_pk(destination_token_account), is_signer=False, is_writable=True),
        AccountMeta(_pk(owner), is_signer=True, is_writable=False),
    ])


def create_ata_idempotent(payer: str | Pubkey, ata: str | Pubkey, owner: str | Pubkey,
                          mint: str | Pubkey) -> Instruction:
    """Create `owner`'s token account for `mint` if missing; a no-op if it already exists. `payer` funds the rent."""
    return Instruction(_pk(ATA_PROGRAM), bytes([ATA_CREATE_IDEMPOTENT]), [
        AccountMeta(_pk(payer), is_signer=True, is_writable=True),
        AccountMeta(_pk(ata), is_signer=False, is_writable=True),
        AccountMeta(_pk(owner), is_signer=False, is_writable=False),
        AccountMeta(_pk(mint), is_signer=False, is_writable=False),
        AccountMeta(_pk(SYSTEM_PROGRAM), is_signer=False, is_writable=False),
        AccountMeta(_pk(TOKEN_PROGRAM), is_signer=False, is_writable=False),
    ])


def set_compute_unit_limit(units: int) -> Instruction:
    _check_int('units', units, 1, MAX_COMPUTE_UNITS)
    return Instruction(_pk(COMPUTE_BUDGET_PROGRAM), bytes([CU_LIMIT]) + struct.pack('<I', units), [])


def set_compute_unit_price(micro_lamports: int) -> Instruction:
    """Priority fee in micro-lamports per compute unit."""
    _check_int('micro_lamports', micro_lamports, 0, U64_MAX)
    return Instruction(_pk(COMPUTE_BUDGET_PROGRAM), bytes([CU_PRICE]) + struct.pack('<Q', micro_lamports), [])


def memo(text: str) -> Instruction:
    """A memo (UTF-8, 1 to 120 bytes). Kept short on purpose: memos are public and cost transaction space."""
    payload = text.encode('utf-8')
    if not 1 <= len(payload) <= MAX_MEMO_BYTES:
        raise ValueError(f'memo must be 1 to {MAX_MEMO_BYTES} bytes')
    return Instruction(_pk(MEMO_PROGRAM), payload, [])
