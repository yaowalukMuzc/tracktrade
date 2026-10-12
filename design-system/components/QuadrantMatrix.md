# QuadrantMatrix

Quality × Outcome 2×2 (principle 1: Quality ≠ P/L). Rows = quality (grade ≥ B is Good), columns = outcome.

- Structure: `tt-quad` with axis labels and four `tt-quad__cell--gw|gl|bw|bl`; each cell shows the label and count (or %).
- Top stripe colors: `q-good-win`, `q-good-loss`, `q-bad-win`, `q-bad-loss`. Good-Loss is blue on purpose — losing while following the plan is a success.
- Cells are tap targets that filter the trade list to that quadrant.
