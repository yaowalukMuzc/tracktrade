# Button

Use **primary** (Lavender `brand-600` fill, dark `on-brand` text) once per screen for the action the screen exists for — "ล็อกแผน", "บันทึกรีวิว", "ยืนยันเทรด".

- Classes: `tt-btn` + `tt-btn--primary | --secondary | --ghost | --danger`; sizes `--sm` (36px), default (44px, the minimum touch target), `--lg` (52px, sticky bottom CTA); `--block` for full width on mobile.
- Consumer provides: label (verb first, Thai or English per locale), optional leading Hugeicon at 20px (16px on `--sm`), `disabled` state with the reason in the label or helper ("Lock (checklist 3/4)").
- `tt-iconbtn` is the 40px square icon button for app-bar actions; always give it an `aria-label`. `--active` marks a toggled tool (AI Coach, drawing tool).
- Danger is only for destructive, irreversible actions (delete account, revoke mentor). Never use red for "Sell" — directions use `tt-badge--long/--short`.

Tailwind: `inline-flex items-center gap-2 h-11 px-4 rounded-md font-semibold bg-brand-600 text-on-brand hover:bg-brand-hover`.
