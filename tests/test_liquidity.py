"""Tests for THORChain liquidity-provision memos."""

import pytest

from cryptoswap_wallet.liquidity import add_liquidity_memo, withdraw_liquidity_memo


def test_add_memo():
    assert add_liquidity_memo("BTC.BTC") == "+:BTC.BTC"


def test_withdraw_memo_full():
    assert withdraw_liquidity_memo("BTC.BTC", 10000) == "-:BTC.BTC:10000"


def test_withdraw_memo_partial():
    assert withdraw_liquidity_memo("ETH.ETH", 2500) == "-:ETH.ETH:2500"


def test_withdraw_memo_rejects_out_of_range():
    with pytest.raises(ValueError):
        withdraw_liquidity_memo("BTC.BTC", 0)
    with pytest.raises(ValueError):
        withdraw_liquidity_memo("BTC.BTC", 10001)
