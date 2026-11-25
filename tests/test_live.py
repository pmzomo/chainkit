"""Checks against public Solana RPC and Pyth. Skipped unless CHAINKIT_LIVE=1 (also run weekly in CI)."""
import os

import pytest

from chainkit import pyth
from chainkit.addresses import derive_ata
from chainkit.constants import TOKEN_ACCOUNT_SIZE, TOKEN_PROGRAM, genesis_hash, usdc_mint
from chainkit.rpc import SolanaRpc

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get('CHAINKIT_LIVE') != '1', reason='set CHAINKIT_LIVE=1 to run')]

RPC = {'mainnet-beta': 'https://api.mainnet-beta.solana.com', 'devnet': 'https://api.devnet.solana.com'}
# A Devnet wallet known to hold Circle Devnet USDC in its associated token account (GT Pay's Devnet hot wallet).
DEVNET_USDC_HOLDER = 'G2wwq6LrtETbcjSjek5WubiwquVQRDXotGTPGhXU71oE'


@pytest.mark.parametrize('cluster', ['mainnet-beta', 'devnet'])
def test_genesis_hash_and_usdc_mint_are_correct(cluster):
    rpc = SolanaRpc([RPC[cluster]])
    assert rpc.genesis_hash() == genesis_hash(cluster)
    mint = rpc.account_info(usdc_mint(cluster))
    assert mint is not None and mint['owner'] == TOKEN_PROGRAM
    info = mint['data']['parsed']['info']
    assert mint['data']['parsed']['type'] == 'mint' and info['decimals'] == 6


def test_derived_token_account_exists_on_chain():
    rpc = SolanaRpc([RPC['devnet']])
    ata = str(derive_ata(DEVNET_USDC_HOLDER, usdc_mint('devnet')))
    account = rpc.account_info(ata)
    assert account is not None and account['owner'] == TOKEN_PROGRAM
    info = account['data']['parsed']['info']
    assert info['owner'] == DEVNET_USDC_HOLDER and info['mint'] == usdc_mint('devnet')


def test_token_account_rent_is_queried_not_assumed():
    # Rent changes over time (2,039,280 lamports for many years, 1,488,440 by November 2026): always ask the cluster.
    mainnet = SolanaRpc([RPC['mainnet-beta']]).minimum_balance_for_rent_exemption(TOKEN_ACCOUNT_SIZE)
    devnet = SolanaRpc([RPC['devnet']]).minimum_balance_for_rent_exemption(TOKEN_ACCOUNT_SIZE)
    assert 0 < mainnet <= 2_039_280 and 0 < devnet <= 2_039_280


def test_usdc_mint_is_circles_and_has_supply():
    mint = SolanaRpc([RPC['mainnet-beta']]).account_info(usdc_mint('mainnet-beta'))
    assert mint is not None and int(mint['data']['parsed']['info']['supply']) > 1_000_000 * 10 ** 6


def test_pyth_sol_usd_on_mainnet():
    reading = pyth.read_price(SolanaRpc([RPC['mainnet-beta']]))
    assert reading.fully_verified and 1 < reading.price < 100_000
