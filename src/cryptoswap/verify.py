"""The pre-broadcast safety gate for Bitcoin -> * swaps.

Given the outputs of an *unsigned* transaction and the swap we intend it to
perform, return a list of human-readable problems. An empty list means the
transaction matches the intended swap exactly and is safe to sign and
broadcast; a non-empty list MUST block broadcasting. On THORChain a wrong
vault, amount or memo means irreversible loss of funds, so this gate is
deliberately strict and dependency-free (easy to read and test).
"""

from __future__ import annotations

import dataclasses

OP_RETURN_MAX_BYTES = 80


@dataclasses.dataclass(frozen=True)
class TxOutput:
    """One output of a Bitcoin transaction.

    ``address`` is ``None`` for an OP_RETURN (data) output, in which case
    ``op_return_data`` holds the raw bytes.
    """

    address: str | None
    value: int
    op_return_data: bytes | None = None


@dataclasses.dataclass(frozen=True)
class SwapPlan:
    """What we intend the transaction to do, derived from a THORChain quote."""

    inbound_address: str
    amount: int
    memo: str
    expiry: int


def verify_btc_swap(
    outputs: list[TxOutput],
    fee: int,
    plan: SwapPlan,
    owned_addresses: set[str],
    now: int,
    *,
    max_fee: int,
) -> list[str]:
    """Return reasons the tx does not match ``plan``; empty means safe.

    ``now`` and ``plan.expiry`` are unix timestamps. ``fee`` and ``max_fee`` are
    in satoshis.
    """
    problems: list[str] = []

    if now >= plan.expiry:
        problems.append(f"quote expired (now {now} >= expiry {plan.expiry})")

    # Exactly one output to the vault, for the exact amount.
    vault_outs = [o for o in outputs if o.address == plan.inbound_address]
    if len(vault_outs) != 1:
        problems.append(
            f"expected exactly one output to vault {plan.inbound_address}, "
            f"found {len(vault_outs)}"
        )
    elif vault_outs[0].value != plan.amount:
        problems.append(
            f"vault output amount {vault_outs[0].value} != intended {plan.amount}"
        )

    # Exactly one OP_RETURN, decoding to exactly the quoted memo.
    op_returns = [o for o in outputs if o.op_return_data is not None]
    if len(op_returns) != 1:
        problems.append(
            f"expected exactly one OP_RETURN output, found {len(op_returns)}"
        )
    else:
        data = op_returns[0].op_return_data
        assert data is not None  # narrowed by the op_return_data filter above
        if len(data) > OP_RETURN_MAX_BYTES:
            problems.append(
                f"memo is {len(data)} bytes, exceeds OP_RETURN limit of "
                f"{OP_RETURN_MAX_BYTES}"
            )
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            problems.append("OP_RETURN memo is not valid UTF-8")
        else:
            if decoded != plan.memo:
                problems.append(
                    f"OP_RETURN memo {decoded!r} != quoted memo {plan.memo!r}"
                )

    # Every non-vault, non-OP_RETURN output (i.e. change) must return to us.
    for o in outputs:
        if o.op_return_data is not None or o.address == plan.inbound_address:
            continue
        if o.address not in owned_addresses:
            problems.append(f"change output to non-owned address {o.address}")

    if fee < 0:
        problems.append(f"negative fee {fee}")
    elif fee > max_fee:
        problems.append(f"fee {fee} exceeds max_fee {max_fee}")

    return problems
