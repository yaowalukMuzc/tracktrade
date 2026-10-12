# PlanLock

Shows that a plan is locked (F-06 AC4): lock time, short `lock_hash`, revision number. The only edit path is "แก้ไข (สร้าง revision)", which opens a sheet that requires a reason.

- Structure: `tt-lock` > `tt-lock__icon` (`square-lock-02` on `brand-600`) + text + secondary small Button.
- After entry, a revision is flagged `changed_after_entry` and shown as a `warning` badge "แก้หลังเข้าเทรด".
