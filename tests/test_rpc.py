import pytest
import requests

from chainkit import __version__
from chainkit.rpc import RpcError, SolanaRpc


class Response:
    def __init__(self, status=200, body=None, invalid_json=False):
        self.status_code, self._body, self._invalid = status, body, invalid_json

    def json(self):
        if self._invalid:
            raise ValueError('bad json')
        return self._body


class Session:
    """Scripted session: `script[url]` is a list of replies (Response or Exception), consumed in order."""

    def __init__(self, script):
        self.script, self.calls, self.headers = script, [], {}

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        reply = self.script[url].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def ok(result):
    return Response(body={'jsonrpc': '2.0', 'id': 1, 'result': result})


def client(*urls_and_replies):
    script = {url: list(replies) for url, replies in urls_and_replies}
    session = Session(script)
    return SolanaRpc([url for url, _ in urls_and_replies], session=session), session


def test_requires_an_endpoint():
    with pytest.raises(ValueError):
        SolanaRpc([])


def test_sets_a_user_agent():
    _, session = client(('a', [ok('x')]))
    assert session.headers['User-Agent'] == f'chainkit/{__version__}'


@pytest.mark.parametrize('failure', [requests.ConnectionError('down'), requests.Timeout('slow'), Response(429),
                                     Response(503), Response(invalid_json=True), Response(body=['not', 'a', 'dict'])])
def test_fails_over_on_transient_problems(failure):
    rpc, session = client(('a', [failure]), ('b', [ok('hash')]))
    assert rpc.genesis_hash() == 'hash'
    assert [url for url, _ in session.calls] == ['a', 'b']


def test_all_transient_failures_raise_transient():
    rpc, _ = client(('a', [Response(500)]), ('b', [requests.ConnectionError('down')]))
    with pytest.raises(RpcError) as info:
        rpc.genesis_hash()
    assert info.value.transient and 'ConnectionError' in str(info.value)


def test_jsonrpc_error_is_final_and_carries_the_code():
    simulation_failed = Response(body={'error': {'code': -32002, 'message': 'Transaction simulation failed'}})
    rpc, session = client(('a', [simulation_failed]), ('b', [ok('never')]))
    with pytest.raises(RpcError) as info:
        rpc.send_transaction('AAAA')
    assert info.value.code == -32002 and not info.value.transient and len(session.calls) == 1


def test_string_error_and_non_integer_code():
    rpc, _ = client(('a', [Response(body={'error': 'boom'})]))
    with pytest.raises(RpcError, match='boom') as info:
        rpc.genesis_hash()
    assert info.value.code is None
    rpc2, _ = client(('a', [Response(body={'error': {'code': 'x', 'message': 'odd'}})]))
    with pytest.raises(RpcError) as info2:
        rpc2.genesis_hash()
    assert info2.value.code is None


def test_send_transaction_never_lets_the_node_retry():
    rpc, session = client(('a', [ok('sig')]))
    assert rpc.send_transaction('AAAA') == 'sig'
    params = session.calls[0][1]['params']
    assert params == ['AAAA', {'encoding': 'base64', 'skipPreflight': False, 'preflightCommitment': 'confirmed',
                               'maxRetries': 0}]


def test_typed_helpers():
    rpc, session = client(('a', [
        ok({'value': {'blockhash': 'bh', 'lastValidBlockHeight': 99}}), ok(1234), ok({'value': [None, {'x': 1}]}),
        ok({'slot': 1}), ok({'value': {'owner': 'o'}}), ok({'value': {'amount': '42'}}), ok({'value': 7}),
        ok(2039280), ok('airdrop-sig'),
    ]))
    assert rpc.latest_blockhash() == ('bh', 99)
    assert rpc.block_height() == 1234
    assert rpc.signature_statuses(['s1', 's2']) == [None, {'x': 1}]
    assert rpc.transaction('s') == {'slot': 1}
    assert rpc.account_info('acct', encoding='base64') == {'owner': 'o'}
    assert rpc.token_balance('acct') == 42
    assert rpc.sol_balance('acct') == 7
    assert rpc.minimum_balance_for_rent_exemption(165) == 2039280
    assert rpc.request_airdrop('acct', 1) == 'airdrop-sig'
    methods = [body['method'] for _, body in session.calls]
    assert methods == ['getLatestBlockhash', 'getBlockHeight', 'getSignatureStatuses', 'getTransaction',
                       'getAccountInfo', 'getTokenAccountBalance', 'getBalance', 'getMinimumBalanceForRentExemption',
                       'requestAirdrop']
    assert session.calls[3][1]['params'][1]['maxSupportedTransactionVersion'] == 0


def test_token_balance_of_missing_account_is_zero_but_other_errors_raise():
    rpc, _ = client(('a', [Response(body={'error': {'code': -32602, 'message': 'could not find account'}}),
                           Response(body={'error': {'code': -32005, 'message': 'node behind'}})]))
    assert rpc.token_balance('acct') == 0
    with pytest.raises(RpcError):
        rpc.token_balance('acct')


def test_paging_follows_every_page():
    first = [{'signature': f's{i}'} for i in range(1000)]
    rpc, session = client(('a', [ok(first), ok([{'signature': 'last'}])]))
    result = rpc.all_signatures_since('addr', until='old')
    assert len(result) == 1001 and result[-1]['signature'] == 'last'
    second_options = session.calls[1][1]['params'][1]
    assert second_options['before'] == 's999' and second_options['until'] == 'old'


def test_paging_beyond_the_limit_raises_instead_of_truncating():
    page = [{'signature': f's{i}'} for i in range(1000)]
    rpc, _ = client(('a', [ok(list(page)), ok(list(page))]))
    with pytest.raises(RpcError, match='more than 2 pages'):
        rpc.all_signatures_since('addr', until=None, max_pages=2)


def test_verify_client_uses_the_last_endpoint():
    rpc, session = client(('a', []), ('b', [ok('h')]))
    verifier = rpc.verify_client()
    assert verifier.urls == ['b'] and verifier.session is session
    assert verifier.genesis_hash() == 'h'
