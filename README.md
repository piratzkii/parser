 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index 35a1abeef1d57f43c761606f27cc9c2f618bd9a4..3e07bb44aa5307e0417388638ce20cfe691af6fd 100644
--- a/README.md
+++ b/README.md
@@ -1,2 +1,30 @@
 # parser
-Arbitration
+
+Utility to compare token prices across several crypto exchanges and DEX aggregators.
+The tool also reports perpetual futures prices and their funding rates when
+available.
+
+## Installation
+
+```bash
+pip install -r requirements.txt
+```
+
+## Usage
+
+```bash
+python arbitrage_parser.py
+```
+
+By default the script checks a few popular pairs and reports only those where
+the spread between the best buy and best sell price exceeds 1%.
+
+Use custom symbols or tweak the threshold like so:
+
+```bash
+python arbitrage_parser.py BTC/USDT ETH/USDT --threshold 0.5
+```
+
+The tool queries multiple centralized exchanges via the `ccxt` library, asks
+1inch and Jupiter aggregators when token data is available, and fetches funding
+rates for perpetual futures markets.
 
EOF
)
