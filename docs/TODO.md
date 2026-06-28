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

## Other known gaps

- **Live integration is unproven** for the spending path (real Esplora UTXO
  scan + broadcast); only `quote` and the empty-wallet scan have run live.
- **BIP49/44 scanning**: real wiring scans BIP84 only (Trust Wallet's scheme).
  `scan_account` is generic enough to add `m/49'`/`m/44'` accounts + script
  types when needed.
- **ETH `--amount max`**: sweep the ETH balance minus the gas reserve
  (balance − gas·maxFeePerGas). Numeric amounts only for ETH source today.
- **ETH gas estimation**: ETH source uses a fixed `--eth-gas` (default 60000);
  could call `eth_estimateGas` against the quote's vault/memo instead.
- **TRON as a swap source**: native TRX source adapter (tronpy) behind
  `ChainAdapter`. ETH source is done (native ETH only).
- **Token (USDT/USDC) swaps**: THORChain has `ETH.USDT`, `TRON.USDT`,
  `ETH.USDC`, etc. As a *destination* (e.g. BTC→TRON.USDT) it's mostly an
  asset-map + destination-address addition. As a *source* it needs the ERC-20 /
  TRC-20 `approve` + `router.depositWithExpiry` path.
- **Phase 2 — semi-automatic convert**: human-in-the-loop "convert everything
  above dust since last run" command (accumulate small inbounds, stream large
  swaps, idempotent on processed txids).
