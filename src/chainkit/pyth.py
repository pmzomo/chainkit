"""Pyth price feeds read directly from Solana (no API key, no Django).

Pyth's push oracle keeps a sponsored `PriceUpdateV2` account per feed, written by the Pyth Solana Receiver program.
We read the SOL/USD account with getAccountInfo and trust it only if:
  * the account is owned by the Pyth Solana Receiver program,
  * the update is fully verified (all Wormhole guardian signatures checked on-chain),
  * the embedded feed id is SOL/USD,
  * it is recent and its confidence interval is tight.

PriceUpdateV2 layout (Anchor/Borsh):
  8  discriminator
  32 write_authority
  1  verification_level variant (0 = Partial, followed by u8 num_signatures; 1 = Full)
  PriceFeedMessage: 32 feed_id, i64 price, u64 conf, i32 exponent, i64 publish_time, i64 prev_publish_time,
                    i64 ema_price, u64 ema_conf
  8  posted_slot
"""
import base64
import struct
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

PYTH_RECEIVER_PROGRAM = 'rec5EKMGg6MxZYaMdyBfgwp4d5rB9T1VQH5pJv5LtFJ'
SOL_USD_FEED_ID = 'ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d'
# Sponsored SOL/USD price feed account (shard 0), the same address on mainnet and devnet.
SOL_USD_PRICE_ACCOUNT = '7UVimffxr9ow1uXYxsr4LHAcV58mLzhmwaeKvJ1pjLiE'
_HEADER = 8 + 32
_PRICE = struct.Struct('<qQiq')  # price, conf, exponent, publish_time


class SupportsCall(Protocol):
    """Anything with a JSON-RPC `call(method, params)`, such as `chainkit.rpc.SolanaRpc`."""

    def call(self, method: str, params: list[Any] | None = None) -> Any: ...


class PythError(ValueError):
    """The account is not a trustworthy, current Pyth price."""


@dataclass(frozen=True)
class PythPrice:
    feed_id: str
    price: Decimal
    conf: Decimal
    publish_time: int
    fully_verified: bool


def parse_price_update(data: bytes) -> PythPrice:
    if len(data) < _HEADER + 2 + 32 + _PRICE.size:
        raise PythError('Account data is too short for a Pyth PriceUpdateV2.')
    offset = _HEADER
    level = data[offset]
    if level == 0:
        offset += 2      # Partial { num_signatures: u8 }
    elif level == 1:
        offset += 1      # Full
    else:
        raise PythError(f'Unknown verification level {level}.')
    feed_id = data[offset:offset + 32].hex()
    offset += 32
    raw_price, raw_conf, exponent, publish_time = _PRICE.unpack_from(data, offset)
    scale = Decimal(10) ** exponent
    return PythPrice(feed_id=feed_id, price=Decimal(raw_price) * scale, conf=Decimal(raw_conf) * scale,
                     publish_time=publish_time, fully_verified=level == 1)


def read_price(rpc: SupportsCall, account: str = SOL_USD_PRICE_ACCOUNT, feed_id: str = SOL_USD_FEED_ID, *,
               max_age_seconds: int = 300, max_conf_ratio: Decimal = Decimal('0.02'), now: float | None = None
               ) -> PythPrice:
    """Fetch and validate a Pyth price account through a `chainkit.rpc.SolanaRpc`."""
    value = rpc.call('getAccountInfo', [account, {'encoding': 'base64', 'commitment': 'confirmed'}])['value']
    if value is None:
        raise PythError(f'Pyth price account {account} does not exist on this cluster.')
    if value.get('owner') != PYTH_RECEIVER_PROGRAM:
        raise PythError('Price account is not owned by the Pyth Solana Receiver program.')
    price = parse_price_update(base64.b64decode(value['data'][0]))
    if not price.fully_verified:
        raise PythError('Pyth price update is only partially verified.')
    if price.feed_id != feed_id:
        raise PythError('Price account holds a different Pyth feed.')
    if price.price <= 0:
        raise PythError('Pyth price is not positive.')
    age = (now if now is not None else time.time()) - price.publish_time
    if age > max_age_seconds:
        raise PythError(f'Pyth price is {int(age)} s old (limit {max_age_seconds} s).')
    if price.conf / price.price > max_conf_ratio:
        raise PythError('Pyth confidence interval is too wide to price fees.')
    return price
