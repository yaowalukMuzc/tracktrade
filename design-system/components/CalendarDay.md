# CalendarDay

A day cell in the Trading Calendar (F-17): date, P/L ($ or R per the toggle), trade count, mood, adherence/quality badge.

- Classes: `tt-cal` (7-column grid, `tt-cal__dow` headers) > `tt-day` + `--win` (`profit-100`) / `--loss` (`loss-100`) / `--today` (2px `brand-600` outline) / `--out` (other month).
- Inside: `tt-day__n` (date + optional mood icon), `tt-day__pnl` (sign always), count, `tt-day__marks` (adherence dot: `brand-600` ≥ 80, `warning` 60–79, `loss` < 60; quality grade letter).
- Tap opens the Day sheet (trades + journal for that day). Weeks start Sunday (TH) or Monday (EN locale).
