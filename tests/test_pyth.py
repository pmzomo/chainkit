import base64
import struct
from decimal import Decimal

import pytest

from chainkit import pyth

NOW = 1_800_000_000


def price_account(price=7_573_071_548, conf=2_361_433, expo=-8, publish_time=NOW - 30, level=1,
                  feed_id=pyth.SOL_USD_FEED_ID) -> bytes:
    body = b'\x22' * 8 + b'\x01' * 32
    body += bytes([0, 13]) if level == 0 else bytes([level])
    body += bytes.fromhex(feed_id)
    body += struct.pack('<qQiqqqQ', price, conf, expo, publish_time, publish_time - 1, price, conf)
    return body + struct.pack('<Q', 123)


class FakeRpc:
    def __init__(self, data: bytes | None, owner=pyth.PYTH_RECEIVER_PROGRAM):
        self.data, self.owner, self.params = data, owner, None

    def call(self, method, params=None):
        self.params = params
        assert method == 'getAccountInfo'
        if self.data is None:
            return {'value': None}
        return {'value': {'owner': self.owner, 'data': [base64.b64encode(self.data).decode(), 'base64']}}


def test_reads_a_valid_price():
    rpc = FakeRpc(price_account())
    reading = pyth.read_price(rpc, now=NOW)
    assert reading.price == Decimal('75.73071548') and reading.conf == Decimal('0.02361433')
    assert reading.fully_verified and reading.feed_id == pyth.SOL_USD_FEED_ID and reading.publish_time == NOW - 30
    assert rpc.params[0] == pyth.SOL_USD_PRICE_ACCOUNT and rpc.params[1]['encoding'] == 'base64'


def test_partial_verification_is_parsed_but_refused():
    assert pyth.parse_price_update(price_account(level=0)).price == Decimal('75.73071548')
    with pytest.raises(pyth.PythError, match='partially verified'):
        pyth.read_price(FakeRpc(price_account(level=0)), now=NOW)


def test_custom_limits_and_feed():
    other_feed = 'ab' * 32
    reading = pyth.read_price(FakeRpc(price_account(feed_id=other_feed, publish_time=NOW - 900)), feed_id=other_feed,
                              max_age_seconds=1000, now=NOW)
    assert reading.feed_id == other_feed


@pytest.mark.parametrize('rpc, message', [
    (FakeRpc(price_account(), owner='11111111111111111111111111111111'), 'not owned by the Pyth'),
    (FakeRpc(price_account(feed_id='ab' * 32)), 'different Pyth feed'),
    (FakeRpc(price_account(publish_time=NOW - 3600)), 'old'),
    (FakeRpc(price_account(conf=500_000_000)), 'confidence'),
    (FakeRpc(price_account(price=-5)), 'not positive'),
    (FakeRpc(price_account(price=0)), 'not positive'),
    (FakeRpc(None), 'does not exist'),
    (FakeRpc(b'\x00' * 20), 'too short'),
    (FakeRpc(price_account(level=7)), 'Unknown verification level'),
])
def test_untrustworthy_accounts_are_refused(rpc, message):
    with pytest.raises(pyth.PythError, match=message):
        pyth.read_price(rpc, now=NOW)
