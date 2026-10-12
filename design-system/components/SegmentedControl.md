# SegmentedControl

Switches between 2–4 views of the same data: period (เดือนนี้/ทั้งปี/ทั้งหมด), unit ($/R), view (การ์ด/ตาราง).

- Classes: `tt-seg` > `tt-seg__item` (`--on` for the selected one); `tt-seg--block` stretches items full width.
- Consumer provides: options, selected value, `role="tablist"` semantics. The selection persists per viewer (e.g. $/R toggle).
- When `pnl_visibility = r_only` (mentor view) hide the $/R control and show R only.
