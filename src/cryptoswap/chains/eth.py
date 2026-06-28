"""Minimal Ethereum support: deriving the destination address from the seed.

This is the seed of a future full EthAdapter; for now it only derives the
checksummed (EIP-55) address so BTC->ETH swaps can target the same wallet.
"""

from __future__ import annotations

from bitcoinlib.keys import HDKey
from bitcoinlib.mnemonic import Mnemonic
from Crypto.Hash import keccak

DEFAULT_ETH_DERIVATION = "m/44'/60'/0'/0/0"


def _keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def to_checksum_address(addr: bytes) -> str:
    """EIP-55 checksum encoding of a 20-byte address."""
    lower = addr.hex()
    digest = _keccak256(lower.encode()).hex()
    encoded = "".join(
        c.upper() if c.isalpha() and int(d, 16) >= 8 else c
        for c, d in zip(lower, digest, strict=False)
    )
    return "0x" + encoded


class EthAdapter:
    chain = "ETH"
    asset = "ETH.ETH"

    def derive_address(self, mnemonic: str, path: str = DEFAULT_ETH_DERIVATION) -> str:
        seed = Mnemonic().to_seed(mnemonic)
        key = HDKey.from_seed(seed).subkey_for_path(path)
        pubkey = key.public_uncompressed_byte  # 0x04 || X(32) || Y(32)
        return to_checksum_address(_keccak256(pubkey[1:])[-20:])
