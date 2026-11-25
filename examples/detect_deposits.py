"""List recent USDC deposits to a wallet, from any sender (wallets, exchanges, contracts).

    python examples/detect_deposits.py <wallet-address> [devnet|mainnet-beta]
"""
import sys

from chainkit.addresses import derive_ata
from chainkit.amounts import format_usdc
from chainkit.constants import usdc_mint
from chainkit.parse import senders, usdc_delta
from chainkit.rpc import SolanaRpc

ENDPOINTS = {'devnet': ['https://api.devnet.solana.com'],
             'mainnet-beta': ['https://api.mainnet-beta.solana.com', 'https://solana-rpc.publicnode.com']}


def main(wallet: str, cluster: str = 'devnet') -> None:
    rpc = SolanaRpc(ENDPOINTS[cluster])
    mint = usdc_mint(cluster)
    token_account = str(derive_ata(wallet, mint))
    print(f'USDC token account of {wallet}: {token_account}')
    for item in rpc.signatures_for_address(token_account, limit=20):
        tx = rpc.transaction(item['signature'])
        if tx is None:
            continue
        received = usdc_delta(tx, token_account, mint)
        if received > 0:
            print(f"+{format_usdc(received, 6)} USDC  from {', '.join(senders(tx, mint)) or 'unknown'}  "
                  f"{item['signature']}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'devnet')
