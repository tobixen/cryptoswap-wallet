"""Opt-in integration tests against live THORChain (read-only, no funds moved).

Excluded by default; run with `uv run pytest -m network`. They catch API drift
and stale hard-coded asset strings (e.g. the USDT contracts) that unit tests
with recorded fixtures cannot.
"""

import pytest

from cryptoswap_wallet.cli import ASSET
from cryptoswap_wallet.thorchain import ThorchainClient

pytestmark = pytest.mark.network

ETH_DEST = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
BTC_DEST = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
TRON_DEST = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
LTC_DEST = "ltc1qjmxnz78nmc8nq77wuxh25n2es7rzm5c2rkk4wh"
DOGE_DEST = "DH5yaieqoZN36fDVciNyRueRGvGLR3mr7L"
BCH_DEST = "qpm2qsznhks23z7629mms6s4cwef74vcwvy22gdx6a"


def test_inbound_addresses_live():
    with ThorchainClient() as thor:
        chains = thor.inbound_addresses()
    assert chains["BTC"].tradable
    assert chains["BTC"].address  # vault address present (used by LP)


def test_btc_to_eth_quote_live():
    with ThorchainClient() as thor:
        quote = thor.quote_swap("BTC.BTC", "ETH.ETH", 178100, ETH_DEST)
    assert quote.memo and quote.memo.startswith("=:")
    assert quote.expected_amount_out > 0


def test_hardcoded_usdt_assets_still_quote_live():
    # Guards the contract strings baked into cli.ASSET against THORChain changes.
    with ThorchainClient() as thor:
        to_tron = thor.quote_swap(ASSET["BTC"], ASSET["USDT-TRON"], 178100, TRON_DEST)
        to_eth = thor.quote_swap(ASSET["BTC"], ASSET["USDT-ETH"], 178100, ETH_DEST)
    assert to_tron.expected_amount_out > 0
    assert to_eth.expected_amount_out > 0


def test_eth_usdt_source_quote_live():
    with ThorchainClient() as thor:
        quote = thor.quote_swap(ASSET["USDT-ETH"], "BTC.BTC", 5_000_000_000, BTC_DEST)
    assert quote.router  # token source needs the router for depositWithExpiry
    assert quote.expected_amount_out > 0


@pytest.mark.parametrize(
    ("asset", "dest"),
    [("LTC", LTC_DEST), ("DOGE", DOGE_DEST), ("BCH", BCH_DEST)],
)
def test_destination_only_assets_quote_live(asset, dest):
    # Item 3: BTC -> LTC/DOGE/BCH to an external address. Confirms the pool is
    # live and the quoted memo actually pays the destination we asked for.
    with ThorchainClient() as thor:
        quote = thor.quote_swap(ASSET["BTC"], ASSET[asset], 5_000_000, dest)
    assert quote.expected_amount_out > 0
    assert quote.memo and dest in quote.memo
