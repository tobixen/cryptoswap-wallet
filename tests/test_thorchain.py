"""Tests for the THORChain REST client's parsing logic.

Fixtures are trimmed real responses captured from the live API; see README.
"""

import pytest

from cryptoswap_wallet.thorchain import (
    ThorchainClient,
    ThorchainError,
    normalize_txid,
    parse_inbound_addresses,
    parse_quote,
)

BTC_TO_ETH_QUOTE = {
    "inbound_address": "bc1qct4mxayrdy96d4py20l4u02mu06r667f42p9fp",
    "memo": "=:ETH.ETH:0x1111111111111111111111111111111111111111:6700000",
    "fees": {
        "asset": "ETH.ETH",
        "affiliate": "0",
        "outbound": "15820",
        "liquidity": "13590",
        "total": "29410",
        "slippage_bps": 19,
        "total_bps": 43,
    },
    "expiry": 1782589433,
    "dust_threshold": "1000",
    "recommended_min_amount_in": "7761",
    "recommended_gas_rate": "4",
    "gas_rate_units": "satsperbyte",
    "expected_amount_out": "6768430",
    "max_streaming_quantity": 1,
    "streaming_swap_blocks": 1,
    "total_swap_seconds": 606,
}

ETH_TO_TRX_QUOTE = {  # EVM source chains carry a router contract address
    "inbound_address": "0x85034887f6656d610c38ef1710208495791fb146",
    "router": "0xD37BbE5744D730a1d98d8DC97c42F0Ca46aD7146",
    "memo": "=:TRON.TRX:TXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "fees": {
        "asset": "TRON.TRX",
        "affiliate": "0",
        "outbound": "151819000",
        "liquidity": "25451600",
        "total": "177270600",
        "slippage_bps": 20,
        "total_bps": 137,
    },
    "expiry": 1782589475,
    "dust_threshold": "1000",
    "recommended_min_amount_in": "98391",
    "recommended_gas_rate": "15",
    "gas_rate_units": "gwei",
    "expected_amount_out": "12546254700",
    "max_streaming_quantity": 1,
    "streaming_swap_blocks": 1,
    "total_swap_seconds": 30,
}

INBOUND_ADDRESSES = [
    {
        "chain": "BTC",
        "gas_rate": "3",
        "gas_rate_units": "satsperbyte",
        "outbound_fee": "1058",
        "dust_threshold": "1000",
        "halted": False,
        "global_trading_paused": False,
        "chain_trading_paused": False,
    },
    {
        "chain": "ETH",
        "gas_rate": "15",
        "gas_rate_units": "gwei",
        "outbound_fee": "15821",
        "dust_threshold": "1000",
        "halted": False,
        "global_trading_paused": False,
        "chain_trading_paused": False,
    },
    {
        "chain": "TRON",
        "gas_rate": "25387800",
        "gas_rate_units": "sun",
        "outbound_fee": "151819000",
        "dust_threshold": "10000000",
        "halted": True,
        "global_trading_paused": False,
        "chain_trading_paused": False,
    },
]


def test_parse_quote_btc_to_eth():
    q = parse_quote(BTC_TO_ETH_QUOTE)
    assert q.inbound_address == "bc1qct4mxayrdy96d4py20l4u02mu06r667f42p9fp"
    assert q.expected_amount_out == 6768430
    assert q.recommended_min_amount_in == 7761
    assert q.memo.startswith("=:ETH.ETH:")
    assert q.fees.total == 29410
    assert q.fees.total_bps == 43
    assert q.fees.slippage_bps == 19
    assert q.dust_threshold == 1000
    assert q.router is None


def test_parse_quote_evm_source_has_router():
    q = parse_quote(ETH_TO_TRX_QUOTE)
    assert q.router == "0xD37BbE5744D730a1d98d8DC97c42F0Ca46aD7146"


def test_parse_quote_without_memo():
    payload = dict(BTC_TO_ETH_QUOTE)
    del payload["memo"]
    assert parse_quote(payload).memo is None


def test_parse_quote_error_raises():
    with pytest.raises(ThorchainError):
        parse_quote({"error": "swap too small; recommended minimum: 7761"})


def test_parse_inbound_addresses():
    chains = parse_inbound_addresses(INBOUND_ADDRESSES)
    assert chains["BTC"].gas_rate == 3
    assert chains["BTC"].outbound_fee == 1058
    assert chains["BTC"].tradable is True
    assert chains["TRON"].tradable is False  # halted


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # EVM hashes are quoted 0x-prefixed (explorers, our broadcast output),
        # but thornode/mayanode index them without the prefix.
        ("0x3a8927cc190f91d9", "3a8927cc190f91d9"),
        ("0X3A8927CC190F91D9", "3A8927CC190F91D9"),
        # already in the indexed form -> untouched.
        ("3a8927cc190f91d9", "3a8927cc190f91d9"),
        # UTXO/Cosmos txids have no 0x prefix -> no-op (no regression).
        ("ABCDEF0123456789CABBAGE", "ABCDEF0123456789CABBAGE"),
    ],
)
def test_normalize_txid_strips_evm_prefix(raw, expected):
    assert normalize_txid(raw) == expected


def test_tx_status_queries_without_0x_prefix(monkeypatch):
    """Regression: a 0x-prefixed hash must not be sent verbatim, or Maya/THOR
    return an empty 'never observed' status for an already-confirmed inbound."""
    client = ThorchainClient("https://node.example", path_prefix="mayachain")
    captured: dict[str, str] = {}

    class _Resp:
        def raise_for_status(self) -> None: ...

        def json(self) -> dict[str, object]:
            return {"ok": True}

    def fake_get(url: str, **_kw: object) -> _Resp:
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr(client, "_get", fake_get)
    client.tx_status("0x3a8927cc190f91d9")
    assert (
        captured["url"] == "https://node.example/mayachain/tx/status/3a8927cc190f91d9"
    )
