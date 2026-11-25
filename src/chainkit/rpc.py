"""Minimal Solana JSON-RPC client with ordered failover across several endpoints.

Endpoints are tried in order. Network errors, HTTP 429 and 5xx, and invalid JSON move on to the next endpoint
(`RpcError.transient` is True when every endpoint failed that way, so a retry later is safe). A JSON-RPC error
answer is final and raised immediately (`transient` False): another node would give the same answer.

`verify_client()` returns a client pinned to the last configured endpoint, so a critical fact (for example that a
deposit is finalized) can be confirmed by a second, independent provider.
"""
import itertools
from typing import Any, cast

import requests

from . import __version__

_ids = itertools.count(1)
Json = dict[str, Any]


class RpcError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, transient: bool = False):
        super().__init__(message)
        self.code = code
        self.transient = transient


class SolanaRpc:
    def __init__(self, urls: list[str], timeout: float = 20.0, session: requests.Session | None = None):
        if not urls:
            raise ValueError('At least one RPC URL is required.')
        self.urls = list(urls)
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault('User-Agent', f'chainkit/{__version__}')

    def verify_client(self) -> 'SolanaRpc':
        return SolanaRpc([self.urls[-1]], self.timeout, self.session)

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        last_error: RpcError | None = None
        for url in self.urls:
            try:
                response = self.session.post(url, json={'jsonrpc': '2.0', 'id': next(_ids), 'method': method,
                                                        'params': params or []}, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = RpcError(f'{method}: {exc.__class__.__name__}', transient=True)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_error = RpcError(f'{method}: HTTP {response.status_code}', transient=True)
                continue
            try:
                body = response.json()
            except ValueError:
                last_error = RpcError(f'{method}: invalid JSON', transient=True)
                continue
            if not isinstance(body, dict):
                last_error = RpcError(f'{method}: unexpected response', transient=True)
                continue
            if 'error' in body:
                error = body['error'] if isinstance(body['error'], dict) else {'message': str(body['error'])}
                code = error.get('code')
                raise RpcError(f"{method}: {error.get('message')}", code=code if isinstance(code, int) else None)
            return body.get('result')
        raise last_error or RpcError(f'{method}: no RPC endpoint answered', transient=True)

    # Typed helpers -------------------------------------------------------------------------
    def genesis_hash(self) -> str:
        return str(self.call('getGenesisHash'))

    def latest_blockhash(self, commitment: str = 'confirmed') -> tuple[str, int]:
        """(blockhash, lastValidBlockHeight). A transaction using this blockhash can never land after that height."""
        value = self.call('getLatestBlockhash', [{'commitment': commitment}])['value']
        return value['blockhash'], int(value['lastValidBlockHeight'])

    def block_height(self, commitment: str = 'confirmed') -> int:
        return int(self.call('getBlockHeight', [{'commitment': commitment}]))

    def send_transaction(self, tx_base64: str) -> str:
        """Submit with preflight simulation and no node-side retries (the caller owns retry decisions)."""
        options = {'encoding': 'base64', 'skipPreflight': False, 'preflightCommitment': 'confirmed', 'maxRetries': 0}
        return str(self.call('sendTransaction', [tx_base64, options]))

    def signature_statuses(self, signatures: list[str]) -> list[Json | None]:
        value = self.call('getSignatureStatuses', [signatures, {'searchTransactionHistory': True}])['value']
        return cast(list[Json | None], value)

    def transaction(self, signature: str, commitment: str = 'finalized') -> Json | None:
        options = {'encoding': 'jsonParsed', 'commitment': commitment, 'maxSupportedTransactionVersion': 0}
        return cast(Json | None, self.call('getTransaction', [signature, options]))

    def signatures_for_address(self, address: str, until: str | None = None, limit: int = 100,
                               commitment: str = 'finalized', before: str | None = None) -> list[Json]:
        options: dict[str, Any] = {'limit': limit, 'commitment': commitment}
        if until:
            options['until'] = until
        if before:
            options['before'] = before
        return cast(list[Json], self.call('getSignaturesForAddress', [address, options]))

    def all_signatures_since(self, address: str, until: str | None, commitment: str = 'finalized',
                             max_pages: int = 50) -> list[Json]:
        """Every signature newer than `until` (newest first), following pages so none are skipped.
        Raises RpcError if more than `max_pages` pages exist, rather than silently returning a partial list."""
        result: list[Json] = []
        before = None
        for _ in range(max_pages):
            page = self.signatures_for_address(address, until=until, limit=1000, commitment=commitment,
                                               before=before)
            result.extend(page)
            if len(page) < 1000:
                return result
            before = page[-1]['signature']
        raise RpcError(f'getSignaturesForAddress: more than {max_pages} pages for {address}', transient=True)

    def account_info(self, address: str, commitment: str = 'confirmed', encoding: str = 'jsonParsed') -> Json | None:
        value = self.call('getAccountInfo', [address, {'encoding': encoding, 'commitment': commitment}])['value']
        return cast(Json | None, value)

    def token_balance(self, token_account: str, commitment: str = 'finalized') -> int:
        """Balance in atomic units; 0 if the token account does not exist yet."""
        try:
            value = self.call('getTokenAccountBalance', [token_account, {'commitment': commitment}])['value']
        except RpcError as exc:
            if exc.code == -32602:  # invalid param: the account does not exist (yet)
                return 0
            raise
        return int(value['amount'])

    def sol_balance(self, address: str, commitment: str = 'finalized') -> int:
        return int(self.call('getBalance', [address, {'commitment': commitment}])['value'])

    def minimum_balance_for_rent_exemption(self, size: int) -> int:
        """Lamports an account of `size` bytes must hold (165 bytes for a token account)."""
        return int(self.call('getMinimumBalanceForRentExemption', [size]))

    def request_airdrop(self, address: str, lamports: int) -> str:
        """Devnet/testnet only."""
        return str(self.call('requestAirdrop', [address, lamports]))
