"""Gap-limit HD address scanning, independent of any wallet library.

The chain-specific operations (derive an address, check on-chain history, fetch
UTXOs) are injected, so the gap logic stays pure and unit-testable; the real
implementations come from :class:`cryptoswap.chains.btc.BtcAdapter`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from cryptoswap.chains.coins import Utxo

DEFAULT_GAP_LIMIT = 20


def scan_account(
    *,
    derive_address: Callable[[str], str],
    has_history: Callable[[str], bool],
    fetch_utxos: Callable[[str], list[Utxo]],
    account: str,
    gap_limit: int = DEFAULT_GAP_LIMIT,
    branches: tuple[int, ...] = (0, 1),
) -> list[Utxo]:
    """Scan an account's receive/change branches, returning found UTXOs.

    Gap counting uses *history* (used-but-empty addresses keep the scan going),
    while funds come from ``fetch_utxos``. Each returned UTXO has its ``path``
    set so the caller can sign it.
    """
    found: list[Utxo] = []
    for branch in branches:
        gap = 0
        index = 0
        while gap < gap_limit:
            path = f"{account}/{branch}/{index}"
            address = derive_address(path)
            if has_history(address):
                gap = 0
                found.extend(
                    dataclasses.replace(utxo, path=path)
                    for utxo in fetch_utxos(address)
                )
            else:
                gap += 1
            index += 1
    return found
