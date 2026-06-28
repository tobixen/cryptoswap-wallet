# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is derived
automatically from git tags (PEP 440 / SemVer).

## [Unreleased]

### Added
- THORChain REST client, pre-broadcast verify gate, and encrypted keystore
  (HD seeds + raw keys, AES-256-GCM, atomic writes).
- Chain adapters: BTC (bitcoinlib), ETH + ERC-20 (eth-account/eth-abi),
  TRON (address + balance).
- Swaps: BTC, ETH (native), TRX (native) and USDT-ETH (ERC-20) as sources; BTC,
  ETH, TRX, USDT-TRON, USDT-ETH and (external-`--dest`-only) LTC, DOGE, BCH as
  destinations. `--amount max` sweep for BTC/ETH (swap and add-liquidity). TRX
  source signs a native
  TransferContract with the memo in tx data (tronpy), via a keyless public node.
- Permissive `--dest` sanity check (network/format) to catch gross typos before
  a swap is quoted or broadcast.
- Registry-based multi-chain `balance` (now also reports THORChain/Maya
  liquidity positions: total redeemable value in the asset — the RUNE/CACAO side
  of a position is converted at the pool price and folded in, not added raw —
  plus any pending); `quote`, `status`, `address`.
- Experimental `add-liquidity` / `withdraw-liquidity` (BTC, ETH, TRX,
  single-sided), with `--backend {thorchain,maya}` and a pre-flight `PAUSELP`
  check that aborts an add THORChain would only refund.
- `send` to an external address (BTC; plain transfer, no swap/memo), with
  `--amount max` to sweep. Guarded by a dedicated verify gate.
- Packaging: Hatch + hatch-vcs, `make install`, `--version`, CI, and PyPI
  trusted-publishing gated on the live integration tests.
