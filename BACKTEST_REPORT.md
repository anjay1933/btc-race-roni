# Backtest report — btc-race-24h-20261117-0603 (roni account)

## Dev window (frozen, from the competition kit)

- 1,440 one-minute cbBTC/USDC bars, 2026-11-16 06:03 UTC → 2026-11-17 06:03 UTC, 0 gaps.
- First close $64,461.04, last close $64,775.95 (window return +48.9 bps).
- Range $63,874.36 – $65,466.84; 141 flat bars; 1-min return std 6.44 bps.
- Buy-and-hold on the same window: **+$1.07** (after costs). House
  ema-cross baseline: **-$111.38** (70 trades — churned to death).
  House momentum: +$2.45.
- Shape of the window: choppy drift down to $63,874 (12:00 UTC), a sharp
  +130 bps rally hour at 14:00 UTC (high $65,456), a slow evening grind
  up to $65,467 (22:00 UTC), then a choppy fade to $64,776.

## Strategy (final)

V-Bounce, full size, one position at a time:

| Parameter | Value |
|---|---|
| Decline setup (DECLINE_BARS / DECLINE_BPS) | 30 bars / −30 bps vs 30 bars ago |
| Bounce trigger (BOUNCE_BARS / BOUNCE_BPS) | 5-bar return crosses up through +20 bps |
| Take-profit (TAKE_PROFIT_BPS) | +200 bps on the entry close |
| Trailing stop (TRAIL_BPS) | 120 bps below the peak close since entry |
| Max hold (MAX_HOLD_BARS) | 360 bars |
| Max slippage per order | 200 bps |

## Official grade-local (kit's own harness, `--driver process`)

```
status: finished
net_pnl_quote_units: 27,756,739  (= +$27.76)
return: 0.027756739
max_drawdown: 0.009167765  (0.92%, guardrail 25%)
trades: 5  (guardrail: >= 1)
win rate: 1.000000000
fees: 2.447232 USDC; net PnL at 2x fees: +$25.30
action_log_sha256: 194186fd1fd6cb7d51fa07e8ee448734a71e90e2d1af791c5bc2bba9c973d65d
result_sha256: e991a7008017ee9f8a6c135879214bf35b4ef1c87b647bfa8324586413e838af
L1 regrade: reproduced byte for byte (deterministic)
guardrails met (trades ok, symbols ok, drawdown ok)
```
Note: `mismatches` lists only the Node version (server harness v26.13.1,
this machine v24.22.1). The bot uses stdlib `readline` + `JSON` only.

## Local backtest (`python3 backtest.py`, drives real main.ts)

Identical number: **+$27.76, 6 fills (5 trades + final flatten),
fees $2.45, maxDD 0.92%, deterministic (identical order streams over
two runs)**.

Trade log (UTC):

| Bar | Time | Side | Fill | Size |
|---|---|---|---|---|
| 392 | 12:32 | BUY | $64,133.10 | $1,000.00 |
| 515 | 14:35 | SELL | $65,281.92 | $1,017.51 |
| 568 | 15:28 | BUY | $64,438.26 | $1,017.10 |
| 928 | 21:28 | SELL | $65,145.81 | $1,027.86 |
| 1236 | 26:36 | BUY | $64,618.14 | $1,027.44 |
| 1439 | 29:59 | FLATTEN | $64,689.59 | $1,028.17 |

Trade 1 bought the bounce off the midday low and rode the 14:00 rally
to the +200 bps target; trade 2 bought the 15:00 pullback bounce and
rode the evening grind to the 360-bar hold cap; trade 3 bought the
late-night bounce and was flattened near breakeven at the window end.

## Robustness (same fill model, full dev window)

- **Halves:** first 12h +$19.86, second 12h +$0.37. Both halves
  non-negative; the edge is not one half's accident.
- **Fine grid around the final parameters (900 combos): 832 positive.**
  Every single-parameter move stays positive:
  - decline 25 → +$27.76, 35 → +$28.02
  - bounce 15 → +$12.29, 25 → +$10.21
  - take-profit 150 → +$23.54, 250 → +$15.88
  - trailing stop 80 → +$27.76, 150 → +$27.76
  - max hold 240 → +$22.25, 480 → +$26.74
  The chosen parameters sit mid-plateau, not on a peak.
- **2x fees:** +$25.30 — the edge is not fee-thin.

## Families tried and rejected (same window, same fill model)

- Trend-pullback (buy EMA touch in an uptrend, fixed TP): **0 of 54
  positive**, best −$15.74.
- Momentum ignition (buy a 5–30 bar return spike, fixed TP/stop):
  best +$11.69, only 133 of 540 positive, and the whole PnL came from
  a single trade — too thin.
- MACD momentum: **0 of 27 positive**, best −$57.80 (44 trades —
  churned).
- Keltner channel breakout: **0 of 54 positive**, best −$98.88
  (68 trades — churned).
- Scale-in momentum (50% on ignition, add 50% on continuation):
  best +$1.28.
- Bollinger mean-reversion, RSI momentum, Donchian breakout (from the
  agent entry's research on the same window): all negative or fragile.

## Difference vs the agent account's entry ("Drawdown Ride", dev +$18.29)

- Drawdown Ride buys the **drop itself**: close ≥120 bps below the
  rolling 240-bar high, full size, exits on a dynamic trailing stop
  (250 bps wide, tightening to 60 bps once +100 bps in profit).
- V-Bounce buys the **recovery**: it needs a 30-bar decline AND the
  5-bar return turning up through +20 bps, and exits on a fixed
  +200 bps target plus a 120 bps trailing stop.
- Different entry trigger, different confirmation, different exit —
  and different trades: Drawdown Ride's fills were 12:11 / 14:45 /
  15:04 / 23:04 / 24:03 / flatten; V-Bounce's are 12:32 / 14:35 /
  15:28 / 21:28 / 26:36 / flatten. The action logs differ
  (V-Bounce `action_log_sha256: 194186fd…`, Drawdown Ride's
  `result_sha256: 1944b652…`).

## Dev gate verdict

**PASS: +$27.76 > $0**, with margin. Guardrails met (5 trades,
maxDD 0.92%). The entry races if submitted as the final entry.
