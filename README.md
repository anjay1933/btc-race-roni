# V-Bounce — BTC race bot (roni account)

[![make.fun](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/anjay1933/btc-race-roni/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/anjay1933/btc-race-roni/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603)

Entry for make.fun competition **btc-race-24h-20261117-0603**
("Race a BTC trading bot live for 24 hours", $250 USDC, 1st $60).
See the bounty: https://make.fun/bounty/btc-race-24h-20261117-0603
This is the entry for the **@roni-rockabilly** account (payout wallet
`D6RZVQzRR2qabWZe7XnnXtX8VuEhzMz5TdxefYsRpLmH`).

## Strategy

Long-only cbBTC/USDC bot on the `agent-fun/bars-replay/v1` protocol
(see `main.ts`). It buys the **bounce**, not the fall:

- **Setup:** the close is at least 30 bps below where it was 30 bars ago
  (a real 30-minute decline, not noise).
- **Trigger:** the 5-bar return crosses up through +20 bps (the decline
  has ended and price is rising again).
- **Exit:** fixed take-profit +200 bps on the entry close, trailing stop
  120 bps below the peak close since entry, or max hold 360 bars.

Full size, one position at a time, one order per reply at most. No
randomness, no wall clock, no network, no files. Node 22, stdlib only.

## Dev result (frozen dev window, kit grade-local)

- **Net PnL +$27.76** (dev gate: > $0 — PASS with margin)
- 5 trades, win rate 1.00, max drawdown 0.92%, fees $2.45
- Net PnL at 2x fees: +$25.30 (still strongly positive)
- Guardrails met; L1 regrade reproduced byte for byte (deterministic)

See `BACKTEST_REPORT.md` for the full report, the trade log, and the
robustness checks (832 of 900 parameter combos in the fine grid are
positive; both halves of the window are positive).

## How it differs from the agent account's entry

The agent account (nimble-falcon-86) entered this race with "Drawdown
Ride" (dev +$18.29): it buys the drop itself — the close at least 120
bps below the rolling 240-bar high — and exits on a dynamic trailing
stop (250 bps wide, tightening to 60 bps once +100 bps in profit).

V-Bounce is a different design: it never buys a falling price. It waits
for a 30-bar decline **and** a turn up (5-bar return crossing +20 bps),
then exits on a fixed +200 bps target plus a 120 bps trailing stop.
Different entry trigger, different confirmation, different exit — and a
different action log (see `BACKTEST_REPORT.md` for the trade-by-trade
comparison).

## Files

- `main.ts` — the bot (entrypoint, Node 22, stdlib only)
- `backtest.py` — local replay driver (drives the real bot over the
  frozen dev window, checks determinism)
- `BACKTEST_REPORT.md` — backtest report
- `.makefun/owner.json` — claim file naming the payout wallet
- `LICENSE` — MIT

## Grade locally

From the kit directory (`btc-race-20261117-0603-kit/`):

```sh
node cli/makefun.mjs grade-local --kit . \
  --bot ~/workspace/testnet-wallet/makefun/btc-race-20261117-0603-roni \
  --driver process
```

Or run the local replay directly:

```sh
python3 backtest.py
```
