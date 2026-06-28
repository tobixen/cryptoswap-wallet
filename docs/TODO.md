# TODO

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
- **`send` to external address**: still pending (plain transfer, no swap memo).
- **BasicSwap backend** (trustless P2P / privacy / XMR): orchestrate its daemon
  via API; needs full nodes (heavy) and a different custody seam. Future.
- **`--backend auto` for liquidity**: LP currently THORChain-only.

## Other known gaps

- **Live integration is unproven** for the spending path (real Esplora UTXO
  scan + broadcast); only `quote` and the empty-wallet scan have run live.
- **BIP49/44 scanning**: real wiring scans BIP84 only (Trust Wallet's scheme).
  `scan_account` is generic enough to add `m/49'`/`m/44'` accounts + script
  types when needed.
- **ETH gas estimation**: ETH source uses a fixed `--eth-gas` (default 60000);
  could call `eth_estimateGas` against the quote's vault/memo instead.
- **TRX + USDT-TRON as sources**: native TRON signing via tronpy (TRX = transfer
  to vault + memo in tx data; USDT-TRON = TRC-20 transfer to vault + memo, no
  router on TRON). Needs a TronGrid API key — tronpy can't even build a tx
  without a node, and the keyless endpoint 429s. ETH and USDT-ETH sources done.
- **Token balances in `balance`**: show USDT (TRC-20/ERC-20) holdings, not just
  native BTC/ETH/TRX.
- **USDT-ETH source niceties**: `--amount max` (needs token balance), real
  `eth_estimateGas` instead of fixed approve/deposit gas, and the USDT
  "reset allowance to 0 before re-approving" edge case for repeat swaps.
- **Phase 2 — semi-automatic convert**: human-in-the-loop "convert everything
  above dust since last run" command (accumulate small inbounds, stream large
  swaps, idempotent on processed txids).
