"""Read USDC movements out of `jsonParsed` transactions (as returned by getTransaction).

Balance deltas (pre/post token balances) are used instead of instruction parsing, so a payment is seen no matter
which program moved it: a wallet, an exchange withdrawal, an aggregator or a smart contract. Every balance row is
checked against the exact mint and the classic token program, so look-alike tokens are never counted.
"""
from typing import Any

from .constants import TOKEN_PROGRAM

Json = dict[str, Any]


def _key_of(entry: object) -> str:
    return str(entry['pubkey']) if isinstance(entry, dict) else str(entry)


def _index_of(tx: Json, account: str) -> int | None:
    keys = tx['transaction']['message']['accountKeys']
    for i, key in enumerate(keys):
        if _key_of(key) == account:
            return i
    return None


def _usdc_rows(rows: list[Json] | None, mint: str) -> dict[int, Json]:
    return {row['accountIndex']: row for row in rows or []
            if row.get('mint') == mint and row.get('programId', TOKEN_PROGRAM) == TOKEN_PROGRAM}


def _amount(row: Json | None) -> int:
    return int(row['uiTokenAmount']['amount']) if row else 0


def _succeeded(tx: Json) -> bool:
    meta = tx.get('meta') or {}
    return bool(meta) and meta.get('err') is None


def usdc_delta(tx: Json, token_account: str, mint: str) -> int:
    """Net change, in atomic units, of `token_account` for `mint`. 0 for failed transactions, for accounts not in
    the transaction, and for rows of another mint or token program. Negative when USDC left the account, including
    when the account was closed."""
    if not _succeeded(tx):
        return 0
    index = _index_of(tx, token_account)
    if index is None:
        return 0
    meta = tx['meta']
    pre = _usdc_rows(meta.get('preTokenBalances'), mint).get(index)
    post = _usdc_rows(meta.get('postTokenBalances'), mint).get(index)
    return _amount(post) - _amount(pre)


def owner_delta(tx: Json, owner: str, mint: str) -> int:
    """Net change across every `mint` token account owned by `owner` (not only its associated account)."""
    if not _succeeded(tx):
        return 0
    meta = tx['meta']
    pre = _usdc_rows(meta.get('preTokenBalances'), mint)
    post = _usdc_rows(meta.get('postTokenBalances'), mint)
    total = 0
    for index in set(pre) | set(post):
        row_owner = (post.get(index) or pre.get(index) or {}).get('owner')
        if row_owner == owner:
            total += _amount(post.get(index)) - _amount(pre.get(index))
    return total


def senders(tx: Json, mint: str) -> list[str]:
    """Owners whose `mint` balance decreased in a successful transaction (the apparent source wallets), sorted."""
    if not _succeeded(tx):
        return []
    meta = tx['meta']
    pre = _usdc_rows(meta.get('preTokenBalances'), mint)
    post = _usdc_rows(meta.get('postTokenBalances'), mint)
    result = {row['owner'] for index, row in pre.items()
              if row.get('owner') and _amount(post.get(index)) < _amount(row)}
    return sorted(result)


def fee_lamports(tx: Json) -> int:
    """Network fee paid by the fee payer, in lamports."""
    return int((tx.get('meta') or {}).get('fee') or 0)
