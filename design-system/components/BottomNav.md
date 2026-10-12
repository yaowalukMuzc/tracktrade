# BottomNav

Mobile primary navigation (< 1024px): exactly five items — วันนี้ (Today), ปฏิทิน (Calendar), เทรด (Trades), สถิติ (Performance), เพิ่มเติม (More).

- Classes: `tt-nav` > `tt-nav__item` (24px Hugeicon + 11px label; `--on` = `brand-600` with a 3px top indicator). `tt-nav__dot` marks pending work (trades waiting for review/match).
- ≥ 1024px the same five destinations move to a 240px left sidebar; "More" expands into Playbook, AI Coach, News, Alerts, Accounts, Mentorship, Settings.
- Respect `safe-area-inset-bottom`; `z-nav`.
