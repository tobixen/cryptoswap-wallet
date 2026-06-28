# TODO

## Next up (priority order)

Owner's requested order; two-sided liquidity comes *after* these.

1. ~~**`send` to an external address — BTC first.**~~ **DONE for BTC.** Plain
   on-chain transfer (no swap, no memo) via `cryptoswap-wallet send <addr>
   --amount <btc|max>`, reusing the BTC spending path with a dedicated
   `verify_btc_send` gate. ETH/TRX sends still to do (need account-model transfer
   builders; ETH is mostly a value-transfer of the existing signing path).

2. ~~**TRX liquidity.**~~ **DONE.** TRON source signing landed (native
   `TransferContract` + memo via tronpy, keyless public node), unblocking both
   TRX swaps-from and `add/withdraw-liquidity` on TRON. Pre-broadcast
   `verify_tron_swap` gate checks vault/amount/memo. Pool `TRON.TRX` is
   `Available`. Broadcast remains unproven against mainnet (no funds spent in
   testing) — same caveat as the BTC/ETH spending paths.

3. **More swap *destinations* via external `--dest` addresses.** **DONE for
   LTC, DOGE, BCH** — added as `ASSET` entries (destination-only) with a
   permissive per-chain `--dest` sanity check (`addresses.py`; prefix/charset/
   length, not checksum — THORChain validates the checksum). Live quote tests
   confirm the pools and that the memo pays the dest. Remaining candidates: ATOM,
   XRP, SOL (XRP needs care re: destination tag), plus the Maya-only
   DASH/ZEC/ADA/ARB under *Swap backends*. A full checksum validator (bech32/
   base58check/cashaddr) would be a stronger guard than the current sanity check.

4. **Two-sided (symmetric) liquidity — gated behind a RUNE/THORChain backend.**
   A symmetric add is two *linked* deposits: the asset leg (`+:POOL:<thor1addr>`
   to the inbound vault) and a RUNE leg (a Cosmos `MsgDeposit` carrying RUNE with
   memo `+:POOL:<assetaddr>`), paired by the protocol via the cross-referenced
   addresses within a time window. The wallet has none of the RUNE side today, so
   this requires:
   - `thor1…` address derivation (bech32, secp256k1, Cosmos HD path
     `m/44'/931'/0'/0/0`);
   - build + sign + broadcast a Cosmos SDK `MsgDeposit` (protobuf tx, account
     number/sequence from a THORNode, gas) — a new signing stack and dependency
     (e.g. `cosmpy`);
   - two-leg coordination + partial-failure handling (one leg lands, the other
     doesn't → lopsided/stuck position) — material risk on an experimental,
     loss-prone feature.

   The same backend also unlocks RUNE as a swap asset (to/from), so it is not
   wasted work. Note that one-sided LP already carries ~50% RUNE price exposure;
   symmetric mainly buys *no entry slip* in exchange for sourcing and holding
   RUNE. Sensible sub-phasing: (a) `thor1` derivation + RUNE balance (read-only,
   testable now); (b) `MsgDeposit` sign/broadcast; (c) symmetric add/withdraw.

## Integration tests towards testnet / stagenet

...

## Spend unconfirmed inbound via CPFP (`--allow-unconfirmed`)

Currently `fetch_utxos` is confirmed-only and the fee model is a flat
`fee_rate`, so a swap can't be funded from an inbound tx still in the mempool.

Add an opt-in `--allow-unconfirmed` that:

- includes unconfirmed UTXOs as spendable, and
- does proper **child-pays-for-parent** fee selection: detect the parent's fee
  deficit and overpay on the swap (child) tx so the parent+child *package*
  reaches the target feerate.

Notes / caveats (see the chat that prompted this):

- THORChain still only acts on **confirmed** deposits (value-scaled
  confirmation count), so CPFP speeds up reaching that point but does not skip
  it. Main benefit is when the inbound is fee-stuck.
- Only safe when we control the parent. An external RBF-signalling parent can
  be replaced, which invalidates our deposit tx (benign failure: the swap just
  never happens, no funds lost) — warn the user.
- Mind Bitcoin mempool ancestor/descendant limits.

## From core review 2 (docs/core-review-2.md)

Done: T0 (`to_checksum_address` handles `0X`/`0x`; real-ASSET token build test),
T1/T2 (ABI-decode the approve+deposit calldata positionally and bind amount /
vault / token / memo to intent, with selector checks), T3 (CLI warns about the
residual router allowance if a token deposit fails after approve), T5
(`KNOWN_TOKEN_DECIMALS` + `token_decimals()`), N4 (case-sensitive
`memo_pays_destination` with hex-only fallback), R1 (ruff clean). L-1
documented (LP vault is self-referential — see `prepare_liquidity` docstring).

Still open: N5 (BTC→token-destination memo vs 80-byte OP_RETURN limit — becomes
live once USDT destinations from BTC are exercised); carried-forward
A2/A3/A5/A7, M3, L2 below.

## From the core review (docs/core-review.md)

Done: A1 (shared niquests `HttpClient`), M2 (fee fallback → max), L1 (fail-closed
UTXOs), H1 (atomic keystore write), M1 (memo-pays-destination check), A4 (one
`prepare_swap`; adapters own `build_and_verify`; single `SwapSource` protocol).

Still open:

- **M3** — after BTC `sign`, assert every input is actually signed (don't rely on
  broadcast rejection).
- **L2** — reject `amount <= 0` at parse time.
- **A2/A3** — share the EVM key derivation + `to_checksum`/keccak helpers between
  ETH and TRON; default `wallet_balance` on an account-model base.
- **A5** — table-drive the CLI per-chain factories / `_resolve_destination` /
  `cmd_address` / `_swap_from_*`.
- **A7** — split `base.ChainAdapter` into `WalletChain` vs `SourceChain` (Tron is
  destination-only). The `swap.SwapSource` protocol already exists from A4.
- **C-list** — keystore envelope `length` unused; one `ThreadPoolExecutor` per
  scan; `quote` memo row alignment; note ETH/TRON balance only inspects index 0;
  `--tolerance-bps` flag.

## Swap backends

Done: Maya backend (THORChain fork, same API/memo) + `--backend auto`
lowest-price routing across backends.

- **Maya-only assets**: expose DASH, ZEC, ADA (Cardano), ARB (Arbitrum) — Maya
  has pools THORChain lacks; just needs `ASSET` entries + dest derivation.
- **`send` to external address**: see *Next up* item 1 (BTC first).
- **BasicSwap backend** (trustless P2P / privacy / XMR): orchestrate its daemon
  via API; needs full nodes (heavy) and a different custody seam. Future.
- **liquidity backend**: `add/withdraw-liquidity --backend {thorchain,maya}` now
  works (Maya pairs with CACAO, different pools, no TRON). No `auto` for LP —
  it's a network/pairing choice, not price-routed.

## Other known gaps

- **Live integration is unproven** for the spending path (real Esplora UTXO
  scan + broadcast); only `quote` and the empty-wallet scan have run live.
- **BIP49/44 scanning**: real wiring scans BIP84 only (Trust Wallet's scheme).
  `scan_account` is generic enough to add `m/49'`/`m/44'` accounts + script
  types when needed.
- **ETH gas estimation**: ETH source uses a fixed `--eth-gas` (default 60000);
  could call `eth_estimateGas` against the quote's vault/memo instead.
- **USDT-TRON as a source**: TRX (native) source is now done — signs a
  TransferContract with the memo in tx data via tronpy, against the keyless
  public node (`tron-rpc.publicnode.com`; the old "needs a TronGrid API key /
  429s" worry was TronGrid's free tier, not this node). USDT-TRON still pending:
  it's a TRC-20 `transfer` to the vault with the memo, no router on TRON — needs
  a TriggerSmartContract build + its own verify gate (decode the transfer
  calldata, bind recipient/amount, check the memo).
- **Token balances in `balance`**: show USDT (TRC-20/ERC-20) holdings, not just
  native BTC/ETH/TRX.
- **USDT-ETH source niceties**: `--amount max` (needs token balance), real
  `eth_estimateGas` instead of fixed approve/deposit gas, and the USDT
  "reset allowance to 0 before re-approving" edge case for repeat swaps.
- **Phase 2 — semi-automatic convert**: human-in-the-loop "convert everything
  above dust since last run" command (accumulate small inbounds, stream large
  swaps, idempotent on processed txids).
