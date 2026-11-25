"""Program ids, clusters and the exact USDC mints.

Payments code should compare mints by exact address, never by name or symbol: anyone can create a token called
"USDC". The addresses below are Circle's official USDC mints.
"""

TOKEN_PROGRAM = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'  # nosec B105 (public program id) classic SPL Token
TOKEN_2022_PROGRAM = 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'  # nosec B105 (public program id)
ATA_PROGRAM = 'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'
SYSTEM_PROGRAM = '11111111111111111111111111111111'
COMPUTE_BUDGET_PROGRAM = 'ComputeBudget111111111111111111111111111111'
MEMO_PROGRAM = 'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr'

USDC_DECIMALS = 6
ATOMIC_PER_USDC = 10 ** USDC_DECIMALS
MAX_TRANSACTION_BYTES = 1232          # Solana packet limit for a serialized transaction
TOKEN_ACCOUNT_SIZE = 165              # bytes in an SPL token account (rent is charged on this size)
U64_MAX = 2 ** 64 - 1

# Genesis hashes identify a cluster with certainty (a URL does not). Genesis hashes and mints are verified
# against public RPC by tests/test_live.py (2026-11-25: mint account owned by the token program, 6 decimals).
CLUSTERS: dict[str, dict[str, str]] = {
    'mainnet-beta': {
        'genesis_hash': '5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d',
        'usdc_mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # Circle USDC (checked by live tests)
    },
    'devnet': {
        'genesis_hash': 'EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG',
        'usdc_mint': '4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU',  # Circle Devnet USDC
    },
}

# The only programs a USDC transfer built by chainkit ever touches.
ALLOWED_PROGRAMS = frozenset({TOKEN_PROGRAM, ATA_PROGRAM, COMPUTE_BUDGET_PROGRAM, MEMO_PROGRAM, SYSTEM_PROGRAM})


def usdc_mint(cluster: str) -> str:
    """Circle's USDC mint for `cluster` ('mainnet-beta' or 'devnet')."""
    try:
        return CLUSTERS[cluster]['usdc_mint']
    except KeyError:
        raise ValueError(f'Unknown cluster {cluster!r}') from None


def genesis_hash(cluster: str) -> str:
    """Genesis hash of `cluster`; compare with `SolanaRpc.genesis_hash()` before signing anything."""
    try:
        return CLUSTERS[cluster]['genesis_hash']
    except KeyError:
        raise ValueError(f'Unknown cluster {cluster!r}') from None


def cluster_for_genesis(genesis: str) -> str | None:
    """The cluster name for a genesis hash, or None if it is not a known cluster."""
    for name, values in CLUSTERS.items():
        if values['genesis_hash'] == genesis:
            return name
    return None
