"""Tests for the bitcoinlib-backed BtcAdapter.

The build path is the safety-critical one: a constructed (unsigned) swap tx must
pass the same verify gate that guards broadcasting. Skipped if bitcoinlib (the
``btc`` extra) is not installed.
"""

import pytest

pytest.importorskip("bitcoinlib")

from cryptoswap.chains.btc import BtcAdapter  # noqa: E402
from cryptoswap.chains.coins import Utxo  # noqa: E402
from cryptoswap.verify import SwapPlan, verify_btc_swap  # noqa: E402

MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)
PATH = "m/84'/0'/0'/0/0"
EXPECTED_ADDR = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
VAULT = "bc1qct4mxayrdy96d4py20l4u02mu06r667f42p9fp"
MEMO = "=:ETH.ETH:0x1111111111111111111111111111111111111111"


def test_derive_address_matches_bip84_vector():
    assert BtcAdapter().derive_address(MNEMONIC, PATH) == EXPECTED_ADDR


def test_built_swap_passes_verify_gate():
    a = BtcAdapter()
    addr = a.derive_address(MNEMONIC, PATH)
    utxos = [Utxo(txid="aa" * 32, vout=0, value=200000, address=addr)]
    built = a.build_unsigned_swap(
        mnemonic=MNEMONIC,
        path=PATH,
        utxos=utxos,
        vault_address=VAULT,
        amount=178100,
        memo=MEMO,
        fee_rate=2,
    )
    plan = SwapPlan(
        inbound_address=VAULT, amount=178100, memo=MEMO, expiry=9_999_999_999
    )
    problems = verify_btc_swap(
        built.outputs,
        fee=built.fee,
        plan=plan,
        owned_addresses={addr, built.change_address},
        now=0,
        max_fee=100_000,
    )
    assert problems == []


def test_built_swap_is_signable():
    a = BtcAdapter()
    addr = a.derive_address(MNEMONIC, PATH)
    utxos = [Utxo(txid="aa" * 32, vout=0, value=200000, address=addr)]
    built = a.build_unsigned_swap(
        mnemonic=MNEMONIC,
        path=PATH,
        utxos=utxos,
        vault_address=VAULT,
        amount=178100,
        memo=MEMO,
        fee_rate=2,
    )
    raw = a.sign(built, mnemonic=MNEMONIC, path=PATH)
    assert isinstance(raw, str) and len(raw) > 0
