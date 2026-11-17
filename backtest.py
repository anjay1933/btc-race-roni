"""Local replay of the make.fun bars protocol for the BTC race dev window.

Drives the REAL submitted bot (main.ts, Node 22) over stdin/stdout with the
exact agent-fun/bars-replay/v1 line protocol, and applies the documented
fill model: fills at the next bar's open, 4 bps fee, 2 bps modelled
slippage, constant-product impact vs the bar's open depth,
max_slippage_bps vs the latest close. Runs the bot twice and requires the
two order streams to match byte for byte (determinism), the way the server
grades it. Data: the FROZEN dev window of btc-race-24h-20261117-0603
(dataset in the kit next to this repo).
"""
import gzip
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(HERE), "btc-race-20261117-0603-kit",
                   "btc-race-24h-20261117-0603-kit")
BOT = os.path.join(HERE, "main.ts")

BARS = [json.loads(line) for line in gzip.open(os.path.join(KIT, "dataset/bars/CBBTC.ndjson.gz"), "rt")]


def hello_msg():
    return {"type": "hello", "protocol": "agent-fun/bars-replay/v1", "seed": "1",
            "symbols": [{"symbol": "CBBTC", "mint": "cbbtcf3aa214zXHbiAZQwf4122FBYbraNdFqgw4iMij",
                         "price_scale": 5, "qty_scale": 8}],
            "capital": {"quote": "USDC", "quote_scale": 6, "quote_units": "1000000000"},
            "bar_interval": "1m", "first_close_ms": BARS[0]["t"],
            "caps": {"max_open_positions": 1, "max_orders_per_bar": 16, "max_weight_bps": 10000,
                     "shorts": False, "leverage": False},
            "fees": {"fee_bps": 4, "slippage_bps": 2, "min_notional_quote_units": "1000000"},
            "warmup_bars": 0}


def run_once(bars=None):
    if bars is None:
        bars = BARS
    proc = subprocess.Popen(["node", BOT], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    proc.stdin.write(json.dumps(hello_msg()) + "\n")
    proc.stdin.flush()
    cash = 1000000000
    qty = 0
    cost = 0
    pending = []
    prev_close = None
    trades = 0
    fees = 0
    peak = cash
    maxdd = 0.0
    order_stream = []
    trade_log = []
    for k, bar in enumerate(bars):
        o = int(bar["o"])
        c = int(bar["c"])
        o_depth = int(bar["o_depth"][0])
        fills = []
        for order in pending:
            cid = order.get("client_id", "x")
            if order["side"] == "buy":
                n = int(order["notional_quote_units"])
                if n > cash:
                    fills.append({"client_id": cid, "status": "rejected", "reason": "insufficient_cash"})
                    continue
                fee = n * 4 // 10000
                a = n - fee
                slipped = o * 10002 // 10000
                fill_price = slipped * (o_depth + a) // o_depth
                if prev_close is not None and fill_price > prev_close * (10000 + int(order["max_slippage_bps"])) // 10000:
                    fills.append({"client_id": cid, "status": "rejected", "reason": "max_slippage"})
                    continue
                q = a * 10 ** 7 // fill_price
                if q <= 0:
                    fills.append({"client_id": cid, "status": "rejected", "reason": "zero_amount"})
                    continue
                cash -= n
                qty += q
                cost += n
                fees += fee
                trades += 1
                fills.append({"client_id": cid, "status": "filled", "qty": str(q), "price": str(fill_price)})
                trade_log.append((k, "BUY", round(fill_price / 1e5, 2), round(n / 1e6, 2)))
            else:
                q = int(order["qty"])
                if q > qty:
                    fills.append({"client_id": cid, "status": "rejected", "reason": "insufficient_position"})
                    continue
                val = q * o // 10 ** 7
                slipped = o * 9998 // 10000
                fill_price = slipped * o_depth // (o_depth + val)
                if prev_close is not None and fill_price < prev_close * (10000 - int(order["max_slippage_bps"])) // 10000:
                    fills.append({"client_id": cid, "status": "rejected", "reason": "max_slippage"})
                    continue
                gross = q * fill_price // 10 ** 7
                fee = gross * 4 // 10000
                cash += gross - fee
                qty -= q
                cost = cost * qty // (qty + q) if qty > 0 else 0
                fees += fee
                trades += 1
                fills.append({"client_id": cid, "status": "filled", "qty": str(q), "price": str(fill_price)})
                trade_log.append((k, "SELL", round(fill_price / 1e5, 2), round(gross / 1e6, 2)))
        positions = []
        if qty > 0:
            positions.append({"symbol": "CBBTC", "qty": str(qty), "cost_quote_units": str(cost)})
        equity = cash + (qty * c // 10 ** 7 if qty else 0)
        peak = max(peak, equity)
        maxdd = max(maxdd, (peak - equity) / peak)
        account = {"cash_quote_units": str(cash), "positions": positions,
                   "equity_quote_units": str(equity)}
        batch = {"type": "batch", "seq": k, "t": bar["t"],
                 "bars": [dict(bar, symbol="CBBTC")], "fills": fills, "account": account}
        proc.stdin.write(json.dumps(batch) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(f"bot exited early at batch {k}")
        reply = json.loads(line)
        assert reply["type"] == "reply" and reply["seq"] == k, f"bad reply at {k}: {line[:200]}"
        orders = reply["orders"]
        order_stream.append(json.dumps(orders, sort_keys=True))
        pending = orders
        prev_close = c
    if qty > 0:
        c = int(bars[-1]["c"])
        d = int(bars[-1]["c_depth"][0])
        val = qty * c // 10 ** 7
        slipped = c * 9998 // 10000
        fill_price = slipped * d // (d + val)
        gross = qty * fill_price // 10 ** 7
        fee = gross * 4 // 10000
        cash += gross - fee
        fees += fee
        trades += 1
        trade_log.append((len(bars) - 1, "FLATTEN", round(fill_price / 1e5, 2), round(gross / 1e6, 2)))
        qty = 0
    proc.stdin.write(json.dumps({"type": "done", "seq": len(bars),
                                 "account": {"cash_quote_units": str(cash), "positions": [],
                                             "equity_quote_units": str(cash)}}) + "\n")
    proc.stdin.flush()
    proc.stdin.close()
    rc = proc.wait(timeout=60)
    assert rc == 0, f"bot exited with code {rc}"
    pnl = (cash - 1000000000) / 1e6
    return {"pnl_usd": round(pnl, 2), "trades": trades,
            "fees_usd": round(fees / 1e6, 2), "maxdd_pct": round(maxdd * 100, 2),
            "orders": order_stream, "trade_log": trade_log}


if __name__ == "__main__":
    r1 = run_once()
    r2 = run_once()
    deterministic = r1["orders"] == r2["orders"]
    print("run 1:", {k: r1[k] for k in ("pnl_usd", "trades", "fees_usd", "maxdd_pct")})
    print("run 2:", {k: r2[k] for k in ("pnl_usd", "trades", "fees_usd", "maxdd_pct")})
    print("deterministic (identical order streams):", deterministic)
    for k, side, price, amt in r1["trade_log"]:
        print(f"  bar {k} ({6 + k // 60:02d}:{k % 60:02d} UTC) {side} @ ${price:.2f} ${amt:.2f}")
