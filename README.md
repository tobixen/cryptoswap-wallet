# cryptoswap

A python/CLI multi-currency wallet that may do non-custodial cross-chain swaps via [THORChain](https://thorchain.org/).

⚠️ This project is vibed-up, what could possibly go wrong?  **Don't use this wallet for more funds than what you can afford to lose**.  Bugs in the code may easily cause **irreversible loss of funds**.  Even if all the code is perfect, consider that this is a **hot wallet**, an attacker that gains a foothold on the computer running this wallet software may potentially manage to drain the funds in the wallet.

## Status

Working (dry-run by default; `--confirm` to broadcast):

- [x] THORChain client — `cryptoswap.thorchain`
- [x] Pre-broadcast verify gate (BTC + ETH) — `cryptoswap.verify`
- [x] Encrypted keystore (HD seed **and** raw keys) — `cryptoswap.keystore`
- [x] Chain adapters: BTC (bitcoinlib), ETH (eth-account), TRON (addr + balance) — `cryptoswap.chains`
- [x] Swap orchestrator + gap-limit BTC scanning — `cryptoswap.swap`, `cryptoswap.chains.scan`
- [x] Registry-based multi-chain `balance`; `--amount max` sweep (BTC and ETH)
- [x] CLI: `init`, `add-hd`, `add-raw`, `list`, `show-seed`, `address`, `balance`, `quote`, `swap`, `status`

**Swap routes** (source → destination)

| from ↓ \ to → | BTC | ETH | TRX | USDT-TRON | USDT-ETH |
|---|:--:|:--:|:--:|:--:|:--:|
| **BTC** | — | ✅ | ✅ | ✅ | ✅ |
| **ETH** | ✅ | — | ✅ | ✅ | ✅ |

Sources are **BTC and ETH** (native). TRX, USDT-TRON and USDT-ETH are
**destinations only** — spending *from* TRON, or from a token (the TRC-20 /
ERC-20 `approve` + router path), is future work. Destination addresses
auto-derive from the seed; pass `--dest` to override. BTC scanning is BIP84
(Trust Wallet's scheme); compiled BDK has no Python 3.14 wheel, so BTC uses
`bitcoinlib`.

See `docs/TODO.md` for remaining work. Phase 2 (later): semi-automatic "convert
everything above dust since last run".

## Usage

```sh
uv run cryptoswap init                                   # create encrypted keystore
uv run cryptoswap add-hd --label main                    # import seed (prompted), or:
uv run cryptoswap add-hd --label test --generate         # generate a fresh seed
uv run cryptoswap address                                # BTC / ETH / TRON addresses
uv run cryptoswap balance                                # balances across all chains
uv run cryptoswap quote --from ETH --to USDT-TRON --amount 0.02   # read-only
uv run cryptoswap swap  --from ETH --to BTC --amount max          # DRY RUN (sweep)
uv run cryptoswap swap  --from BTC --to USDT-TRON --amount 0.001 --confirm
```

Defaults are `--from BTC --to ETH`. `--confirm` prints the freshly-quoted swap
and asks before broadcasting (`--yes` skips the prompt for automation).

Config via flags or env: keystore `$CRYPTOSWAP_KEYSTORE`
(`~/.config/cryptoswap/keystore.json`), passphrase `$CRYPTOSWAP_PASSPHRASE`,
Esplora `$CRYPTOSWAP_ESPLORA`, Ethereum RPC `$CRYPTOSWAP_ETH_RPC`, TRON API
`$CRYPTOSWAP_TRON_API`.

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
