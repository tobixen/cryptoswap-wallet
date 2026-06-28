"""Tests for ETH address derivation (destination for BTC->ETH swaps)."""

import pytest

pytest.importorskip("bitcoinlib")

from cryptoswap_wallet.chains.eth import EthAdapter, to_checksum_address  # noqa: E402

MNEMONIC = (
    "abandon abandon abandon abandon abandon abandon "
    "abandon abandon abandon abandon abandon about"
)


def test_derive_eth_address_matches_vector():
    # m/44'/60'/0'/0/0 for the canonical test mnemonic
    assert EthAdapter().derive_address(MNEMONIC) == (
        "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
    )


def test_eip55_checksum():
    raw = bytes.fromhex("5aaeb6053f3e94c9b9a09f33669435e7ef1beaed")
    assert to_checksum_address(raw) == "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"


VAULT = "0x85034887f6656d610c38ef1710208495791fb146"
BTC_MEMO = "=:BTC.BTC:bc1qexampledest:123"


def _build(nonce=0):
    return EthAdapter().build_unsigned_swap(
        mnemonic=MNEMONIC,
        vault_address=VAULT,
        amount=100000,  # 1e8 units -> 1e15 wei
        memo=BTC_MEMO,
        nonce=nonce,
        gas=60000,
        max_fee_per_gas=20_000_000_000,
        max_priority_fee_per_gas=1_000_000_000,
    )


def test_build_eth_swap_tx_fields():
    built = _build(nonce=3)
    assert built.value == 100000 * 10**10
    assert built.data == "0x" + BTC_MEMO.encode().hex()
    assert built.chain_id == 1
    assert built.to.lower() == VAULT
    assert built.tx["nonce"] == 3
    assert built.fee == 60000 * 20_000_000_000


def test_eth_sign_produces_typed_raw():
    raws = EthAdapter().sign(_build())
    assert len(raws) == 1
    assert raws[0].startswith("0x02")  # EIP-1559 typed transaction


def test_eth_sweep_amount_leaves_gas_reserve():
    from cryptoswap_wallet.chains.eth import eth_sweep_amount

    amount = eth_sweep_amount(10**18, gas=60000, max_fee_per_gas=20_000_000_000)
    expected = (10**18 - 60000 * 20_000_000_000) // 10**10
    assert amount == expected


def test_eth_sweep_amount_insufficient():
    import pytest

    from cryptoswap_wallet.chains.coins import InsufficientFunds
    from cryptoswap_wallet.chains.eth import eth_sweep_amount

    with pytest.raises(InsufficientFunds):
        eth_sweep_amount(1000, gas=60000, max_fee_per_gas=20_000_000_000)


def test_eth_build_and_verify_clean():
    from cryptoswap_wallet.swap import SwapRequest
    from cryptoswap_wallet.thorchain import Quote, SwapFees

    a = EthAdapter()
    dest = "bc1qexampledest"
    quote = Quote(
        inbound_address=VAULT,
        expected_amount_out=170000,
        memo=f"=:b:{dest}",
        fees=SwapFees("BTC.BTC", 1058, 0, 500, 1558, 20, 50),
        recommended_min_amount_in=1000,
        expiry=9_999_999_999,
        dust_threshold=1000,
        recommended_gas_rate=15,
        gas_rate_units="gwei",
        router=None,
        max_streaming_quantity=1,
        streaming_swap_blocks=1,
        total_swap_seconds=30,
        raw={},
    )
    request = SwapRequest(
        from_asset="ETH.ETH", to_asset="BTC.BTC", amount=100000, destination=dest
    )
    prepared = a.build_and_verify(
        quote=quote,
        request=request,
        now=0,
        mnemonic=MNEMONIC,
        nonce=0,
        gas=60000,
        max_fee_per_gas=20_000_000_000,
        max_priority_fee_per_gas=1_000_000_000,
        max_fee_wei=10**17,
    )
    assert prepared.problems == []


def _eth_token_quote(memo, *, expiry=9_999_999_999):
    from cryptoswap_wallet.thorchain import Quote, SwapFees

    return Quote(
        inbound_address="0xe3536ba9559966c357f551ceccccf38b533aa171",
        expected_amount_out=24556,
        memo=memo,
        fees=SwapFees("BTC.BTC", 1058, 0, 500, 1558, 20, 50),
        recommended_min_amount_in=1,
        expiry=expiry,
        dust_threshold=0,
        recommended_gas_rate=15,
        gas_rate_units="gwei",
        router="0xD37BbE5744D730a1d98d8DC97c42F0Ca46aD7146",
        max_streaming_quantity=1,
        streaming_swap_blocks=1,
        total_swap_seconds=30,
        raw={},
    )


USDT_ASSET = "ETH.USDT-0xdAC17F958D2ee523a2206206994597C13D831ec7"


def _build_usdt(dest="bc1qexampledest", amount=500_000_000):
    from cryptoswap_wallet.swap import SwapRequest

    request = SwapRequest(
        from_asset=USDT_ASSET, to_asset="BTC.BTC", amount=amount, destination=dest
    )
    return EthAdapter().build_token_swap(
        mnemonic=MNEMONIC,
        request=request,
        quote=_eth_token_quote(f"=:b:{dest}"),
        nonce=7,
        max_fee_per_gas=20_000_000_000,
        max_priority_fee_per_gas=1_000_000_000,
        decimals=6,
    )


def test_eth_token_build_amounts_and_nonces():
    built = _build_usdt()
    assert built.native_amount == 5_000_000  # 5e8 thorchain units -> 5 USDT (6 dec)
    assert built.approve_tx["nonce"] == 7
    assert built.deposit_tx["nonce"] == 8
    assert built.approve_tx["to"].lower().endswith("831ec7")  # token contract
    assert built.deposit_tx["to"].lower().endswith("ad7146")  # router
    assert len(built.txs) == 2


def test_eth_token_verify_clean():
    from cryptoswap_wallet.chains.eth import verify_eth_token_swap

    built = _build_usdt()
    problems = verify_eth_token_swap(
        built=built, destination="bc1qexampledest", now=0, max_fee_wei=10**18
    )
    assert problems == []


def test_eth_token_verify_rejects_wrong_destination():
    from cryptoswap_wallet.chains.eth import verify_eth_token_swap

    built = _build_usdt()
    problems = verify_eth_token_swap(
        built=built, destination="bc1qsomeoneelse", now=0, max_fee_wei=10**18
    )
    assert any("destination" in p.lower() for p in problems)


def test_eth_token_sign_produces_two_raws():
    raws = EthAdapter().sign(_build_usdt())
    assert len(raws) == 2
    assert all(r.startswith("0x02") for r in raws)


def test_eth_token_build_from_uppercase_0x_asset():
    # ASSET uses THORChain's uppercase "0X..." contract form — must not crash (T0).
    from cryptoswap_wallet.swap import SwapRequest

    asset = "ETH.USDT-0XDAC17F958D2EE523A2206206994597C13D831EC7"
    req = SwapRequest(
        from_asset=asset, to_asset="BTC.BTC", amount=500_000_000, destination="bc1qx"
    )
    built = EthAdapter().build_token_swap(
        mnemonic=MNEMONIC,
        request=req,
        quote=_eth_token_quote("=:b:bc1qx"),
        nonce=1,
        max_fee_per_gas=20_000_000_000,
        max_priority_fee_per_gas=1_000_000_000,
        decimals=6,
    )
    assert built.token.lower().endswith("831ec7")


def test_eth_token_verify_rejects_wrong_amount():
    from cryptoswap_wallet.chains.eth import encode_deposit, verify_eth_token_swap

    built = _build_usdt()
    built.deposit_tx["data"] = encode_deposit(
        built.vault, built.token, built.native_amount + 1, built.memo, built.expiry
    )
    problems = verify_eth_token_swap(
        built=built, destination="bc1qexampledest", now=0, max_fee_wei=10**18
    )
    assert any("amount" in p.lower() for p in problems)


def test_eth_token_verify_rejects_swapped_vault_token():
    from cryptoswap_wallet.chains.eth import encode_deposit, verify_eth_token_swap

    built = _build_usdt()
    # vault and token slots swapped — substring checks would have missed this.
    built.deposit_tx["data"] = encode_deposit(
        built.token, built.vault, built.native_amount, built.memo, built.expiry
    )
    problems = verify_eth_token_swap(
        built=built, destination="bc1qexampledest", now=0, max_fee_wei=10**18
    )
    assert problems
