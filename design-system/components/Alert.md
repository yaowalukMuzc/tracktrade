# Alert

Inline banner and alert-center row: rule breaches (F-20), pre-news warnings (F-21), pending matches, sync errors.

- Classes: `tt-alert` (info, brand) / `--loss` (breach, error) / `--warning` (news, near-limit, pending) / `--profit` (success) / `--gold` (Pro). Lead with a 20px Hugeicon (`alert-02`, `news-01`, `information-circle`, `plug-01`); `tt-alert__title` + `tt-alert__body`.
- Consumer provides: type, severity, title, body, account, time, link target. Real-time alerts arrive as a toast using the same styles on `surface-raised` + `shadow-lg`, `z-toast`.
