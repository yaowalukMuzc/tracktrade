# PnL

Every money or R result. Color is never the only signal: always print the sign (`+` / `−` U+2212) and, where space allows, the arrow icon.

- Classes: `tt-pnl` + `--up` (`profit`) / `--down` (`loss`) / `--flat` (`ink-muted`, break-even). Pair with a type style: `display` (hero), `num-lg` (tiles), `num` (lists), `num-sm` (calendar).
- `tt-pnl__r` appends R next to money in `ink-muted`.
- Consumer provides: value, currency, R, and the viewer's `pnl_visibility`. In `r_only` mentor views render R only — never a `$` value (F-22 AC2).
- Format: thousands separators, 2 decimals for money, 1–2 for R. P/L is NEVER used to color quality or adherence.
