# Field

A labelled input, select or textarea. Label sits above the control (`tt-label`, `ink-muted`); required fields mark `*` in `loss`.

- Classes: `tt-field` > `tt-label` + control (`tt-input`, `tt-select`, `tt-textarea`) + optional `tt-help`.
- Prices, lots, % and R use `tt-input--num` (right-aligned, tabular) inside `tt-input-wrap` with a `tt-suffix` unit (USD, %, R, lot).
- States: `tt-input--error` + `tt-help--error` for validation; `tt-input--lowconf` + `tt-help--warn` for OCR fields with low confidence (F-09 AC3).
- Consumer provides: label text via i18n, value, validation message, unit suffix. Controls are 44px high; borders use `border-strong` (3:1).
- Two columns at ≥ 360px for paired values (Entry/SL, TP/Risk%); one column for text.
