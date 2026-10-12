# Timeline

Trade lifecycle in order (F-12 AC4): analysis → plan (and revisions) → executions/modifications → emotion logs → review.

- Structure: `tt-tl` > `tt-tl__item` with `tt-tl__dot` (16px Hugeicon; `--brand` analysis/plan, neutral executions, `--loss` risk-increasing modification or breach, `--warning` revision after entry, `--profit` review), `tt-tl__time` (account timezone), `tt-tl__title`, optional `tt-tl__body`.
- Consumer provides: ordered events with type, time, title, detail.
