"""Tests for TRON address derivation and base58check encoding."""

import pytest

pytest.importorskip("eth_account")

from cryptoswap.chains.tron import TronAdapter, base58check_encode  # noqa: E402

MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)


def test_base58check_against_known_tron_address():
    # Canonical hex <-> base58 mapping: the TRON USDT (TRC-20) contract address.
    payload = bytes.fromhex("41a614f803b6fd780986a42c78ec9c7f77e6ded13c")
    assert base58check_encode(payload) == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def test_derive_tron_address_vector():
    addr = TronAdapter().derive_address(MNEMONIC)
    assert addr == "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
    assert addr.startswith("T")
    assert len(addr) == 34
