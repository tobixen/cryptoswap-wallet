"""Best-effort external spot-price lookup, to compare a swap quote against a
public market mid.

This is **advisory only**: it is used to print a "vs market" line so the user
can see the *total* realised cost of a swap (protocol fees + slip + the
pool-vs-market spread that arbitrageurs capture), which the quote's own fee
fields do not include. It is never consulted when building, verifying, or
broadcasting a transaction — a wrong or unreachable price must never change what
gets signed, so every caller treats a failure here as "just skip the line".

Keyless (CoinGecko ``simple/price``). The pure helpers are kept free of I/O so
they can be unit-tested against a recorded response.
"""

from __future__ import annotations

from cryptoswap_wallet.net import HttpClient

DEFAULT_COINGECKO = "https://api.coingecko.com/api/v3"

# Wallet ASSET key (the --from / --to values) -> CoinGecko coin id. Tokens map
# to the underlying asset regardless of chain (USDT on ETH or TRON is "tether").
# Assets absent here simply get no market line (e.g. RUNE/CACAO/synths).
COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "TRX": "tron",
    "LTC": "litecoin",
    "DOGE": "dogecoin",
    "BCH": "bitcoin-cash",
    "DASH": "dash",
    "BNB": "binancecoin",
    "USDT-ETH": "tether",
    "USDT-TRON": "tether",
    "USDC-ETH": "usd-coin",
}


def parse_spot(payload: dict) -> dict[str, float]:
    """Extract ``{coin_id: usd_price}`` from a CoinGecko ``simple/price`` body."""
    return {
        coin: float(v["usd"])
        for coin, v in payload.items()
        if isinstance(v, dict) and "usd" in v
    }


def market_out(amount_in: float, price_in: float, price_out: float) -> float:
    """Destination units a perfect (fee-less, slip-less) mid-price swap would yield.

    ``amount_in`` is in whole source units; prices are USD per whole unit.
    """
    if price_out <= 0:
        raise ValueError("non-positive destination price")
    return amount_in * price_in / price_out


def loss_vs_market_bps(quoted_out: float, market: float) -> float:
    """How far the quoted output falls below the market mid, in basis points.

    Positive = you receive less than market (the normal case: fees + slip +
    spread). Negative would mean the pool priced in your favour.
    """
    if market <= 0:
        return 0.0
    return (market - quoted_out) / market * 10_000


class PriceFeed(HttpClient):
    """Thin keyless client for CoinGecko spot prices (USD)."""

    def __init__(
        self, base_url: str = DEFAULT_COINGECKO, timeout: float = 10.0
    ) -> None:
        super().__init__(timeout)
        self.base_url = base_url.rstrip("/")

    def spot_usd(self, coin_ids: list[str]) -> dict[str, float]:
        resp = self._get(
            f"{self.base_url}/simple/price",
            params={"ids": ",".join(sorted(set(coin_ids))), "vs_currencies": "usd"},
        )
        resp.raise_for_status()
        return parse_spot(resp.json())
