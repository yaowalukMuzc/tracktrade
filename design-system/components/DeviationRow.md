# DeviationRow

One plan-vs-actual deviation (F-13 AC5): name, expected → actual, cost in $ and R, mapped dimension.

- Structure: `tt-dev` > `tt-dev__name` (16px icon + type), `tt-dev__cost` (`loss`, sign always), `tt-dev__ea` ("Plan X → Actual Y", tabular), dimension Badge with a `dim-*` swatch.
- Consumer provides: `deviations` rows; in `r_only` show R cost only.
