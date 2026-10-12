# TradeCard

One position in a list (Trades, Calendar day sheet, Playbook detail, Mentor review queue).

- Structure: `tt-trade` > `tt-trade__sym` (symbol + direction badge) · `tt-trade__right` (PnL) · `tt-trade__meta` (open time, hold time, session, setup, source) · `tt-trade__scores` (adherence, grade, quadrant, review state).
- Consumer provides: position summary, adherence %, grade, quadrant, review status, `pnl_visibility`.
- Quadrant label colors: Good-Win `q-good-win`, Good-Loss `q-good-loss` (blue — a good trade), Bad-Win `q-bad-win`, Bad-Loss `q-bad-loss`.
- The whole card is the tap target → Trade detail.
