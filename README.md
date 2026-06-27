# cryptoswap

A CLI multi-currency wallet with **non-custodial** cross-chain swaps via
[THORChain](https://thorchain.org/).

> ⚠️ **Hot-wallet, small-funds tool.** Private keys live (encrypted) on this
> machine and sign programmatically. Do not keep meaningful funds here. A
> THORChain swap with a wrong vault address, amount or memo means
> **irreversible loss** — that is why every swap goes through a strict
> pre-broadcast verify gate (`cryptoswap.verify`).

## Status

Phase 1, in progress:

- [x] THORChain client (quotes, inbound addresses) — `cryptoswap.thorchain`
- [x] Pre-broadcast verify gate — `cryptoswap.verify`
- [ ] Keystore (HD seed **and** raw private keys, encrypted at rest)
- [ ] BTC wallet (BDK): sync, build OP_RETURN swap tx, sign, broadcast
- [ ] CLI: `balance`, `quote`, `swap`, `status`

Phase 2 (later): semi-automatic "convert everything above dust since last run".

## Development

```sh
uv run pytest        # tests (auto-syncs the env)
uv run ruff check .
uv run ruff format .
```

## Refreshing test fixtures

The fixtures in `tests/` are trimmed real responses from the THORChain REST API:

```sh
curl -s "https://thornode.thorchain.liquify.com/thorchain/quote/swap?from_asset=BTC.BTC&to_asset=ETH.ETH&amount=178100"
curl -s "https://thornode.thorchain.liquify.com/thorchain/inbound_addresses"
```
