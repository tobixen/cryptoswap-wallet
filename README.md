# cryptoswap

A python/CLI multi-currency wallet that may do **non-custodial** cross-chain swaps via [THORChain](https://thorchain.org/).

⚠️ This project is vibed-up, what could possibly go wrong?  **Don't use this wallet for more funds than what you can afford to lose**.  Bugs in the code may easily cause **irreversible loss of funds**.  Even if all the code is perfect, consider that this is a **hot wallet**, an attacker that gains a foothold on the computer running this wallet software may potentially manage to drain the funds in the wallet.

## Status

Phase 1 complete (BTC→ETH/TRX swaps, dry-run by default):

- [x] THORChain client — `cryptoswap.thorchain`
- [x] Pre-broadcast verify gate — `cryptoswap.verify`
- [x] Encrypted keystore (HD seed **and** raw keys) — `cryptoswap.keystore`
- [x] `ChainAdapter` interface + BTC adapter (bitcoinlib) + minimal ETH address — `cryptoswap.chains`
- [x] Swap orchestrator + gap-limit address scanning — `cryptoswap.swap`, `cryptoswap.chains.scan`
- [x] CLI: `init`, `add-hd`, `add-raw`, `list`, `address`, `balance`, `quote`, `swap`, `status`

Notes / limits: BTC source only so far (ETH/TRON as sources are future adapters);
real wiring scans BIP84 (Trust Wallet's scheme); compiled BDK has no Python 3.14
wheel, so BTC uses `bitcoinlib`.

Phase 2 (later): semi-automatic "convert everything above dust since last run".

## Usage

```sh
uv run cryptoswap init                              # create encrypted keystore
uv run cryptoswap add-hd --label main               # paste seed when prompted
uv run cryptoswap address                           # show derived BTC + ETH addresses
uv run cryptoswap balance                           # scan + show BTC balance
uv run cryptoswap quote --amount 0.001781           # BTC->ETH quote (read-only)
uv run cryptoswap swap  --amount 0.001781           # build + verify, DRY RUN
uv run cryptoswap swap  --amount 0.001781 --confirm # actually broadcast
```

Keystore path: `$CRYPTOSWAP_KEYSTORE` or `~/.config/cryptoswap/keystore.json`.
Passphrase: `$CRYPTOSWAP_PASSPHRASE` or interactive prompt.

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
