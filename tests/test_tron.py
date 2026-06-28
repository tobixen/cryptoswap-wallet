"""Tests for TRON address derivation and base58check encoding."""

import pytest

pytest.importorskip("eth_account")

from cryptoswap_wallet.chains.tron import TronAdapter, base58check_encode  # noqa: E402

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


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def test_fetch_balance_uses_walletgetaccount_api(monkeypatch):
    """Balance must come from the standard /wallet/getaccount full-node API
    (keyless, served by many public nodes) rather than TronGrid's proprietary
    indexed /v1/accounts route."""
    adapter = TronAdapter(api_url="https://tron-rpc.publicnode.com")
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs.get("json")
        return _FakeResponse({"balance": 1234567})

    monkeypatch.setattr(adapter, "_post", fake_post)
    assert adapter.fetch_balance("TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH") == 1234567
    assert calls["url"] == "https://tron-rpc.publicnode.com/wallet/getaccount"
    assert calls["json"] == {
        "address": "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        "visible": True,
    }


def test_fetch_balance_zero_for_account_without_balance_field(monkeypatch):
    """An activated account with no TRX omits the 'balance' field; a fresh
    account returns {}. Both mean zero."""
    adapter = TronAdapter()
    monkeypatch.setattr(adapter, "_post", lambda url, **kw: _FakeResponse({}))
    assert adapter.fetch_balance("TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH") == 0
