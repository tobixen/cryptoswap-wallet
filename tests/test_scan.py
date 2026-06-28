"""Tests for gap-limit HD address scanning (pure, injected chain calls)."""

from cryptoswap.chains.coins import Utxo
from cryptoswap.chains.scan import scan_account

ACCOUNT = "m/84'/0'/0'"


def derive(path: str) -> str:
    return f"addr::{path}"


def test_scan_finds_funds_and_records_path():
    addr0 = derive(f"{ACCOUNT}/0/0")
    activity = {addr0: [Utxo(txid="aa" * 32, vout=0, value=5000, address=addr0)]}
    found = scan_account(
        derive_address=derive,
        has_history=lambda a: a in activity,
        fetch_utxos=lambda a: activity.get(a, []),
        account=ACCOUNT,
        gap_limit=3,
        branches=(0,),
    )
    assert len(found) == 1
    assert found[0].value == 5000
    assert found[0].path == f"{ACCOUNT}/0/0"


def test_scan_respects_gap_limit_when_empty():
    found = scan_account(
        derive_address=derive,
        has_history=lambda a: False,
        fetch_utxos=lambda a: [],
        account=ACCOUNT,
        gap_limit=2,
        branches=(0,),
    )
    assert found == []


def test_scan_continues_past_used_but_empty_address():
    a0 = derive(f"{ACCOUNT}/0/0")  # used, now empty
    a1 = derive(f"{ACCOUNT}/0/1")  # holds funds
    activity = {a0: [], a1: [Utxo(txid="bb" * 32, vout=0, value=7000, address=a1)]}
    found = scan_account(
        derive_address=derive,
        has_history=lambda a: a in activity,
        fetch_utxos=lambda a: activity.get(a, []),
        account=ACCOUNT,
        gap_limit=2,
        branches=(0,),
    )
    assert len(found) == 1
    assert found[0].value == 7000
    assert found[0].path == f"{ACCOUNT}/0/1"


def test_scan_covers_receive_and_change_branches():
    recv = derive(f"{ACCOUNT}/0/0")
    chng = derive(f"{ACCOUNT}/1/0")
    activity = {
        recv: [Utxo(txid="aa" * 32, vout=0, value=1000, address=recv)],
        chng: [Utxo(txid="cc" * 32, vout=0, value=2000, address=chng)],
    }
    found = scan_account(
        derive_address=derive,
        has_history=lambda a: a in activity,
        fetch_utxos=lambda a: activity.get(a, []),
        account=ACCOUNT,
        gap_limit=2,
        branches=(0, 1),
    )
    assert {u.value for u in found} == {1000, 2000}
