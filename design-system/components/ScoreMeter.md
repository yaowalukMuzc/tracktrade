# ScoreMeter

0–100 scores: Plan Adherence (and its Price & Size / Rules / Management parts) and Trade Quality.

- Ring: `tt-ring` with `--v` (0–100) and optional `--c`; the number sits in the middle. Bar: `tt-meter` > `tt-meter__top` (label + `<b>` value) + `tt-meter__track` > `tt-meter__fill` (`width:%`).
- Color by score, never by P/L: ≥ 80 `brand-600`, 60–79 `warning`, < 60 `loss`.
- Always print the number; the fill is decoration.
