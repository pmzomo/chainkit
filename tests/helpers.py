"""Builders for jsonParsed transactions shaped like getTransaction results."""
from solders.keypair import Keypair

from chainkit.constants import TOKEN_PROGRAM, usdc_mint

DEVNET_USDC = usdc_mint('devnet')
MAINNET_USDC = usdc_mint('mainnet-beta')


def new_address() -> str:
    return str(Keypair().pubkey())


def row(index: int, mint: str, owner: str, amount: int, program: str = TOKEN_PROGRAM) -> dict:
    return {'accountIndex': index, 'mint': mint, 'owner': owner, 'programId': program,
            'uiTokenAmount': {'amount': str(amount), 'decimals': 6}}


def parsed_tx(keys: list[str], pre: list[dict], post: list[dict], err=None, fee: int = 5000,
              keys_as_dicts: bool = True) -> dict:
    account_keys = [{'pubkey': k, 'signer': i == 0, 'writable': True} for i, k in enumerate(keys)] \
        if keys_as_dicts else list(keys)
    return {'slot': 1, 'transaction': {'message': {'accountKeys': account_keys}, 'signatures': ['sig']},
            'meta': {'err': err, 'fee': fee, 'preTokenBalances': pre, 'postTokenBalances': post}}
