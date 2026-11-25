from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from chainkit.amounts import AmountError, format_usdc, from_atomic, to_atomic
from chainkit.constants import U64_MAX


@pytest.mark.parametrize('text, atomic', [
    ('150.25', 150_250_000), ('0.000001', 1), ('1', 1_000_000), (' 7.5 ', 7_500_000), ('1,250.50', 1_250_500_000),
    ('12,345,678.123456', 12_345_678_123_456), ('0001.10', 1_100_000), ('18446744073709.551615', U64_MAX),
])
def test_valid_strings(text, atomic):
    assert to_atomic(text) == atomic


def test_decimals_are_accepted():
    assert to_atomic(Decimal('2.000001')) == 2_000_001
    assert to_atomic(Decimal('1E+2')) == 100_000_000  # an explicit Decimal is unambiguous


@pytest.mark.parametrize('bad', [
    '0', '0.0', '-1', '+1', '1.0000001', 'abc', '', ' ', '1e3', '1E3', 'NaN', 'Infinity', '1,0,0', ',100',
    '1,00.5', '1.', '.5', '1 000', '1_000', '18446744073709.551616', '١٢٣',
])
def test_invalid_strings(bad):
    with pytest.raises(AmountError):
        to_atomic(bad)


@pytest.mark.parametrize('bad', [1.5, 0.1, True, 10, None, b'1', [1], Decimal('NaN'), Decimal('-1'),
                                 Decimal('0'), Decimal('0.0000001'), Decimal('18446744073709.551616')])
def test_invalid_types_and_decimals(bad):
    with pytest.raises(AmountError):
        to_atomic(bad)


def test_from_atomic_and_format():
    assert from_atomic(150_250_000) == Decimal('150.250000')
    assert from_atomic(-5) == Decimal('-0.000005')
    assert format_usdc(1_234_567_891) == '1,234.57'
    assert format_usdc(1_234_565_000) == '1,234.57'      # half up
    assert format_usdc(1, places=6) == '0.000001'
    assert format_usdc(999_999, places=0) == '1'
    for bad in (1.5, '10', True, None):
        with pytest.raises(TypeError):
            from_atomic(bad)
    with pytest.raises(ValueError):
        format_usdc(1, places=7)


@given(st.integers(min_value=1, max_value=U64_MAX))
def test_round_trip_is_exact(atomic):
    assert to_atomic(str(from_atomic(atomic))) == atomic
    assert to_atomic(format_usdc(atomic, places=6)) == atomic


@given(st.decimals(min_value=Decimal('0.000001'), max_value=Decimal('1000000000'), places=6, allow_nan=False))
def test_decimal_input_matches_string_input(value):
    assert to_atomic(value) == to_atomic(format(value, 'f'))
