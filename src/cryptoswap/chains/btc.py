"""Bitcoin chain adapter, backed by bitcoinlib for HD keys, signing and OP_RETURN.

Building a swap is deliberately split from signing: ``build_unsigned_swap``
returns the tx together with neutral outputs for the :mod:`cryptoswap.verify`
gate, and only after that gate passes should the caller ``sign`` and
``broadcast``. UTXO sync and broadcast use a public Esplora API (no node).

Current limitation: signing assumes all selected UTXOs belong to a single
derived key (``path``); per-input paths are a later addition.
"""

from __future__ import annotations

import dataclasses

import httpx
from bitcoinlib.keys import HDKey
from bitcoinlib.mnemonic import Mnemonic
from bitcoinlib.transactions import Transaction

from cryptoswap.chains.coins import (
    Utxo,
    decode_op_return,
    encode_op_return,
    select_coins,
)
from cryptoswap.verify import TxOutput

DEFAULT_ESPLORA = "https://blockstream.info/api"
DEFAULT_DERIVATION = "m/84'/0'/0'/0/0"


@dataclasses.dataclass
class BuiltSwap:
    tx: Transaction
    outputs: list[TxOutput]
    fee: int
    change_address: str


def _extract_outputs(tx: Transaction) -> list[TxOutput]:
    outputs: list[TxOutput] = []
    for o in tx.outputs:
        if o.script_type == "nulldata":
            outputs.append(
                TxOutput(
                    address=None,
                    value=o.value,
                    op_return_data=decode_op_return(bytes(o.lock_script)),
                )
            )
        else:
            outputs.append(TxOutput(address=o.address, value=o.value))
    return outputs


class BtcAdapter:
    """ChainAdapter for Bitcoin (native segwit / P2WPKH)."""

    chain = "BTC"
    asset = "BTC.BTC"

    def __init__(
        self, esplora_url: str = DEFAULT_ESPLORA, timeout: float = 20.0
    ) -> None:
        self.esplora_url = esplora_url.rstrip("/")
        self._timeout = timeout

    def _hdkey(self, mnemonic: str, path: str) -> HDKey:
        seed = Mnemonic().to_seed(mnemonic)
        return HDKey.from_seed(seed, network="bitcoin").subkey_for_path(path)

    def derive_address(self, mnemonic: str, path: str = DEFAULT_DERIVATION) -> str:
        return self._hdkey(mnemonic, path).address(
            script_type="p2wpkh", encoding="bech32"
        )

    def build_unsigned_swap(
        self,
        *,
        mnemonic: str,
        path: str,
        utxos: list[Utxo],
        vault_address: str,
        amount: int,
        memo: str,
        fee_rate: float,
        change_address: str | None = None,
    ) -> BuiltSwap:
        key = self._hdkey(mnemonic, path)
        own = key.address(script_type="p2wpkh", encoding="bech32")
        change_address = change_address or own
        memo_bytes = memo.encode()
        sel = select_coins(utxos, amount, fee_rate, len(memo_bytes))

        tx = Transaction(network="bitcoin", witness_type="segwit")
        for utxo in sel.utxos:
            tx.add_input(
                prev_txid=utxo.txid,
                output_n=utxo.vout,
                value=utxo.value,
                keys=key,
                witness_type="segwit",
            )
        tx.add_output(amount, address=vault_address)
        tx.add_output(0, lock_script=encode_op_return(memo_bytes))
        if sel.change > 0:
            tx.add_output(sel.change, address=change_address)

        return BuiltSwap(
            tx=tx,
            outputs=_extract_outputs(tx),
            fee=sel.fee,
            change_address=change_address,
        )

    def sign(
        self, built: BuiltSwap, *, mnemonic: str, path: str = DEFAULT_DERIVATION
    ) -> str:
        built.tx.sign(self._hdkey(mnemonic, path))
        return built.tx.raw_hex()

    # --- network via Esplora; covered by manual/integration testing, not units ---

    def fetch_utxos(self, address: str) -> list[Utxo]:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self.esplora_url}/address/{address}/utxo")
            resp.raise_for_status()
            return [
                Utxo(txid=x["txid"], vout=x["vout"], value=x["value"], address=address)
                for x in resp.json()
                if x.get("status", {}).get("confirmed", True)
            ]

    def fetch_balance(self, address: str) -> int:
        return sum(u.value for u in self.fetch_utxos(address))

    def fetch_fee_rate(self, target_blocks: int = 6) -> float:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.get(f"{self.esplora_url}/fee-estimates")
            resp.raise_for_status()
            estimates = resp.json()
            return float(estimates.get(str(target_blocks)) or min(estimates.values()))

    def broadcast(self, raw_hex: str) -> str:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(f"{self.esplora_url}/tx", content=raw_hex)
            resp.raise_for_status()
            return resp.text.strip()
