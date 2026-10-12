# MoodScale

1–10 rating for mood and confidence (pre-trade in the plan, in-trade prompt, post-trade review, daily mood).

- Structure: `tt-mood` > label + `tt-mood__scale` of ten `tt-mood__step` buttons (values ≤ selection `--fill`, the selection `--on`) + `tt-mood__ends` with the Hugeicons `sad-01` / `smile`.
- Consumer provides: value, phase (pre/in/post/daily), label. Pair it with emotion Chips below.
- Numbers are always visible — no emoji-only scales.
