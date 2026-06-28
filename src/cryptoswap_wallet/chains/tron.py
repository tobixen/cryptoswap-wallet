"""TRON chain adapter for THORChain swaps.

Currently supports TRON as a swap *destination*: deriving the Tron address from
the seed and reading the TRX balance (via TronGrid). A Tron address is the
keccak-derived 20-byte account (same as Ethereum) prefixed with 0x41 and
base58check-encoded. Spending FROM Tron (a source adapter) is future work.
"""

from __future__ import annotations

import hashlib

from eth_account import Account
from eth_account.signers.local import LocalAccount

from cryptoswap_wallet.chains.base import BalanceReport
from cryptoswap_wallet.net import HttpClient

DEFAULT_TRON_DERIVATION = "m/44'/195'/0'/0/0"
DEFAULT_TRON_API = "https://api.trongrid.io"
TRON_MAINNET_PREFIX = 0x41
TRX_DECIMALS = 6
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

Account.enable_unaudited_hdwallet_features()


def base58check_encode(payload: bytes) -> str:
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    data = payload + checksum
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, remainder = divmod(n, 58)
        out = _B58_ALPHABET[remainder] + out
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + out


class TronAdapter(HttpClient):
    chain = "TRON"
    asset = "TRON.TRX"

    def __init__(self, api_url: str = DEFAULT_TRON_API, timeout: float = 20.0) -> None:
        super().__init__(timeout)
        self.api_url = api_url.rstrip("/")

    def _key(self, mnemonic: str, path: str) -> LocalAccount:
        return Account.from_mnemonic(mnemonic, account_path=path)

    def derive_address(self, mnemonic: str, path: str = DEFAULT_TRON_DERIVATION) -> str:
        addr20 = bytes.fromhex(self._key(mnemonic, path).address[2:])
        return base58check_encode(bytes([TRON_MAINNET_PREFIX]) + addr20)

    def fetch_balance(self, address: str) -> int:
        """Confirmed TRX balance in sun (1 TRX = 1e6 sun); 0 for unused accounts."""
        resp = self._get(f"{self.api_url}/v1/accounts/{address}")
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return int(data[0].get("balance", 0)) if data else 0

    def wallet_balance(self, mnemonic: str) -> BalanceReport:
        address = self.derive_address(mnemonic)
        return BalanceReport(
            symbol="TRX",
            confirmed=self.fetch_balance(address),
            decimals=TRX_DECIMALS,
            note=f"({address})",
        )
