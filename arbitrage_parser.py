 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a//dev/null b/arbitrage_parser.py
index 0000000000000000000000000000000000000000..b33bb82db936a7e7c67d70b774fd6fcff8e96519 100644
--- a//dev/null
+++ b/arbitrage_parser.py
@@ -0,0 +1,206 @@
+import argparse
+import ccxt
+import requests
+
+# List of centralized exchanges to query
+CEFI_EXCHANGES = [
+    "binance", "bybit", "mexc", "kucoin", "gate", "coinex",
+    "huobi", "bitget", "bingx", "bitmart"
+]
+
+# Default symbols to inspect when none are provided
+DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDC"]
+
+# Token address mapping for 1inch on Ethereum mainnet
+INCH_ADDRESSES = {
+    "BTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
+    "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
+    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
+}
+
+# Token decimals for 1inch
+INCH_DECIMALS = {
+    "BTC": 8,
+    "ETH": 18,
+    "USDT": 6,
+}
+
+# Token mint mapping for Jupiter (Solana)
+JUPITER_MINTS = {
+    "SOL": "So11111111111111111111111111111111111111112",
+    "USDC": "EPjFWdd5AufqSSqeM2qVw2fChwxhKMPhnT7SqDfjaap",
+}
+
+JUPITER_DECIMALS = {
+    "SOL": 9,
+    "USDC": 6,
+}
+
+
+def get_cex_prices(symbol: str) -> dict:
+    """Fetch last traded price for a symbol from multiple centralized exchanges."""
+    prices = {}
+    for exchange_id in CEFI_EXCHANGES:
+        try:
+            exchange = getattr(ccxt, exchange_id)()
+            exchange.load_markets()
+            ticker = exchange.fetch_ticker(symbol)
+            prices[exchange_id] = ticker["last"]
+        except Exception:
+            prices[exchange_id] = None
+    return prices
+
+
+def get_1inch_price(symbol: str, amount: float = 1.0) -> float | None:
+    """Get price for a pair using the 1inch aggregator."""
+    base, quote = symbol.split("/")
+    if base not in INCH_ADDRESSES or quote not in INCH_ADDRESSES:
+        return None
+    from_addr = INCH_ADDRESSES[base]
+    to_addr = INCH_ADDRESSES[quote]
+    from_dec = INCH_DECIMALS[base]
+    to_dec = INCH_DECIMALS[quote]
+    raw_amount = int(amount * (10 ** from_dec))
+    url = "https://api.1inch.io/v5.0/1/quote"
+    params = {
+        "fromTokenAddress": from_addr,
+        "toTokenAddress": to_addr,
+        "amount": raw_amount,
+    }
+    try:
+        resp = requests.get(url, params=params, timeout=10)
+        resp.raise_for_status()
+        data = resp.json()
+        out_amount = int(data["toTokenAmount"]) / (10 ** to_dec)
+        return out_amount / amount
+    except Exception:
+        return None
+
+
+def get_jupiter_price(symbol: str, amount: float = 1.0) -> float | None:
+    """Get price for a pair using the Jupiter aggregator on Solana."""
+    base, quote = symbol.split("/")
+    if base not in JUPITER_MINTS or quote not in JUPITER_MINTS:
+        return None
+    base_dec = JUPITER_DECIMALS[base]
+    quote_dec = JUPITER_DECIMALS[quote]
+    raw_amount = int(amount * (10 ** base_dec))
+    url = "https://quote-api.jup.ag/v6/quote"
+    params = {
+        "inputMint": JUPITER_MINTS[base],
+        "outputMint": JUPITER_MINTS[quote],
+        "amount": raw_amount,
+    }
+    try:
+        resp = requests.get(url, params=params, timeout=10)
+        resp.raise_for_status()
+        data = resp.json()
+        out_amount = int(data["outAmount"]) / (10 ** quote_dec)
+        return out_amount / amount
+    except Exception:
+        return None
+
+
+def get_futures_data(symbol: str) -> dict:
+    """Fetch perpetual futures prices and funding rates."""
+    futures = {}
+    for exchange_id in CEFI_EXCHANGES:
+        try:
+            exchange = getattr(ccxt, exchange_id)()
+            if exchange.has.get("swap"):
+                exchange.options["defaultType"] = "swap"
+                exchange.load_markets()
+                ticker = exchange.fetch_ticker(symbol)
+                funding = None
+                if exchange.has.get("fetchFundingRate"):
+                    try:
+                        fr = exchange.fetch_funding_rate(symbol)
+                        funding = fr.get("fundingRate")
+                    except Exception:
+                        funding = None
+                futures[exchange_id] = {
+                    "price": ticker["last"],
+                    "funding": funding,
+                }
+            else:
+                futures[exchange_id] = None
+        except Exception:
+            futures[exchange_id] = None
+    return futures
+
+
+def analyse_symbol(symbol: str) -> dict | None:
+    """Return pricing information and spread for a symbol."""
+    prices = get_cex_prices(symbol)
+    prices["1inch"] = get_1inch_price(symbol)
+    jup_price = get_jupiter_price(symbol)
+    if jup_price is not None:
+        prices["jupiter"] = jup_price
+
+    valid = {k: v for k, v in prices.items() if v is not None}
+    if not valid:
+        return None
+
+    min_ex = min(valid, key=valid.get)
+    max_ex = max(valid, key=valid.get)
+    spread = (valid[max_ex] - valid[min_ex]) / valid[min_ex] if valid[min_ex] else 0
+
+    futures = get_futures_data(symbol)
+    valid_futures = {k: v for k, v in futures.items() if v is not None}
+    return {
+        "buy_exchange": min_ex,
+        "buy_price": valid[min_ex],
+        "sell_exchange": max_ex,
+        "sell_price": valid[max_ex],
+        "all_prices": valid,
+        "spread": spread,
+        "futures": valid_futures,
+    }
+
+
+def display_opportunity(symbol: str, info: dict) -> None:
+    """Pretty-print an arbitrage opportunity."""
+    print(f"{symbol}: {info['spread']*100:.2f}% spread")
+    print(f"  Best buy: {info['buy_exchange']} at {info['buy_price']:.8f}")
+    print(f"  Best sell: {info['sell_exchange']} at {info['sell_price']:.8f}")
+    print("  All prices:")
+    for ex, price in sorted(info["all_prices"].items(), key=lambda item: item[1]):
+        print(f"    {ex:10s} {price}")
+
+    futures = info["futures"]
+    if futures:
+        print("  Futures prices and funding rates:")
+        for ex, data in futures.items():
+            funding = data["funding"]
+            rate = f"{funding:.6f}" if funding is not None else "n/a"
+            print(f"    {ex:10s} {data['price']} (funding {rate})")
+
+
+def main():
+    parser = argparse.ArgumentParser(description="Crypto arbitrage price checker")
+    parser.add_argument("symbols", nargs="*", help="Trading pair symbols, e.g. BTC/USDT")
+    parser.add_argument(
+        "--threshold",
+        type=float,
+        default=1.0,
+        help="Minimum spread percentage to display",
+    )
+    args = parser.parse_args()
+
+    symbols = args.symbols or DEFAULT_SYMBOLS
+    threshold = args.threshold / 100.0
+    found = False
+    for sym in symbols:
+        info = analyse_symbol(sym)
+        if info is None:
+            print(f"No price data available for {sym}")
+            continue
+        if info["spread"] >= threshold:
+            display_opportunity(sym, info)
+            found = True
+    if not found:
+        print("No opportunities above threshold")
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)
