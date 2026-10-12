# Badge

Small read-only status label. Not clickable.

| Meaning | Class |
| --- | --- |
| Plan `draft` / `expired` | `tt-badge` (neutral) |
| Plan `locked` | `tt-badge--solid` |
| Plan `triggered` | `tt-badge--brand` |
| Plan `closed` | `tt-badge--outline` |
| Plan `skipped` / `missed`, `is_unplanned`, `match_status=pending`, "รอรีวิว" | `tt-badge--warning` |
| Plan `invalidated`, rule breach | `tt-badge--loss` |
| Direction | `tt-badge--long` / `tt-badge--short` (always the word, never color alone) |
| Plan tier, Pro feature | `tt-badge--gold` |
| Source (MT5 · cTrader · OCR · Manual) | `tt-badge--outline` |

Quality grade uses `tt-grade--A…D`: A `profit`, B `brand`, C `warning`, D `loss`. Grade ≥ B counts as "good" in the quadrant (F-14 AC4).
