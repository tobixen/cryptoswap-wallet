# TODO

## Next up (priority order)

Owner's requested order; two-sided liquidity comes *after* these.

1. ~~**`send` to an external address.**~~ **DONE for BTC, ETH, USDT-ETH, TRX,
   USDT-TRON** (USDC-ETH shares the ERC-20 path). Plain on-chain transfer (no
   swap, no memo) via `cryptoswap-wallet send <addr> --asset <A> --amount
   <n|max>`, each with a dedicated memo-less verify gate (`verify_{btc,eth,
   eth_token,tron,tron_token}_send`) that binds recipient + amount and rejects
   any memo/router/extra calldata. ERC-20/TRC-20 sends are a routerless,
   approveless `transfer(recipient, amount)`. `max` is exact for tokens, leaves a
   gas reserve for ETH, and is refused for native TRX (can't be exact). Broadcast
   remains unproven on mainnet — see the testnet test work below.

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

Done: opt-in full-loop **`send`** broadcast tests on **BTC testnet3** and **ETH
Sepolia** (`tests/test_integration_testnet.py`), gated on funded testnet accounts
via env / CI secrets (skip otherwise), mirroring the Nile TRC-20 loop. The BTC
and ETH adapters are now network-parameterized (`BtcAdapter(network=...)`,
`EthAdapter(chain_id=...)`) so mainnet stays the default. This proves the account
+ UTXO spending path end to end for the first time.

Still to do:
- **Sepolia token send** (USDT/USDC on Sepolia) — the token-swap gate still bakes
  in mainnet `CHAIN_ID`; parameterize it (fold into A2/A3) to testnet-cover the
  ERC-20 send/swap path too.
- **THORChain stagenet swaps** — a real cross-chain swap loop (deposit on one
  testnet, receive on another) needs a stagenet vault + memo, a bigger lift.
- Wire the testnet secrets into the CI **Integration (network)** workflow so the
  broadcast loops run there, not just locally.

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

Done (continued): **M3** — `BtcAdapter.sign` now refuses a half-signed tx
(asserts every input carries a signature and `tx.verify()` passes) instead of
relying on broadcast rejection. **L2** — `_amount` rejects `<= 0` (and nan/inf)
at parse time, so no handler re-checks and a typo fails fast at the CLI.

Still open:

- **A2/A3** — share the EVM key derivation + `to_checksum`/keccak helpers between
  ETH and TRON; default `wallet_balance` on an account-model base.
- **A5** — table-drive the CLI per-chain factories / `_resolve_destination` /
  `cmd_address` / `_swap_from_*`.
- **A7** — split `base.ChainAdapter` into `WalletChain` vs `SourceChain` (Tron is
  destination-only). The `swap.SwapSource` protocol already exists from A4.
- **C-list** — one `ThreadPoolExecutor` per scan; `quote` memo row alignment;
  note ETH/TRON balance only inspects index 0.
  Done: keystore envelope `length` is now honoured on load (was written but
  ignored — `load` hardcoded `KEY_LEN`); `--tolerance-bps` flag (wired through
  every swap path, `cli.py`).

## Swap backends

Done: Maya backend (THORChain fork, same API/memo) + `--backend auto`
lowest-price routing across backends.

- **Maya-only assets**: expose DASH, ZEC, ADA (Cardano), ARB (Arbitrum) — Maya
  has pools THORChain lacks; just needs `ASSET` entries + dest derivation.
- **USDC on cheaper chains**: ETH.USDC is done (mirrors USDT-ETH). THORChain also
  pools USDC on AVAX/BASE and Maya on ARB — all far cheaper to use than ETH
  mainnet. Each needs a new EVM chain adapter (RPC, chain-id, native coin, dest
  validation), so this is the moment to do A2/A3 (generalize `EthAdapter` into a
  shared EVM code path) rather than copy it per chain.
- **BSC (BNB Smart Chain)** — Hold + Balance **DONE** (`chains/bsc.py`, a thin
  EVM subclass of `EthAdapter`: native BNB + BEP-20 USDC/USDT at 18 decimals,
  wired into `cmd_address`/`balance` with `--bsc-rpc`/`$CRYPTOSWAP_WALLET_BSC_RPC`).
  Swaps are still **blocked, do not implement yet**: THORChain has BSC
  `chain_trading_paused`/`halted` (a live `BTC->BSC.BNB` quote returns "trading is
  halted, can't process swap") and Maya has no BSC pools, so To/From/Sweep/Liq are
  unusable and untestable. `BscAdapter.build_and_verify` raises by design (the
  inherited builders bake in ETH's chain id 1, wrong for BSC's 56). Revisit when
  `inbound_addresses` shows BSC `chain_trading_paused: false`; a swap source will
  also need the EVM chain id parameterized (currently the module-level
  `CHAIN_ID` in `eth.py`) — fold into the A2/A3 EVM generalization.
- **`send` to external address**: see *Next up* item 1 (BTC first).
- **BasicSwap backend** (trustless P2P / privacy / XMR): orchestrate its daemon
  via API; needs full nodes (heavy) and a different custody seam. Future.
- **Monero (XMR) hold/balance/send**: blocked on a custody/architecture
  decision — see `docs/monero.md` for the analysis and the open choices.
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
- ~~**USDT-TRON as a source**~~ **DONE.** TRX (native) and the TRC-20 token
  source both land: a `TriggerSmartContract` `transfer(vault, amount)` with the
  swap memo in the tx data (no router on TRON), gated by `verify_tron_token_swap`
  which decodes the transfer calldata and binds recipient/amount/memo. See
  `tron.py` (`build_unsigned_trc20_transfer`, `_build_and_verify_token`).
- ~~**Token balances in `balance`**~~ **DONE.** `balance` now reports USDT
  (TRC-20/ERC-20) holdings alongside native BTC/ETH/TRX, via each adapter's
  `token_balances` and `cli._report_token_balances`.
- **Cache LP provider addresses (balance-report speed-up)**: reporting added
  liquidity queries the backend's `pool/{POOL}/liquidity_provider/{ADDRESS}`
  endpoint. ETH/TRON have a single derived address; BTC's LP is keyed by the
  deposit tx's VIN0, which isn't predictable, so the report has to query every
  *used* address the account scan already enumerates (× each backend). To skip
  those per-address LP calls, cache the provider address learned when *we* build
  an `add-liquidity` tx — read VIN0 back from the final built/signed tx (don't
  predict it from coin-selection order: bitcoinlib may BIP-69-reorder inputs).
  Deferred because it's only a BTC concern and a cache must **extend** coverage,
  never shrink it: a lost/stale cache (seed restored elsewhere, LP added by
  another tool) would silently under-report funds — the worst failure for a
  wallet. So treat it as a hint unioned with the full scan, or as an opt-in fast
  path with the scan as the default source of truth. (See the chat that prompted
  this.)
- **USDT-ETH source niceties**: `--amount max` (needs token balance), real
  `eth_estimateGas` instead of fixed approve/deposit gas, and the USDT
  "reset allowance to 0 before re-approving" edge case for repeat swaps.
- **Phase 2 — semi-automatic convert**: human-in-the-loop "convert everything
  above dust since last run" command (accumulate small inbounds, stream large
  swaps, idempotent on processed txids).
