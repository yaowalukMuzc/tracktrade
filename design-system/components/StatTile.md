# StatTile

One metric: label, value, one line of context. Used in Performance (P/L metrics and Behavior metrics), Playbook setup stats, Mentor dashboard.

- Classes: `tt-stat` > `tt-stat__label` (`caption`, may lead with a 16px icon) + `tt-stat__value` (`num-lg`, tabular) + `tt-stat__delta`.
- Color the value only when it IS a P/L (`tt-pnl--up/--down`). Rates, scores and counts stay `ink`.
- Grid: 2 columns at 375px, 4 at ≥768px. Keep P/L tiles and Behavior tiles in separate sections (F-18).
