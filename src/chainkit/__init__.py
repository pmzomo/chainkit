"""chainkit: production-grade building blocks for USDC payments on Solana, in Python.

Modules (import what you need; nothing here touches the network on import):

    chainkit.constants     program ids, clusters, Circle's exact USDC mints
    chainkit.amounts       exact USDC amounts as integer atomic units, never floats
    chainkit.addresses     strict address parsing, associated token account derivation
    chainkit.instructions  range-checked transferChecked, createIdempotent, compute budget, memo
    chainkit.transactions  build a USDC transfer; decode any message into facts before signing
    chainkit.parse         detect payments from balance deltas (works for any wallet or exchange)
    chainkit.rpc           JSON-RPC client with ordered failover and transient-error signalling
    chainkit.pyth          verified SOL/USD (or any Pyth feed) read directly from Solana
"""

__version__ = '0.1.0'
__all__ = ['__version__']
