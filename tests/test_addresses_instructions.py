import struct

import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from chainkit import instructions as ix
from chainkit.addresses import AddressError, derive_ata, is_on_curve, parse_pubkey
from chainkit.constants import (
    ATA_PROGRAM,
    COMPUTE_BUDGET_PROGRAM,
    MEMO_PROGRAM,
    SYSTEM_PROGRAM,
    TOKEN_PROGRAM,
    U64_MAX,
    cluster_for_genesis,
    genesis_hash,
    usdc_mint,
)

from .helpers import DEVNET_USDC, MAINNET_USDC, new_address

# Fixed vector: ATA of the Pyth receiver program id for mainnet USDC, computed once and pinned so a regression in
# derivation is caught (the live tests also check derivation against a real on-chain account).
VECTOR_OWNER = 'rec5EKMGg6MxZYaMdyBfgwp4d5rB9T1VQH5pJv5LtFJ'


def test_parse_pubkey_strict():
    owner = new_address()
    assert str(parse_pubkey(owner)) == owner
    assert str(parse_pubkey(f'  {owner}\n')) == owner
    for bad in ['', 'not-an-address', owner + 'x', owner[:-1] + '0', '0' * 44, 'O' * 32, None, 123, b'abc']:
        with pytest.raises(AddressError):
            parse_pubkey(bad)


def test_derive_ata_properties():
    owner = new_address()
    a, b = derive_ata(owner, DEVNET_USDC), derive_ata(Pubkey.from_string(owner), DEVNET_USDC)
    assert a == b                                   # str and Pubkey inputs agree
    assert not a.is_on_curve()                      # token accounts are program-derived
    assert derive_ata(owner, MAINNET_USDC) != a     # one account per mint
    assert is_on_curve(owner) and not is_on_curve(str(a))
    with pytest.raises(AddressError):
        derive_ata('bad', DEVNET_USDC)


def test_derive_ata_matches_manual_seed_derivation():
    owner = Pubkey.from_string(VECTOR_OWNER)
    expected, _ = Pubkey.find_program_address(
        [bytes(owner), bytes(Pubkey.from_string(TOKEN_PROGRAM)), bytes(Pubkey.from_string(MAINNET_USDC))],
        Pubkey.from_string(ATA_PROGRAM))
    assert derive_ata(VECTOR_OWNER, MAINNET_USDC) == expected


def test_cluster_helpers():
    assert usdc_mint('mainnet-beta') == MAINNET_USDC
    assert cluster_for_genesis(genesis_hash('devnet')) == 'devnet'
    assert cluster_for_genesis('unknown') is None
    for fn in (usdc_mint, genesis_hash):
        with pytest.raises(ValueError):
            fn('testnet-x')


def test_transfer_checked_encoding_and_accounts():
    src, mint, dst, owner = (new_address() for _ in range(4))
    instruction = ix.transfer_checked(src, mint, dst, owner, 5, 6)
    assert bytes(instruction.data) == bytes([12]) + struct.pack('<Q', 5) + bytes([6])
    assert str(instruction.program_id) == TOKEN_PROGRAM
    metas = instruction.accounts
    assert [str(m.pubkey) for m in metas] == [src, mint, dst, owner]
    assert [m.is_signer for m in metas] == [False, False, False, True]
    assert [m.is_writable for m in metas] == [True, False, True, False]
    assert bytes(ix.transfer_checked(src, mint, dst, owner, U64_MAX, 6).data)[1:9] == b'\xff' * 8


@pytest.mark.parametrize('amount, decimals', [(0, 6), (-1, 6), (U64_MAX + 1, 6), (True, 6), (1.0, 6), (1, 256),
                                              (1, -1)])
def test_transfer_checked_rejects_out_of_range(amount, decimals):
    with pytest.raises(ValueError):
        ix.transfer_checked(new_address(), new_address(), new_address(), new_address(), amount, decimals)


def test_create_ata_idempotent_layout():
    payer, ata, owner, mint = (new_address() for _ in range(4))
    instruction = ix.create_ata_idempotent(payer, ata, owner, mint)
    assert str(instruction.program_id) == ATA_PROGRAM and bytes(instruction.data) == bytes([1])
    assert [str(m.pubkey) for m in instruction.accounts] == [payer, ata, owner, mint, SYSTEM_PROGRAM, TOKEN_PROGRAM]
    assert instruction.accounts[0].is_signer and instruction.accounts[0].is_writable


def test_compute_budget_and_memo():
    limit = ix.set_compute_unit_limit(60_000)
    assert str(limit.program_id) == COMPUTE_BUDGET_PROGRAM
    assert bytes(limit.data) == bytes([2]) + struct.pack('<I', 60_000)
    assert bytes(ix.set_compute_unit_price(1000).data) == bytes([3]) + struct.pack('<Q', 1000)
    assert bytes(ix.set_compute_unit_price(0).data) == bytes([3]) + bytes(8)
    note = ix.memo('invoice 1042')
    assert str(note.program_id) == MEMO_PROGRAM and bytes(note.data) == b'invoice 1042'
    assert len(bytes(ix.memo('é' * 60).data)) == 120


@pytest.mark.parametrize('call', [
    lambda: ix.set_compute_unit_limit(0), lambda: ix.set_compute_unit_limit(1_400_001),
    lambda: ix.set_compute_unit_price(-1), lambda: ix.set_compute_unit_price(U64_MAX + 1),
    lambda: ix.memo(''), lambda: ix.memo('x' * 121), lambda: ix.memo('é' * 61),
])
def test_range_checks(call):
    with pytest.raises(ValueError):
        call()


def test_keypair_addresses_are_on_curve():
    assert is_on_curve(Keypair().pubkey())
