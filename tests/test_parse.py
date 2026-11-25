from chainkit.constants import TOKEN_2022_PROGRAM
from chainkit.parse import fee_lamports, owner_delta, senders, usdc_delta

from .helpers import DEVNET_USDC, MAINNET_USDC, new_address, parsed_tx, row


def deposit(amount=25_000_000, mint=DEVNET_USDC, err=None, program=None, keys_as_dicts=True):
    sender_owner, receiver_owner = new_address(), new_address()
    sender_acct, receiver_acct = new_address(), new_address()
    extra = {'program': program} if program else {}
    tx = parsed_tx([new_address(), sender_acct, receiver_acct],
                   pre=[row(1, mint, sender_owner, 100_000_000, **extra), row(2, mint, receiver_owner, 5, **extra)],
                   post=[row(1, mint, sender_owner, 100_000_000 - amount, **extra),
                         row(2, mint, receiver_owner, 5 + amount, **extra)],
                   err=err, keys_as_dicts=keys_as_dicts)
    return tx, sender_owner, receiver_owner, sender_acct, receiver_acct


def test_deposit_is_read_from_balance_deltas():
    tx, sender_owner, receiver_owner, sender_acct, receiver_acct = deposit()
    assert usdc_delta(tx, receiver_acct, DEVNET_USDC) == 25_000_000
    assert usdc_delta(tx, sender_acct, DEVNET_USDC) == -25_000_000
    assert owner_delta(tx, receiver_owner, DEVNET_USDC) == 25_000_000
    assert senders(tx, DEVNET_USDC) == [sender_owner]
    assert fee_lamports(tx) == 5000


def test_plain_string_account_keys_are_supported():
    tx, _, _, _, receiver_acct = deposit(keys_as_dicts=False)
    assert usdc_delta(tx, receiver_acct, DEVNET_USDC) == 25_000_000


def test_new_token_account_counts_from_zero():
    owner, acct = new_address(), new_address()
    tx = parsed_tx([new_address(), acct], pre=[], post=[row(1, DEVNET_USDC, owner, 7_000_000)])
    assert usdc_delta(tx, acct, DEVNET_USDC) == 7_000_000


def test_closed_account_reports_the_outflow():
    owner, acct = new_address(), new_address()
    tx = parsed_tx([new_address(), acct], pre=[row(1, DEVNET_USDC, owner, 3_000_000)], post=[])
    assert usdc_delta(tx, acct, DEVNET_USDC) == -3_000_000
    assert senders(tx, DEVNET_USDC) == [owner]


def test_failed_transactions_move_nothing():
    tx, _, receiver_owner, _, receiver_acct = deposit(err={'InstructionError': [0, 'Custom']})
    assert usdc_delta(tx, receiver_acct, DEVNET_USDC) == 0
    assert owner_delta(tx, receiver_owner, DEVNET_USDC) == 0
    assert senders(tx, DEVNET_USDC) == []
    assert usdc_delta({'transaction': tx['transaction'], 'meta': None}, receiver_acct, DEVNET_USDC) == 0


def test_lookalike_mint_and_other_token_program_are_ignored():
    fake, _, _, _, receiver_acct = deposit(mint=new_address())
    assert usdc_delta(fake, receiver_acct, DEVNET_USDC) == 0 and senders(fake, DEVNET_USDC) == []
    wrong_cluster, *_, acct = deposit(mint=MAINNET_USDC)
    assert usdc_delta(wrong_cluster, acct, DEVNET_USDC) == 0
    token_2022, _, owner_2022, _, acct_2022 = deposit(program=TOKEN_2022_PROGRAM)
    assert usdc_delta(token_2022, acct_2022, DEVNET_USDC) == 0
    assert owner_delta(token_2022, owner_2022, DEVNET_USDC) == 0


def test_account_not_in_transaction():
    tx, *_ = deposit()
    assert usdc_delta(tx, new_address(), DEVNET_USDC) == 0


def test_owner_delta_sums_several_token_accounts():
    owner, a, b = new_address(), new_address(), new_address()
    tx = parsed_tx([new_address(), a, b], pre=[row(1, DEVNET_USDC, owner, 1_000_000)],
                   post=[row(1, DEVNET_USDC, owner, 3_000_000), row(2, DEVNET_USDC, owner, 500_000)])
    assert owner_delta(tx, owner, DEVNET_USDC) == 2_500_000
    assert owner_delta(tx, new_address(), DEVNET_USDC) == 0


def test_fee_defaults_to_zero():
    assert fee_lamports({}) == 0 and fee_lamports({'meta': {'fee': None}}) == 0
