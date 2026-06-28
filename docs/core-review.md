# Core review — cryptoswap

*Date: 2026-06-28. Reviewer: Claude Opus 4.8 via Claude Code, on behalf of tobixen.
Scope: all of `src/cryptoswap` (cli, swap, verify, keystore, thorchain, chains/*).
State at review: `pytest` 88 passed, `ruff check` clean.*

This is a hot wallet that builds and broadcasts irreversible transactions, so the
review weights **fund-safety** and **the integrity of the verify gate** highest,
then the **abstraction / duplication** question you flagged, then robustness/style.

---

## TL;DR

The core design is sound: a strict, dependency-free pre-broadcast verify gate,
secrets wrapped so they don't leak into reprs, dry-run-by-default, and a quote →
build → verify → confirm → sign → broadcast pipeline that is genuinely
unit-testable via fakes. Naming *is* consistent across chains (`derive_address`,
`wallet_balance`, `fetch_balance`, `broadcast`, `build_unsigned_swap`, `sign`).

But the **shared implementation is copy-pasted, not factored** — the HTTP-client
plumbing, the eth_account key derivation, the single-address `wallet_balance`,
the `prepare_*_swap` orchestration and the CLI per-chain handlers each exist in
2–3 near-identical copies. The `ChainAdapter` protocol is also thinner than the
code it claims to describe and isn't fully honoured. None of this is a bug today,
but it's exactly the kind of drift that bites when you add the next chain/token.

Two findings touch fund-safety and deserve action regardless of polish:
**H1 (non-atomic keystore write)** and **M1 (the gate never confirms the quoted
memo actually pays *you*)**.

---

## A. Abstraction & code duplication (your main concern)

Verdict: **the interface is clean, the implementations are duplicated.** The
abstraction is "consistent method names" but not "shared code." Below, concrete
copies with file:line.

### A1. HTTP-client boilerplate copied 3× (+ a 4th variant)

The identical lazy-client / `close` / `__enter__` / `__exit__` block appears in:

- `chains/btc.py:95-114`
- `chains/eth.py:95-110`
- `chains/tron.py:49-64`

and `thorchain.py:147-165` is a fourth, slightly different, hand-rolled variant.
That's ~20 lines duplicated four ways. This is the single clearest cleanup.

**Fix:** a small `HttpClient` mixin/base (holds `_client`, `_http`, `close`,
context-manager protocol; takes `timeout`). All adapters inherit it; the only
per-chain difference is the base URL field name, which can be a constructor arg.

### A2. eth_account key derivation copied between ETH and TRON

`chains/eth.py:112-116` and `chains/tron.py:66-71` both do:

```python
Account.enable_unaudited_hdwallet_features()   # module level, twice
def _key(self, mnemonic, path): return Account.from_mnemonic(mnemonic, account_path=path)
```

TRON then reuses the *EVM* address (`self._key(...).address[2:]`) and re-encodes
it. So there is a genuine shared "EVM secp256k1 keypair from mnemonic" concept
split across two files, plus `enable_unaudited_hdwallet_features()` called in two
modules.

**Fix:** a shared `chains/_evm.py` (or `_secp.py`) exposing `evm_account(mnemonic,
path)` and the `to_checksum_address`/keccak helpers (currently only in
`eth.py:34-65`). TRON's address is then "take the 20-byte EVM pubkey-hash, prefix
0x41, base58check" — expressed in terms of the shared primitive.

### A3. Single-address `wallet_balance` copied between ETH and TRON

`chains/eth.py:137-144` and `chains/tron.py:80-87` are structurally identical:

```python
def wallet_balance(self, mnemonic):
    address = self.derive_address(mnemonic)
    return BalanceReport(symbol=..., confirmed=self.fetch_balance(address),
                         decimals=..., note=f"({address})")
```

Only `symbol`/`decimals` differ. (BTC legitimately differs — it scans.)

**Fix:** a default `wallet_balance` on the account-model base that calls
`self.fetch_balance(self.derive_address(mnemonic))` and reads `symbol`/`decimals`
from class attributes. Two methods collapse to zero.

### A4. `prepare_btc_swap` vs `prepare_eth_swap` are parallel (~60 lines each)

`swap.py:142-201` and `swap.py:204-265` share the same skeleton: tradable check →
quote → `recommended_min_amount_in` check → memo-present check → build → construct
plan → call the verify gate → return `Prepared`. The divergence is only: which
`build_*` signature, how the plan is built, and which `verify_*` runs.

This duplication forced two near-identical `Protocol`s too (`BtcSwapAdapter` /
`EthSwapAdapter`, plus `BuiltSwapLike` / `EthBuiltLike`). It's readable, but every
future source chain adds another 60-line near-copy and another protocol pair.

**Fix (worth it once a 3rd source chain lands, not before):** give the adapter
the responsibility of returning *both* the built tx **and** its verify-plan +
running its own gate, behind one `prepare()` signature. The orchestrator keeps
the chain-agnostic parts (tradable/quote/min/memo/expiry) and delegates
build+verify to the adapter. That removes the BTC/ETH fork from `swap.py` and the
parallel protocols.

### A5. CLI per-chain duplication

- Three near-identical adapter factories `_btc_adapter`/`_eth_adapter`/
  `_tron_adapter` (`cli.py:67-93`) — same arg→env→default URL dance.
- `_resolve_destination` (`cli.py:220-241`) and `cmd_address` (`cli.py:179-188`)
  both hand-dispatch on chain with `if ETH / if BTC / if TRON` and instantiate
  adapters inline.
- `_swap_from_btc` (`cli.py:303-371`) and `_swap_from_eth` (`cli.py:374-434`)
  are large parallel handlers (load mnemonic → resolve dest → sweep branch →
  build request → `prepare_*` → print summary → `_confirm_and_execute`).

**Fix:** a small registry mapping chain → adapter factory (URL env var + default)
so the three factories, the `_resolve_destination` dispatch and `cmd_address`
all iterate one table. The two `_swap_from_*` bodies can share a helper for the
common skeleton, leaving only the summary-print and the sweep-amount call
chain-specific.

### A6. Where the abstraction is actually good (keep doing this)

- **Token *destination* handling is clean** — the `ASSET` map (`cli.py:39-45`)
  plus `_derivable_chain` + `_resolve_destination` means `BTC→TRON.USDT` lands at
  the same derived Tron address as native TRX with no new code. This is the model
  to extend the source side toward once USDT-source is picked up.
- `scan.py` is correctly generic: `derive_address`/`probe` injected, pure gap
  logic, reused by `BtcAdapter.wallet_balance` and the swap path alike.
- `BalanceReport` (`base.py`) gives one formatting path for all chains.
- `verify.py` is dependency-free and the same gate is the choke point for every
  source chain.

### A7. The `ChainAdapter` protocol under-describes and is under-honoured

`base.py:36-49` declares `chain`, `asset`, `derive_address`, `wallet_balance`,
`broadcast`. Reality:

- `TronAdapter` has **no `broadcast`** (destination-only) yet is presented as a
  `ChainAdapter` and is put in `_wallet_adapters` — so the protocol claims a
  method the object lacks. It's `runtime_checkable` but never actually checked,
  so this passes silently today.
- Source adapters add `build_unsigned_swap`/`sign` that the protocol doesn't
  mention; the orchestrator instead relies on the separate ad-hoc protocols in
  `swap.py`.

**Fix:** split the protocol into what it really is — a `WalletChain` (derive +
balance, all three satisfy) and a `SourceChain` (adds build/sign/broadcast, BTC
& ETH satisfy). That makes "Tron is destination-only" a type-level fact instead
of a latent `AttributeError` waiting for someone to call `broadcast` on it.

---

## B. Correctness & fund-safety findings

### H1 — Keystore save is not atomic; a crash can destroy the keystore

`keystore.py:147-169` opens the target path with `O_TRUNC` and writes in place.
Every mutating CLI command is load → mutate → `save` over the same file
(`cmd_add_hd` `cli.py:123-148`, `cmd_add_raw` `cli.py:160-168`). A crash, full
disk, or `^C` between truncate and full write leaves a **truncated/corrupt
keystore**.

Why this is more than theoretical here: `add-hd --generate` (`cli.py:127-130`)
creates a seed that exists **only** inside this keystore. Corrupting the file on
that save = irreversible loss of those funds, with no external backup yet made.

**Fix:** write to a temp file in the same directory (0600), `fsync`, then
`os.replace()` onto the target — atomic on POSIX. Optionally keep a `.bak` of the
previous envelope. Cheap, removes a whole class of loss.

### M1 — The verify gate never confirms the quoted memo pays *your* destination

`verify.py` checks the on-chain memo equals `plan.memo`, and `plan.memo` is just
`quote.memo` echoed back (`swap.py:187-192`, `248-253`). Nothing cross-checks
that `quote.memo` actually encodes `request.destination`. So the gate guarantees
"the tx matches the quote," but **not** "the quote sends funds to me."

The module docstring says the gate's job is that "a wrong vault, amount or memo
means irreversible loss." A quote whose memo carried someone else's destination
(buggy/compromised quote endpoint, or a `--dest` that silently differs from what
was quoted) would sail through. HTTPS + trusting THORChain lowers the likelihood,
but checking your own destination is squarely the gate's stated mission and is
nearly free.

**Fix:** thread `request.destination` into `SwapPlan`/`EthSwapPlan` and assert it
appears in the decoded memo (THORChain swap memos are
`=:ASSET:DEST:LIM/interval/qty:...`). Add a unit test with a memo whose
destination differs from the requested one and assert it's rejected.

### M2 — `fetch_fee_rate` fallback picks the *cheapest* (slowest) rate

`chains/btc.py:220-224`: if the requested `target_blocks` key is absent, it falls
back to `min(estimates.values())` — the lowest fee rate, i.e. the longest
confirmation target. A swap funded at the slowest rate can sit unconfirmed; on
THORChain slow inbound confirmation is exactly what you don't want. Blockstream
normally returns `"6"`, so this is latent, but the fallback direction is wrong.

**Fix:** fall back to the nearest available target ≤ requested (highest fee among
the conservative options), or just `max(...)`; never silently choose the cheapest.

### M3 — `sign` swallows unmatched keys with no completeness check

`chains/btc.py:176-180` signs with `fail_on_unknown_key=False`. The comment
explains why (per-input keys), but if a path bug left an input *unsigned*, this
hides it; you'd only find out when broadcast is rejected (benign — no funds move,
but a confusing failure right at the "confirm" moment).

**Fix:** after signing, assert every input has a witness/scriptSig (bitcoinlib
exposes input completeness) and raise a clear error otherwise.

### L1 — `fetch_utxos` defaults missing `status.confirmed` to `True`

`chains/btc.py:196`: `if x.get("status", {}).get("confirmed", True)`. If a future
Esplora-compatible backend omits `status`, an **unconfirmed** UTXO would be
treated as spendable — the opposite of the confirmed-only intent in TODO.md.
Default to `False` (fail closed) for a money path.

### L2 — No guard against non-positive amounts

`cli.py:248`/`341`/`400`: `int(round(args.amount * THORCHAIN_UNIT))` accepts `0`
or negative floats. `0` is caught later by the `recommended_min` check; negatives
rely on THORChain erroring. Cheap to reject `amount <= 0` at parse time.

---

## C. Minor / robustness / style

- **`_derive_key` ignores the stored `length`** (`keystore.py:182` passes n/r/p
  but not `length`); harmless because it's always 32, but the envelope advertises
  a parameter the loader doesn't honour. Either read it or drop it from the
  envelope.
- **`scan_account` rebuilds a `ThreadPoolExecutor` per window**
  (`scan.py:48`). Create one pool for the whole account scan.
- **`quote` output misalignment** — `memo:` is indented differently from the
  other rows (`cli.py:264` vs `266`). Cosmetic.
- **ETH/TRON balance only inspects index 0** (`eth.py:137`, `tron.py:80`).
  Consistent with how addresses are derived/used today; fine, but note it the way
  BTC's "(N used addresses)" does, so a user with funds at index 1 isn't
  surprised by a `0.0` balance.
- **`recommended_min`/tolerance not user-tunable** — `tolerance_bps` is fixed at
  300 (`swap.py:24`); there's no CLI flag to tighten slippage protection. Worth a
  `--tolerance-bps` once you trust the live path.

---

## D. USDT / work-in-progress (noted, not scored)

You flagged USDT source support as WIP, so it's excluded from the findings. For
when you pick it up: the **destination** side is already the clean part (A6); the
**source** side is where the A4/A5 duplication will hurt most, because ERC-20 /
TRC-20 `approve` + `router.depositWithExpiry` is a third `build_unsigned_swap`
shape. Doing the A4 refactor (adapter owns build+plan+verify behind one
`prepare()`) *before* adding the token source path will save you a third
near-copy of `prepare_*_swap` and `_swap_from_*`.

---

## Suggested order of work

1. **H1** atomic keystore write — smallest change, biggest downside removed.
2. **M1** memo-destination assertion + test — restores the gate's full promise.
3. **A1** HTTP mixin, **A2/A3** EVM key + account-balance sharing — low-risk
   dedup, immediate readability win.
4. **M2 / L1 / M3** fee-fallback, fail-closed UTXOs, sign completeness.
5. **A4/A5/A7** the deeper orchestrator/protocol refactor — do this as the lead-in
   to USDT-source rather than as standalone churn.
