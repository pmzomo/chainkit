"""What does it cost, in USD, to create a recipient's USDC account? Live rent from Solana, price from Pyth on-chain.

    python examples/account_setup_cost.py
"""
from decimal import Decimal

from chainkit import pyth
from chainkit.constants import TOKEN_ACCOUNT_SIZE
from chainkit.rpc import SolanaRpc


def main() -> None:
    rpc = SolanaRpc(['https://api.mainnet-beta.solana.com', 'https://solana-rpc.publicnode.com'])
    rent_lamports = rpc.minimum_balance_for_rent_exemption(TOKEN_ACCOUNT_SIZE)
    price = pyth.read_price(rpc)
    sol = Decimal(rent_lamports) / Decimal(1_000_000_000)
    print(f'Token account rent: {rent_lamports} lamports = {sol} SOL')
    print(f'SOL/USD (Pyth on Solana, verified): {price.price:.4f} +/- {price.conf:.4f}')
    print(f'One-time account setup: about ${sol * price.price:.4f}')


if __name__ == '__main__':
    main()
