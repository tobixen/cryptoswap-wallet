# Dash (DASH) support — design notes

Status: **not started** as a wallet chain; **destination-only is trivial and
recommended first.** This note records the findings from scoping "full support
for Dash" so the work is recoverable and the risky parts are decided
deliberately rather than in the middle of a money path.

## TL;DR

- **Swaps are feasible — via Maya only.** Dash is **not on THORChain** at all.
  Maya runs a live `DASH.DASH` pool (checked 2026-07-01: `Available`, depth
  ~2,291 DASH). Every Dash swap therefore routes through the Maya backend
  (`--backend maya`, or `auto`, which price-routes across backends).
- **Destination (`--to DASH`) is a small, low-risk, testable increment** — it
  mirrors LTC/DOGE/BCH: an `ASSET` entry plus a permissive `--dest` sanity
  rule. No wallet-side code, no new data source. **Do this first.**
- **The full wallet side (Hold/Bal/Send/Sweep/From/Liq) is a much bigger,
  riskier job than the other UTXO coins**, because Dash is a *legacy* (non-
  segwit) UTXO chain with **no Blockstream Esplora** and **no easy testnet
  path**. It needs a new legacy-UTXO adapter, generalized money-sensitive fee
  maths, and a Dash data source we must choose and trust.

## Why Dash is not "just another BTC"

The BTC adapter (`chains/btc.py`) and the coin-selection/fee maths
(`chains/coins.py`) are hardcoded to **native segwit (P2WPKH)**: bech32
addresses, `witness_type="segwit"`, and P2WPKH input/output virtual sizes
(`P2WPKH_INPUT_VB = 68`, `P2WPKH_OUTPUT_VB = 31`, `DUST_P2WPKH = 294`). Dash
has **no segwit** — it is legacy pay-to-pubkey-hash only. That means:

1. **No Dash network in bitcoinlib.** The installed bitcoinlib ships
   `bitcoin`, `litecoin`, `dogecoin` — but **not** `dash` (nor bch/zcash). A
   Dash network must be registered at runtime by adding an entry to
   `bitcoinlib.networks.NETWORK_DEFINITIONS`. Dash mainnet parameters:

   | field | value | note |
   |---|---|---|
   | `prefix_address` (P2PKH) | `4C` (76) | addresses start with `X` |
   | `prefix_address_p2sh` | `10` (16) | P2SH start with `7` |
   | `prefix_wif` | `CC` (204) | |
   | xpub / xprv | `0488B21E` / `0488ADE4` | standard BIP32 (as Trust Wallet uses; the legacy `drkp/drkv` bytes are deprecated) |
   | `bip44_cointype` | `5` | derivation `m/44'/5'/0'/0/x` |
   | segwit | **none** | legacy `p2pkh` only |

2. **Legacy derivation + script type.** Addresses derive at `m/44'/5'/0'/0/x`
   with `script_type="p2pkh"` / `encoding="base58"` (contrast BTC's
   `m/84'/0'/0'/0/x`, `p2wpkh`/bech32). The transaction must be built with
   `witness_type="legacy"`.

3. **Different fee maths.** Legacy vsizes differ from segwit: a P2PKH input is
   ~148 vbytes and a P2PKH output ~34 vbytes (vs 68/31 for P2WPKH), with no
   witness discount and a different dust threshold (~546). `coins.py`
   (`estimate_vsize`, `select_coins`, `sweep_amount`, the `P2WPKH_*`/`DUST_*`
   constants) must be **parameterized by script type**, not copy-pasted — this
   is the money-sensitive core and should stay a single, well-tested code path.

## The data-source problem (the real blocker)

The BTC adapter's entire balance / UTXO / broadcast / fee layer is
**Esplora-shaped** (`/address/{a}`, `/address/{a}/utxo`, `POST /tx`,
`/fee-estimates`). **There is no Blockstream Esplora for Dash.** So the wallet
side needs a different data source, with its own client methods. Options
scoped on 2026-07-01:

| Option | keyless | status when checked | API shape | risk |
|---|:--:|---|---|---|
| **Insight** (`insight.dash.org/insight-api`) | ✅ | up, synced 100% (height 2,497,657) | Insight/Bitcore: `GET /addr/{a}`, `GET /addr/{a}/utxo`, `POST /tx/send`, `GET /addrs/{a}/txs` | **single community-run instance** — a lone SPOF for a wallet; if it's down you can't spend, if it lies you mis-report funds |
| **Trezor Blockbook** (`dashN.trezor.io/api/v2`) | ✅ | **did not respond** at the probed hosts | Blockbook v2: `/address/{a}`, `/utxo/{a}`, `/sendtx/{hex}` | keyless + reputable operator, but availability unconfirmed; different (non-Esplora) shape |
| **Blockchair** (`api.blockchair.com/dash`) | ❌ | not probed | its own JSON; UTXO + push | needs an API key + is rate-limited; ToS |
| **Configurable `--dash-api`** | — | — | pick one shape, allow override | best for resilience: default to one, let the user point at their own node/instance; ideally **union two sources** so a stale/lying instance can't silently *shrink* the balance |

Notes:
- `estimatefee` is not available on the Insight instance (Dash Core doesn't
  expose it usefully). Dash fees are ~fixed and low; for a **swap** use Maya's
  quote `recommended_gas_rate` / `gas_rate_units`, and for a plain **send** use
  a conservative fixed rate (duffs/byte) or Maya `inbound_addresses` gas rate.
- A wallet's worst failure is silently **under-reporting** funds (see the
  balance-cache caveat in `TODO.md`). A single explorer that is behind or
  degraded can do exactly that, so the "let me decide later / configurable +
  union" path is the safest and is the current owner preference.

**Decision deferred (owner):** compare Insight / Blockbook / Blockchair /
configurable-endpoint and pick before committing wallet-side code.

## Testability caveat

Like the rest of the project's spending paths, the Dash spend side would ship
**unexercised on mainnet**: there is no widely-available Dash testnet with an
Esplora/Insight faucet path comparable to BTC testnet3 / ETH Sepolia
(`tests/test_integration_testnet.py`). Coin-selection/fee maths and the verify
gate are unit-testable offline; the actual UTXO-scan-and-broadcast loop is not,
without funded mainnet Dash. Plan units + an opt-in mainnet broadcast test
gated on a funded account/secret, mirroring the Nile TRC-20 loop.

## Recommended phasing

- **Phase 0 — destination (`--to DASH`).** Add `DASH: "DASH.DASH"` to the CLI
  asset map and a `--dest` rule to `addresses.py`
  (`re.compile(rf"^[X7]{_B58}{{24,34}}$")` — Dash P2PKH `X` / P2SH `7`, charset
  + length, **not** checksum; Maya validates the checksum). Confirm with a live
  `--backend maya`/`auto` quote that a `DASH.DASH` pool is hit and the memo
  pays the dest. Fully doable and testable today.
- **Phase 1 — Hold + Balance (read-only).** Register the Dash network in
  bitcoinlib; new `chains/dash.py` with `derive_address` (`m/44'/5'`, p2pkh)
  and `wallet_balance` via the chosen data source + `scan_account`. Read-only,
  so testable without spending. Wire into `cmd_address` and the balance report.
- **Phase 2 — Send / Sweep.** Generalize `coins.py` for legacy (P2PKH) vsizes;
  build a legacy `build_unsigned_*` in `dash.py`; add a `verify_dash_send`
  gate (recipient + amount, no memo/witness) mirroring `verify_btc_send`. Wire
  into `cmd_send`. Add an opt-in mainnet broadcast test.
- **Phase 3 — From (swap source) + Liq.** Reuse the Phase-2 deposit path with a
  Maya vault + `=:`-memo OP_RETURN (mind Dash relay policy on OP_RETURN size);
  `build_and_verify` / `build_and_verify_deposit` against the **Maya** client;
  single-sided LP pairs with CACAO (no `auto` for LP — it's a pairing choice).

## See also

- `docs/TODO.md` — "Swap backends" → Maya-only assets (DASH/ZEC/ADA/ARB).
- `docs/monero.md` — the other "doesn't fit the model yet" chain, same note style.
- `README.md` — currency roadmap row for DASH.
