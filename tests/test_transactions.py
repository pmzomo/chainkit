import struct

import pytest
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.message import Message
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer

from chainkit import instructions as ix
from chainkit import transactions
from chainkit.addresses import derive_ata
from chainkit.constants import ATA_PROGRAM, COMPUTE_BUDGET_PROGRAM, TOKEN_PROGRAM
from chainkit.transactions import TransferPlan, build_transfer_message, describe_message, transaction_size

from .helpers import DEVNET_USDC, new_address

BLOCKHASH = str(Hash.new_unique())


def plan(**overrides):
    values = {'fee_payer': new_address(), 'source_owner': new_address(), 'mint': DEVNET_USDC, 'amount': 12_340_000,
              'destination_owner': new_address()}
    values.update(overrides)
    return TransferPlan(**values)


def test_transfer_to_owner_creates_account_and_only_uses_allowlisted_instructions():
    p = plan(memo='invoice 1042', cu_price_micro_lamports=1000)
    message = build_transfer_message(p, BLOCKHASH)
    facts = describe_message(message)
    assert facts.is_clean and facts.unknown == []
    assert facts.fee_payer == p.fee_payer and set(facts.signers) == {p.fee_payer, p.source_owner}
    assert facts.transfers == [{'source': str(derive_ata(p.source_owner, DEVNET_USDC)), 'mint': DEVNET_USDC,
                                'destination': str(derive_ata(p.destination_owner, DEVNET_USDC)),
                                'owner': p.source_owner, 'amount': 12_340_000, 'decimals': 6}]
    assert facts.ata_creations == [{'payer': p.fee_payer, 'ata': str(derive_ata(p.destination_owner, DEVNET_USDC)),
                                    'owner': p.destination_owner, 'mint': DEVNET_USDC}]
    assert facts.memos == ['invoice 1042']
    assert facts.compute_unit_limit == transactions.DEFAULT_CU_LIMIT and facts.compute_unit_price == 1000
    assert str(message.recent_blockhash) == BLOCKHASH
    assert transaction_size(message) <= 1232


def test_transfer_to_token_account_skips_creation_and_priority_fee():
    destination = str(derive_ata(new_address(), DEVNET_USDC))
    facts = describe_message(build_transfer_message(plan(destination_owner=None,
                                                         destination_token_account=destination), BLOCKHASH))
    assert facts.ata_creations == [] and facts.compute_unit_price is None
    assert facts.transfers[0]['destination'] == destination and facts.memos == []


def test_fee_payer_can_also_be_the_owner():
    owner = new_address()
    facts = describe_message(build_transfer_message(plan(fee_payer=owner, source_owner=owner), BLOCKHASH))
    assert facts.signers == [owner]


@pytest.mark.parametrize('overrides, message', [
    ({'destination_owner': None}, 'exactly one'),
    ({'destination_token_account': 'x' * 40}, 'exactly one'),
    ({'amount': 0}, 'amount'), ({'amount': 1.5}, 'amount'), ({'amount': True}, 'amount'),
    ({'amount': 2 ** 64}, 'amount'),
    ({'fee_payer': 'not-an-address'}, 'valid Solana address'), ({'mint': ''}, 'valid Solana address'),
    ({'cu_limit': 0}, 'units'), ({'memo': 'x' * 121}, 'memo'), ({'decimals': 300}, 'decimals'),
])
def test_invalid_plans_are_refused(overrides, message):
    with pytest.raises(ValueError, match=message):
        build_transfer_message(plan(**overrides), BLOCKHASH)


def test_sending_to_your_own_token_account_is_refused():
    owner = new_address()
    with pytest.raises(ValueError, match='same token account'):
        build_transfer_message(plan(source_owner=owner, destination_owner=owner), BLOCKHASH)


def test_oversized_transaction_is_refused(monkeypatch):
    monkeypatch.setattr(transactions, 'MAX_TRANSACTION_BYTES', 300)
    with pytest.raises(ValueError, match='size limit'):
        build_transfer_message(plan(), BLOCKHASH)


def test_destination_account_requires_a_destination():
    with pytest.raises(ValueError):
        plan(destination_owner=None).destination_account()


def _message(*instructions: Instruction, payer: str | None = None) -> Message:
    return Message.new_with_blockhash(list(instructions), Pubkey.from_string(payer or new_address()),
                                      Hash.from_string(BLOCKHASH))


def test_describe_flags_everything_it_does_not_recognise():
    payer, other = new_address(), new_address()
    foreign = Instruction(Pubkey.from_string(new_address()), b'\x00', [])
    sol_transfer = transfer(TransferParams(from_pubkey=Pubkey.from_string(payer), to_pubkey=Pubkey.from_string(other),
                                           lamports=1))
    plain_transfer = Instruction(Pubkey.from_string(TOKEN_PROGRAM), bytes([3]) + struct.pack('<Q', 5),
                                 [AccountMeta(Pubkey.from_string(new_address()), False, True),
                                  AccountMeta(Pubkey.from_string(new_address()), False, True),
                                  AccountMeta(Pubkey.from_string(payer), True, False)])
    ata_create = Instruction(Pubkey.from_string(ATA_PROGRAM), b'', [])
    heap_frame = Instruction(Pubkey.from_string(COMPUTE_BUDGET_PROGRAM), bytes([1]) + struct.pack('<I', 1024), [])
    bad_limit = Instruction(Pubkey.from_string(COMPUTE_BUDGET_PROGRAM), bytes([2, 0]), [])
    facts = describe_message(_message(foreign, sol_transfer, plain_transfer, ata_create, heap_frame, bad_limit,
                                      payer=payer))
    assert not facts.is_clean and len(facts.unknown) == 6
    assert any(u.startswith('program ') for u in facts.unknown)
    assert 'direct call to 11111111111111111111111111111111' in facts.unknown
    assert 'token instruction other than transferChecked' in facts.unknown
    assert facts.transfers == [] and facts.compute_unit_limit is None


def test_describe_rejects_transfer_checked_with_extra_signer_accounts():
    accounts = [new_address() for _ in range(4)]
    instruction = ix.transfer_checked(*accounts, 5, 6)
    padded = Instruction(instruction.program_id, bytes(instruction.data),
                         [*instruction.accounts, AccountMeta(Pubkey.from_string(new_address()), True, False)])
    facts = describe_message(_message(padded))
    assert facts.transfers == [] and facts.unknown == ['token instruction other than transferChecked']
