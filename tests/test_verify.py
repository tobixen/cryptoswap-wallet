"""Tests for the pre-broadcast swap verify gate.

These guard against the irreversible-loss failure modes of a THORChain BTC
swap: wrong vault, wrong amount, wrong/garbled memo, change leaking to a
non-owned address, an expired quote, or an absurd fee.
"""

from cryptoswap.verify import SwapPlan, TxOutput, verify_btc_swap

VAULT = "bc1qct4mxayrdy96d4py20l4u02mu06r667f42p9fp"
CHANGE = "bc1qchange00000000000000000000000000000000"
MEMO = "=:ETH.ETH:0x1111111111111111111111111111111111111111:6700000"

PLAN = SwapPlan(inbound_address=VAULT, amount=178100, memo=MEMO, expiry=2000)
OWNED = {CHANGE}


def good_outputs():
    return [
        TxOutput(address=VAULT, value=178100),
        TxOutput(address=CHANGE, value=50000),
        TxOutput(address=None, value=0, op_return_data=MEMO.encode()),
    ]


def verify(outputs, fee=600, now=1000, max_fee=10000):
    return verify_btc_swap(
        outputs, fee=fee, plan=PLAN, owned_addresses=OWNED, now=now, max_fee=max_fee
    )


def test_valid_swap_has_no_problems():
    assert verify(good_outputs()) == []


def test_wrong_vault_amount():
    outs = good_outputs()
    outs[0] = TxOutput(address=VAULT, value=178099)
    assert any("amount" in p for p in verify(outs))


def test_wrong_vault_address():
    outs = good_outputs()
    outs[0] = TxOutput(address="bc1qwrongvault0000000000000000000", value=178100)
    assert any("vault" in p.lower() for p in verify(outs))


def test_memo_mismatch():
    outs = good_outputs()
    outs[2] = TxOutput(address=None, value=0, op_return_data=b"=:ETH.ETH:0xDEADBEEF")
    assert any("memo" in p.lower() for p in verify(outs))


def test_missing_op_return():
    assert any("op_return" in p.lower() for p in verify(good_outputs()[:2]))


def test_change_to_unowned_address():
    outs = good_outputs()
    outs[1] = TxOutput(address="bc1qattacker00000000000000000000000000000", value=50000)
    assert any("owned" in p.lower() for p in verify(outs))


def test_expired_quote():
    assert any("expir" in p.lower() for p in verify(good_outputs(), now=99999))


def test_excessive_fee():
    assert any("fee" in p.lower() for p in verify(good_outputs(), fee=999999))


def test_memo_too_long_for_op_return():
    long_memo = "=:ETH.ETH:" + "x" * 90
    plan = SwapPlan(inbound_address=VAULT, amount=178100, memo=long_memo, expiry=2000)
    outs = [
        TxOutput(address=VAULT, value=178100),
        TxOutput(address=CHANGE, value=50000),
        TxOutput(address=None, value=0, op_return_data=long_memo.encode()),
    ]
    problems = verify_btc_swap(
        outs, fee=600, plan=plan, owned_addresses=OWNED, now=1000, max_fee=10000
    )
    assert any("80" in p for p in problems)
