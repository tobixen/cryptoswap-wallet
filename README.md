# cryptoswap

A python/CLI multi-currency wallet that may do **non-custodial**
cross-chain swaps via [THORChain](https://thorchain.org/).

⚠️ This project is vibed-up, what could possibly go wrong?  **Don't use this wallet for more funds than what you can afford to lose**.  Bugs in the code may easily cause **irreversible loss of funds**.  Even if all the code is perfect, consider that this is a **hot wallet**, an attacker that gains a foothold on the computer running this wallet software may potentially manage to drain the funds in the wallet.

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
