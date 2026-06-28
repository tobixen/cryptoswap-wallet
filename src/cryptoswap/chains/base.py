"""The common interface every chain adapter implements.

The uniform surface across chains is intentionally small: address derivation,
balance lookup, and broadcast. Building the swap transaction is chain-specific
(UTXO vs account models differ), but every adapter funnels its result through
the shared :mod:`cryptoswap.verify` gate before signing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ChainAdapter(Protocol):
    chain: str  # e.g. "BTC"
    asset: str  # THORChain asset notation, e.g. "BTC.BTC"

    def derive_address(self, mnemonic: str, path: str) -> str: ...

    def fetch_balance(self, address: str) -> int:
        """Confirmed balance in the chain's native base unit (sats for BTC)."""
        ...

    def broadcast(self, raw_hex: str) -> str:
        """Broadcast a signed transaction; return its txid."""
        ...
