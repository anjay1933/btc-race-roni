/**
 * V-Bounce BTC bot for make.fun btc-race-24h-20261117-0603 (roni account).
 *
 * Long-only cbBTC/USDC bot on the agent-fun/bars-replay/v1 protocol: it reads
 * one JSON line per minute (hello, then one batch per 1-minute bar, then done)
 * and answers every batch with exactly one reply echoing its seq.
 *
 * Strategy (validated on the frozen 24h dev window of this competition):
 *   - Flat: wait for a V-bounce. A bounce is set up when the close is at
 *     least DECLINE_BPS below where it was 30 bars ago (a real 30-minute
 *     decline, not noise), and it fires when the 5-bar return crosses up
 *     through BOUNCE_BPS (the decline has ended and price is rising again:
 *     the short return is at or above the threshold now and was below it
 *     one bar ago). The bot buys the recovery, not the fall: it never
 *     catches a falling knife, it only enters once short momentum has
 *     turned positive.
 *   - Holding: ride the recovery with a fixed take-profit
 *     (TAKE_PROFIT_BPS above the entry close) and a trailing stop
 *     (TRAIL_BPS below the peak close since entry) so a reversal cannot
 *     give the gain back. Sell on either, or after MAX_HOLD_BARS,
 *     whichever comes first. One order per reply at most; fills land at
 *     the next bar's open (4 bps fee, 2 bps slippage, constant-product
 *     impact), so every signal is judged on closes the bot has seen.
 *
 * This is a bounce design, not a dip-buying or a breakout design: the
 * entry needs a decline first AND a turn up, and the exit is a fixed
 * target plus a trailing stop. Deterministic: no randomness, no wall
 * clock, no network, no files. The only state is the close history and
 * the entry/peak/hold record. Two runs on the same data produce the same
 * orders. Runs on plain Node 22, stdlib only.
 */

const readline = require("readline");

const SYMBOL = "CBBTC";

// Strategy parameters (chosen by grid-searching the frozen dev window;
// see BACKTEST_REPORT.md for the search and the robustness checks).
const DECLINE_BARS = 30; // bars for the decline that sets up the bounce
const DECLINE_BPS = 30; // buy setup: close this far below 30 bars ago
const BOUNCE_BARS = 5; // bars for the short return that confirms the turn
const BOUNCE_BPS = 20; // buy when the short return crosses up through this
const TAKE_PROFIT_BPS = 200; // sell once up this much on the entry close
const TRAIL_BPS = 120; // trailing stop below the peak close since entry
const MAX_HOLD_BARS = 360; // sell after this many bars even without a stop
const MAX_SLIPPAGE_BPS = 200;

class VBounceBot {
  constructor() {
    this.closes = []; // close prices in dollars, per bar
    this.cash = 0; // micro-USDC, from the latest account
    this.qty = 0; // asset qty units held, from the latest account
    this.entry = null; // close at entry, dollars
    this.peak = null; // highest close since entry, dollars
    this.barsHeld = 0; // bars since the current position opened
    this.orderNo = 0;
    this.batchesSeen = 0;
    this.warmupBars = 0;
    this.minNotional = 1000000; // $1 in micro-USDC
  }

  onHello(msg) {
    const cap = msg.capital || {};
    this.cash =
      cap.quote_units !== undefined && cap.quote_units !== null
        ? Number(cap.quote_units)
        : 1000000000;
    const fees = msg.fees || {};
    if (fees.min_notional_quote_units !== undefined) {
      this.minNotional = Number(fees.min_notional_quote_units);
    }
    this.warmupBars = Number(msg.warmup_bars || 0);
  }

  nextId(side) {
    this.orderNo += 1;
    return side + "-" + this.orderNo;
  }

  decide() {
    const n = this.closes.length;
    if (n <= DECLINE_BARS + 2 || this.batchesSeen <= this.warmupBars) return [];
    const close = this.closes[n - 1];
    if (this.qty === 0) {
      this.entry = null;
      this.peak = null;
      this.barsHeld = 0;
      const declineBps =
        (close / this.closes[n - 1 - DECLINE_BARS] - 1.0) * 10000;
      const shortNow =
        (close / this.closes[n - 1 - BOUNCE_BARS] - 1.0) * 10000;
      const shortPrev =
        (this.closes[n - 2] / this.closes[n - 2 - BOUNCE_BARS] - 1.0) *
        10000;
      const bounced =
        shortNow >= BOUNCE_BPS && shortPrev < BOUNCE_BPS;
      if (
        declineBps <= -DECLINE_BPS &&
        bounced &&
        this.cash >= this.minNotional
      ) {
        this.entry = close;
        this.peak = close;
        this.barsHeld = 0;
        return [
          {
            side: "buy",
            client_id: this.nextId("buy"),
            symbol: SYMBOL,
            notional_quote_units: String(this.cash),
            max_slippage_bps: MAX_SLIPPAGE_BPS,
          },
        ];
      }
      return [];
    }
    // Holding: update the peak, then check take-profit / trailing stop / hold cap.
    this.barsHeld += 1;
    if (close > this.peak) this.peak = close;
    const gainBps = (close / this.entry - 1.0) * 10000;
    const trailBps = (this.peak / close - 1.0) * 10000;
    if (
      gainBps >= TAKE_PROFIT_BPS ||
      trailBps >= TRAIL_BPS ||
      this.barsHeld >= MAX_HOLD_BARS
    ) {
      return [
        {
          side: "sell",
          client_id: this.nextId("sell"),
          symbol: SYMBOL,
          qty: String(this.qty),
          max_slippage_bps: MAX_SLIPPAGE_BPS,
        },
      ];
    }
    return [];
  }

  onBatch(msg) {
    this.batchesSeen += 1;
    const bars = msg.bars || [];
    let bar = null;
    for (const b of bars) {
      if (b.symbol === SYMBOL) {
        bar = b;
        break;
      }
    }
    if (bar !== null) this.closes.push(Number(bar.c) / 100000);
    const account = msg.account || {};
    if (account.cash_quote_units !== undefined && account.cash_quote_units !== null) {
      this.cash = Number(account.cash_quote_units);
    }
    this.qty = 0;
    for (const pos of account.positions || []) {
      if (pos.symbol === SYMBOL) this.qty = Number(pos.qty || 0);
    }
    if (bar === null) return [];
    return this.decide();
  }
}

function main() {
  const bot = new VBounceBot();
  const rl = readline.createInterface({ input: process.stdin, terminal: false });
  rl.on("line", (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const msg = JSON.parse(trimmed);
    if (msg.type === "hello") {
      bot.onHello(msg);
    } else if (msg.type === "batch") {
      const orders = bot.onBatch(msg);
      process.stdout.write(
        JSON.stringify({ type: "reply", seq: msg.seq, orders }) + "\n"
      );
    } else if (msg.type === "done") {
      rl.close();
      process.exit(0);
    }
  });
}

main();
