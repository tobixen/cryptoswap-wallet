"""Ethereum chain adapter (native ETH) for THORChain swaps.

Derivation and signing use eth-account; chain state and broadcast use JSON-RPC.
A native ETH deposit goes directly to the inbound vault with the THORChain memo
hex-encoded in the transaction's calldata (the router is only needed for tokens).

build_unsigned_swap is pure given nonce/gas/fees (so it is unit-testable); the
caller fetches those over RPC. Amounts are THORChain 1e8 base units, converted
to wei via WEI_PER_THORCHAIN_UNIT.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from Crypto.Hash import keccak
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.signers.local import LocalAccount

from cryptoswap_wallet.chains.base import BalanceReport
from cryptoswap_wallet.chains.coins import InsufficientFunds
from cryptoswap_wallet.net import HttpClient
from cryptoswap_wallet.swap import Prepared, SwapRequest
from cryptoswap_wallet.thorchain import Quote
from cryptoswap_wallet.verify import (
    WEI_PER_THORCHAIN_UNIT,
    EthSwapPlan,
    verify_eth_swap,
)

DEFAULT_ETH_DERIVATION = "m/44'/60'/0'/0/0"
DEFAULT_RPC = "https://ethereum-rpc.publicnode.com"
CHAIN_ID = 1
DEFAULT_GAS = 60000

# ERC-20 token source: approve(router, amount) then router.depositWithExpiry(...).
APPROVE_SELECTOR = "095ea7b3"  # approve(address,uint256)
DEPOSIT_SELECTOR = (
    "44bc937b"  # depositWithExpiry(address,address,uint256,string,uint256)
)
DECIMALS_SELECTOR = "313ce567"  # decimals()
APPROVE_GAS = 70000
TOKEN_DEPOSIT_GAS = 200000

Account.enable_unaudited_hdwallet_features()


def encode_approve(router: str, amount: int) -> str:
    return (
        "0x"
        + APPROVE_SELECTOR
        + abi_encode(["address", "uint256"], [router, amount]).hex()
    )


def encode_deposit(vault: str, token: str, amount: int, memo: str, expiry: int) -> str:
    args = abi_encode(
        ["address", "address", "uint256", "string", "uint256"],
        [vault, token, amount, memo, expiry],
    )
    return "0x" + DEPOSIT_SELECTOR + args.hex()


def _keccak256(data: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def eth_sweep_amount(balance_wei: int, gas: int, max_fee_per_gas: int) -> int:
    """THORChain 1e8 amount sweeping the balance minus the worst-case gas reserve.

    Reserves ``gas * max_fee_per_gas`` so the deposit always leaves enough wei to
    pay the L1 fee; any sub-1e10-wei remainder is left behind.
    """
    sendable = balance_wei - gas * max_fee_per_gas
    if sendable <= 0:
        raise InsufficientFunds(
            f"balance {balance_wei} wei too small to cover gas reserve "
            f"{gas * max_fee_per_gas}"
        )
    return sendable // WEI_PER_THORCHAIN_UNIT


def to_checksum_address(addr: bytes | str) -> str:
    """EIP-55 checksum encoding of a 20-byte address (bytes or hex string)."""
    if isinstance(addr, str):
        addr = bytes.fromhex(addr.removeprefix("0x"))
    lower = addr.hex()
    digest = _keccak256(lower.encode()).hex()
    encoded = "".join(
        c.upper() if c.isalpha() and int(d, 16) >= 8 else c
        for c, d in zip(lower, digest, strict=False)
    )
    return "0x" + encoded


@dataclasses.dataclass
class EthBuiltSwap:
    tx: dict[str, Any]
    private_key: Any
    to: str
    value: int
    data: str
    chain_id: int
    gas: int
    max_fee_per_gas: int

    @property
    def fee(self) -> int:
        return self.gas * self.max_fee_per_gas

    @property
    def txs(self) -> list[dict[str, Any]]:
        return [self.tx]


@dataclasses.dataclass
class EthTokenBuiltSwap:
    """An ERC-20 token swap: approve(router) then router.depositWithExpiry(...)."""

    approve_tx: dict[str, Any]
    deposit_tx: dict[str, Any]
    private_key: Any
    token: str
    router: str
    vault: str
    native_amount: int
    memo: str
    expiry: int

    @property
    def txs(self) -> list[dict[str, Any]]:
        return [self.approve_tx, self.deposit_tx]

    @property
    def fee(self) -> int:
        return sum(t["gas"] * t["maxFeePerGas"] for t in self.txs)


def verify_eth_token_swap(
    *, built: EthTokenBuiltSwap, destination: str, now: int, max_fee_wei: int
) -> list[str]:
    """Gate for an ERC-20 token deposit (approve + router.depositWithExpiry)."""
    problems: list[str] = []
    approve, deposit = built.approve_tx, built.deposit_tx

    if now >= built.expiry:
        problems.append(f"quote expired (now {now} >= expiry {built.expiry})")
    if approve["to"].lower() != built.token.lower():
        problems.append(f"approve 'to' {approve['to']} != token {built.token}")
    if deposit["to"].lower() != built.router.lower():
        problems.append(f"deposit 'to' {deposit['to']} != router {built.router}")
    if approve["value"] != 0 or deposit["value"] != 0:
        problems.append("token txs must not send ETH value")
    if approve["chainId"] != CHAIN_ID or deposit["chainId"] != CHAIN_ID:
        problems.append("wrong chainId")
    # The deposit calldata must carry our vault, token and memo.
    data = deposit["data"].lower()
    if built.vault[2:].lower() not in data:
        problems.append("deposit calldata does not contain the vault")
    if built.token[2:].lower() not in data:
        problems.append("deposit calldata does not contain the token")
    if built.memo.encode().hex() not in data:
        problems.append("deposit calldata does not contain the memo")
    if destination and destination.lower() not in built.memo.lower():
        problems.append(f"memo {built.memo!r} does not pay destination {destination}")
    if built.fee > max_fee_wei:
        problems.append(f"max fee {built.fee} wei exceeds limit {max_fee_wei}")
    return problems


class EthAdapter(HttpClient):
    """ChainAdapter for native Ethereum."""

    chain = "ETH"
    asset = "ETH.ETH"

    def __init__(self, rpc_url: str = DEFAULT_RPC, timeout: float = 20.0) -> None:
        super().__init__(timeout)
        self.rpc_url = rpc_url

    def _key(self, mnemonic: str, path: str) -> LocalAccount:
        return Account.from_mnemonic(mnemonic, account_path=path)

    def derive_address(self, mnemonic: str, path: str = DEFAULT_ETH_DERIVATION) -> str:
        return self._key(mnemonic, path).address

    # --- JSON-RPC ---

    def _rpc(self, method: str, params: list[object]) -> object:
        resp = self._post(
            self.rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error"):
            raise RuntimeError(f"RPC {method}: {payload['error']}")
        return payload["result"]

    def get_nonce(self, address: str) -> int:
        return int(self._rpc("eth_getTransactionCount", [address, "pending"]), 16)

    def fetch_balance(self, address: str) -> int:
        return int(self._rpc("eth_getBalance", [address, "latest"]), 16)

    def fetch_token_decimals(self, token: str) -> int:
        result = self._rpc(
            "eth_call", [{"to": token, "data": "0x" + DECIMALS_SELECTOR}, "latest"]
        )
        return int(result, 16)

    def wallet_balance(self, mnemonic: str) -> BalanceReport:
        address = self.derive_address(mnemonic)
        return BalanceReport(
            symbol="ETH",
            confirmed=self.fetch_balance(address),
            decimals=18,
            note=f"({address})",
        )

    def fetch_fees(self) -> tuple[int, int]:
        """Return ``(max_fee_per_gas, max_priority_fee_per_gas)`` in wei."""
        tip = int(self._rpc("eth_maxPriorityFeePerGas", []), 16)
        block = self._rpc("eth_getBlockByNumber", ["latest", False])
        base = int(block["baseFeePerGas"], 16)
        return base * 2 + tip, tip

    def broadcast(self, raws: list[str]) -> str:
        txid = ""
        for raw in raws:
            txid = self._rpc("eth_sendRawTransaction", [raw])
        return str(txid)

    def build_unsigned_swap(
        self,
        *,
        mnemonic: str,
        vault_address: str,
        amount: int,
        memo: str,
        nonce: int,
        gas: int,
        max_fee_per_gas: int,
        max_priority_fee_per_gas: int,
        path: str = DEFAULT_ETH_DERIVATION,
    ) -> EthBuiltSwap:
        account = self._key(mnemonic, path)
        to = to_checksum_address(vault_address)
        value = amount * WEI_PER_THORCHAIN_UNIT
        data = "0x" + memo.encode().hex()
        tx = {
            "type": 2,
            "chainId": CHAIN_ID,
            "nonce": nonce,
            "to": to,
            "value": value,
            "gas": gas,
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
            "data": data,
        }
        return EthBuiltSwap(
            tx=tx,
            private_key=account.key,
            to=to,
            value=value,
            data=data,
            chain_id=CHAIN_ID,
            gas=gas,
            max_fee_per_gas=max_fee_per_gas,
        )

    def _sign_tx(self, tx: dict[str, Any], private_key: object) -> str:
        signed = Account.sign_transaction(tx, private_key)
        raw = getattr(signed, "raw_transaction", None)
        if raw is None:
            raw = signed.rawTransaction
        return "0x" + raw.hex()

    def sign(self, built: EthBuiltSwap | EthTokenBuiltSwap) -> list[str]:
        return [self._sign_tx(tx, built.private_key) for tx in built.txs]

    def build_token_swap(
        self,
        *,
        mnemonic: str,
        request: SwapRequest,
        quote: Quote,
        nonce: int,
        max_fee_per_gas: int,
        max_priority_fee_per_gas: int,
        decimals: int,
    ) -> EthTokenBuiltSwap:
        account = self._key(mnemonic, DEFAULT_ETH_DERIVATION)
        token = to_checksum_address(request.from_asset.split("-", 1)[1])
        router = to_checksum_address(quote.router or "")
        vault = to_checksum_address(quote.inbound_address)
        memo = quote.memo or ""
        # THORChain 1e8 units -> the token's native decimals.
        native = request.amount * 10**decimals // 10**8
        common = {
            "type": 2,
            "chainId": CHAIN_ID,
            "value": 0,
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": max_priority_fee_per_gas,
        }
        approve_tx = {
            **common,
            "nonce": nonce,
            "to": token,
            "gas": APPROVE_GAS,
            "data": encode_approve(router, native),
        }
        deposit_tx = {
            **common,
            "nonce": nonce + 1,
            "to": router,
            "gas": TOKEN_DEPOSIT_GAS,
            "data": encode_deposit(vault, token, native, memo, quote.expiry),
        }
        return EthTokenBuiltSwap(
            approve_tx=approve_tx,
            deposit_tx=deposit_tx,
            private_key=account.key,
            token=token,
            router=router,
            vault=vault,
            native_amount=native,
            memo=memo,
            expiry=quote.expiry,
        )

    def build_and_verify(
        self,
        *,
        quote: Quote,
        request: SwapRequest,
        now: int,
        mnemonic: str,
        nonce: int,
        gas: int,
        max_fee_per_gas: int,
        max_priority_fee_per_gas: int,
        max_fee_wei: int,
    ) -> Prepared:
        if "-" in request.from_asset:  # ERC-20 token source
            built_token = self.build_token_swap(
                mnemonic=mnemonic,
                request=request,
                quote=quote,
                nonce=nonce,
                max_fee_per_gas=max_fee_per_gas,
                max_priority_fee_per_gas=max_priority_fee_per_gas,
                decimals=self.fetch_token_decimals(request.from_asset.split("-", 1)[1]),
            )
            problems = verify_eth_token_swap(
                built=built_token,
                destination=request.destination,
                now=now,
                max_fee_wei=max_fee_wei,
            )
            return Prepared(
                quote=quote, built=built_token, plan=built_token, problems=problems
            )

        built = self.build_unsigned_swap(
            mnemonic=mnemonic,
            vault_address=quote.inbound_address,
            amount=request.amount,
            memo=quote.memo or "",
            nonce=nonce,
            gas=gas,
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
        )
        plan = EthSwapPlan(
            inbound_address=quote.inbound_address,
            amount_wei=request.amount * WEI_PER_THORCHAIN_UNIT,
            memo=quote.memo or "",
            expiry=quote.expiry,
            destination=request.destination,
        )
        problems = verify_eth_swap(
            to=built.to,
            value=built.value,
            data=built.data,
            chain_id=built.chain_id,
            gas=built.gas,
            max_fee_per_gas=built.max_fee_per_gas,
            plan=plan,
            now=now,
            max_fee_wei=max_fee_wei,
        )
        return Prepared(quote=quote, built=built, plan=plan, problems=problems)

    def build_and_verify_deposit(
        self,
        *,
        vault: str,
        memo: str,
        amount: int,
        now: int,
        mnemonic: str,
        nonce: int,
        gas: int,
        max_fee_per_gas: int,
        max_priority_fee_per_gas: int,
        max_fee_wei: int,
    ) -> Prepared:
        built = self.build_unsigned_swap(
            mnemonic=mnemonic,
            vault_address=vault,
            amount=amount,
            memo=memo,
            nonce=nonce,
            gas=gas,
            max_fee_per_gas=max_fee_per_gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
        )
        plan = EthSwapPlan(
            inbound_address=vault,
            amount_wei=amount * WEI_PER_THORCHAIN_UNIT,
            memo=memo,
            expiry=now + 3600,
        )
        problems = verify_eth_swap(
            to=built.to,
            value=built.value,
            data=built.data,
            chain_id=built.chain_id,
            gas=built.gas,
            max_fee_per_gas=built.max_fee_per_gas,
            plan=plan,
            now=now,
            max_fee_wei=max_fee_wei,
        )
        return Prepared(quote=None, built=built, plan=plan, problems=problems)
